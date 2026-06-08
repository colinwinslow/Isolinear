"""Versioned WebSocket command registration for the Isolinear integration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .const import (
    DATA_WEBSOCKET_COMMANDS,
    DOMAIN,
    INTEGRATION_COMMAND_TYPES,
    INTEGRATION_WS_VERSION,
)
from .job_orchestration import (
    handle_job_orchestration_start_ws_command,
    has_enabled_job_orchestration,
)
from .job_state import handle_job_state_ws_command


try:  # pragma: no cover - exercised by Home Assistant, not repo tests.
    import voluptuous as vol
    from homeassistant.components import websocket_api
    from homeassistant.core import callback
except ImportError:  # pragma: no cover - deterministic fallback for repo tests.

    class _FallbackVol:
        @staticmethod
        def Required(key: str) -> str:
            return key

    class _FallbackWebSocketApi:
        @staticmethod
        def websocket_command(schema: dict[Any, Any]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                func._isolinear_command_schema = schema
                return func

            return decorator

        @staticmethod
        def async_register_command(hass: Any, handler: Callable[..., Any]) -> None:
            domain_data = hass.data.setdefault(DOMAIN, {})
            domain_data.setdefault("_fallback_websocket_handlers", []).append(handler)

    def callback(func: Callable[..., Any]) -> Callable[..., Any]:
        return func

    vol = _FallbackVol()
    websocket_api = _FallbackWebSocketApi()


FORBIDDEN_CARD_KEYS = {
    "access_token",
    "call_service",
    "domain",
    "entity_allowlist",
    "generated_code",
    "generated_image",
    "ha_token",
    "home_assistant_token",
    "long_lived_access_token",
    "model_endpoint",
    "model_url",
    "raw_history",
    "semantic_memory",
    "service",
    "service_data",
    "target",
    "worker_token",
    "worker_url",
}

REQUIRED_COMMAND_FIELDS = {
    INTEGRATION_COMMAND_TYPES["start_job"]: {"type", "version", "config_entry_id", "prompt"},
    INTEGRATION_COMMAND_TYPES["answer_clarification"]: {
        "type",
        "version",
        "config_entry_id",
        "job_id",
        "question_id",
        "option_id",
        "remember",
    },
    INTEGRATION_COMMAND_TYPES["retry_job"]: {"type", "version", "config_entry_id", "job_id"},
    INTEGRATION_COMMAND_TYPES["get_snapshot"]: {"type", "version", "config_entry_id", "job_id"},
    INTEGRATION_COMMAND_TYPES["subscribe_job"]: {"type", "version", "config_entry_id", "job_id"},
}

STRING_COMMAND_FIELDS = {
    "type",
    "config_entry_id",
    "prompt",
    "job_id",
    "question_id",
    "option_id",
}

DATA_WEBSOCKET_API_MODULE = "_websocket_api_module"
DATA_WEBSOCKET_REGISTRATION = "websocket_registration"

NO_ORCHESTRATION_CALLS = {
    "worker_called": False,
    "model_provider_called": False,
    "home_assistant_history_called": False,
    "semantic_memory_called": False,
    "home_assistant_mutation_called": False,
}

NO_WEBSOCKET_ORCHESTRATION_CALLS = {
    "worker_called": False,
    "model_provider_called": False,
    "home_assistant_history_called": False,
    "semantic_memory_called": False,
    "home_assistant_service_or_state_mutation_called": False,
    "token_generated": False,
    "job_orchestration_called": False,
    "dashboard_resource_metadata_written_or_reused": False,
}

ERROR_MESSAGES = {
    "forbidden_card_boundary_content": "The command included content that cannot cross the card boundary.",
    "invalid_integration_job_snapshot": "The Isolinear job snapshot failed schema validation.",
    "invalid_integration_ws_command": "The Isolinear WebSocket command payload is invalid.",
    "unknown_job": "The requested Isolinear job was not found for this config entry.",
    "unknown_config_entry": "The Isolinear config entry was not found for this command.",
    "unknown_integration_ws_command": "Unknown Isolinear WebSocket command.",
    "unsupported_integration_ws_version": "Unsupported Isolinear WebSocket command version.",
}


async def async_register_websocket_api(
    hass: Any,
    *,
    entry: Any | None = None,
    websocket_api_module: Any | None = None,
) -> dict[str, Any]:
    """Register Isolinear WebSocket command handlers with Home Assistant."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    entry_id = getattr(entry, "entry_id", None)
    existing = domain_data.get(DATA_WEBSOCKET_REGISTRATION)
    if existing is not None:
        return {
            **existing,
            "code": "websocket_commands_already_registered",
            "entry_id": entry_id,
            "config_entry_scoped": entry_id is not None,
            "call_made": False,
            "orchestration": websocket_registration_side_effects(False),
        }

    api = websocket_api_module or domain_data.get(DATA_WEBSOCKET_API_MODULE) or websocket_api
    commands = list(INTEGRATION_COMMAND_TYPES.values())
    handlers = list(registered_websocket_handlers())
    for handler in handlers:
        api.async_register_command(hass, handler)

    registration = {
        "accepted": True,
        "code": "websocket_commands_registered",
        "registered": True,
        "mode": "home_assistant_websocket",
        "commands": commands,
        "handler_count": len(handlers),
        "handlers": [handler.__name__ for handler in handlers],
        "entry_id": entry_id,
        "config_entry_scoped": entry_id is not None,
        "call_made": True,
        "orchestration": websocket_registration_side_effects(True),
    }
    domain_data[DATA_WEBSOCKET_COMMANDS] = commands
    domain_data[DATA_WEBSOCKET_REGISTRATION] = registration
    return registration


def registered_websocket_handlers() -> tuple[Callable[..., Any], ...]:
    """Return the Home Assistant WebSocket handlers for the command set."""
    return REGISTERED_WS_HANDLERS


def handle_registered_ws_command(
    hass: Any,
    message: dict[str, Any],
) -> dict[str, Any]:
    """Validate a Home Assistant WebSocket message and build a response result."""
    message_id = message.get("id") if isinstance(message, dict) else None
    command = command_payload_from_ws_message(message)
    result = handle_scaffold_ws_command(command)
    if not result["accepted"]:
        return _registered_rejection(result["code"])

    scope = validate_config_entry_scope(hass, command["config_entry_id"])
    if not scope["accepted"]:
        return _registered_rejection(scope["code"], config_entry_id=command["config_entry_id"])

    if (
        command["type"] == INTEGRATION_COMMAND_TYPES["start_job"]
        and has_enabled_job_orchestration(hass, command["config_entry_id"])
    ):
        job_result = handle_job_orchestration_start_ws_command(hass, command)
    else:
        job_result = handle_job_state_ws_command(hass, command, message_id=message_id)
    if not job_result["accepted"]:
        return _registered_rejection(
            job_result["code"],
            config_entry_id=command["config_entry_id"],
            job_id=job_result.get("job_id"),
            orchestration=job_result.get("orchestration"),
        )

    return {
        "accepted": True,
        "code": "registered_job_state_command_accepted",
        "type": command["type"],
        "version": command["version"],
        "config_entry_id": command["config_entry_id"],
        "snapshot": job_result["snapshot"],
        "job_state": {
            "code": job_result["code"],
            "job_id": job_result["job_id"],
            "subscription": job_result.get("subscription"),
        },
        "job_orchestration": {
            "run": job_result.get("run"),
        },
        "orchestration": job_result["orchestration"],
    }


def handle_scaffold_ws_command(command: dict[str, Any]) -> dict[str, Any]:
    """Validate a command and return a schema-compatible scaffold snapshot."""
    validation = validate_ws_command_payload(command)
    if not validation["accepted"]:
        return validation

    snapshot = scaffold_job_snapshot(command)
    return {
        "accepted": True,
        "code": "scaffold_command_accepted",
        "type": command["type"],
        "version": command["version"],
        "snapshot": snapshot,
        "orchestration": dict(NO_ORCHESTRATION_CALLS),
    }


def command_payload_from_ws_message(message: dict[str, Any]) -> dict[str, Any]:
    """Remove Home Assistant transport metadata from an Isolinear command."""
    if not isinstance(message, dict):
        return message
    return {
        key: value
        for key, value in message.items()
        if key != "id"
    }


def validate_config_entry_scope(hass: Any, config_entry_id: str) -> dict[str, Any]:
    """Validate that the command targets a configured Isolinear entry."""
    domain_data = getattr(hass, "data", {}).get(DOMAIN, {})
    entry_data = domain_data.get(config_entry_id)
    if isinstance(entry_data, dict) and "entry" in entry_data:
        return {
            "accepted": True,
            "code": "accepted",
            "config_entry_id": config_entry_id,
            "orchestration": websocket_registration_side_effects(False),
        }
    return _registered_rejection("unknown_config_entry", config_entry_id=config_entry_id)


def validate_ws_command_payload(command: Any) -> dict[str, Any]:
    """Fail closed for unknown, unsupported, leaky, or malformed commands."""
    if not isinstance(command, dict):
        return _rejection("invalid_integration_ws_command", errors=[{"path": "$", "reason": "must_be_object"}])

    forbidden_matches = _find_forbidden_material(command, FORBIDDEN_CARD_KEYS)
    if forbidden_matches:
        return {
            "accepted": False,
            "code": "forbidden_card_boundary_content",
            "render_attempted": False,
            "orchestration": dict(NO_ORCHESTRATION_CALLS),
            "forbidden_matches": forbidden_matches,
        }

    command_type = command.get("type")
    if command_type not in REQUIRED_COMMAND_FIELDS:
        return _rejection("unknown_integration_ws_command")

    if command.get("version") != INTEGRATION_WS_VERSION:
        return _rejection("unsupported_integration_ws_version")

    required = REQUIRED_COMMAND_FIELDS[command_type]
    missing = sorted(required - set(command))
    extra = sorted(set(command) - required)
    errors = []
    for key in missing:
        errors.append({"path": f"$.{key}", "reason": "required"})
    for key in extra:
        errors.append({"path": f"$.{key}", "reason": "unexpected"})

    for key in required & STRING_COMMAND_FIELDS:
        value = command.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append({"path": f"$.{key}", "reason": "must_be_non_empty_string"})

    if "remember" in required and not isinstance(command.get("remember"), bool):
        errors.append({"path": "$.remember", "reason": "must_be_boolean"})

    if errors:
        return _rejection("invalid_integration_ws_command", errors=errors)

    return {
        "accepted": True,
        "code": "accepted",
        "render_attempted": False,
        "type": command_type,
        "version": command["version"],
        "orchestration": dict(NO_ORCHESTRATION_CALLS),
    }


def websocket_registration_side_effects(websocket_command_registered: bool) -> dict[str, bool]:
    """Return side-effect accounting for the WebSocket registration packet."""
    return {
        **NO_WEBSOCKET_ORCHESTRATION_CALLS,
        "websocket_command_registered": websocket_command_registered,
    }


def scaffold_job_snapshot(command: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic snapshot proving only boundary acceptance."""
    job_id = command.get("job_id") or "scaffold-job-001"
    prompt = command.get("prompt") or ""
    return {
        "snapshot_id": f"scaffold-{command['type'].split('/')[-1]}",
        "job_id": job_id,
        "status": "planning",
        "prompt": prompt,
        "state_label": "Scaffold",
        "message": "Command schema accepted by the integration scaffold; orchestration is not implemented yet.",
        "progress": {
            "stage": "scaffold",
            "message": "Waiting for a later orchestration packet.",
        },
        "validation": {
            "status": "not_run",
            "summary": "The scaffold validated only the card-facing command boundary.",
            "checks": [
                {
                    "name": "integration_ws_command_boundary",
                    "status": "pass",
                },
                {
                    "name": "orchestration",
                    "status": "not_implemented",
                },
            ],
        },
        "warnings": ["orchestration_not_implemented"],
    }


def invalid_command_examples() -> dict[str, dict[str, Any]]:
    """Return deterministic command examples that must fail closed."""
    return {
        "unknown_command": {
            "type": "isolinear/v1/job/delete",
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": "fake-config-entry",
            "job_id": "job-001",
        },
        "wrong_version": {
            "type": INTEGRATION_COMMAND_TYPES["get_snapshot"],
            "version": 2,
            "config_entry_id": "fake-config-entry",
            "job_id": "job-001",
        },
        "leaky_worker_url": {
            "type": INTEGRATION_COMMAND_TYPES["start_job"],
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": "fake-config-entry",
            "prompt": "Show the temperature",
            "worker_url": "http://worker.local:8765",
        },
        "mutating_service_call": {
            "type": INTEGRATION_COMMAND_TYPES["start_job"],
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": "fake-config-entry",
            "prompt": "Turn on the kitchen lights",
            "service": "light.turn_on",
            "target": {"entity_id": "light.kitchen"},
        },
    }


def _make_ws_handler(command_type: str) -> Callable[..., Any]:
    @websocket_api.websocket_command(_ha_command_schema(command_type))
    @callback
    def ws_handle_isolinear_command(hass: Any, connection: Any, msg: dict[str, Any]) -> dict[str, Any]:
        """Handle an Isolinear WebSocket command."""
        result = handle_registered_ws_command(hass, msg)
        message_id = msg.get("id") if isinstance(msg, dict) else None
        if result["accepted"]:
            if result["type"] == INTEGRATION_COMMAND_TYPES["subscribe_job"] and hasattr(connection, "subscriptions"):
                connection.subscriptions[message_id] = lambda: None
            connection.send_result(message_id, result["snapshot"])
        else:
            connection.send_error(
                message_id,
                result["code"],
                ERROR_MESSAGES.get(result["code"], "Isolinear WebSocket command rejected."),
            )
        return result

    normalized = command_type.replace("/", "_").replace("-", "_")
    ws_handle_isolinear_command.__name__ = f"ws_handle_{normalized}"
    ws_handle_isolinear_command._isolinear_command_type = command_type
    ws_handle_isolinear_command._isolinear_command_schema = _ha_command_schema(command_type)
    return ws_handle_isolinear_command


def _ha_command_schema(command_type: str) -> dict[Any, Any]:
    # Home Assistant owns command routing. Isolinear's deterministic validator
    # owns version, payload shape, forbidden material, and config-entry scope so
    # all failures get the same structured codes in tests and production.
    return {
        vol.Required("type"): command_type,
    }


REGISTERED_WS_HANDLERS = tuple(
    _make_ws_handler(command_type)
    for command_type in INTEGRATION_COMMAND_TYPES.values()
)


def _rejection(code: str, *, errors: list[dict[str, str]] | None = None) -> dict[str, Any]:
    result = {
        "accepted": False,
        "code": code,
        "render_attempted": False,
        "orchestration": dict(NO_ORCHESTRATION_CALLS),
    }
    if errors is not None:
        result["errors"] = errors
    return result


def _registered_rejection(
    code: str,
    *,
    config_entry_id: str | None = None,
    job_id: str | None = None,
    orchestration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "accepted": False,
        "code": code,
        "render_attempted": False,
        "orchestration": orchestration or websocket_registration_side_effects(False),
    }
    if config_entry_id is not None:
        result["config_entry_id"] = config_entry_id
    if job_id is not None:
        result["job_id"] = job_id
    return result


def _find_forbidden_material(payload: Any, forbidden_keys: set[str]) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    _walk_forbidden_material(payload, forbidden_keys, "$", matches)
    return matches


def _walk_forbidden_material(
    payload: Any,
    forbidden_keys: set[str],
    path: str,
    matches: list[dict[str, str]],
) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            child_path = f"{path}.{key}"
            if key.lower() in forbidden_keys:
                matches.append({"path": child_path, "reason": "forbidden_key"})
                continue
            _walk_forbidden_material(value, forbidden_keys, child_path, matches)
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            _walk_forbidden_material(item, forbidden_keys, f"{path}[{index}]", matches)
