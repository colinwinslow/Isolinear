"""Worker render transport boundary for the Isolinear integration."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from copy import deepcopy
from typing import Any

from .const import DOMAIN


DATA_WORKER_RENDER_CLIENT = "worker_render_client"
DATA_WORKER_RENDER_SETUP = "worker_render_setup"
DATA_WORKER_RENDER_TOKEN = "worker_render_token"

WORKER_TRANSPORT_VERSION = 1
WORKER_RENDER_PATH = "/v1/render"
DEFAULT_WORKER_TIMEOUT_SECONDS = 60


def setup_worker_renderer(hass: Any, entry: Any) -> dict[str, Any]:
    """Install a worker renderer client only when an integration-owned token exists."""
    entry_id = getattr(entry, "entry_id", "scaffold-entry")
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    existing = entry_data.get(DATA_WORKER_RENDER_CLIENT)
    if existing is not None:
        setup = _setup_enabled(entry_id, worker_client_metadata(existing), call_made=False)
        entry_data[DATA_WORKER_RENDER_SETUP] = setup
        return setup

    config_data = getattr(entry, "data", {}) or {}
    endpoint_url = config_data.get("worker_endpoint_url")
    token = entry_data.get(DATA_WORKER_RENDER_TOKEN)
    if isinstance(endpoint_url, str) and endpoint_url.strip().startswith(("http://", "https://")) and isinstance(token, str) and token.strip():
        client = HttpJsonWorkerRenderClient(endpoint_url=endpoint_url, worker_token=token)
        entry_data[DATA_WORKER_RENDER_CLIENT] = client
        setup = _setup_enabled(entry_id, client.provider_metadata(), call_made=True)
        entry_data[DATA_WORKER_RENDER_SETUP] = setup
        return setup

    setup = {
        "accepted": True,
        "code": "worker_renderer_token_missing",
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "enabled": False,
        "worker": None,
        "orchestration": worker_renderer_setup_side_effects(),
    }
    entry_data[DATA_WORKER_RENDER_SETUP] = setup
    return setup


def get_worker_render_client(hass: Any, entry_id: str) -> Any | None:
    """Return the configured worker client for one config entry, if any."""
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    client = entry_data.get(DATA_WORKER_RENDER_CLIENT) if isinstance(entry_data, dict) else None
    return client if client is not None else None


def worker_renderer_setup_side_effects() -> dict[str, bool]:
    """Return side-effect accounting for worker renderer setup."""
    return {
        "worker_called": False,
        "chart_rendering_called": False,
        "chart_artifact_written": False,
        "token_generated": False,
        "home_assistant_service_or_state_mutation_called": False,
        "semantic_memory_called": False,
    }


def build_worker_transport_request(
    render_request: dict[str, Any],
    *,
    request_id: str,
    worker_token: str,
) -> dict[str, Any]:
    """Build the ADR-0012 worker transport envelope."""
    return {
        "protocol_version": WORKER_TRANSPORT_VERSION,
        "method": "POST",
        "path": WORKER_RENDER_PATH,
        "headers": {
            "content_type": "application/json",
            "x_isolinear_worker_api_version": str(WORKER_TRANSPORT_VERSION),
            "authorization": f"Bearer {worker_token}",
        },
        "body": {
            "version": WORKER_TRANSPORT_VERSION,
            "operation": "render_chart",
            "request_id": request_id,
            "render_request": deepcopy(render_request),
        },
    }


def redacted_worker_transport_request(request: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe worker transport envelope with authorization redacted."""
    redacted = deepcopy(request)
    headers = redacted.get("headers")
    if isinstance(headers, dict):
        headers["authorization"] = redact_authorization(headers.get("authorization"))
    return redacted


def redact_authorization(value: Any) -> str:
    """Redact a worker bearer header without preserving token material."""
    if isinstance(value, str) and value.startswith("Bearer "):
        return "Bearer <redacted>"
    return "<missing>"


def worker_client_metadata(client: Any) -> dict[str, Any]:
    """Return schema-safe worker metadata from a client object."""
    if hasattr(client, "provider_metadata"):
        metadata = client.provider_metadata()
        if isinstance(metadata, dict):
            return {
                "type": str(metadata.get("type") or "http_json_worker"),
                "role": str(metadata.get("role") or "renderer"),
                "endpoint_url": str(metadata.get("endpoint_url") or ""),
                "api_version": int(metadata.get("api_version") or WORKER_TRANSPORT_VERSION),
            }

    return {
        "type": str(getattr(client, "provider_type", "http_json_worker")),
        "role": str(getattr(client, "role", "renderer")),
        "endpoint_url": str(getattr(client, "endpoint_url", "")),
        "api_version": int(getattr(client, "api_version", WORKER_TRANSPORT_VERSION)),
    }


def worker_client_token(client: Any) -> str | None:
    """Return the integration-owned worker bearer token from a client object."""
    token = getattr(client, "worker_token", None)
    if isinstance(token, str) and token.strip():
        return token
    token_method = getattr(client, "get_worker_token", None)
    if callable(token_method):
        value = token_method()
        if isinstance(value, str) and value.strip():
            return value
    return None


class HttpJsonWorkerRenderClient:
    """Small stdlib client for ADR-0012 worker render calls."""

    provider_type = "http_json_worker"
    role = "renderer"
    api_version = WORKER_TRANSPORT_VERSION

    def __init__(
        self,
        *,
        endpoint_url: str,
        worker_token: str,
        timeout_seconds: int = DEFAULT_WORKER_TIMEOUT_SECONDS,
    ) -> None:
        self.endpoint_url = endpoint_url.rstrip("/")
        self.worker_token = worker_token
        self.timeout_seconds = timeout_seconds

    def provider_metadata(self) -> dict[str, Any]:
        return {
            "type": self.provider_type,
            "role": self.role,
            "endpoint_url": self.endpoint_url,
            "api_version": self.api_version,
        }

    def render_chart(self, transport_request: dict[str, Any]) -> dict[str, Any]:
        """Call the worker render endpoint and return a RenderResult envelope."""
        headers = transport_request.get("headers", {})
        body = transport_request.get("body", {})
        encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            f"{self.endpoint_url}{WORKER_RENDER_PATH}",
            data=encoded,
            headers={
                "Content-Type": headers.get("content_type", "application/json"),
                "X-Isolinear-Worker-API-Version": headers.get("x_isolinear_worker_api_version", "1"),
                "Authorization": headers.get("authorization", ""),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return _worker_failure("worker_http_error", str(exc), retry_safe=True)
        except (urllib.error.URLError, TimeoutError) as exc:
            return _worker_failure("worker_connection_error", str(exc), retry_safe=True)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            return _worker_failure("worker_response_error", str(exc), retry_safe=False)

        render_result = payload.get("render_result") if isinstance(payload, dict) else payload
        return {
            "accepted": True,
            "code": "worker_render_result_received",
            "worker": self.provider_metadata(),
            "render_result": render_result,
        }


def _setup_enabled(entry_id: str, worker: dict[str, Any], *, call_made: bool) -> dict[str, Any]:
    return {
        "accepted": True,
        "code": "worker_renderer_configured",
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "enabled": True,
        "worker": worker,
        "call_made": call_made,
        "orchestration": worker_renderer_setup_side_effects(),
    }


def _worker_failure(code: str, message: str, *, retry_safe: bool) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": code,
        "provider_role": "renderer",
        "retry_safe": retry_safe,
        "message": message,
    }
