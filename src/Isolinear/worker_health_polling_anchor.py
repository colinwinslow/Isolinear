from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from custom_components.isolinear import async_unload_entry
from custom_components.isolinear.const import DOMAIN
from custom_components.isolinear.worker_health_polling import (
    DATA_WORKER_HEALTH_POLLING_STORE,
    DATA_WORKER_HEALTH_POLLING_TIMER,
    FAILURE_BACKOFF_SECONDS,
    READY_POLL_CADENCE_SECONDS,
    WorkerHealthPollingStorageHelper,
    async_setup_worker_health_polling,
    get_worker_health_polling_state,
    get_worker_health_polling_storage,
    mark_worker_health_poll_in_flight,
    run_worker_health_poll,
    setup_worker_health_polling,
    unload_worker_health_polling,
)
from custom_components.isolinear.worker_readiness import (
    provision_integration_worker_token,
    rotate_integration_worker_token,
)
from custom_components.isolinear.worker_renderer import DATA_WORKER_RENDER_CLIENT

from .contracts import ContractValidationError, validate_contract
from .dashboard_card_anchor import repo_root
from .job_orchestration_scaffold_anchor import _fake_hass, _run
from .websocket_command_registration_anchor import FakeWebSocketApiModule
from .worker_health_readiness_endpoint_anchor import (
    FakeWorkerHealthClient,
    _accepted_health_response,
    _ready_hass_with_fake_health_client,
    _setup_entry_in_hass,
)
from .worker_token_provisioning_readiness_anchor import (
    WORKER_ENDPOINT_URL,
    WORKER_READINESS_SECOND_TOKEN,
    WORKER_READINESS_TEST_TOKEN,
    CountingTokenFactory,
    _entry_data,
    _setup_readiness_hass,
    _worker_entry,
)


BASE_TIME = datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc)
SECOND_TIME = datetime(2026, 6, 11, 12, 1, 0, tzinfo=timezone.utc)

WORKER_HEALTH_POLLING_FILES = [
    "custom_components/isolinear/worker_health_polling.py",
    "custom_components/isolinear/worker_health.py",
    "custom_components/isolinear/worker_readiness.py",
    "custom_components/isolinear/__init__.py",
    "docs/decisions/0015-durable-worker-health-polling.md",
    "docs/specs/home-assistant-durable-worker-health-polling-scaffold-spec.md",
    "bdd/integration/home-assistant-durable-worker-health-polling-scaffold-bdd.md",
    "bdd/integration/home-assistant-durable-worker-health-polling-scaffold-evidence.md",
    "docs/evals/home_assistant_durable_worker_health_polling_scaffold.yaml",
    "docs/schemas/integration-worker-health-polling-state.schema.json",
    "tests/test_worker_health_polling_anchor.py",
    "evals/home_assistant_durable_worker_health_polling_scaffold.py",
    "src/Isolinear/worker_health_polling_anchor.py",
]

WORKER_HEALTH_POLLING_FORBIDDEN_SIDE_EFFECT_KEYS = [
    "home_assistant_history_read",
    "semantic_memory_called",
    "home_assistant_service_or_state_mutation_called",
    "token_generated",
    "token_rotation_called",
    "token_repair_called",
    "worker_render_called",
    "model_provider_called",
    "chart_rendering_called",
    "chart_artifact_written",
    "durable_retry_storage_written",
    "recorder_called",
    "config_entry_options_written",
    "external_queue_called",
    "automatic_retry_called",
    "automatic_progress_task_called",
    "automatic_repair_called",
    "worker_endpoint_leaked_to_card",
    "token_leaked_to_card",
    "polling_metadata_leaked_to_card",
]


class InspectingWorkerHealthClient(FakeWorkerHealthClient):
    def __init__(
        self,
        *,
        hass: Any,
        entry_id: str,
        endpoint_url: str,
        worker_token: str,
        response: dict[str, Any],
    ) -> None:
        super().__init__(
            endpoint_url=endpoint_url,
            worker_token=worker_token,
            response=response,
        )
        self.hass = hass
        self.entry_id = entry_id
        self.poll_in_flight_during_health_call: bool | None = None

    def check_health(self, health_request: dict[str, Any]) -> dict[str, Any]:
        state = get_worker_health_polling_state(self.hass, self.entry_id)
        self.poll_in_flight_during_health_call = (
            isinstance(state, dict)
            and isinstance(state.get("scheduler"), dict)
            and state["scheduler"].get("poll_in_flight") is True
        )
        return super().check_health(health_request)


class FakeHomeAssistantPollingStore:
    def __init__(self, loaded_data: dict[str, Any]) -> None:
        self.loaded_data = deepcopy(loaded_data)
        self.saved_payloads: list[dict[str, Any]] = []
        self.save_delays: list[int] = []

    async def async_load(self) -> dict[str, Any]:
        return deepcopy(self.loaded_data)

    def async_delay_save(self, data_func: Any, delay: int) -> None:
        self.saved_payloads.append(deepcopy(data_func()))
        self.save_delays.append(delay)


class FakePollingScheduler:
    def __init__(self) -> None:
        self.scheduled: list[dict[str, Any]] = []
        self.cancelled: list[dict[str, Any]] = []
        self.created_tasks: list[Any] = []
        self.executor_jobs: list[Any] = []
        self.task_results: list[Any] = []

    def install(self, hass: Any, *, executor: bool = False) -> "FakePollingScheduler":
        hass.async_call_later = self.async_call_later
        if executor:
            hass.async_add_executor_job = self.async_add_executor_job
            hass.async_create_task = self.async_create_task
        return self

    def async_call_later(self, delay_seconds: float, action: Any) -> Any:
        delay_value = float(delay_seconds)
        record = {
            "delay_seconds": int(delay_value) if delay_value.is_integer() else delay_value,
            "action": action,
            "cancelled": False,
            "fired": False,
        }
        self.scheduled.append(record)

        def cancel() -> None:
            record["cancelled"] = True
            self.cancelled.append(record)

        return cancel

    async def async_add_executor_job(self, func: Any) -> Any:
        self.executor_jobs.append(func)
        return func()

    def async_create_task(self, coro: Any) -> Any:
        self.created_tasks.append(coro)
        result = _run(coro)
        self.task_results.append(result)
        return result

    def fire_next(self, now: datetime) -> dict[str, Any]:
        for record in self.scheduled:
            if not record["cancelled"] and not record["fired"]:
                record["fired"] = True
                record["action"](now)
                return record
        raise AssertionError("No pending worker health polling timer to fire.")

    def summary(self) -> dict[str, Any]:
        return {
            "scheduled_count": len(self.scheduled),
            "cancelled_count": len(self.cancelled),
            "created_task_count": len(self.created_tasks),
            "executor_job_count": len(self.executor_jobs),
            "scheduled_delays": [record["delay_seconds"] for record in self.scheduled],
            "fired_count": sum(1 for record in self.scheduled if record["fired"]),
        }


class UnloadingWorkerHealthClient(FakeWorkerHealthClient):
    def __init__(
        self,
        *,
        hass: Any,
        entry_id: str,
        endpoint_url: str,
        worker_token: str,
        response: dict[str, Any],
    ) -> None:
        super().__init__(
            endpoint_url=endpoint_url,
            worker_token=worker_token,
            response=response,
        )
        self.hass = hass
        self.entry_id = entry_id

    def check_health(self, health_request: dict[str, Any]) -> dict[str, Any]:
        unload_worker_health_polling(self.hass, self.entry_id)
        self.hass.data.get(DOMAIN, {}).pop(self.entry_id, None)
        return super().check_health(health_request)


class ReloadingWorkerHealthClient(FakeWorkerHealthClient):
    def __init__(
        self,
        *,
        hass: Any,
        entry_id: str,
        endpoint_url: str,
        worker_token: str,
        response: dict[str, Any],
    ) -> None:
        super().__init__(
            endpoint_url=endpoint_url,
            worker_token=worker_token,
            response=response,
        )
        self.hass = hass
        self.entry_id = entry_id
        self.reloaded_entry: Any | None = None
        self.reloaded_client: FakeWorkerHealthClient | None = None

    def check_health(self, health_request: dict[str, Any]) -> dict[str, Any]:
        unload_worker_health_polling(self.hass, self.entry_id)
        self.hass.data.get(DOMAIN, {}).pop(self.entry_id, None)
        self.reloaded_entry = _worker_entry(self.entry_id)
        _setup_entry_in_hass(self.hass, self.reloaded_entry)
        self.reloaded_client = _make_entry_ready_for_polling(
            self.hass,
            self.reloaded_entry,
            _accepted_health_response("ready"),
            WORKER_READINESS_SECOND_TOKEN,
        )
        setup_worker_health_polling(self.hass, self.reloaded_entry, now=BASE_TIME + timedelta(seconds=30))
        return super().check_health(health_request)


class RotatingWorkerHealthClient(FakeWorkerHealthClient):
    def __init__(
        self,
        *,
        hass: Any,
        entry_id: str,
        endpoint_url: str,
        worker_token: str,
        response: dict[str, Any],
    ) -> None:
        super().__init__(
            endpoint_url=endpoint_url,
            worker_token=worker_token,
            response=response,
        )
        self.hass = hass
        self.entry_id = entry_id
        self.replacement_client: FakeWorkerHealthClient | None = None
        self.rotation_result: dict[str, Any] | None = None

    def check_health(self, health_request: dict[str, Any]) -> dict[str, Any]:
        self.rotation_result = rotate_integration_worker_token(
            self.hass,
            self.entry_id,
            token_factory=CountingTokenFactory(WORKER_READINESS_SECOND_TOKEN),
        )
        self.replacement_client = FakeWorkerHealthClient(
            endpoint_url=WORKER_ENDPOINT_URL,
            worker_token=WORKER_READINESS_SECOND_TOKEN,
            response=_accepted_health_response("ready"),
        )
        _entry_data(self.hass, self.entry_id)[DATA_WORKER_RENDER_CLIENT] = self.replacement_client
        return super().check_health(health_request)


def verify_worker_health_polling_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in WORKER_HEALTH_POLLING_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_setup_enqueues_post_setup_poll_without_worker_call(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, client, _provision, _health_setup = _ready_hass_with_fake_health_client(
        "worker-polling-setup-entry",
        _accepted_health_response("ready"),
    )
    setup = setup_worker_health_polling(hass, entry, now=BASE_TIME)
    state = get_worker_health_polling_state(hass, entry.entry_id)
    return {
        "setup": _polling_setup_summary(setup),
        "state": _polling_state_summary(state),
        "state_validation": _validate_polling_state(state, root),
        "storage": get_worker_health_polling_storage(hass).summary(),
        "health_call_count": client.health_calls,
        "render_call_count": client.render_calls,
    }


def verify_home_assistant_timer_schedules_post_setup_and_next_poll(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, client, _provision, _health_setup = _ready_hass_with_fake_health_client(
        "worker-polling-scheduler-entry",
        _accepted_health_response("ready"),
    )
    scheduler = FakePollingScheduler().install(hass, executor=True)
    setup = setup_worker_health_polling(hass, entry, now=BASE_TIME)
    entry_data = _entry_data(hass, entry.entry_id)
    setup_timer = deepcopy(entry_data.get(DATA_WORKER_HEALTH_POLLING_TIMER))
    health_calls_after_setup = client.health_calls

    fired = scheduler.fire_next(BASE_TIME)
    state_after_fire = get_worker_health_polling_state(hass, entry.entry_id)
    next_timer = deepcopy(entry_data.get(DATA_WORKER_HEALTH_POLLING_TIMER))
    unload = unload_worker_health_polling(hass, entry.entry_id)

    return {
        "setup": _polling_setup_summary(setup),
        "setup_timer": setup_timer,
        "health_calls_after_setup": health_calls_after_setup,
        "fired_timer_delay_seconds": fired["delay_seconds"],
        "state_after_fire": _polling_state_summary(state_after_fire),
        "state_validation": _validate_polling_state(state_after_fire, root),
        "next_timer": next_timer,
        "health_call_count": client.health_calls,
        "render_call_count": client.render_calls,
        "created_task_count": scheduler.summary()["created_task_count"],
        "executor_job_count": scheduler.summary()["executor_job_count"],
        "unload": unload,
        "timer_absent_after_unload": DATA_WORKER_HEALTH_POLLING_TIMER not in entry_data,
        "scheduler": scheduler.summary(),
    }


def verify_scheduled_ready_poll_records_cadence(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, client, _provision, _health_setup = _ready_hass_with_fake_health_client(
        "worker-polling-ready-entry",
        _accepted_health_response("ready"),
    )
    setup_worker_health_polling(hass, entry, now=BASE_TIME)
    result = run_worker_health_poll(hass, entry.entry_id, now=BASE_TIME)
    state = get_worker_health_polling_state(hass, entry.entry_id)
    entry_data = _entry_data(hass, entry.entry_id)
    return {
        "result": _polling_result_summary(result),
        "state": _polling_state_summary(state),
        "state_validation": _validate_polling_state(state, root),
        "health_call_count": client.health_calls,
        "render_call_count": client.render_calls,
        "explicit_health_state_written": "worker_health" in entry_data,
        "worker_health_setup_code": entry_data["worker_health_setup"]["code"],
        "next_poll_delay_seconds": _seconds_between(
            state["scheduler"]["last_poll_at"],
            state["scheduler"]["next_poll_not_before"],
        ),
        "ready_cadence_seconds": READY_POLL_CADENCE_SECONDS,
    }


def verify_next_poll_timing_blocks_early_duplicate_polls(root=None) -> dict[str, Any]:
    root = root or repo_root()
    ready_hass, ready_entry, ready_client, _ready_provision, _ready_setup = _ready_hass_with_fake_health_client(
        "worker-polling-early-ready-entry",
        _accepted_health_response("ready"),
    )
    setup_worker_health_polling(ready_hass, ready_entry, now=BASE_TIME)
    first_ready = run_worker_health_poll(ready_hass, ready_entry.entry_id, now=BASE_TIME)
    early_ready = run_worker_health_poll(
        ready_hass,
        ready_entry.entry_id,
        now=BASE_TIME + timedelta(seconds=60),
    )
    ready_state = get_worker_health_polling_state(ready_hass, ready_entry.entry_id)
    _entry_data(ready_hass, ready_entry.entry_id).pop(DATA_WORKER_RENDER_CLIENT, None)
    lost_precondition_ready = run_worker_health_poll(
        ready_hass,
        ready_entry.entry_id,
        now=BASE_TIME + timedelta(seconds=90),
    )
    lost_precondition_state = get_worker_health_polling_state(ready_hass, ready_entry.entry_id)

    not_ready_hass, not_ready_entry, not_ready_client, _provision, _setup = _ready_hass_with_fake_health_client(
        "worker-polling-early-not-ready-entry",
        _accepted_health_response("not_ready", rendering=False),
    )
    setup_worker_health_polling(not_ready_hass, not_ready_entry, now=BASE_TIME)
    first_not_ready = run_worker_health_poll(not_ready_hass, not_ready_entry.entry_id, now=BASE_TIME)
    early_not_ready = run_worker_health_poll(
        not_ready_hass,
        not_ready_entry.entry_id,
        now=BASE_TIME + timedelta(seconds=10),
    )
    not_ready_state = get_worker_health_polling_state(not_ready_hass, not_ready_entry.entry_id)

    return {
        "ready": {
            "first_result": _polling_result_summary(first_ready),
            "early_result": _polling_result_summary(early_ready),
            "state": _polling_state_summary(ready_state),
            "state_validation": _validate_polling_state(ready_state, root),
            "health_call_count": ready_client.health_calls,
            "next_poll_delay_seconds": _seconds_between(
                ready_state["scheduler"]["last_poll_at"],
                ready_state["scheduler"]["next_poll_not_before"],
            ),
            "lost_precondition_result": _polling_result_summary(lost_precondition_ready),
            "lost_precondition_state": _polling_state_summary(lost_precondition_state),
            "lost_precondition_validation": _validate_polling_state(lost_precondition_state, root),
        },
        "not_ready": {
            "first_result": _polling_result_summary(first_not_ready),
            "early_result": _polling_result_summary(early_not_ready),
            "state": _polling_state_summary(not_ready_state),
            "state_validation": _validate_polling_state(not_ready_state, root),
            "health_call_count": not_ready_client.health_calls,
            "consecutive_failures": not_ready_state["scheduler"]["consecutive_failures"],
            "backoff_seconds": not_ready_state["scheduler"]["backoff_seconds"],
        },
    }


def verify_failure_poll_results_use_bounded_backoff(root=None) -> dict[str, Any]:
    root = root or repo_root()
    not_ready_hass, not_ready_entry, not_ready_client, _provision, _setup = _ready_hass_with_fake_health_client(
        "worker-polling-not-ready-entry",
        _accepted_health_response("not_ready", rendering=False),
    )
    setup_worker_health_polling(not_ready_hass, not_ready_entry, now=BASE_TIME)
    first_not_ready = run_worker_health_poll(not_ready_hass, not_ready_entry.entry_id, now=BASE_TIME)
    second_not_ready = run_worker_health_poll(not_ready_hass, not_ready_entry.entry_id, now=SECOND_TIME)
    not_ready_state = get_worker_health_polling_state(not_ready_hass, not_ready_entry.entry_id)

    unavailable_hass, unavailable_entry, unavailable_client, _provision, _setup = _ready_hass_with_fake_health_client(
        "worker-polling-unavailable-entry",
        {
            "accepted": False,
            "code": "worker_connection_error",
            "message": "Connection refused by worker health endpoint.",
            "retry_safe": True,
        },
    )
    setup_worker_health_polling(unavailable_hass, unavailable_entry, now=BASE_TIME)
    unavailable_result = run_worker_health_poll(unavailable_hass, unavailable_entry.entry_id, now=BASE_TIME)
    unavailable_state = get_worker_health_polling_state(unavailable_hass, unavailable_entry.entry_id)

    return {
        "not_ready": {
            "first_result": _polling_result_summary(first_not_ready),
            "second_result": _polling_result_summary(second_not_ready),
            "state": _polling_state_summary(not_ready_state),
            "state_validation": _validate_polling_state(not_ready_state, root),
            "health_call_count": not_ready_client.health_calls,
            "render_call_count": not_ready_client.render_calls,
        },
        "unavailable": {
            "result": _polling_result_summary(unavailable_result),
            "state": _polling_state_summary(unavailable_state),
            "state_validation": _validate_polling_state(unavailable_state, root),
            "health_call_count": unavailable_client.health_calls,
            "render_call_count": unavailable_client.render_calls,
        },
        "expected_backoff_seconds": list(FAILURE_BACKOFF_SECONDS),
    }


def verify_missing_preconditions_block_before_worker_call(root=None) -> dict[str, Any]:
    root = root or repo_root()
    entry = _worker_entry("worker-polling-blocked-entry")
    hass = _setup_readiness_hass(entry)
    setup = setup_worker_health_polling(hass, entry, now=BASE_TIME)
    result = run_worker_health_poll(hass, entry.entry_id, now=BASE_TIME)
    state = get_worker_health_polling_state(hass, entry.entry_id)
    return {
        "setup": _polling_setup_summary(setup),
        "result": _polling_result_summary(result),
        "state": _polling_state_summary(state),
        "state_validation": _validate_polling_state(state, root),
        "worker_client_present": DATA_WORKER_RENDER_CLIENT in _entry_data(hass, entry.entry_id),
    }


def verify_single_flight_guard_prevents_overlapping_poll(root=None) -> dict[str, Any]:
    root = root or repo_root()
    normal_poll = verify_normal_poll_marks_and_clears_in_flight_guard(root)
    hass, entry, client, _provision, _health_setup = _ready_hass_with_fake_health_client(
        "worker-polling-single-flight-entry",
        _accepted_health_response("ready"),
    )
    setup_worker_health_polling(hass, entry, now=BASE_TIME)
    mark = mark_worker_health_poll_in_flight(hass, entry.entry_id)
    result = run_worker_health_poll(hass, entry.entry_id, now=BASE_TIME)
    state = get_worker_health_polling_state(hass, entry.entry_id)
    return {
        "mark": _polling_result_summary(mark),
        "result": _polling_result_summary(result),
        "state": _polling_state_summary(state),
        "state_validation": _validate_polling_state(state, root),
        "health_call_count": client.health_calls,
        "render_call_count": client.render_calls,
        "normal_poll": normal_poll,
    }


def verify_normal_poll_marks_and_clears_in_flight_guard(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, _client, _provision, _health_setup = _ready_hass_with_fake_health_client(
        "worker-polling-normal-single-flight-entry",
        _accepted_health_response("ready"),
    )
    client = InspectingWorkerHealthClient(
        hass=hass,
        entry_id=entry.entry_id,
        endpoint_url=WORKER_ENDPOINT_URL,
        worker_token=WORKER_READINESS_TEST_TOKEN,
        response=_accepted_health_response("ready"),
    )
    _entry_data(hass, entry.entry_id)[DATA_WORKER_RENDER_CLIENT] = client
    setup_worker_health_polling(hass, entry, now=BASE_TIME)
    result = run_worker_health_poll(hass, entry.entry_id, now=BASE_TIME)
    state = get_worker_health_polling_state(hass, entry.entry_id)
    return {
        "result": _polling_result_summary(result),
        "state": _polling_state_summary(state),
        "state_validation": _validate_polling_state(state, root),
        "poll_in_flight_during_health_call": client.poll_in_flight_during_health_call,
        "poll_in_flight_after_poll": state["scheduler"]["poll_in_flight"],
        "health_call_count": client.health_calls,
        "render_call_count": client.render_calls,
    }


def verify_unload_removes_durable_polling_state(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = _worker_entry("worker-polling-unload-entry-a")
    entry_b = _worker_entry("worker-polling-unload-entry-b")
    _setup_entry_in_hass(hass, entry_a)
    _setup_entry_in_hass(hass, entry_b)
    _make_entry_ready_for_polling(hass, entry_a, _accepted_health_response("ready"), WORKER_READINESS_TEST_TOKEN)
    _make_entry_ready_for_polling(hass, entry_b, _accepted_health_response("ready"), WORKER_READINESS_SECOND_TOKEN)
    setup_worker_health_polling(hass, entry_a, now=BASE_TIME)
    setup_worker_health_polling(hass, entry_b, now=BASE_TIME)
    before_unload = get_worker_health_polling_storage(hass).summary()
    unload_result = _run(async_unload_entry(hass, entry_a))
    after_unload = get_worker_health_polling_storage(hass).summary()
    return {
        "before_unload": before_unload,
        "unload_result": unload_result,
        "after_unload": after_unload,
        "entry_a_state": get_worker_health_polling_state(hass, entry_a.entry_id),
        "entry_b_state": _polling_state_summary(get_worker_health_polling_state(hass, entry_b.entry_id)),
        "entry_b_validation": _validate_polling_state(get_worker_health_polling_state(hass, entry_b.entry_id), root),
    }


def verify_worker_health_polling_stays_config_entry_scoped(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = _worker_entry("worker-polling-isolation-entry-a")
    entry_b = _worker_entry("worker-polling-isolation-entry-b")
    _setup_entry_in_hass(hass, entry_a)
    _setup_entry_in_hass(hass, entry_b)
    client_a = _make_entry_ready_for_polling(
        hass,
        entry_a,
        _accepted_health_response("ready"),
        WORKER_READINESS_TEST_TOKEN,
    )
    client_b = _make_entry_ready_for_polling(
        hass,
        entry_b,
        _accepted_health_response("not_ready", rendering=False),
        WORKER_READINESS_SECOND_TOKEN,
    )
    setup_worker_health_polling(hass, entry_a, now=BASE_TIME)
    setup_worker_health_polling(hass, entry_b, now=BASE_TIME)
    result_a = run_worker_health_poll(hass, entry_a.entry_id, now=BASE_TIME)
    result_b = run_worker_health_poll(hass, entry_b.entry_id, now=BASE_TIME)
    state_a = get_worker_health_polling_state(hass, entry_a.entry_id)
    state_b = get_worker_health_polling_state(hass, entry_b.entry_id)
    return {
        "entry_a": {
            "result": _polling_result_summary(result_a),
            "state": _polling_state_summary(state_a),
            "state_validation": _validate_polling_state(state_a, root),
            "health_call_count": client_a.health_calls,
            "raw_request_uses_own_token": (
                client_a.received_health_requests[0]["headers"]["authorization"]
                == f"Bearer {WORKER_READINESS_TEST_TOKEN}"
            ),
            "other_token_absent_from_request": WORKER_READINESS_SECOND_TOKEN
            not in str(client_a.received_health_requests[0]),
        },
        "entry_b": {
            "result": _polling_result_summary(result_b),
            "state": _polling_state_summary(state_b),
            "state_validation": _validate_polling_state(state_b, root),
            "health_call_count": client_b.health_calls,
            "raw_request_uses_own_token": (
                client_b.received_health_requests[0]["headers"]["authorization"]
                == f"Bearer {WORKER_READINESS_SECOND_TOKEN}"
            ),
            "other_token_absent_from_request": WORKER_READINESS_TEST_TOKEN
            not in str(client_b.received_health_requests[0]),
        },
    }


def verify_storage_load_merges_persisted_entries_without_dropping_unsaved(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass_a, entry_a, _client_a, _provision_a, _health_setup_a = _ready_hass_with_fake_health_client(
        "worker-polling-unsaved-entry",
        _accepted_health_response("ready"),
    )
    setup_worker_health_polling(hass_a, entry_a, now=BASE_TIME)
    unsaved_state = get_worker_health_polling_state(hass_a, entry_a.entry_id)

    hass_b, entry_b, _client_b, _provision_b, _health_setup_b = _ready_hass_with_fake_health_client(
        "worker-polling-persisted-entry",
        _accepted_health_response("ready"),
    )
    setup_worker_health_polling(hass_b, entry_b, now=BASE_TIME)
    persisted_state = get_worker_health_polling_state(hass_b, entry_b.entry_id)

    cadence_hass, cadence_entry, _cadence_client, _cadence_provision, _cadence_setup = (
        _ready_hass_with_fake_health_client(
            "worker-polling-invalid-cadence-source-entry",
            _accepted_health_response("ready"),
        )
    )
    setup_worker_health_polling(cadence_hass, cadence_entry, now=BASE_TIME)
    run_worker_health_poll(cadence_hass, cadence_entry.entry_id, now=BASE_TIME)
    invalid_cadence_state = get_worker_health_polling_state(cadence_hass, cadence_entry.entry_id)
    invalid_cadence_state["polling_id"] = "worker-polling-invalid-cadence-entry-worker-health-polling-001"
    invalid_cadence_state["config_entry_id"] = "worker-polling-invalid-cadence-entry"
    invalid_cadence_state["scheduler"]["next_poll_not_before"] = (
        BASE_TIME + timedelta(days=2)
    ).isoformat()

    token_missing_entry = _worker_entry("worker-polling-token-missing-entry")
    token_missing_hass = _setup_readiness_hass(token_missing_entry)
    provision = provision_integration_worker_token(
        token_missing_hass,
        token_missing_entry.entry_id,
        token_factory=CountingTokenFactory(WORKER_READINESS_TEST_TOKEN),
    )
    if not provision["accepted"]:
        raise AssertionError(f"Token provisioning failed for {token_missing_entry.entry_id}: {provision!r}")
    _entry_data(token_missing_hass, token_missing_entry.entry_id)[DATA_WORKER_RENDER_CLIENT] = FakeWorkerHealthClient(
        endpoint_url=WORKER_ENDPOINT_URL,
        worker_token="short",
        response=_accepted_health_response("ready"),
    )
    setup_worker_health_polling(token_missing_hass, token_missing_entry, now=BASE_TIME)
    token_missing_state = get_worker_health_polling_state(token_missing_hass, token_missing_entry.entry_id)

    invalid_bounds_state = deepcopy(persisted_state)
    invalid_bounds_state["polling_id"] = "worker-polling-invalid-bounds-entry-worker-health-polling-001"
    invalid_bounds_state["config_entry_id"] = "worker-polling-invalid-bounds-entry"
    invalid_bounds_state["scheduler"]["backoff_seconds"] = 901

    ha_store = FakeHomeAssistantPollingStore(
        {
            "version": 1,
            "entries": {
                entry_b.entry_id: persisted_state,
                token_missing_entry.entry_id: token_missing_state,
                "worker-polling-invalid-persisted-entry": {
                    "type": "not_a_valid_polling_state",
                    "config_entry_id": "worker-polling-invalid-persisted-entry",
                },
                "worker-polling-invalid-bounds-entry": invalid_bounds_state,
                "worker-polling-invalid-cadence-entry": invalid_cadence_state,
            },
        }
    )
    store = WorkerHealthPollingStorageHelper(ha_store=ha_store)
    store.write_state(entry_a.entry_id, unsaved_state)
    before_load = store.summary()
    after_load = _run(store.async_load())
    state_a_after_load = store.read_state(entry_a.entry_id)
    state_b_after_load = store.read_state(entry_b.entry_id)
    token_missing_state_after_load = store.read_state(token_missing_entry.entry_id)
    store.delete_state(entry_a.entry_id)
    ha_store.loaded_data["entries"][entry_a.entry_id] = unsaved_state
    after_unloaded_load = _run(store.async_load())
    return {
        "before_load": before_load,
        "after_load": after_load,
        "after_unloaded_load": after_unloaded_load,
        "unsaved_entry_present": entry_a.entry_id in after_load["entry_ids"],
        "persisted_entry_present": entry_b.entry_id in after_load["entry_ids"],
        "token_missing_entry_loaded": token_missing_entry.entry_id in after_load["entry_ids"],
        "invalid_entry_absent": "worker-polling-invalid-persisted-entry" not in after_load["entry_ids"],
        "invalid_bounds_entry_absent": "worker-polling-invalid-bounds-entry" not in after_load["entry_ids"],
        "invalid_cadence_entry_absent": "worker-polling-invalid-cadence-entry"
        not in after_load["entry_ids"],
        "unloaded_entry_not_remerged": entry_a.entry_id not in after_unloaded_load["entry_ids"],
        "persisted_entry_still_present_after_unloaded_load": entry_b.entry_id
        in after_unloaded_load["entry_ids"],
        "unsaved_state_preserved": state_a_after_load == unsaved_state,
        "persisted_state_loaded": state_b_after_load == persisted_state,
        "token_missing_state_loaded": token_missing_state_after_load == token_missing_state,
        "unloaded_state_not_loaded": store.read_state(entry_a.entry_id) is None,
        "invalid_state_not_loaded": store.read_state("worker-polling-invalid-persisted-entry") is None,
        "invalid_bounds_state_not_loaded": store.read_state("worker-polling-invalid-bounds-entry") is None,
        "invalid_cadence_state_not_loaded": store.read_state("worker-polling-invalid-cadence-entry") is None,
        "state_a_validation": _validate_polling_state(state_a_after_load, root),
        "state_b_validation": _validate_polling_state(state_b_after_load, root),
        "token_missing_validation": _validate_polling_state(token_missing_state_after_load, root),
        "save_delay_seconds": ha_store.save_delays[-1],
    }


def verify_setup_resumes_persisted_polling_cadence(root=None) -> dict[str, Any]:
    root = root or repo_root()
    source_hass, source_entry, source_client, _provision, _setup = _ready_hass_with_fake_health_client(
        "worker-polling-resume-entry",
        _accepted_health_response("not_ready", rendering=False),
    )
    setup_worker_health_polling(source_hass, source_entry, now=BASE_TIME)
    run_worker_health_poll(source_hass, source_entry.entry_id, now=BASE_TIME)
    run_worker_health_poll(source_hass, source_entry.entry_id, now=SECOND_TIME)
    persisted_state = get_worker_health_polling_state(source_hass, source_entry.entry_id)

    resumed_hass, resumed_entry, resumed_client, _resumed_provision, _resumed_health_setup = (
        _ready_hass_with_fake_health_client(
            source_entry.entry_id,
            _accepted_health_response("ready"),
        )
    )
    ha_store = FakeHomeAssistantPollingStore(
        {
            "version": 1,
            "entries": {
                source_entry.entry_id: persisted_state,
            },
        }
    )
    resumed_hass.data[DOMAIN][DATA_WORKER_HEALTH_POLLING_STORE] = WorkerHealthPollingStorageHelper(
        ha_store=ha_store
    )
    scheduler = FakePollingScheduler().install(resumed_hass, executor=True)
    resume_time = BASE_TIME + timedelta(seconds=90)
    setup = _run(async_setup_worker_health_polling(resumed_hass, resumed_entry, now=resume_time))
    resumed_state = get_worker_health_polling_state(resumed_hass, resumed_entry.entry_id)
    setup_timer = deepcopy(_entry_data(resumed_hass, resumed_entry.entry_id).get(DATA_WORKER_HEALTH_POLLING_TIMER))

    return {
        "setup": _polling_setup_summary(setup),
        "source_health_call_count": source_client.health_calls,
        "resumed_health_call_count": resumed_client.health_calls,
        "state": _polling_state_summary(resumed_state),
        "state_validation": _validate_polling_state(resumed_state, root),
        "setup_timer": setup_timer,
        "scheduler": scheduler.summary(),
        "persisted_next_poll_not_before": persisted_state["scheduler"]["next_poll_not_before"],
        "resumed_next_poll_not_before": resumed_state["scheduler"]["next_poll_not_before"],
        "cadence_preserved": resumed_state["scheduler"]["next_poll_not_before"]
        == persisted_state["scheduler"]["next_poll_not_before"],
        "consecutive_failures_preserved": resumed_state["scheduler"]["consecutive_failures"]
        == persisted_state["scheduler"]["consecutive_failures"],
        "backoff_seconds_preserved": resumed_state["scheduler"]["backoff_seconds"]
        == persisted_state["scheduler"]["backoff_seconds"],
    }


def verify_unload_races_do_not_resurrect_polling_state(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, _client, _provision, _health_setup = _ready_hass_with_fake_health_client(
        "worker-polling-unload-race-entry",
        _accepted_health_response("ready"),
    )
    client = UnloadingWorkerHealthClient(
        hass=hass,
        entry_id=entry.entry_id,
        endpoint_url=WORKER_ENDPOINT_URL,
        worker_token=WORKER_READINESS_TEST_TOKEN,
        response=_accepted_health_response("ready"),
    )
    _entry_data(hass, entry.entry_id)[DATA_WORKER_RENDER_CLIENT] = client
    setup_worker_health_polling(hass, entry, now=BASE_TIME)
    result = run_worker_health_poll(hass, entry.entry_id, now=BASE_TIME)
    state = get_worker_health_polling_state(hass, entry.entry_id)
    return {
        "result": _polling_result_summary(result),
        "state_after_poll": state,
        "state_absent_after_poll": state is None,
        "entry_data_absent_after_poll": entry.entry_id not in hass.data.get(DOMAIN, {}),
        "health_call_count": client.health_calls,
        "storage": get_worker_health_polling_storage(hass).summary(),
    }


def verify_in_flight_poll_does_not_write_after_same_entry_reload(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, _client, _provision, _health_setup = _ready_hass_with_fake_health_client(
        "worker-polling-reload-race-entry",
        _accepted_health_response("ready"),
    )
    client = ReloadingWorkerHealthClient(
        hass=hass,
        entry_id=entry.entry_id,
        endpoint_url=WORKER_ENDPOINT_URL,
        worker_token=WORKER_READINESS_TEST_TOKEN,
        response=_accepted_health_response("ready"),
    )
    _entry_data(hass, entry.entry_id)[DATA_WORKER_RENDER_CLIENT] = client
    setup_worker_health_polling(hass, entry, now=BASE_TIME)
    result = run_worker_health_poll(hass, entry.entry_id, now=BASE_TIME)
    state = get_worker_health_polling_state(hass, entry.entry_id)
    entry_data = _entry_data(hass, entry.entry_id)

    return {
        "result": _polling_result_summary(result),
        "state": _polling_state_summary(state),
        "state_validation": _validate_polling_state(state, root),
        "old_health_call_count": client.health_calls,
        "reloaded_health_call_count": (
            client.reloaded_client.health_calls if client.reloaded_client is not None else None
        ),
        "new_entry_is_current": entry_data.get("entry") is client.reloaded_entry,
        "old_worker_health_absent_from_reloaded_entry": "worker_health" not in entry_data,
        "stale_ready_state_absent": state["status"] == "scheduled",
        "stale_old_token_absent": WORKER_READINESS_TEST_TOKEN not in str(entry_data),
        "new_token_present_only_in_worker_client": (
            client.reloaded_client is not None
            and client.reloaded_client.worker_token == WORKER_READINESS_SECOND_TOKEN
        ),
        "storage": get_worker_health_polling_storage(hass).summary(),
    }


def verify_in_flight_poll_clears_after_worker_context_change(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, _client, _provision, _health_setup = _ready_hass_with_fake_health_client(
        "worker-polling-context-change-entry",
        _accepted_health_response("ready"),
    )
    client = RotatingWorkerHealthClient(
        hass=hass,
        entry_id=entry.entry_id,
        endpoint_url=WORKER_ENDPOINT_URL,
        worker_token=WORKER_READINESS_TEST_TOKEN,
        response=_accepted_health_response("ready"),
    )
    _entry_data(hass, entry.entry_id)[DATA_WORKER_RENDER_CLIENT] = client
    setup_worker_health_polling(hass, entry, now=BASE_TIME)
    result = run_worker_health_poll(hass, entry.entry_id, now=BASE_TIME)
    state_after_context_change = get_worker_health_polling_state(hass, entry.entry_id)
    follow_up_result = run_worker_health_poll(hass, entry.entry_id, now=BASE_TIME)
    state_after_follow_up = get_worker_health_polling_state(hass, entry.entry_id)

    return {
        "result": _polling_result_summary(result),
        "state_after_context_change": _polling_state_summary(state_after_context_change),
        "context_state_validation": _validate_polling_state(state_after_context_change, root),
        "follow_up_result": _polling_result_summary(follow_up_result),
        "state_after_follow_up": _polling_state_summary(state_after_follow_up),
        "follow_up_state_validation": _validate_polling_state(state_after_follow_up, root),
        "old_health_call_count": client.health_calls,
        "replacement_health_call_count": (
            client.replacement_client.health_calls if client.replacement_client is not None else None
        ),
        "rotation_accepted": (
            isinstance(client.rotation_result, dict)
            and client.rotation_result.get("accepted") is True
        ),
        "in_flight_cleared": state_after_context_change["scheduler"]["poll_in_flight"] is False,
        "follow_up_poll_accepted": follow_up_result["accepted"] is True,
        "follow_up_used_replacement_client": (
            client.replacement_client is not None
            and client.replacement_client.health_calls == 1
        ),
        "storage": get_worker_health_polling_storage(hass).summary(),
    }


def verify_worker_health_polling_details_do_not_leak_to_card(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, client, _provision, _health_setup = _ready_hass_with_fake_health_client(
        "worker-polling-leak-entry",
        _accepted_health_response("ready", message=f"Bearer {WORKER_READINESS_TEST_TOKEN} should not leak"),
    )
    setup = setup_worker_health_polling(hass, entry, now=BASE_TIME)
    result = run_worker_health_poll(hass, entry.entry_id, now=BASE_TIME)
    state = get_worker_health_polling_state(hass, entry.entry_id)

    endpoint_hass, endpoint_entry, _endpoint_client, _endpoint_provision, _endpoint_setup = _ready_hass_with_fake_health_client(
        "worker-polling-endpoint-message-entry",
        _accepted_health_response("ready", message=f"Worker ready at {WORKER_ENDPOINT_URL}"),
    )
    setup_worker_health_polling(endpoint_hass, endpoint_entry, now=BASE_TIME)
    endpoint_result = run_worker_health_poll(endpoint_hass, endpoint_entry.entry_id, now=BASE_TIME)
    endpoint_state = get_worker_health_polling_state(endpoint_hass, endpoint_entry.entry_id)

    endpoint_code_response = _accepted_health_response("ready")
    endpoint_code_response["health_result"]["code"] = f"{WORKER_ENDPOINT_URL}/v1/health"
    endpoint_code_hass, endpoint_code_entry, _endpoint_code_client, _endpoint_code_provision, _endpoint_code_setup = _ready_hass_with_fake_health_client(
        "worker-polling-endpoint-code-entry",
        endpoint_code_response,
    )
    setup_worker_health_polling(endpoint_code_hass, endpoint_code_entry, now=BASE_TIME)
    endpoint_code_result = run_worker_health_poll(
        endpoint_code_hass,
        endpoint_code_entry.entry_id,
        now=BASE_TIME,
    )
    endpoint_code_state = get_worker_health_polling_state(endpoint_code_hass, endpoint_code_entry.entry_id)

    bare_token_response = _accepted_health_response("ready", message=WORKER_READINESS_TEST_TOKEN)
    bare_token_response["health_result"]["code"] = WORKER_READINESS_TEST_TOKEN
    bare_token_hass, bare_token_entry, _bare_token_client, _bare_token_provision, _bare_token_setup = _ready_hass_with_fake_health_client(
        "worker-polling-bare-token-message-entry",
        bare_token_response,
    )
    setup_worker_health_polling(bare_token_hass, bare_token_entry, now=BASE_TIME)
    bare_token_result = run_worker_health_poll(bare_token_hass, bare_token_entry.entry_id, now=BASE_TIME)
    bare_token_state = get_worker_health_polling_state(bare_token_hass, bare_token_entry.entry_id)

    entry_data = _entry_data(hass, entry.entry_id)
    dashboard_metadata = entry_data["websocket_api"]
    model_provider_metadata = entry_data["model_provider_setup"]
    dashboard_visible_payload = {
        "websocket_api": dashboard_metadata,
        "card_snapshot_payload": {
            "accepted": True,
            "code": "no_card_polling_command",
            "worker_health_polling": None,
        },
    }
    evidence_payload = {
        "setup": _polling_setup_summary(setup),
        "result": _polling_result_summary(result),
        "polling_state": _polling_state_summary(state),
    }
    state_text = str(state)
    endpoint_state_text = str(endpoint_state)
    endpoint_code_state_text = str(endpoint_code_state)
    bare_token_state_text = str(bare_token_state)
    endpoint_evidence_payload = {
        "result": _polling_result_summary(endpoint_result),
        "polling_state": _polling_state_summary(endpoint_state),
    }
    bare_token_evidence_payload = {
        "result": _polling_result_summary(bare_token_result),
        "polling_state": _polling_state_summary(bare_token_state),
    }
    endpoint_code_evidence_payload = {
        "result": _polling_result_summary(endpoint_code_result),
        "polling_state": _polling_state_summary(endpoint_code_state),
    }
    dashboard_text = str(dashboard_visible_payload)
    return {
        "state_validation": _validate_polling_state(state, root),
        "endpoint_message_state_validation": _validate_polling_state(endpoint_state, root),
        "raw_worker_authorization_received": client.received_health_requests[0]["headers"]["authorization"].startswith(
            "Bearer "
        ),
        "token_absent_from_polling_state": WORKER_READINESS_TEST_TOKEN not in state_text,
        "token_absent_from_setup": WORKER_READINESS_TEST_TOKEN not in str(setup),
        "token_absent_from_evidence_payload": WORKER_READINESS_TEST_TOKEN not in str(evidence_payload),
        "token_absent_from_dashboard_card_metadata": WORKER_READINESS_TEST_TOKEN not in str(dashboard_metadata),
        "token_absent_from_model_provider_metadata": WORKER_READINESS_TEST_TOKEN not in str(model_provider_metadata),
        "endpoint_absent_from_polling_state": WORKER_ENDPOINT_URL not in state_text,
        "endpoint_message_absent_from_polling_state": WORKER_ENDPOINT_URL not in endpoint_state_text,
        "endpoint_message_url_scheme_absent": "http://" not in endpoint_state["health"]["message"],
        "endpoint_message_absent_from_evidence_payload": WORKER_ENDPOINT_URL not in str(endpoint_evidence_payload),
        "endpoint_code_absent_from_polling_state": "worker.local" not in endpoint_code_state_text,
        "endpoint_code_redacted": endpoint_code_state["code"] == "worker_health_redacted",
        "endpoint_health_code_redacted": endpoint_code_state["health"]["code"] == "worker_health_redacted",
        "endpoint_code_absent_from_evidence_payload": "worker.local" not in str(endpoint_code_evidence_payload),
        "bare_token_absent_from_polling_state": WORKER_READINESS_TEST_TOKEN not in bare_token_state_text,
        "bare_token_absent_from_evidence_payload": WORKER_READINESS_TEST_TOKEN not in str(bare_token_evidence_payload),
        "bare_token_code_redacted": bare_token_state["code"] == "worker_health_redacted",
        "bare_token_health_code_redacted": bare_token_state["health"]["code"] == "worker_health_redacted",
        "bare_token_message_redacted": bare_token_state["health"]["message"]
        == "Worker health endpoint response was sanitized.",
        "authorization_absent_from_polling_state": "Bearer " not in state_text,
        "request_absent_from_polling_state": "headers" not in state_text,
        "response_checks_absent_from_polling_state": "worker_process" not in state_text,
        "endpoint_absent_from_dashboard_payload": WORKER_ENDPOINT_URL not in dashboard_text,
        "polling_absent_from_dashboard_payload": "isolinear_worker_health_polling_state" not in dashboard_text,
        "repair_recommendation_absent_from_dashboard_payload": "recommendation" not in dashboard_text,
    }


def verify_worker_health_polling_side_effect_boundaries() -> dict[str, Any]:
    setup = verify_setup_enqueues_post_setup_poll_without_worker_call()
    scheduler = verify_home_assistant_timer_schedules_post_setup_and_next_poll()
    ready = verify_scheduled_ready_poll_records_cadence()
    failures = verify_failure_poll_results_use_bounded_backoff()
    blocked = verify_missing_preconditions_block_before_worker_call()
    single_flight = verify_single_flight_guard_prevents_overlapping_poll()
    isolation = verify_worker_health_polling_stays_config_entry_scoped()
    resume = verify_setup_resumes_persisted_polling_cadence()
    reload_race = verify_in_flight_poll_does_not_write_after_same_entry_reload()
    context_change = verify_in_flight_poll_clears_after_worker_context_change()

    observed = [
        {"name": "setup", **setup["setup"]["orchestration"]},
        {"name": "ha_timer_poll", **scheduler["state_after_fire"]["orchestration"]},
        {"name": "ready_poll", **ready["state"]["orchestration"]},
        {"name": "not_ready_poll", **failures["not_ready"]["state"]["orchestration"]},
        {"name": "unavailable_poll", **failures["unavailable"]["state"]["orchestration"]},
        {"name": "blocked_poll", **blocked["state"]["orchestration"]},
        {"name": "single_flight_guard", **single_flight["result"]["orchestration"]},
        {"name": "isolation_entry_a", **isolation["entry_a"]["state"]["orchestration"]},
        {"name": "isolation_entry_b", **isolation["entry_b"]["state"]["orchestration"]},
        {"name": "resume_setup", **resume["setup"]["orchestration"]},
        {"name": "reload_race", **reload_race["result"]["orchestration"]},
        {"name": "context_change", **context_change["state_after_context_change"]["orchestration"]},
    ]
    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in WORKER_HEALTH_POLLING_FORBIDDEN_SIDE_EFFECT_KEYS
    }
    allowed_aggregate = {
        "durable_health_storage_written": any(
            item.get("durable_health_storage_written") for item in observed
        ),
        "scheduler_bookkeeping_written": any(
            item.get("scheduler_bookkeeping_written") for item in observed
        ),
        "post_setup_poll_enqueued": any(item.get("post_setup_poll_enqueued") for item in observed),
        "worker_health_check_called": any(item.get("worker_health_check_called") for item in observed),
        "worker_health_request_validated": any(
            item.get("worker_health_request_validated") for item in observed
        ),
        "worker_health_response_validated": any(
            item.get("worker_health_response_validated") for item in observed
        ),
        "single_flight_guard_checked": any(
            item.get("single_flight_guard_checked") for item in observed
        ),
    }
    return {
        "expected_forbidden": {
            key: False for key in WORKER_HEALTH_POLLING_FORBIDDEN_SIDE_EFFECT_KEYS
        },
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }


def verify_worker_health_polling_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_worker_health_polling_files(root)
    setup = verify_setup_enqueues_post_setup_poll_without_worker_call(root)
    scheduler = verify_home_assistant_timer_schedules_post_setup_and_next_poll(root)
    ready = verify_scheduled_ready_poll_records_cadence(root)
    timing = verify_next_poll_timing_blocks_early_duplicate_polls(root)
    failures = verify_failure_poll_results_use_bounded_backoff(root)
    blocked = verify_missing_preconditions_block_before_worker_call(root)
    single_flight = verify_single_flight_guard_prevents_overlapping_poll(root)
    unload = verify_unload_removes_durable_polling_state(root)
    isolation = verify_worker_health_polling_stays_config_entry_scoped(root)
    storage_merge = verify_storage_load_merges_persisted_entries_without_dropping_unsaved(root)
    resume = verify_setup_resumes_persisted_polling_cadence(root)
    unload_race = verify_unload_races_do_not_resurrect_polling_state(root)
    reload_race = verify_in_flight_poll_does_not_write_after_same_entry_reload(root)
    context_change = verify_in_flight_poll_clears_after_worker_context_change(root)
    leakage = verify_worker_health_polling_details_do_not_leak_to_card(root)
    side_effects = verify_worker_health_polling_side_effect_boundaries()

    failure_messages = []
    if not files["all_files_present"]:
        failure_messages.append("One or more worker health polling scaffold files are missing.")
    if setup["state"]["status"] != "scheduled" or setup["health_call_count"] != 0:
        failure_messages.append("Setup did not enqueue polling without a worker call.")
    if not setup["state_validation"]["accepted"]:
        failure_messages.append("Setup polling state did not validate.")
    if (
        scheduler["health_calls_after_setup"] != 0
        or scheduler["setup_timer"]["registered"] is not True
        or scheduler["setup_timer"]["delay_seconds"] != 0
        or scheduler["state_after_fire"]["status"] != "ready"
        or scheduler["health_call_count"] != 1
        or scheduler["created_task_count"] != 1
        or scheduler["executor_job_count"] != 1
        or scheduler["next_timer"]["registered"] is not True
        or scheduler["next_timer"]["delay_seconds"] != READY_POLL_CADENCE_SECONDS
        or scheduler["unload"]["cancelled_scheduled_poll"] is not True
        or not scheduler["timer_absent_after_unload"]
    ):
        failure_messages.append("Home Assistant timer did not run the post-setup poll and schedule the next poll.")
    if ready["state"]["status"] != "ready" or ready["next_poll_delay_seconds"] != READY_POLL_CADENCE_SECONDS:
        failure_messages.append("Ready poll did not store ready state with 300 second cadence.")
    if ready["state"]["scheduler"]["consecutive_failures"] != 0:
        failure_messages.append("Ready poll did not reset consecutive failures.")
    if ready["explicit_health_state_written"] or ready["worker_health_setup_code"] != "worker_health_probe_available":
        failure_messages.append("Scheduled poll wrote explicit worker health state.")
    if timing["ready"]["early_result"]["code"] != "worker_health_poll_not_due":
        failure_messages.append("Ready poll did not block an early duplicate poll.")
    if timing["ready"]["health_call_count"] != 1:
        failure_messages.append("Ready early duplicate poll called the worker.")
    if (
        timing["ready"]["lost_precondition_result"]["code"] != "worker_health_polling_blocked"
        or timing["ready"]["lost_precondition_state"]["status"] != "blocked"
        or timing["ready"]["lost_precondition_state"]["orchestration"]["worker_health_check_called"]
    ):
        failure_messages.append("Ready poll did not revalidate preconditions before the not-due shortcut.")
    if timing["not_ready"]["early_result"]["code"] != "worker_health_poll_not_due":
        failure_messages.append("Not-ready poll did not block an early duplicate poll.")
    if timing["not_ready"]["health_call_count"] != 1 or timing["not_ready"]["consecutive_failures"] != 1:
        failure_messages.append("Not-ready early duplicate poll advanced failure state.")
    if not failures["not_ready"]["state_validation"]["accepted"] or not failures["unavailable"]["state_validation"]["accepted"]:
        failure_messages.append("Failure polling states did not validate.")
    if failures["not_ready"]["state"]["scheduler"]["backoff_seconds"] != 60:
        failure_messages.append("Repeated not-ready poll did not advance to 60 second backoff.")
    if failures["unavailable"]["state"]["scheduler"]["backoff_seconds"] != 30:
        failure_messages.append("Unavailable poll did not start at 30 second backoff.")
    if blocked["state"]["status"] != "blocked" or blocked["worker_client_present"]:
        failure_messages.append("Blocked preconditions did not stop before worker client setup.")
    if single_flight["result"]["code"] != "worker_health_poll_already_in_flight":
        failure_messages.append("Single-flight guard did not reject overlapping poll.")
    if single_flight["health_call_count"] != 0:
        failure_messages.append("Single-flight guard allowed a worker health call.")
    if single_flight["normal_poll"]["poll_in_flight_during_health_call"] is not True:
        failure_messages.append("Normal poll did not mark in-flight before the worker health call.")
    if single_flight["normal_poll"]["poll_in_flight_after_poll"] is not False:
        failure_messages.append("Normal poll did not clear in-flight state after the worker health call.")
    if unload["entry_a_state"] is not None or "worker-polling-unload-entry-a" in unload["after_unload"]["entry_ids"]:
        failure_messages.append("Unload did not remove entry A durable polling state.")
    if "worker-polling-unload-entry-b" not in unload["after_unload"]["entry_ids"]:
        failure_messages.append("Unload removed unrelated polling state.")
    if isolation["entry_a"]["state"]["config_entry_id"] == isolation["entry_b"]["state"]["config_entry_id"]:
        failure_messages.append("Polling states did not stay config-entry scoped.")
    if not isolation["entry_a"]["other_token_absent_from_request"] or not isolation["entry_b"]["other_token_absent_from_request"]:
        failure_messages.append("A polling health request included another entry's token.")
    if (
        not storage_merge["unsaved_entry_present"]
        or not storage_merge["persisted_entry_present"]
        or not storage_merge["token_missing_entry_loaded"]
        or not storage_merge["invalid_entry_absent"]
        or not storage_merge["invalid_bounds_entry_absent"]
        or not storage_merge["invalid_cadence_entry_absent"]
        or not storage_merge["unloaded_entry_not_remerged"]
    ):
        failure_messages.append("Storage load did not merge persisted and unsaved polling entries.")
    if (
        not storage_merge["unsaved_state_preserved"]
        or not storage_merge["persisted_state_loaded"]
        or not storage_merge["token_missing_state_loaded"]
        or not storage_merge["invalid_state_not_loaded"]
        or not storage_merge["invalid_bounds_state_not_loaded"]
        or not storage_merge["invalid_cadence_state_not_loaded"]
        or not storage_merge["unloaded_state_not_loaded"]
    ):
        failure_messages.append("Storage load replaced or corrupted polling entries.")
    if (
        not resume["state_validation"]["accepted"]
        or not resume["cadence_preserved"]
        or not resume["consecutive_failures_preserved"]
        or not resume["backoff_seconds_preserved"]
        or resume["resumed_health_call_count"] != 0
        or resume["setup_timer"]["delay_seconds"] != 30
    ):
        failure_messages.append("Setup did not resume persisted polling cadence.")
    if (
        unload_race["result"]["code"] != "worker_health_polling_entry_unloaded"
        or not unload_race["state_absent_after_poll"]
        or not unload_race["entry_data_absent_after_poll"]
    ):
        failure_messages.append("In-flight poll completion resurrected unloaded polling state.")
    if (
        reload_race["result"]["code"] != "worker_health_polling_entry_reloaded"
        or reload_race["old_health_call_count"] != 1
        or reload_race["reloaded_health_call_count"] != 0
        or not reload_race["new_entry_is_current"]
        or not reload_race["old_worker_health_absent_from_reloaded_entry"]
        or not reload_race["stale_ready_state_absent"]
        or not reload_race["stale_old_token_absent"]
        or not reload_race["new_token_present_only_in_worker_client"]
    ):
        failure_messages.append("In-flight poll completion wrote stale state after same-entry reload.")
    if (
        context_change["result"]["code"] != "worker_health_polling_context_changed"
        or not context_change["rotation_accepted"]
        or not context_change["in_flight_cleared"]
        or context_change["follow_up_result"]["code"] != "worker_health_ready"
        or not context_change["follow_up_poll_accepted"]
        or not context_change["follow_up_used_replacement_client"]
    ):
        failure_messages.append("In-flight poll completion wedged polling after worker context changed.")
    if not all(
        leakage[key]
        for key in (
            "token_absent_from_polling_state",
            "token_absent_from_setup",
            "token_absent_from_evidence_payload",
            "token_absent_from_dashboard_card_metadata",
            "token_absent_from_model_provider_metadata",
            "endpoint_absent_from_polling_state",
            "endpoint_message_absent_from_polling_state",
            "endpoint_message_url_scheme_absent",
            "endpoint_message_absent_from_evidence_payload",
            "endpoint_code_absent_from_polling_state",
            "endpoint_code_redacted",
            "endpoint_health_code_redacted",
            "endpoint_code_absent_from_evidence_payload",
            "bare_token_absent_from_polling_state",
            "bare_token_absent_from_evidence_payload",
            "bare_token_code_redacted",
            "bare_token_health_code_redacted",
            "bare_token_message_redacted",
            "authorization_absent_from_polling_state",
            "request_absent_from_polling_state",
            "response_checks_absent_from_polling_state",
            "endpoint_absent_from_dashboard_payload",
            "polling_absent_from_dashboard_payload",
            "repair_recommendation_absent_from_dashboard_payload",
        )
    ):
        failure_messages.append("Worker health polling details leaked to durable state or dashboard payloads.")
    if any(side_effects["forbidden_aggregate"].values()):
        failure_messages.append("Worker health polling scaffold reported forbidden side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failure_messages.append("Worker health polling scaffold did not report expected allowed side effects.")

    return {
        "passed": not failure_messages,
        "failures": failure_messages,
        "files": files,
        "setup": setup,
        "scheduler": scheduler,
        "ready": ready,
        "timing": timing,
        "failures_case": failures,
        "blocked": blocked,
        "single_flight": single_flight,
        "unload": unload,
        "isolation": isolation,
        "storage_merge": storage_merge,
        "resume": resume,
        "unload_race": unload_race,
        "reload_race": reload_race,
        "context_change": context_change,
        "leakage": leakage,
        "side_effects": side_effects,
    }


def _make_entry_ready_for_polling(
    hass: Any,
    entry: Any,
    response: dict[str, Any],
    token: str,
) -> FakeWorkerHealthClient:
    provision = provision_integration_worker_token(
        hass,
        entry.entry_id,
        token_factory=CountingTokenFactory(token),
    )
    if not provision["accepted"]:
        raise AssertionError(f"Token provisioning failed for {entry.entry_id}: {provision!r}")
    client = FakeWorkerHealthClient(
        endpoint_url=WORKER_ENDPOINT_URL,
        worker_token=token,
        response=response,
    )
    _entry_data(hass, entry.entry_id)[DATA_WORKER_RENDER_CLIENT] = client
    return client


def _polling_setup_summary(setup: dict[str, Any]) -> dict[str, Any]:
    return {
        "accepted": setup["accepted"],
        "code": setup["code"],
        "entry_id": setup["entry_id"],
        "enabled": setup["enabled"],
        "orchestration": deepcopy(setup["orchestration"]),
        "polling_state": _polling_state_summary(setup["polling_state"]),
    }


def _polling_result_summary(result: dict[str, Any]) -> dict[str, Any]:
    orchestration = result.get("orchestration")
    if orchestration is None and isinstance(result.get("polling_state"), dict):
        orchestration = result["polling_state"].get("orchestration")
    summary = {
        "accepted": result["accepted"],
        "code": result["code"],
        "orchestration": deepcopy(orchestration or {}),
    }
    if "polling_state" in result:
        summary["polling_state"] = _polling_state_summary(result["polling_state"])
    return summary


def _polling_state_summary(state: dict[str, Any] | None) -> dict[str, Any] | None:
    if state is None:
        return None
    return {
        "polling_id": state["polling_id"],
        "type": state["type"],
        "version": state["version"],
        "config_entry_id": state["config_entry_id"],
        "status": state["status"],
        "code": state["code"],
        "health": deepcopy(state["health"]),
        "scheduler": deepcopy(state["scheduler"]),
        "repair": deepcopy(state["repair"]),
        "storage": deepcopy(state["storage"]),
        "validation": deepcopy(state["validation"]),
        "warnings": list(state["warnings"]),
        "orchestration": deepcopy(state["orchestration"]),
    }


def _validate_polling_state(state: dict[str, Any] | None, root) -> dict[str, Any]:
    if state is None:
        return {
            "accepted": False,
            "code": "missing_polling_state",
        }
    try:
        validate_contract("integration-worker-health-polling-state", state, repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "contract_validation_failed",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "polling_id": state["polling_id"],
        "config_entry_id": state["config_entry_id"],
        "status": state["status"],
        "next_poll_not_before": state["scheduler"]["next_poll_not_before"],
        "backoff_seconds": state["scheduler"]["backoff_seconds"],
    }


def _seconds_between(start: str, end: str) -> int:
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    return int((end_dt - start_dt).total_seconds())
