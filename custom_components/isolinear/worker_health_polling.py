"""Durable worker health polling boundary for Isolinear."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .const import DOMAIN
from .job_state import JobStateSnapshotValidationError, _validate_json_schema
from .worker_health import (
    _build_worker_health,
    _call_worker_health,
    validate_worker_health_contract,
    validate_worker_health_request_contract,
    worker_health_side_effects,
)
from .worker_readiness import get_worker_readiness
from .worker_renderer import build_worker_health_request, get_worker_render_client, worker_client_token

try:
    from homeassistant.helpers.storage import Store as HomeAssistantStore
except ImportError:  # pragma: no cover - Home Assistant is absent in verifier tests.
    HomeAssistantStore = None

try:
    from homeassistant.helpers.event import async_call_later as _ha_async_call_later
except ImportError:  # pragma: no cover - Home Assistant is absent in verifier tests.
    _ha_async_call_later = None


DATA_WORKER_HEALTH_POLLING = "worker_health_polling"
DATA_WORKER_HEALTH_POLLING_CANCEL = "worker_health_polling_cancel"
DATA_WORKER_HEALTH_POLLING_GENERATIONS = "worker_health_polling_generations"
DATA_WORKER_HEALTH_POLLING_TIMER = "worker_health_polling_timer"
DATA_WORKER_HEALTH_POLLING_SETUP = "worker_health_polling_setup"
DATA_WORKER_HEALTH_POLLING_STORE = "worker_health_polling_storage_helper"

POLLING_STORAGE_KEY = "isolinear_worker_health_polling"
POLLING_STORAGE_VERSION = 1
READY_POLL_CADENCE_SECONDS = 300
FAILURE_BACKOFF_SECONDS = (30, 60, 120, 300, 900)
POLLING_HEALTH_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
POLLING_HEALTH_SECRET_RE = re.compile(
    r"\bBearer\s+\S+|access_token|home_assistant_token|long_lived_access_token|worker_token",
    re.IGNORECASE,
)
POLLING_LOADED_FORBIDDEN_RE = re.compile(
    r"\bBearer\s+\S+|access_token|home_assistant_token|long_lived_access_token",
    re.IGNORECASE,
)

WORKER_HEALTH_POLLING_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "schemas"
    / "integration-worker-health-polling-state.schema.json"
)


class WorkerHealthPollingStorageHelper:
    """Small JSON-safe storage-helper surface for durable polling state."""

    def __init__(self, *, ha_store: Any | None = None) -> None:
        self.storage_key = POLLING_STORAGE_KEY
        self.version = POLLING_STORAGE_VERSION
        self._ha_store = ha_store
        self.backend = (
            "home_assistant_storage_helper"
            if ha_store is not None
            else "in_memory_scaffold_storage_helper"
        )
        self.data: dict[str, Any] = {
            "version": self.version,
            "entries": {},
        }
        self._deleted_entry_ids: set[str] = set()

    async def async_load(self) -> dict[str, Any]:
        """Load persisted polling state when Home Assistant storage is available."""
        async_load = getattr(self._ha_store, "async_load", None)
        if not callable(async_load):
            return self.summary()

        loaded = await async_load()
        if (
            isinstance(loaded, dict)
            and loaded.get("version") == self.version
            and isinstance(loaded.get("entries"), dict)
        ):
            current_entries = self.data.setdefault("entries", {})
            for entry_id, state in loaded["entries"].items():
                if (
                    entry_id not in current_entries
                    and entry_id not in self._deleted_entry_ids
                    and _loaded_polling_entry_is_valid(entry_id, state)
                ):
                    current_entries[entry_id] = deepcopy(state)
        return self.summary()

    def read_state(self, entry_id: str) -> dict[str, Any] | None:
        state = self.data["entries"].get(entry_id)
        return deepcopy(state) if isinstance(state, dict) else None

    def write_state(self, entry_id: str, state: dict[str, Any]) -> None:
        self._deleted_entry_ids.discard(entry_id)
        self.data["entries"][entry_id] = deepcopy(state)
        self._schedule_save()

    def delete_state(self, entry_id: str) -> bool:
        self._deleted_entry_ids.add(entry_id)
        removed = self.data["entries"].pop(entry_id, None) is not None
        self._schedule_save()
        return removed

    def summary(self) -> dict[str, Any]:
        return {
            "storage_key": self.storage_key,
            "version": self.version,
            "backend": self.backend,
            "entry_ids": sorted(self.data["entries"]),
            "entry_count": len(self.data["entries"]),
        }

    def _schedule_save(self) -> None:
        async_delay_save = getattr(self._ha_store, "async_delay_save", None)
        if callable(async_delay_save):
            async_delay_save(lambda: deepcopy(self.data), 0)


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


def get_worker_health_polling_state(hass: Any, entry_id: str) -> dict[str, Any] | None:
    """Return the latest durable polling state for one config entry."""
    return get_worker_health_polling_storage(hass).read_state(entry_id)


def get_worker_health_polling_storage(hass: Any) -> WorkerHealthPollingStorageHelper:
    """Return the integration-owned worker health polling storage helper."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    store = domain_data.get(DATA_WORKER_HEALTH_POLLING_STORE)
    if isinstance(store, WorkerHealthPollingStorageHelper):
        return store
    store = WorkerHealthPollingStorageHelper(ha_store=_build_home_assistant_store(hass))
    domain_data[DATA_WORKER_HEALTH_POLLING_STORE] = store
    return store


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


def _write_polling_state(hass: Any, entry_id: str, state: dict[str, Any]) -> None:
    get_worker_health_polling_storage(hass).write_state(entry_id, state)
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    entry_data[DATA_WORKER_HEALTH_POLLING] = deepcopy(state)


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


def _build_home_assistant_store(hass: Any) -> Any | None:
    if HomeAssistantStore is None:
        return None
    return HomeAssistantStore(hass, POLLING_STORAGE_VERSION, POLLING_STORAGE_KEY)


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


def _worker_endpoint_url(client: Any) -> str | None:
    provider_metadata = getattr(client, "provider_metadata", None)
    if callable(provider_metadata):
        metadata = provider_metadata()
        if isinstance(metadata, dict) and isinstance(metadata.get("endpoint_url"), str):
            return metadata["endpoint_url"]
    endpoint_url = getattr(client, "endpoint_url", None)
    return endpoint_url if isinstance(endpoint_url, str) else None


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
