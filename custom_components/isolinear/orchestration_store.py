"""Orchestration store plumbing for job orchestration (ADR-0035 step 1).

The record bookkeeping under the orchestration spine: validated-record
writers/removers/rollback with their ordered-id + latest-pointer discipline,
per-job record lookups, the per-job artifact-snapshot lock (guarded by the
module lock), the ADR-0025 live-reasoning slots, the side-effect accounting
envelope, and the evidence-friendly store summary. Layer L0 of the split:
depends only on const/job_state. See docs/specs/job-orchestration-split.md.
"""
from __future__ import annotations

import threading
from copy import deepcopy
from typing import Any

from .const import DOMAIN
from .job_state import DATA_JOB_STATE, validate_job_snapshot_contract

DATA_JOB_ORCHESTRATION = "job_orchestration"


DATA_JOB_ORCHESTRATION_SETUP = "job_orchestration_setup"


DATA_JOB_ORCHESTRATION_TIME_RANGE = "job_orchestration_default_time_range"


THREAD_LOCK_TYPE = type(threading.Lock())


ARTIFACT_SNAPSHOT_LOCKS_GUARD = threading.Lock()


# ADR-0025 D2/D3: per-job slot holding the latest sanitized, length-capped
# reasoning tail (+ active phase) so concurrent in-progress polls can surface it.
DATA_LIVE_REASONING = "live_reasoning"


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


def _store_validated_artifact_metadata(store: dict[str, Any], artifact: dict[str, Any]) -> None:
    artifact_id = artifact["artifact_id"]
    store["next_artifact_number"] += 1
    store["artifact_metadata"][artifact_id] = deepcopy(artifact)
    store["artifact_order"].append(artifact_id)
    store["artifact_by_job_id"][artifact["job_id"]] = artifact_id
    store["latest_artifact"] = deepcopy(artifact)


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
