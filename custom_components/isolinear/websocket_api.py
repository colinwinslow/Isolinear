"""Versioned WebSocket command stubs for the Isolinear scaffold."""

from __future__ import annotations

from typing import Any

from .const import (
    DATA_WEBSOCKET_COMMANDS,
    DOMAIN,
    INTEGRATION_COMMAND_TYPES,
    INTEGRATION_WS_VERSION,
)


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

NO_ORCHESTRATION_CALLS = {
    "worker_called": False,
    "model_provider_called": False,
    "home_assistant_history_called": False,
    "semantic_memory_called": False,
    "home_assistant_mutation_called": False,
}


async def async_register_websocket_api(hass: Any) -> dict[str, Any]:
    """Record scaffold command names without registering real orchestration."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    commands = list(INTEGRATION_COMMAND_TYPES.values())
    domain_data[DATA_WEBSOCKET_COMMANDS] = commands
    return {
        "registered": True,
        "mode": "scaffold",
        "commands": commands,
        "orchestration": dict(NO_ORCHESTRATION_CALLS),
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
