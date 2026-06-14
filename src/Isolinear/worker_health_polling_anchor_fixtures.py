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
    "custom_components/isolinear/worker_health_polling_constants.py",
    "custom_components/isolinear/worker_health_polling_contract.py",
    "custom_components/isolinear/worker_health_polling_storage.py",
    "custom_components/isolinear/worker_health_polling_state.py",
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
    "src/Isolinear/worker_health_polling_anchor_fixtures.py",
    "src/Isolinear/worker_health_polling_anchor_cases.py",
    "src/Isolinear/worker_health_polling_anchor_verifier.py",
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

__all__ = [name for name in globals() if not name.startswith("__")]
