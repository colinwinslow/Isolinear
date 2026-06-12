"""Contract validation helpers for durable worker health polling."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .job_state import JobStateSnapshotValidationError, _validate_json_schema
from .worker_health_polling_constants import (
    FAILURE_BACKOFF_SECONDS,
    POLLING_HEALTH_URL_RE,
    POLLING_LOADED_FORBIDDEN_RE,
    READY_POLL_CADENCE_SECONDS,
    WORKER_HEALTH_POLLING_SCHEMA_PATH,
)


def validate_worker_health_polling_contract(state: Any) -> dict[str, Any]:
    """Validate IntegrationWorkerHealthPollingState against the repo schema."""
    try:
        schema = json.loads(WORKER_HEALTH_POLLING_SCHEMA_PATH.read_text(encoding="utf-8"))
        _validate_json_schema(state, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_worker_health_polling_state",
            "error": str(exc),
        }
    bounds_error = _polling_state_bounds_error(state)
    if bounds_error is not None:
        return {
            "accepted": False,
            "code": "invalid_integration_worker_health_polling_state",
            "error": bounds_error,
        }
    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(WORKER_HEALTH_POLLING_SCHEMA_PATH),
    }


def worker_health_polling_side_effects(
    *,
    durable_health_storage_written: bool = False,
    scheduler_bookkeeping_written: bool = False,
    post_setup_poll_enqueued: bool = False,
    worker_health_check_called: bool = False,
    worker_health_request_validated: bool = False,
    worker_health_response_validated: bool = False,
    single_flight_guard_checked: bool = False,
) -> dict[str, bool]:
    """Return side-effect accounting for durable worker health polling."""
    return {
        "durable_health_storage_written": durable_health_storage_written,
        "scheduler_bookkeeping_written": scheduler_bookkeeping_written,
        "post_setup_poll_enqueued": post_setup_poll_enqueued,
        "worker_health_check_called": worker_health_check_called,
        "worker_health_request_validated": worker_health_request_validated,
        "worker_health_response_validated": worker_health_response_validated,
        "single_flight_guard_checked": single_flight_guard_checked,
        "home_assistant_history_read": False,
        "semantic_memory_called": False,
        "home_assistant_service_or_state_mutation_called": False,
        "token_generated": False,
        "token_rotation_called": False,
        "token_repair_called": False,
        "worker_render_called": False,
        "model_provider_called": False,
        "chart_rendering_called": False,
        "chart_artifact_written": False,
        "durable_retry_storage_written": False,
        "recorder_called": False,
        "config_entry_options_written": False,
        "external_queue_called": False,
        "automatic_retry_called": False,
        "automatic_progress_task_called": False,
        "automatic_repair_called": False,
        "worker_endpoint_leaked_to_card": False,
        "token_leaked_to_card": False,
        "polling_metadata_leaked_to_card": False,
    }

def _loaded_polling_entry_is_valid(entry_id: Any, state: Any) -> bool:
    if not isinstance(entry_id, str) or not isinstance(state, dict):
        return False
    if state.get("config_entry_id") != entry_id:
        return False
    scheduler = state.get("scheduler")
    if isinstance(scheduler, dict) and scheduler.get("poll_in_flight") is True:
        return False
    if _polling_state_has_forbidden_text(state):
        return False
    return validate_worker_health_polling_contract(state)["accepted"] is True


def _resumable_polling_state(
    entry_id: str,
    state: dict[str, Any] | None,
    *,
    now: datetime,
) -> bool:
    if not _loaded_polling_entry_is_valid(entry_id, state):
        return False
    scheduler = state["scheduler"]
    if _resumable_polling_cadence_error(state, now=now) is not None:
        return False
    return (
        scheduler.get("enabled") is True
        and scheduler.get("poll_in_flight") is not True
        and isinstance(scheduler.get("next_poll_not_before"), str)
    )


def _polling_state_has_forbidden_text(state: dict[str, Any]) -> bool:
    state_text = str(state)
    return (
        POLLING_LOADED_FORBIDDEN_RE.search(state_text) is not None
        or POLLING_HEALTH_URL_RE.search(state_text) is not None
    )


def _polling_state_bounds_error(state: Any) -> str | None:
    if not isinstance(state, dict) or not isinstance(state.get("scheduler"), dict):
        return "scheduler must be an object"
    scheduler = state["scheduler"]
    backoff_seconds = scheduler.get("backoff_seconds")
    if backoff_seconds is not None and (
        type(backoff_seconds) is not int
        or backoff_seconds < 0
        or backoff_seconds > FAILURE_BACKOFF_SECONDS[-1]
    ):
        return "scheduler.backoff_seconds must be null or an integer from 0 through 900"
    consecutive_failures = scheduler.get("consecutive_failures")
    if type(consecutive_failures) is not int or consecutive_failures < 0:
        return "scheduler.consecutive_failures must be a non-negative integer"
    cadence_error = _polling_state_cadence_error(state)
    if cadence_error is not None:
        return cadence_error
    return None


def _polling_state_cadence_error(state: dict[str, Any]) -> str | None:
    scheduler = state["scheduler"]
    if scheduler.get("enabled") is not True:
        return None

    next_poll = _parse_scheduler_datetime(scheduler.get("next_poll_not_before"))
    if next_poll is None:
        return "enabled scheduler metadata must include next_poll_not_before"
    last_poll = _parse_scheduler_datetime(scheduler.get("last_poll_at"))
    if scheduler.get("last_poll_at") is not None and last_poll is None:
        return "scheduler.last_poll_at must be a valid date-time"

    status = state.get("status")
    if status == "ready":
        expected_delay = READY_POLL_CADENCE_SECONDS
    elif status in {"not_ready", "unavailable"}:
        expected_delay = scheduler.get("backoff_seconds")
        if expected_delay not in FAILURE_BACKOFF_SECONDS:
            return "failure scheduler backoff_seconds must use a bounded backoff window"
    else:
        expected_delay = None

    if last_poll is not None:
        delay_seconds = int((next_poll - last_poll).total_seconds())
        if delay_seconds < 0:
            return "scheduler.next_poll_not_before must not precede last_poll_at"
        if expected_delay is not None and delay_seconds != expected_delay:
            return "scheduler.next_poll_not_before must match the bounded polling cadence"
    return None


def _resumable_polling_cadence_error(state: dict[str, Any], *, now: datetime) -> str | None:
    cadence_error = _polling_state_cadence_error(state)
    if cadence_error is not None:
        return cadence_error
    scheduler = state["scheduler"]
    next_poll = _parse_scheduler_datetime(scheduler.get("next_poll_not_before"))
    if next_poll is None:
        return "enabled scheduler metadata must include next_poll_not_before"
    max_delay = _maximum_resumable_delay_seconds(state)
    if max_delay is None:
        max_delay = READY_POLL_CADENCE_SECONDS
    if (next_poll - now).total_seconds() > max_delay:
        return "scheduler.next_poll_not_before is outside the bounded resume window"
    return None


def _maximum_resumable_delay_seconds(state: dict[str, Any]) -> int | None:
    scheduler = state["scheduler"]
    if state.get("status") == "ready":
        return READY_POLL_CADENCE_SECONDS
    if state.get("status") in {"not_ready", "unavailable"}:
        backoff_seconds = scheduler.get("backoff_seconds")
        return backoff_seconds if backoff_seconds in FAILURE_BACKOFF_SECONDS else None
    return None


def _parse_scheduler_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return _coerce_datetime(value)
    except (TypeError, ValueError):
        return None

def _coerce_datetime(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    raise TypeError("now must be a datetime, ISO datetime string, or None")


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")
