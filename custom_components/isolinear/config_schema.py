"""Pure configuration shape helpers for the Isolinear scaffold."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from .const import (
    MODEL_PROVIDER_OLLAMA_COMPATIBLE,
    RENDER_MODE_SAFE,
    SUPPORTED_MODEL_PROVIDER_TYPES,
    SUPPORTED_RENDER_MODES,
)


ENTITY_ID_PATTERN = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")
SECRET_VALUE_PATTERN = re.compile(
    r"(access_token|bearer\s+|home_assistant_token|long_lived_access_token|"
    r"model_provider_token|ollama_api_key|super-secret|worker_token)",
    re.IGNORECASE,
)

FORBIDDEN_CONFIG_KEYS = {
    "access_token",
    "ha_token",
    "home_assistant_token",
    "long_lived_access_token",
    "model_provider_token",
    "ollama_api_key",
    "password",
    "semantic_memory",
    "service",
    "service_data",
    "worker_credentials",
    "worker_token",
}


@dataclass(frozen=True)
class IsolinearConfigShape:
    """Config-entry data owned by the integration scaffold."""

    model_provider_type: str
    model_endpoint_url: str
    planner_model: str
    codegen_model: str | None
    visual_validator_model: str | None
    worker_endpoint_url: str


@dataclass(frozen=True)
class IsolinearOptionsShape:
    """Options data owned by the integration scaffold."""

    default_render_mode: str
    max_codegen_repair_attempts: int
    codegen_enabled: bool
    entity_allowlist: tuple[str, ...]


def default_config_data() -> dict[str, Any]:
    """Return local-first config-entry defaults for the scaffold."""
    return {
        "model_provider_type": MODEL_PROVIDER_OLLAMA_COMPATIBLE,
        "model_endpoint_url": "http://localhost:11434",
        "planner_model": "llama3.1",
        "codegen_model": None,
        "visual_validator_model": None,
        "worker_endpoint_url": "http://localhost:8765",
    }


def default_options_data() -> dict[str, Any]:
    """Return safe-mode options defaults for the scaffold."""
    return {
        "default_render_mode": RENDER_MODE_SAFE,
        "max_codegen_repair_attempts": 1,
        # ADR-0029 packet 4: codegen is the opt-in advanced render path
        # (invariant #6). Disabled by default; kept cleanly removable.
        "codegen_enabled": False,
        "entity_allowlist": [],
    }


def validate_config_and_options(
    config_data: dict[str, Any],
    options_data: dict[str, Any],
) -> dict[str, Any]:
    """Validate scaffold config and options without touching Home Assistant."""
    forbidden_matches = _find_forbidden_material(
        {"config_data": config_data, "options_data": options_data},
        FORBIDDEN_CONFIG_KEYS,
    )
    if forbidden_matches:
        return {
            "accepted": False,
            "code": "forbidden_config_material",
            "forbidden_matches": forbidden_matches,
        }

    config_errors = _validate_config_data(config_data)
    option_errors = _validate_options_data(options_data)
    errors = config_errors + option_errors
    if errors:
        return {
            "accepted": False,
            "code": "invalid_integration_config",
            "errors": errors,
        }

    normalized_config = IsolinearConfigShape(
        model_provider_type=config_data["model_provider_type"],
        model_endpoint_url=config_data["model_endpoint_url"],
        planner_model=config_data["planner_model"],
        codegen_model=config_data["codegen_model"],
        visual_validator_model=config_data["visual_validator_model"],
        worker_endpoint_url=config_data["worker_endpoint_url"],
    )
    normalized_options = IsolinearOptionsShape(
        default_render_mode=options_data["default_render_mode"],
        max_codegen_repair_attempts=options_data["max_codegen_repair_attempts"],
        codegen_enabled=options_data["codegen_enabled"],
        entity_allowlist=tuple(options_data["entity_allowlist"]),
    )
    return {
        "accepted": True,
        "code": "accepted",
        "config": normalized_config,
        "options": normalized_options,
    }


def validate_default_config_and_options() -> dict[str, Any]:
    """Validate the scaffold's default local-first shape."""
    return validate_config_and_options(default_config_data(), default_options_data())


def invalid_config_examples() -> dict[str, dict[str, Any]]:
    """Return deterministic malformed config examples for tests and evals."""
    invalid_render_mode = {
        "config_data": default_config_data(),
        "options_data": {
            **default_options_data(),
            "default_render_mode": "unsafe_direct_python",
        },
    }
    secret_bearing = {
        "config_data": {
            **default_config_data(),
            "worker_token": "super-secret-worker-token",
        },
        "options_data": default_options_data(),
    }
    credential_endpoint_url = {
        "config_data": {
            **default_config_data(),
            "worker_endpoint_url": "http://user:secret@localhost:8765",
        },
        "options_data": default_options_data(),
    }
    secret_like_allowed_value = {
        "config_data": {
            **default_config_data(),
            "planner_model": "long_lived_access_token",
        },
        "options_data": default_options_data(),
    }
    duplicate_allowlist = {
        "config_data": default_config_data(),
        "options_data": {
            **default_options_data(),
            "entity_allowlist": [
                "sensor.upstairs_temperature",
                "sensor.upstairs_temperature",
            ],
        },
    }
    malformed_allowlist = {
        "config_data": default_config_data(),
        "options_data": {
            **default_options_data(),
            "entity_allowlist": ["not-an-entity-id"],
        },
    }
    return {
        "invalid_render_mode": invalid_render_mode,
        "secret_bearing": secret_bearing,
        "credential_endpoint_url": credential_endpoint_url,
        "secret_like_allowed_value": secret_like_allowed_value,
        "duplicate_allowlist": duplicate_allowlist,
        "malformed_allowlist": malformed_allowlist,
    }


def redacted_config_result(result: dict[str, Any]) -> dict[str, Any]:
    """Convert dataclass payloads into deterministic JSON-safe evidence."""
    redacted = copy.deepcopy(result)
    for key in ("config", "options"):
        value = redacted.get(key)
        if hasattr(value, "__dataclass_fields__"):
            redacted[key] = {
                field_name: getattr(value, field_name)
                for field_name in value.__dataclass_fields__
            }
    if "options" in redacted and isinstance(redacted["options"], dict):
        allowlist = redacted["options"].get("entity_allowlist")
        if isinstance(allowlist, tuple):
            redacted["options"]["entity_allowlist"] = list(allowlist)
    return redacted


def _validate_config_data(config_data: dict[str, Any]) -> list[dict[str, str]]:
    required = {
        "model_provider_type",
        "model_endpoint_url",
        "planner_model",
        "codegen_model",
        "visual_validator_model",
        "worker_endpoint_url",
    }
    errors: list[dict[str, str]] = []
    _require_exact_keys(config_data, required, "$.config_data", errors)
    if errors:
        return errors

    if config_data["model_provider_type"] not in SUPPORTED_MODEL_PROVIDER_TYPES:
        errors.append(
            {
                "path": "$.config_data.model_provider_type",
                "reason": "unsupported_model_provider_type",
            }
        )
    _validate_http_url(config_data["model_endpoint_url"], "$.config_data.model_endpoint_url", errors)
    _validate_http_url(config_data["worker_endpoint_url"], "$.config_data.worker_endpoint_url", errors)
    _validate_non_empty_string(config_data["planner_model"], "$.config_data.planner_model", errors)
    _validate_optional_string(config_data["codegen_model"], "$.config_data.codegen_model", errors)
    _validate_optional_string(
        config_data["visual_validator_model"],
        "$.config_data.visual_validator_model",
        errors,
    )
    return errors


def _validate_options_data(options_data: dict[str, Any]) -> list[dict[str, str]]:
    required = {
        "default_render_mode",
        "max_codegen_repair_attempts",
        "codegen_enabled",
        "entity_allowlist",
    }
    errors: list[dict[str, str]] = []
    _require_exact_keys(options_data, required, "$.options_data", errors)
    if errors:
        return errors

    if options_data["default_render_mode"] not in SUPPORTED_RENDER_MODES:
        errors.append(
            {
                "path": "$.options_data.default_render_mode",
                "reason": "unsupported_render_mode",
            }
        )
    max_attempts = options_data["max_codegen_repair_attempts"]
    if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or max_attempts < 0:
        errors.append(
            {
                "path": "$.options_data.max_codegen_repair_attempts",
                "reason": "must_be_non_negative_integer",
            }
        )
    if not isinstance(options_data["codegen_enabled"], bool):
        errors.append(
            {
                "path": "$.options_data.codegen_enabled",
                "reason": "must_be_boolean",
            }
        )
    allowlist = options_data["entity_allowlist"]
    if not isinstance(allowlist, list):
        errors.append(
            {
                "path": "$.options_data.entity_allowlist",
                "reason": "must_be_list",
            }
        )
        return errors
    if len(allowlist) != len(set(allowlist)):
        errors.append(
            {
                "path": "$.options_data.entity_allowlist",
                "reason": "duplicate_entity_id",
            }
        )
    for index, entity_id in enumerate(allowlist):
        if not isinstance(entity_id, str) or ENTITY_ID_PATTERN.search(entity_id) is None:
            errors.append(
                {
                    "path": f"$.options_data.entity_allowlist[{index}]",
                    "reason": "invalid_entity_id",
                }
            )
    return errors


def _require_exact_keys(
    payload: dict[str, Any],
    required: set[str],
    path: str,
    errors: list[dict[str, str]],
) -> None:
    if not isinstance(payload, dict):
        errors.append({"path": path, "reason": "must_be_object"})
        return
    missing = sorted(required - set(payload))
    extra = sorted(set(payload) - required)
    for key in missing:
        errors.append({"path": f"{path}.{key}", "reason": "required"})
    for key in extra:
        errors.append({"path": f"{path}.{key}", "reason": "unexpected"})


def _validate_http_url(value: Any, path: str, errors: list[dict[str, str]]) -> None:
    if not isinstance(value, str):
        errors.append({"path": path, "reason": "must_be_string"})
        return
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        errors.append({"path": path, "reason": "must_be_http_url"})
        return
    if parsed.username is not None or parsed.password is not None:
        errors.append({"path": path, "reason": "endpoint_userinfo_forbidden"})


def _validate_non_empty_string(value: Any, path: str, errors: list[dict[str, str]]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append({"path": path, "reason": "must_be_non_empty_string"})


def _validate_optional_string(value: Any, path: str, errors: list[dict[str, str]]) -> None:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        errors.append({"path": path, "reason": "must_be_null_or_non_empty_string"})


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
    elif isinstance(payload, str) and SECRET_VALUE_PATTERN.search(payload):
        matches.append({"path": path, "reason": "secret_like_value"})
