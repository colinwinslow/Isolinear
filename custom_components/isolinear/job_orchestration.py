"""Config-entry-scoped job orchestration scaffold for the Isolinear integration."""

from __future__ import annotations

import base64
import binascii
import json
import re
import threading
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from ._paths import load_schema_document, schema_path
from .artifact_serving import prepare_png_artifact, remove_png_artifact, write_png_artifact
from .const import DOMAIN, INTEGRATION_COMMAND_TYPES
from .entity_catalog import DATA_ENTITY_CATALOG, DATA_ENTITY_CATALOG_SETUP
from .history_retrieval import (
    DATA_HISTORY_RETRIEVAL,
    classify_series_kind,
    retrieve_approved_history,
    validate_history_series_collection_contract,
)
from .in_process_renderer import (
    IN_PROCESS_RENDERER_NAME,
    first_real_vertical_slice_enabled,
    render_in_process_chart,
)
from .job_state import (
    DATA_JOB_STATE,
    JobStateSnapshotValidationError,
    _validate_json_schema,
    append_validated_job_snapshot,
    handle_job_state_ws_command,
    store_validated_job_snapshot,
    validate_job_snapshot_contract,
)
from .model_provider import (
    get_model_provider_planner,
    load_entity_selector_schema,
    load_planner_result_schema,
    planner_client_metadata,
)
from .worker_renderer import (
    build_worker_transport_request,
    get_worker_render_client,
    redacted_worker_transport_request,
    worker_client_metadata,
    worker_client_token,
)


DATA_JOB_ORCHESTRATION = "job_orchestration"
DATA_JOB_ORCHESTRATION_SETUP = "job_orchestration_setup"
DATA_JOB_ORCHESTRATION_TIME_RANGE = "job_orchestration_default_time_range"
ARTIFACT_METADATA_SCHEMA_PATH = (
    schema_path("integration-artifact-metadata.schema.json")
)
RENDER_PLAN_SCHEMA_PATH = (
    schema_path("integration-render-plan.schema.json")
)
MODEL_PROVIDER_PLAN_SCHEMA_PATH = (
    schema_path("integration-model-provider-plan.schema.json")
)
MODEL_PROVIDER_RETRY_POLICY_SCHEMA_PATH = (
    schema_path("integration-model-provider-retry-policy.schema.json")
)
WORKER_DISPATCH_SCHEMA_PATH = (
    schema_path("integration-worker-dispatch.schema.json")
)
WORKER_PROGRESS_SCHEMA_PATH = (
    schema_path("integration-worker-progress.schema.json")
)
WORKER_RETRY_POLICY_SCHEMA_PATH = (
    schema_path("integration-worker-retry-policy.schema.json")
)
WORKER_TRANSPORT_FAILURE_CLASSIFICATION_SCHEMA_PATH = (
    schema_path("integration-worker-transport-failure-classification.schema.json")
)
WORKER_TRANSPORT_REQUEST_SCHEMA_PATH = (
    schema_path("worker-transport-request.schema.json")
)
RENDER_REQUEST_SCHEMA_PATH = schema_path("render-request.schema.json")
RENDER_RESULT_SCHEMA_PATH = schema_path("render-result.schema.json")
PLANNER_RESULT_SCHEMA_PATH = schema_path("planner-result.schema.json")
CHART_SPEC_SCHEMA_PATH = schema_path("chart-spec.schema.json")
THREAD_LOCK_TYPE = type(threading.Lock())
ARTIFACT_SNAPSHOT_LOCKS_GUARD = threading.Lock()

# ADR-0025 R3: coarse phase labels surfaced via progress.stage / state_label
# while the model runs, derived from which model call is active.
SELECT_ENTITY_PHASE_LABEL = "Selecting entities…"
PLAN_CHART_PHASE_LABEL = "Planning chart…"
# ADR-0025 D2/D3: per-job slot holding the latest sanitized, length-capped
# reasoning tail (+ active phase) so concurrent in-progress polls can surface it.
DATA_LIVE_REASONING = "live_reasoning"

ENTITY_ID_IN_PROMPT = re.compile(r"\b[a-z0-9_]+\.[a-z0-9_]+\b")
FORBIDDEN_WORKER_PROGRESS_TEXT = re.compile(
    r"\bBearer\s+\S+|access_token|home_assistant_token|long_lived_access_token|worker_token",
    re.IGNORECASE,
)
FORBIDDEN_MODEL_PROVIDER_FAILURE_TEXT = re.compile(
    r"\bBearer\s+\S+|access_token|home_assistant_token|long_lived_access_token|"
    r"worker_token|model_provider_token|ollama_api_key",
    re.IGNORECASE,
)
ARTIFACT_SOURCE_PROGRESS_STAGES = {
    "job_orchestration_scaffold_ready",
    "job_orchestration_clarification_continuation_ready",
    "job_orchestration_retry_continuation_ready",
}

NO_JOB_ORCHESTRATION_CALLS = {
    "worker_called": False,
    "model_provider_called": False,
    "home_assistant_history_called": False,
    "semantic_memory_called": False,
    "home_assistant_service_or_state_mutation_called": False,
    "token_generated": False,
    "chart_artifact_written": False,
    "chart_rendering_called": False,
    "durable_storage_written": False,
    "retry_behavior_called": False,
    "subscription_progress_streaming_called": False,
    "worker_progress_streaming_called": False,
    "automatic_progress_task_called": False,
    "job_orchestration_called": False,
    "model_provider_retry_policy_bookkeeping_written": False,
}

MAX_WORKER_PROGRESS_EVENTS = 5
WORKER_RENDERER_NAME = "worker_renderer"


def apply_live_reasoning(
    snapshot: dict[str, Any], slot: dict[str, Any] | None
) -> dict[str, Any]:
    """Return a copy of an in-progress planning snapshot with live reasoning.

    ADR-0025 D2/D3/R3: when a poll returns the in-progress active-planning
    snapshot, the integration injects the per-job live-reasoning ``slot`` — the
    coarse phase label as ``progress.stage`` / ``state_label`` and the
    sanitized, capped tail as ``progress.reasoning`` (omitted when empty). The
    returned snapshot is re-validated against the schema before use; the stored
    snapshot is never mutated, so reasoning never lands on a persisted snapshot
    (D4). When ``slot`` is None the snapshot is returned unchanged.
    """
    if not slot:
        return snapshot
    updated = deepcopy(snapshot)
    progress = updated.setdefault("progress", {})
    stage = slot.get("stage")
    if stage:
        progress["stage"] = stage
        updated["state_label"] = stage
    text = slot.get("text") or ""
    if text:
        progress["reasoning"] = text
    else:
        progress.pop("reasoning", None)
    validation = validate_job_snapshot_contract(updated)
    if not validation["accepted"]:
        # A bad reasoning injection must never corrupt the poll; fall back to the
        # plain snapshot (graceful degradation, D6).
        return snapshot
    return updated


def _live_reasoning_store(store: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return store.setdefault(DATA_LIVE_REASONING, {})


def _live_reasoning_slot(store: dict[str, Any], job_id: str) -> dict[str, Any] | None:
    return _live_reasoning_store(store).get(job_id)


def _set_live_reasoning(
    store: dict[str, Any], job_id: str, *, stage: str, text: str
) -> None:
    _live_reasoning_store(store)[job_id] = {"stage": stage, "text": text}


def _clear_live_reasoning(store: dict[str, Any], job_id: str) -> None:
    _live_reasoning_store(store).pop(job_id, None)


def _live_reasoning_callback(
    store: dict[str, Any], job_id: str, *, stage: str
):
    """Build an on_reasoning callback that writes the slot for one model call."""

    def _on_reasoning(text: str) -> None:
        _set_live_reasoning(store, job_id, stage=stage, text=text)

    return _on_reasoning


def _call_planner_with_optional_reasoning(
    method: Any,
    request: dict[str, Any],
    *,
    result_schema: dict[str, Any] | None,
    on_reasoning: Any | None,
) -> dict[str, Any]:
    """Call a planner method, passing on_reasoning when the method accepts it.

    ADR-0025 streaming is additive (D6): planners that predate the callback (and
    test doubles that don't accept it) are called the original way. We pass the
    callback only when requested and the method advertises the keyword.
    """
    if on_reasoning is not None:
        try:
            return method(request, result_schema=result_schema, on_reasoning=on_reasoning)
        except TypeError:
            # Older planner signature without on_reasoning — fall back (no live
            # reasoning, plain planning state).
            pass
    return method(request, result_schema=result_schema)


def setup_job_orchestration(hass: Any, entry: Any) -> dict[str, Any]:
    """Initialize one config-entry-scoped orchestration scaffold store."""
    entry_id = getattr(entry, "entry_id", "scaffold-entry")
    store = ensure_job_orchestration_store(hass, entry_id)
    approved_items = _approved_catalog_items(hass, entry_id)
    result = {
        "accepted": True,
        "code": "job_orchestration_ready",
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "enabled": bool(approved_items),
        "approved_entity_ids": [item["entity_id"] for item in approved_items],
        "store": summarize_job_orchestration_store(store),
        "orchestration": job_orchestration_side_effects(
            approved_entity_catalog_read=True,
        ),
    }
    hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})[DATA_JOB_ORCHESTRATION_SETUP] = result
    return result


def ensure_job_orchestration_store(hass: Any, entry_id: str) -> dict[str, Any]:
    """Return the in-memory orchestration store for one config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    entry_data = domain_data.setdefault(entry_id, {})
    store = entry_data.get(DATA_JOB_ORCHESTRATION)
    if isinstance(store, dict):
        store.setdefault("next_progress_event_number", 1)
        store.setdefault("progress_events", {})
        store.setdefault("progress_event_order", [])
        store.setdefault("latest_progress_event", None)
        store.setdefault("next_artifact_number", 1)
        store.setdefault("artifact_metadata", {})
        store.setdefault("artifact_order", [])
        store.setdefault("latest_artifact", None)
        store.setdefault("artifact_by_job_id", {})
        store.setdefault("next_render_plan_number", 1)
        store.setdefault("render_plans", {})
        store.setdefault("render_plan_order", [])
        store.setdefault("latest_render_plan", None)
        store.setdefault("render_plan_by_job_id", {})
        store.setdefault("next_model_provider_plan_number", 1)
        store.setdefault("model_provider_plans", {})
        store.setdefault("model_provider_plan_order", [])
        store.setdefault("latest_model_provider_plan", None)
        store.setdefault("model_provider_plan_by_job_id", {})
        store.setdefault("next_model_provider_retry_policy_number", 1)
        store.setdefault("model_provider_retry_policies", {})
        store.setdefault("model_provider_retry_policy_order", [])
        store.setdefault("latest_model_provider_retry_policy", None)
        store.setdefault("model_provider_retry_policy_ids_by_job_id", {})
        store.setdefault("next_worker_dispatch_number", 1)
        store.setdefault("worker_dispatches", {})
        store.setdefault("worker_dispatch_order", [])
        store.setdefault("latest_worker_dispatch", None)
        store.setdefault("worker_dispatch_by_job_id", {})
        store.setdefault("next_worker_progress_event_number", 1)
        store.setdefault("worker_progress_events", {})
        store.setdefault("worker_progress_event_order", [])
        store.setdefault("latest_worker_progress_event", None)
        store.setdefault("worker_progress_event_ids_by_job_id", {})
        store.setdefault("next_worker_retry_policy_number", 1)
        store.setdefault("worker_retry_policies", {})
        store.setdefault("worker_retry_policy_order", [])
        store.setdefault("latest_worker_retry_policy", None)
        store.setdefault("worker_retry_policy_ids_by_job_id", {})
        store.setdefault("next_worker_transport_failure_classification_number", 1)
        store.setdefault("worker_transport_failure_classifications", {})
        store.setdefault("worker_transport_failure_classification_order", [])
        store.setdefault("latest_worker_transport_failure_classification", None)
        store.setdefault("worker_transport_failure_classification_ids_by_job_id", {})
        store.setdefault("_artifact_snapshot_locks", {})
        return store

    store = {
        "entry_id": entry_id,
        "next_run_number": 1,
        "runs": {},
        "run_order": [],
        "latest_run": None,
        "next_progress_event_number": 1,
        "progress_events": {},
        "progress_event_order": [],
        "latest_progress_event": None,
        "next_artifact_number": 1,
        "artifact_metadata": {},
        "artifact_order": [],
        "latest_artifact": None,
        "artifact_by_job_id": {},
        "next_render_plan_number": 1,
        "render_plans": {},
        "render_plan_order": [],
        "latest_render_plan": None,
        "render_plan_by_job_id": {},
        "next_model_provider_plan_number": 1,
        "model_provider_plans": {},
        "model_provider_plan_order": [],
        "latest_model_provider_plan": None,
        "model_provider_plan_by_job_id": {},
        "next_model_provider_retry_policy_number": 1,
        "model_provider_retry_policies": {},
        "model_provider_retry_policy_order": [],
        "latest_model_provider_retry_policy": None,
        "model_provider_retry_policy_ids_by_job_id": {},
        "next_worker_dispatch_number": 1,
        "worker_dispatches": {},
        "worker_dispatch_order": [],
        "latest_worker_dispatch": None,
        "worker_dispatch_by_job_id": {},
        "next_worker_progress_event_number": 1,
        "worker_progress_events": {},
        "worker_progress_event_order": [],
        "latest_worker_progress_event": None,
        "worker_progress_event_ids_by_job_id": {},
        "next_worker_retry_policy_number": 1,
        "worker_retry_policies": {},
        "worker_retry_policy_order": [],
        "latest_worker_retry_policy": None,
        "worker_retry_policy_ids_by_job_id": {},
        "next_worker_transport_failure_classification_number": 1,
        "worker_transport_failure_classifications": {},
        "worker_transport_failure_classification_order": [],
        "latest_worker_transport_failure_classification": None,
        "worker_transport_failure_classification_ids_by_job_id": {},
        "_artifact_snapshot_locks": {},
    }
    entry_data[DATA_JOB_ORCHESTRATION] = store
    return store


def has_enabled_job_orchestration(hass: Any, entry_id: str) -> bool:
    """Return whether a config entry has enough approved catalog data to orchestrate start."""
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    setup = entry_data.get(DATA_JOB_ORCHESTRATION_SETUP) if isinstance(entry_data, dict) else None
    return isinstance(setup, dict) and setup.get("enabled") is True


def has_job_orchestration_setup(hass: Any, entry_id: str) -> bool:
    """Return whether a config entry completed the orchestration setup boundary."""
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    setup = entry_data.get(DATA_JOB_ORCHESTRATION_SETUP) if isinstance(entry_data, dict) else None
    return isinstance(setup, dict)


def _defer_history_to_planning(
    *,
    store: dict[str, Any],
    command: dict[str, Any],
    job: dict[str, Any],
    catalog_items: list[dict[str, Any]],
    requested_entity_ids: list[str],
    progress_stage: str,
    result_code: str,
    accepted_code: str,
    warnings_prefix: list[str],
    extra_checks: list[dict[str, str]] | None = None,
    clarification_answer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Stage approved entities and defer history retrieval to the planning path.

    For the first real vertical slice the time window is resolved by the model
    during planning, so history cannot be fetched at job/start (ADR-0020). This
    appends the artifact-source planning snapshot without reading history; the
    snapshot path resolves the window, retrieves history, and renders.
    """
    checks = [
        {"name": "integration_job_state_scaffold", "status": "pass"},
        {"name": "approved_entity_catalog", "status": "pass"},
        *(extra_checks or []),
        {"name": "approved_history_retrieval", "status": "deferred_to_planning"},
        {"name": "model_provider", "status": "not_called"},
        {"name": "worker", "status": "not_called"},
        {"name": "chart_rendering", "status": "not_called"},
    ]
    snapshot = append_validated_job_snapshot(
        job,
        status="planning",
        state_label="Ready",
        message=(
            "Approved entities are selected. The model resolves the time window and "
            "approved history is retrieved during planning."
        ),
        progress_stage=progress_stage,
        progress_message="Approved entities are staged for model planning.",
        validation_status="pass",
        validation_summary="The orchestration selected approved entities for first-real-slice planning.",
        validation_checks=checks,
        entities=_snapshot_entities(catalog_items, requested_entity_ids),
        warnings=[*warnings_prefix, "history_retrieval_deferred_to_planning"],
    )
    run_kwargs: dict[str, Any] = {}
    if clarification_answer is not None:
        run_kwargs["clarification_answer"] = clarification_answer
    run = _record_run(
        store,
        command=command,
        job=job,
        result_code=result_code,
        requested_entity_ids=requested_entity_ids,
        history_entity_ids=[],
        snapshot_ids=_snapshot_ids(job),
        **run_kwargs,
    )
    return _accepted(
        accepted_code,
        command,
        snapshot,
        run=run,
        approved_entity_catalog_read=True,
        home_assistant_history_read=False,
        history_retrieval_written=False,
        job_state_written=True,
        job_orchestration_written=True,
    )


def handle_job_orchestration_start_ws_command(hass: Any, command: dict[str, Any]) -> dict[str, Any]:
    """Compose job state, approved catalog, and approved history for job/start."""
    if command["type"] != INTEGRATION_COMMAND_TYPES["start_job"]:
        return _orchestration_rejection("unsupported_job_orchestration_command")

    entry_id = command["config_entry_id"]
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    entry = entry_data.get("entry")
    if entry is None:
        return _orchestration_rejection("unknown_config_entry")

    store = ensure_job_orchestration_store(hass, entry_id)
    start_result = handle_job_state_ws_command(hass, command)
    if not start_result["accepted"]:
        return start_result

    job = _job_for_result(hass, entry_id, start_result)
    if job is None:
        return _orchestration_rejection("unknown_job", job_id=start_result.get("job_id"))

    catalog_items = _approved_catalog_items(hass, entry_id)
    selection = select_prompt_entity_ids(command["prompt"], catalog_items)
    if not selection["accepted"] and selection["code"] == "entity_selection_requires_clarification":
        d2 = _run_model_entity_selection(
            hass, entry_id, command["prompt"], catalog_items,
            candidate_items=selection.get("candidate_items", catalog_items),
            store=store, job_id=job["job_id"],
        )
        if d2["accepted"]:
            selection = d2
    if not selection["accepted"]:
        missing_entity_ids = []
        run_result_code = selection["code"]
        if selection["code"] == "entity_selection_requires_clarification":
            snapshot = _append_clarification_snapshot(
                job,
                message=selection["message"],
                options=selection["options"],
            )
            result_code = "job_orchestration_scaffold_clarification_needed"
        else:
            failure = _catalog_selection_failure(hass, entry_id, selection)
            missing_entity_ids = failure.get("missing_entity_ids", [])
            run_result_code = failure["code"]
            snapshot = _append_failed_snapshot(
                job,
                code=failure["code"],
                stage="approved_entity_catalog",
                message=failure["message"],
                checks=[
                    {"name": "integration_job_state_scaffold", "status": "pass"},
                    {"name": "approved_entity_catalog", "status": "fail"},
                    {"name": "approved_history_retrieval", "status": "not_run"},
                    {"name": "model_provider", "status": "not_called"},
                    {"name": "worker", "status": "not_called"},
                ],
            )
            result_code = "job_orchestration_scaffold_failed"
        run = _record_run(
            store,
            command=command,
            job=job,
            result_code=run_result_code,
            requested_entity_ids=[],
            history_entity_ids=[],
            snapshot_ids=_snapshot_ids(job),
            missing_entity_ids=missing_entity_ids,
        )
        return _accepted(
            result_code,
            command,
            snapshot,
            run=run,
            approved_entity_catalog_read=True,
            job_state_written=True,
            job_orchestration_written=True,
        )

    requested_entity_ids = selection["entity_ids"]
    rejected_entity_ids = [
        entity_id
        for entity_id in requested_entity_ids
        if entity_id not in {item["entity_id"] for item in catalog_items}
    ]
    if first_real_vertical_slice_enabled(hass, entry_id) and not rejected_entity_ids:
        return _defer_history_to_planning(
            store=store,
            command=command,
            job=job,
            catalog_items=catalog_items,
            requested_entity_ids=requested_entity_ids,
            progress_stage="job_orchestration_scaffold_ready",
            result_code="approved_entities_ready_for_planning",
            accepted_code="job_orchestration_scaffold_ready",
            warnings_prefix=["first_real_vertical_slice"],
        )

    time_range = _default_history_time_range(hass)

    if not rejected_entity_ids:
        _append_fetching_history_snapshot(job, requested_entity_ids)

    history_result = retrieve_approved_history(
        hass,
        entry,
        entity_ids=requested_entity_ids,
        start=time_range["start"],
        end=time_range["end"],
    )
    if not history_result["accepted"]:
        failed_snapshot = _append_failed_snapshot(
            job,
            code=history_result["code"],
            stage="approved_history_retrieval",
            message=_failure_message(history_result),
            checks=[
                {"name": "integration_job_state_scaffold", "status": "pass"},
                {
                    "name": "approved_entity_catalog",
                    "status": "fail" if history_result["code"] == "entity_not_in_approved_catalog" else "pass",
                },
                {"name": "approved_history_retrieval", "status": "fail"},
                {"name": "model_provider", "status": "not_called"},
                {"name": "worker", "status": "not_called"},
            ],
        )
        run = _record_run(
            store,
            command=command,
            job=job,
            result_code=history_result["code"],
            requested_entity_ids=requested_entity_ids,
            history_entity_ids=[],
            snapshot_ids=_snapshot_ids(job),
            rejected_entity_ids=history_result.get("rejected_entity_ids"),
            missing_entity_ids=history_result.get("missing_entity_ids"),
        )
        return _accepted(
            "job_orchestration_scaffold_failed",
            command,
            failed_snapshot,
            run=run,
            history_result=history_result,
            approved_entity_catalog_read=True,
            home_assistant_history_read=history_result["orchestration"].get("home_assistant_history_read", False),
            history_retrieval_written=False,
            job_state_written=True,
            job_orchestration_written=True,
        )

    ready_snapshot = append_validated_job_snapshot(
        job,
        status="planning",
        state_label="Ready",
        message=(
            "Approved catalog and history are ready for a later planning packet; "
            "model and worker calls are not implemented yet."
        ),
        progress_stage="job_orchestration_scaffold_ready",
        progress_message="Approved history is staged for future planning.",
        validation_status="pass",
        validation_summary="The orchestration scaffold composed approved catalog, history, and job state.",
        validation_checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "approved_entity_catalog", "status": "pass"},
            {"name": "approved_history_retrieval", "status": "pass"},
            {"name": "model_provider", "status": "not_called"},
            {"name": "worker", "status": "not_called"},
            {"name": "chart_rendering", "status": "not_called"},
        ],
        entities=_snapshot_entities(catalog_items, requested_entity_ids),
        warnings=[
            "job_orchestration_scaffold",
            "model_provider_not_called",
            "worker_not_called",
            "chart_rendering_not_started",
        ],
    )
    run = _record_run(
        store,
        command=command,
        job=job,
        result_code="approved_history_ready",
        requested_entity_ids=requested_entity_ids,
        history_entity_ids=[series["entity_id"] for series in history_result["history_series"]],
        snapshot_ids=_snapshot_ids(job),
    )
    return _accepted(
        "job_orchestration_scaffold_ready",
        command,
        ready_snapshot,
        run=run,
        history_result=history_result,
        approved_entity_catalog_read=True,
        home_assistant_history_read=True,
        history_retrieval_written=True,
        job_state_written=True,
        job_orchestration_written=True,
    )


def handle_job_orchestration_clarification_answer_ws_command(
    hass: Any,
    command: dict[str, Any],
) -> dict[str, Any]:
    """Resume a pending approved-entity clarification through approved history retrieval."""
    if command["type"] != INTEGRATION_COMMAND_TYPES["answer_clarification"]:
        return _orchestration_rejection("unsupported_job_orchestration_command")

    entry_id = command["config_entry_id"]
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    entry = entry_data.get("entry")
    if entry is None:
        return _orchestration_rejection("unknown_config_entry")

    store = ensure_job_orchestration_store(hass, entry_id)
    job = _job_for_command(hass, entry_id, command)
    if job is None:
        return _orchestration_rejection("unknown_job", job_id=command.get("job_id"))

    pending = _pending_clarification_for_job(job)
    if not pending["accepted"]:
        return _reject_clarification_answer(
            store,
            command=command,
            job=job,
            code=pending["code"],
        )

    clarification = pending["clarification"]
    if command["question_id"] != clarification["question_id"]:
        return _reject_clarification_answer(
            store,
            command=command,
            job=job,
            code="clarification_question_mismatch",
        )

    selected = _selected_clarification_entity(hass, entry_id, clarification, command["option_id"])
    if not selected["accepted"]:
        return _reject_clarification_answer(
            store,
            command=command,
            job=job,
            code=selected["code"],
            approved_entity_catalog_read=selected.get("approved_entity_catalog_read", False),
        )

    selected_entity_id = selected["entity_id"]
    catalog_items = selected["catalog_items"]
    job.setdefault("clarification_answers", []).append(
        {
            "question_id": command["question_id"],
            "option_id": command["option_id"],
            "remember": command["remember"],
            "entity_id": selected_entity_id,
        }
    )
    _append_clarification_answer_accepted_snapshot(
        job,
        entity_id=selected_entity_id,
        remember=command["remember"],
    )
    if first_real_vertical_slice_enabled(hass, entry_id):
        return _defer_history_to_planning(
            store=store,
            command=command,
            job=job,
            catalog_items=catalog_items,
            requested_entity_ids=[selected_entity_id],
            progress_stage="job_orchestration_clarification_continuation_ready",
            result_code="clarification_entities_ready_for_planning",
            accepted_code="job_orchestration_clarification_continuation_ready",
            warnings_prefix=[
                "job_orchestration_clarification_continuation_scaffold",
                "first_real_vertical_slice",
            ],
            extra_checks=[{"name": "clarification_answer", "status": "pass"}],
            clarification_answer=_clarification_answer_summary(command, selected_entity_id),
        )
    _append_fetching_history_snapshot(job, [selected_entity_id])

    time_range = _default_history_time_range(hass)
    history_result = retrieve_approved_history(
        hass,
        entry,
        entity_ids=[selected_entity_id],
        start=time_range["start"],
        end=time_range["end"],
    )
    if not history_result["accepted"]:
        failed_snapshot = _append_failed_snapshot(
            job,
            code=history_result["code"],
            stage="approved_history_retrieval",
            message=_failure_message(history_result),
            checks=[
                {"name": "integration_job_state_scaffold", "status": "pass"},
                {"name": "approved_entity_catalog", "status": "pass"},
                {"name": "clarification_answer", "status": "pass"},
                {"name": "approved_history_retrieval", "status": "fail"},
                {"name": "model_provider", "status": "not_called"},
                {"name": "worker", "status": "not_called"},
            ],
        )
        run = _record_run(
            store,
            command=command,
            job=job,
            result_code=history_result["code"],
            requested_entity_ids=[selected_entity_id],
            history_entity_ids=[],
            snapshot_ids=_snapshot_ids(job),
            missing_entity_ids=history_result.get("missing_entity_ids"),
            rejected_entity_ids=history_result.get("rejected_entity_ids"),
            clarification_answer=_clarification_answer_summary(command, selected_entity_id),
        )
        return _accepted(
            "job_orchestration_clarification_continuation_failed",
            command,
            failed_snapshot,
            run=run,
            history_result=history_result,
            approved_entity_catalog_read=True,
            home_assistant_history_read=history_result["orchestration"].get("home_assistant_history_read", False),
            history_retrieval_written=False,
            job_state_written=True,
            job_orchestration_written=True,
        )

    ready_snapshot = append_validated_job_snapshot(
        job,
        status="planning",
        state_label="Ready",
        message=(
            "Clarification answer selected an approved entity and history is ready "
            "for a later planning packet; model and worker calls are not implemented yet."
        ),
        progress_stage="job_orchestration_clarification_continuation_ready",
        progress_message="Approved clarification history is staged for future planning.",
        validation_status="pass",
        validation_summary=(
            "The clarification continuation scaffold composed approved catalog, "
            "the selected option, history, and job state."
        ),
        validation_checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "approved_entity_catalog", "status": "pass"},
            {"name": "clarification_answer", "status": "pass"},
            {"name": "approved_history_retrieval", "status": "pass"},
            {"name": "model_provider", "status": "not_called"},
            {"name": "worker", "status": "not_called"},
            {"name": "chart_rendering", "status": "not_called"},
        ],
        entities=_snapshot_entities(catalog_items, [selected_entity_id]),
        warnings=[
            "job_orchestration_clarification_continuation_scaffold",
            "model_provider_not_called",
            "worker_not_called",
            "chart_rendering_not_started",
        ],
    )
    run = _record_run(
        store,
        command=command,
        job=job,
        result_code="clarification_approved_history_ready",
        requested_entity_ids=[selected_entity_id],
        history_entity_ids=[series["entity_id"] for series in history_result["history_series"]],
        snapshot_ids=_snapshot_ids(job),
        clarification_answer=_clarification_answer_summary(command, selected_entity_id),
    )
    return _accepted(
        "job_orchestration_clarification_continuation_ready",
        command,
        ready_snapshot,
        run=run,
        history_result=history_result,
        approved_entity_catalog_read=True,
        home_assistant_history_read=True,
        history_retrieval_written=True,
        job_state_written=True,
        job_orchestration_written=True,
    )


def handle_job_orchestration_retry_ws_command(hass: Any, command: dict[str, Any]) -> dict[str, Any]:
    """Resume a retryable failed scaffold job through approved history retrieval."""
    if command["type"] != INTEGRATION_COMMAND_TYPES["retry_job"]:
        return _orchestration_rejection("unsupported_job_orchestration_command")

    entry_id = command["config_entry_id"]
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    entry = entry_data.get("entry")
    if entry is None:
        return _orchestration_rejection("unknown_config_entry")

    store = ensure_job_orchestration_store(hass, entry_id)
    job = _job_for_command(hass, entry_id, command)
    if job is None:
        return _orchestration_rejection("unknown_job", job_id=command.get("job_id"))

    retryable = _retryable_failure_for_job(job)
    if not retryable["accepted"]:
        run = _record_run(
            store,
            command=command,
            job=job,
            result_code=retryable["code"],
            requested_entity_ids=[],
            history_entity_ids=[],
            snapshot_ids=_snapshot_ids(job),
        )
        return _orchestration_rejection(
            retryable["code"],
            job_id=command.get("job_id"),
            run=run,
            orchestration=job_orchestration_side_effects(job_orchestration_written=True),
        )

    _append_retry_accepted_snapshot(job, failed_snapshot=retryable["snapshot"])
    catalog_items = _approved_catalog_items(hass, entry_id)
    selection = select_prompt_entity_ids(job["prompt"], catalog_items)
    if not selection["accepted"] and selection["code"] == "entity_selection_requires_clarification":
        d2 = _run_model_entity_selection(
            hass, entry_id, job["prompt"], catalog_items,
            candidate_items=selection.get("candidate_items", catalog_items),
            store=store, job_id=job["job_id"],
        )
        if d2["accepted"]:
            selection = d2
    if not selection["accepted"]:
        missing_entity_ids = []
        run_result_code = selection["code"]
        if selection["code"] == "entity_selection_requires_clarification":
            snapshot = _append_clarification_snapshot(
                job,
                message=selection["message"],
                options=selection["options"],
            )
            result_code = "job_orchestration_retry_continuation_clarification_needed"
        else:
            failure = _catalog_selection_failure(hass, entry_id, selection)
            missing_entity_ids = failure.get("missing_entity_ids", [])
            run_result_code = failure["code"]
            snapshot = _append_failed_snapshot(
                job,
                code=failure["code"],
                stage="approved_entity_catalog",
                message=failure["message"],
                checks=[
                    {"name": "integration_job_state_scaffold", "status": "pass"},
                    {"name": "retry_command", "status": "pass"},
                    {"name": "approved_entity_catalog", "status": "fail"},
                    {"name": "approved_history_retrieval", "status": "not_run"},
                    {"name": "model_provider", "status": "not_called"},
                    {"name": "worker", "status": "not_called"},
                ],
            )
            result_code = "job_orchestration_retry_continuation_failed"
        run = _record_run(
            store,
            command=command,
            job=job,
            result_code=run_result_code,
            requested_entity_ids=[],
            history_entity_ids=[],
            snapshot_ids=_snapshot_ids(job),
            missing_entity_ids=missing_entity_ids,
        )
        return _accepted(
            result_code,
            command,
            snapshot,
            run=run,
            approved_entity_catalog_read=True,
            job_state_written=True,
            job_orchestration_written=True,
            retry_behavior_called=True,
        )

    requested_entity_ids = selection["entity_ids"]
    rejected_entity_ids = [
        entity_id
        for entity_id in requested_entity_ids
        if entity_id not in {item["entity_id"] for item in catalog_items}
    ]
    if first_real_vertical_slice_enabled(hass, entry_id) and not rejected_entity_ids:
        return _defer_history_to_planning(
            store=store,
            command=command,
            job=job,
            catalog_items=catalog_items,
            requested_entity_ids=requested_entity_ids,
            progress_stage="job_orchestration_retry_continuation_ready",
            result_code="retry_entities_ready_for_planning",
            accepted_code="job_orchestration_retry_continuation_ready",
            warnings_prefix=[
                "job_orchestration_retry_continuation_scaffold",
                "first_real_vertical_slice",
            ],
            extra_checks=[{"name": "retry_command", "status": "pass"}],
        )

    time_range = _default_history_time_range(hass)

    if not rejected_entity_ids:
        _append_fetching_history_snapshot(job, requested_entity_ids)

    history_result = retrieve_approved_history(
        hass,
        entry,
        entity_ids=requested_entity_ids,
        start=time_range["start"],
        end=time_range["end"],
    )
    if not history_result["accepted"]:
        failed_snapshot = _append_failed_snapshot(
            job,
            code=history_result["code"],
            stage="approved_history_retrieval",
            message=_failure_message(history_result),
            checks=[
                {"name": "integration_job_state_scaffold", "status": "pass"},
                {"name": "retry_command", "status": "pass"},
                {
                    "name": "approved_entity_catalog",
                    "status": "fail" if history_result["code"] == "entity_not_in_approved_catalog" else "pass",
                },
                {"name": "approved_history_retrieval", "status": "fail"},
                {"name": "model_provider", "status": "not_called"},
                {"name": "worker", "status": "not_called"},
            ],
        )
        run = _record_run(
            store,
            command=command,
            job=job,
            result_code=history_result["code"],
            requested_entity_ids=requested_entity_ids,
            history_entity_ids=[],
            snapshot_ids=_snapshot_ids(job),
            rejected_entity_ids=history_result.get("rejected_entity_ids"),
            missing_entity_ids=history_result.get("missing_entity_ids"),
        )
        return _accepted(
            "job_orchestration_retry_continuation_failed",
            command,
            failed_snapshot,
            run=run,
            history_result=history_result,
            approved_entity_catalog_read=True,
            home_assistant_history_read=history_result["orchestration"].get("home_assistant_history_read", False),
            history_retrieval_written=False,
            job_state_written=True,
            job_orchestration_written=True,
            retry_behavior_called=True,
        )

    ready_snapshot = append_validated_job_snapshot(
        job,
        status="planning",
        state_label="Ready",
        message=(
            "Retry composed approved catalog and history for a later planning packet; "
            "model and worker calls are not implemented yet."
        ),
        progress_stage="job_orchestration_retry_continuation_ready",
        progress_message="Approved retry history is staged for future planning.",
        validation_status="pass",
        validation_summary=(
            "The retry continuation scaffold composed approved catalog, history, "
            "and existing job state."
        ),
        validation_checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "retry_command", "status": "pass"},
            {"name": "approved_entity_catalog", "status": "pass"},
            {"name": "approved_history_retrieval", "status": "pass"},
            {"name": "model_provider", "status": "not_called"},
            {"name": "worker", "status": "not_called"},
            {"name": "chart_rendering", "status": "not_called"},
        ],
        entities=_snapshot_entities(catalog_items, requested_entity_ids),
        warnings=[
            "job_orchestration_retry_continuation_scaffold",
            "model_provider_not_called",
            "worker_not_called",
            "chart_rendering_not_started",
        ],
    )
    run = _record_run(
        store,
        command=command,
        job=job,
        result_code="retry_approved_history_ready",
        requested_entity_ids=requested_entity_ids,
        history_entity_ids=[series["entity_id"] for series in history_result["history_series"]],
        snapshot_ids=_snapshot_ids(job),
    )
    return _accepted(
        "job_orchestration_retry_continuation_ready",
        command,
        ready_snapshot,
        run=run,
        history_result=history_result,
        approved_entity_catalog_read=True,
        home_assistant_history_read=True,
        history_retrieval_written=True,
        job_state_written=True,
        job_orchestration_written=True,
        retry_behavior_called=True,
    )


def handle_job_orchestration_subscribe_ws_command(
    hass: Any,
    command: dict[str, Any],
    *,
    message_id: int | str | None = None,
) -> dict[str, Any]:
    """Record a subscription and latest-snapshot progress event for one job."""
    if command["type"] != INTEGRATION_COMMAND_TYPES["subscribe_job"]:
        return _orchestration_rejection("unsupported_job_orchestration_command")

    entry_id = command["config_entry_id"]
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    if entry_data.get("entry") is None:
        return _orchestration_rejection("unknown_config_entry")

    store = ensure_job_orchestration_store(hass, entry_id)
    job = _job_for_command(hass, entry_id, command)
    if job is None:
        return _orchestration_rejection("unknown_job", job_id=command.get("job_id"))

    latest_snapshot = job.get("latest_snapshot")
    validation = validate_job_snapshot_contract(latest_snapshot)
    if not validation["accepted"]:
        result = _orchestration_rejection("invalid_integration_job_snapshot", job_id=command.get("job_id"))
        result["validation"] = validation
        return result

    subscription_result = handle_job_state_ws_command(hass, command, message_id=message_id)
    if not subscription_result["accepted"]:
        return subscription_result

    subscription = subscription_result["subscription"]
    progress_event = _record_progress_event(
        store,
        command=command,
        subscription=subscription,
        snapshot=subscription_result["snapshot"],
    )
    return _accepted_subscription(
        "job_orchestration_subscription_progress_recorded",
        command,
        subscription_result["snapshot"],
        subscription=subscription,
        progress_event=progress_event,
    )


def handle_job_orchestration_snapshot_ws_command(hass: Any, command: dict[str, Any]) -> dict[str, Any]:
    """Return the latest snapshot, creating scaffold artifact metadata when ready."""
    if command["type"] != INTEGRATION_COMMAND_TYPES["get_snapshot"]:
        return _orchestration_rejection("unsupported_job_orchestration_command")

    entry_id = command["config_entry_id"]
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    if entry_data.get("entry") is None:
        return _orchestration_rejection("unknown_config_entry")

    store = ensure_job_orchestration_store(hass, entry_id)
    job = _job_for_command(hass, entry_id, command)
    if job is None:
        return _orchestration_rejection("unknown_job", job_id=command.get("job_id"))

    latest_snapshot = job.get("latest_snapshot")
    validation = validate_job_snapshot_contract(latest_snapshot)
    if not validation["accepted"]:
        result = _orchestration_rejection("invalid_integration_job_snapshot", job_id=command.get("job_id"))
        result["validation"] = validation
        return result

    existing_artifact = _artifact_for_job(store, job["job_id"])
    existing_render_plan = _render_plan_for_job(store, job["job_id"])
    existing_model_provider_plan = _model_provider_plan_for_job(store, job["job_id"])
    existing_worker_dispatch = _worker_dispatch_for_job(store, job["job_id"])
    existing_worker_progress_events = _worker_progress_events_for_job(store, job["job_id"])
    if existing_artifact is not None and _is_artifact_complete_snapshot(latest_snapshot, existing_artifact):
        return _accepted_artifact_snapshot(
            "job_orchestration_artifact_snapshot_returned",
            command,
            latest_snapshot,
            artifact=existing_artifact,
            render_plan=existing_render_plan,
            model_provider_plan=existing_model_provider_plan,
            worker_dispatch=existing_worker_dispatch,
            worker_progress_events=existing_worker_progress_events,
            artifact_metadata_written=False,
            render_plan_written=False,
            model_provider_plan_written=False,
            worker_dispatch_written=False,
            worker_progress_written=False,
            worker_progress_streaming_called=False,
            model_provider_called=False,
            worker_called=False,
            chart_rendering_called=False,
            job_state_written=False,
            job_orchestration_written=False,
        )

    if not _is_artifact_source_snapshot(latest_snapshot):
        snapshot_result = handle_job_state_ws_command(hass, command)
        if not snapshot_result["accepted"]:
            return snapshot_result
        return _accepted_artifact_snapshot(
            "job_orchestration_snapshot_returned_without_artifact",
            command,
            snapshot_result["snapshot"],
            artifact=None,
            render_plan=existing_render_plan,
            model_provider_plan=existing_model_provider_plan,
            worker_dispatch=existing_worker_dispatch,
            worker_progress_events=existing_worker_progress_events,
            artifact_metadata_written=False,
            render_plan_written=False,
            model_provider_plan_written=False,
            worker_dispatch_written=False,
            worker_progress_written=False,
            worker_progress_streaming_called=False,
            model_provider_called=False,
            worker_called=False,
            chart_rendering_called=False,
            job_state_written=False,
            job_orchestration_written=False,
        )

    planning_lock = _artifact_snapshot_lock_for_job(store, job["job_id"])
    if not planning_lock.acquire(blocking=False):
        # ADR-0025 D2/D3: another poll is driving the model phase under the
        # single-flight lock. Surface the latest live reasoning tail (+ coarse
        # phase) on the transient in-progress snapshot the card sees this poll.
        in_progress_snapshot = apply_live_reasoning(
            latest_snapshot, _live_reasoning_slot(store, job["job_id"])
        )
        return _accepted_artifact_snapshot(
            "job_orchestration_artifact_snapshot_in_progress",
            command,
            in_progress_snapshot,
            artifact=existing_artifact,
            render_plan=existing_render_plan,
            model_provider_plan=existing_model_provider_plan,
            worker_dispatch=existing_worker_dispatch,
            worker_progress_events=existing_worker_progress_events,
            artifact_metadata_written=False,
            render_plan_written=False,
            model_provider_plan_written=False,
            worker_dispatch_written=False,
            worker_progress_written=False,
            worker_progress_streaming_called=False,
            model_provider_called=False,
            worker_called=False,
            chart_rendering_called=False,
            job_state_written=False,
            job_orchestration_written=False,
        )

    try:
        latest_snapshot = job.get("latest_snapshot")
        validation = validate_job_snapshot_contract(latest_snapshot)
        if not validation["accepted"]:
            result = _orchestration_rejection("invalid_integration_job_snapshot", job_id=command.get("job_id"))
            result["validation"] = validation
            return result

        existing_artifact = _artifact_for_job(store, job["job_id"])
        existing_render_plan = _render_plan_for_job(store, job["job_id"])
        existing_model_provider_plan = _model_provider_plan_for_job(store, job["job_id"])
        existing_worker_dispatch = _worker_dispatch_for_job(store, job["job_id"])
        existing_worker_progress_events = _worker_progress_events_for_job(store, job["job_id"])
        if existing_artifact is not None and _is_artifact_complete_snapshot(latest_snapshot, existing_artifact):
            return _accepted_artifact_snapshot(
                "job_orchestration_artifact_snapshot_returned",
                command,
                latest_snapshot,
                artifact=existing_artifact,
                render_plan=existing_render_plan,
                model_provider_plan=existing_model_provider_plan,
                worker_dispatch=existing_worker_dispatch,
                worker_progress_events=existing_worker_progress_events,
                artifact_metadata_written=False,
                render_plan_written=False,
                model_provider_plan_written=False,
                worker_dispatch_written=False,
                worker_progress_written=False,
                worker_progress_streaming_called=False,
                model_provider_called=False,
                worker_called=False,
                chart_rendering_called=False,
                job_state_written=False,
                job_orchestration_written=False,
            )

        if not _is_artifact_source_snapshot(latest_snapshot):
            snapshot_result = handle_job_state_ws_command(hass, command)
            if not snapshot_result["accepted"]:
                return snapshot_result
            return _accepted_artifact_snapshot(
                "job_orchestration_snapshot_returned_without_artifact",
                command,
                snapshot_result["snapshot"],
                artifact=None,
                render_plan=existing_render_plan,
                model_provider_plan=existing_model_provider_plan,
                worker_dispatch=existing_worker_dispatch,
                worker_progress_events=existing_worker_progress_events,
                artifact_metadata_written=False,
                render_plan_written=False,
                model_provider_plan_written=False,
                worker_dispatch_written=False,
                worker_progress_written=False,
                worker_progress_streaming_called=False,
                model_provider_called=False,
                worker_called=False,
                chart_rendering_called=False,
                job_state_written=False,
                job_orchestration_written=False,
            )

        return _record_artifact_snapshot_for_source(
            hass,
            command,
            entry_id=entry_id,
            store=store,
            job=job,
            source_snapshot=latest_snapshot,
        )
    finally:
        # ADR-0025 D4: the model phase for this poll has concluded (the terminal
        # complete/failed snapshot is now stored). The live reasoning is
        # ephemeral wait-feedback and is never written to the stored snapshot, so
        # discard the slot — the next poll surfaces the chart or failure card.
        _clear_live_reasoning(store, job["job_id"])
        planning_lock.release()


def _record_artifact_snapshot_for_source(
    hass: Any,
    command: dict[str, Any],
    *,
    entry_id: str,
    store: dict[str, Any],
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
) -> dict[str, Any]:
    planning_result = _record_artifact_and_render_plan(
        store,
        hass=hass,
        entry_id=entry_id,
        job=job,
        source_snapshot=source_snapshot,
    )
    if not planning_result["accepted"]:
        model_provider_failure_snapshot = _append_model_provider_failure_snapshot_from_planning_result(
            job,
            planning_result,
        )
        if model_provider_failure_snapshot is not None:
            return _accepted_artifact_snapshot(
                "job_orchestration_model_provider_failure_snapshot_recorded",
                command,
                model_provider_failure_snapshot,
                artifact=None,
                render_plan=None,
                model_provider_plan=None,
                worker_dispatch=None,
                artifact_metadata_written=False,
                render_plan_written=False,
                model_provider_plan_written=False,
                worker_dispatch_written=False,
                model_provider_called=planning_result.get("model_provider_called", False),
                worker_called=False,
                chart_rendering_called=False,
                job_state_written=True,
                job_orchestration_written=True,
                model_provider_retry_policy=planning_result.get("model_provider_retry_policy"),
                model_provider_retry_policy_written=(
                    planning_result.get("model_provider_retry_policy") is not None
                ),
            )
        worker_failure_snapshot = _append_worker_failure_snapshot_from_planning_result(
            job,
            planning_result,
        )
        if worker_failure_snapshot is not None:
            return _accepted_artifact_snapshot(
                "job_orchestration_worker_failure_snapshot_recorded",
                command,
                worker_failure_snapshot,
                artifact=None,
                render_plan=None,
                model_provider_plan=None,
                worker_dispatch=None,
                worker_progress_events=None,
                artifact_metadata_written=False,
                render_plan_written=False,
                model_provider_plan_written=False,
                worker_dispatch_written=False,
                worker_progress_written=False,
                worker_progress_streaming_called=planning_result.get("worker_progress_streaming_called", False),
                worker_retry_policy_written=planning_result.get("worker_retry_policy") is not None,
                worker_transport_failure_classification_written=(
                    planning_result.get("worker_transport_failure_classification") is not None
                ),
                model_provider_called=planning_result.get("model_provider_called", False),
                worker_called=planning_result.get("worker_called", False),
                chart_rendering_called=planning_result.get("chart_rendering_called", False),
                job_state_written=True,
                job_orchestration_written=True,
            )
        renderer_failure_snapshot = _append_in_process_renderer_failure_snapshot_from_planning_result(
            job,
            planning_result,
        )
        if renderer_failure_snapshot is not None:
            return _accepted_artifact_snapshot(
                "job_orchestration_in_process_renderer_failure_snapshot_recorded",
                command,
                renderer_failure_snapshot,
                artifact=None,
                render_plan=None,
                model_provider_plan=None,
                worker_dispatch=None,
                worker_progress_events=None,
                artifact_metadata_written=False,
                render_plan_written=False,
                model_provider_plan_written=False,
                worker_dispatch_written=False,
                worker_progress_written=False,
                worker_progress_streaming_called=False,
                model_provider_called=planning_result.get("model_provider_called", False),
                worker_called=False,
                chart_rendering_called=planning_result.get("chart_rendering_called", False),
                chart_artifact_written=False,
                job_state_written=True,
                job_orchestration_written=True,
            )
        history_failure_snapshot = _append_history_failure_snapshot_from_planning_result(
            job,
            planning_result,
        )
        if history_failure_snapshot is not None:
            return _accepted_artifact_snapshot(
                "job_orchestration_history_failure_snapshot_recorded",
                command,
                history_failure_snapshot,
                artifact=None,
                render_plan=None,
                model_provider_plan=None,
                worker_dispatch=None,
                worker_progress_events=None,
                artifact_metadata_written=False,
                render_plan_written=False,
                model_provider_plan_written=False,
                worker_dispatch_written=False,
                worker_progress_written=False,
                worker_progress_streaming_called=False,
                model_provider_called=planning_result.get("model_provider_called", False),
                worker_called=False,
                chart_rendering_called=False,
                job_state_written=True,
                job_orchestration_written=True,
            )
        result = _orchestration_rejection(
            planning_result["code"],
            job_id=command.get("job_id"),
            orchestration=planning_result.get("orchestration", job_orchestration_side_effects()),
        )
        result["validation"] = planning_result.get("validation")
        if "model_provider" in planning_result:
            result["model_provider"] = deepcopy(planning_result["model_provider"])
        if "worker" in planning_result:
            result["worker"] = deepcopy(planning_result["worker"])
        if "worker_retry_policy" in planning_result:
            result["worker_retry_policy"] = deepcopy(planning_result["worker_retry_policy"])
        return result

    artifact = planning_result["artifact"]
    render_plan = planning_result["render_plan"]
    model_provider_plan = planning_result.get("model_provider_plan")
    worker_dispatch = planning_result.get("worker_dispatch")
    worker_progress_events = planning_result.get("worker_progress_events") or []
    in_process_render = planning_result.get("in_process_render")
    try:
        complete_snapshot = _append_artifact_complete_snapshot(job, artifact, worker_dispatch=worker_dispatch)
    except JobStateSnapshotValidationError as exc:
        rollback = None
        if planning_result.get("chart_artifact_written"):
            rollback = remove_png_artifact(hass, entry_id, artifact_id=artifact["artifact_id"])
        _rollback_artifact_planning_records(
            store,
            artifact=artifact,
            render_plan=render_plan,
            model_provider_plan=model_provider_plan,
            worker_dispatch=worker_dispatch,
            worker_progress_events=worker_progress_events,
        )
        result = _orchestration_rejection(
            "invalid_integration_job_snapshot",
            job_id=command.get("job_id"),
            orchestration=job_orchestration_side_effects(
                model_provider_called=planning_result.get("model_provider_called", False),
                worker_called=planning_result.get("worker_called", False),
                chart_rendering_called=planning_result.get("chart_rendering_called", False),
                chart_artifact_written=False,
                artifact_metadata_bookkeeping_written=False,
                render_plan_bookkeeping_written=False,
                model_provider_plan_bookkeeping_written=False,
                worker_dispatch_bookkeeping_written=False,
                worker_progress_bookkeeping_written=False,
                worker_progress_streaming_called=planning_result.get("worker_progress_streaming_called", False),
                job_orchestration_written=True,
            ),
        )
        result["validation"] = exc.result
        if rollback is not None:
            result["artifact_rollback"] = rollback
        return result
    return _accepted_artifact_snapshot(
        "job_orchestration_artifact_storage_recorded",
        command,
        complete_snapshot,
        artifact=artifact,
        render_plan=render_plan,
        model_provider_plan=model_provider_plan,
        worker_dispatch=worker_dispatch,
        worker_progress_events=worker_progress_events,
        artifact_metadata_written=True,
        render_plan_written=True,
        model_provider_plan_written=model_provider_plan is not None,
        worker_dispatch_written=worker_dispatch is not None,
        worker_progress_written=bool(worker_progress_events),
        worker_progress_streaming_called=planning_result.get("worker_progress_streaming_called", False),
        in_process_render=in_process_render,
        model_provider_called=planning_result.get("model_provider_called", False),
        worker_called=planning_result.get("worker_called", False),
        chart_rendering_called=planning_result.get("chart_rendering_called", False),
        chart_artifact_written=planning_result.get("chart_artifact_written", False),
        job_state_written=True,
        job_orchestration_written=True,
    )


def _run_model_entity_selection(
    hass: Any,
    entry_id: str,
    prompt: str,
    catalog_items: list[dict[str, Any]],
    candidate_items: list[dict[str, Any]],
    *,
    store: dict[str, Any] | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    """Try model-driven entity selection for the residue path (ADR-0024 D2).

    Called when the deterministic fast-path cannot resolve (tie or zero
    matches). Returns an accepted selection with ``source: model_entity_selection``
    when the model picks a valid approved set, or a rejected result when the
    model abstains, the provider is absent, or the chosen IDs are off-allowlist.
    The caller falls through to user clarification on any rejection.
    """
    planner = get_model_provider_planner(hass, entry_id)
    if planner is None or not hasattr(planner, "select_entity"):
        return {"accepted": False, "code": "no_model_provider_for_entity_selection"}

    candidate_entity_ids = [item["entity_id"] for item in candidate_items]
    if not candidate_entity_ids:
        return {"accepted": False, "code": "no_candidates_for_entity_selection"}

    catalog_entity_ids = {item["entity_id"] for item in catalog_items}
    request = {
        "prompt": prompt,
        "candidate_entity_ids": candidate_entity_ids,
        "candidate_labels": {
            item["entity_id"]: item.get("friendly_name") or item["entity_id"]
            for item in candidate_items
        },
    }
    schema = load_entity_selector_schema(candidate_entity_ids)
    # ADR-0025 D1/D7: stream the selection thinking into the per-job live slot so
    # the wait-feedback covers this model call too. Only when streaming is
    # supported (callback accepted) and we have a job to attribute it to.
    on_reasoning = (
        _live_reasoning_callback(store, job_id, stage=SELECT_ENTITY_PHASE_LABEL)
        if store is not None and job_id is not None
        else None
    )
    result = _call_planner_with_optional_reasoning(
        planner.select_entity, request, result_schema=schema, on_reasoning=on_reasoning
    )
    if not result.get("accepted"):
        return {"accepted": False, "code": "model_entity_selection_provider_failure"}

    selection_result = result.get("selection_result")
    if not isinstance(selection_result, dict):
        return {"accepted": False, "code": "model_entity_selection_malformed_result"}

    if selection_result.get("status") != "entity_selected":
        return {"accepted": False, "code": "model_entity_selection_abstained"}

    chosen_ids = selection_result.get("entity_ids")
    if not isinstance(chosen_ids, list) or not chosen_ids:
        return {"accepted": False, "code": "model_entity_selection_empty_result"}

    candidate_set = set(candidate_entity_ids)
    invalid_ids = [
        eid for eid in chosen_ids
        if not isinstance(eid, str) or eid not in catalog_entity_ids or eid not in candidate_set
    ]
    if invalid_ids:
        return {"accepted": False, "code": "model_entity_selection_out_of_allowlist"}

    return {
        "accepted": True,
        "code": "accepted",
        "entity_ids": list(dict.fromkeys(eid for eid in chosen_ids if isinstance(eid, str))),
        "source": "model_entity_selection",
    }


def select_prompt_entity_ids(prompt: str, catalog_items: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministically select scaffold entity IDs from prompt text and catalog labels."""
    explicit_entity_ids = _unique(ENTITY_ID_IN_PROMPT.findall(prompt.lower()))
    if explicit_entity_ids:
        return {
            "accepted": True,
            "code": "accepted",
            "entity_ids": explicit_entity_ids,
            "source": "explicit_entity_id",
        }

    matches = [
        item
        for item in catalog_items
        if _catalog_item_matches_prompt(prompt, item)
    ]
    if len(matches) == 1:
        return {
            "accepted": True,
            "code": "accepted",
            "entity_ids": [matches[0]["entity_id"]],
            "source": "catalog_label",
        }
    if len(matches) > 1:
        # A fuzzy prompt that matches exactly one numeric series plus one or more
        # binary/categorical entities composes deterministically into a numeric
        # line + shaded overlays (ADR-0022 D4) rather than asking the user to
        # pick one. Any other multi-match (e.g. two numeric series) stays
        # ambiguous and clarifies.
        match_kinds = [(item, classify_series_kind(item)) for item in matches]
        numeric_matches = [item for item, kind in match_kinds if kind == "numeric"]
        binary_matches = [item for item, kind in match_kinds if kind == "binary_state"]
        non_numeric_matches = [item for item, kind in match_kinds if kind != "numeric"]
        # Binary-only overlay composition (ADR-0022 D4): one numeric primary plus
        # one or more binary entities. Categorical entities that happen to match
        # a shared token ("kitchen" matching both climate.kitchen_ecobee and
        # binary_sensor.kitchen_door) are noise matches — they don't block the
        # composite path. Only the numeric+binary pair is forwarded; the
        # categorical match is discarded.
        if len(numeric_matches) == 1 and binary_matches:
            return {
                "accepted": True,
                "code": "accepted",
                "entity_ids": [numeric_matches[0]["entity_id"]]
                + [item["entity_id"] for item in binary_matches],
                "source": "numeric_with_overlay",
            }
        # Specificity tie-break (ADR-0024 D1): when one candidate matches strictly
        # more of its distinctive tokens than every other, the prompt named it
        # ("kitchen door" → kitchen_door, not kitchen_ecobee). Selecting the
        # uniquely best-specified approved entity is not a silent guess (invariant
        # #1); a top-score tie is genuine ambiguity and still clarifies.
        scored = [(item, _catalog_item_match_score(prompt, item)) for item in matches]
        best_score = max(score for _, score in scored)
        top_matches = [item for item, score in scored if score == best_score]
        if len(top_matches) == 1:
            return {
                "accepted": True,
                "code": "accepted",
                "entity_ids": [top_matches[0]["entity_id"]],
                "source": "catalog_label_specificity",
            }
        return {
            "accepted": False,
            "code": "entity_selection_requires_clarification",
            "message": "Multiple approved entities match this question; choose one.",
            "options": [_clarification_option_for_item(item) for item in top_matches],
            "candidate_items": top_matches,
        }

    return {
        "accepted": False,
        "code": "entity_selection_requires_clarification" if catalog_items else "no_approved_entities_available",
        "message": (
            "Choose which approved entity Isolinear should use for this question."
            if catalog_items
            else "No approved entities are available for this config entry."
        ),
        "options": [_clarification_option_for_item(item) for item in catalog_items],
        "candidate_items": catalog_items,
    }


def summarize_job_orchestration_store(store: dict[str, Any]) -> dict[str, Any]:
    """Return an evidence-friendly orchestration store summary."""
    latest_run = store.get("latest_run")
    latest_progress_event = store.get("latest_progress_event")
    latest_artifact = store.get("latest_artifact")
    latest_render_plan = store.get("latest_render_plan")
    latest_model_provider_plan = store.get("latest_model_provider_plan")
    latest_model_provider_retry_policy = store.get("latest_model_provider_retry_policy")
    latest_worker_dispatch = store.get("latest_worker_dispatch")
    latest_worker_progress_event = store.get("latest_worker_progress_event")
    latest_worker_retry_policy = store.get("latest_worker_retry_policy")
    latest_worker_transport_failure_classification = store.get(
        "latest_worker_transport_failure_classification"
    )
    return {
        "entry_id": store.get("entry_id"),
        "run_count": len(store.get("run_order", [])),
        "run_ids": list(store.get("run_order", [])),
        "latest_job_id": latest_run.get("job_id") if isinstance(latest_run, dict) else None,
        "latest_result_code": latest_run.get("result_code") if isinstance(latest_run, dict) else None,
        "latest_requested_entity_ids": latest_run.get("requested_entity_ids", []) if isinstance(latest_run, dict) else [],
        "latest_history_entity_ids": latest_run.get("history_entity_ids", []) if isinstance(latest_run, dict) else [],
        "progress_event_count": len(store.get("progress_event_order", [])),
        "progress_event_ids": list(store.get("progress_event_order", [])),
        "latest_progress_event_id": (
            latest_progress_event.get("event_id") if isinstance(latest_progress_event, dict) else None
        ),
        "latest_progress_snapshot_id": (
            latest_progress_event.get("snapshot_id") if isinstance(latest_progress_event, dict) else None
        ),
        "artifact_count": len(store.get("artifact_order", [])),
        "artifact_ids": list(store.get("artifact_order", [])),
        "latest_artifact_id": latest_artifact.get("artifact_id") if isinstance(latest_artifact, dict) else None,
        "latest_artifact_job_id": latest_artifact.get("job_id") if isinstance(latest_artifact, dict) else None,
        "latest_artifact_source_snapshot_id": (
            latest_artifact.get("source_snapshot_id") if isinstance(latest_artifact, dict) else None
        ),
        "render_plan_count": len(store.get("render_plan_order", [])),
        "render_plan_ids": list(store.get("render_plan_order", [])),
        "latest_render_plan_id": (
            latest_render_plan.get("render_plan_id") if isinstance(latest_render_plan, dict) else None
        ),
        "latest_render_plan_job_id": (
            latest_render_plan.get("job_id") if isinstance(latest_render_plan, dict) else None
        ),
        "latest_render_plan_artifact_id": (
            latest_render_plan.get("artifact_id") if isinstance(latest_render_plan, dict) else None
        ),
        "model_provider_plan_count": len(store.get("model_provider_plan_order", [])),
        "model_provider_plan_ids": list(store.get("model_provider_plan_order", [])),
        "latest_model_provider_plan_id": (
            latest_model_provider_plan.get("provider_plan_id")
            if isinstance(latest_model_provider_plan, dict)
            else None
        ),
        "latest_model_provider_plan_job_id": (
            latest_model_provider_plan.get("job_id") if isinstance(latest_model_provider_plan, dict) else None
        ),
        "latest_model_provider_plan_source_snapshot_id": (
            latest_model_provider_plan.get("source_snapshot_id")
            if isinstance(latest_model_provider_plan, dict)
            else None
        ),
        "model_provider_retry_policy_count": len(store.get("model_provider_retry_policy_order", [])),
        "model_provider_retry_policy_ids": list(store.get("model_provider_retry_policy_order", [])),
        "latest_model_provider_retry_policy_id": (
            latest_model_provider_retry_policy.get("policy_id")
            if isinstance(latest_model_provider_retry_policy, dict)
            else None
        ),
        "latest_model_provider_retry_policy_job_id": (
            latest_model_provider_retry_policy.get("job_id")
            if isinstance(latest_model_provider_retry_policy, dict)
            else None
        ),
        "latest_model_provider_retry_policy_delay_seconds": (
            latest_model_provider_retry_policy.get("backoff", {}).get("delay_seconds")
            if isinstance(latest_model_provider_retry_policy, dict)
            else None
        ),
        "worker_dispatch_count": len(store.get("worker_dispatch_order", [])),
        "worker_dispatch_ids": list(store.get("worker_dispatch_order", [])),
        "latest_worker_dispatch_id": (
            latest_worker_dispatch.get("dispatch_id") if isinstance(latest_worker_dispatch, dict) else None
        ),
        "latest_worker_dispatch_job_id": (
            latest_worker_dispatch.get("job_id") if isinstance(latest_worker_dispatch, dict) else None
        ),
        "latest_worker_dispatch_render_plan_id": (
            latest_worker_dispatch.get("render_plan_id") if isinstance(latest_worker_dispatch, dict) else None
        ),
        "worker_progress_event_count": len(store.get("worker_progress_event_order", [])),
        "worker_progress_event_ids": list(store.get("worker_progress_event_order", [])),
        "latest_worker_progress_event_id": (
            latest_worker_progress_event.get("event_id")
            if isinstance(latest_worker_progress_event, dict)
            else None
        ),
        "latest_worker_progress_job_id": (
            latest_worker_progress_event.get("job_id")
            if isinstance(latest_worker_progress_event, dict)
            else None
        ),
        "latest_worker_progress_snapshot_id": (
            latest_worker_progress_event.get("snapshot_id")
            if isinstance(latest_worker_progress_event, dict)
            else None
        ),
        "worker_retry_policy_count": len(store.get("worker_retry_policy_order", [])),
        "worker_retry_policy_ids": list(store.get("worker_retry_policy_order", [])),
        "latest_worker_retry_policy_id": (
            latest_worker_retry_policy.get("policy_id")
            if isinstance(latest_worker_retry_policy, dict)
            else None
        ),
        "latest_worker_retry_policy_job_id": (
            latest_worker_retry_policy.get("job_id")
            if isinstance(latest_worker_retry_policy, dict)
            else None
        ),
        "latest_worker_retry_policy_delay_seconds": (
            latest_worker_retry_policy.get("backoff", {}).get("delay_seconds")
            if isinstance(latest_worker_retry_policy, dict)
            else None
        ),
        "worker_transport_failure_classification_count": len(
            store.get("worker_transport_failure_classification_order", [])
        ),
        "worker_transport_failure_classification_ids": list(
            store.get("worker_transport_failure_classification_order", [])
        ),
        "latest_worker_transport_failure_classification_id": (
            latest_worker_transport_failure_classification.get("classification_id")
            if isinstance(latest_worker_transport_failure_classification, dict)
            else None
        ),
        "latest_worker_transport_failure_classification_job_id": (
            latest_worker_transport_failure_classification.get("job_id")
            if isinstance(latest_worker_transport_failure_classification, dict)
            else None
        ),
        "latest_worker_transport_failure_classification_family": (
            latest_worker_transport_failure_classification.get("classification", {}).get("family")
            if isinstance(latest_worker_transport_failure_classification, dict)
            else None
        ),
    }


def job_orchestration_side_effects(
    *,
    worker_called: bool = False,
    model_provider_called: bool = False,
    chart_rendering_called: bool = False,
    chart_artifact_written: bool = False,
    approved_entity_catalog_read: bool = False,
    home_assistant_history_read: bool = False,
    history_retrieval_written: bool = False,
    job_state_written: bool = False,
    job_orchestration_written: bool = False,
    retry_behavior_called: bool = False,
    subscription_bookkeeping_written: bool = False,
    subscription_progress_streaming_called: bool = False,
    artifact_metadata_bookkeeping_written: bool = False,
    render_plan_bookkeeping_written: bool = False,
    model_provider_plan_bookkeeping_written: bool = False,
    model_provider_retry_policy_bookkeeping_written: bool = False,
    worker_dispatch_bookkeeping_written: bool = False,
    worker_progress_bookkeeping_written: bool = False,
    worker_progress_streaming_called: bool = False,
    worker_retry_policy_bookkeeping_written: bool = False,
    worker_transport_failure_classification_bookkeeping_written: bool = False,
    websocket_command_registered: bool = False,
) -> dict[str, bool]:
    """Return side-effect accounting for the job orchestration scaffold."""
    return {
        **NO_JOB_ORCHESTRATION_CALLS,
        "worker_called": worker_called,
        "model_provider_called": model_provider_called,
        "chart_rendering_called": chart_rendering_called,
        "chart_artifact_written": chart_artifact_written,
        "retry_behavior_called": retry_behavior_called,
        "subscription_progress_streaming_called": subscription_progress_streaming_called,
        "approved_entity_catalog_read": approved_entity_catalog_read,
        "home_assistant_history_read": home_assistant_history_read,
        "history_retrieval_scaffold_written": history_retrieval_written,
        "job_state_scaffold_written": job_state_written,
        "job_orchestration_scaffold_written": job_orchestration_written,
        "subscription_bookkeeping_written": subscription_bookkeeping_written,
        "artifact_metadata_bookkeeping_written": artifact_metadata_bookkeeping_written,
        "render_plan_bookkeeping_written": render_plan_bookkeeping_written,
        "model_provider_plan_bookkeeping_written": model_provider_plan_bookkeeping_written,
        "model_provider_retry_policy_bookkeeping_written": model_provider_retry_policy_bookkeeping_written,
        "worker_dispatch_bookkeeping_written": worker_dispatch_bookkeeping_written,
        "worker_progress_bookkeeping_written": worker_progress_bookkeeping_written,
        "worker_progress_streaming_called": worker_progress_streaming_called,
        "worker_retry_policy_bookkeeping_written": worker_retry_policy_bookkeeping_written,
        "worker_transport_failure_classification_bookkeeping_written": (
            worker_transport_failure_classification_bookkeeping_written
        ),
        "websocket_command_registered": websocket_command_registered,
    }


def _append_fetching_history_snapshot(job: dict[str, Any], entity_ids: list[str]) -> dict[str, Any]:
    return append_validated_job_snapshot(
        job,
        status="fetching_history",
        state_label="Fetching History",
        message="Approved entity history is being retrieved by the scaffold boundary.",
        progress_stage="approved_history_retrieval",
        progress_message="Retrieving approved fake Home Assistant history.",
        validation_status="in_progress",
        validation_summary="The scaffold is retrieving approved history before future planning.",
        validation_checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "approved_entity_catalog", "status": "pass"},
            {"name": "approved_history_retrieval", "status": "in_progress"},
            {"name": "model_provider", "status": "not_called"},
            {"name": "worker", "status": "not_called"},
        ],
        entities=[{"entity_id": entity_id, "label": entity_id} for entity_id in entity_ids],
        warnings=["job_orchestration_scaffold", "approved_history_retrieval_scaffold"],
    )


def _append_clarification_answer_accepted_snapshot(
    job: dict[str, Any],
    *,
    entity_id: str,
    remember: bool,
) -> dict[str, Any]:
    warnings = [
        "job_orchestration_clarification_continuation_scaffold",
        "clarification_answer_accepted",
    ]
    if remember:
        warnings.append("semantic_memory_not_persisted_in_scaffold")
    return append_validated_job_snapshot(
        job,
        status="planning",
        state_label="Clarification Accepted",
        message="Approved clarification option accepted; approved history retrieval will continue.",
        progress_stage="clarification_answer_accepted",
        progress_message=f"Continuing with approved entity {entity_id}.",
        validation_status="pass",
        validation_summary="The returned clarification option matched an approved entity option.",
        validation_checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "approved_entity_catalog", "status": "pass"},
            {"name": "clarification_answer", "status": "pass"},
            {"name": "approved_history_retrieval", "status": "not_run"},
            {"name": "model_provider", "status": "not_called"},
            {"name": "worker", "status": "not_called"},
        ],
        entities=[{"entity_id": entity_id, "label": entity_id}],
        warnings=warnings,
    )


def _append_retry_accepted_snapshot(
    job: dict[str, Any],
    *,
    failed_snapshot: dict[str, Any],
) -> dict[str, Any]:
    failure_code = failed_snapshot.get("failure", {}).get("code", "failed")
    return append_validated_job_snapshot(
        job,
        status="planning",
        state_label="Retry Accepted",
        message="Retry accepted for a failed scaffold job; approved history retrieval will run again.",
        progress_stage="job_orchestration_retry_accepted",
        progress_message=f"Retrying after scaffold failure {failure_code}.",
        validation_status="pass",
        validation_summary="The retry command targeted a failed retryable scaffold job.",
        validation_checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "retry_command", "status": "pass"},
            {"name": "approved_entity_catalog", "status": "not_run"},
            {"name": "approved_history_retrieval", "status": "not_run"},
            {"name": "model_provider", "status": "not_called"},
            {"name": "worker", "status": "not_called"},
        ],
        warnings=[
            "job_orchestration_retry_continuation_scaffold",
            "retry_accepted",
        ],
    )


def _append_failed_snapshot(
    job: dict[str, Any],
    *,
    code: str,
    stage: str,
    message: str,
    checks: list[dict[str, str]],
) -> dict[str, Any]:
    return append_validated_job_snapshot(
        job,
        status="failed",
        state_label="Failed",
        message=message,
        progress_stage="job_orchestration_scaffold_failed",
        progress_message=message,
        validation_status="fail",
        validation_summary="The orchestration scaffold stopped at a deterministic gate.",
        validation_checks=checks,
        failure={
            "stage": stage,
            "code": code,
            "message": message,
        },
        retry_allowed=True,
        warnings=["job_orchestration_scaffold", code, "orchestration_stopped_before_model_worker"],
    )


def _append_worker_failure_snapshot_from_planning_result(
    job: dict[str, Any],
    planning_result: dict[str, Any],
) -> dict[str, Any] | None:
    retry_policy = planning_result.get("worker_retry_policy")
    if isinstance(retry_policy, dict):
        return _append_worker_failure_snapshot(
            job,
            code=retry_policy.get("failure", {}).get("code", "worker_render_failed"),
            stage="worker_render",
            message=retry_policy.get("failure", {}).get(
                "message",
                "Worker render failed before a chart artifact was accepted.",
            ),
            retry_allowed=retry_policy.get("decision", {}).get("manual_retry_allowed") is True,
            validation_check_name="worker_failure_metadata",
            warning="worker_failure_metadata_recorded",
        )

    classification = planning_result.get("worker_transport_failure_classification")
    if isinstance(classification, dict):
        return _append_worker_failure_snapshot(
            job,
            code=classification.get("failure", {}).get("code", "worker_transport_failed"),
            stage="worker_transport",
            message=classification.get("failure", {}).get(
                "message",
                "Worker transport failed before a render result was accepted.",
            ),
            retry_allowed=classification.get("classification", {}).get("manual_retry_allowed") is True,
            validation_check_name="worker_failure_metadata",
            warning="worker_failure_metadata_recorded",
        )

    return None


def _append_history_failure_snapshot_from_planning_result(
    job: dict[str, Any],
    planning_result: dict[str, Any],
) -> dict[str, Any] | None:
    if not planning_result.get("history_failure"):
        return None
    code = planning_result.get("code", "approved_history_unavailable")
    history_result = planning_result.get("history_result", {})
    return _append_failed_snapshot(
        job,
        code=code,
        stage="approved_history_retrieval",
        message=_history_failure_message(code, history_result),
        checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "approved_entity_catalog", "status": "pass"},
            {"name": "model_provider", "status": "pass"},
            {"name": "approved_history_retrieval", "status": "fail"},
            {"name": "chart_rendering", "status": "not_called"},
        ],
    )


def _history_failure_message(code: str, history_result: dict[str, Any]) -> str:
    entity_ids = []
    if isinstance(history_result, dict):
        for key in ("missing_entity_ids", "rejected_entity_ids"):
            value = history_result.get(key)
            if isinstance(value, list):
                entity_ids.extend(str(item) for item in value if isinstance(item, str))
    entity_suffix = f" ({', '.join(sorted(set(entity_ids)))})" if entity_ids else ""
    messages = {
        "no_long_term_statistics": (
            "No long-term statistics are available to chart this time range"
            f"{entity_suffix}. Statistics require an entity with a measurement state class."
        ),
        "missing_approved_history": (
            f"No approved history was found for the requested time range{entity_suffix}."
        ),
        "entity_not_in_approved_catalog": (
            f"The requested entity is not in the approved catalog{entity_suffix}."
        ),
    }
    return messages.get(
        code,
        f"Approved history could not be retrieved for the requested time range{entity_suffix}.",
    )


def _append_model_provider_failure_snapshot_from_planning_result(
    job: dict[str, Any],
    planning_result: dict[str, Any],
) -> dict[str, Any] | None:
    if planning_result.get("code") == "model_provider_planner_not_configured":
        return _append_model_provider_failure_snapshot(
            job,
            code="model_provider_planner_not_configured",
            message="Model provider planner is not configured for this Isolinear entry.",
            retry_allowed=False,
        )

    retry_policy = planning_result.get("model_provider_retry_policy")
    if not isinstance(retry_policy, dict):
        if _is_model_provider_output_failure_code(planning_result.get("code")):
            return _append_model_provider_failure_snapshot(
                job,
                code=planning_result.get("code", "model_provider_planning_failed"),
                message=_model_provider_planning_failure_message(planning_result),
                retry_allowed=False,
            )
        return None

    return _append_model_provider_failure_snapshot(
        job,
        code=retry_policy.get("failure", {}).get("code", "model_provider_planning_failed"),
        message=retry_policy.get("failure", {}).get(
            "message",
            "Model provider planning failed before a chart spec was accepted.",
        ),
        retry_allowed=retry_policy.get("decision", {}).get("manual_retry_allowed") is True,
    )


def _append_in_process_renderer_failure_snapshot_from_planning_result(
    job: dict[str, Any],
    planning_result: dict[str, Any],
) -> dict[str, Any] | None:
    if not _is_in_process_renderer_failure_code(planning_result.get("code")):
        return None
    return _append_in_process_renderer_failure_snapshot(
        job,
        code=planning_result.get("code", "in_process_renderer_failed"),
        message=_in_process_renderer_failure_message(planning_result),
    )


def _is_model_provider_output_failure_code(code: Any) -> bool:
    return code in {
        "invalid_integration_model_provider_plan",
        "invalid_model_provider_chart_spec",
        "invalid_planner_result",
        "model_provider_chart_spec_hidden_entity",
        "model_provider_referenced_unapproved_entity",
        "model_provider_substituted_entity",
        "mixed_chart_composition_unsupported",
        "model_provider_planner_not_chart_spec_ready",
        "model_provider_planning_failed",
    }


def _is_in_process_renderer_failure_code(code: Any) -> bool:
    return code in {
        "artifact_directory_unavailable",
        "artifact_png_too_large",
        "artifact_write_failed",
        "in_process_renderer_failed",
        "in_process_renderer_output_too_large",
        "invalid_artifact_id",
        "invalid_artifact_png_payload",
        "invalid_in_process_render_request",
        "invalid_in_process_render_result",
        "renderer_dependency_unavailable",
        "unsupported_chart_spec",
    }


def _model_provider_planning_failure_message(planning_result: dict[str, Any]) -> str:
    code = planning_result.get("code")
    messages = {
        "invalid_planner_result": "The model provider returned a planner result that failed schema validation.",
        "model_provider_planner_not_chart_spec_ready": (
            "The model provider did not return a chart-ready planner result."
        ),
        "invalid_model_provider_chart_spec": (
            "The model provider returned a chart spec that failed schema validation."
        ),
        "model_provider_chart_spec_hidden_entity": (
            "The model provider returned a chart spec that referenced an entity outside the approved allowlist."
        ),
        "model_provider_referenced_unapproved_entity": (
            "The model provider referenced an entity that is not on the approved allowlist."
        ),
        "model_provider_substituted_entity": (
            "The model provider substituted an entity that was not selected for this question."
        ),
        "mixed_chart_composition_unsupported": (
            "Charting numeric and binary entities together is not supported yet; ask about them separately."
        ),
        "invalid_integration_model_provider_plan": (
            "The model provider plan failed integration metadata validation."
        ),
        "model_provider_planning_failed": "Model provider planning failed before a chart spec was accepted.",
    }
    if isinstance(code, str) and code in messages:
        return messages[code]
    return "Model provider planning failed before a chart spec was accepted."


def _in_process_renderer_failure_message(planning_result: dict[str, Any]) -> str:
    code = planning_result.get("code")
    messages = {
        "artifact_directory_unavailable": "Isolinear could not open the chart artifact directory.",
        "artifact_png_too_large": "The trusted chart renderer produced an artifact that was too large.",
        "artifact_write_failed": "Isolinear could not write the rendered chart artifact.",
        "in_process_renderer_failed": "The trusted chart renderer failed before a chart artifact was accepted.",
        "in_process_renderer_output_too_large": "The trusted chart renderer produced an artifact that was too large.",
        "invalid_artifact_id": "Isolinear could not prepare a valid chart artifact target.",
        "invalid_artifact_png_payload": "The trusted chart renderer returned an invalid PNG payload.",
        "invalid_in_process_render_request": "Isolinear could not prepare a valid request for the trusted chart renderer.",
        "invalid_in_process_render_result": "The trusted chart renderer returned an invalid render result.",
        "renderer_dependency_unavailable": (
            "The trusted chart renderer dependency is not installed in this Home Assistant environment."
        ),
        "unsupported_chart_spec": "The trusted chart renderer does not support this chart spec yet.",
    }
    if isinstance(code, str) and code in messages:
        return messages[code]
    return "The trusted chart renderer failed before a chart artifact was accepted."


def _append_model_provider_failure_snapshot(
    job: dict[str, Any],
    *,
    code: str,
    message: str,
    retry_allowed: bool,
) -> dict[str, Any]:
    safe_code = _safe_model_provider_failure_code(code)
    safe_message = _safe_model_provider_failure_message(message)
    return append_validated_job_snapshot(
        job,
        status="failed",
        state_label="Failed",
        message=safe_message,
        progress_stage="model_provider_failure_snapshot_ready",
        progress_message=safe_message,
        validation_status="fail",
        validation_summary="A validated model-provider failure was converted to a card-facing failed snapshot.",
        validation_checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "model_provider", "status": "fail"},
            {"name": "model_provider_failure_metadata", "status": "pass"},
            {"name": "manual_retry_affordance", "status": "pass" if retry_allowed else "not_allowed"},
            {"name": "automatic_retry", "status": "not_scheduled"},
        ],
        failure={
            "stage": "model_provider_planning",
            "code": safe_code,
            "message": safe_message,
        },
        retry_allowed=retry_allowed,
        warnings=[
            "model_provider_retry_backoff_policy_scaffold",
            "model_provider_metadata_not_exposed_to_card",
            "automatic_retry_not_scheduled",
        ],
    )


def _append_in_process_renderer_failure_snapshot(
    job: dict[str, Any],
    *,
    code: str,
    message: str,
) -> dict[str, Any]:
    safe_code = _safe_renderer_failure_code(code)
    safe_message = _safe_renderer_failure_message(message)
    return append_validated_job_snapshot(
        job,
        status="failed",
        state_label="Failed",
        message=safe_message,
        progress_stage="in_process_renderer_failure_snapshot_ready",
        progress_message=safe_message,
        validation_status="fail",
        validation_summary="A trusted renderer failure was converted to a card-facing failed snapshot.",
        validation_checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "model_provider", "status": "pass"},
            {"name": "chart_rendering", "status": "fail"},
            {"name": "artifact_metadata", "status": "not_written"},
            {"name": "manual_retry_affordance", "status": "pass"},
            {"name": "automatic_retry", "status": "not_scheduled"},
        ],
        failure={
            "stage": "chart_rendering",
            "code": safe_code,
            "message": safe_message,
        },
        retry_allowed=True,
        warnings=[
            "in_process_renderer_failure_snapshot",
            "renderer_metadata_not_exposed_to_card",
            "automatic_retry_not_scheduled",
        ],
    )


def _append_worker_failure_snapshot(
    job: dict[str, Any],
    *,
    code: str,
    stage: str,
    message: str,
    retry_allowed: bool,
    validation_check_name: str,
    warning: str,
) -> dict[str, Any]:
    safe_code = _safe_worker_snapshot_failure_code(code, stage=stage)
    safe_message = _safe_worker_snapshot_failure_message(message, stage=stage)
    return append_validated_job_snapshot(
        job,
        status="failed",
        state_label="Failed",
        message=safe_message,
        progress_stage="worker_failure_snapshot_ready",
        progress_message=safe_message,
        validation_status="fail",
        validation_summary="A validated worker failure was converted to a card-facing failed snapshot.",
        validation_checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "worker", "status": "fail"},
            {"name": validation_check_name, "status": "pass"},
            {"name": "worker_authorization_redacted", "status": "pass"},
            {"name": "manual_retry_affordance", "status": "pass" if retry_allowed else "not_allowed"},
            {"name": "automatic_retry", "status": "not_scheduled"},
        ],
        failure={
            "stage": stage,
            "code": safe_code,
            "message": safe_message,
        },
        retry_allowed=retry_allowed,
        warnings=[
            "worker_failure_snapshot_manual_retry_integration_scaffold",
            warning,
            "worker_authorization_not_exposed_to_card",
            "worker_metadata_not_exposed_to_card",
            "automatic_retry_not_scheduled",
        ],
    )


def _append_clarification_snapshot(
    job: dict[str, Any],
    *,
    message: str,
    options: list[dict[str, Any]],
) -> dict[str, Any]:
    return append_validated_job_snapshot(
        job,
        status="clarification_needed",
        state_label="Clarification Needed",
        message=message,
        progress_stage="entity_selection_clarification",
        progress_message=message,
        validation_status="blocked",
        validation_summary="The orchestration scaffold refused to guess an entity from an ambiguous prompt.",
        validation_checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "approved_entity_catalog", "status": "clarification_needed"},
            {"name": "approved_history_retrieval", "status": "not_run"},
            {"name": "model_provider", "status": "not_called"},
            {"name": "worker", "status": "not_called"},
        ],
        clarification={
            "question_id": "select_approved_entity",
            "message": message,
            "reason": "The prompt did not name a specific approved entity.",
            "options": options,
        },
        warnings=[
            "job_orchestration_scaffold",
            "entity_selection_requires_clarification",
            "history_not_read_before_clarification",
        ],
    )


def _record_run(
    store: dict[str, Any],
    *,
    command: dict[str, Any],
    job: dict[str, Any],
    result_code: str,
    requested_entity_ids: list[str],
    history_entity_ids: list[str],
    snapshot_ids: list[str],
    rejected_entity_ids: list[str] | None = None,
    missing_entity_ids: list[str] | None = None,
    clarification_answer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_number = store["next_run_number"]
    run_id = f"{store['entry_id']}-orchestration-run-{run_number:03d}"
    run = {
        "run_id": run_id,
        "entry_id": store["entry_id"],
        "job_id": job["job_id"],
        "prompt": command.get("prompt", job.get("prompt", "")),
        "result_code": result_code,
        "requested_entity_ids": list(requested_entity_ids),
        "history_entity_ids": list(history_entity_ids),
        "snapshot_ids": list(snapshot_ids),
        "rejected_entity_ids": list(rejected_entity_ids or []),
        "missing_entity_ids": list(missing_entity_ids or []),
    }
    if clarification_answer is not None:
        run["clarification_answer"] = deepcopy(clarification_answer)
    store["next_run_number"] = run_number + 1
    store["runs"][run_id] = deepcopy(run)
    store["run_order"].append(run_id)
    store["latest_run"] = deepcopy(run)
    return deepcopy(run)


def _record_progress_event(
    store: dict[str, Any],
    *,
    command: dict[str, Any],
    subscription: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    event_number = store["next_progress_event_number"]
    event_id = f"{store['entry_id']}-progress-event-{event_number:03d}"
    event = {
        "event_id": event_id,
        "type": "isolinear_job_progress",
        "config_entry_id": store["entry_id"],
        "job_id": command["job_id"],
        "subscription_id": subscription["subscription_id"],
        "message_id": subscription.get("message_id"),
        "snapshot_id": snapshot["snapshot_id"],
        "progress": deepcopy(snapshot["progress"]),
        "snapshot": deepcopy(snapshot),
    }
    store["next_progress_event_number"] = event_number + 1
    store["progress_events"][event_id] = deepcopy(event)
    store["progress_event_order"].append(event_id)
    store["latest_progress_event"] = deepcopy(event)
    return deepcopy(event)


def _record_artifact_metadata(
    store: dict[str, Any],
    *,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
) -> dict[str, Any]:
    artifact = _build_artifact_metadata(store, job=job, source_snapshot=source_snapshot)
    validation = validate_artifact_metadata_contract(artifact)
    if not validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_integration_artifact_metadata",
            "validation": validation,
        }

    _store_validated_artifact_metadata(store, artifact)
    return {
        "accepted": True,
        "code": "accepted",
        "artifact": deepcopy(artifact),
        "validation": validation,
    }


def _retrieve_history_for_plan(
    hass: Any,
    *,
    entry_id: str,
    chart_spec: Any,
) -> dict[str, Any] | None:
    """Fetch approved history for the model-resolved window (first real slice).

    Returns ``None`` for the legacy scaffold path (history is staged at start).
    For the real path, resolves the absolute window from the chart spec
    (ADR-0020), fetches tiered history (ADR-0021), and stores it for rendering.
    On failure returns a result flagged ``history_failure`` so the snapshot path
    can surface a card-facing failed snapshot.
    """
    if not first_real_vertical_slice_enabled(hass, entry_id):
        return None
    if not isinstance(chart_spec, dict):
        return None

    entry = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {}).get("entry")
    if entry is None:
        return {"accepted": False, "code": "unknown_config_entry", "history_failure": True}

    entity_ids = sorted(_chart_spec_entity_ids(chart_spec)["entity_ids"])
    if not entity_ids:
        return {
            "accepted": False,
            "code": "missing_approved_history",
            "history_failure": True,
            "history_result": {"missing_entity_ids": []},
        }

    now = _history_now(hass)
    window = resolve_history_window(chart_spec, now=now)
    result = dict(
        retrieve_approved_history(
            hass,
            entry,
            entity_ids=entity_ids,
            start=window["start"],
            end=window["end"],
            now=now,
            allow_statistics=True,
        )
    )
    result["window"] = window
    if not result["accepted"]:
        result["history_failure"] = True
    return result


def _record_artifact_and_render_plan(
    store: dict[str, Any],
    *,
    hass: Any,
    entry_id: str,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
) -> dict[str, Any]:
    artifact = _build_artifact_metadata(store, job=job, source_snapshot=source_snapshot)
    artifact_validation = validate_artifact_metadata_contract(artifact)
    if not artifact_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_integration_artifact_metadata",
            "validation": artifact_validation,
        }

    model_provider_result = _record_model_provider_plan(
        store,
        hass=hass,
        entry_id=entry_id,
        job=job,
        source_snapshot=source_snapshot,
    )
    if not model_provider_result["accepted"]:
        return {
            "accepted": False,
            "code": model_provider_result["code"],
            "validation": model_provider_result.get("validation"),
            "model_provider": model_provider_result.get("model_provider"),
            "model_provider_retry_policy": model_provider_result.get("model_provider_retry_policy"),
            "model_provider_called": model_provider_result.get("model_provider_called", False),
            "orchestration": job_orchestration_side_effects(
                model_provider_called=model_provider_result.get("model_provider_called", False),
                model_provider_retry_policy_bookkeeping_written=(
                    model_provider_result.get("model_provider_retry_policy_written", False)
                ),
            ),
        }

    history_for_plan = _retrieve_history_for_plan(
        hass,
        entry_id=entry_id,
        chart_spec=model_provider_result.get("chart_spec"),
    )
    if history_for_plan is not None and not history_for_plan["accepted"]:
        return {
            "accepted": False,
            "code": history_for_plan["code"],
            "history_failure": True,
            "history_result": history_for_plan,
            "model_provider_called": model_provider_result.get("model_provider_called", False),
            "orchestration": job_orchestration_side_effects(
                model_provider_called=model_provider_result.get("model_provider_called", False),
                home_assistant_history_read=history_for_plan.get("orchestration", {}).get(
                    "home_assistant_history_read", False
                ),
            ),
        }

    render_plan = _build_render_plan(
        store,
        job=job,
        source_snapshot=source_snapshot,
        artifact=artifact,
        chart_spec=model_provider_result.get("chart_spec"),
    )
    render_plan_validation = validate_render_plan_contract(render_plan)
    if not render_plan_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_integration_render_plan",
            "validation": render_plan_validation,
        }

    in_process_render_result = _record_in_process_render(
        store,
        hass=hass,
        entry_id=entry_id,
        artifact=artifact,
        render_plan=render_plan,
        model_provider_result=model_provider_result,
    )
    if in_process_render_result.get("enabled"):
        if not in_process_render_result["accepted"]:
            return {
                "accepted": False,
                "code": in_process_render_result["code"],
                "validation": in_process_render_result.get("validation"),
                "model_provider_called": model_provider_result.get("model_provider_called", False),
                "worker_called": False,
                "chart_rendering_called": in_process_render_result.get("chart_rendering_called", False),
                "chart_artifact_written": in_process_render_result.get("chart_artifact_written", False),
                "orchestration": job_orchestration_side_effects(
                    model_provider_called=model_provider_result.get("model_provider_called", False),
                    chart_rendering_called=in_process_render_result.get("chart_rendering_called", False),
                    chart_artifact_written=in_process_render_result.get("chart_artifact_written", False),
                ),
            }

        model_provider_plan = model_provider_result.get("model_provider_plan")
        artifact = in_process_render_result["artifact"]
        if model_provider_plan is not None:
            _store_validated_model_provider_plan(store, model_provider_plan)
        _store_validated_artifact_metadata(store, artifact)
        _store_validated_render_plan(store, render_plan)
        return {
            "accepted": True,
            "code": "accepted",
            "artifact": deepcopy(artifact),
            "render_plan": deepcopy(render_plan),
            "model_provider_plan": deepcopy(model_provider_plan) if model_provider_plan is not None else None,
            "worker_dispatch": None,
            "worker_progress_events": [],
            "in_process_render": deepcopy(in_process_render_result["in_process_render"]),
            "model_provider_called": model_provider_result.get("model_provider_called", False),
            "worker_called": False,
            "chart_rendering_called": True,
            "chart_artifact_written": in_process_render_result.get("chart_artifact_written", False),
            "worker_progress_streaming_called": False,
            "artifact_validation": in_process_render_result.get("artifact_validation"),
            "model_provider_validation": model_provider_result.get("validation"),
            "render_plan_validation": render_plan_validation,
            "worker_dispatch_validation": None,
            "worker_progress_validation": None,
        }

    worker_dispatch_result = _record_worker_dispatch(
        store,
        hass=hass,
        entry_id=entry_id,
        job=job,
        source_snapshot=source_snapshot,
        artifact=artifact,
        render_plan=render_plan,
        serve_artifact=model_provider_result.get("model_provider_plan") is not None,
    )
    if not worker_dispatch_result["accepted"]:
        return {
            "accepted": False,
            "code": worker_dispatch_result["code"],
            "validation": worker_dispatch_result.get("validation"),
            "worker": worker_dispatch_result.get("worker"),
            "model_provider_called": model_provider_result.get("model_provider_called", False),
            "worker_called": worker_dispatch_result.get("worker_called", False),
            "chart_rendering_called": worker_dispatch_result.get("chart_rendering_called", False),
            "chart_artifact_written": worker_dispatch_result.get("chart_artifact_written", False),
            "worker_retry_policy": worker_dispatch_result.get("worker_retry_policy"),
            "worker_transport_failure_classification": worker_dispatch_result.get(
                "worker_transport_failure_classification"
            ),
            "orchestration": job_orchestration_side_effects(
                model_provider_called=model_provider_result.get("model_provider_called", False),
                worker_called=worker_dispatch_result.get("worker_called", False),
                chart_rendering_called=worker_dispatch_result.get("chart_rendering_called", False),
                chart_artifact_written=worker_dispatch_result.get("chart_artifact_written", False),
                worker_progress_streaming_called=worker_dispatch_result.get("worker_progress_streaming_called", False),
                worker_retry_policy_bookkeeping_written=worker_dispatch_result.get(
                    "worker_retry_policy_written",
                    False,
                ),
                worker_transport_failure_classification_bookkeeping_written=worker_dispatch_result.get(
                    "worker_transport_failure_classification_written",
                    False,
                ),
            ),
        }

    model_provider_plan = model_provider_result.get("model_provider_plan")
    artifact = worker_dispatch_result.get("artifact", artifact)
    worker_dispatch = worker_dispatch_result.get("worker_dispatch")
    worker_progress_events = worker_dispatch_result.get("worker_progress_events") or []
    if model_provider_plan is not None:
        _store_validated_model_provider_plan(store, model_provider_plan)
    _store_validated_artifact_metadata(store, artifact)
    _store_validated_render_plan(store, render_plan)
    if worker_dispatch is not None:
        _store_validated_worker_dispatch(store, worker_dispatch)
    return {
        "accepted": True,
        "code": "accepted",
        "artifact": deepcopy(artifact),
        "render_plan": deepcopy(render_plan),
        "model_provider_plan": deepcopy(model_provider_plan) if model_provider_plan is not None else None,
        "worker_dispatch": deepcopy(worker_dispatch) if worker_dispatch is not None else None,
        "worker_progress_events": deepcopy(worker_progress_events),
        "model_provider_called": model_provider_result.get("model_provider_called", False),
        "worker_called": worker_dispatch_result.get("worker_called", False),
        "chart_rendering_called": worker_dispatch_result.get("chart_rendering_called", False),
        "chart_artifact_written": worker_dispatch_result.get("chart_artifact_written", False),
        "worker_progress_streaming_called": worker_dispatch_result.get("worker_progress_streaming_called", False),
        "artifact_validation": worker_dispatch_result.get("artifact_validation", artifact_validation),
        "model_provider_validation": model_provider_result.get("validation"),
        "render_plan_validation": render_plan_validation,
        "worker_dispatch_validation": worker_dispatch_result.get("validation"),
        "worker_progress_validation": worker_dispatch_result.get("worker_progress_validation"),
    }


def _record_model_provider_plan(
    store: dict[str, Any],
    *,
    hass: Any,
    entry_id: str,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
) -> dict[str, Any]:
    planner = get_model_provider_planner(hass, entry_id)
    if planner is None:
        if first_real_vertical_slice_enabled(hass, entry_id):
            return {
                "accepted": False,
                "code": "model_provider_planner_not_configured",
                "model_provider_called": False,
                "model_provider_plan": None,
                "chart_spec": None,
                "validation": {
                    "accepted": False,
                    "code": "model_provider_planner_not_configured",
                    "error": "The real render path requires a configured model-provider planner.",
                },
            }
        return {
            "accepted": True,
            "code": "model_provider_planner_not_configured",
            "model_provider_called": False,
            "model_provider_plan": None,
            "chart_spec": None,
        }

    # Deterministic render-family routing (ADR-0022): classify each resolved
    # entity by series kind *before* planning and select the matching planner
    # schema. The model never chooses chart_type.
    catalog_items = _approved_catalog_items(hass, entry_id)
    requested_entity_ids = _source_snapshot_entity_ids(source_snapshot)
    routing = _resolve_render_family(catalog_items, requested_entity_ids)
    if routing["family"] == "mixed":
        return {
            "accepted": False,
            "code": "mixed_chart_composition_unsupported",
            "model_provider_called": False,
            "model_provider_plan": None,
            "chart_spec": None,
            "validation": {
                "accepted": False,
                "code": "mixed_chart_composition_unsupported",
                "error": (
                    "This question mixes more than one numeric series with a binary entity, so the primary "
                    "chart cannot be chosen automatically; ask about a single numeric series with the binary "
                    "overlay."
                ),
                "kinds": routing["kinds"],
            },
        }

    # The model only ever produces the chartable *series* (ADR-0022 D5): for the
    # overlay composition it plans the single numeric primary as a time_series
    # line, and the integration injects the binary entities as shaded_intervals
    # overlays afterwards. The planner is disclosed only the series entities.
    is_overlay = routing["family"] == "time_series_overlay"
    planner_family = "time_series" if is_overlay else routing["family"]
    series_entity_ids = (
        routing["numeric_entity_ids"]
        if planner_family == "time_series"
        else routing["categorical_entity_ids"]
    )
    request = _model_provider_planner_request(
        hass=hass,
        job=job,
        source_snapshot=source_snapshot,
        entity_ids=series_entity_ids or None,
    )
    # Pin the structured-output entity enum to exactly the disclosed entities so
    # the provider cannot emit an off-allowlist entity (ADR-0022, invariant #1).
    # request["approved_entity_ids"] is the resolved disclosure (series_entity_ids
    # or the source-snapshot fallback inside _model_provider_planner_request).
    result_schema = load_planner_result_schema(
        planner_family, entity_ids=request["approved_entity_ids"]
    )
    # ADR-0025 D1: stream the chart-planning thinking into the per-job live slot
    # so concurrent ~1s polls surface it in the chart area while the model runs.
    plan_on_reasoning = _live_reasoning_callback(
        store, job["job_id"], stage=PLAN_CHART_PHASE_LABEL
    )
    provider_response = _call_planner_with_optional_reasoning(
        planner.plan_chart, request, result_schema=result_schema, on_reasoning=plan_on_reasoning
    )
    provider_summary = {
        "provider": planner_client_metadata(planner),
        "response_code": provider_response.get("code") if isinstance(provider_response, dict) else None,
    }
    if not isinstance(provider_response, dict) or not provider_response.get("accepted"):
        if isinstance(provider_response, dict):
            retry_policy_result = _record_model_provider_retry_policy(
                store,
                job=job,
                source_snapshot=source_snapshot,
                provider=planner_client_metadata(planner),
                request=request,
                provider_response=provider_response,
            )
            if retry_policy_result["accepted"]:
                policy = retry_policy_result["model_provider_retry_policy"]
                return {
                    "accepted": False,
                    "code": policy["failure"]["code"],
                    "model_provider_called": True,
                    "model_provider": provider_summary,
                    "model_provider_retry_policy": policy,
                    "model_provider_retry_policy_written": True,
                    "validation": retry_policy_result.get("validation"),
                }
            return {
                "accepted": False,
                "code": retry_policy_result["code"],
                "validation": retry_policy_result.get("validation"),
                "model_provider_called": True,
                "model_provider": provider_summary,
            }
        return {
            "accepted": False,
            "code": "model_provider_planning_failed",
            "model_provider_called": True,
            "model_provider": provider_summary,
        }

    planner_result = provider_response.get("planner_result")
    planner_result_validation = validate_planner_result_contract(planner_result)
    if not planner_result_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_planner_result",
            "validation": planner_result_validation,
            "model_provider_called": True,
            "model_provider": provider_summary,
        }

    if not isinstance(planner_result, dict) or planner_result.get("status") != "chart_spec_ready":
        return {
            "accepted": False,
            "code": "model_provider_planner_not_chart_spec_ready",
            "validation": planner_result_validation,
            "model_provider_called": True,
            "model_provider": provider_summary,
        }

    chart_spec = planner_result.get("chart_spec")
    chart_spec_validation = validate_chart_spec_contract(chart_spec)
    if not chart_spec_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_model_provider_chart_spec",
            "validation": chart_spec_validation,
            "model_provider_called": True,
            "model_provider": provider_summary,
        }

    # Deterministically inject binary shaded_intervals overlays (ADR-0022 D4/D5).
    if is_overlay and isinstance(chart_spec, dict):
        chart_spec = _compose_binary_overlays(
            chart_spec,
            overlay_entity_ids=routing["overlay_entity_ids"],
            catalog_items=catalog_items,
        )
        composed_validation = validate_chart_spec_contract(chart_spec)
        if not composed_validation["accepted"]:
            return {
                "accepted": False,
                "code": "invalid_model_provider_chart_spec",
                "validation": composed_validation,
                "model_provider_called": True,
                "model_provider": provider_summary,
            }
        planner_result = deepcopy(planner_result)
        planner_result["chart_spec"] = chart_spec

    entity_validation = validate_model_provider_output_entities(
        planner_result,
        chart_spec,
        source_snapshot,
        approved_catalog_entity_ids=[item["entity_id"] for item in catalog_items],
    )
    if not entity_validation["accepted"]:
        return {
            "accepted": False,
            "code": entity_validation["code"],
            "validation": entity_validation,
            "model_provider_called": True,
            "model_provider": provider_summary,
        }

    provider_plan = _build_model_provider_plan(
        store,
        job=job,
        source_snapshot=source_snapshot,
        request=request,
        provider=provider_response.get("provider") or planner_client_metadata(planner),
        planner_result=planner_result,
        chart_spec=chart_spec,
    )
    provider_plan_validation = validate_model_provider_plan_contract(provider_plan)
    if not provider_plan_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_integration_model_provider_plan",
            "validation": provider_plan_validation,
            "model_provider_called": True,
            "model_provider": provider_summary,
        }

    return {
        "accepted": True,
        "code": "accepted",
        "model_provider_called": True,
        "model_provider_plan": provider_plan,
        "chart_spec": deepcopy(chart_spec),
        "validation": provider_plan_validation,
        "model_provider": provider_summary,
    }


def _record_in_process_render(
    store: dict[str, Any],
    *,
    hass: Any,
    entry_id: str,
    artifact: dict[str, Any],
    render_plan: dict[str, Any],
    model_provider_result: dict[str, Any],
) -> dict[str, Any]:
    if not first_real_vertical_slice_enabled(hass, entry_id):
        return {"enabled": False}
    if get_worker_render_client(hass, entry_id) is not None:
        return {"enabled": False}
    if model_provider_result.get("model_provider_plan") is None:
        return {"enabled": False}

    render_request = _build_worker_render_request(
        store,
        hass=hass,
        entry_id=entry_id,
        render_plan=render_plan,
    )
    render_request_validation = validate_render_request_contract(render_request)
    if not render_request_validation["accepted"]:
        return {
            "enabled": True,
            "accepted": False,
            "code": "invalid_in_process_render_request",
            "validation": render_request_validation,
            "chart_rendering_called": False,
        }

    render_response = render_in_process_chart(render_request)
    render_result = render_response.get("render_result") if isinstance(render_response, dict) else None
    render_result_validation = validate_render_result_contract(render_result)
    if not render_result_validation["accepted"]:
        return {
            "enabled": True,
            "accepted": False,
            "code": "invalid_in_process_render_result",
            "validation": render_result_validation,
            "chart_rendering_called": True,
        }
    if not isinstance(render_response, dict) or not render_response.get("accepted"):
        return {
            "enabled": True,
            "accepted": False,
            "code": render_response.get("code", "in_process_renderer_failed")
            if isinstance(render_response, dict)
            else "in_process_renderer_failed",
            "validation": render_result_validation,
            "chart_rendering_called": True,
            "in_process_render": render_response if isinstance(render_response, dict) else None,
        }
    if not isinstance(render_result, dict) or render_result.get("status") != "success":
        return {
            "enabled": True,
            "accepted": False,
            "code": "in_process_renderer_failed",
            "validation": render_result_validation,
            "chart_rendering_called": True,
            "in_process_render": render_response,
        }

    prepared_artifact = prepare_png_artifact(
        hass,
        entry_id,
        artifact_id=artifact["artifact_id"],
        png_bytes=render_response.get("png_bytes"),
    )
    if not prepared_artifact["accepted"]:
        return {
            "enabled": True,
            "accepted": False,
            "code": prepared_artifact["code"],
            "validation": prepared_artifact,
            "chart_rendering_called": True,
            "chart_artifact_written": False,
            "in_process_render": render_response,
        }

    render_result = deepcopy(render_result)
    render_result["image_path"] = prepared_artifact["artifact_path"]
    render_result_validation = validate_render_result_contract(render_result)
    if not render_result_validation["accepted"]:
        return {
            "enabled": True,
            "accepted": False,
            "code": "invalid_in_process_render_result",
            "validation": render_result_validation,
            "chart_rendering_called": True,
            "chart_artifact_written": False,
            "in_process_render": render_response,
        }

    rendered_artifact = _build_in_process_artifact_metadata(
        artifact,
        render_result=render_result,
        image_url=prepared_artifact["image_url"],
    )
    artifact_validation = validate_artifact_metadata_contract(rendered_artifact)
    if not artifact_validation["accepted"]:
        return {
            "enabled": True,
            "accepted": False,
            "code": "invalid_in_process_artifact_metadata",
            "validation": artifact_validation,
            "chart_rendering_called": True,
            "chart_artifact_written": False,
            "in_process_render": render_response,
        }

    artifact_write = write_png_artifact(
        hass,
        entry_id,
        artifact_id=artifact["artifact_id"],
        png_bytes=render_response.get("png_bytes"),
    )
    if not artifact_write["accepted"]:
        return {
            "enabled": True,
            "accepted": False,
            "code": artifact_write["code"],
            "validation": artifact_write,
            "chart_rendering_called": True,
            "chart_artifact_written": False,
            "in_process_render": {
                **render_response,
                "render_result": render_result,
            },
        }

    return {
        "enabled": True,
        "accepted": True,
        "code": "in_process_render_recorded",
        "artifact": rendered_artifact,
        "artifact_validation": artifact_validation,
        "render_result_validation": render_result_validation,
        "in_process_render": {
            "renderer": render_response["renderer"],
            "render_result": render_result,
            "png_byte_count": render_response["png_byte_count"],
            "image_url": artifact_write["image_url"],
            "artifact_path": artifact_write["artifact_path"],
            "image_url_prefix": "/api/isolinear/artifacts",
        },
        "chart_rendering_called": True,
        "chart_artifact_written": True,
    }


def _record_worker_rendered_artifact(
    hass: Any,
    entry_id: str,
    *,
    artifact: dict[str, Any],
    render_result: dict[str, Any],
) -> dict[str, Any]:
    png_result = _worker_png_bytes_from_render_result(render_result)
    if not png_result["accepted"]:
        return png_result

    prepared_artifact = prepare_png_artifact(
        hass,
        entry_id,
        artifact_id=artifact["artifact_id"],
        png_bytes=png_result["png_bytes"],
    )
    if not prepared_artifact["accepted"]:
        return {
            "accepted": False,
            "code": prepared_artifact["code"],
            "validation": prepared_artifact,
        }

    sanitized_render_result = deepcopy(render_result)
    sanitized_render_result.pop("image_bytes_base64", None)
    sanitized_render_result["image_path"] = prepared_artifact["artifact_path"]
    render_result_validation = validate_render_result_contract(sanitized_render_result)
    if not render_result_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_worker_render_result",
            "validation": render_result_validation,
        }

    rendered_artifact = _build_worker_artifact_metadata(
        artifact,
        render_result=sanitized_render_result,
        image_url=prepared_artifact["image_url"],
    )
    artifact_validation = validate_artifact_metadata_contract(rendered_artifact)
    if not artifact_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_worker_artifact_metadata",
            "validation": artifact_validation,
        }

    artifact_write = write_png_artifact(
        hass,
        entry_id,
        artifact_id=artifact["artifact_id"],
        png_bytes=png_result["png_bytes"],
    )
    if not artifact_write["accepted"]:
        return {
            "accepted": False,
            "code": artifact_write["code"],
            "validation": artifact_write,
        }

    return {
        "accepted": True,
        "code": "worker_rendered_artifact_recorded",
        "artifact": rendered_artifact,
        "render_result": sanitized_render_result,
        "artifact_validation": artifact_validation,
        "render_result_validation": render_result_validation,
        "artifact_write": artifact_write,
        "chart_artifact_written": True,
    }


def _rollback_worker_rendered_artifact(
    hass: Any,
    entry_id: str,
    artifact_result: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(artifact_result, dict) or not artifact_result.get("chart_artifact_written"):
        return None
    artifact = artifact_result.get("artifact")
    if not isinstance(artifact, dict) or not isinstance(artifact.get("artifact_id"), str):
        return None
    return remove_png_artifact(hass, entry_id, artifact_id=artifact["artifact_id"])


def _worker_png_bytes_from_render_result(render_result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(render_result, dict):
        return {
            "accepted": False,
            "code": "invalid_worker_render_result",
        }
    if render_result.get("image_mime_type") != "image/png":
        return {
            "accepted": False,
            "code": "invalid_worker_image_mime_type",
            "validation": {
                "accepted": False,
                "code": "invalid_worker_image_mime_type",
                "expected": "image/png",
                "observed": render_result.get("image_mime_type"),
            },
        }

    encoded = render_result.get("image_bytes_base64")
    if not isinstance(encoded, str) or not encoded.strip():
        return {
            "accepted": False,
            "code": "missing_worker_image_bytes",
            "validation": {
                "accepted": False,
                "code": "missing_worker_image_bytes",
            },
        }

    try:
        png_bytes = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return {
            "accepted": False,
            "code": "invalid_worker_image_bytes",
            "validation": {
                "accepted": False,
                "code": "invalid_worker_image_bytes",
            },
        }
    return {
        "accepted": True,
        "code": "accepted",
        "png_bytes": png_bytes,
    }


def _record_worker_progress_events(
    store: dict[str, Any],
    *,
    hass: Any,
    entry_id: str,
    job: dict[str, Any],
    worker: dict[str, Any],
    worker_authorization: str,
    request_id: str,
    progress_payloads: Any,
) -> dict[str, Any]:
    forbidden_text_values = [worker_authorization]
    if worker_authorization.startswith("Bearer "):
        forbidden_text_values.append(worker_authorization.removeprefix("Bearer ").strip())
    payload_validation = _normalize_worker_progress_payloads(
        progress_payloads,
        forbidden_text_values=forbidden_text_values,
    )
    if not payload_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_integration_worker_progress",
            "validation": payload_validation,
            "worker_progress_streaming_called": False,
        }

    normalized_payloads = payload_validation["progress_payloads"]
    if not normalized_payloads:
        return {
            "accepted": True,
            "code": "worker_progress_not_reported",
            "worker_progress_events": [],
            "worker_progress_streaming_called": False,
            "validation": payload_validation,
        }

    stored_events = []
    for payload in normalized_payloads:
        snapshot = _build_worker_progress_snapshot(job, payload)
        event = _build_worker_progress_event(
            store,
            hass=hass,
            entry_id=entry_id,
            job=job,
            worker=worker,
            worker_authorization=worker_authorization,
            request_id=request_id,
            payload=payload,
            snapshot=snapshot,
        )
        progress_validation = validate_worker_progress_contract(event)
        if not progress_validation["accepted"]:
            return {
                "accepted": False,
                "code": "invalid_integration_worker_progress",
                "validation": progress_validation,
                "worker_progress_streaming_called": True,
            }

        snapshot_result = store_validated_job_snapshot(job, snapshot)
        if not snapshot_result["accepted"]:
            return {
                "accepted": False,
                "code": "invalid_integration_worker_progress",
                "validation": snapshot_result,
                "worker_progress_streaming_called": True,
            }
        job["next_snapshot_number"] += 1
        _store_validated_worker_progress_event(store, event)
        stored_events.append(deepcopy(event))

    return {
        "accepted": True,
        "code": "worker_progress_recorded",
        "worker_progress_events": stored_events,
        "worker_progress_streaming_called": True,
        "validation": {
            "accepted": True,
            "code": "accepted",
            "event_count": len(stored_events),
            "schema": str(WORKER_PROGRESS_SCHEMA_PATH),
        },
    }


def _normalize_worker_progress_payloads(
    progress_payloads: Any,
    *,
    forbidden_text_values: list[str] | None = None,
) -> dict[str, Any]:
    if progress_payloads is None:
        return {
            "accepted": True,
            "code": "worker_progress_not_reported",
            "progress_payloads": [],
        }
    if not isinstance(progress_payloads, list):
        return {
            "accepted": False,
            "code": "invalid_worker_progress_payloads",
            "error": "worker progress payloads must be a list",
        }
    if len(progress_payloads) > MAX_WORKER_PROGRESS_EVENTS:
        return {
            "accepted": False,
            "code": "too_many_worker_progress_payloads",
            "max_worker_progress_events": MAX_WORKER_PROGRESS_EVENTS,
            "observed_worker_progress_events": len(progress_payloads),
        }

    normalized = []
    for index, payload in enumerate(progress_payloads, start=1):
        if not isinstance(payload, dict):
            return {
                "accepted": False,
                "code": "invalid_worker_progress_payload",
                "path": f"progress_events[{index - 1}]",
                "error": "worker progress payload must be an object",
            }
        sequence = payload.get("sequence", index)
        stage = payload.get("stage")
        message = payload.get("message")
        percent_complete = payload.get("percent_complete")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            return {
                "accepted": False,
                "code": "invalid_worker_progress_sequence",
                "path": f"progress_events[{index - 1}].sequence",
            }
        if not isinstance(stage, str) or not stage.strip():
            return {
                "accepted": False,
                "code": "invalid_worker_progress_stage",
                "path": f"progress_events[{index - 1}].stage",
            }
        if not isinstance(message, str) or not message.strip():
            return {
                "accepted": False,
                "code": "invalid_worker_progress_message",
                "path": f"progress_events[{index - 1}].message",
            }
        if _worker_progress_text_contains_forbidden_material(stage, forbidden_text_values):
            return {
                "accepted": False,
                "code": "forbidden_worker_progress_text",
                "path": f"progress_events[{index - 1}].stage",
            }
        if _worker_progress_text_contains_forbidden_material(message, forbidden_text_values):
            return {
                "accepted": False,
                "code": "forbidden_worker_progress_text",
                "path": f"progress_events[{index - 1}].message",
            }
        if (
            not isinstance(percent_complete, (int, float))
            or isinstance(percent_complete, bool)
            or percent_complete < 0
            or percent_complete > 100
        ):
            return {
                "accepted": False,
                "code": "invalid_worker_progress_percent",
                "path": f"progress_events[{index - 1}].percent_complete",
            }
        normalized.append(
            {
                "sequence": sequence,
                "stage": stage.strip(),
                "message": message.strip(),
                "percent_complete": percent_complete,
            }
        )

    return {
        "accepted": True,
        "code": "accepted",
        "progress_payloads": normalized,
    }


def _worker_progress_text_contains_forbidden_material(
    value: str,
    forbidden_text_values: list[str] | None,
) -> bool:
    if FORBIDDEN_WORKER_PROGRESS_TEXT.search(value):
        return True
    for forbidden in forbidden_text_values or []:
        if isinstance(forbidden, str) and forbidden.strip() and forbidden.strip() in value:
            return True
    return False


def _build_worker_progress_snapshot(job: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    snapshot_number = job["next_snapshot_number"]
    return {
        "snapshot_id": f"{job['job_id']}-snapshot-{snapshot_number:03d}",
        "job_id": job["job_id"],
        "status": "rendering",
        "prompt": job["prompt"],
        "state_label": "Rendering",
        "message": payload["message"],
        "progress": {
            "stage": payload["stage"],
            "message": payload["message"],
        },
        "validation": {
            "status": "in_progress",
            "summary": "Worker progress validates before snapshot storage.",
            "checks": [
                {"name": "worker_progress_payload", "status": "pass"},
                {"name": "worker_authorization_redacted", "status": "pass"},
                {"name": "integration_job_snapshot", "status": "pass"},
            ],
        },
        "warnings": [
            "worker_progress_streaming_scaffold",
            "worker_authorization_redacted",
            "integration_chart_artifact_file_not_written",
        ],
    }


def _build_worker_progress_event(
    store: dict[str, Any],
    *,
    hass: Any,
    entry_id: str,
    job: dict[str, Any],
    worker: dict[str, Any],
    worker_authorization: str,
    request_id: str,
    payload: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    event_number = store["next_worker_progress_event_number"]
    event_id = f"{store['entry_id']}-worker-progress-{event_number:03d}"
    return {
        "event_id": event_id,
        "type": "isolinear_worker_progress",
        "config_entry_id": store["entry_id"],
        "job_id": job["job_id"],
        "worker": {
            "type": worker.get("type") or "http_json_worker",
            "role": worker.get("role") or "renderer",
            "endpoint_url": worker.get("endpoint_url") or "",
            "api_version": worker.get("api_version") or 1,
            "authorization": "Bearer <redacted>" if worker_authorization.startswith("Bearer ") else "<missing>",
        },
        "request_id": request_id,
        "sequence": payload["sequence"],
        "stage": payload["stage"],
        "message": payload["message"],
        "percent_complete": payload["percent_complete"],
        "subscription_ids": _subscription_ids_for_job(hass, entry_id, job["job_id"]),
        "snapshot_id": snapshot["snapshot_id"],
        "snapshot": deepcopy(snapshot),
        "validation": {
            "status": "pass",
            "summary": "Worker progress payload and rendering snapshot validate before storage.",
            "checks": [
                {"name": "worker_progress_payload", "status": "pass"},
                {"name": "integration_worker_progress_schema", "status": "pass"},
                {"name": "integration_job_snapshot_schema", "status": "pass"},
                {"name": "worker_authorization_redacted", "status": "pass"},
            ],
        },
        "warnings": [
            "worker_progress_streaming_scaffold",
            "worker_authorization_redacted",
            "bounded_in_memory_progress_event",
        ],
    }


def _record_worker_dispatch(
    store: dict[str, Any],
    *,
    hass: Any,
    entry_id: str,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    artifact: dict[str, Any],
    render_plan: dict[str, Any],
    serve_artifact: bool = False,
) -> dict[str, Any]:
    worker_client = get_worker_render_client(hass, entry_id)
    if worker_client is None:
        return {
            "accepted": True,
            "code": "worker_renderer_not_configured",
            "worker_called": False,
            "chart_rendering_called": False,
            "worker_progress_streaming_called": False,
            "worker_dispatch": None,
            "worker_progress_events": [],
        }

    token = worker_client_token(worker_client)
    worker_summary = {
        "worker": worker_client_metadata(worker_client),
        "authorization": "Bearer <redacted>" if token else "<missing>",
    }
    if token is None:
        return {
            "accepted": False,
            "code": "worker_renderer_token_missing",
            "worker_called": False,
            "chart_rendering_called": False,
            "worker_progress_streaming_called": False,
            "worker": worker_summary,
        }

    render_request = _build_worker_render_request(
        store,
        hass=hass,
        entry_id=entry_id,
        render_plan=render_plan,
    )
    render_request_validation = validate_render_request_contract(render_request)
    if not render_request_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_worker_render_request",
            "validation": render_request_validation,
            "worker_called": False,
            "chart_rendering_called": False,
            "worker_progress_streaming_called": False,
            "worker": worker_summary,
        }

    dispatch_number = store["next_worker_dispatch_number"]
    transport_request = build_worker_transport_request(
        render_request,
        request_id=f"{store['entry_id']}-worker-transport-{dispatch_number:03d}",
        worker_token=token,
    )
    transport_validation = validate_worker_transport_request_contract(transport_request)
    if not transport_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_worker_transport_request",
            "validation": transport_validation,
            "worker_called": False,
            "chart_rendering_called": False,
            "worker_progress_streaming_called": False,
            "worker": worker_summary,
        }

    render_method = getattr(worker_client, "render_chart", None)
    if not callable(render_method):
        return {
            "accepted": False,
            "code": "worker_renderer_unavailable",
            "worker_called": False,
            "chart_rendering_called": False,
            "worker_progress_streaming_called": False,
            "worker": worker_summary,
        }

    worker_response = render_method(transport_request)
    if not isinstance(worker_response, dict) or not worker_response.get("accepted"):
        classification_result = _record_worker_transport_failure_classification(
            store,
            job=job,
            source_snapshot=source_snapshot,
            worker=worker_client_metadata(worker_client),
            transport_request=transport_request,
            worker_response=worker_response,
        )
        if not classification_result["accepted"]:
            return {
                "accepted": False,
                "code": classification_result["code"],
                "validation": classification_result.get("validation"),
                "worker_called": True,
                "chart_rendering_called": True,
                "worker_progress_streaming_called": False,
                "worker": worker_summary,
            }

        classification = classification_result["worker_transport_failure_classification"]
        return {
            "accepted": False,
            "code": classification["failure"]["code"],
            "worker_called": True,
            "chart_rendering_called": True,
            "worker_progress_streaming_called": False,
            "worker": worker_summary,
            "worker_transport_failure_classification": classification,
            "worker_transport_failure_classification_written": True,
        }

    render_result = worker_response.get("render_result")
    render_result_validation = validate_render_result_contract(render_result)
    if not render_result_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_worker_render_result",
            "validation": render_result_validation,
            "worker_called": True,
            "chart_rendering_called": True,
            "worker_progress_streaming_called": False,
            "worker": worker_summary,
        }
    if not isinstance(render_result, dict) or render_result.get("status") != "success":
        retry_policy_result = _record_worker_retry_policy(
            store,
            job=job,
            source_snapshot=source_snapshot,
            worker=worker_response.get("worker") or worker_client_metadata(worker_client),
            transport_request=transport_request,
            failure_code=_worker_failure_code(render_result),
            retry_safe=True,
        )
        if not retry_policy_result["accepted"]:
            return {
                "accepted": False,
                "code": retry_policy_result["code"],
                "validation": retry_policy_result.get("validation"),
                "worker_called": True,
                "chart_rendering_called": True,
                "worker_progress_streaming_called": False,
                "worker": worker_summary,
            }
        return {
            "accepted": False,
            "code": _worker_failure_code(render_result),
            "validation": render_result_validation,
            "worker_called": True,
            "chart_rendering_called": True,
            "worker_progress_streaming_called": False,
            "worker": worker_summary,
            "worker_retry_policy": retry_policy_result.get("worker_retry_policy"),
            "worker_retry_policy_written": True,
        }

    artifact_result = None
    if serve_artifact:
        artifact_result = _record_worker_rendered_artifact(
            hass,
            entry_id,
            artifact=artifact,
            render_result=render_result,
        )
        if not artifact_result["accepted"]:
            retry_policy_result = _record_worker_retry_policy(
                store,
                job=job,
                source_snapshot=source_snapshot,
                worker=worker_response.get("worker") or worker_client_metadata(worker_client),
                transport_request=transport_request,
                failure_code=artifact_result["code"],
                retry_safe=False,
            )
            if not retry_policy_result["accepted"]:
                return {
                    "accepted": False,
                    "code": retry_policy_result["code"],
                    "validation": retry_policy_result.get("validation"),
                    "worker_called": True,
                    "chart_rendering_called": True,
                    "chart_artifact_written": False,
                    "worker_progress_streaming_called": False,
                    "worker": worker_summary,
                }
            return {
                "accepted": False,
                "code": artifact_result["code"],
                "validation": artifact_result.get("validation"),
                "worker_called": True,
                "chart_rendering_called": True,
                "chart_artifact_written": False,
                "worker_progress_streaming_called": False,
                "worker": worker_summary,
                "worker_retry_policy": retry_policy_result.get("worker_retry_policy"),
                "worker_retry_policy_written": True,
            }
        artifact = artifact_result["artifact"]
        render_result = artifact_result["render_result"]

    worker_dispatch = _build_worker_dispatch(
        store,
        job=job,
        source_snapshot=source_snapshot,
        artifact=artifact,
        render_plan=render_plan,
        worker=worker_response.get("worker") or worker_client_metadata(worker_client),
        transport_request=transport_request,
        render_result=render_result,
        chart_artifact_written=artifact_result is not None,
    )
    dispatch_validation = validate_worker_dispatch_contract(worker_dispatch)
    if not dispatch_validation["accepted"]:
        artifact_rollback = _rollback_worker_rendered_artifact(hass, entry_id, artifact_result)
        return {
            "accepted": False,
            "code": "invalid_integration_worker_dispatch",
            "validation": dispatch_validation,
            "worker_called": True,
            "chart_rendering_called": True,
            "chart_artifact_written": False,
            "worker_progress_streaming_called": False,
            "worker": worker_summary,
            "artifact_rollback": artifact_rollback,
        }

    worker_progress_result = _record_worker_progress_events(
        store,
        hass=hass,
        entry_id=entry_id,
        job=job,
        worker=worker_response.get("worker") or worker_client_metadata(worker_client),
        worker_authorization=f"Bearer {token}",
        request_id=transport_request["body"]["request_id"],
        progress_payloads=worker_response.get("progress_events"),
    )
    if not worker_progress_result["accepted"]:
        artifact_rollback = _rollback_worker_rendered_artifact(hass, entry_id, artifact_result)
        return {
            "accepted": False,
            "code": worker_progress_result["code"],
            "validation": worker_progress_result.get("validation"),
            "worker_called": True,
            "chart_rendering_called": True,
            "chart_artifact_written": False,
            "worker_progress_streaming_called": worker_progress_result.get("worker_progress_streaming_called", False),
            "worker": worker_summary,
            "artifact_rollback": artifact_rollback,
        }

    return {
        "accepted": True,
        "code": "accepted",
        "worker_called": True,
        "chart_rendering_called": True,
        "chart_artifact_written": artifact_result is not None,
        "worker_progress_streaming_called": worker_progress_result.get("worker_progress_streaming_called", False),
        "artifact": deepcopy(artifact),
        "artifact_validation": artifact_result.get("artifact_validation") if artifact_result is not None else None,
        "worker_dispatch": worker_dispatch,
        "worker_progress_events": worker_progress_result.get("worker_progress_events", []),
        "validation": dispatch_validation,
        "worker_progress_validation": worker_progress_result.get("validation"),
        "worker": worker_summary,
    }


def _build_artifact_metadata(
    store: dict[str, Any],
    *,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
) -> dict[str, Any]:
    artifact_number = store["next_artifact_number"]
    artifact_id = f"{store['entry_id']}-artifact-{artifact_number:03d}"
    chart = _chart_metadata_for_artifact(
        artifact_id=artifact_id,
        job=job,
        source_snapshot=source_snapshot,
    )
    artifact = {
        "artifact_id": artifact_id,
        "config_entry_id": store["entry_id"],
        "job_id": job["job_id"],
        "source_snapshot_id": source_snapshot["snapshot_id"],
        "artifact_kind": "chart_image",
        "status": "placeholder",
        **chart,
        "render_metadata": {
            "renderer": "artifact_storage_scaffold",
            "render_attempted": False,
            "worker_called": False,
            "chart_rendering_called": False,
        },
        "validation": {
            "status": "pass",
            "summary": "Placeholder artifact metadata validates before storage.",
            "checks": [
                {"name": "integration_job_snapshot", "status": "pass"},
                {"name": "artifact_metadata_schema", "status": "pass"},
                {"name": "worker", "status": "not_called"},
                {"name": "chart_rendering", "status": "not_called"},
            ],
        },
        "warnings": [
            "artifact_storage_scaffold",
            "placeholder_chart_artifact",
            "chart_rendering_not_started",
        ],
    }
    return artifact


def _build_in_process_artifact_metadata(
    artifact: dict[str, Any],
    *,
    render_result: dict[str, Any],
    image_url: str,
) -> dict[str, Any]:
    rendered = deepcopy(artifact)
    render_metadata = render_result.get("render_metadata") if isinstance(render_result, dict) else {}
    rendered["status"] = "rendered"
    rendered["image_url"] = image_url
    rendered["render_metadata"] = {
        "renderer": IN_PROCESS_RENDERER_NAME,
        "render_attempted": True,
        "worker_called": False,
        "chart_rendering_called": True,
    }
    rendered["validation"] = {
        "status": "pass",
        "summary": "In-process trusted Pillow artifact validates before storage.",
        "checks": [
            {"name": "integration_job_snapshot", "status": "pass"},
            {"name": "integration_render_plan", "status": "pass"},
            {"name": "render_request_schema", "status": "pass"},
            {"name": "render_result_schema", "status": "pass"},
            {"name": "pillow_png", "status": "pass"},
            {"name": "worker", "status": "not_called"},
        ],
    }
    rendered["warnings"] = [
        "first_real_vertical_slice",
        "in_process_pillow_renderer",
        "chart_artifact_served_url",
        *list(render_metadata.get("warnings", []) if isinstance(render_metadata, dict) else []),
    ]
    return rendered


def _build_worker_artifact_metadata(
    artifact: dict[str, Any],
    *,
    render_result: dict[str, Any],
    image_url: str,
) -> dict[str, Any]:
    rendered = deepcopy(artifact)
    render_metadata = render_result.get("render_metadata") if isinstance(render_result, dict) else {}
    rendered["status"] = "rendered"
    rendered["image_url"] = image_url
    rendered["render_metadata"] = {
        "renderer": WORKER_RENDERER_NAME,
        "render_attempted": True,
        "worker_called": True,
        "chart_rendering_called": True,
    }
    rendered["validation"] = {
        "status": "pass",
        "summary": "Worker-rendered artifact validates before storage.",
        "checks": [
            {"name": "integration_job_snapshot", "status": "pass"},
            {"name": "integration_render_plan", "status": "pass"},
            {"name": "render_request_schema", "status": "pass"},
            {"name": "render_result_schema", "status": "pass"},
            {"name": "worker_png_payload", "status": "pass"},
            {"name": "worker", "status": "pass"},
        ],
    }
    rendered["warnings"] = [
        "first_real_vertical_slice",
        "worker_renderer",
        "worker_rendered_artifact_serving",
        "worker_render_result_recorded",
        "chart_artifact_served_url",
        *list(render_metadata.get("warnings", []) if isinstance(render_metadata, dict) else []),
    ]
    return rendered


def _store_validated_artifact_metadata(store: dict[str, Any], artifact: dict[str, Any]) -> None:
    artifact_id = artifact["artifact_id"]
    store["next_artifact_number"] += 1
    store["artifact_metadata"][artifact_id] = deepcopy(artifact)
    store["artifact_order"].append(artifact_id)
    store["artifact_by_job_id"][artifact["job_id"]] = artifact_id
    store["latest_artifact"] = deepcopy(artifact)


def _build_render_plan(
    store: dict[str, Any],
    *,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    artifact: dict[str, Any],
    chart_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    render_plan_number = store["next_render_plan_number"]
    render_plan_id = f"{store['entry_id']}-render-plan-{render_plan_number:03d}"
    provider_produced = chart_spec is not None
    planned_chart_spec = deepcopy(chart_spec) if chart_spec is not None else _chart_spec_for_render_plan(
        render_plan_id=render_plan_id,
        job=job,
        source_snapshot=source_snapshot,
    )
    return {
        "render_plan_id": render_plan_id,
        "config_entry_id": store["entry_id"],
        "job_id": job["job_id"],
        "source_snapshot_id": source_snapshot["snapshot_id"],
        "artifact_id": artifact["artifact_id"],
        "status": "planned",
        "render_mode": "safe",
        "renderer": "trusted_chart_spec",
        "chart_spec": planned_chart_spec,
        "history_entity_ids": _source_snapshot_entity_ids(source_snapshot),
        "output": {
            "format": "png",
            "width": 1400,
            "height": 800,
        },
        "validation": {
            "status": "pass",
            "summary": (
                "Provider-produced render plan and chart spec validate before storage."
                if provider_produced
                else "Placeholder render plan and chart spec validate before storage."
            ),
            "checks": [
                {"name": "integration_job_snapshot", "status": "pass"},
                {"name": "integration_artifact_metadata", "status": "pass"},
                {"name": "model_provider", "status": "pass" if provider_produced else "not_called"},
                {"name": "chart_spec_schema", "status": "pass"},
                {"name": "worker", "status": "not_called"},
                {"name": "chart_rendering", "status": "not_called"},
            ],
        },
        "warnings": (
            [
                "model_provider_planning_scaffold",
                "provider_produced_chart_spec",
                "worker_not_called",
                "chart_rendering_not_started",
            ]
            if provider_produced
            else [
                "render_planning_scaffold",
                "placeholder_chart_spec",
                "model_provider_not_called",
                "worker_not_called",
                "chart_rendering_not_started",
            ]
        ),
    }


def _build_model_provider_plan(
    store: dict[str, Any],
    *,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    request: dict[str, Any],
    provider: dict[str, Any],
    planner_result: dict[str, Any],
    chart_spec: dict[str, Any],
) -> dict[str, Any]:
    provider_plan_number = store["next_model_provider_plan_number"]
    provider_plan_id = f"{store['entry_id']}-provider-plan-{provider_plan_number:03d}"
    return {
        "provider_plan_id": provider_plan_id,
        "config_entry_id": store["entry_id"],
        "job_id": job["job_id"],
        "source_snapshot_id": source_snapshot["snapshot_id"],
        "provider": {
            "type": provider.get("type") or "ollama_compatible",
            "role": provider.get("role") or "planner",
            "endpoint_url": provider.get("endpoint_url") or "",
            "model": provider.get("model") or provider.get("planner_model") or "",
        },
        "request": deepcopy(request),
        "status": "chart_spec_ready",
        "planner_result": deepcopy(planner_result),
        "chart_spec": deepcopy(chart_spec),
        "validation": {
            "status": "pass",
            "summary": "PlannerResult and provider-produced ChartSpec validate before storage.",
            "checks": [
                {"name": "planner_result_schema", "status": "pass"},
                {"name": "chart_spec_schema", "status": "pass"},
                {"name": "entity_allowlist", "status": "pass"},
                {"name": "worker", "status": "not_called"},
                {"name": "chart_rendering", "status": "not_called"},
            ],
        },
        "warnings": [
            "model_provider_planning_scaffold",
            "ollama_compatible_planner",
            "worker_not_called",
            "chart_rendering_not_started",
        ],
    }


def _record_model_provider_retry_policy(
    store: dict[str, Any],
    *,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    provider: dict[str, Any],
    request: dict[str, Any],
    provider_response: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(provider_response.get("retry_safe"), bool):
        return {
            "accepted": False,
            "code": "invalid_model_provider_failure",
            "validation": {
                "accepted": False,
                "code": "invalid_model_provider_failure",
                "error": "Provider failure retry_safe must be boolean.",
            },
        }
    if _model_provider_failure_contains_forbidden_material(provider_response):
        return {
            "accepted": False,
            "code": "model_provider_failure_forbidden_material",
            "validation": {
                "accepted": False,
                "code": "model_provider_failure_forbidden_material",
                "error": "Provider failure text contained forbidden material.",
            },
        }

    policy = _build_model_provider_retry_policy(
        store,
        job=job,
        source_snapshot=source_snapshot,
        provider=provider,
        request=request,
        provider_response=provider_response,
    )
    validation = validate_model_provider_retry_policy_contract(policy)
    if not validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_integration_model_provider_retry_policy",
            "validation": validation,
        }

    _store_validated_model_provider_retry_policy(store, policy)
    return {
        "accepted": True,
        "code": "model_provider_retry_policy_recorded",
        "model_provider_retry_policy": deepcopy(policy),
        "validation": validation,
    }


def _build_model_provider_retry_policy(
    store: dict[str, Any],
    *,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    provider: dict[str, Any],
    request: dict[str, Any],
    provider_response: dict[str, Any],
) -> dict[str, Any]:
    policy_number = store["next_model_provider_retry_policy_number"]
    attempt_number = _model_provider_retry_policy_attempt_number(store, job["job_id"])
    eligible = provider_response.get("retry_safe") is True
    delay_seconds = min(60, 5 * (2 ** (attempt_number - 1))) if eligible else 0
    return {
        "policy_id": f"{store['entry_id']}-model-provider-retry-policy-{policy_number:03d}",
        "type": "isolinear_model_provider_retry_policy",
        "config_entry_id": store["entry_id"],
        "job_id": job["job_id"],
        "source_snapshot_id": source_snapshot["snapshot_id"],
        "provider": {
            "type": provider.get("type") or "ollama_compatible",
            "role": provider.get("role") or "planner",
            "endpoint_url": provider.get("endpoint_url") or "",
            "model": provider.get("model") or provider.get("planner_model") or "",
        },
        "request": deepcopy(request),
        "failure": {
            "stage": "model_provider_planning",
            "code": _safe_model_provider_failure_code(provider_response.get("code")),
            "message": _safe_model_provider_failure_message(provider_response.get("message")),
            "retry_safe": eligible,
        },
        "decision": {
            "eligible": eligible,
            "reason": "model_provider_failure_retry_safe" if eligible else "model_provider_failure_not_retry_safe",
            "manual_retry_allowed": eligible,
            "automatic_retry_scheduled": False,
        },
        "backoff": {
            "strategy": "bounded_exponential_scaffold",
            "attempt_number": attempt_number,
            "delay_seconds": delay_seconds,
            "max_delay_seconds": 60,
            "jitter_applied": False,
        },
        "validation": {
            "status": "pass",
            "summary": "Model-provider retry/backoff policy validates before storage.",
            "checks": [
                {"name": "model_provider_failure_observed", "status": "pass"},
                {"name": "model_provider_retry_policy_schema", "status": "pass"},
                {"name": "model_provider_failure_text_sanitized", "status": "pass"},
                {"name": "automatic_retry_not_scheduled", "status": "pass"},
            ],
        },
        "warnings": [
            "model_provider_retry_backoff_policy_scaffold",
            "automatic_retry_not_scheduled",
            "bounded_in_memory_retry_policy",
        ],
    }


def _build_worker_render_request(
    store: dict[str, Any],
    *,
    hass: Any,
    entry_id: str,
    render_plan: dict[str, Any],
) -> dict[str, Any]:
    dispatch_number = store["next_worker_dispatch_number"]
    return {
        "request_id": f"{store['entry_id']}-render-request-{dispatch_number:03d}",
        "render_mode": render_plan["render_mode"],
        "chart_spec": deepcopy(render_plan["chart_spec"]),
        "history_series": _history_series_for_render_plan(
            hass,
            entry_id=entry_id,
            render_plan=render_plan,
        ),
        "derived_intervals": [],
        "output": deepcopy(render_plan["output"]),
        "theme": {},
        "codegen": None,
    }


def _history_series_for_render_plan(
    hass: Any,
    *,
    entry_id: str,
    render_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    store = entry_data.get(DATA_HISTORY_RETRIEVAL, {}) if isinstance(entry_data, dict) else {}
    staged = store.get("series", []) if isinstance(store, dict) else []
    by_entity_id = {
        series.get("entity_id"): series
        for series in staged
        if isinstance(series, dict) and isinstance(series.get("entity_id"), str)
    }
    return [
        deepcopy(by_entity_id[entity_id])
        for entity_id in render_plan.get("history_entity_ids", [])
        if entity_id in by_entity_id
    ]


def _build_worker_dispatch(
    store: dict[str, Any],
    *,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    artifact: dict[str, Any],
    render_plan: dict[str, Any],
    worker: dict[str, Any],
    transport_request: dict[str, Any],
    render_result: dict[str, Any],
    chart_artifact_written: bool = False,
) -> dict[str, Any]:
    dispatch_number = store["next_worker_dispatch_number"]
    dispatch_id = f"{store['entry_id']}-worker-dispatch-{dispatch_number:03d}"
    return {
        "dispatch_id": dispatch_id,
        "config_entry_id": store["entry_id"],
        "job_id": job["job_id"],
        "source_snapshot_id": source_snapshot["snapshot_id"],
        "render_plan_id": render_plan["render_plan_id"],
        "artifact_id": artifact["artifact_id"],
        "status": "render_succeeded",
        "worker": {
            "type": worker.get("type") or "http_json_worker",
            "role": worker.get("role") or "renderer",
            "endpoint_url": worker.get("endpoint_url") or "",
            "api_version": worker.get("api_version") or 1,
        },
        "request": redacted_worker_transport_request(transport_request),
        "render_result": deepcopy(render_result),
        "validation": {
            "status": "pass",
            "summary": "Worker transport request and render result validate before dispatch storage.",
            "checks": [
                {"name": "integration_render_plan", "status": "pass"},
                {"name": "render_request_schema", "status": "pass"},
                {"name": "worker_transport_request_schema", "status": "pass"},
                {"name": "render_result_schema", "status": "pass"},
                {"name": "worker_authorization_redacted", "status": "pass"},
            ],
        },
        "warnings": [
            "worker_dispatch_rendering_scaffold",
            "worker_render_result_recorded",
            "worker_authorization_redacted",
            (
                "worker_rendered_artifact_serving"
                if chart_artifact_written
                else "integration_chart_artifact_file_not_written"
            ),
        ],
    }


def _store_validated_render_plan(store: dict[str, Any], render_plan: dict[str, Any]) -> None:
    render_plan_id = render_plan["render_plan_id"]
    store["next_render_plan_number"] += 1
    store["render_plans"][render_plan_id] = deepcopy(render_plan)
    store["render_plan_order"].append(render_plan_id)
    store["render_plan_by_job_id"][render_plan["job_id"]] = render_plan_id
    store["latest_render_plan"] = deepcopy(render_plan)


def _store_validated_model_provider_plan(store: dict[str, Any], provider_plan: dict[str, Any]) -> None:
    provider_plan_id = provider_plan["provider_plan_id"]
    store["next_model_provider_plan_number"] += 1
    store["model_provider_plans"][provider_plan_id] = deepcopy(provider_plan)
    store["model_provider_plan_order"].append(provider_plan_id)
    store["model_provider_plan_by_job_id"][provider_plan["job_id"]] = provider_plan_id
    store["latest_model_provider_plan"] = deepcopy(provider_plan)


def _model_provider_retry_policy_attempt_number(store: dict[str, Any], job_id: str) -> int:
    return len(store.get("model_provider_retry_policy_ids_by_job_id", {}).get(job_id, [])) + 1


def _store_validated_model_provider_retry_policy(store: dict[str, Any], policy: dict[str, Any]) -> None:
    policy_id = policy["policy_id"]
    store["next_model_provider_retry_policy_number"] += 1
    store["model_provider_retry_policies"][policy_id] = deepcopy(policy)
    store["model_provider_retry_policy_order"].append(policy_id)
    store.setdefault("model_provider_retry_policy_ids_by_job_id", {}).setdefault(policy["job_id"], []).append(
        policy_id
    )
    store["latest_model_provider_retry_policy"] = deepcopy(policy)


def _store_validated_worker_dispatch(store: dict[str, Any], worker_dispatch: dict[str, Any]) -> None:
    dispatch_id = worker_dispatch["dispatch_id"]
    store["next_worker_dispatch_number"] += 1
    store["worker_dispatches"][dispatch_id] = deepcopy(worker_dispatch)
    store["worker_dispatch_order"].append(dispatch_id)
    store["worker_dispatch_by_job_id"][worker_dispatch["job_id"]] = dispatch_id
    store["latest_worker_dispatch"] = deepcopy(worker_dispatch)


def _store_validated_worker_progress_event(store: dict[str, Any], event: dict[str, Any]) -> None:
    event_id = event["event_id"]
    store["next_worker_progress_event_number"] += 1
    store["worker_progress_events"][event_id] = deepcopy(event)
    store["worker_progress_event_order"].append(event_id)
    store.setdefault("worker_progress_event_ids_by_job_id", {}).setdefault(event["job_id"], []).append(event_id)
    store["latest_worker_progress_event"] = deepcopy(event)


def _rollback_artifact_planning_records(
    store: dict[str, Any],
    *,
    artifact: dict[str, Any] | None,
    render_plan: dict[str, Any] | None,
    model_provider_plan: dict[str, Any] | None,
    worker_dispatch: dict[str, Any] | None,
    worker_progress_events: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Remove artifact-planning records whose final job snapshot could not be stored."""
    return {
        "artifact_metadata_removed": _remove_stored_artifact_metadata(store, artifact),
        "render_plan_removed": _remove_stored_render_plan(store, render_plan),
        "model_provider_plan_removed": _remove_stored_model_provider_plan(store, model_provider_plan),
        "worker_dispatch_removed": _remove_stored_worker_dispatch(store, worker_dispatch),
        "worker_progress_events_removed": _remove_stored_worker_progress_events(store, worker_progress_events or []),
    }


def _remove_stored_artifact_metadata(store: dict[str, Any], artifact: dict[str, Any] | None) -> bool:
    if not isinstance(artifact, dict):
        return False
    artifact_id = artifact.get("artifact_id")
    if not isinstance(artifact_id, str):
        return False

    removed = store.get("artifact_metadata", {}).pop(artifact_id, None) is not None
    _remove_ordered_id(store.get("artifact_order", []), artifact_id)
    if store.get("artifact_by_job_id", {}).get(artifact.get("job_id")) == artifact_id:
        store.get("artifact_by_job_id", {}).pop(artifact.get("job_id"), None)
    if _latest_record_id(store.get("latest_artifact"), "artifact_id") == artifact_id:
        store["latest_artifact"] = _latest_stored_record(store, "artifact_metadata", "artifact_order")
    return removed


def _remove_stored_render_plan(store: dict[str, Any], render_plan: dict[str, Any] | None) -> bool:
    if not isinstance(render_plan, dict):
        return False
    render_plan_id = render_plan.get("render_plan_id")
    if not isinstance(render_plan_id, str):
        return False

    removed = store.get("render_plans", {}).pop(render_plan_id, None) is not None
    _remove_ordered_id(store.get("render_plan_order", []), render_plan_id)
    if store.get("render_plan_by_job_id", {}).get(render_plan.get("job_id")) == render_plan_id:
        store.get("render_plan_by_job_id", {}).pop(render_plan.get("job_id"), None)
    if _latest_record_id(store.get("latest_render_plan"), "render_plan_id") == render_plan_id:
        store["latest_render_plan"] = _latest_stored_record(store, "render_plans", "render_plan_order")
    return removed


def _remove_stored_model_provider_plan(
    store: dict[str, Any], provider_plan: dict[str, Any] | None
) -> bool:
    if not isinstance(provider_plan, dict):
        return False
    provider_plan_id = provider_plan.get("provider_plan_id")
    if not isinstance(provider_plan_id, str):
        return False

    removed = store.get("model_provider_plans", {}).pop(provider_plan_id, None) is not None
    _remove_ordered_id(store.get("model_provider_plan_order", []), provider_plan_id)
    if store.get("model_provider_plan_by_job_id", {}).get(provider_plan.get("job_id")) == provider_plan_id:
        store.get("model_provider_plan_by_job_id", {}).pop(provider_plan.get("job_id"), None)
    if _latest_record_id(store.get("latest_model_provider_plan"), "provider_plan_id") == provider_plan_id:
        store["latest_model_provider_plan"] = _latest_stored_record(
            store,
            "model_provider_plans",
            "model_provider_plan_order",
        )
    return removed


def _remove_stored_worker_dispatch(store: dict[str, Any], worker_dispatch: dict[str, Any] | None) -> bool:
    if not isinstance(worker_dispatch, dict):
        return False
    dispatch_id = worker_dispatch.get("dispatch_id")
    if not isinstance(dispatch_id, str):
        return False

    removed = store.get("worker_dispatches", {}).pop(dispatch_id, None) is not None
    _remove_ordered_id(store.get("worker_dispatch_order", []), dispatch_id)
    if store.get("worker_dispatch_by_job_id", {}).get(worker_dispatch.get("job_id")) == dispatch_id:
        store.get("worker_dispatch_by_job_id", {}).pop(worker_dispatch.get("job_id"), None)
    if _latest_record_id(store.get("latest_worker_dispatch"), "dispatch_id") == dispatch_id:
        store["latest_worker_dispatch"] = _latest_stored_record(
            store,
            "worker_dispatches",
            "worker_dispatch_order",
        )
    return removed


def _remove_stored_worker_progress_events(
    store: dict[str, Any],
    worker_progress_events: list[dict[str, Any]],
) -> int:
    removed_count = 0
    for event in worker_progress_events:
        if not isinstance(event, dict):
            continue
        event_id = event.get("event_id")
        if not isinstance(event_id, str):
            continue
        if store.get("worker_progress_events", {}).pop(event_id, None) is not None:
            removed_count += 1
        _remove_ordered_id(store.get("worker_progress_event_order", []), event_id)
        job_id = event.get("job_id")
        event_ids_by_job = store.get("worker_progress_event_ids_by_job_id", {})
        if event_ids_by_job.get(job_id):
            _remove_ordered_id(event_ids_by_job[job_id], event_id)
            if not event_ids_by_job[job_id]:
                event_ids_by_job.pop(job_id, None)

    removed_ids = {event.get("event_id") for event in worker_progress_events if isinstance(event, dict)}
    if _latest_record_id(store.get("latest_worker_progress_event"), "event_id") in removed_ids:
        store["latest_worker_progress_event"] = _latest_stored_record(
            store,
            "worker_progress_events",
            "worker_progress_event_order",
        )
    return removed_count


def _remove_ordered_id(order: list[Any], value: str) -> None:
    while value in order:
        order.remove(value)


def _latest_record_id(record: Any, id_key: str) -> str | None:
    return record.get(id_key) if isinstance(record, dict) and isinstance(record.get(id_key), str) else None


def _latest_stored_record(store: dict[str, Any], records_key: str, order_key: str) -> dict[str, Any] | None:
    records = store.get(records_key, {})
    for record_id in reversed(store.get(order_key, [])):
        record = records.get(record_id)
        if isinstance(record, dict):
            return deepcopy(record)
    return None


def _record_worker_transport_failure_classification(
    store: dict[str, Any],
    *,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    worker: dict[str, Any],
    transport_request: dict[str, Any],
    worker_response: Any,
) -> dict[str, Any]:
    classification = _build_worker_transport_failure_classification(
        store,
        job=job,
        source_snapshot=source_snapshot,
        worker=worker,
        transport_request=transport_request,
        worker_response=worker_response,
    )
    validation = validate_worker_transport_failure_classification_contract(classification)
    if not validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_integration_worker_transport_failure_classification",
            "validation": validation,
        }

    _store_validated_worker_transport_failure_classification(store, classification)
    return {
        "accepted": True,
        "code": "worker_transport_failure_classification_recorded",
        "worker_transport_failure_classification": deepcopy(classification),
        "validation": validation,
    }


def _build_worker_transport_failure_classification(
    store: dict[str, Any],
    *,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    worker: dict[str, Any],
    transport_request: dict[str, Any],
    worker_response: Any,
) -> dict[str, Any]:
    classification_number = store["next_worker_transport_failure_classification_number"]
    attempt_number = _worker_transport_failure_classification_attempt_number(store, job["job_id"])
    failure_code = _safe_worker_transport_failure_code(
        worker_response.get("code") if isinstance(worker_response, dict) else None
    )
    retry_safe = (
        bool(worker_response.get("retry_safe"))
        if isinstance(worker_response, dict) and isinstance(worker_response.get("retry_safe"), bool)
        else False
    )
    family = _worker_transport_failure_family(failure_code)
    delay_seconds = min(60, 5 * (2 ** (attempt_number - 1))) if retry_safe else 0
    return {
        "classification_id": f"{store['entry_id']}-worker-transport-failure-{classification_number:03d}",
        "type": "isolinear_worker_transport_failure_classification",
        "config_entry_id": store["entry_id"],
        "job_id": job["job_id"],
        "source_snapshot_id": source_snapshot["snapshot_id"],
        "worker": {
            "type": worker.get("type") or "http_json_worker",
            "role": worker.get("role") or "renderer",
            "endpoint_url": worker.get("endpoint_url") or "",
            "api_version": worker.get("api_version") or 1,
            "authorization": "Bearer <redacted>",
        },
        "request": redacted_worker_transport_request(transport_request),
        "failure": {
            "stage": "worker_transport",
            "code": failure_code,
            "message": _safe_worker_transport_failure_message(
                worker_response.get("message") if isinstance(worker_response, dict) else None
            ),
            "retry_safe": retry_safe,
        },
        "classification": {
            "family": family,
            "retry_eligible": retry_safe,
            "reason": f"worker_transport_{family}_{'retry_safe' if retry_safe else 'not_retry_safe'}",
            "manual_retry_allowed": retry_safe,
            "automatic_retry_scheduled": False,
        },
        "backoff": {
            "strategy": "bounded_exponential_scaffold",
            "attempt_number": attempt_number,
            "delay_seconds": delay_seconds,
            "max_delay_seconds": 60,
            "jitter_applied": False,
        },
        "validation": {
            "status": "pass",
            "summary": "Worker transport failure classification validates before storage.",
            "checks": [
                {"name": "worker_transport_failure_observed", "status": "pass"},
                {"name": "worker_transport_failure_classification_schema", "status": "pass"},
                {"name": "worker_failure_text_sanitized", "status": "pass"},
                {"name": "worker_authorization_redacted", "status": "pass"},
                {"name": "automatic_retry_not_scheduled", "status": "pass"},
            ],
        },
        "warnings": [
            "worker_transport_failure_retry_classification_scaffold",
            "worker_authorization_redacted",
            "automatic_retry_not_scheduled",
            "bounded_in_memory_transport_classification",
        ],
    }


def _worker_transport_failure_classification_attempt_number(store: dict[str, Any], job_id: str) -> int:
    return len(store.get("worker_transport_failure_classification_ids_by_job_id", {}).get(job_id, [])) + 1


def _store_validated_worker_transport_failure_classification(
    store: dict[str, Any],
    classification: dict[str, Any],
) -> None:
    classification_id = classification["classification_id"]
    store["next_worker_transport_failure_classification_number"] += 1
    store["worker_transport_failure_classifications"][classification_id] = deepcopy(classification)
    store["worker_transport_failure_classification_order"].append(classification_id)
    store.setdefault("worker_transport_failure_classification_ids_by_job_id", {}).setdefault(
        classification["job_id"],
        [],
    ).append(classification_id)
    store["latest_worker_transport_failure_classification"] = deepcopy(classification)


def _record_worker_retry_policy(
    store: dict[str, Any],
    *,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    worker: dict[str, Any],
    transport_request: dict[str, Any],
    failure_code: str,
    retry_safe: bool,
) -> dict[str, Any]:
    policy = _build_worker_retry_policy(
        store,
        job=job,
        source_snapshot=source_snapshot,
        worker=worker,
        transport_request=transport_request,
        failure_code=failure_code,
        retry_safe=retry_safe,
    )
    validation = validate_worker_retry_policy_contract(policy)
    if not validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_integration_worker_retry_policy",
            "validation": validation,
        }

    _store_validated_worker_retry_policy(store, policy)
    return {
        "accepted": True,
        "code": "worker_retry_policy_recorded",
        "worker_retry_policy": deepcopy(policy),
        "validation": validation,
    }


def _build_worker_retry_policy(
    store: dict[str, Any],
    *,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    worker: dict[str, Any],
    transport_request: dict[str, Any],
    failure_code: str,
    retry_safe: bool,
) -> dict[str, Any]:
    policy_number = store["next_worker_retry_policy_number"]
    attempt_number = _worker_retry_policy_attempt_number(store, job["job_id"])
    delay_seconds = min(60, 5 * (2 ** (attempt_number - 1)))
    normalized_failure_code = _safe_worker_failure_code(failure_code)
    eligible = bool(retry_safe)
    return {
        "policy_id": f"{store['entry_id']}-worker-retry-policy-{policy_number:03d}",
        "type": "isolinear_worker_retry_policy",
        "config_entry_id": store["entry_id"],
        "job_id": job["job_id"],
        "source_snapshot_id": source_snapshot["snapshot_id"],
        "worker": {
            "type": worker.get("type") or "http_json_worker",
            "role": worker.get("role") or "renderer",
            "endpoint_url": worker.get("endpoint_url") or "",
            "api_version": worker.get("api_version") or 1,
            "authorization": "Bearer <redacted>",
        },
        "request": redacted_worker_transport_request(transport_request),
        "failure": {
            "stage": "worker_render",
            "code": normalized_failure_code,
            "message": "Worker render failed before scaffold artifact metadata was accepted.",
            "retry_safe": eligible,
        },
        "decision": {
            "eligible": eligible,
            "reason": "worker_failure_retry_safe" if eligible else "worker_failure_not_retry_safe",
            "manual_retry_allowed": eligible,
            "automatic_retry_scheduled": False,
        },
        "backoff": {
            "strategy": "bounded_exponential_scaffold",
            "attempt_number": attempt_number,
            "delay_seconds": delay_seconds if eligible else 0,
            "max_delay_seconds": 60,
            "jitter_applied": False,
        },
        "validation": {
            "status": "pass",
            "summary": "Worker retry/backoff policy validates before storage.",
            "checks": [
                {"name": "worker_failure_observed", "status": "pass"},
                {"name": "worker_retry_policy_schema", "status": "pass"},
                {"name": "worker_authorization_redacted", "status": "pass"},
                {"name": "automatic_retry_not_scheduled", "status": "pass"},
            ],
        },
        "warnings": [
            "worker_retry_backoff_policy_scaffold",
            "worker_authorization_redacted",
            "automatic_retry_not_scheduled",
            "bounded_in_memory_retry_policy",
        ],
    }


def _worker_retry_policy_attempt_number(store: dict[str, Any], job_id: str) -> int:
    return len(store.get("worker_retry_policy_ids_by_job_id", {}).get(job_id, [])) + 1


def _store_validated_worker_retry_policy(store: dict[str, Any], policy: dict[str, Any]) -> None:
    policy_id = policy["policy_id"]
    store["next_worker_retry_policy_number"] += 1
    store["worker_retry_policies"][policy_id] = deepcopy(policy)
    store["worker_retry_policy_order"].append(policy_id)
    store.setdefault("worker_retry_policy_ids_by_job_id", {}).setdefault(policy["job_id"], []).append(policy_id)
    store["latest_worker_retry_policy"] = deepcopy(policy)


def _subscription_ids_for_job(hass: Any, entry_id: str, job_id: str) -> list[str]:
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    store = entry_data.get(DATA_JOB_STATE, {}) if isinstance(entry_data, dict) else {}
    subscriptions = store.get("subscriptions", {}) if isinstance(store, dict) else {}
    subscription_order = store.get("subscription_order", []) if isinstance(store, dict) else []
    return [
        subscription_id
        for subscription_id in subscription_order
        if (
            subscription_id in subscriptions
            and isinstance(subscriptions[subscription_id], dict)
            and subscriptions[subscription_id].get("job_id") == job_id
        )
    ]


def validate_artifact_metadata_contract(artifact: Any) -> dict[str, Any]:
    """Validate IntegrationArtifactMetadata against the repo JSON Schema."""
    try:
        schema = load_schema_document(ARTIFACT_METADATA_SCHEMA_PATH)
        _validate_json_schema(artifact, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_artifact_metadata",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(ARTIFACT_METADATA_SCHEMA_PATH),
    }


def validate_render_plan_contract(render_plan: Any) -> dict[str, Any]:
    """Validate IntegrationRenderPlan and its placeholder ChartSpec."""
    try:
        schema = load_schema_document(RENDER_PLAN_SCHEMA_PATH)
        _validate_json_schema(render_plan, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_render_plan",
            "error": str(exc),
        }

    chart_validation = validate_chart_spec_contract(render_plan.get("chart_spec") if isinstance(render_plan, dict) else None)
    if not chart_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_chart_spec",
            "chart_validation": chart_validation,
        }

    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(RENDER_PLAN_SCHEMA_PATH),
        "chart_schema": str(CHART_SPEC_SCHEMA_PATH),
    }


def validate_worker_dispatch_contract(worker_dispatch: Any) -> dict[str, Any]:
    """Validate IntegrationWorkerDispatch and its nested render result."""
    try:
        schema = load_schema_document(WORKER_DISPATCH_SCHEMA_PATH)
        _validate_json_schema(worker_dispatch, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_worker_dispatch",
            "error": str(exc),
        }

    render_result_validation = validate_render_result_contract(
        worker_dispatch.get("render_result") if isinstance(worker_dispatch, dict) else None
    )
    if not render_result_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_worker_render_result",
            "render_result_validation": render_result_validation,
        }

    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(WORKER_DISPATCH_SCHEMA_PATH),
        "render_result_schema": str(RENDER_RESULT_SCHEMA_PATH),
    }


def validate_worker_progress_contract(worker_progress: Any) -> dict[str, Any]:
    """Validate IntegrationWorkerProgress and its nested job snapshot."""
    try:
        schema = load_schema_document(WORKER_PROGRESS_SCHEMA_PATH)
        _validate_json_schema(worker_progress, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_worker_progress",
            "error": str(exc),
        }

    snapshot_validation = validate_job_snapshot_contract(
        worker_progress.get("snapshot") if isinstance(worker_progress, dict) else None
    )
    if not snapshot_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_worker_progress_snapshot",
            "snapshot_validation": snapshot_validation,
        }

    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(WORKER_PROGRESS_SCHEMA_PATH),
        "snapshot_schema": str(schema_path("integration-job-snapshot.schema.json")),
    }


def validate_worker_retry_policy_contract(worker_retry_policy: Any) -> dict[str, Any]:
    """Validate IntegrationWorkerRetryPolicy against the repo JSON Schema."""
    try:
        schema = load_schema_document(WORKER_RETRY_POLICY_SCHEMA_PATH)
        _validate_json_schema(worker_retry_policy, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_worker_retry_policy",
            "error": str(exc),
        }

    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(WORKER_RETRY_POLICY_SCHEMA_PATH),
    }


def validate_model_provider_retry_policy_contract(model_provider_retry_policy: Any) -> dict[str, Any]:
    """Validate IntegrationModelProviderRetryPolicy against the repo JSON Schema."""
    try:
        schema = load_schema_document(MODEL_PROVIDER_RETRY_POLICY_SCHEMA_PATH)
        _validate_json_schema(model_provider_retry_policy, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_model_provider_retry_policy",
            "error": str(exc),
        }

    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(MODEL_PROVIDER_RETRY_POLICY_SCHEMA_PATH),
    }


def validate_worker_transport_failure_classification_contract(classification: Any) -> dict[str, Any]:
    """Validate IntegrationWorkerTransportFailureClassification against the repo JSON Schema."""
    try:
        schema = load_schema_document(WORKER_TRANSPORT_FAILURE_CLASSIFICATION_SCHEMA_PATH)
        _validate_json_schema(classification, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_worker_transport_failure_classification",
            "error": str(exc),
        }

    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(WORKER_TRANSPORT_FAILURE_CLASSIFICATION_SCHEMA_PATH),
    }


def validate_worker_transport_request_contract(request: Any) -> dict[str, Any]:
    """Validate WorkerTransportRequest and its nested RenderRequest."""
    try:
        schema = load_schema_document(WORKER_TRANSPORT_REQUEST_SCHEMA_PATH)
        _validate_json_schema(request, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_worker_transport_request",
            "error": str(exc),
        }

    body = request.get("body") if isinstance(request, dict) else None
    render_request_validation = validate_render_request_contract(
        body.get("render_request") if isinstance(body, dict) else None
    )
    if not render_request_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_worker_render_request",
            "render_request_validation": render_request_validation,
        }

    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(WORKER_TRANSPORT_REQUEST_SCHEMA_PATH),
        "render_request_schema": str(RENDER_REQUEST_SCHEMA_PATH),
    }


def validate_render_request_contract(render_request: Any) -> dict[str, Any]:
    """Validate RenderRequest, ChartSpec, and HistorySeries before worker dispatch."""
    try:
        schema = load_schema_document(RENDER_REQUEST_SCHEMA_PATH)
        _validate_json_schema(render_request, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_worker_render_request",
            "error": str(exc),
        }

    chart_validation = validate_chart_spec_contract(
        render_request.get("chart_spec") if isinstance(render_request, dict) else None
    )
    if not chart_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_chart_spec",
            "chart_validation": chart_validation,
        }

    history_validation = validate_history_series_collection_contract(
        render_request.get("history_series") if isinstance(render_request, dict) else None
    )
    if not history_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_history_series",
            "history_validation": history_validation,
        }

    history_entity_ids = {
        item.get("entity_id")
        for item in render_request.get("history_series", [])
        if isinstance(item, dict)
    }
    render_plan_entity_ids = _chart_spec_entity_ids(render_request.get("chart_spec", {}))["entity_ids"]
    missing_entity_ids = sorted(
        entity_id
        for entity_id in render_plan_entity_ids
        if entity_id not in history_entity_ids
    )
    if missing_entity_ids:
        return {
            "accepted": False,
            "code": "missing_worker_history_series",
            "missing_entity_ids": missing_entity_ids,
        }

    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(RENDER_REQUEST_SCHEMA_PATH),
        "chart_schema": str(CHART_SPEC_SCHEMA_PATH),
        "history_schema": str(schema_path("history-series.schema.json")),
    }


def validate_render_result_contract(render_result: Any) -> dict[str, Any]:
    """Validate RenderResult before worker dispatch metadata storage."""
    try:
        schema = load_schema_document(RENDER_RESULT_SCHEMA_PATH)
        _validate_json_schema(render_result, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_worker_render_result",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(RENDER_RESULT_SCHEMA_PATH),
    }


def validate_model_provider_plan_contract(provider_plan: Any) -> dict[str, Any]:
    """Validate IntegrationModelProviderPlan and its nested planner output."""
    try:
        schema = load_schema_document(MODEL_PROVIDER_PLAN_SCHEMA_PATH)
        _validate_json_schema(provider_plan, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_model_provider_plan",
            "error": str(exc),
        }

    planner_validation = validate_planner_result_contract(
        provider_plan.get("planner_result") if isinstance(provider_plan, dict) else None
    )
    if not planner_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_planner_result",
            "planner_validation": planner_validation,
        }

    chart_validation = validate_chart_spec_contract(
        provider_plan.get("chart_spec") if isinstance(provider_plan, dict) else None
    )
    if not chart_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_model_provider_chart_spec",
            "chart_validation": chart_validation,
        }

    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(MODEL_PROVIDER_PLAN_SCHEMA_PATH),
        "planner_schema": str(PLANNER_RESULT_SCHEMA_PATH),
        "chart_schema": str(CHART_SPEC_SCHEMA_PATH),
    }


def validate_planner_result_contract(planner_result: Any) -> dict[str, Any]:
    """Validate PlannerResult against the repo JSON Schema."""
    try:
        schema = load_schema_document(PLANNER_RESULT_SCHEMA_PATH)
        _validate_json_schema(planner_result, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_planner_result",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(PLANNER_RESULT_SCHEMA_PATH),
    }


def validate_chart_spec_contract(chart_spec: Any) -> dict[str, Any]:
    """Validate a placeholder ChartSpec against the repo JSON Schema."""
    try:
        schema = load_schema_document(CHART_SPEC_SCHEMA_PATH)
        _validate_json_schema(chart_spec, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_chart_spec",
            "error": str(exc),
        }
    duplicate_error = _check_chart_spec_no_duplicate_series_sources(chart_spec)
    if duplicate_error:
        return duplicate_error
    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(CHART_SPEC_SCHEMA_PATH),
    }


def _check_chart_spec_no_duplicate_series_sources(chart_spec: Any) -> dict[str, Any] | None:
    """Return an error if two series reference the same (type, entity_id, attribute) source.

    A planner that returns two series from the same source is always wrong — the
    renderer would draw two identical lanes (or a hallucinated label over real
    data). This catches that class of model error before the chart reaches the
    renderer.
    """
    if not isinstance(chart_spec, dict):
        return None
    series_list = chart_spec.get("series", [])
    if not isinstance(series_list, list):
        return None
    seen: dict[tuple, int] = {}
    for i, series in enumerate(series_list):
        if not isinstance(series, dict):
            continue
        source = series.get("source")
        if not isinstance(source, dict):
            continue
        key = (source.get("type"), source.get("entity_id"), source.get("attribute"))
        if key in seen:
            return {
                "accepted": False,
                "code": "invalid_chart_spec",
                "error": (
                    f"series[{i}] duplicates the source of series[{seen[key]}]: "
                    f"type={key[0]!r} entity_id={key[1]!r} attribute={key[2]!r}"
                ),
            }
        seen[key] = i
    return None


def validate_model_provider_chart_spec_entities(
    chart_spec: dict[str, Any],
    source_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Ensure provider-produced chart specs reference only approved source entities."""
    return validate_model_provider_output_entities(chart_spec, chart_spec, source_snapshot)


def validate_model_provider_output_entities(
    planner_result: dict[str, Any],
    chart_spec: dict[str, Any],
    source_snapshot: dict[str, Any],
    approved_catalog_entity_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Ensure provider output references only approved, disclosed entity IDs.

    Validation is *structural*: it inspects the fields that actually mean "use
    this entity" — chart-spec ``series``/``overlays`` sources and persisted
    ``memory_proposals`` entity references — not free-text fields such as
    ``chart_id``, ``title``, ``notes``, ``reasoning_summary``, or axis
    metadata. An entity-shaped token in those inert fields cannot reach a data
    path (the renderer only fetches from structured sources), so flagging them
    only produced false positives — e.g. a timeline a small model named
    ``binary_sensor.kitchen_door_timeline`` after its own entity.

    Disambiguates the failure (ADR-0022): a reference to an entity absent from
    the approved catalog is a true allowlist breach
    (``model_provider_referenced_unapproved_entity``); a reference to an entity
    that is approved but was not disclosed for this job is a substitution
    (``model_provider_substituted_entity``).
    """
    approved_entity_ids = set(_source_snapshot_entity_ids(source_snapshot))
    catalog_entity_ids = set(approved_catalog_entity_ids or []) | approved_entity_ids
    structured_refs = _chart_spec_entity_ids(chart_spec)
    memory_proposal_entity_ids = _memory_proposal_entity_ids(planner_result)
    referenced_entity_ids = structured_refs["entity_ids"] | memory_proposal_entity_ids
    rejected_entity_ids = sorted(referenced_entity_ids - approved_entity_ids)
    if rejected_entity_ids or structured_refs["unsupported_source_refs"]:
        unapproved_entity_ids = sorted(set(rejected_entity_ids) - catalog_entity_ids)
        substituted_entity_ids = sorted(set(rejected_entity_ids) & catalog_entity_ids)
        if unapproved_entity_ids or structured_refs["unsupported_source_refs"]:
            code = "model_provider_referenced_unapproved_entity"
        else:
            code = "model_provider_substituted_entity"
        return {
            "accepted": False,
            "code": code,
            "approved_entity_ids": sorted(approved_entity_ids),
            "referenced_entity_ids": sorted(referenced_entity_ids),
            "rejected_entity_ids": rejected_entity_ids,
            "unapproved_entity_ids": unapproved_entity_ids,
            "substituted_entity_ids": substituted_entity_ids,
            "unsupported_source_refs": structured_refs["unsupported_source_refs"],
        }
    return {
        "accepted": True,
        "code": "accepted",
        "approved_entity_ids": sorted(approved_entity_ids),
        "referenced_entity_ids": sorted(referenced_entity_ids),
    }


def _resolve_render_family(
    catalog_items: list[dict[str, Any]],
    requested_entity_ids: list[str],
) -> dict[str, Any]:
    """Deterministically choose the render family from resolved entity kinds (ADR-0022).

    Families: ``time_series`` (all numeric), ``timeline`` (all binary/categorical),
    ``time_series_overlay`` (exactly one numeric primary line + one or more
    binary/categorical ``shaded_intervals`` overlays — ADR-0022 D4/D5), and
    ``mixed`` (an ambiguous numeric+categorical set, e.g. two numeric series mixed
    with a binary, where the primary line cannot be chosen deterministically).
    """
    by_id = {item["entity_id"]: item for item in catalog_items}
    numeric_entity_ids: list[str] = []
    binary_entity_ids: list[str] = []
    state_entity_ids: list[str] = []  # all non-numeric (binary + categorical), for the timeline family
    kinds: set[str] = set()
    for entity_id in requested_entity_ids:
        item = by_id.get(entity_id)
        if item is None:
            continue
        kind = classify_series_kind(item)
        kinds.add(kind)
        if kind == "numeric":
            numeric_entity_ids.append(entity_id)
        elif kind == "binary_state":
            binary_entity_ids.append(entity_id)
            state_entity_ids.append(entity_id)
        else:
            state_entity_ids.append(entity_id)
    has_numeric = bool(numeric_entity_ids)
    has_state = bool(state_entity_ids)
    # Overlay composition is binary-only (ADR-0022 D4 scope): shaded_intervals
    # shade an "on" region. A non-binary categorical mixed with numeric has no
    # "on" region, so it stays ambiguous (mixed) rather than shading nothing.
    overlay_eligible = (
        len(numeric_entity_ids) == 1 and binary_entity_ids and len(state_entity_ids) == len(binary_entity_ids)
    )
    if has_numeric and has_state:
        family = "time_series_overlay" if overlay_eligible else "mixed"
    elif has_state:
        family = "timeline"
    else:
        family = "time_series"
    return {
        "family": family,
        "kinds": sorted(kinds),
        "numeric_entity_ids": numeric_entity_ids,
        "categorical_entity_ids": state_entity_ids,
        "overlay_entity_ids": binary_entity_ids,
    }


# Binary states treated as "on"/active for shaded_intervals overlays (ADR-0022).
_OVERLAY_ACTIVE_VALUES = ["on"]


def _compose_binary_overlays(
    chart_spec: dict[str, Any],
    *,
    overlay_entity_ids: list[str],
    catalog_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Inject binary entities as shaded_intervals overlays on a numeric spec (ADR-0022 D4/D5).

    The model plans only the numeric primary series; the integration appends one
    overlay per binary entity deterministically so the model never composes the
    overlay. The overlay source is the approved binary entity; "on" regions are
    shaded behind the primary line.
    """
    by_id = {item["entity_id"]: item for item in catalog_items}
    composed = deepcopy(chart_spec)
    overlays = list(composed.get("overlays") or [])
    for index, entity_id in enumerate(overlay_entity_ids, start=1):
        label = by_id.get(entity_id, {}).get("friendly_name") or entity_id
        overlays.append(
            {
                "overlay_id": f"overlay-{index:03d}",
                "label": label,
                "source": {"type": "entity", "entity_id": entity_id, "attribute": None},
                "render_as": "shaded_intervals",
                "active_values": list(_OVERLAY_ACTIVE_VALUES),
            }
        )
    composed["overlays"] = overlays
    return composed


def _accepted(
    code: str,
    command: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    run: dict[str, Any],
    history_result: dict[str, Any] | None = None,
    approved_entity_catalog_read: bool,
    home_assistant_history_read: bool = False,
    history_retrieval_written: bool = False,
    job_state_written: bool = False,
    job_orchestration_written: bool = False,
    retry_behavior_called: bool = False,
) -> dict[str, Any]:
    result = {
        "accepted": True,
        "code": code,
        "type": command["type"],
        "version": command["version"],
        "config_entry_id": command["config_entry_id"],
        "job_id": snapshot["job_id"],
        "snapshot": deepcopy(snapshot),
        "run": deepcopy(run),
        "orchestration": job_orchestration_side_effects(
            approved_entity_catalog_read=approved_entity_catalog_read,
            home_assistant_history_read=home_assistant_history_read,
            history_retrieval_written=history_retrieval_written,
            job_state_written=job_state_written,
            job_orchestration_written=job_orchestration_written,
            retry_behavior_called=retry_behavior_called,
        ),
    }
    if history_result is not None:
        result["history"] = {
            "code": history_result["code"],
            "accepted": history_result["accepted"],
            "store": history_result.get("store"),
            "requested_entity_ids": history_result.get("requested_entity_ids"),
            "rejected_entity_ids": history_result.get("rejected_entity_ids", []),
            "missing_entity_ids": history_result.get("missing_entity_ids", []),
        }
    return result


def _accepted_subscription(
    code: str,
    command: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    subscription: dict[str, Any],
    progress_event: dict[str, Any],
) -> dict[str, Any]:
    return {
        "accepted": True,
        "code": code,
        "type": command["type"],
        "version": command["version"],
        "config_entry_id": command["config_entry_id"],
        "job_id": snapshot["job_id"],
        "snapshot": deepcopy(snapshot),
        "subscription": deepcopy(subscription),
        "progress_event": deepcopy(progress_event),
        "orchestration": job_orchestration_side_effects(
            subscription_bookkeeping_written=True,
            subscription_progress_streaming_called=True,
            job_orchestration_written=True,
        ),
    }


def _accepted_artifact_snapshot(
    code: str,
    command: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    artifact: dict[str, Any] | None,
    render_plan: dict[str, Any] | None,
    model_provider_plan: dict[str, Any] | None,
    worker_dispatch: dict[str, Any] | None,
    artifact_metadata_written: bool,
    render_plan_written: bool,
    model_provider_plan_written: bool,
    worker_dispatch_written: bool,
    model_provider_called: bool,
    worker_called: bool,
    chart_rendering_called: bool,
    job_state_written: bool,
    job_orchestration_written: bool,
    worker_progress_events: list[dict[str, Any]] | None = None,
    model_provider_retry_policy: dict[str, Any] | None = None,
    model_provider_retry_policy_written: bool = False,
    worker_progress_written: bool = False,
    worker_progress_streaming_called: bool = False,
    worker_retry_policy_written: bool = False,
    worker_transport_failure_classification_written: bool = False,
    in_process_render: dict[str, Any] | None = None,
    chart_artifact_written: bool = False,
) -> dict[str, Any]:
    result = {
        "accepted": True,
        "code": code,
        "type": command["type"],
        "version": command["version"],
        "config_entry_id": command["config_entry_id"],
        "job_id": snapshot["job_id"],
        "snapshot": deepcopy(snapshot),
        "orchestration": job_orchestration_side_effects(
            worker_called=worker_called,
            model_provider_called=model_provider_called,
            chart_rendering_called=chart_rendering_called,
            chart_artifact_written=chart_artifact_written,
            artifact_metadata_bookkeeping_written=artifact_metadata_written,
            render_plan_bookkeeping_written=render_plan_written,
            model_provider_plan_bookkeeping_written=model_provider_plan_written,
            model_provider_retry_policy_bookkeeping_written=model_provider_retry_policy_written,
            worker_dispatch_bookkeeping_written=worker_dispatch_written,
            worker_progress_bookkeeping_written=worker_progress_written,
            worker_progress_streaming_called=worker_progress_streaming_called,
            worker_retry_policy_bookkeeping_written=worker_retry_policy_written,
            worker_transport_failure_classification_bookkeeping_written=(
                worker_transport_failure_classification_written
            ),
            job_state_written=job_state_written,
            job_orchestration_written=job_orchestration_written,
        ),
    }
    if artifact is not None:
        result["artifact"] = deepcopy(artifact)
    if render_plan is not None:
        result["render_plan"] = deepcopy(render_plan)
    if model_provider_plan is not None:
        result["model_provider_plan"] = deepcopy(model_provider_plan)
    if model_provider_retry_policy is not None:
        result["model_provider_retry_policy"] = deepcopy(model_provider_retry_policy)
    if worker_dispatch is not None:
        result["worker_dispatch"] = deepcopy(worker_dispatch)
    if worker_progress_events:
        result["worker_progress_events"] = deepcopy(worker_progress_events)
    if in_process_render is not None:
        result["in_process_render"] = deepcopy(in_process_render)
    return result


def _orchestration_rejection(
    code: str,
    *,
    job_id: str | None = None,
    orchestration: dict[str, bool] | None = None,
    run: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "accepted": False,
        "code": code,
        "render_attempted": False,
        "orchestration": orchestration or job_orchestration_side_effects(),
    }
    if job_id is not None:
        result["job_id"] = job_id
    if run is not None:
        result["run"] = deepcopy(run)
    return result


def _approved_catalog_items(hass: Any, entry_id: str) -> list[dict[str, Any]]:
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    store = entry_data.get(DATA_ENTITY_CATALOG, {}) if isinstance(entry_data, dict) else {}
    items = store.get("items", []) if isinstance(store, dict) else []
    if not isinstance(items, list):
        return []
    return [
        item
        for item in items
        if isinstance(item, dict) and item.get("visible_to_agent") is True
    ]


def _catalog_selection_failure(
    hass: Any,
    entry_id: str,
    selection: dict[str, Any],
) -> dict[str, Any]:
    if selection.get("code") != "no_approved_entities_available":
        return {
            "code": selection.get("code", "approved_entity_catalog_failed"),
            "message": selection.get(
                "message",
                "The approved entity catalog rejected this request.",
            ),
            "missing_entity_ids": [],
        }

    setup = _entity_catalog_setup_result(hass, entry_id)
    if not isinstance(setup, dict) or setup.get("accepted") is not False:
        return {
            "code": selection["code"],
            "message": selection["message"],
            "missing_entity_ids": [],
        }

    missing_entity_ids = [
        str(entity_id)
        for entity_id in setup.get("missing_entity_ids", [])
        if isinstance(entity_id, str)
    ]
    if missing_entity_ids:
        return {
            "code": setup.get("code", "unknown_allowlisted_entity"),
            "message": (
                "The configured allowlist contains entity IDs Home Assistant "
                f"could not resolve: {', '.join(missing_entity_ids)}. "
                "Check the spelling or choose entities from the options picker."
            ),
            "missing_entity_ids": missing_entity_ids,
        }

    errors = setup.get("errors", [])
    if isinstance(errors, list) and errors:
        reason = errors[0].get("reason") if isinstance(errors[0], dict) else None
        return {
            "code": setup.get("code", "invalid_entity_allowlist"),
            "message": (
                "The configured allowlist is invalid"
                + (f" ({reason})." if reason else ".")
            ),
            "missing_entity_ids": [],
        }

    return {
        "code": setup.get("code", "approved_entity_catalog_unavailable"),
        "message": "The approved entity catalog setup failed for this config entry.",
        "missing_entity_ids": [],
    }


def _entity_catalog_setup_result(hass: Any, entry_id: str) -> dict[str, Any] | None:
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    if not isinstance(entry_data, dict):
        return None
    setup = entry_data.get(DATA_ENTITY_CATALOG_SETUP)
    return setup if isinstance(setup, dict) else None


def _job_for_result(hass: Any, entry_id: str, result: dict[str, Any]) -> dict[str, Any] | None:
    entry_data = hass.data.get(DOMAIN, {}).get(entry_id, {})
    store = entry_data.get(DATA_JOB_STATE, {}) if isinstance(entry_data, dict) else {}
    jobs = store.get("jobs", {}) if isinstance(store, dict) else {}
    job = jobs.get(result.get("job_id"))
    return job if isinstance(job, dict) else None


def _job_for_command(hass: Any, entry_id: str, command: dict[str, Any]) -> dict[str, Any] | None:
    entry_data = hass.data.get(DOMAIN, {}).get(entry_id, {})
    store = entry_data.get(DATA_JOB_STATE, {}) if isinstance(entry_data, dict) else {}
    jobs = store.get("jobs", {}) if isinstance(store, dict) else {}
    job = jobs.get(command.get("job_id"))
    return job if isinstance(job, dict) else None


def _artifact_for_job(store: dict[str, Any], job_id: str) -> dict[str, Any] | None:
    artifact_id = store.get("artifact_by_job_id", {}).get(job_id)
    artifact = store.get("artifact_metadata", {}).get(artifact_id)
    return deepcopy(artifact) if isinstance(artifact, dict) else None


def _artifact_snapshot_lock_for_job(store: dict[str, Any], job_id: str) -> threading.Lock:
    with ARTIFACT_SNAPSHOT_LOCKS_GUARD:
        locks = store.setdefault("_artifact_snapshot_locks", {})
        lock = locks.get(job_id)
        if not isinstance(lock, THREAD_LOCK_TYPE):
            lock = threading.Lock()
            locks[job_id] = lock
        return lock


def _render_plan_for_job(store: dict[str, Any], job_id: str) -> dict[str, Any] | None:
    render_plan_id = store.get("render_plan_by_job_id", {}).get(job_id)
    render_plan = store.get("render_plans", {}).get(render_plan_id)
    return deepcopy(render_plan) if isinstance(render_plan, dict) else None


def _model_provider_plan_for_job(store: dict[str, Any], job_id: str) -> dict[str, Any] | None:
    provider_plan_id = store.get("model_provider_plan_by_job_id", {}).get(job_id)
    provider_plan = store.get("model_provider_plans", {}).get(provider_plan_id)
    return deepcopy(provider_plan) if isinstance(provider_plan, dict) else None


def _worker_dispatch_for_job(store: dict[str, Any], job_id: str) -> dict[str, Any] | None:
    dispatch_id = store.get("worker_dispatch_by_job_id", {}).get(job_id)
    worker_dispatch = store.get("worker_dispatches", {}).get(dispatch_id)
    return deepcopy(worker_dispatch) if isinstance(worker_dispatch, dict) else None


def _worker_progress_events_for_job(store: dict[str, Any], job_id: str) -> list[dict[str, Any]]:
    event_ids = store.get("worker_progress_event_ids_by_job_id", {}).get(job_id, [])
    return [
        deepcopy(store.get("worker_progress_events", {})[event_id])
        for event_id in event_ids
        if event_id in store.get("worker_progress_events", {})
    ]


def _is_artifact_source_snapshot(snapshot: dict[str, Any]) -> bool:
    progress = snapshot.get("progress")
    return (
        snapshot.get("status") == "planning"
        and isinstance(progress, dict)
        and progress.get("stage") in ARTIFACT_SOURCE_PROGRESS_STAGES
    )


def _is_artifact_complete_snapshot(snapshot: dict[str, Any], artifact: dict[str, Any]) -> bool:
    chart = snapshot.get("chart")
    return (
        snapshot.get("status") == "complete"
        and isinstance(chart, dict)
        and chart.get("image_url") == artifact.get("image_url")
    )


def _chart_metadata_for_artifact(
    *,
    artifact_id: str,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
) -> dict[str, Any]:
    series = _artifact_series(source_snapshot)
    return {
        "title": _artifact_title(job, source_snapshot),
        "image_url": f"/api/isolinear/artifacts/{artifact_id}.png",
        "time_range": "approved scaffold history window",
        "series": series,
        "overlays": [],
    }


def _chart_spec_for_render_plan(
    *,
    render_plan_id: str,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
) -> dict[str, Any]:
    entities = _source_snapshot_entities(source_snapshot)
    chart_type = "timeline" if entities and all(
        entity["entity_id"].startswith("binary_sensor.")
        for entity in entities
    ) else "time_series"
    render_as = "step" if chart_type == "timeline" else "line"
    return {
        "chart_id": f"{render_plan_id}-chart-spec",
        "chart_type": chart_type,
        "title": _artifact_title(job, source_snapshot),
        "time_range": {
            "type": "relative",
            "duration": "approved scaffold history window",
        },
        "series": [
            {
                "series_id": f"series-{index:03d}",
                "label": entity["label"],
                "source": {
                    "type": "entity",
                    "entity_id": entity["entity_id"],
                    "attribute": None,
                },
                "role": "primary" if index == 1 else "comparison",
                "render_as": render_as,
                "transform": {
                    "operation": "none",
                    "window": None,
                },
                "unit": None,
            }
            for index, entity in enumerate(entities, start=1)
        ],
        "overlays": [],
        "x_axis": {
            "type": "time",
        },
        "y_axis": {},
        "notes": [
            "render_planning_scaffold",
            "model_provider_not_called",
            "worker_not_called",
            "chart_rendering_not_started",
        ],
    }


def _model_provider_planner_request(
    *,
    hass: Any,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    entity_ids: list[str] | None = None,
) -> dict[str, Any]:
    # ``entity_ids`` restricts what the planner may chart as series; for the
    # overlay composition only the numeric primary is disclosed (ADR-0022 D5).
    entity_ids = entity_ids if entity_ids is not None else _source_snapshot_entity_ids(source_snapshot)
    return {
        "prompt": job.get("prompt") if isinstance(job.get("prompt"), str) else "",
        "approved_entity_ids": entity_ids,
        "history_entity_ids": entity_ids,
        "now": _history_now(hass).isoformat(timespec="seconds"),
        "time_zone": _hass_time_zone(hass),
        "output_schema": "PlannerResult",
    }


def _hass_time_zone(hass: Any) -> str:
    config = getattr(hass, "config", None)
    time_zone = getattr(config, "time_zone", None)
    if isinstance(time_zone, str) and time_zone.strip():
        return time_zone
    return "UTC"


def _chart_spec_entity_ids(chart_spec: dict[str, Any]) -> dict[str, Any]:
    entity_ids: set[str] = set()
    unsupported_source_refs: list[dict[str, Any]] = []

    for collection_name in ("series", "overlays"):
        for index, item in enumerate(chart_spec.get(collection_name, [])):
            if not isinstance(item, dict):
                continue
            source = item.get("source")
            _collect_source_entity_ids(
                source,
                entity_ids,
                unsupported_source_refs,
                path=f"{collection_name}[{index}].source",
            )

    return {
        "entity_ids": entity_ids,
        "unsupported_source_refs": unsupported_source_refs,
    }


def _memory_proposal_entity_ids(planner_result: Any) -> set[str]:
    """Collect entity IDs from ``memory_proposals`` (a persisted, reusable path).

    Unlike free-text fields, a memory proposal persists a ``SemanticAlias`` that
    a later prompt can resolve, so an off-allowlist ``entity_id`` here is a real
    reference worth rejecting at creation time rather than relying solely on the
    use-time alias revalidation (invariant #7).
    """
    entity_ids: set[str] = set()
    if not isinstance(planner_result, dict):
        return entity_ids
    proposals = planner_result.get("memory_proposals")
    if not isinstance(proposals, list):
        return entity_ids
    for proposal in proposals:
        if isinstance(proposal, dict):
            entity_id = proposal.get("entity_id")
            if isinstance(entity_id, str) and entity_id:
                entity_ids.add(entity_id)
    return entity_ids


def _collect_source_entity_ids(
    source: Any,
    entity_ids: set[str],
    unsupported_source_refs: list[dict[str, Any]],
    *,
    path: str,
) -> None:
    if not isinstance(source, dict):
        unsupported_source_refs.append({"path": path, "reason": "missing_source"})
        return

    source_type = source.get("type")
    if source_type == "entity":
        entity_id = source.get("entity_id")
        if isinstance(entity_id, str):
            entity_ids.add(entity_id)
        return
    if source_type == "aggregate":
        for entity_id in source.get("entity_ids", []):
            if isinstance(entity_id, str):
                entity_ids.add(entity_id)
        return

    unsupported_source_refs.append(
        {
            "path": path,
            "reason": "unsupported_or_unresolved_source",
            "source_type": source_type,
        }
    )


def _artifact_series(source_snapshot: dict[str, Any]) -> list[dict[str, str]]:
    result = []
    for index, entity in enumerate(_source_snapshot_entities(source_snapshot), start=1):
        result.append(
            {
                "series_id": f"series-{index:03d}",
                "label": entity["label"],
                "entity_id": entity["entity_id"],
            }
        )
    return result


def _source_snapshot_entity_ids(source_snapshot: dict[str, Any]) -> list[str]:
    return [entity["entity_id"] for entity in _source_snapshot_entities(source_snapshot)]


def _source_snapshot_entities(source_snapshot: dict[str, Any]) -> list[dict[str, str]]:
    result = []
    for entity in source_snapshot.get("entities", []):
        if not isinstance(entity, dict):
            continue
        entity_id = entity.get("entity_id")
        label = entity.get("label") or entity_id
        if not isinstance(entity_id, str) or not isinstance(label, str):
            continue
        result.append(
            {
                "entity_id": entity_id,
                "label": label,
            }
        )
    return result


def _artifact_title(job: dict[str, Any], source_snapshot: dict[str, Any]) -> str:
    entities = source_snapshot.get("entities", [])
    if isinstance(entities, list) and len(entities) == 1 and isinstance(entities[0], dict):
        label = entities[0].get("label")
        if isinstance(label, str) and label.strip():
            return f"{label} Chart"
    prompt = job.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        return f"Isolinear Chart: {prompt.strip()}"
    return "Isolinear Chart"


def _append_artifact_complete_snapshot(
    job: dict[str, Any],
    artifact: dict[str, Any],
    *,
    worker_dispatch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    chart = {
        "title": artifact["title"],
        "image_url": artifact["image_url"],
        "time_range": artifact["time_range"],
        "series": deepcopy(artifact["series"]),
        "overlays": deepcopy(artifact["overlays"]),
    }
    worker_rendered = worker_dispatch is not None
    worker_artifact_rendered = artifact.get("render_metadata", {}).get("renderer") == WORKER_RENDERER_NAME
    in_process_rendered = artifact.get("render_metadata", {}).get("renderer") == IN_PROCESS_RENDERER_NAME
    return append_validated_job_snapshot(
        job,
        status="complete",
        state_label="Complete",
        message=(
            (
                "Worker-rendered chart artifact is ready for the dashboard card."
                if worker_artifact_rendered
                else (
                    "Worker render result is recorded and placeholder chart artifact metadata is ready for the "
                    "dashboard card."
                )
            )
            if worker_rendered
            else (
                "In-process trusted Pillow render is ready for the dashboard card."
                if in_process_rendered
                else "Placeholder chart artifact metadata is ready for the dashboard card."
            )
        ),
        progress_stage="job_orchestration_artifact_storage_ready",
        progress_message=(
            (
                "Worker dispatch metadata and served chart artifact metadata are stored."
                if worker_artifact_rendered
                else "Worker dispatch metadata is stored with the scaffold artifact metadata."
            )
            if worker_rendered
            else (
                "Rendered chart artifact metadata is stored for the first real slice."
                if in_process_rendered
                else "Scaffold artifact metadata is stored for future rendering."
            )
        ),
        validation_status="pass",
        validation_summary=(
            (
                "The worker dispatch recorded a schema-valid render result and served PNG artifact."
                if worker_artifact_rendered
                else (
                    "The worker dispatch scaffold recorded a schema-valid worker render result and placeholder chart "
                    "metadata."
                )
            )
            if worker_rendered
            else (
                "The first real vertical slice rendered a schema-valid PNG chart in process."
                if in_process_rendered
                else "The artifact storage scaffold created schema-valid placeholder chart metadata."
            )
        ),
        validation_checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "integration_artifact_metadata", "status": "pass"},
            {"name": "worker", "status": "pass" if worker_rendered else "not_called"},
            {
                "name": "chart_rendering",
                "status": "pass" if worker_rendered or in_process_rendered else "not_called",
            },
        ],
        chart=chart,
        entities=[
            {"entity_id": item["entity_id"], "label": item["label"]}
            for item in artifact["series"]
        ],
        warnings=(
            (
                [
                    "first_real_vertical_slice",
                    "worker_renderer",
                    "worker_rendered_artifact_serving",
                    "worker_render_result_recorded",
                    "chart_artifact_served_url",
                ]
                if worker_artifact_rendered
                else [
                    "artifact_storage_scaffold",
                    "placeholder_chart_artifact",
                    "worker_dispatch_rendering_scaffold",
                    "worker_render_result_recorded",
                    "integration_chart_artifact_file_not_written",
                ]
            )
            if worker_rendered
            else (
                [
                    "first_real_vertical_slice",
                    "in_process_pillow_renderer",
                    "chart_artifact_served_url",
                    "worker_not_called",
                ]
                if in_process_rendered
                else [
                    "artifact_storage_scaffold",
                    "placeholder_chart_artifact",
                    "worker_not_called",
                    "chart_rendering_not_started",
                ]
            )
        ),
    )


# The time window is resolved by the model (ADR-0020): the planner emits an
# absolute chart_spec.time_range, the integration validates and clamps it, and
# any failure falls back to a fixed last-24h window. The 366-day ceiling is only
# useful because windows older than recorder retention are served from long-term
# statistics (ADR-0021).
_MIN_HISTORY_WINDOW = timedelta(seconds=60)
_MAX_HISTORY_WINDOW = timedelta(days=366)
_DEFAULT_HISTORY_WINDOW = timedelta(hours=24)


def _default_history_time_range(hass: Any) -> dict[str, str]:
    """Return the deterministic last-24h fallback window (or a test override)."""
    configured = getattr(hass, "data", {}).get(DOMAIN, {}).get(DATA_JOB_ORCHESTRATION_TIME_RANGE)
    if isinstance(configured, dict) and isinstance(configured.get("start"), str) and isinstance(configured.get("end"), str):
        return {
            "start": configured["start"],
            "end": configured["end"],
        }

    end = _history_now(hass)
    start = end - _DEFAULT_HISTORY_WINDOW
    return {
        "start": start.isoformat(timespec="seconds"),
        "end": end.isoformat(timespec="seconds"),
    }


def _history_now(hass: Any) -> datetime:
    """Return 'now' (UTC, second precision), honoring a test override."""
    configured = getattr(hass, "data", {}).get(DOMAIN, {}).get(DATA_JOB_ORCHESTRATION_TIME_RANGE)
    if isinstance(configured, dict) and isinstance(configured.get("now"), str):
        parsed = _parse_window_timestamp(configured["now"])
        if parsed is not None:
            return parsed.replace(microsecond=0)
    return datetime.now(timezone.utc).replace(microsecond=0)


def resolve_history_window(chart_spec: Any, *, now: datetime) -> dict[str, Any]:
    """Validate and clamp a model-supplied absolute window, else fall back to 24h.

    Returns a dict with ``start``/``end`` ISO strings, the resolved ``source``
    intent flag ``model_resolved`` (vs. the 24h fallback), and a list of
    ``warnings`` describing any clamping that was applied. The fallback is the
    only deterministic default; there is no keyword parsing (ADR-0020).
    """
    now = now.astimezone(timezone.utc).replace(microsecond=0)
    fallback_start = now - _DEFAULT_HISTORY_WINDOW

    def _fallback(reason: str) -> dict[str, Any]:
        return {
            "model_resolved": False,
            "start": fallback_start.isoformat(timespec="seconds"),
            "end": now.isoformat(timespec="seconds"),
            "warnings": [reason],
        }

    time_range = chart_spec.get("time_range") if isinstance(chart_spec, dict) else None
    if not isinstance(time_range, dict) or time_range.get("type") != "absolute":
        return _fallback("history_window_missing_absolute_range")

    start = _parse_window_timestamp(time_range.get("start"))
    end = _parse_window_timestamp(time_range.get("end"))
    if start is None or end is None:
        return _fallback("history_window_unparseable")

    start = start.astimezone(timezone.utc).replace(microsecond=0)
    end = end.astimezone(timezone.utc).replace(microsecond=0)

    warnings: list[str] = []
    if end > now:
        end = now
        warnings.append("history_window_end_clamped_to_now")
    if start >= end:
        return _fallback("history_window_not_increasing")
    if end - start > _MAX_HISTORY_WINDOW:
        start = end - _MAX_HISTORY_WINDOW
        warnings.append("history_window_span_clamped_to_max")
    if end - start < _MIN_HISTORY_WINDOW:
        start = end - _MIN_HISTORY_WINDOW
        warnings.append("history_window_span_expanded_to_min")

    return {
        "model_resolved": True,
        "start": start.isoformat(timespec="seconds"),
        "end": end.isoformat(timespec="seconds"),
        "warnings": warnings,
    }


def _parse_window_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _catalog_item_meaningful_tokens(item: dict[str, Any]) -> set[str]:
    item_tokens = set(_prompt_tokens(" ".join(str(value or "") for value in [
        item.get("entity_id", "").replace(".", " "),
        item.get("friendly_name", ""),
        item.get("area", ""),
        item.get("device_name", ""),
    ])))
    return {
        token
        for token in item_tokens
        if len(token) >= 4 and token not in {"sensor", "binary", "temperature"}
    }


def _catalog_item_match_score(prompt: str, item: dict[str, Any]) -> int:
    """Count how many of an entity's distinctive tokens appear in the prompt.

    The count (not just a boolean) is what separates false ambiguity — one entity
    matched on its specific tokens while another shares only a generic word
    ("kitchen door" vs "kitchen ecobee") — from genuine ambiguity, where rivals
    tie on a shared term ("show thermostat history" with two thermostats).
    See ADR-0024 D1.
    """
    prompt_tokens = set(_prompt_tokens(prompt))
    return len(_catalog_item_meaningful_tokens(item) & prompt_tokens)


def _catalog_item_matches_prompt(prompt: str, item: dict[str, Any]) -> bool:
    return _catalog_item_match_score(prompt, item) >= 1


def _prompt_tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", value.lower())


def _unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _worker_failure_code(render_result: Any) -> str:
    if isinstance(render_result, dict):
        error = render_result.get("error")
        if isinstance(error, dict) and isinstance(error.get("code"), str) and error["code"].strip():
            return _safe_worker_failure_code(error["code"])
    return "worker_render_failed"


def _model_provider_failure_contains_forbidden_material(provider_response: dict[str, Any]) -> bool:
    return any(
        FORBIDDEN_MODEL_PROVIDER_FAILURE_TEXT.search(value)
        for value in (
            provider_response.get("code"),
            provider_response.get("message"),
        )
        if isinstance(value, str)
    )


def _safe_model_provider_failure_code(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "model_provider_planning_failed"
    stripped = value.strip()
    if FORBIDDEN_MODEL_PROVIDER_FAILURE_TEXT.search(stripped):
        return "model_provider_planning_failed"
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "_", stripped).strip("_")
    return normalized[:80] if normalized else "model_provider_planning_failed"


def _safe_model_provider_failure_message(value: Any) -> str:
    fallback = "Model provider planning failed before a chart spec was accepted."
    if not isinstance(value, str) or not value.strip():
        return fallback
    stripped = re.sub(r"\s+", " ", value.strip())
    if FORBIDDEN_MODEL_PROVIDER_FAILURE_TEXT.search(stripped):
        return fallback
    return stripped[:240] if stripped else fallback


def _safe_worker_failure_code(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "worker_render_failed"
    stripped = value.strip()
    if FORBIDDEN_WORKER_PROGRESS_TEXT.search(stripped):
        return "worker_render_failed"
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "_", stripped).strip("_")
    return normalized[:80] if normalized else "worker_render_failed"


def _safe_worker_transport_failure_code(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "worker_transport_failed"
    stripped = value.strip()
    if FORBIDDEN_WORKER_PROGRESS_TEXT.search(stripped):
        return "worker_transport_failed"
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "_", stripped).strip("_")
    return normalized[:80] if normalized else "worker_transport_failed"


def _safe_worker_transport_failure_message(value: Any) -> str:
    fallback = "Worker transport failed before a render result was accepted."
    if not isinstance(value, str) or not value.strip():
        return fallback
    stripped = re.sub(r"\s+", " ", value.strip())
    if FORBIDDEN_WORKER_PROGRESS_TEXT.search(stripped):
        return fallback
    return stripped[:240] if stripped else fallback


def _safe_worker_snapshot_failure_code(value: Any, *, stage: str) -> str:
    if stage == "worker_transport":
        return _safe_worker_transport_failure_code(value)
    return _safe_worker_failure_code(value)


def _safe_worker_snapshot_failure_message(value: Any, *, stage: str) -> str:
    fallback = (
        "Worker transport failed before a render result was accepted."
        if stage == "worker_transport"
        else "Worker render failed before a chart artifact was accepted."
    )
    if not isinstance(value, str) or not value.strip():
        return fallback
    stripped = re.sub(r"\s+", " ", value.strip())
    if FORBIDDEN_WORKER_PROGRESS_TEXT.search(stripped):
        return fallback
    return stripped[:240] if stripped else fallback


def _safe_renderer_failure_code(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "in_process_renderer_failed"
    stripped = value.strip()
    if FORBIDDEN_WORKER_PROGRESS_TEXT.search(stripped) or FORBIDDEN_MODEL_PROVIDER_FAILURE_TEXT.search(stripped):
        return "in_process_renderer_failed"
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "_", stripped).strip("_")
    return normalized[:80] if normalized else "in_process_renderer_failed"


def _safe_renderer_failure_message(value: Any) -> str:
    fallback = "The trusted chart renderer failed before a chart artifact was accepted."
    if not isinstance(value, str) or not value.strip():
        return fallback
    stripped = re.sub(r"\s+", " ", value.strip())
    if FORBIDDEN_WORKER_PROGRESS_TEXT.search(stripped) or FORBIDDEN_MODEL_PROVIDER_FAILURE_TEXT.search(stripped):
        return fallback
    return stripped[:240] if stripped else fallback


def _worker_transport_failure_family(code: str) -> str:
    if code == "worker_connection_error":
        return "connection"
    if code == "worker_http_error":
        return "http"
    if code == "worker_response_error":
        return "malformed_response"
    if code == "worker_renderer_unavailable":
        return "unavailable"
    return "unknown"


def _snapshot_entities(catalog_items: list[dict[str, Any]], entity_ids: list[str]) -> list[dict[str, str]]:
    by_entity = {item["entity_id"]: item for item in catalog_items}
    entities = []
    for entity_id in entity_ids:
        item = by_entity.get(entity_id, {})
        entities.append(
            {
                "entity_id": entity_id,
                "label": item.get("friendly_name") or entity_id,
            }
        )
    return entities


def _clarification_option_for_item(item: dict[str, Any]) -> dict[str, Any]:
    entity_id = item["entity_id"]
    label = item.get("friendly_name") or entity_id
    return {
        "option_id": _option_id_for_entity(entity_id),
        "label": label,
        "description": f"Use {entity_id}.",
        "can_remember": False,
    }


def _option_id_for_entity(entity_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", entity_id).strip("_")


def _pending_clarification_for_job(job: dict[str, Any]) -> dict[str, Any]:
    snapshot = job.get("latest_snapshot")
    if not isinstance(snapshot, dict) or snapshot.get("status") != "clarification_needed":
        return {
            "accepted": False,
            "code": "job_not_awaiting_clarification",
        }
    clarification = snapshot.get("clarification")
    if not isinstance(clarification, dict) or not isinstance(clarification.get("options"), list):
        return {
            "accepted": False,
            "code": "job_not_awaiting_clarification",
        }
    return {
        "accepted": True,
        "code": "accepted",
        "snapshot": snapshot,
        "clarification": clarification,
    }


def _retryable_failure_for_job(job: dict[str, Any]) -> dict[str, Any]:
    snapshot = job.get("latest_snapshot")
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("status") != "failed"
        or snapshot.get("retry_allowed") is not True
    ):
        return {
            "accepted": False,
            "code": "job_not_retryable",
        }
    return {
        "accepted": True,
        "code": "accepted",
        "snapshot": snapshot,
    }


def _selected_clarification_entity(
    hass: Any,
    entry_id: str,
    clarification: dict[str, Any],
    option_id: str,
) -> dict[str, Any]:
    returned_option_ids = {
        option.get("option_id")
        for option in clarification.get("options", [])
        if isinstance(option, dict)
    }
    if option_id not in returned_option_ids:
        return {
            "accepted": False,
            "code": "unknown_clarification_option",
            "approved_entity_catalog_read": False,
        }

    catalog_items = _approved_catalog_items(hass, entry_id)
    matches = [
        item
        for item in catalog_items
        if isinstance(item.get("entity_id"), str) and _option_id_for_entity(item["entity_id"]) == option_id
    ]
    if len(matches) == 1:
        return {
            "accepted": True,
            "code": "accepted",
            "entity_id": matches[0]["entity_id"],
            "catalog_items": catalog_items,
            "approved_entity_catalog_read": True,
        }
    if len(matches) > 1:
        return {
            "accepted": False,
            "code": "ambiguous_clarification_option",
            "approved_entity_catalog_read": True,
        }

    return {
        "accepted": False,
        "code": "clarification_option_not_in_approved_catalog",
        "approved_entity_catalog_read": True,
    }


def _reject_clarification_answer(
    store: dict[str, Any],
    *,
    command: dict[str, Any],
    job: dict[str, Any],
    code: str,
    approved_entity_catalog_read: bool = False,
) -> dict[str, Any]:
    run = _record_run(
        store,
        command=command,
        job=job,
        result_code=code,
        requested_entity_ids=[],
        history_entity_ids=[],
        snapshot_ids=_snapshot_ids(job),
        clarification_answer=_clarification_answer_summary(command, None),
    )
    return _orchestration_rejection(
        code,
        job_id=command.get("job_id"),
        run=run,
        orchestration=job_orchestration_side_effects(
            approved_entity_catalog_read=approved_entity_catalog_read,
            job_orchestration_written=True,
        ),
    )


def _clarification_answer_summary(
    command: dict[str, Any],
    entity_id: str | None,
) -> dict[str, Any]:
    return {
        "question_id": command["question_id"],
        "option_id": command["option_id"],
        "remember": command["remember"],
        "entity_id": entity_id,
    }


def _snapshot_ids(job: dict[str, Any]) -> list[str]:
    return [
        snapshot["snapshot_id"]
        for snapshot in job.get("snapshots", [])
        if isinstance(snapshot, dict)
    ]


def _failure_message(history_result: dict[str, Any]) -> str:
    code = history_result["code"]
    if code == "entity_not_in_approved_catalog":
        rejected = ", ".join(history_result.get("rejected_entity_ids", []))
        return f"Prompt referenced entities outside the approved catalog: {rejected}."
    if code == "missing_approved_history":
        missing = ", ".join(history_result.get("missing_entity_ids", []))
        return f"Approved history is missing for: {missing}."
    return "Approved history retrieval failed before future planning."
