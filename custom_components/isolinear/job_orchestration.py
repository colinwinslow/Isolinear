"""Config-entry-scoped job orchestration scaffold for the Isolinear integration."""

from __future__ import annotations

import re
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .const import DOMAIN, INTEGRATION_COMMAND_TYPES
from .entity_catalog import DATA_ENTITY_CATALOG
from .history_retrieval import retrieve_approved_history
from .job_state import (
    DATA_JOB_STATE,
    JobStateSnapshotValidationError,
    _validate_json_schema,
    append_validated_job_snapshot,
    handle_job_state_ws_command,
    validate_job_snapshot_contract,
)


DATA_JOB_ORCHESTRATION = "job_orchestration"
DATA_JOB_ORCHESTRATION_SETUP = "job_orchestration_setup"
DATA_JOB_ORCHESTRATION_TIME_RANGE = "job_orchestration_default_time_range"
ARTIFACT_METADATA_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "schemas" / "integration-artifact-metadata.schema.json"
)
RENDER_PLAN_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "schemas" / "integration-render-plan.schema.json"
)
CHART_SPEC_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "docs" / "schemas" / "chart-spec.schema.json"

ENTITY_ID_IN_PROMPT = re.compile(r"\b[a-z0-9_]+\.[a-z0-9_]+\b")
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
    "job_orchestration_called": False,
}


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
    }
    entry_data[DATA_JOB_ORCHESTRATION] = store
    return store


def has_enabled_job_orchestration(hass: Any, entry_id: str) -> bool:
    """Return whether a config entry has enough approved catalog data to orchestrate start."""
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    setup = entry_data.get(DATA_JOB_ORCHESTRATION_SETUP) if isinstance(entry_data, dict) else None
    return isinstance(setup, dict) and setup.get("enabled") is True


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
    if not selection["accepted"]:
        if selection["code"] == "entity_selection_requires_clarification":
            snapshot = _append_clarification_snapshot(
                job,
                message=selection["message"],
                options=selection["options"],
            )
            result_code = "job_orchestration_scaffold_clarification_needed"
        else:
            snapshot = _append_failed_snapshot(
                job,
                code=selection["code"],
                stage="approved_entity_catalog",
                message=selection["message"],
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
            result_code=selection["code"],
            requested_entity_ids=[],
            history_entity_ids=[],
            snapshot_ids=_snapshot_ids(job),
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
    time_range = _default_history_time_range(hass)
    rejected_entity_ids = [
        entity_id
        for entity_id in requested_entity_ids
        if entity_id not in {item["entity_id"] for item in catalog_items}
    ]

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
    if not selection["accepted"]:
        if selection["code"] == "entity_selection_requires_clarification":
            snapshot = _append_clarification_snapshot(
                job,
                message=selection["message"],
                options=selection["options"],
            )
            result_code = "job_orchestration_retry_continuation_clarification_needed"
        else:
            snapshot = _append_failed_snapshot(
                job,
                code=selection["code"],
                stage="approved_entity_catalog",
                message=selection["message"],
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
            result_code=selection["code"],
            requested_entity_ids=[],
            history_entity_ids=[],
            snapshot_ids=_snapshot_ids(job),
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
    time_range = _default_history_time_range(hass)
    rejected_entity_ids = [
        entity_id
        for entity_id in requested_entity_ids
        if entity_id not in {item["entity_id"] for item in catalog_items}
    ]

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
    if existing_artifact is not None and _is_artifact_complete_snapshot(latest_snapshot, existing_artifact):
        return _accepted_artifact_snapshot(
            "job_orchestration_artifact_snapshot_returned",
            command,
            latest_snapshot,
            artifact=existing_artifact,
            render_plan=existing_render_plan,
            artifact_metadata_written=False,
            render_plan_written=False,
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
            artifact_metadata_written=False,
            render_plan_written=False,
            job_state_written=False,
            job_orchestration_written=False,
        )

    planning_result = _record_artifact_and_render_plan(
        store,
        job=job,
        source_snapshot=latest_snapshot,
    )
    if not planning_result["accepted"]:
        result = _orchestration_rejection(
            planning_result["code"],
            job_id=command.get("job_id"),
            orchestration=job_orchestration_side_effects(),
        )
        result["validation"] = planning_result.get("validation")
        return result

    artifact = planning_result["artifact"]
    render_plan = planning_result["render_plan"]
    complete_snapshot = _append_artifact_complete_snapshot(job, artifact)
    return _accepted_artifact_snapshot(
        "job_orchestration_artifact_storage_recorded",
        command,
        complete_snapshot,
        artifact=artifact,
        render_plan=render_plan,
        artifact_metadata_written=True,
        render_plan_written=True,
        job_state_written=True,
        job_orchestration_written=True,
    )


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
        return {
            "accepted": False,
            "code": "entity_selection_requires_clarification",
            "message": "Multiple approved entities match this question; choose one.",
            "options": [_clarification_option_for_item(item) for item in matches],
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
    }


def summarize_job_orchestration_store(store: dict[str, Any]) -> dict[str, Any]:
    """Return an evidence-friendly orchestration store summary."""
    latest_run = store.get("latest_run")
    latest_progress_event = store.get("latest_progress_event")
    latest_artifact = store.get("latest_artifact")
    latest_render_plan = store.get("latest_render_plan")
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
    }


def job_orchestration_side_effects(
    *,
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
    websocket_command_registered: bool = False,
) -> dict[str, bool]:
    """Return side-effect accounting for the job orchestration scaffold."""
    return {
        **NO_JOB_ORCHESTRATION_CALLS,
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


def _record_artifact_and_render_plan(
    store: dict[str, Any],
    *,
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

    render_plan = _build_render_plan(
        store,
        job=job,
        source_snapshot=source_snapshot,
        artifact=artifact,
    )
    render_plan_validation = validate_render_plan_contract(render_plan)
    if not render_plan_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_integration_render_plan",
            "validation": render_plan_validation,
        }

    _store_validated_artifact_metadata(store, artifact)
    _store_validated_render_plan(store, render_plan)
    return {
        "accepted": True,
        "code": "accepted",
        "artifact": deepcopy(artifact),
        "render_plan": deepcopy(render_plan),
        "artifact_validation": artifact_validation,
        "render_plan_validation": render_plan_validation,
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
) -> dict[str, Any]:
    render_plan_number = store["next_render_plan_number"]
    render_plan_id = f"{store['entry_id']}-render-plan-{render_plan_number:03d}"
    chart_spec = _chart_spec_for_render_plan(
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
        "chart_spec": chart_spec,
        "history_entity_ids": _source_snapshot_entity_ids(source_snapshot),
        "output": {
            "format": "png",
            "width": 1400,
            "height": 800,
        },
        "validation": {
            "status": "pass",
            "summary": "Placeholder render plan and chart spec validate before storage.",
            "checks": [
                {"name": "integration_job_snapshot", "status": "pass"},
                {"name": "integration_artifact_metadata", "status": "pass"},
                {"name": "chart_spec_schema", "status": "pass"},
                {"name": "model_provider", "status": "not_called"},
                {"name": "worker", "status": "not_called"},
                {"name": "chart_rendering", "status": "not_called"},
            ],
        },
        "warnings": [
            "render_planning_scaffold",
            "placeholder_chart_spec",
            "model_provider_not_called",
            "worker_not_called",
            "chart_rendering_not_started",
        ],
    }


def _store_validated_render_plan(store: dict[str, Any], render_plan: dict[str, Any]) -> None:
    render_plan_id = render_plan["render_plan_id"]
    store["next_render_plan_number"] += 1
    store["render_plans"][render_plan_id] = deepcopy(render_plan)
    store["render_plan_order"].append(render_plan_id)
    store["render_plan_by_job_id"][render_plan["job_id"]] = render_plan_id
    store["latest_render_plan"] = deepcopy(render_plan)


def validate_artifact_metadata_contract(artifact: Any) -> dict[str, Any]:
    """Validate IntegrationArtifactMetadata against the repo JSON Schema."""
    try:
        schema = json.loads(ARTIFACT_METADATA_SCHEMA_PATH.read_text(encoding="utf-8"))
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
        schema = json.loads(RENDER_PLAN_SCHEMA_PATH.read_text(encoding="utf-8"))
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


def validate_chart_spec_contract(chart_spec: Any) -> dict[str, Any]:
    """Validate a placeholder ChartSpec against the repo JSON Schema."""
    try:
        schema = json.loads(CHART_SPEC_SCHEMA_PATH.read_text(encoding="utf-8"))
        _validate_json_schema(chart_spec, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_chart_spec",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(CHART_SPEC_SCHEMA_PATH),
    }


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
    artifact_metadata_written: bool,
    render_plan_written: bool,
    job_state_written: bool,
    job_orchestration_written: bool,
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
            artifact_metadata_bookkeeping_written=artifact_metadata_written,
            render_plan_bookkeeping_written=render_plan_written,
            job_state_written=job_state_written,
            job_orchestration_written=job_orchestration_written,
        ),
    }
    if artifact is not None:
        result["artifact"] = deepcopy(artifact)
    if render_plan is not None:
        result["render_plan"] = deepcopy(render_plan)
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


def _render_plan_for_job(store: dict[str, Any], job_id: str) -> dict[str, Any] | None:
    render_plan_id = store.get("render_plan_by_job_id", {}).get(job_id)
    render_plan = store.get("render_plans", {}).get(render_plan_id)
    return deepcopy(render_plan) if isinstance(render_plan, dict) else None


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
        and "artifact_storage_scaffold" in snapshot.get("warnings", [])
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


def _append_artifact_complete_snapshot(job: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
    chart = {
        "title": artifact["title"],
        "image_url": artifact["image_url"],
        "time_range": artifact["time_range"],
        "series": deepcopy(artifact["series"]),
        "overlays": deepcopy(artifact["overlays"]),
    }
    return append_validated_job_snapshot(
        job,
        status="complete",
        state_label="Complete",
        message="Placeholder chart artifact metadata is ready for the dashboard card.",
        progress_stage="job_orchestration_artifact_storage_ready",
        progress_message="Scaffold artifact metadata is stored for future rendering.",
        validation_status="pass",
        validation_summary="The artifact storage scaffold created schema-valid placeholder chart metadata.",
        validation_checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            {"name": "integration_artifact_metadata", "status": "pass"},
            {"name": "worker", "status": "not_called"},
            {"name": "chart_rendering", "status": "not_called"},
        ],
        chart=chart,
        entities=[
            {"entity_id": item["entity_id"], "label": item["label"]}
            for item in artifact["series"]
        ],
        warnings=[
            "artifact_storage_scaffold",
            "placeholder_chart_artifact",
            "worker_not_called",
            "chart_rendering_not_started",
        ],
    )


def _default_history_time_range(hass: Any) -> dict[str, str]:
    configured = getattr(hass, "data", {}).get(DOMAIN, {}).get(DATA_JOB_ORCHESTRATION_TIME_RANGE)
    if isinstance(configured, dict) and isinstance(configured.get("start"), str) and isinstance(configured.get("end"), str):
        return {
            "start": configured["start"],
            "end": configured["end"],
        }

    end = datetime.now(timezone.utc).replace(microsecond=0)
    start = end - timedelta(hours=24)
    return {
        "start": start.isoformat(timespec="seconds"),
        "end": end.isoformat(timespec="seconds"),
    }


def _catalog_item_matches_prompt(prompt: str, item: dict[str, Any]) -> bool:
    prompt_tokens = set(_prompt_tokens(prompt))
    item_tokens = set(_prompt_tokens(" ".join(str(value or "") for value in [
        item.get("entity_id", "").replace(".", " "),
        item.get("friendly_name", ""),
        item.get("area", ""),
        item.get("device_name", ""),
    ])))
    meaningful_tokens = {
        token
        for token in item_tokens
        if len(token) >= 4 and token not in {"sensor", "binary", "temperature"}
    }
    return bool(meaningful_tokens & prompt_tokens)


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
