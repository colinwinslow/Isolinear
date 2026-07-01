"""Standalone worker HTTP server: the ADR-0012 transport in front of the sandbox.

ADR-0029 packet 2. A long-running stdlib `http.server` process that speaks the
ADR-0012 worker transport (`POST /v1/render`, `GET /v1/health`, bearer auth,
versioned headers) and drives the packet-1 codegen sandbox
(`isolinear_worker.codegen_sandbox`).

This module imports **only** the packet-1 sandbox public API and the standard
library. It must not import from `custom_components/isolinear/` or
`src/Isolinear/` — the worker knows nothing about Home Assistant
(ADR-0012 / ADR-0029). The framework is stdlib `http.server`
(`ThreadingHTTPServer` + `BaseHTTPRequestHandler`); no external web framework is
adopted (invariant #8: no silent architecture decisions).

Request processing is strictly fail-closed and ordered on every request:
auth first, then API version, then body/envelope schema, then the sandbox.
No sandbox subprocess is ever spawned for an unauthenticated request.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .codegen_sandbox import (
    default_codegen_sandbox_policy,
    invoke_codegen_sandbox,
)

LOGGER = logging.getLogger("isolinear_worker.http_server")

WORKER_API_VERSION = "1"
RENDER_PATH = "/v1/render"
HEALTH_PATH = "/v1/health"

# Matches the integration's MIN_WORKER_RENDER_TOKEN_LENGTH; the worker refuses to
# start with a shorter token so the two sides fail closed together (ADR-0012).
MIN_WORKER_TOKEN_LENGTH = 24

_ENV_TOKEN = "ISOLINEAR_WORKER_TOKEN"
_ENV_BIND_HOST = "ISOLINEAR_WORKER_BIND_HOST"
_ENV_BIND_PORT = "ISOLINEAR_WORKER_BIND_PORT"
_ENV_WORK_ROOT = "ISOLINEAR_WORKER_WORK_ROOT"

_DEFAULT_BIND_HOST = "0.0.0.0"
_DEFAULT_BIND_PORT = 8080

_MAX_REQUEST_BODY_BYTES = 5_000_000


class WorkerConfigError(ValueError):
    """Raised when the worker configuration is invalid (fail-closed startup)."""


@dataclass(frozen=True)
class WorkerConfig:
    """Resolved 12-factor configuration for the worker HTTP server."""

    token: str
    bind_host: str = _DEFAULT_BIND_HOST
    bind_port: int = _DEFAULT_BIND_PORT
    work_root: str | None = None


@dataclass(frozen=True)
class WorkerResponse:
    """A transport-layer response produced by the request-handling core."""

    status: int
    body: dict[str, Any]


def load_config_from_env(environ: dict[str, str] | None = None) -> WorkerConfig:
    """Resolve `WorkerConfig` from the environment, failing closed on bad input.

    `ISOLINEAR_WORKER_TOKEN` is required and must be at least
    `MIN_WORKER_TOKEN_LENGTH` characters; a missing/short token raises
    `WorkerConfigError` so the entry point can exit non-zero before binding a
    socket. The token is never included in the raised message.
    """

    environ = os.environ if environ is None else environ

    token = (environ.get(_ENV_TOKEN) or "").strip()
    if not token:
        raise WorkerConfigError(
            f"{_ENV_TOKEN} is required; refusing to start without a bearer token."
        )
    if len(token) < MIN_WORKER_TOKEN_LENGTH:
        raise WorkerConfigError(
            f"{_ENV_TOKEN} must be at least {MIN_WORKER_TOKEN_LENGTH} characters; "
            "refusing to start with a weak token."
        )

    bind_host = (environ.get(_ENV_BIND_HOST) or "").strip() or _DEFAULT_BIND_HOST

    bind_port_raw = (environ.get(_ENV_BIND_PORT) or "").strip()
    if bind_port_raw:
        try:
            bind_port = int(bind_port_raw)
        except ValueError as exc:
            raise WorkerConfigError(
                f"{_ENV_BIND_PORT} must be an integer; got {bind_port_raw!r}."
            ) from exc
        if not 0 < bind_port < 65536:
            raise WorkerConfigError(
                f"{_ENV_BIND_PORT} must be in 1..65535; got {bind_port}."
            )
    else:
        bind_port = _DEFAULT_BIND_PORT

    work_root = (environ.get(_ENV_WORK_ROOT) or "").strip() or None

    return WorkerConfig(
        token=token,
        bind_host=bind_host,
        bind_port=bind_port,
        work_root=work_root,
    )


class WorkerApp:
    """The socket-free request-handling core of the worker HTTP server.

    Unit-testable without binding a socket: `handle_render` / `handle_health`
    take the already-extracted request pieces (headers, raw body) and return a
    `WorkerResponse`. The `BaseHTTPRequestHandler` glue just extracts those and
    writes the JSON back out.
    """

    def __init__(self, config: WorkerConfig) -> None:
        self._config = config
        # A per-process temp dir is created lazily when no work_root is set, so
        # constructing the app (e.g. in unit tests) never leaves a stray dir.
        self._temp_work_root: tempfile.TemporaryDirectory[str] | None = None

    @property
    def config(self) -> WorkerConfig:
        return self._config

    def work_root(self) -> str:
        if self._config.work_root:
            root = Path(self._config.work_root)
            root.mkdir(parents=True, exist_ok=True)
            return str(root)
        if self._temp_work_root is None:
            self._temp_work_root = tempfile.TemporaryDirectory(
                prefix="isolinear-worker-http-"
            )
        return self._temp_work_root.name

    # -- Auth / version gates (run before body parsing, before the sandbox) ----

    def _authorize(self, authorization: str | None) -> WorkerResponse | None:
        """Return a 401 response if auth fails, else None. Constant-time compare."""
        expected = f"Bearer {self._config.token}"
        if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
            return _error_response(
                HTTPStatus.UNAUTHORIZED,
                "unauthorized",
                "Missing or malformed Authorization header.",
            )
        if not hmac.compare_digest(authorization, expected):
            return _error_response(
                HTTPStatus.UNAUTHORIZED,
                "unauthorized",
                "Bearer token is not authorized.",
            )
        return None

    def _check_api_version(self, api_version: str | None) -> WorkerResponse | None:
        if api_version != WORKER_API_VERSION:
            return _error_response(
                HTTPStatus.BAD_REQUEST,
                "unsupported_api_version",
                f"Unsupported worker API version; expected {WORKER_API_VERSION}.",
            )
        return None

    # -- Endpoint handlers -----------------------------------------------------

    def handle_render(
        self,
        *,
        authorization: str | None,
        api_version: str | None,
        raw_body: bytes,
    ) -> WorkerResponse:
        """POST /v1/render: auth → version → envelope → sandbox, fail-closed."""
        auth_failure = self._authorize(authorization)
        if auth_failure is not None:
            return auth_failure

        version_failure = self._check_api_version(api_version)
        if version_failure is not None:
            return version_failure

        envelope, envelope_failure = self._parse_render_envelope(raw_body)
        if envelope_failure is not None:
            return envelope_failure

        # Only reached for authenticated, correctly-versioned, schema-valid
        # requests: this is the single point where the sandbox is invoked.
        render_result = invoke_codegen_sandbox(
            envelope["render_request"],
            work_root=self.work_root(),
        )
        return WorkerResponse(HTTPStatus.OK, {"render_result": render_result})

    def handle_health(
        self,
        *,
        authorization: str | None,
        api_version: str | None,
    ) -> WorkerResponse:
        """GET /v1/health: auth → version → readiness probe (HTTP 200 both ways)."""
        auth_failure = self._authorize(authorization)
        if auth_failure is not None:
            return auth_failure

        version_failure = self._check_api_version(api_version)
        if version_failure is not None:
            return version_failure

        return WorkerResponse(HTTPStatus.OK, {"health": self._probe_readiness()})

    # -- Internals -------------------------------------------------------------

    def _parse_render_envelope(
        self, raw_body: bytes
    ) -> tuple[dict[str, Any] | None, WorkerResponse | None]:
        try:
            parsed = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, _error_response(
                HTTPStatus.BAD_REQUEST,
                "invalid_request",
                "Request body must be valid JSON.",
            )

        error = _validate_render_envelope(parsed)
        if error is not None:
            return None, _error_response(
                HTTPStatus.BAD_REQUEST, "invalid_request", error
            )
        return parsed, None

    def _probe_readiness(self) -> dict[str, Any]:
        checks: list[dict[str, str]] = []

        policy_ok = True
        try:
            default_codegen_sandbox_policy()
        except Exception:  # pragma: no cover - policy is a static dict today
            policy_ok = False
        checks.append(
            {"name": "sandbox_policy", "status": "ok" if policy_ok else "unavailable"}
        )

        matplotlib_ok = _sandbox_can_import_matplotlib()
        checks.append(
            {
                "name": "matplotlib_import",
                "status": "ok" if matplotlib_ok else "unavailable",
            }
        )

        ready = policy_ok and matplotlib_ok
        if ready:
            return {
                "accepted": True,
                "status": "ready",
                "code": "worker_ready",
                "message": "Worker is ready to render.",
                "checks": checks,
                "capabilities": {"rendering": True},
            }
        return {
            "accepted": True,
            "status": "not_ready",
            "code": "worker_not_ready",
            "message": "Worker cannot render: sandbox rendering is unavailable.",
            "checks": checks,
            "capabilities": {"rendering": False},
        }


def _validate_render_envelope(parsed: Any) -> str | None:
    """Return an error string if the transport envelope body is invalid, else None.

    Mirrors `worker-transport-request.schema.json`'s `body`: `version == 1`,
    `operation == "render_chart"`, a non-blank `request_id`, and a
    `render_request` object. Messages are safe (no request content echoed).
    """
    if not isinstance(parsed, dict):
        return "Request body must be a JSON object."
    if parsed.get("version") != 1:
        return "Envelope 'version' must equal 1."
    if parsed.get("operation") != "render_chart":
        return "Envelope 'operation' must equal 'render_chart'."
    request_id = parsed.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        return "Envelope 'request_id' must be a non-empty string."
    if not isinstance(parsed.get("render_request"), dict):
        return "Envelope 'render_request' must be an object."
    return None


def _error_response(status: HTTPStatus, code: str, message: str) -> WorkerResponse:
    return WorkerResponse(int(status), {"error": {"code": code, "message": message}})


def _sandbox_can_import_matplotlib() -> bool:
    """True when the sandbox subprocess (`python -I`) can import matplotlib.

    The readiness probe reflects whether the sandbox can actually render: the
    generated code runs under `-I` (isolated mode), which excludes user
    site-packages, so this probes the same interpreter/flags the sandbox uses.
    """
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-c", "import matplotlib"],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def redact_authorization(value: Any) -> str:
    """Redact a bearer header so token material never reaches logs (ADR-0012)."""
    if isinstance(value, str) and value.startswith("Bearer "):
        return "Bearer <redacted>"
    return "<missing>"


def create_worker_app(config: WorkerConfig) -> WorkerApp:
    """Factory for the socket-free request-handling core."""
    return WorkerApp(config)


class _WorkerRequestHandler(BaseHTTPRequestHandler):
    """Thin `http.server` glue: extract headers/body, delegate to `WorkerApp`."""

    server_version = "IsolinearWorker/1"
    protocol_version = "HTTP/1.1"

    @property
    def _app(self) -> WorkerApp:
        return self.server.worker_app  # type: ignore[attr-defined]

    def _headers(self) -> tuple[str | None, str | None]:
        authorization = self.headers.get("Authorization")
        api_version = self.headers.get("X-Isolinear-Worker-API-Version")
        return authorization, api_version

    def _read_body(self) -> bytes:
        length_raw = self.headers.get("Content-Length")
        if not length_raw:
            return b""
        try:
            length = int(length_raw)
        except ValueError:
            return b""
        if length < 0 or length > _MAX_REQUEST_BODY_BYTES:
            return b""
        return self.rfile.read(length)

    def _send(self, response: WorkerResponse) -> None:
        encoded = json.dumps(response.body).encode("utf-8")
        self.send_response(response.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:  # noqa: N802 - http.server naming
        authorization, api_version = self._headers()
        if self.path == RENDER_PATH:
            try:
                raw_body = self._read_body()
                response = self._app.handle_render(
                    authorization=authorization,
                    api_version=api_version,
                    raw_body=raw_body,
                )
            except Exception:  # pragma: no cover - defensive; never leak details
                LOGGER.exception("Unhandled error in POST %s", self.path)
                response = _error_response(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    "internal_error",
                    "The worker encountered an internal error.",
                )
            self._send(response)
            return
        self._send(
            _error_response(
                HTTPStatus.METHOD_NOT_ALLOWED,
                "method_not_allowed",
                "Unsupported method or path.",
            )
        )

    def do_GET(self) -> None:  # noqa: N802 - http.server naming
        authorization, api_version = self._headers()
        if self.path == HEALTH_PATH:
            try:
                response = self._app.handle_health(
                    authorization=authorization,
                    api_version=api_version,
                )
            except Exception:  # pragma: no cover - defensive; never leak details
                LOGGER.exception("Unhandled error in GET %s", self.path)
                response = _error_response(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    "internal_error",
                    "The worker encountered an internal error.",
                )
            self._send(response)
            return
        self._send(
            _error_response(
                HTTPStatus.METHOD_NOT_ALLOWED,
                "method_not_allowed",
                "Unsupported method or path.",
            )
        )

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # Route through the module logger and never emit the Authorization value.
        LOGGER.info("%s - %s", self.address_string(), format % args)


class WorkerHTTPServer(ThreadingHTTPServer):
    """`ThreadingHTTPServer` carrying the `WorkerApp` for the request handler."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, config: WorkerConfig, app: WorkerApp | None = None) -> None:
        self.worker_app = app if app is not None else create_worker_app(config)
        super().__init__((config.bind_host, config.bind_port), _WorkerRequestHandler)


def serve(config: WorkerConfig) -> None:
    """Bind the socket and serve forever. Called by the module entry point."""
    server = WorkerHTTPServer(config)
    host, port = server.server_address[0], server.server_address[1]
    LOGGER.info("Isolinear worker listening on %s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - manual shutdown
        pass
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        config = load_config_from_env()
    except WorkerConfigError as exc:
        # Fail closed: clear, non-leaking message; no socket bound.
        print(f"isolinear worker startup failed: {exc}", file=sys.stderr)
        return 1
    serve(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
