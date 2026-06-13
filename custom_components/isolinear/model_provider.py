"""Ollama-compatible model-provider planning boundary for Isolinear."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any

from .const import DOMAIN, MODEL_PROVIDER_OLLAMA_COMPATIBLE


DATA_MODEL_PROVIDER_PLANNER = "model_provider_planner"
DATA_MODEL_PROVIDER_SETUP = "model_provider_setup"

PLANNER_RESULT_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "docs" / "schemas" / "planner-result.schema.json"
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 30
MODEL_PROVIDER_HEALTH_PATH = "/api/tags"


def setup_model_provider_planner(hass: Any, entry: Any) -> dict[str, Any]:
    """Install an Ollama-compatible planner client when config-entry data exists."""
    entry_id = getattr(entry, "entry_id", "scaffold-entry")
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    config_data = getattr(entry, "data", {}) or {}
    setup = _setup_disabled(entry_id, "model_provider_config_missing")

    if _has_ollama_planner_config(config_data):
        client = OllamaCompatiblePlannerClient(
            endpoint_url=config_data["model_endpoint_url"],
            planner_model=config_data["planner_model"],
        )
        entry_data[DATA_MODEL_PROVIDER_PLANNER] = client
        setup = {
            "accepted": True,
            "code": "model_provider_planner_configured",
            "entry_id": entry_id,
            "config_entry_scoped": True,
            "enabled": True,
            "provider": client.provider_metadata(),
            "orchestration": model_provider_setup_side_effects(),
        }

    entry_data[DATA_MODEL_PROVIDER_SETUP] = setup
    return setup


def get_model_provider_planner(hass: Any, entry_id: str) -> Any | None:
    """Return the configured planner client for one config entry, if any."""
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    planner = entry_data.get(DATA_MODEL_PROVIDER_PLANNER) if isinstance(entry_data, dict) else None
    return planner if planner is not None else None


def load_planner_result_schema() -> dict[str, Any]:
    """Load the PlannerResult JSON Schema for Ollama structured output."""
    schema = json.loads(PLANNER_RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    schema.setdefault("properties", {})["chart_spec"] = {
        "type": "object",
        "required": ["chart_id", "chart_type", "title", "time_range", "series"],
        "additionalProperties": False,
        "properties": {
            "chart_id": {"type": "string"},
            "chart_type": {"enum": ["time_series"]},
            "title": {"type": "string"},
            "time_range": {
                "type": "object",
                "required": ["type", "duration"],
                "additionalProperties": False,
                "properties": {
                    "type": {"enum": ["relative"]},
                    "duration": {"type": "string"},
                },
            },
            "series": {
                "type": "array",
                "minItems": 1,
                "items": {
                "type": "object",
                "required": ["series_id", "label", "source", "role", "render_as", "transform", "unit"],
                "additionalProperties": False,
                    "properties": {
                        "series_id": {"type": "string"},
                        "label": {"type": "string"},
                        "source": {
                            "type": "object",
                            "required": ["type", "entity_id", "attribute"],
                            "additionalProperties": False,
                            "properties": {
                                "type": {"enum": ["entity"]},
                                "entity_id": {"type": "string"},
                                "attribute": {"type": ["string", "null"]},
                            },
                        },
                        "role": {"enum": ["primary", "comparison", "secondary", "annotation"]},
                        "render_as": {"enum": ["line"]},
                        "transform": {
                            "type": "object",
                            "required": ["operation", "window"],
                            "additionalProperties": False,
                            "properties": {
                                "operation": {"enum": ["none"]},
                                "window": {"type": ["string", "null"]},
                            },
                        },
                        "unit": {"type": ["string", "null"]},
                    },
                },
            },
            "overlays": {
                "type": "array",
                "items": {"type": "object"},
            },
            "x_axis": {"type": "object"},
            "y_axis": {"type": "object"},
            "notes": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
    }
    return schema


def planner_client_metadata(planner: Any) -> dict[str, str]:
    """Return schema-safe provider metadata from a planner client."""
    if hasattr(planner, "provider_metadata"):
        metadata = planner.provider_metadata()
        if isinstance(metadata, dict):
            return {
                "type": str(metadata.get("type") or MODEL_PROVIDER_OLLAMA_COMPATIBLE),
                "role": str(metadata.get("role") or "planner"),
                "endpoint_url": str(metadata.get("endpoint_url") or ""),
                "model": str(metadata.get("model") or metadata.get("planner_model") or ""),
            }

    return {
        "type": str(getattr(planner, "provider_type", MODEL_PROVIDER_OLLAMA_COMPATIBLE)),
        "role": str(getattr(planner, "role", "planner")),
        "endpoint_url": str(getattr(planner, "endpoint_url", "")),
        "model": str(getattr(planner, "planner_model", "")),
    }


def model_provider_setup_side_effects() -> dict[str, bool]:
    """Return side-effect accounting for model-provider setup."""
    return {
        "model_provider_called": False,
        "worker_called": False,
        "home_assistant_history_called": False,
        "home_assistant_service_or_state_mutation_called": False,
        "semantic_memory_called": False,
        "token_generated": False,
    }


class OllamaCompatiblePlannerClient:
    """Small stdlib client for Ollama-compatible planner chat calls."""

    provider_type = MODEL_PROVIDER_OLLAMA_COMPATIBLE
    role = "planner"

    def __init__(
        self,
        *,
        endpoint_url: str,
        planner_model: str,
        timeout_seconds: int = DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    ) -> None:
        self.endpoint_url = endpoint_url.rstrip("/")
        self.planner_model = planner_model
        self.timeout_seconds = timeout_seconds

    def provider_metadata(self) -> dict[str, str]:
        return {
            "type": self.provider_type,
            "role": self.role,
            "endpoint_url": self.endpoint_url,
            "model": self.planner_model,
        }

    def plan_chart(
        self,
        request: dict[str, Any],
        *,
        result_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call `/api/chat` with structured output and return a PlannerResult."""
        schema = result_schema or load_planner_result_schema()
        payload = self._chat_payload(request, schema)
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        http_request = urllib.request.Request(
            _ollama_chat_url(self.endpoint_url),
            data=encoded,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return _provider_failure("model_provider_http_error", str(exc), retry_safe=True)
        except (urllib.error.URLError, TimeoutError) as exc:
            return _provider_failure("model_provider_connection_error", str(exc), retry_safe=True)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            return _provider_failure("model_provider_response_error", str(exc), retry_safe=False)

        message = response_payload.get("message") if isinstance(response_payload, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            return _provider_failure("model_provider_empty_response", "Planner response content was empty.", retry_safe=True)

        try:
            planner_result = json.loads(content)
        except json.JSONDecodeError as exc:
            return _provider_failure("model_provider_non_json_response", str(exc), retry_safe=False)

        return {
            "accepted": True,
            "code": "model_provider_planner_result_received",
            "provider": self.provider_metadata(),
            "planner_result": planner_result,
            "provider_response": _provider_response_summary(response_payload),
        }

    def check_health(self, request: dict[str, Any]) -> dict[str, Any]:
        """Call the Ollama tags endpoint and return provider health metadata."""
        http_request = urllib.request.Request(
            _ollama_tags_url(self.endpoint_url),
            headers={"Accept": request.get("headers", {}).get("accept", "application/json")},
            method="GET",
        )

        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return _provider_failure("model_provider_health_http_error", str(exc), retry_safe=True)
        except (urllib.error.URLError, TimeoutError) as exc:
            return _provider_failure("model_provider_health_connection_error", str(exc), retry_safe=True)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            return _provider_failure("model_provider_health_response_error", str(exc), retry_safe=False)

        model_names = _ollama_model_names(response_payload)
        model_ready = _planner_model_is_listed(self.planner_model, model_names)
        status = "ready" if model_ready else "not_ready"
        return {
            "accepted": True,
            "code": "model_provider_health_result_received",
            "provider": self.provider_metadata(),
            "health_result": {
                "version": 1,
                "status": status,
                "code": f"model_provider_health_{status}",
                "message": (
                    "Configured planner model is available."
                    if model_ready
                    else "Configured planner model was not listed by the provider."
                ),
                "checks": [
                    {"name": "ollama_tags_endpoint", "status": "pass"},
                    {"name": "planner_model", "status": "pass" if model_ready else "not_ready"},
                ],
                "capabilities": {
                    "planning": model_ready,
                    "structured_output": model_ready,
                },
            },
            "provider_response": {
                "model_count": len(model_names),
            },
        }

    def _chat_payload(self, request: dict[str, Any], result_schema: dict[str, Any]) -> dict[str, Any]:
        prompt_payload = {
            "task": "Return one PlannerResult JSON object for an Isolinear chart plan.",
            "rules": [
                "Use only approved_entity_ids supplied in the request.",
                "Return status chart_spec_ready with a ChartSpec for this packet.",
                "The chart_spec must use chart_type, not graph_type.",
                "Each series must include series_id, label, source, role, render_as, transform, and unit.",
                "Each entity series source must be {\"type\":\"entity\",\"entity_id\":\"<approved id>\",\"attribute\":null}.",
                "Use chart_type time_series, render_as line, transform operation none, x_axis type time, and overlays [].",
                "Do not include raw Home Assistant history, secrets, worker URLs, tokens, or prose outside JSON.",
            ],
            "planner_request": deepcopy(request),
            "planner_result_schema": result_schema,
            "minimal_chart_spec_example": {
                "chart_id": "approved_entity_time_series",
                "chart_type": "time_series",
                "title": "Approved entity history",
                "time_range": {"type": "relative", "duration": "24h"},
                "series": [
                    {
                        "series_id": "approved_entity",
                        "label": "Approved Entity",
                        "source": {
                            "type": "entity",
                            "entity_id": "<one approved_entity_ids value>",
                            "attribute": None,
                        },
                        "role": "primary",
                        "render_as": "line",
                        "transform": {"operation": "none", "window": None},
                        "unit": None,
                    }
                ],
                "overlays": [],
                "x_axis": {"type": "time"},
                "y_axis": {},
                "notes": [],
            },
        }
        return {
            "model": self.planner_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are the Isolinear planner. Return only JSON that validates "
                        "against the supplied PlannerResult schema."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(prompt_payload, separators=(",", ":")),
                },
            ],
            "stream": False,
            "format": result_schema,
            "options": {
                "temperature": 0,
            },
        }


def _setup_disabled(entry_id: str, code: str) -> dict[str, Any]:
    return {
        "accepted": True,
        "code": code,
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "enabled": False,
        "provider": None,
        "orchestration": model_provider_setup_side_effects(),
    }


def _has_ollama_planner_config(config_data: Any) -> bool:
    return (
        isinstance(config_data, dict)
        and config_data.get("model_provider_type") == MODEL_PROVIDER_OLLAMA_COMPATIBLE
        and isinstance(config_data.get("model_endpoint_url"), str)
        and config_data["model_endpoint_url"].strip().startswith(("http://", "https://"))
        and isinstance(config_data.get("planner_model"), str)
        and bool(config_data["planner_model"].strip())
    )


def _ollama_chat_url(endpoint_url: str) -> str:
    if endpoint_url.rstrip("/").endswith("/api/chat"):
        return endpoint_url.rstrip("/")
    return f"{endpoint_url.rstrip('/')}/api/chat"


def _ollama_tags_url(endpoint_url: str) -> str:
    if endpoint_url.rstrip("/").endswith(MODEL_PROVIDER_HEALTH_PATH):
        return endpoint_url.rstrip("/")
    return f"{endpoint_url.rstrip('/')}{MODEL_PROVIDER_HEALTH_PATH}"


def _provider_failure(code: str, message: str, *, retry_safe: bool) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": code,
        "provider_role": "planner",
        "retry_safe": retry_safe,
        "message": message,
    }


def _provider_response_summary(response_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": response_payload.get("model"),
        "done": response_payload.get("done"),
        "done_reason": response_payload.get("done_reason"),
        "prompt_eval_count": response_payload.get("prompt_eval_count"),
        "eval_count": response_payload.get("eval_count"),
    }


def _ollama_model_names(response_payload: Any) -> list[str]:
    if not isinstance(response_payload, dict) or not isinstance(response_payload.get("models"), list):
        return []
    names: list[str] = []
    for item in response_payload["models"]:
        if not isinstance(item, dict):
            continue
        for key in ("name", "model"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                names.append(value.strip())
    return names


def _planner_model_is_listed(planner_model: str, model_names: list[str]) -> bool:
    return any(name == planner_model or name.startswith(f"{planner_model}:") for name in model_names)
