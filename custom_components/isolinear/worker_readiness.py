"""Worker token provisioning and readiness boundary for Isolinear."""

from __future__ import annotations

import json
import secrets
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from .const import DOMAIN
from .job_state import JobStateSnapshotValidationError, _validate_json_schema
from .worker_renderer import (
    DATA_WORKER_RENDER_TOKEN,
    WORKER_RENDER_PATH,
    WORKER_TRANSPORT_VERSION,
    is_valid_worker_render_token,
    redact_authorization,
)


DATA_WORKER_READINESS = "worker_readiness"
DATA_WORKER_READINESS_SETUP = "worker_readiness_setup"

WORKER_READINESS_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "schemas" / "integration-worker-readiness.schema.json"
)
DEFAULT_WORKER_TOKEN_BYTES = 32


def setup_worker_readiness(hass: Any, entry: Any) -> dict[str, Any]:
    """Record redacted worker token readiness for one config entry."""
    return _record_worker_readiness(hass, entry)


def provision_integration_worker_token(
    hass: Any,
    entry_id: str,
    *,
    token_factory: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Explicitly provision one in-memory integration-owned worker token."""
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id)
    if not isinstance(entry_data, dict) or entry_data.get("entry") is None:
        return _readiness_rejection("unknown_config_entry")

    existing_token = entry_data.get(DATA_WORKER_RENDER_TOKEN)
    token_generated = False
    token_stored = False
    if is_valid_worker_render_token(existing_token):
        code = "worker_token_already_present"
    else:
        factory = token_factory or _generate_worker_token
        candidate = factory()
        if not is_valid_worker_render_token(candidate):
            return _readiness_rejection("invalid_worker_token")
        previous_token_present = DATA_WORKER_RENDER_TOKEN in entry_data
        previous_token = entry_data.get(DATA_WORKER_RENDER_TOKEN)
        entry_data[DATA_WORKER_RENDER_TOKEN] = candidate
        token_generated = True
        token_stored = True
        code = "worker_token_provisioned"

    result = _record_worker_readiness(
        hass,
        entry_data["entry"],
        code=code,
        token_generated=token_generated,
        token_stored=token_stored,
    )
    if not result["accepted"] and token_stored:
        if previous_token_present:
            entry_data[DATA_WORKER_RENDER_TOKEN] = previous_token
        else:
            entry_data.pop(DATA_WORKER_RENDER_TOKEN, None)
        result["orchestration"] = worker_readiness_side_effects(
            token_generated=token_generated,
            token_stored=False,
            readiness_bookkeeping_written=False,
            worker_renderer_setup_gated=False,
        )
    return result


def get_worker_readiness(hass: Any, entry_id: str) -> dict[str, Any] | None:
    """Return the latest worker readiness envelope for one config entry."""
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    readiness = entry_data.get(DATA_WORKER_READINESS) if isinstance(entry_data, dict) else None
    return deepcopy(readiness) if isinstance(readiness, dict) else None


def validate_worker_readiness_contract(readiness: Any) -> dict[str, Any]:
    """Validate IntegrationWorkerReadiness against the repo JSON Schema."""
    try:
        schema = json.loads(WORKER_READINESS_SCHEMA_PATH.read_text(encoding="utf-8"))
        _validate_json_schema(readiness, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_worker_readiness",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(WORKER_READINESS_SCHEMA_PATH),
    }


def worker_readiness_side_effects(
    *,
    token_generated: bool = False,
    token_stored: bool = False,
    readiness_bookkeeping_written: bool = False,
    worker_renderer_setup_gated: bool = False,
) -> dict[str, bool]:
    """Return side-effect accounting for worker token/readiness setup."""
    return {
        "token_generated": token_generated,
        "token_stored": token_stored,
        "readiness_bookkeeping_written": readiness_bookkeeping_written,
        "worker_renderer_setup_gated": worker_renderer_setup_gated,
        "home_assistant_history_read": False,
        "semantic_memory_called": False,
        "home_assistant_service_or_state_mutation_called": False,
        "worker_called": False,
        "chart_rendering_called": False,
        "chart_artifact_written": False,
        "durable_token_storage_written": False,
        "token_rotation_called": False,
        "worker_health_check_called": False,
        "retry_behavior_called": False,
        "automatic_progress_task_called": False,
        "worker_streaming_called": False,
        "token_leaked_to_card": False,
        "token_leaked_to_model_provider": False,
    }


def _record_worker_readiness(
    hass: Any,
    entry: Any,
    *,
    code: str | None = None,
    token_generated: bool = False,
    token_stored: bool = False,
) -> dict[str, Any]:
    entry_id = getattr(entry, "entry_id", "scaffold-entry")
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    endpoint_url = _worker_endpoint_url(entry)
    token = entry_data.get(DATA_WORKER_RENDER_TOKEN)
    readiness = _build_worker_readiness(
        entry_id=entry_id,
        endpoint_url=endpoint_url,
        token=token,
        code=code,
        token_generated=token_generated,
        token_stored=token_stored,
    )
    validation = validate_worker_readiness_contract(readiness)
    if not validation["accepted"]:
        result = _readiness_rejection("invalid_integration_worker_readiness")
        result["validation"] = validation
        return result

    entry_data[DATA_WORKER_READINESS] = deepcopy(readiness)
    setup = {
        "accepted": True,
        "code": code or readiness["code"],
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "enabled": readiness["status"] == "ready",
        "readiness": deepcopy(readiness),
        "validation": validation,
        "orchestration": deepcopy(readiness["orchestration"]),
    }
    entry_data[DATA_WORKER_READINESS_SETUP] = deepcopy(setup)
    return setup


def _build_worker_readiness(
    *,
    entry_id: str,
    endpoint_url: str | None,
    token: Any,
    code: str | None,
    token_generated: bool,
    token_stored: bool,
) -> dict[str, Any]:
    endpoint_configured = isinstance(endpoint_url, str) and endpoint_url.strip().startswith(("http://", "https://"))
    token_valid = is_valid_worker_render_token(token)
    token_present = token_valid
    token_source = "integration_owned" if token_valid else ("invalid" if isinstance(token, str) and token.strip() else "missing")

    if not endpoint_configured:
        status = "disabled"
        readiness_code = "worker_endpoint_missing"
        warnings = ["worker_endpoint_not_configured", "worker_renderer_disabled"]
    elif not token_valid:
        status = "not_ready"
        readiness_code = "worker_token_missing" if token_source == "missing" else "worker_token_invalid"
        warnings = [readiness_code, "worker_renderer_disabled"]
    else:
        status = "ready"
        readiness_code = "worker_ready"
        warnings = ["worker_token_redacted"]

    return {
        "readiness_id": f"{entry_id}-worker-readiness-001",
        "config_entry_id": entry_id,
        "status": status,
        "code": code or readiness_code,
        "worker": {
            "type": "http_json_worker",
            "role": "renderer",
            "endpoint_url": endpoint_url.strip() if endpoint_configured else None,
            "endpoint_configured": endpoint_configured,
            "api_version": WORKER_TRANSPORT_VERSION,
            "render_path": WORKER_RENDER_PATH,
        },
        "token": {
            "present": token_present,
            "source": token_source,
            "authorization": redact_authorization(f"Bearer {token}") if token_valid else "<missing>",
        },
        "validation": {
            "status": "pass",
            "summary": "Worker token readiness validates before storage.",
            "checks": [
                {
                    "name": "worker_endpoint_configured",
                    "status": "pass" if endpoint_configured else "not_configured",
                },
                {
                    "name": "integration_owned_worker_token",
                    "status": "pass" if token_valid else token_source,
                },
                {
                    "name": "worker_authorization_redacted",
                    "status": "pass",
                },
            ],
        },
        "warnings": warnings,
        "orchestration": worker_readiness_side_effects(
            token_generated=token_generated,
            token_stored=token_stored,
            readiness_bookkeeping_written=True,
            worker_renderer_setup_gated=True,
        ),
    }


def _worker_endpoint_url(entry: Any) -> str | None:
    config_data = getattr(entry, "data", {}) or {}
    value = config_data.get("worker_endpoint_url") if isinstance(config_data, dict) else None
    return value if isinstance(value, str) and value.strip() else None


def _generate_worker_token() -> str:
    return secrets.token_urlsafe(DEFAULT_WORKER_TOKEN_BYTES)


def _readiness_rejection(code: str) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": code,
        "enabled": False,
        "orchestration": worker_readiness_side_effects(),
    }
