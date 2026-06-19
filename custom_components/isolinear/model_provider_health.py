"""Model-provider health diagnostics boundary for Isolinear."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from ._paths import load_schema_document, schema_path
from .const import DOMAIN
from .job_state import JobStateSnapshotValidationError, _validate_json_schema
from .model_provider import (
    MODEL_PROVIDER_HEALTH_PATH,
    get_model_provider_planner,
    planner_client_metadata,
)


DATA_MODEL_PROVIDER_HEALTH = "model_provider_health"
DATA_MODEL_PROVIDER_HEALTH_SETUP = "model_provider_health_setup"

MODEL_PROVIDER_HEALTH_SCHEMA_PATH = (
    schema_path("integration-model-provider-health.schema.json")
)
MODEL_PROVIDER_HEALTH_REQUEST_SCHEMA_PATH = (
    schema_path("model-provider-health-request.schema.json")
)

FORBIDDEN_MODEL_PROVIDER_HEALTH_TEXT = re.compile(
    r"\bBearer\s+\S+|access_token|home_assistant_token|long_lived_access_token|"
    r"worker_token|model_provider_token|ollama_api_key",
    re.IGNORECASE,
)


def setup_model_provider_health(hass: Any, entry: Any) -> dict[str, Any]:
    """Record whether an explicit model-provider health probe is available."""
    entry_id = getattr(entry, "entry_id", "scaffold-entry")
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    planner = get_model_provider_planner(hass, entry_id)
    enabled = planner is not None
    setup = {
        "accepted": True,
        "code": "model_provider_health_probe_available" if enabled else "model_provider_health_probe_disabled",
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "enabled": enabled,
        "provider": _provider_health_metadata(planner) if enabled else None,
        "orchestration": model_provider_health_side_effects(),
    }
    entry_data[DATA_MODEL_PROVIDER_HEALTH_SETUP] = deepcopy(setup)
    return setup


def check_model_provider_health(hass: Any, entry_id: str) -> dict[str, Any]:
    """Explicitly probe one config-entry-scoped model provider."""
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id)
    if not isinstance(entry_data, dict) or entry_data.get("entry") is None:
        return _health_rejection("unknown_config_entry")

    planner = get_model_provider_planner(hass, entry_id)
    if planner is None:
        return _health_rejection("model_provider_health_not_configured")

    request = build_model_provider_health_request()
    request_validation = validate_model_provider_health_request_contract(request)
    if not request_validation["accepted"]:
        result = _health_rejection(
            "invalid_model_provider_health_request",
            orchestration=model_provider_health_side_effects(
                model_provider_health_request_validated=False,
            ),
        )
        result["validation"] = request_validation
        return result

    provider_response = _call_model_provider_health(planner, request)
    health = _build_model_provider_health(
        entry_id=entry_id,
        planner=planner,
        request=request,
        provider_response=provider_response,
    )
    if health is None:
        return _health_rejection(
            "invalid_model_provider_health_response",
            orchestration=model_provider_health_side_effects(
                model_provider_health_check_called=True,
                model_provider_health_request_validated=True,
            ),
        )

    validation = validate_model_provider_health_contract(health)
    if not validation["accepted"]:
        result = _health_rejection(
            "invalid_integration_model_provider_health",
            orchestration=model_provider_health_side_effects(
                model_provider_health_check_called=True,
                model_provider_health_request_validated=True,
                model_provider_health_response_validated=True,
            ),
        )
        result["validation"] = validation
        return result

    entry_data[DATA_MODEL_PROVIDER_HEALTH] = deepcopy(health)
    result = {
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
    entry_data[DATA_MODEL_PROVIDER_HEALTH_SETUP] = {
        "accepted": True,
        "code": "model_provider_health_probe_recorded",
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "enabled": health["status"] == "ready",
        "provider": deepcopy(health["provider"]),
        "orchestration": deepcopy(health["orchestration"]),
    }
    return result


def get_model_provider_health(hass: Any, entry_id: str) -> dict[str, Any] | None:
    """Return the latest model-provider health envelope for one config entry."""
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    health = entry_data.get(DATA_MODEL_PROVIDER_HEALTH) if isinstance(entry_data, dict) else None
    return deepcopy(health) if isinstance(health, dict) else None


def build_model_provider_health_request() -> dict[str, Any]:
    """Build the Ollama-compatible provider health request envelope."""
    return {
        "protocol_version": 1,
        "method": "GET",
        "path": MODEL_PROVIDER_HEALTH_PATH,
        "headers": {
            "accept": "application/json",
        },
    }


def validate_model_provider_health_request_contract(request: Any) -> dict[str, Any]:
    """Validate ModelProviderHealthRequest against the repo JSON Schema."""
    try:
        schema = load_schema_document(MODEL_PROVIDER_HEALTH_REQUEST_SCHEMA_PATH)
        _validate_json_schema(request, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_model_provider_health_request",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(MODEL_PROVIDER_HEALTH_REQUEST_SCHEMA_PATH),
    }


def validate_model_provider_health_contract(health: Any) -> dict[str, Any]:
    """Validate IntegrationModelProviderHealth against the repo JSON Schema."""
    try:
        schema = load_schema_document(MODEL_PROVIDER_HEALTH_SCHEMA_PATH)
        _validate_json_schema(health, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_model_provider_health",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(MODEL_PROVIDER_HEALTH_SCHEMA_PATH),
    }


def model_provider_health_side_effects(
    *,
    model_provider_health_check_called: bool = False,
    model_provider_health_bookkeeping_written: bool = False,
    model_provider_health_request_validated: bool = False,
    model_provider_health_response_validated: bool = False,
) -> dict[str, bool]:
    """Return side-effect accounting for model-provider health diagnostics."""
    return {
        "model_provider_health_check_called": model_provider_health_check_called,
        "model_provider_health_bookkeeping_written": model_provider_health_bookkeeping_written,
        "model_provider_health_request_validated": model_provider_health_request_validated,
        "model_provider_health_response_validated": model_provider_health_response_validated,
        "model_provider_planning_called": False,
        "model_provider_retry_policy_written": False,
        "worker_called": False,
        "worker_health_check_called": False,
        "home_assistant_history_read": False,
        "semantic_memory_called": False,
        "home_assistant_service_or_state_mutation_called": False,
        "token_generated": False,
        "token_rotation_called": False,
        "chart_rendering_called": False,
        "chart_artifact_written": False,
        "durable_storage_written": False,
        "durable_retry_storage_written": False,
        "retry_behavior_called": False,
        "scheduler_called": False,
        "automatic_retry_called": False,
        "automatic_progress_task_called": False,
        "new_provider_transport_added": False,
        "provider_details_leaked_to_card": False,
    }


def _call_model_provider_health(planner: Any, request: dict[str, Any]) -> dict[str, Any]:
    check_health = getattr(planner, "check_health", None)
    if callable(check_health):
        response = check_health(request)
        return response if isinstance(response, dict) else _provider_health_failure("model_provider_health_response_error", "")
    return _provider_health_failure(
        "model_provider_health_endpoint_unavailable",
        "Configured model provider client does not implement health diagnostics.",
    )


def _build_model_provider_health(
    *,
    entry_id: str,
    planner: Any,
    request: dict[str, Any],
    provider_response: dict[str, Any],
) -> dict[str, Any] | None:
    response = _normalized_health_response(provider_response)
    if response is None:
        return None

    status = response["status"]
    code = response["code"]
    return {
        "health_id": f"{entry_id}-model-provider-health-001",
        "type": "isolinear_model_provider_health",
        "config_entry_id": entry_id,
        "status": status,
        "code": code,
        "provider": _provider_health_metadata(planner),
        "request": deepcopy(request),
        "response": response,
        "validation": {
            "status": "pass",
            "summary": "Model-provider health metadata validates before storage.",
            "checks": [
                {"name": "model_provider_health_request", "status": "pass"},
                {"name": "model_provider_health_response", "status": "pass"},
                {"name": "provider_health_metadata_card_safe", "status": "pass"},
            ],
        },
        "warnings": _health_warnings(status),
        "orchestration": model_provider_health_side_effects(
            model_provider_health_check_called=True,
            model_provider_health_bookkeeping_written=True,
            model_provider_health_request_validated=True,
            model_provider_health_response_validated=True,
        ),
    }


def _normalized_health_response(provider_response: dict[str, Any]) -> dict[str, Any] | None:
    if provider_response.get("accepted") is not True:
        return {
            "accepted": False,
            "status": "unavailable",
            "code": _safe_provider_health_code(provider_response.get("code")),
            "message": _safe_provider_health_message(
                provider_response.get("message"),
                fallback="Model-provider health endpoint was unavailable.",
            ),
            "checks": [],
            "capabilities": {"planning": False, "structured_output": False},
        }

    health_result = provider_response.get("health_result")
    if not isinstance(health_result, dict) or _health_result_contains_forbidden_material(health_result):
        return None
    status = health_result.get("status")
    if status not in {"ready", "not_ready"}:
        return None

    capabilities = health_result.get("capabilities") if isinstance(health_result.get("capabilities"), dict) else {}
    return {
        "accepted": True,
        "status": status,
        "code": _safe_provider_health_code(health_result.get("code") or f"model_provider_health_{status}"),
        "message": _safe_provider_health_message(
            health_result.get("message"),
            fallback=f"Model-provider health endpoint reports {status}.",
        ),
        "checks": _safe_health_checks(health_result.get("checks")),
        "capabilities": {
            "planning": status == "ready" and capabilities.get("planning") is True,
            "structured_output": status == "ready" and capabilities.get("structured_output") is True,
        },
    }


def _provider_health_metadata(planner: Any) -> dict[str, Any]:
    metadata = planner_client_metadata(planner)
    return {
        "type": metadata["type"],
        "role": metadata["role"],
        "endpoint_url": metadata["endpoint_url"],
        "model": metadata["model"],
        "health_path": MODEL_PROVIDER_HEALTH_PATH,
    }


def _safe_health_checks(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    checks = []
    for item in value[:10]:
        if not isinstance(item, dict):
            continue
        name = _safe_provider_health_code(item.get("name"))
        status = _safe_provider_health_code(item.get("status"))
        checks.append({"name": name, "status": status})
    return checks


def _safe_provider_health_code(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "model_provider_health_failed"
    stripped = value.strip()
    if FORBIDDEN_MODEL_PROVIDER_HEALTH_TEXT.search(stripped):
        return "model_provider_health_failed"
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "_", stripped).strip("_")
    return normalized[:80] if normalized else "model_provider_health_failed"


def _safe_provider_health_message(value: Any, *, fallback: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return fallback
    stripped = re.sub(r"\s+", " ", value.strip())
    if FORBIDDEN_MODEL_PROVIDER_HEALTH_TEXT.search(stripped):
        return fallback
    return stripped[:240] if stripped else fallback


def _health_result_contains_forbidden_material(health_result: dict[str, Any]) -> bool:
    return FORBIDDEN_MODEL_PROVIDER_HEALTH_TEXT.search(str(health_result)) is not None


def _health_warnings(status: str) -> list[str]:
    if status == "ready":
        return ["model_provider_health_ready", "provider_details_internal_only"]
    if status == "not_ready":
        return ["model_provider_health_not_ready", "provider_details_internal_only"]
    return ["model_provider_health_unavailable", "provider_details_internal_only", "automatic_retry_not_scheduled"]


def _provider_health_failure(code: str, message: str) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": code,
        "provider_role": "planner",
        "retry_safe": False,
        "message": message,
    }


def _health_rejection(
    code: str,
    *,
    orchestration: dict[str, bool] | None = None,
) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": code,
        "enabled": False,
        "orchestration": orchestration or model_provider_health_side_effects(),
    }
