from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from .contracts import ContractValidationError, validate_contract
from .dashboard_card_anchor import VALID_CARD_CONFIG, load_job_snapshots, repo_root


INTEGRATION_WS_VERSION = 1
WORKER_TRANSPORT_VERSION = 1
WORKER_RENDER_PATH = "/v1/render"
TEST_WORKER_TOKEN = "test-worker-token-000000000000"

INTEGRATION_COMMAND_TYPES = {
    "start_job": "isolinear/v1/job/start",
    "answer_clarification": "isolinear/v1/clarification/answer",
    "retry_job": "isolinear/v1/job/retry",
    "get_snapshot": "isolinear/v1/job/snapshot",
    "subscribe_job": "isolinear/v1/job/subscribe",
}

FORBIDDEN_CARD_KEYS = {
    "access_token",
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
    "worker_token",
    "worker_url",
}

FORBIDDEN_WORKER_KEYS = {
    "access_token",
    "entity_allowlist",
    "generated_image",
    "ha_token",
    "home_assistant_token",
    "long_lived_access_token",
    "model_endpoint",
    "model_url",
    "model_provider_token",
    "ollama_api_key",
    "raw_history",
    "semantic_memory",
    "worker_credentials",
    "worker_token",
}

SECRET_VALUE_PATTERN = re.compile(
    r"(home_assistant_token|long_lived_access_token|ha-token|super-secret)",
    re.IGNORECASE,
)


def sample_integration_ws_commands() -> dict[str, dict[str, Any]]:
    config_entry_id = VALID_CARD_CONFIG["config_entry_id"]
    return {
        "start_job": {
            "type": INTEGRATION_COMMAND_TYPES["start_job"],
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": config_entry_id,
            "prompt": "Compare upstairs and downstairs temperatures",
        },
        "answer_clarification": {
            "type": INTEGRATION_COMMAND_TYPES["answer_clarification"],
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": config_entry_id,
            "job_id": "job-clarify-001",
            "question_id": "clarify_upstairs_temperature",
            "option_id": "average_upstairs_temperature",
            "remember": False,
        },
        "retry_job": {
            "type": INTEGRATION_COMMAND_TYPES["retry_job"],
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": config_entry_id,
            "job_id": "job-failed-001",
        },
        "get_snapshot": {
            "type": INTEGRATION_COMMAND_TYPES["get_snapshot"],
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": config_entry_id,
            "job_id": "job-complete-001",
        },
        "subscribe_job": {
            "type": INTEGRATION_COMMAND_TYPES["subscribe_job"],
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": config_entry_id,
            "job_id": "job-complete-001",
        },
    }


def sample_render_request() -> dict[str, Any]:
    return {
        "request_id": "render-transport-001",
        "render_mode": "safe",
        "chart_spec": {
            "chart_id": "upstairs_downstairs_temperature",
            "chart_type": "time_series",
            "title": "Upstairs vs Downstairs Temperature",
            "time_range": {
                "type": "relative",
                "duration": "24h",
            },
            "series": [
                {
                    "series_id": "upstairs_temperature",
                    "label": "Upstairs Temperature",
                    "source": {
                        "type": "entity",
                        "entity_id": "sensor.upstairs_temperature",
                    },
                    "role": "primary",
                    "render_as": "line",
                    "unit": "degF",
                }
            ],
            "overlays": [],
            "notes": [],
        },
        "history_series": [
            {
                "series_id": "upstairs_temperature",
                "entity_id": "sensor.upstairs_temperature",
                "label": "Upstairs Temperature",
                "kind": "numeric",
                "unit": "degF",
                "points": [
                    {
                        "ts": "2026-06-05T08:00:00Z",
                        "value": 71.2,
                        "raw_state": "71.2",
                        "quality": "ok",
                    },
                    {
                        "ts": "2026-06-05T09:00:00Z",
                        "value": 71.8,
                        "raw_state": "71.8",
                        "quality": "ok",
                    },
                ],
                "source_entity_ids": ["sensor.upstairs_temperature"],
                "warnings": [],
            }
        ],
        "derived_intervals": [],
        "output": {
            "format": "png",
            "width": 1400,
            "height": 800,
        },
        "theme": {
            "mode": "light",
        },
        "codegen": None,
    }


def sample_worker_transport_request(token: str = TEST_WORKER_TOKEN) -> dict[str, Any]:
    return {
        "protocol_version": WORKER_TRANSPORT_VERSION,
        "method": "POST",
        "path": WORKER_RENDER_PATH,
        "headers": {
            "content_type": "application/json",
            "x_isolinear_worker_api_version": str(WORKER_TRANSPORT_VERSION),
            "authorization": f"Bearer {token}",
        },
        "body": {
            "version": WORKER_TRANSPORT_VERSION,
            "operation": "render_chart",
            "request_id": "transport-envelope-001",
            "render_request": sample_render_request(),
        },
    }


def validate_integration_ws_command(
    command: dict[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    forbidden_matches = _find_forbidden_material(command, FORBIDDEN_CARD_KEYS)
    if forbidden_matches:
        return {
            "accepted": False,
            "code": "forbidden_card_boundary_content",
            "render_attempted": False,
            "forbidden_matches": forbidden_matches,
        }

    try:
        validate_contract("integration-ws-command", command, repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_ws_command",
            "render_attempted": False,
            "error": str(exc),
        }

    return {
        "accepted": True,
        "code": "accepted",
        "render_attempted": False,
        "type": command["type"],
        "version": command["version"],
    }


def validate_worker_transport_request(
    request: dict[str, Any],
    *,
    expected_token: str = TEST_WORKER_TOKEN,
    root: Path | None = None,
) -> dict[str, Any]:
    headers = request.get("headers") if isinstance(request, dict) else None
    body = request.get("body") if isinstance(request, dict) else None
    authorization = headers.get("authorization") if isinstance(headers, dict) else None

    if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
        return _worker_rejection("missing_worker_authorization")

    if (
        not isinstance(headers, dict)
        or not isinstance(body, dict)
        or request.get("protocol_version") != WORKER_TRANSPORT_VERSION
        or headers.get("x_isolinear_worker_api_version") != str(WORKER_TRANSPORT_VERSION)
        or body.get("version") != WORKER_TRANSPORT_VERSION
    ):
        return _worker_rejection("unsupported_worker_api_version")

    expected_header = f"Bearer {expected_token}"
    if authorization != expected_header:
        return _worker_rejection("unauthorized_worker_request")

    forbidden_matches = _find_forbidden_material(request, FORBIDDEN_WORKER_KEYS)
    if forbidden_matches:
        return {
            "accepted": False,
            "code": "forbidden_worker_boundary_content",
            "render_attempted": False,
            "authorization": _redact_authorization(authorization),
            "forbidden_matches": forbidden_matches,
        }

    try:
        validate_contract("worker-transport-request", request, repo_root=root)
        validate_contract("render-request", body["render_request"], repo_root=root)
        validate_contract("chart-spec", body["render_request"]["chart_spec"], repo_root=root)
        for series in body["render_request"]["history_series"]:
            validate_contract("history-series", series, repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "invalid_worker_transport_request",
            "render_attempted": False,
            "authorization": _redact_authorization(authorization),
            "error": str(exc),
        }

    return {
        "accepted": True,
        "code": "accepted",
        "render_attempted": True,
        "authorization": _redact_authorization(authorization),
        "path": request["path"],
        "operation": body["operation"],
        "render_request_id": body["render_request"]["request_id"],
    }


def redacted_worker_transport_request(request: dict[str, Any]) -> dict[str, Any]:
    redacted = copy.deepcopy(request)
    headers = redacted.get("headers")
    if isinstance(headers, dict) and "authorization" in headers:
        headers["authorization"] = _redact_authorization(headers["authorization"])
    return redacted


def worker_rejection_examples() -> dict[str, dict[str, Any]]:
    missing_auth = sample_worker_transport_request()
    del missing_auth["headers"]["authorization"]

    bad_token = sample_worker_transport_request(token="wrong-worker-token-000000000")

    wrong_version = sample_worker_transport_request()
    wrong_version["protocol_version"] = 2
    wrong_version["headers"]["x_isolinear_worker_api_version"] = "2"
    wrong_version["body"]["version"] = 2

    leaked_home_assistant_token = sample_worker_transport_request()
    leaked_home_assistant_token["body"]["render_request"]["theme"] = {
        "home_assistant_token": "super-secret-home-assistant-token",
    }

    return {
        "missing_auth": missing_auth,
        "bad_token": bad_token,
        "wrong_version": wrong_version,
        "leaked_home_assistant_token": leaked_home_assistant_token,
    }


def validate_fixture_snapshots(root: Path | None = None) -> dict[str, Any]:
    snapshots = load_job_snapshots(root)
    results = {}
    for state, snapshot in snapshots.items():
        try:
            validate_contract("integration-job-snapshot", snapshot, repo_root=root)
        except ContractValidationError as exc:
            results[state] = {
                "accepted": False,
                "code": "invalid_integration_job_snapshot",
                "error": str(exc),
            }
        else:
            results[state] = {
                "accepted": True,
                "code": "accepted",
                "status": snapshot["status"],
            }
    return results


def verify_transport_auth_anchor(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    commands = sample_integration_ws_commands()
    command_results = {
        name: validate_integration_ws_command(command, root=root)
        for name, command in commands.items()
    }
    snapshots = validate_fixture_snapshots(root)

    valid_worker_request = sample_worker_transport_request()
    valid_worker_result = validate_worker_transport_request(valid_worker_request, root=root)
    rejection_results = {
        name: validate_worker_transport_request(example, root=root)
        for name, example in worker_rejection_examples().items()
    }

    invalid_card_command = copy.deepcopy(commands["start_job"])
    invalid_card_command["worker_url"] = "http://worker.local:8765"
    invalid_card_command_result = validate_integration_ws_command(invalid_card_command, root=root)

    evidence_payload = {
        "redacted_worker_request": redacted_worker_transport_request(valid_worker_request),
        "valid_worker_result": valid_worker_result,
        "rejection_results": rejection_results,
    }
    evidence_json = json.dumps(evidence_payload, sort_keys=True)

    failures = []
    if not all(result["accepted"] for result in command_results.values()):
        failures.append("One or more integration WebSocket commands failed schema validation.")
    if not all(result["type"].startswith("isolinear/v1/") for result in command_results.values() if result["accepted"]):
        failures.append("One or more integration WebSocket commands are outside isolinear/v1/.")
    if not all(result["accepted"] for result in snapshots.values()):
        failures.append("One or more integration job snapshots failed schema validation.")
    if not valid_worker_result["accepted"]:
        failures.append("The valid worker transport request was rejected.")
    if not all(not result["accepted"] for result in rejection_results.values()):
        failures.append("One or more invalid worker transport examples were accepted.")
    if invalid_card_command_result["accepted"]:
        failures.append("A card command containing a worker URL was accepted.")
    if TEST_WORKER_TOKEN in evidence_json or "super-secret-home-assistant-token" in evidence_json:
        failures.append("Evidence payload leaked token material.")

    return {
        "passed": not failures,
        "failures": failures,
        "commands": commands,
        "command_results": command_results,
        "snapshot_results": snapshots,
        "valid_worker_request": redacted_worker_transport_request(valid_worker_request),
        "valid_worker_result": valid_worker_result,
        "rejection_results": rejection_results,
        "invalid_card_command_result": invalid_card_command_result,
        "evidence_redaction": {
            "worker_token_redacted": TEST_WORKER_TOKEN not in evidence_json,
            "home_assistant_token_redacted": "super-secret-home-assistant-token" not in evidence_json,
        },
    }


def _worker_rejection(code: str) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": code,
        "render_attempted": False,
    }


def _redact_authorization(value: Any) -> str:
    if isinstance(value, str) and value.startswith("Bearer "):
        return "Bearer <redacted>"
    return "<missing>"


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
            normalized_key = key.lower()
            if normalized_key in forbidden_keys:
                matches.append({"path": child_path, "reason": "forbidden_key"})
                continue
            _walk_forbidden_material(value, forbidden_keys, child_path, matches)
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            _walk_forbidden_material(item, forbidden_keys, f"{path}[{index}]", matches)
    elif (
        isinstance(payload, str)
        and path != "$.headers.authorization"
        and SECRET_VALUE_PATTERN.search(payload)
    ):
        matches.append({"path": path, "reason": "secret_like_value"})
