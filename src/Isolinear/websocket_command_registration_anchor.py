from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from custom_components.isolinear import async_setup_entry
from custom_components.isolinear.const import (
    CONFIG_ENTRY_AUTO,
    DATA_WEBSOCKET_COMMANDS,
    DOMAIN,
    INTEGRATION_COMMAND_TYPES,
    INTEGRATION_WS_NAMESPACE,
    INTEGRATION_WS_VERSION,
)
from custom_components.isolinear.dashboard_resource import (
    CARD_RESOURCE_TYPE,
    CARD_RESOURCE_URL,
)
from custom_components.isolinear.websocket_api import (
    DATA_WEBSOCKET_API_MODULE,
    DATA_WEBSOCKET_OBSERVABILITY,
    DATA_WEBSOCKET_REGISTRATION,
    NO_WEBSOCKET_ORCHESTRATION_CALLS,
    async_register_websocket_api,
    handle_registered_ws_command,
    invalid_command_examples,
    websocket_registration_side_effects,
)

from .contracts import ContractValidationError, validate_contract
from .dashboard_card_anchor import repo_root
from .transport_auth_anchor import sample_integration_ws_commands


WEBSOCKET_REGISTRATION_FILES = [
    "custom_components/isolinear/websocket_api.py",
    "custom_components/isolinear/__init__.py",
    "docs/schemas/integration-ws-command.schema.json",
    "docs/schemas/integration-job-snapshot.schema.json",
]


@dataclass
class FakeConfigEntry:
    entry_id: str = "fake-config-entry"
    domain: str = DOMAIN


class FakeConfigEntries:
    def __init__(self, entry_ids: list[str]) -> None:
        self._entries = [FakeConfigEntry(entry_id) for entry_id in entry_ids]

    def async_entries(self, domain: str | None = None) -> list[FakeConfigEntry]:
        if domain is None:
            return list(self._entries)
        return [entry for entry in self._entries if entry.domain == domain]


class FakeConnection:
    def __init__(self) -> None:
        self.results: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []

    def send_result(self, message_id: int | str | None, result: Any) -> None:
        self.results.append({"id": message_id, "result": result})

    def send_error(self, message_id: int | str | None, code: str, message: str) -> None:
        self.errors.append({"id": message_id, "code": code, "message": message})


class FakeWebSocketApiModule:
    def __init__(self) -> None:
        self.registered_handlers: list[Any] = []

    def async_register_command(self, hass: Any, handler: Any) -> None:
        self.registered_handlers.append(handler)

    def dispatch(self, hass: Any, message: dict[str, Any]) -> dict[str, Any]:
        connection = FakeConnection()
        handler = self.handler_for_type(message.get("type"))
        if handler is None:
            connection.send_error(
                message.get("id"),
                "unknown_integration_ws_command",
                "Unknown Isolinear WebSocket command.",
            )
            return {
                "accepted": False,
                "handler_called": False,
                "connection": _connection_payload(connection),
                "orchestration": websocket_registration_side_effects(False),
            }

        handler_result = _run_if_awaitable(handler(hass, connection, message))
        return {
            "accepted": bool(connection.results) and not connection.errors,
            "handler_called": True,
            "handler_result": handler_result,
            "connection": _connection_payload(connection),
            "orchestration": handler_result.get("orchestration", websocket_registration_side_effects(False))
            if isinstance(handler_result, dict)
            else websocket_registration_side_effects(False),
        }

    def handler_for_type(self, command_type: Any) -> Any | None:
        for handler in self.registered_handlers:
            if getattr(handler, "_isolinear_command_type", None) == command_type:
                return handler
        return None


class FakeHttp:
    def __init__(self) -> None:
        self.static_path_calls: list[list[Any]] = []

    async def async_register_static_paths(self, paths: list[Any]) -> None:
        self.static_path_calls.append(paths)


class FakeLovelaceResources:
    def __init__(self) -> None:
        self.loaded = True
        self._items: list[dict[str, Any]] = []
        self.create_calls: list[dict[str, Any]] = []

    def async_items(self) -> list[dict[str, Any]]:
        return list(self._items)

    async def async_create_item(self, data: dict[str, Any]) -> dict[str, Any]:
        self.create_calls.append(dict(data))
        item = {
            "id": f"resource-{len(self._items) + 1:03d}",
            "url": data["url"],
            "type": data.get("type") or data.get("res_type"),
        }
        self._items.append(item)
        return item


class FakeHass:
    def __init__(
        self,
        websocket_api_module: FakeWebSocketApiModule | None = None,
        *,
        include_entry: bool = True,
        registry_entry_ids: list[str] | None = None,
    ) -> None:
        self.data: dict[str, Any] = {
            DOMAIN: {},
            "lovelace": SimpleNamespace(resources=FakeLovelaceResources()),
        }
        self.http = FakeHttp()
        if registry_entry_ids is not None:
            self.config_entries = FakeConfigEntries(registry_entry_ids)
        if websocket_api_module is not None:
            self.data[DOMAIN][DATA_WEBSOCKET_API_MODULE] = websocket_api_module
        if include_entry:
            self.data[DOMAIN]["fake-config-entry"] = {"entry": FakeConfigEntry()}


def verify_websocket_registration_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in WEBSOCKET_REGISTRATION_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_registered_command_names(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = FakeHass(websocket_api_module)
    result = _run(async_register_websocket_api(hass))
    handlers = websocket_api_module.registered_handlers
    registered_types = [
        getattr(handler, "_isolinear_command_type", None)
        for handler in handlers
    ]
    handler_schemas = {
        getattr(handler, "_isolinear_command_type", f"handler-{index}"): getattr(
            handler,
            "_isolinear_command_schema",
            None,
        )
        for index, handler in enumerate(handlers)
    }
    return {
        "accepted": result["accepted"],
        "code": result["code"],
        "namespace": INTEGRATION_WS_NAMESPACE,
        "version": INTEGRATION_WS_VERSION,
        "expected_commands": list(INTEGRATION_COMMAND_TYPES.values()),
        "registered_types": registered_types,
        "registered_count": len(registered_types),
        "registered_via_async_register_command": len(handlers) == len(INTEGRATION_COMMAND_TYPES),
        "handlers_have_command_schema": all(schema is not None for schema in handler_schemas.values()),
        "handler_schemas": handler_schemas,
        "hass_data_commands": hass.data[DOMAIN].get(DATA_WEBSOCKET_COMMANDS),
        "result": result,
        "files": verify_websocket_registration_files(root),
    }


def verify_setup_entry_websocket_registration(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = FakeHass(websocket_api_module, include_entry=False)
    entry = FakeConfigEntry()
    setup_accepted = _run(async_setup_entry(hass, entry))
    entry_data = hass.data[DOMAIN][entry.entry_id]
    registration = entry_data["websocket_api"]
    return {
        "setup_accepted": setup_accepted,
        "entry_id": entry.entry_id,
        "entry_data_keys": sorted(entry_data),
        "registration": registration,
        "config_entry_scoped_result": registration["entry_id"] == entry.entry_id,
        "registered_count": len(websocket_api_module.registered_handlers),
        "dashboard_resource": entry_data["dashboard_resource"],
        "dashboard_resource_expected": {
            "url": CARD_RESOURCE_URL,
            "type": CARD_RESOURCE_TYPE,
        },
        "files": verify_websocket_registration_files(root),
    }


def verify_registered_callback_snapshots(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module, registration = _registered_fake_hass()
    samples = sample_integration_ws_commands()
    start_result = websocket_api_module.dispatch(hass, {"id": 1, **samples["start_job"]})
    start_snapshot = _first_result_payload(start_result)
    job_id = start_snapshot["job_id"] if isinstance(start_snapshot, dict) else "missing-job"
    commands = {
        "start_job": samples["start_job"],
        "answer_clarification": {
            **samples["answer_clarification"],
            "job_id": job_id,
        },
        "retry_job": {
            **samples["retry_job"],
            "job_id": job_id,
        },
        "get_snapshot": {
            **samples["get_snapshot"],
            "job_id": job_id,
        },
        "subscribe_job": {
            **samples["subscribe_job"],
            "job_id": job_id,
        },
    }
    dispatch_results = {}
    snapshot_validation = {}
    for index, (name, command) in enumerate(commands.items(), start=10):
        if name == "start_job":
            result = start_result
        else:
            result = websocket_api_module.dispatch(hass, {"id": index, **command})
        dispatch_results[name] = result
        snapshot = _first_result_payload(result)
        try:
            validate_contract("integration-ws-command", command, repo_root=root)
            validate_contract("integration-job-snapshot", snapshot, repo_root=root)
        except ContractValidationError as exc:
            snapshot_validation[name] = {
                "accepted": False,
                "code": "contract_validation_failed",
                "error": str(exc),
            }
        else:
            snapshot_validation[name] = {
                "accepted": True,
                "code": "accepted",
                "status": snapshot["status"],
                "warnings": snapshot["warnings"],
            }

    return {
        "registration": registration,
        "dispatch_results": dispatch_results,
        "snapshot_validation": snapshot_validation,
    }


def verify_invalid_registered_commands_fail_closed() -> dict[str, Any]:
    hass, websocket_api_module, registration = _registered_fake_hass()
    examples = invalid_command_examples()
    selected = {
        "unknown_command": {"id": 40, **examples["unknown_command"]},
        "wrong_version": {"id": 41, **examples["wrong_version"]},
        "leaky_worker_url": {"id": 42, **examples["leaky_worker_url"]},
        "mutating_service_call": {"id": 43, **examples["mutating_service_call"]},
    }
    dispatch_results = {
        name: websocket_api_module.dispatch(hass, command)
        for name, command in selected.items()
    }
    return {
        "registration": registration,
        "dispatch_results": dispatch_results,
    }


def verify_missing_config_entry_rejection() -> dict[str, Any]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = FakeHass(websocket_api_module, include_entry=False)
    registration = _run(async_register_websocket_api(hass))
    command = sample_integration_ws_commands()["get_snapshot"]
    result = websocket_api_module.dispatch(hass, {"id": 50, **command})
    return {
        "registration": registration,
        "command": command,
        "dispatch_result": result,
    }


def verify_auto_config_entry_resolution() -> dict[str, Any]:
    websocket_api_module = FakeWebSocketApiModule()
    single_hass = FakeHass(websocket_api_module)
    single_command = {
        "id": 51,
        "type": INTEGRATION_COMMAND_TYPES["start_job"],
        "version": INTEGRATION_WS_VERSION,
        "config_entry_id": CONFIG_ENTRY_AUTO,
        "prompt": "Show the family room temperature",
    }
    single_result = handle_registered_ws_command(single_hass, single_command)

    multi_hass = FakeHass(websocket_api_module)
    multi_hass.data[DOMAIN]["second-config-entry"] = {
        "entry": FakeConfigEntry("second-config-entry"),
    }
    multi_result = handle_registered_ws_command(multi_hass, single_command)

    registry_hass = FakeHass(
        websocket_api_module,
        include_entry=False,
        registry_entry_ids=["registry-entry-001"],
    )
    registry_result = handle_registered_ws_command(registry_hass, single_command)

    registry_multi_hass = FakeHass(
        websocket_api_module,
        include_entry=False,
        registry_entry_ids=["registry-entry-001", "registry-entry-002"],
    )
    registry_multi_result = handle_registered_ws_command(registry_multi_hass, single_command)

    return {
        "single_entry": {
            "known_config_entries": ["fake-config-entry"],
            "command": single_command,
            "result": single_result,
        },
        "multiple_entries": {
            "known_config_entries": ["fake-config-entry", "second-config-entry"],
            "command": single_command,
            "result": multi_result,
        },
        "registry_single_entry": {
            "known_config_entries": ["registry-entry-001"],
            "command": single_command,
            "result": registry_result,
        },
        "registry_multiple_entries": {
            "known_config_entries": ["registry-entry-001", "registry-entry-002"],
            "command": single_command,
            "result": registry_multi_result,
        },
    }


def verify_websocket_observability() -> dict[str, Any]:
    hass = FakeHass()
    accepted_command = {
        "id": 52,
        "type": INTEGRATION_COMMAND_TYPES["start_job"],
        "version": INTEGRATION_WS_VERSION,
        "config_entry_id": CONFIG_ENTRY_AUTO,
        "prompt": "Show the family room temperature",
    }
    rejected_command = {
        "id": 53,
        "type": INTEGRATION_COMMAND_TYPES["get_snapshot"],
        "version": INTEGRATION_WS_VERSION,
        "config_entry_id": "missing-config-entry",
        "job_id": "job-001",
    }
    accepted_result = handle_registered_ws_command(hass, accepted_command)
    rejected_result = handle_registered_ws_command(hass, rejected_command)
    events = hass.data[DOMAIN].get(DATA_WEBSOCKET_OBSERVABILITY, [])
    return {
        "accepted_result": accepted_result,
        "rejected_result": rejected_result,
        "events": events,
        "event_count": len(events),
    }


def verify_idempotent_command_registration() -> dict[str, Any]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = FakeHass(websocket_api_module, include_entry=False)
    entry = FakeConfigEntry()
    first_setup = _run(async_setup_entry(hass, entry))
    first_registration = hass.data[DOMAIN][entry.entry_id]["websocket_api"]
    first_count = len(websocket_api_module.registered_handlers)
    second_setup = _run(async_setup_entry(hass, entry))
    second_registration = hass.data[DOMAIN][entry.entry_id]["websocket_api"]
    second_count = len(websocket_api_module.registered_handlers)
    return {
        "first_setup": first_setup,
        "second_setup": second_setup,
        "first_registration": first_registration,
        "second_registration": second_registration,
        "first_count": first_count,
        "second_count": second_count,
        "duplicate_count": second_count - first_count,
        "stored_registration": hass.data[DOMAIN][DATA_WEBSOCKET_REGISTRATION],
    }


def verify_websocket_registration_side_effects() -> dict[str, Any]:
    registered = verify_registered_command_names()["result"]["orchestration"]
    callbacks = verify_registered_callback_snapshots()["dispatch_results"]
    invalid = verify_invalid_registered_commands_fail_closed()["dispatch_results"]
    missing_scope = verify_missing_config_entry_rejection()["dispatch_result"]
    auto_resolution = verify_auto_config_entry_resolution()
    observability = verify_websocket_observability()

    observed = [{"name": "command_registration", **registered}]
    observed.extend(
        {"name": f"accepted_{name}", **result["orchestration"]}
        for name, result in callbacks.items()
    )
    observed.extend(
        {"name": f"invalid_{name}", **result["orchestration"]}
        for name, result in invalid.items()
    )
    observed.append({"name": "missing_config_entry", **missing_scope["orchestration"]})
    observed.append(
        {
            "name": "auto_single_config_entry",
            **auto_resolution["single_entry"]["result"]["orchestration"],
        }
    )
    observed.append(
        {
            "name": "auto_multiple_config_entries",
            **auto_resolution["multiple_entries"]["result"]["orchestration"],
        }
    )
    observed.append(
        {
            "name": "auto_registry_single_config_entry",
            **auto_resolution["registry_single_entry"]["result"]["orchestration"],
        }
    )
    observed.append(
        {
            "name": "auto_registry_multiple_config_entries",
            **auto_resolution["registry_multiple_entries"]["result"]["orchestration"],
        }
    )
    observed.append(
        {
            "name": "observability_accepted_command",
            **observability["accepted_result"]["orchestration"],
        }
    )
    observed.append(
        {
            "name": "observability_rejected_command",
            **observability["rejected_result"]["orchestration"],
        }
    )

    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in NO_WEBSOCKET_ORCHESTRATION_CALLS
    }
    allowed_aggregate = {
        "websocket_command_registered": any(
            item.get("websocket_command_registered") for item in observed
        )
    }
    return {
        "expected_forbidden": dict(NO_WEBSOCKET_ORCHESTRATION_CALLS),
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
        "allowed_side_effects": {
            "websocket_command_registered": True,
            "websocket_decision_observability_recorded": True,
        },
    }


def verify_websocket_command_registration_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_websocket_registration_files(root)
    registration = verify_registered_command_names(root)
    setup_entry = verify_setup_entry_websocket_registration(root)
    callbacks = verify_registered_callback_snapshots(root)
    invalid = verify_invalid_registered_commands_fail_closed()
    missing_scope = verify_missing_config_entry_rejection()
    auto_resolution = verify_auto_config_entry_resolution()
    observability = verify_websocket_observability()
    idempotence = verify_idempotent_command_registration()
    side_effects = verify_websocket_registration_side_effects()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more WebSocket registration anchor files are missing.")
    if not registration["accepted"]:
        failures.append("WebSocket command registration was rejected.")
    if registration["registered_types"] != registration["expected_commands"]:
        failures.append("Registered command names do not match the accepted command set.")
    if not registration["handlers_have_command_schema"]:
        failures.append("One or more registered handlers do not carry a command schema.")
    if not setup_entry["setup_accepted"] or not setup_entry["config_entry_scoped_result"]:
        failures.append("Config entry setup did not store a scoped WebSocket registration result.")
    if not all(item["accepted"] for item in callbacks["snapshot_validation"].values()):
        failures.append("One or more registered callback snapshots failed schema validation.")
    if not all(not item["accepted"] for item in invalid["dispatch_results"].values()):
        failures.append("One or more invalid registered commands were accepted.")
    if missing_scope["dispatch_result"]["accepted"]:
        failures.append("A command for a missing config entry was accepted.")
    if not auto_resolution["single_entry"]["result"]["accepted"]:
        failures.append("The auto config-entry sentinel did not resolve the only configured entry.")
    if auto_resolution["multiple_entries"]["result"]["accepted"]:
        failures.append("The auto config-entry sentinel accepted an ambiguous multi-entry setup.")
    if not auto_resolution["registry_single_entry"]["result"]["accepted"]:
        failures.append("The auto config-entry sentinel did not resolve the registry fallback entry.")
    if auto_resolution["registry_multiple_entries"]["result"]["accepted"]:
        failures.append("The auto config-entry registry fallback accepted an ambiguous setup.")
    if observability["event_count"] != 2:
        failures.append("Registered WebSocket decisions were not recorded for observability.")
    if idempotence["duplicate_count"] != 0:
        failures.append("Repeated setup duplicated WebSocket command registration.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("WebSocket registration reported forbidden orchestration side effects.")
    if not side_effects["allowed_aggregate"]["websocket_command_registered"]:
        failures.append("WebSocket command registration side effect was not reported.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "registration": registration,
        "setup_entry": setup_entry,
        "callbacks": callbacks,
        "invalid": invalid,
        "missing_scope": missing_scope,
        "auto_resolution": auto_resolution,
        "observability": observability,
        "idempotence": idempotence,
        "side_effects": side_effects,
    }


def _registered_fake_hass() -> tuple[FakeHass, FakeWebSocketApiModule, dict[str, Any]]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = FakeHass(websocket_api_module)
    registration = _run(async_register_websocket_api(hass))
    return hass, websocket_api_module, registration


def _connection_payload(connection: FakeConnection) -> dict[str, Any]:
    return {
        "results": list(connection.results),
        "errors": list(connection.errors),
    }


def _first_result_payload(dispatch_result: dict[str, Any]) -> Any:
    results = dispatch_result["connection"]["results"]
    if not results:
        return None
    return results[0]["result"]


def _run(coro):
    return asyncio.run(coro)


def _run_if_awaitable(value):
    if asyncio.iscoroutine(value):
        return _run(value)
    return value
