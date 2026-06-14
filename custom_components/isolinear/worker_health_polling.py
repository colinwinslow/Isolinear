"""Durable worker health polling boundary for Isolinear."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from functools import partial
from typing import Any

from .const import DOMAIN
from .worker_health import (
    _build_worker_health,
    _call_worker_health,
    validate_worker_health_contract,
    validate_worker_health_request_contract,
    worker_health_side_effects,
)
from .worker_health_polling_constants import (
    DATA_WORKER_HEALTH_POLLING,
    DATA_WORKER_HEALTH_POLLING_CANCEL,
    DATA_WORKER_HEALTH_POLLING_GENERATIONS,
    DATA_WORKER_HEALTH_POLLING_SETUP,
    DATA_WORKER_HEALTH_POLLING_STORE,
    DATA_WORKER_HEALTH_POLLING_TIMER,
    FAILURE_BACKOFF_SECONDS,
    POLLING_HEALTH_SECRET_RE,
    POLLING_HEALTH_URL_RE,
    POLLING_LOADED_FORBIDDEN_RE,
    POLLING_STORAGE_KEY,
    POLLING_STORAGE_VERSION,
    READY_POLL_CADENCE_SECONDS,
    WORKER_HEALTH_POLLING_SCHEMA_PATH,
)
from .worker_health_polling_contract import (
    _coerce_datetime,
    _format_datetime,
    _loaded_polling_entry_is_valid,
    _maximum_resumable_delay_seconds,
    _parse_scheduler_datetime,
    _polling_state_bounds_error,
    _polling_state_cadence_error,
    _polling_state_has_forbidden_text,
    _resumable_polling_cadence_error,
    _resumable_polling_state,
    validate_worker_health_polling_contract,
    worker_health_polling_side_effects,
)
from .worker_health_polling_state import (
    _blocked_or_disabled_state,
    _blocked_poll_result_state,
    _build_polling_state,
    _empty_health_summary,
    _failure_backoff_seconds,
    _failure_family,
    _health_summary,
    _in_flight_polling_state,
    _poll_in_flight,
    _poll_not_due,
    _poll_result_state,
    _poll_result_warnings,
    _polling_preconditions,
    _precondition_message,
    _precondition_repair_recommendation,
    _previous_failure_count,
    _redacted_polling_health_code,
    _redacted_polling_health_message,
    _repair_recommendation,
    _scheduler_metadata,
    _worker_endpoint_configured,
    _worker_endpoint_url,
)
from .worker_health_polling_storage import (
    WorkerHealthPollingStorageHelper,
    _build_home_assistant_store,
    _write_polling_state,
    get_worker_health_polling_state,
    get_worker_health_polling_storage,
)
from .worker_renderer import build_worker_health_request, get_worker_render_client, worker_client_token

try:
    from homeassistant.helpers.event import async_call_later as _ha_async_call_later
except ImportError:  # pragma: no cover - Home Assistant is absent in verifier tests.
    _ha_async_call_later = None


def setup_worker_health_polling(
    hass: Any,
    entry: Any,
    *,
    now: datetime | str | None = None,
) -> dict[str, Any]:
    """Record post-setup durable polling state without calling the worker."""
    entry_id = getattr(entry, "entry_id", "scaffold-entry")
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    setup_generation = _bump_polling_generation(hass, entry_id)
    store = get_worker_health_polling_storage(hass)
    timestamp = _coerce_datetime(now)
    preconditions = _polling_preconditions(hass, entry_id)
    previous_state = store.read_state(entry_id)
    setup_orchestration = None
    if preconditions["eligible"]:
        if _resumable_polling_state(entry_id, previous_state, now=timestamp):
            state = deepcopy(previous_state)
            setup_orchestration = worker_health_polling_side_effects(
                durable_health_storage_written=True,
                scheduler_bookkeeping_written=True,
                post_setup_poll_enqueued=True,
            )
        else:
            state = _build_polling_state(
                entry_id=entry_id,
                status="scheduled",
                code="worker_health_polling_scheduled",
                health_summary=_empty_health_summary(),
                scheduler=_scheduler_metadata(
                    enabled=True,
                    post_setup_poll_enqueued=True,
                    last_poll_at=None,
                    next_poll_not_before=timestamp,
                    consecutive_failures=0,
                ),
                repair_recommendation="none",
                warnings=["worker_health_polling_post_setup_enqueued"],
                orchestration=worker_health_polling_side_effects(
                    durable_health_storage_written=True,
                    scheduler_bookkeeping_written=True,
                    post_setup_poll_enqueued=True,
                ),
            )
    else:
        state = _blocked_or_disabled_state(
            entry_id=entry_id,
            reason=preconditions["reason"],
            now=timestamp,
            during_setup=True,
        )

    validation = validate_worker_health_polling_contract(state)
    if not validation["accepted"]:
        result = _polling_rejection("invalid_worker_health_polling_state")
        result["validation"] = validation
        return result

    setup_orchestration = setup_orchestration or deepcopy(state["orchestration"])
    store.write_state(entry_id, state)
    entry_data[DATA_WORKER_HEALTH_POLLING] = deepcopy(state)
    setup = {
        "accepted": True,
        "code": state["code"],
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "enabled": state["scheduler"]["enabled"],
        "polling_state": deepcopy(state),
        "validation": validation,
        "orchestration": deepcopy(setup_orchestration),
        "generation": setup_generation,
    }
    if state["scheduler"]["enabled"]:
        setup["scheduler_registration"] = _schedule_worker_health_poll(
            hass,
            entry_id,
            due_at=state["scheduler"]["next_poll_not_before"],
            now=timestamp,
        )
    else:
        _cancel_scheduled_worker_health_poll(entry_data)
    entry_data[DATA_WORKER_HEALTH_POLLING_SETUP] = deepcopy(setup)
    return setup


async def async_setup_worker_health_polling(
    hass: Any,
    entry: Any,
    *,
    now: datetime | str | None = None,
) -> dict[str, Any]:
    """Load Home Assistant storage, then record post-setup polling state."""
    store = get_worker_health_polling_storage(hass)
    await store.async_load()
    return setup_worker_health_polling(hass, entry, now=now)


def run_worker_health_poll(
    hass: Any,
    entry_id: str,
    *,
    now: datetime | str | None = None,
) -> dict[str, Any]:
    """Run one scheduled worker health poll for an eligible config entry."""
    prepared = _prepare_worker_health_poll(hass, entry_id, now=now)
    if prepared["complete"]:
        return prepared["result"]

    try:
        health_result = _run_prepared_worker_health_poll(hass, entry_id, prepared)
    except Exception as exc:  # pragma: no cover - defensive cleanup path.
        health_result = _poll_exception_result(exc)
    return _finalize_worker_health_poll(hass, entry_id, prepared=prepared, health_result=health_result)


async def async_run_worker_health_poll(
    hass: Any,
    entry_id: str,
    *,
    now: datetime | str | None = None,
) -> dict[str, Any]:
    """Run one scheduled worker health poll without blocking the event loop."""
    prepared = _prepare_worker_health_poll(hass, entry_id, now=now)
    if prepared["complete"]:
        return prepared["result"]

    executor_job = getattr(hass, "async_add_executor_job", None)
    try:
        health_result = _invalid_prepared_worker_health_request_result(prepared)
        if health_result is not None:
            return _finalize_worker_health_poll(
                hass,
                entry_id,
                prepared=prepared,
                health_result=health_result,
            )
        if callable(executor_job):
            worker_response = await executor_job(partial(_call_prepared_worker_health, prepared))
            health_result = _worker_health_result_from_response(
                hass,
                entry_id,
                prepared=prepared,
                worker_response=worker_response,
            )
        else:
            health_result = _run_prepared_worker_health_poll(hass, entry_id, prepared)
    except Exception as exc:  # pragma: no cover - defensive cleanup path.
        health_result = _poll_exception_result(exc)
    return _finalize_worker_health_poll(hass, entry_id, prepared=prepared, health_result=health_result)


def _prepare_worker_health_poll(
    hass: Any,
    entry_id: str,
    *,
    now: datetime | str | None,
) -> dict[str, Any]:
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id)
    if not isinstance(entry_data, dict) or entry_data.get("entry") is None:
        return {
            "complete": True,
            "result": _polling_rejection("unknown_config_entry"),
        }

    store = get_worker_health_polling_storage(hass)
    previous_state = store.read_state(entry_id)

    timestamp = _coerce_datetime(now)
    preconditions = _polling_preconditions(hass, entry_id)
    if not preconditions["eligible"]:
        state = _blocked_or_disabled_state(
            entry_id=entry_id,
            reason=preconditions["reason"],
            now=timestamp,
            during_setup=False,
        )
        validation = validate_worker_health_polling_contract(state)
        if validation["accepted"]:
            _write_polling_state(hass, entry_id, state)
            _cancel_scheduled_worker_health_poll(entry_data)
        result = _polling_rejection("worker_health_polling_blocked")
        result["polling_state"] = deepcopy(state)
        result["validation"] = validation
        return {"complete": True, "result": result}

    if _poll_in_flight(previous_state):
        return {
            "complete": True,
            "result": _polling_rejection(
                "worker_health_poll_already_in_flight",
                orchestration=worker_health_polling_side_effects(single_flight_guard_checked=True),
            ),
        }

    if _poll_not_due(previous_state, timestamp):
        validation = validate_worker_health_polling_contract(previous_state)
        result = _polling_rejection(
            "worker_health_poll_not_due",
            orchestration=worker_health_polling_side_effects(single_flight_guard_checked=True),
        )
        result["polling_state"] = deepcopy(previous_state)
        result["validation"] = validation
        return {"complete": True, "result": result}

    in_flight_state = _in_flight_polling_state(
        entry_id=entry_id,
        now=timestamp,
        previous_state=previous_state,
    )
    in_flight_validation = validate_worker_health_polling_contract(in_flight_state)
    if not in_flight_validation["accepted"]:
        result = _polling_rejection("invalid_worker_health_polling_state")
        result["validation"] = in_flight_validation
        return {"complete": True, "result": result}
    _write_polling_state(hass, entry_id, in_flight_state)

    client = get_worker_render_client(hass, entry_id)
    token = worker_client_token(client) if client is not None else None
    endpoint_url = _worker_endpoint_url(client)
    request = build_worker_health_request(
        request_id=f"{entry_id}-worker-health-request-001",
        worker_token=token,
    )
    request_validation = validate_worker_health_request_contract(request)
    return {
        "complete": False,
        "client": client,
        "entry": entry_data["entry"],
        "entry_data": entry_data,
        "generation": _polling_generation(hass, entry_id),
        "previous_state": previous_state,
        "request": request,
        "request_validation": request_validation,
        "timestamp": timestamp,
        "token": token,
        "endpoint_url": endpoint_url,
    }


def _finalize_worker_health_poll(
    hass: Any,
    entry_id: str,
    *,
    prepared: dict[str, Any],
    health_result: dict[str, Any],
) -> dict[str, Any]:
    timestamp = prepared["timestamp"]
    previous_state = prepared["previous_state"]
    token = prepared["token"]
    endpoint_url = prepared["endpoint_url"]
    store = get_worker_health_polling_storage(hass)
    current_state = _prepared_poll_current_state(hass, entry_id, prepared)
    if current_state == "unloaded":
        store.delete_state(entry_id)
        return _polling_rejection(
            "worker_health_polling_entry_unloaded",
            orchestration=worker_health_polling_side_effects(
                worker_health_check_called=True,
                single_flight_guard_checked=True,
            ),
        )
    if current_state == "reloaded":
        return _polling_rejection(
            "worker_health_polling_entry_reloaded",
            orchestration=worker_health_polling_side_effects(
                worker_health_check_called=True,
                single_flight_guard_checked=True,
            ),
        )
    if current_state == "context_changed":
        return _finalize_context_changed_worker_health_poll(hass, entry_id, prepared=prepared)
    if health_result.get("accepted") is not True:
        state = _blocked_poll_result_state(
            entry_id=entry_id,
            code=_redacted_polling_health_code(
                health_result.get("code") or "worker_health_poll_failed",
                worker_token=token,
                endpoint_url=endpoint_url,
            ),
            now=timestamp,
            previous_state=previous_state,
        )
    else:
        state = _poll_result_state(
            entry_id=entry_id,
            health=health_result["health"],
            now=timestamp,
            previous_state=previous_state,
            worker_token=token,
            endpoint_url=endpoint_url,
        )

    validation = validate_worker_health_polling_contract(state)
    if not validation["accepted"]:
        result = _polling_rejection("invalid_worker_health_polling_state")
        result["validation"] = validation
        return result

    _write_polling_state(hass, entry_id, state)
    scheduler_registration = _schedule_next_worker_health_poll(hass, entry_id, now=timestamp)
    return {
        "accepted": health_result.get("accepted") is True,
        "code": state["code"],
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "polling_state": deepcopy(state),
        "validation": validation,
        "scheduler_registration": scheduler_registration,
        "orchestration": deepcopy(state["orchestration"]),
    }


def _poll_exception_result(exc: Exception) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": "worker_health_poll_exception",
        "message": str(exc),
    }


def _finalize_context_changed_worker_health_poll(
    hass: Any,
    entry_id: str,
    *,
    prepared: dict[str, Any],
) -> dict[str, Any]:
    timestamp = prepared["timestamp"]
    preconditions = _polling_preconditions(hass, entry_id)
    if preconditions["eligible"]:
        state = _build_polling_state(
            entry_id=entry_id,
            status="scheduled",
            code="worker_health_polling_context_changed",
            health_summary=_empty_health_summary(
                code="worker_health_polling_context_changed",
                message="Worker health polling context changed while a poll was in flight.",
            ),
            scheduler=_scheduler_metadata(
                enabled=True,
                post_setup_poll_enqueued=False,
                last_poll_at=None,
                next_poll_not_before=timestamp,
                consecutive_failures=_previous_failure_count(prepared["previous_state"]),
            ),
            repair_recommendation="none",
            warnings=["worker_health_polling_context_changed"],
            orchestration=worker_health_polling_side_effects(
                durable_health_storage_written=True,
                scheduler_bookkeeping_written=True,
                worker_health_check_called=True,
                single_flight_guard_checked=True,
            ),
        )
    else:
        state = _blocked_or_disabled_state(
            entry_id=entry_id,
            reason=preconditions["reason"],
            now=timestamp,
            during_setup=False,
        )
        state["orchestration"]["worker_health_check_called"] = True

    validation = validate_worker_health_polling_contract(state)
    if not validation["accepted"]:
        result = _polling_rejection("invalid_worker_health_polling_state")
        result["validation"] = validation
        return result

    _write_polling_state(hass, entry_id, state)
    scheduler_registration = _schedule_next_worker_health_poll(hass, entry_id, now=timestamp)
    return {
        "accepted": False,
        "code": state["code"],
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "polling_state": deepcopy(state),
        "validation": validation,
        "scheduler_registration": scheduler_registration,
        "orchestration": deepcopy(state["orchestration"]),
    }


def _run_prepared_worker_health_poll(
    hass: Any,
    entry_id: str,
    prepared: dict[str, Any],
) -> dict[str, Any]:
    health_result = _invalid_prepared_worker_health_request_result(prepared)
    if health_result is not None:
        return health_result
    worker_response = _call_prepared_worker_health(prepared)
    return _worker_health_result_from_response(
        hass,
        entry_id,
        prepared=prepared,
        worker_response=worker_response,
    )


def _invalid_prepared_worker_health_request_result(prepared: dict[str, Any]) -> dict[str, Any] | None:
    request_validation = prepared.get("request_validation")
    if isinstance(request_validation, dict) and request_validation.get("accepted") is True:
        return None
    result = _health_rejection_result(
        "invalid_worker_health_request",
        orchestration=worker_health_side_effects(worker_health_request_validated=False),
    )
    if isinstance(request_validation, dict):
        result["validation"] = request_validation
    return result


def _call_prepared_worker_health(prepared: dict[str, Any]) -> dict[str, Any]:
    return _call_worker_health(prepared["client"], prepared["request"])


def _worker_health_result_from_response(
    hass: Any,
    entry_id: str,
    *,
    prepared: dict[str, Any],
    worker_response: dict[str, Any],
) -> dict[str, Any]:
    current_state = _prepared_poll_current_state(hass, entry_id, prepared)
    if current_state != "current":
        return _health_rejection_result(
            "worker_health_polling_entry_unloaded"
            if current_state == "unloaded"
            else "worker_health_polling_entry_reloaded",
            orchestration=worker_health_side_effects(
                worker_health_check_called=True,
                worker_health_request_validated=True,
            ),
        )
    health = _build_worker_health(
        entry_id=entry_id,
        client=prepared["client"],
        token=prepared["token"],
        request=prepared["request"],
        worker_response=worker_response,
    )
    if health is None:
        return _health_rejection_result(
            "invalid_worker_health_response",
            orchestration=worker_health_side_effects(
                worker_health_check_called=True,
                worker_health_request_validated=True,
            ),
        )

    validation = validate_worker_health_contract(health)
    if not validation["accepted"]:
        result = _health_rejection_result(
            "invalid_integration_worker_health",
            orchestration=worker_health_side_effects(
                worker_health_check_called=True,
                worker_health_request_validated=True,
                worker_health_response_validated=True,
            ),
        )
        result["validation"] = validation
        return result

    return {
        "accepted": True,
        "code": health["code"],
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "enabled": health["status"] == "ready",
        "status": health["status"],
        "health": deepcopy(health),
        "validation": validation,
        "orchestration": deepcopy(health["orchestration"]),
    }


def _health_rejection_result(
    code: str,
    *,
    orchestration: dict[str, bool] | None = None,
) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": code,
        "enabled": False,
        "orchestration": orchestration or worker_health_side_effects(),
    }


def mark_worker_health_poll_in_flight(hass: Any, entry_id: str) -> dict[str, Any]:
    """Mark one entry as in-flight for deterministic single-flight tests."""
    state = get_worker_health_polling_state(hass, entry_id)
    if state is None:
        return _polling_rejection("worker_health_polling_state_missing")
    state["scheduler"]["poll_in_flight"] = True
    state["orchestration"]["single_flight_guard_checked"] = True
    validation = validate_worker_health_polling_contract(state)
    if not validation["accepted"]:
        result = _polling_rejection("invalid_worker_health_polling_state")
        result["validation"] = validation
        return result
    _write_polling_state(hass, entry_id, state)
    return {
        "accepted": True,
        "code": "worker_health_poll_marked_in_flight",
        "entry_id": entry_id,
        "polling_state": deepcopy(state),
        "validation": validation,
    }


def unload_worker_health_polling(hass: Any, entry_id: str) -> dict[str, Any]:
    """Remove durable polling state and entry-local polling metadata."""
    _bump_polling_generation(hass, entry_id)
    store = get_worker_health_polling_storage(hass)
    removed = store.delete_state(entry_id)
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id)
    cancelled = _cancel_scheduled_worker_health_poll(entry_data)
    if isinstance(entry_data, dict):
        entry_data.pop(DATA_WORKER_HEALTH_POLLING, None)
        entry_data.pop(DATA_WORKER_HEALTH_POLLING_SETUP, None)
    return {
        "accepted": True,
        "code": "worker_health_polling_unloaded",
        "entry_id": entry_id,
        "removed": removed,
        "cancelled_scheduled_poll": cancelled,
        "storage": store.summary(),
        "orchestration": worker_health_polling_side_effects(
            durable_health_storage_written=removed,
            scheduler_bookkeeping_written=removed or cancelled,
        ),
    }

def _schedule_next_worker_health_poll(
    hass: Any,
    entry_id: str,
    *,
    now: datetime,
) -> dict[str, Any]:
    state = get_worker_health_polling_state(hass, entry_id)
    scheduler = state.get("scheduler") if isinstance(state, dict) else None
    if not isinstance(scheduler, dict) or scheduler.get("enabled") is not True:
        entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id)
        cancelled = _cancel_scheduled_worker_health_poll(entry_data)
        return {
            "registered": False,
            "reason": "worker_health_polling_disabled",
            "cancelled_existing": cancelled,
        }
    due_at = scheduler.get("next_poll_not_before")
    if not isinstance(due_at, str):
        return {
            "registered": False,
            "reason": "worker_health_polling_next_poll_missing",
        }
    return _schedule_worker_health_poll(hass, entry_id, due_at=due_at, now=now)


def _schedule_worker_health_poll(
    hass: Any,
    entry_id: str,
    *,
    due_at: datetime | str,
    now: datetime | str | None,
) -> dict[str, Any]:
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id)
    if not isinstance(entry_data, dict):
        return {"registered": False, "reason": "unknown_config_entry"}

    due_at_dt = _coerce_datetime(due_at)
    now_dt = _coerce_datetime(now)
    delay_seconds = max(0.0, (due_at_dt - now_dt).total_seconds())
    delay_value: int | float = (
        int(delay_seconds) if delay_seconds.is_integer() else delay_seconds
    )
    _cancel_scheduled_worker_health_poll(entry_data)

    def _run_scheduled_poll(callback_now: Any = None) -> None:
        active_entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id)
        if isinstance(active_entry_data, dict):
            active_entry_data.pop(DATA_WORKER_HEALTH_POLLING_CANCEL, None)
            active_entry_data.pop(DATA_WORKER_HEALTH_POLLING_TIMER, None)
        if not _entry_still_loaded(hass, entry_id):
            return
        poll_now = _coerce_callback_datetime(callback_now)
        create_task = getattr(hass, "async_create_task", None)
        executor_job = getattr(hass, "async_add_executor_job", None)
        if callable(create_task) and callable(executor_job):
            create_task(async_run_worker_health_poll(hass, entry_id, now=poll_now))
        else:
            run_worker_health_poll(hass, entry_id, now=poll_now)

    cancel = None
    fake_scheduler = getattr(hass, "async_call_later", None)
    if callable(fake_scheduler):
        cancel = fake_scheduler(delay_seconds, _run_scheduled_poll)
    elif _ha_async_call_later is not None:
        cancel = _ha_async_call_later(hass, delay_seconds, _run_scheduled_poll)

    registered = callable(cancel)
    if registered:
        entry_data[DATA_WORKER_HEALTH_POLLING_CANCEL] = cancel
    timer = {
        "registered": registered,
        "entry_id": entry_id,
        "scheduled_at": now_dt.isoformat(),
        "due_at": due_at_dt.isoformat(),
        "delay_seconds": delay_value,
    }
    entry_data[DATA_WORKER_HEALTH_POLLING_TIMER] = deepcopy(timer)
    return timer


def _cancel_scheduled_worker_health_poll(entry_data: Any) -> bool:
    if not isinstance(entry_data, dict):
        return False
    cancel = entry_data.pop(DATA_WORKER_HEALTH_POLLING_CANCEL, None)
    entry_data.pop(DATA_WORKER_HEALTH_POLLING_TIMER, None)
    if callable(cancel):
        cancel()
        return True
    return False


def _coerce_callback_datetime(value: Any) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    try:
        return _coerce_datetime(value)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


def _polling_generations(hass: Any) -> dict[str, int]:
    domain_data = hass.data.setdefault(DOMAIN, {})
    generations = domain_data.get(DATA_WORKER_HEALTH_POLLING_GENERATIONS)
    if not isinstance(generations, dict):
        generations = {}
        domain_data[DATA_WORKER_HEALTH_POLLING_GENERATIONS] = generations
    return generations


def _polling_generation(hass: Any, entry_id: str) -> int:
    value = _polling_generations(hass).get(entry_id)
    return value if type(value) is int and value >= 0 else 0


def _bump_polling_generation(hass: Any, entry_id: str) -> int:
    generation = _polling_generation(hass, entry_id) + 1
    _polling_generations(hass)[entry_id] = generation
    return generation


def _entry_still_loaded(hass: Any, entry_id: str) -> bool:
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id)
    return isinstance(entry_data, dict) and entry_data.get("entry") is not None


def _prepared_poll_current_state(
    hass: Any,
    entry_id: str,
    prepared: dict[str, Any],
) -> str:
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id)
    if not isinstance(entry_data, dict) or entry_data.get("entry") is None:
        return "unloaded"
    if _polling_generation(hass, entry_id) != prepared.get("generation"):
        return "reloaded"
    if entry_data is not prepared.get("entry_data"):
        return "reloaded"
    if entry_data.get("entry") is not prepared.get("entry"):
        return "reloaded"
    current_client = get_worker_render_client(hass, entry_id)
    if current_client is not prepared.get("client"):
        return "context_changed"
    if worker_client_token(current_client) != prepared.get("token"):
        return "context_changed"
    return "current"


def _polling_rejection(
    code: str,
    *,
    orchestration: dict[str, bool] | None = None,
) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": code,
        "enabled": False,
        "orchestration": orchestration or worker_health_polling_side_effects(),
    }
