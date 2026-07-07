"""Config-entry-scoped job orchestration scaffold for the Isolinear integration."""

from __future__ import annotations

import base64
import binascii
import json
import logging
import re
import threading
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from ._paths import load_schema_document, schema_path
from .artifact_serving import prepare_png_artifact, remove_png_artifact, write_png_artifact
from .const import (
    DOMAIN,
    INTEGRATION_COMMAND_TYPES,
    RENDER_MODE_CODEGEN,
    RENDER_PATH_PILLOW,
)
from .entity_catalog import DATA_ENTITY_CATALOG, DATA_ENTITY_CATALOG_SETUP
from .history_retrieval import (
    DATA_HISTORY_RETRIEVAL,
    backfill_catalog_units_from_state,
    classify_series_kind,
    retrieve_approved_history,
    validate_history_series_collection_contract,
)
from .in_process_renderer import (
    IN_PROCESS_RENDERER_NAME,
    _OVERLAY_COLORS,
    _binary_on_regions,
    _categorical_overlay_states,
    _parse_timestamp,
    _rgb_to_hex,
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
    PLANNER_RENDER_FAMILIES,
    configured_codegen_model,
    configured_render_path,
    get_model_provider_codegen,
    get_model_provider_planner,
    load_entity_selector_schema,
    load_planner_result_schema,
    planner_client_metadata,
)
from .semantic_memory import (
    _entity_id_to_alias_id,
    _iso_utc_now,
    _sanitize_prompt_for_storage,
    derive_alias_natural_names,
    resolve_alias_injection,
    save_semantic_alias,
    semantic_memory_store_for,
)
from .answer_grounding import run_grounding_check as _run_grounding_check
from .worker_renderer import (
    build_worker_transport_request,
    get_worker_render_client,
    redacted_worker_transport_request,
    worker_client_metadata,
    worker_client_token,
)

# ── ADR-0035 step-1 split: contracts seam (docs/specs/job-orchestration-split.md)
# Compat re-exports — tests/evals import these names from job_orchestration, and
# the facade's own remaining code calls them by bare name. Production importers
# (__init__, websocket_api) use none of these. Trim under ADR-0035 step 2+.
from .orchestration_contracts import (  # noqa: F401
    ARTIFACT_METADATA_SCHEMA_PATH,
    CHART_SPEC_SCHEMA_PATH,
    MODEL_PROVIDER_PLAN_SCHEMA_PATH,
    MODEL_PROVIDER_RETRY_POLICY_SCHEMA_PATH,
    PLANNER_RESULT_SCHEMA_PATH,
    RENDER_PLAN_SCHEMA_PATH,
    RENDER_REQUEST_SCHEMA_PATH,
    RENDER_RESULT_SCHEMA_PATH,
    WORKER_DISPATCH_SCHEMA_PATH,
    WORKER_PROGRESS_SCHEMA_PATH,
    WORKER_RETRY_POLICY_SCHEMA_PATH,
    WORKER_TRANSPORT_FAILURE_CLASSIFICATION_SCHEMA_PATH,
    WORKER_TRANSPORT_REQUEST_SCHEMA_PATH,
    _chart_spec_entity_ids,
    _check_chart_spec_no_duplicate_series_sources,
    _collect_source_entity_ids,
    _memory_proposal_entity_ids,
    _source_snapshot_entities,
    _source_snapshot_entity_ids,
    validate_artifact_metadata_contract,
    validate_chart_spec_contract,
    validate_model_provider_chart_spec_entities,
    validate_model_provider_output_entities,
    validate_model_provider_plan_contract,
    validate_model_provider_retry_policy_contract,
    validate_planner_result_contract,
    validate_render_plan_contract,
    validate_render_request_contract,
    validate_render_result_contract,
    validate_worker_dispatch_contract,
    validate_worker_progress_contract,
    validate_worker_retry_policy_contract,
    validate_worker_transport_failure_classification_contract,
    validate_worker_transport_request_contract,
)
# ── ADR-0035 step-1 split: store seam
from .orchestration_store import (  # noqa: F401
    PLAN_CHART_PHASE_LABEL,
    SELECT_ENTITY_PHASE_LABEL,
    _call_planner_with_optional_reasoning,
    ARTIFACT_SNAPSHOT_LOCKS_GUARD,
    DATA_JOB_ORCHESTRATION,
    DATA_JOB_ORCHESTRATION_SETUP,
    DATA_JOB_ORCHESTRATION_TIME_RANGE,
    DATA_LIVE_REASONING,
    NO_JOB_ORCHESTRATION_CALLS,
    THREAD_LOCK_TYPE,
    _artifact_for_job,
    _artifact_snapshot_lock_for_job,
    _clear_live_reasoning,
    _job_for_command,
    _job_for_result,
    _latest_record_id,
    _latest_stored_record,
    _live_reasoning_callback,
    _live_reasoning_slot,
    _live_reasoning_store,
    _model_provider_plan_for_job,
    _model_provider_retry_policy_attempt_number,
    _remove_ordered_id,
    _remove_stored_artifact_metadata,
    _remove_stored_model_provider_plan,
    _remove_stored_render_plan,
    _remove_stored_worker_dispatch,
    _remove_stored_worker_progress_events,
    _render_plan_for_job,
    _rollback_artifact_planning_records,
    _set_live_reasoning,
    _store_validated_artifact_metadata,
    _store_validated_model_provider_plan,
    _store_validated_model_provider_retry_policy,
    _store_validated_render_plan,
    _store_validated_worker_dispatch,
    _store_validated_worker_progress_event,
    _store_validated_worker_retry_policy,
    _store_validated_worker_transport_failure_classification,
    _subscription_ids_for_job,
    _worker_dispatch_for_job,
    _worker_progress_events_for_job,
    _worker_retry_policy_attempt_number,
    _worker_transport_failure_classification_attempt_number,
    apply_live_reasoning,
    job_orchestration_side_effects,
    summarize_job_orchestration_store,
)
# ── ADR-0035 step-1 split: snapshot-assembly seam
from .snapshot_assembly import (  # noqa: F401
    _artifact_series,
    _artifact_title,
    CODEGEN_CONTEXT_OVERFLOW_CODE,
    CODEGEN_RENDER_FAILED_CODE,
    FORBIDDEN_MODEL_PROVIDER_FAILURE_TEXT,
    FORBIDDEN_WORKER_PROGRESS_TEXT,
    WORKER_RENDERER_NAME,
    _append_artifact_complete_snapshot,
    _append_clarification_answer_accepted_snapshot,
    _append_clarification_snapshot,
    _append_codegen_failure_snapshot_from_planning_result,
    _append_failed_snapshot,
    _append_fetching_history_snapshot,
    _append_history_failure_snapshot_from_planning_result,
    _append_in_process_renderer_failure_snapshot,
    _append_in_process_renderer_failure_snapshot_from_planning_result,
    _append_model_provider_failure_snapshot,
    _append_model_provider_failure_snapshot_from_planning_result,
    _append_retry_accepted_snapshot,
    _append_worker_failure_snapshot,
    _append_worker_failure_snapshot_from_planning_result,
    _clarification_answer_summary,
    _clarification_option_for_item,
    _codegen_failure_message,
    _failure_message,
    _history_failure_message,
    _in_process_renderer_failure_message,
    _is_in_process_renderer_failure_code,
    _is_model_provider_output_failure_code,
    _model_provider_failure_contains_forbidden_material,
    _model_provider_planning_failure_message,
    _option_id_for_entity,
    _pending_clarification_for_job,
    _retryable_failure_for_job,
    _safe_model_provider_failure_code,
    _safe_model_provider_failure_message,
    _safe_renderer_failure_code,
    _safe_renderer_failure_message,
    _safe_worker_failure_code,
    _safe_worker_snapshot_failure_code,
    _safe_worker_snapshot_failure_message,
    _safe_worker_transport_failure_code,
    _safe_worker_transport_failure_message,
    _snapshot_entities,
    _snapshot_ids,
    _worker_failure_code,
    _worker_transport_failure_family,
)
# ── ADR-0035 step-1 split: history-dispatch seam
from .history_dispatch import (  # noqa: F401
    _DEFAULT_HISTORY_WINDOW,
    _MAX_HISTORY_WINDOW,
    _MIN_HISTORY_WINDOW,
    _default_history_time_range,
    _hass_time_zone,
    _history_now,
    _history_series_for_render_plan,
    _history_series_with_epoch_ms,
    _history_window_end_dt,
    _parse_window_timestamp,
    _retrieve_history_for_plan,
    _timestamp_to_epoch_ms,
    resolve_history_window,
)
# ── ADR-0035 step-1 split: entity-resolution seam
from .entity_resolution import (  # noqa: F401
    ENTITY_ID_IN_PROMPT,
    _CLIMATE_OVERLAY_COLOR_MAP,
    _D2_EXPANSION_SOURCES,
    _DOMAIN_SYNONYMS,
    _ENTITY_ID_SHAPED,
    _NUMERIC_TYPE_HINTS,
    _OVERLAY_ACTIVE_VALUES,
    _alias_display_entries,
    _approved_catalog_items,
    _catalog_item_match_score,
    _catalog_item_matches_prompt,
    _catalog_item_meaningful_tokens,
    _compose_binary_overlays,
    _compose_state_overlays,
    _composition_has_shared_token,
    _entity_matches_via_domain_synonym,
    _filter_numerics_by_type_hint,
    _inject_semantic_aliases,
    _maybe_save_semantic_alias,
    _prompt_tokens,
    _prune_composition_with_model,
    _resolve_entity_selection_with_model,
    _resolve_overlay_label,
    _resolve_render_envelope,
    _resolve_render_family,
    _run_model_entity_selection,
    _selected_clarification_entity,
    _unique,
    select_prompt_entity_ids,
)
# ── ADR-0035 step-1 split: planning-pipeline seam
from .planning_pipeline import (  # noqa: F401
    _PLANNER_REPLAN_TEMPERATURE,
    _PLANNER_REPLAN_TRIGGER_CODES,
    _apply_catalog_units,
    _build_model_provider_plan,
    _build_model_provider_retry_policy,
    _configured_max_planner_replan_attempts,
    _model_provider_planner_request,
    _plan_once,
    _record_model_provider_plan,
    _record_model_provider_retry_policy,
    validate_model_provider_chart_family,
)
# ── ADR-0035 step-1 split: render-dispatch seam
from .render_dispatch import (  # noqa: F401
    MAX_WORKER_PROGRESS_EVENTS,
    _OVERLAY_BAND_AUTO_PALETTE,
    _accept_in_process_render_result,
    _build_artifact_metadata,
    _build_codegen_render_request,
    _build_in_process_artifact_metadata,
    _build_worker_artifact_metadata,
    _build_worker_dispatch,
    _build_worker_progress_event,
    _build_worker_progress_snapshot,
    _build_worker_render_request,
    _build_worker_retry_policy,
    _build_worker_transport_failure_classification,
    _chart_metadata_for_artifact,
    _codegen_fallback_reason,
    _codegen_render_failed,
    _compact_codegen_error_detail,
    _compute_overlay_bands,
    _configured_max_codegen_repair_attempts,
    _configured_render_path,
    _finish_codegen_success,
    _normalize_worker_progress_payloads,
    _overlay_band,
    _record_codegen_worker_dispatch,
    _record_in_process_render,
    _record_worker_dispatch,
    _record_worker_progress_events,
    _record_worker_rendered_artifact,
    _record_worker_retry_policy,
    _record_worker_transport_failure_classification,
    _rollback_worker_rendered_artifact,
    _worker_png_bytes_from_render_result,
    _worker_progress_text_contains_forbidden_material,
)








_LOGGER = logging.getLogger(__name__)

# ADR-0026: job/start and job/retry append this pending stage and return planning
# immediately; the first snapshot poll resolves model entity selection under the
# planning lock (so selection reasoning streams, realizing ADR-0025 D7). It is an
# artifact-source stage so the poll picks it up, but it carries no resolved
# entities — the locked handler routes it through _resolve_pending_entity_selection
# before any planning/render.
ENTITY_SELECTION_PENDING_STAGE = "job_orchestration_entity_selection_pending"

ARTIFACT_SOURCE_PROGRESS_STAGES = {
    "job_orchestration_scaffold_ready",
    "job_orchestration_clarification_continuation_ready",
    "job_orchestration_retry_continuation_ready",
    ENTITY_SELECTION_PENDING_STAGE,
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


def _defer_selection_to_planning(
    *,
    store: dict[str, Any],
    command: dict[str, Any],
    job: dict[str, Any],
    kind: str,
    result_code: str,
    accepted_code: str,
    warnings_prefix: list[str],
    extra_checks: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Defer model entity selection to the pollable planning phase (ADR-0026 D1).

    job/start and job/retry call this instead of resolving entities inline. It
    appends a schema-valid ``planning`` snapshot whose stage marks selection as
    pending (no entities yet, no model call) and records ``kind`` on the job so
    the first snapshot poll runs the deterministic+model selection under the
    planning lock — where its reasoning streams to the card (ADR-0025 D7).
    """
    job["entity_selection_pending"] = {"kind": kind}
    checks = [
        {"name": "integration_job_state_scaffold", "status": "pass"},
        *(extra_checks or []),
        {"name": "approved_entity_catalog", "status": "pending_planning"},
        {"name": "approved_history_retrieval", "status": "deferred_to_planning"},
        {"name": "model_provider", "status": "not_called"},
        {"name": "worker", "status": "not_called"},
        {"name": "chart_rendering", "status": "not_called"},
    ]
    snapshot = append_validated_job_snapshot(
        job,
        status="planning",
        state_label="Resolving entities",
        message=(
            "Isolinear is selecting the approved entities for this question; the "
            "model resolves the time window and renders during planning."
        ),
        progress_stage=ENTITY_SELECTION_PENDING_STAGE,
        progress_message="Selecting entities…",
        validation_status="pass",
        validation_summary="The orchestration accepted the prompt and deferred entity selection to the planning phase.",
        validation_checks=checks,
        warnings=[*warnings_prefix, "entity_selection_deferred_to_planning"],
    )
    run = _record_run(
        store,
        command=command,
        job=job,
        result_code=result_code,
        requested_entity_ids=[],
        history_entity_ids=[],
        snapshot_ids=_snapshot_ids(job),
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

    # ADR-0026: for the first-real-slice path, defer model entity selection to the
    # pollable planning phase so job/start returns `planning` immediately and the
    # selection reasoning streams to the card (ADR-0025 D7). An empty approved
    # catalog is a pre-model structural rejection and stays synchronous here.
    if first_real_vertical_slice_enabled(hass, entry_id):
        if not catalog_items:
            return _synchronous_empty_catalog_failure(
                hass, entry_id, store=store, command=command, job=job
            )
        return _defer_selection_to_planning(
            store=store,
            command=command,
            job=job,
            kind="start",
            result_code="entity_selection_deferred_to_planning",
            accepted_code="job_orchestration_entity_selection_pending",
            warnings_prefix=["first_real_vertical_slice"],
        )

    selection = select_prompt_entity_ids(command["prompt"], catalog_items)
    selection = _inject_semantic_aliases(hass, entry_id, command["prompt"], catalog_items, selection)
    selection = _resolve_entity_selection_with_model(
        hass, entry_id, command["prompt"], catalog_items, selection,
        store=store, job_id=job["job_id"],
    )
    if not selection["accepted"]:
        missing_entity_ids = []
        run_result_code = selection["code"]
        if selection["code"] == "entity_selection_requires_clarification":
            snapshot = _append_clarification_snapshot(
                job,
                message=selection["message"],
                options=selection["options"],
                candidate_items=selection.get("candidate_items", []),
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
    # Tranche 2: stash matched-alias display entries so the complete snapshot can
    # show which user-confirmed aliases resolved the prompt. Fail-open display.
    job["alias_display"] = _alias_display_entries(
        hass, entry_id, selection.get("matched_alias_ids", [])
    )
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
    if command["remember"] is True:
        _maybe_save_semantic_alias(
            hass, entry_id, job,
            option_id=command["option_id"],
            selected_entity_id=selected_entity_id,
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

    # ADR-0026 D5: retry defers model entity selection to the planning poll the
    # same way job/start does, so retry returns `planning` immediately and the
    # re-resolution streams reasoning. Empty catalog stays a synchronous rejection.
    if first_real_vertical_slice_enabled(hass, entry_id):
        if not catalog_items:
            return _synchronous_empty_catalog_failure(
                hass, entry_id, store=store, command=command, job=job, kind="retry"
            )
        return _defer_selection_to_planning(
            store=store,
            command=command,
            job=job,
            kind="retry",
            result_code="retry_entity_selection_deferred_to_planning",
            accepted_code="job_orchestration_entity_selection_pending",
            warnings_prefix=[
                "job_orchestration_retry_continuation_scaffold",
                "first_real_vertical_slice",
            ],
            extra_checks=[{"name": "retry_command", "status": "pass"}],
        )

    selection = select_prompt_entity_ids(job["prompt"], catalog_items)
    selection = _resolve_entity_selection_with_model(
        hass, entry_id, job["prompt"], catalog_items, selection,
        store=store, job_id=job["job_id"],
    )
    if not selection["accepted"]:
        missing_entity_ids = []
        run_result_code = selection["code"]
        if selection["code"] == "entity_selection_requires_clarification":
            snapshot = _append_clarification_snapshot(
                job,
                message=selection["message"],
                options=selection["options"],
                candidate_items=selection.get("candidate_items", []),
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

        # ADR-0026: a pending-selection placeholder means model entity selection
        # was deferred from job/start/job/retry to this pollable phase. Resolve it
        # under the lock — its reasoning streams to concurrent polls (ADR-0025 D7).
        # On clarification/failure the resolved terminal snapshot is returned; on
        # success we continue into planning/render with the entities-bearing
        # source snapshot, all under this single lock acquisition.
        source_snapshot = latest_snapshot
        if latest_snapshot["progress"]["stage"] == ENTITY_SELECTION_PENDING_STAGE:
            resolution = _resolve_pending_entity_selection(
                hass,
                command,
                entry_id=entry_id,
                store=store,
                job=job,
            )
            if not resolution["proceed"]:
                return resolution["result"]
            source_snapshot = resolution["source_snapshot"]

        return _record_artifact_snapshot_for_source(
            hass,
            command,
            entry_id=entry_id,
            store=store,
            job=job,
            source_snapshot=source_snapshot,
        )
    finally:
        # ADR-0025 D4: the model phase for this poll has concluded (the terminal
        # complete/failed snapshot is now stored). The live reasoning is
        # ephemeral wait-feedback and is never written to the stored snapshot, so
        # discard the slot — the next poll surfaces the chart or failure card.
        _clear_live_reasoning(store, job["job_id"])
        planning_lock.release()


def _resolve_pending_entity_selection(
    hass: Any,
    command: dict[str, Any],
    *,
    entry_id: str,
    store: dict[str, Any],
    job: dict[str, Any],
) -> dict[str, Any]:
    """Run deferred model entity selection inside the planning lock (ADR-0026 D2/D3/D4).

    Called by the snapshot poll when the source snapshot is the
    ``ENTITY_SELECTION_PENDING_STAGE`` placeholder. Runs the same D1 → semantic
    alias → D2 pipeline that job/start/job/retry ran inline before ADR-0026 — the
    resolution logic is unchanged; only its call site moved. Returns either
    ``{"proceed": False, "result": <ws result>}`` for a clarification/failure
    outcome (terminal snapshot already appended), or
    ``{"proceed": True, "source_snapshot": <planning snapshot>}`` on success so
    the caller flows into planning/render under the same lock.

    Idempotent: the model is invoked at most once per job because the first poll
    holds the planning lock for the whole resolution and pops the pending marker
    inside the lock before any terminal snapshot; concurrent polls are served the
    in-progress reasoning snapshot by the lock-contended path.
    """
    pending = job.get("entity_selection_pending") or {}
    kind = pending.get("kind", "start")
    catalog_items = _approved_catalog_items(hass, entry_id)

    selection = select_prompt_entity_ids(job["prompt"], catalog_items)
    if kind == "start":
        selection = _inject_semantic_aliases(
            hass, entry_id, job["prompt"], catalog_items, selection
        )
    selection = _resolve_entity_selection_with_model(
        hass, entry_id, job["prompt"], catalog_items, selection,
        store=store, job_id=job["job_id"],
    )

    if not selection["accepted"]:
        job.pop("entity_selection_pending", None)
        if selection["code"] == "entity_selection_requires_clarification":
            snapshot = _append_clarification_snapshot(
                job,
                message=selection["message"],
                options=selection["options"],
                candidate_items=selection.get("candidate_items", []),
            )
            run_result_code = (
                "job_orchestration_retry_continuation_clarification_needed"
                if kind == "retry"
                else "job_orchestration_scaffold_clarification_needed"
            )
            ws_code = "job_orchestration_entity_selection_clarification_needed"
            missing_entity_ids: list[str] = []
        else:
            failure = _catalog_selection_failure(hass, entry_id, selection)
            missing_entity_ids = failure.get("missing_entity_ids", [])
            checks = [
                {"name": "integration_job_state_scaffold", "status": "pass"},
                *([{"name": "retry_command", "status": "pass"}] if kind == "retry" else []),
                {"name": "approved_entity_catalog", "status": "fail"},
                {"name": "approved_history_retrieval", "status": "not_run"},
                {"name": "model_provider", "status": "not_called"},
                {"name": "worker", "status": "not_called"},
            ]
            snapshot = _append_failed_snapshot(
                job,
                code=failure["code"],
                stage="approved_entity_catalog",
                message=failure["message"],
                checks=checks,
            )
            run_result_code = failure["code"]
            ws_code = "job_orchestration_entity_selection_failed"
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
        return {
            "proceed": False,
            "result": _accepted_artifact_snapshot(
                ws_code,
                command,
                snapshot,
                artifact=None,
                render_plan=None,
                model_provider_plan=None,
                worker_dispatch=None,
                artifact_metadata_written=False,
                render_plan_written=False,
                model_provider_plan_written=False,
                worker_dispatch_written=False,
                model_provider_called=False,
                worker_called=False,
                chart_rendering_called=False,
                job_state_written=True,
                job_orchestration_written=True,
            ),
        }

    requested_entity_ids = selection["entity_ids"]
    # Tranche 2: stash matched-alias display for the complete snapshot. Fail-open.
    job["alias_display"] = _alias_display_entries(
        hass, entry_id, selection.get("matched_alias_ids", [])
    )
    job.pop("entity_selection_pending", None)

    if kind == "retry":
        progress_stage = "job_orchestration_retry_continuation_ready"
        result_code = "retry_entities_ready_for_planning"
        accepted_code = "job_orchestration_retry_continuation_ready"
        warnings_prefix = [
            "job_orchestration_retry_continuation_scaffold",
            "first_real_vertical_slice",
        ]
        extra_checks = [{"name": "retry_command", "status": "pass"}]
    else:
        progress_stage = "job_orchestration_scaffold_ready"
        result_code = "approved_entities_ready_for_planning"
        accepted_code = "job_orchestration_scaffold_ready"
        warnings_prefix = ["first_real_vertical_slice"]
        extra_checks = None

    # Reuse the established resolved-planning snapshot builder so the post-selection
    # source snapshot is byte-identical to the pre-ADR-0026 job/start output; we
    # discard its _accepted wrapper and continue to planning under the same lock.
    _defer_history_to_planning(
        store=store,
        command=command,
        job=job,
        catalog_items=catalog_items,
        requested_entity_ids=requested_entity_ids,
        progress_stage=progress_stage,
        result_code=result_code,
        accepted_code=accepted_code,
        warnings_prefix=warnings_prefix,
        extra_checks=extra_checks,
    )
    return {"proceed": True, "source_snapshot": job["latest_snapshot"]}


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
        codegen_failure_snapshot = _append_codegen_failure_snapshot_from_planning_result(
            job,
            planning_result,
        )
        if codegen_failure_snapshot is not None:
            return _accepted_artifact_snapshot(
                "job_orchestration_codegen_failure_snapshot_recorded",
                command,
                codegen_failure_snapshot,
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
                worker_called=planning_result.get("worker_called", False),
                chart_rendering_called=planning_result.get("chart_rendering_called", False),
                chart_artifact_written=False,
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

        return _accept_in_process_render_result(
            store,
            in_process_render_result=in_process_render_result,
            model_provider_result=model_provider_result,
            render_plan=render_plan,
            render_plan_validation=render_plan_validation,
        )

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
        # ADR-0030: codegen failures (generation, repair exhaustion, transport)
        # fall back to the trusted Pillow renderer, surfaced via render_path +
        # render_fallback_reason on the artifact/chart — never silent.
        # Log at WARNING (visible via the HA system-log channel) with the failure
        # stage/code/attempts + compact detail so codegen fallbacks are
        # diagnosable without reproducing; the worker log carries the full detail.
        _LOGGER.warning(
            "Isolinear codegen render failed, falling back to Pillow: %s",
            worker_dispatch_result.get("codegen_failure")
            or {"code": worker_dispatch_result.get("code")},
        )
        fallback_reason = _codegen_fallback_reason(hass, entry_id, worker_dispatch_result)
        if fallback_reason is not None:
            fallback_render_result = _record_in_process_render(
                store,
                hass=hass,
                entry_id=entry_id,
                artifact=artifact,
                render_plan=render_plan,
                model_provider_result=model_provider_result,
                fallback_reason=fallback_reason,
            )
            if fallback_render_result.get("enabled") and fallback_render_result.get("accepted"):
                return _accept_in_process_render_result(
                    store,
                    in_process_render_result=fallback_render_result,
                    model_provider_result=model_provider_result,
                    render_plan=render_plan,
                    render_plan_validation=render_plan_validation,
                )
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
            "codegen_failure": worker_dispatch_result.get("codegen_failure"),
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


def _synchronous_empty_catalog_failure(
    hass: Any,
    entry_id: str,
    *,
    store: dict[str, Any],
    command: dict[str, Any],
    job: dict[str, Any],
    kind: str = "start",
) -> dict[str, Any]:
    """Fail job/start or job/retry synchronously when the catalog is empty (ADR-0026).

    An empty/unresolvable catalog is a pre-model structural rejection, so it is
    surfaced immediately rather than deferred to the planning poll. Mirrors the
    `no_approved_entities_available` branch of the legacy synchronous path; makes
    no model call.
    """
    selection = select_prompt_entity_ids(job["prompt"], [])
    failure = _catalog_selection_failure(hass, entry_id, selection)
    snapshot = _append_failed_snapshot(
        job,
        code=failure["code"],
        stage="approved_entity_catalog",
        message=failure["message"],
        checks=[
            {"name": "integration_job_state_scaffold", "status": "pass"},
            *([{"name": "retry_command", "status": "pass"}] if kind == "retry" else []),
            {"name": "approved_entity_catalog", "status": "fail"},
            {"name": "approved_history_retrieval", "status": "not_run"},
            {"name": "model_provider", "status": "not_called"},
            {"name": "worker", "status": "not_called"},
        ],
    )
    run = _record_run(
        store,
        command=command,
        job=job,
        result_code=failure["code"],
        requested_entity_ids=[],
        history_entity_ids=[],
        snapshot_ids=_snapshot_ids(job),
        missing_entity_ids=failure.get("missing_entity_ids", []),
    )
    accepted_code = (
        "job_orchestration_retry_continuation_failed"
        if kind == "retry"
        else "job_orchestration_scaffold_failed"
    )
    return _accepted(
        accepted_code,
        command,
        snapshot,
        run=run,
        approved_entity_catalog_read=True,
        job_state_written=True,
        job_orchestration_written=True,
        **({"retry_behavior_called": True} if kind == "retry" else {}),
    )


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


