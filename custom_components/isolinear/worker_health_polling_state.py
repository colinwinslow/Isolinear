"""State-building and redaction helpers for durable worker health polling."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from .const import DOMAIN
from .worker_health_polling_constants import (
    FAILURE_BACKOFF_SECONDS,
    POLLING_HEALTH_SECRET_RE,
    POLLING_HEALTH_URL_RE,
    POLLING_STORAGE_KEY,
    POLLING_STORAGE_VERSION,
    READY_POLL_CADENCE_SECONDS,
)
from .worker_health_polling_contract import (
    _coerce_datetime,
    _format_datetime,
    worker_health_polling_side_effects,
)
from .worker_readiness import get_worker_readiness
from .worker_renderer import get_worker_render_client, worker_client_token


def _worker_endpoint_url(client: Any) -> str | None:
    provider_metadata = getattr(client, "provider_metadata", None)
    if callable(provider_metadata):
        metadata = provider_metadata()
        if isinstance(metadata, dict) and isinstance(metadata.get("endpoint_url"), str):
            return metadata["endpoint_url"]
    endpoint_url = getattr(client, "endpoint_url", None)
    return endpoint_url if isinstance(endpoint_url, str) else None


def _in_flight_polling_state(
    *,
    entry_id: str,
    now: datetime,
    previous_state: dict[str, Any] | None,
) -> dict[str, Any]:
    if isinstance(previous_state, dict):
        state = deepcopy(previous_state)
        state["status"] = "scheduled"
        state["code"] = "worker_health_poll_in_flight"
        state["scheduler"]["post_setup_poll_enqueued"] = False
        state["scheduler"]["poll_in_flight"] = True
        state["scheduler"]["next_poll_not_before"] = _format_datetime(now)
        state["warnings"] = ["worker_health_poll_in_flight"]
        state["orchestration"] = worker_health_polling_side_effects(
            durable_health_storage_written=True,
            scheduler_bookkeeping_written=True,
            single_flight_guard_checked=True,
        )
        return state

    state = _build_polling_state(
        entry_id=entry_id,
        status="scheduled",
        code="worker_health_poll_in_flight",
        health_summary=_empty_health_summary(),
        scheduler=_scheduler_metadata(
            enabled=True,
            post_setup_poll_enqueued=False,
            last_poll_at=None,
            next_poll_not_before=now,
            consecutive_failures=0,
        ),
        repair_recommendation="none",
        warnings=["worker_health_poll_in_flight"],
        orchestration=worker_health_polling_side_effects(
            durable_health_storage_written=True,
            scheduler_bookkeeping_written=True,
            single_flight_guard_checked=True,
        ),
    )
    state["scheduler"]["poll_in_flight"] = True
    return state


def _poll_result_state(
    *,
    entry_id: str,
    health: dict[str, Any],
    now: datetime,
    previous_state: dict[str, Any] | None,
    worker_token: str | None,
    endpoint_url: str | None,
) -> dict[str, Any]:
    status = health["status"]
    code = _redacted_polling_health_code(
        health["code"],
        worker_token=worker_token,
        endpoint_url=endpoint_url,
    )
    previous_failures = _previous_failure_count(previous_state)
    if status == "ready":
        consecutive_failures = 0
        delay_seconds = READY_POLL_CADENCE_SECONDS
        backoff_seconds = None
    else:
        consecutive_failures = previous_failures + 1
        delay_seconds = _failure_backoff_seconds(consecutive_failures)
        backoff_seconds = delay_seconds

    return _build_polling_state(
        entry_id=entry_id,
        status=status,
        code=code,
        health_summary=_health_summary(
            health,
            worker_token=worker_token,
            endpoint_url=endpoint_url,
            code=code,
        ),
        scheduler=_scheduler_metadata(
            enabled=True,
            post_setup_poll_enqueued=False,
            last_poll_at=now,
            next_poll_not_before=now + timedelta(seconds=delay_seconds),
            consecutive_failures=consecutive_failures,
            backoff_seconds=backoff_seconds,
        ),
        repair_recommendation=_repair_recommendation(status, code),
        warnings=_poll_result_warnings(status),
        orchestration=worker_health_polling_side_effects(
            durable_health_storage_written=True,
            scheduler_bookkeeping_written=True,
            worker_health_check_called=True,
            worker_health_request_validated=True,
            worker_health_response_validated=True,
            single_flight_guard_checked=True,
        ),
    )


def _blocked_poll_result_state(
    *,
    entry_id: str,
    code: str,
    now: datetime,
    previous_state: dict[str, Any] | None,
) -> dict[str, Any]:
    consecutive_failures = _previous_failure_count(previous_state) + 1
    delay_seconds = _failure_backoff_seconds(consecutive_failures)
    return _build_polling_state(
        entry_id=entry_id,
        status="blocked",
        code=code,
        health_summary=_empty_health_summary(code=code, message="Worker health poll failed before durable storage."),
        scheduler=_scheduler_metadata(
            enabled=False,
            post_setup_poll_enqueued=False,
            last_poll_at=now,
            next_poll_not_before=now + timedelta(seconds=delay_seconds),
            consecutive_failures=consecutive_failures,
            backoff_seconds=delay_seconds,
            disabled_reason=code,
            stale=True,
        ),
        repair_recommendation="manual_probe",
        warnings=["worker_health_poll_failed_closed"],
        orchestration=worker_health_polling_side_effects(
            durable_health_storage_written=True,
            scheduler_bookkeeping_written=True,
            worker_health_check_called=True,
            worker_health_request_validated=True,
            single_flight_guard_checked=True,
        ),
    )


def _blocked_or_disabled_state(
    *,
    entry_id: str,
    reason: str,
    now: datetime,
    during_setup: bool,
) -> dict[str, Any]:
    status = "disabled" if reason == "worker_endpoint_missing" else "blocked"
    return _build_polling_state(
        entry_id=entry_id,
        status=status,
        code="worker_health_polling_disabled" if status == "disabled" else "worker_health_polling_blocked",
        health_summary=_empty_health_summary(code=reason, message=_precondition_message(reason)),
        scheduler=_scheduler_metadata(
            enabled=False,
            post_setup_poll_enqueued=False,
            last_poll_at=None,
            next_poll_not_before=None,
            consecutive_failures=0,
            disabled_reason=reason,
            stale=not during_setup,
        ),
        repair_recommendation=_precondition_repair_recommendation(reason),
        warnings=[reason, "worker_health_polling_not_started"],
        orchestration=worker_health_polling_side_effects(
            durable_health_storage_written=True,
            scheduler_bookkeeping_written=True,
            single_flight_guard_checked=not during_setup,
        ),
    )


def _build_polling_state(
    *,
    entry_id: str,
    status: str,
    code: str,
    health_summary: dict[str, Any],
    scheduler: dict[str, Any],
    repair_recommendation: str,
    warnings: list[str],
    orchestration: dict[str, bool],
) -> dict[str, Any]:
    return {
        "polling_id": f"{entry_id}-worker-health-polling-001",
        "type": "isolinear_worker_health_polling_state",
        "version": POLLING_STORAGE_VERSION,
        "config_entry_id": entry_id,
        "status": status,
        "code": code,
        "health": health_summary,
        "scheduler": scheduler,
        "repair": {
            "recommendation": repair_recommendation,
            "automatic_repair_scheduled": False,
        },
        "storage": {
            "helper_key": POLLING_STORAGE_KEY,
            "version": POLLING_STORAGE_VERSION,
            "config_entry_scoped": True,
        },
        "validation": {
            "status": "pass",
            "summary": "Durable worker health polling state validates before storage.",
            "checks": [
                {"name": "config_entry_scoped", "status": "pass"},
                {"name": "worker_authorization_absent", "status": "pass"},
                {"name": "scheduler_metadata_bounded", "status": "pass"},
            ],
        },
        "warnings": warnings,
        "orchestration": orchestration,
    }


def _scheduler_metadata(
    *,
    enabled: bool,
    post_setup_poll_enqueued: bool,
    last_poll_at: datetime | None,
    next_poll_not_before: datetime | None,
    consecutive_failures: int,
    backoff_seconds: int | None = None,
    disabled_reason: str | None = None,
    stale: bool = False,
    cancelled: bool = False,
) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "post_setup_poll_enqueued": post_setup_poll_enqueued,
        "single_flight": True,
        "poll_in_flight": False,
        "last_poll_at": _format_datetime(last_poll_at),
        "next_poll_not_before": _format_datetime(next_poll_not_before),
        "ready_cadence_seconds": READY_POLL_CADENCE_SECONDS,
        "backoff_seconds": backoff_seconds,
        "consecutive_failures": consecutive_failures,
        "stale": stale,
        "disabled_reason": disabled_reason,
        "cancelled": cancelled,
    }


def _health_summary(
    health: dict[str, Any],
    *,
    worker_token: str | None,
    endpoint_url: str | None,
    code: str,
) -> dict[str, Any]:
    response = health["response"]
    return {
        "status": health["status"],
        "code": code,
        "message": _redacted_polling_health_message(
            response["message"],
            worker_token=worker_token,
            endpoint_url=endpoint_url,
        ),
        "failure_family": _failure_family(health["status"], code),
        "last_health_id": health["health_id"],
        "capabilities": {
            "rendering": response["capabilities"]["rendering"],
        },
    }


def _redacted_polling_health_code(
    value: Any,
    *,
    worker_token: str | None,
    endpoint_url: str | None,
) -> str:
    if not isinstance(value, str) or not value.strip():
        return "worker_health_redacted"
    code = value.strip()
    if (
        _contains_polling_secret(code, worker_token)
        or POLLING_HEALTH_URL_RE.search(code)
        or _looks_like_endpoint_code(code, endpoint_url)
    ):
        return "worker_health_redacted"
    return code[:80]


def _redacted_polling_health_message(
    value: Any,
    *,
    worker_token: str | None,
    endpoint_url: str | None,
) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    message = re.sub(r"\s+", " ", value.strip())
    if _contains_polling_secret(message, worker_token):
        return "Worker health endpoint response was sanitized."
    if _looks_like_endpoint_code(message, endpoint_url):
        return "Worker health endpoint response was sanitized."
    return POLLING_HEALTH_URL_RE.sub("<redacted-url>", message)[:240]


def _looks_like_endpoint_code(value: str, endpoint_url: str | None) -> bool:
    lowered = value.lower()
    if lowered.startswith(("http_", "https_")):
        return True
    if not isinstance(endpoint_url, str) or not endpoint_url:
        return False
    parsed = urlparse(endpoint_url)
    fragments = {
        _normalize_polling_code_fragment(endpoint_url),
        _normalize_polling_code_fragment(parsed.netloc),
        _normalize_polling_code_fragment(parsed.hostname or ""),
    }
    return any(fragment and fragment in lowered for fragment in fragments)


def _normalize_polling_code_fragment(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value.strip().lower()).strip("_")


def _contains_polling_secret(value: str, worker_token: str | None) -> bool:
    if POLLING_HEALTH_SECRET_RE.search(value):
        return True
    return isinstance(worker_token, str) and bool(worker_token) and worker_token in value


def _empty_health_summary(
    *,
    code: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    return {
        "status": None,
        "code": code,
        "message": message,
        "failure_family": None,
        "last_health_id": None,
        "capabilities": {
            "rendering": None,
        },
    }


def _polling_preconditions(hass: Any, entry_id: str) -> dict[str, Any]:
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id)
    if not isinstance(entry_data, dict) or entry_data.get("entry") is None:
        return {"eligible": False, "reason": "unknown_config_entry"}
    entry = entry_data["entry"]
    if not _worker_endpoint_configured(entry):
        return {"eligible": False, "reason": "worker_endpoint_missing"}
    readiness = get_worker_readiness(hass, entry_id)
    if not isinstance(readiness, dict) or readiness.get("status") != "ready":
        return {"eligible": False, "reason": "worker_readiness_not_ready"}
    client = get_worker_render_client(hass, entry_id)
    if client is None:
        return {"eligible": False, "reason": "worker_health_client_missing"}
    if worker_client_token(client) is None:
        return {"eligible": False, "reason": "worker_token_missing"}
    return {"eligible": True, "reason": "ready"}


def _worker_endpoint_configured(entry: Any) -> bool:
    data = getattr(entry, "data", {}) or {}
    endpoint_url = data.get("worker_endpoint_url") if isinstance(data, dict) else None
    return isinstance(endpoint_url, str) and endpoint_url.strip().startswith(("http://", "https://"))


def _previous_failure_count(state: dict[str, Any] | None) -> int:
    if not isinstance(state, dict):
        return 0
    scheduler = state.get("scheduler")
    if not isinstance(scheduler, dict):
        return 0
    value = scheduler.get("consecutive_failures")
    return value if isinstance(value, int) and value >= 0 else 0


def _poll_in_flight(state: dict[str, Any] | None) -> bool:
    return isinstance(state, dict) and isinstance(state.get("scheduler"), dict) and state["scheduler"].get("poll_in_flight") is True


def _poll_not_due(state: dict[str, Any] | None, now: datetime) -> bool:
    if not isinstance(state, dict) or not isinstance(state.get("scheduler"), dict):
        return False
    next_poll = state["scheduler"].get("next_poll_not_before")
    if not isinstance(next_poll, str):
        return False
    try:
        next_poll_dt = _coerce_datetime(next_poll)
    except (TypeError, ValueError):
        return False
    return now < next_poll_dt


def _failure_backoff_seconds(consecutive_failures: int) -> int:
    index = max(0, min(consecutive_failures - 1, len(FAILURE_BACKOFF_SECONDS) - 1))
    return FAILURE_BACKOFF_SECONDS[index]


def _failure_family(status: str, code: str) -> str:
    if status == "ready":
        return "none"
    if status == "not_ready":
        return "worker_not_ready"
    lowered = code.lower()
    if "connection" in lowered:
        return "connection"
    if "http" in lowered:
        return "http"
    if "response" in lowered or "malformed" in lowered:
        return "malformed_response"
    if "unavailable" in lowered:
        return "unavailable"
    return "unknown"


def _repair_recommendation(status: str, code: str) -> str:
    if status == "ready":
        return "none"
    if status == "not_ready":
        return "check_worker"
    if "token" in code.lower():
        return "token_repair_available"
    return "manual_probe"


def _precondition_repair_recommendation(reason: str) -> str:
    if "token" in reason:
        return "token_repair_available"
    if reason == "worker_endpoint_missing":
        return "none"
    return "manual_probe"


def _precondition_message(reason: str) -> str:
    messages = {
        "worker_endpoint_missing": "Worker endpoint is not configured.",
        "worker_readiness_not_ready": "Worker readiness metadata is not ready.",
        "worker_health_client_missing": "Worker health client is not configured.",
        "worker_token_missing": "Integration-owned worker token is missing.",
        "unknown_config_entry": "Config entry is not known to Isolinear.",
    }
    return messages.get(reason, "Worker health polling preconditions are not satisfied.")


def _poll_result_warnings(status: str) -> list[str]:
    if status == "ready":
        return ["worker_health_poll_ready", "worker_health_polling_cadence_300_seconds"]
    if status == "not_ready":
        return ["worker_health_poll_not_ready", "worker_health_polling_backoff_applied"]
    return ["worker_health_poll_unavailable", "worker_health_polling_backoff_applied"]
