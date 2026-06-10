"""Worker health/readiness endpoint boundary for Isolinear."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .const import DOMAIN
from .job_state import JobStateSnapshotValidationError, _validate_json_schema
from .worker_readiness import get_worker_readiness
from .worker_renderer import (
    WORKER_HEALTH_PATH,
    build_worker_health_request,
    get_worker_render_client,
    redacted_worker_health_request,
    worker_client_metadata,
    worker_client_token,
)


DATA_WORKER_HEALTH = "worker_health"
DATA_WORKER_HEALTH_SETUP = "worker_health_setup"

WORKER_HEALTH_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "schemas" / "integration-worker-health.schema.json"
)
WORKER_HEALTH_REQUEST_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "schemas" / "worker-health-request.schema.json"
)

FORBIDDEN_WORKER_HEALTH_TEXT = re.compile(
    r"\bBearer\s+\S+|access_token|home_assistant_token|long_lived_access_token|worker_token",
    re.IGNORECASE,
)


def setup_worker_health(hass: Any, entry: Any) -> dict[str, Any]:
    """Record whether an explicit worker health probe is currently available."""
    entry_id = getattr(entry, "entry_id", "scaffold-entry")
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    readiness = get_worker_readiness(hass, entry_id)
    client = get_worker_render_client(hass, entry_id)
    token = worker_client_token(client) if client is not None else None
    enabled = (
        isinstance(readiness, dict)
        and readiness.get("status") == "ready"
        and client is not None
        and token is not None
    )
    setup = {
        "accepted": True,
        "code": "worker_health_probe_available" if enabled else "worker_health_probe_disabled",
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "enabled": enabled,
        "worker": _redacted_worker_metadata(client, token) if enabled else None,
        "orchestration": worker_health_side_effects(),
    }
    entry_data[DATA_WORKER_HEALTH_SETUP] = deepcopy(setup)
    return setup


def check_worker_health(hass: Any, entry_id: str) -> dict[str, Any]:
    """Explicitly probe one config-entry-scoped worker health endpoint."""
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id)
    if not isinstance(entry_data, dict) or entry_data.get("entry") is None:
        return _health_rejection("unknown_config_entry")

    readiness = get_worker_readiness(hass, entry_id)
    client = get_worker_render_client(hass, entry_id)
    token = worker_client_token(client) if client is not None else None
    if (
        not isinstance(readiness, dict)
        or readiness.get("status") != "ready"
        or client is None
        or token is None
    ):
        return _health_rejection("worker_health_not_ready")

    request = build_worker_health_request(
        request_id=f"{entry_id}-worker-health-request-001",
        worker_token=token,
    )
    request_validation = validate_worker_health_request_contract(request)
    if not request_validation["accepted"]:
        result = _health_rejection(
            "invalid_worker_health_request",
            orchestration=worker_health_side_effects(worker_health_request_validated=False),
        )
        result["validation"] = request_validation
        return result

    worker_response = _call_worker_health(client, request)
    health = _build_worker_health(
        entry_id=entry_id,
        client=client,
        token=token,
        request=request,
        worker_response=worker_response,
    )
    if health is None:
        return _health_rejection(
            "invalid_worker_health_response",
            orchestration=worker_health_side_effects(
                worker_health_check_called=True,
                worker_health_request_validated=True,
            ),
        )

    validation = validate_worker_health_contract(health)
    if not validation["accepted"]:
        result = _health_rejection(
            "invalid_integration_worker_health",
            orchestration=worker_health_side_effects(
                worker_health_check_called=True,
                worker_health_request_validated=True,
                worker_health_response_validated=True,
            ),
        )
        result["validation"] = validation
        return result

    entry_data[DATA_WORKER_HEALTH] = deepcopy(health)
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
    entry_data[DATA_WORKER_HEALTH_SETUP] = {
        "accepted": True,
        "code": "worker_health_probe_recorded",
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "enabled": health["status"] == "ready",
        "worker": deepcopy(health["worker"]),
        "orchestration": deepcopy(health["orchestration"]),
    }
    return result


def get_worker_health(hass: Any, entry_id: str) -> dict[str, Any] | None:
    """Return the latest worker health envelope for one config entry."""
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    health = entry_data.get(DATA_WORKER_HEALTH) if isinstance(entry_data, dict) else None
    return deepcopy(health) if isinstance(health, dict) else None


def validate_worker_health_request_contract(request: Any) -> dict[str, Any]:
    """Validate WorkerHealthRequest against the repo JSON Schema."""
    try:
        schema = json.loads(WORKER_HEALTH_REQUEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        _validate_json_schema(request, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_worker_health_request",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(WORKER_HEALTH_REQUEST_SCHEMA_PATH),
    }


def validate_worker_health_contract(health: Any) -> dict[str, Any]:
    """Validate IntegrationWorkerHealth against the repo JSON Schema."""
    try:
        schema = json.loads(WORKER_HEALTH_SCHEMA_PATH.read_text(encoding="utf-8"))
        _validate_json_schema(health, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_worker_health",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(WORKER_HEALTH_SCHEMA_PATH),
    }


def worker_health_side_effects(
    *,
    worker_health_check_called: bool = False,
    worker_health_bookkeeping_written: bool = False,
    worker_health_request_validated: bool = False,
    worker_health_response_validated: bool = False,
) -> dict[str, bool]:
    """Return side-effect accounting for worker health endpoint checks."""
    return {
        "worker_health_check_called": worker_health_check_called,
        "worker_health_bookkeeping_written": worker_health_bookkeeping_written,
        "worker_health_request_validated": worker_health_request_validated,
        "worker_health_response_validated": worker_health_response_validated,
        "home_assistant_history_read": False,
        "semantic_memory_called": False,
        "home_assistant_service_or_state_mutation_called": False,
        "token_generated": False,
        "token_rotation_called": False,
        "worker_render_called": False,
        "chart_rendering_called": False,
        "chart_artifact_written": False,
        "durable_storage_written": False,
        "durable_retry_storage_written": False,
        "retry_behavior_called": False,
        "scheduler_called": False,
        "automatic_retry_called": False,
        "automatic_progress_task_called": False,
        "new_worker_transport_added": False,
        "token_leaked_to_card": False,
        "token_leaked_to_model_provider": False,
    }


def _call_worker_health(client: Any, request: dict[str, Any]) -> dict[str, Any]:
    check_health = getattr(client, "check_health", None)
    if callable(check_health):
        response = check_health(request)
        return response if isinstance(response, dict) else _worker_health_failure("worker_health_response_error", "")
    return _worker_health_failure(
        "worker_health_endpoint_unavailable",
        "Configured worker client does not implement the health endpoint.",
    )


def _build_worker_health(
    *,
    entry_id: str,
    client: Any,
    token: str,
    request: dict[str, Any],
    worker_response: dict[str, Any],
) -> dict[str, Any] | None:
    response = _normalized_health_response(worker_response)
    if response is None:
        return None

    status = response["status"]
    code = response["code"]
    return {
        "health_id": f"{entry_id}-worker-health-001",
        "type": "isolinear_worker_health",
        "config_entry_id": entry_id,
        "status": status,
        "code": code,
        "worker": _redacted_worker_metadata(client, token),
        "request": redacted_worker_health_request(request),
        "response": response,
        "validation": {
            "status": "pass",
            "summary": "Worker health endpoint metadata validates before storage.",
            "checks": [
                {"name": "worker_health_request", "status": "pass"},
                {"name": "worker_health_response", "status": "pass"},
                {"name": "worker_authorization_redacted", "status": "pass"},
            ],
        },
        "warnings": _health_warnings(status),
        "orchestration": worker_health_side_effects(
            worker_health_check_called=True,
            worker_health_bookkeeping_written=True,
            worker_health_request_validated=True,
            worker_health_response_validated=True,
        ),
    }


def _normalized_health_response(worker_response: dict[str, Any]) -> dict[str, Any] | None:
    if worker_response.get("accepted") is not True:
        return {
            "accepted": False,
            "status": "unavailable",
            "code": _safe_worker_health_code(worker_response.get("code")),
            "message": _safe_worker_health_message(
                worker_response.get("message"),
                fallback="Worker health endpoint was unavailable.",
            ),
            "checks": [],
            "capabilities": {"rendering": False},
        }

    health_result = worker_response.get("health_result")
    if not isinstance(health_result, dict):
        return None
    status = health_result.get("status")
    if status not in {"ready", "not_ready"}:
        return None

    return {
        "accepted": True,
        "status": status,
        "code": _safe_worker_health_code(health_result.get("code") or f"worker_health_{status}"),
        "message": _safe_worker_health_message(
            health_result.get("message"),
            fallback=f"Worker health endpoint reports {status}.",
        ),
        "checks": _safe_health_checks(health_result.get("checks")),
        "capabilities": {
            "rendering": (
                status == "ready"
                and isinstance(health_result.get("capabilities"), dict)
                and health_result["capabilities"].get("rendering") is True
            ),
        },
    }


def _redacted_worker_metadata(client: Any, token: str | None) -> dict[str, Any]:
    metadata = worker_client_metadata(client)
    return {
        "type": metadata["type"],
        "role": metadata["role"],
        "endpoint_url": metadata["endpoint_url"],
        "api_version": metadata["api_version"],
        "health_path": WORKER_HEALTH_PATH,
        "authorization": "Bearer <redacted>" if token else "<missing>",
    }


def _safe_health_checks(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    checks = []
    for item in value[:10]:
        if not isinstance(item, dict):
            continue
        name = _safe_worker_health_code(item.get("name"))
        status = _safe_worker_health_code(item.get("status"))
        checks.append({"name": name, "status": status})
    return checks


def _safe_worker_health_code(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "worker_health_failed"
    stripped = value.strip()
    if FORBIDDEN_WORKER_HEALTH_TEXT.search(stripped):
        return "worker_health_failed"
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "_", stripped).strip("_")
    return normalized[:80] if normalized else "worker_health_failed"


def _safe_worker_health_message(value: Any, *, fallback: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return fallback
    stripped = re.sub(r"\s+", " ", value.strip())
    if FORBIDDEN_WORKER_HEALTH_TEXT.search(stripped):
        return "Worker health endpoint response was sanitized."
    return stripped[:240] if stripped else fallback


def _health_warnings(status: str) -> list[str]:
    if status == "ready":
        return ["worker_health_ready", "worker_authorization_redacted"]
    if status == "not_ready":
        return ["worker_health_not_ready", "worker_authorization_redacted"]
    return ["worker_health_unavailable", "worker_authorization_redacted", "automatic_retry_not_scheduled"]


def _worker_health_failure(code: str, message: str) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": code,
        "provider_role": "renderer",
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
        "orchestration": orchestration or worker_health_side_effects(),
    }
