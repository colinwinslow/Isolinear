"""Real tests for the standalone worker HTTP server (ADR-0029 packet 2).

Drives `isolinear_worker.http_server` through its socket-free request-handling
core (`WorkerApp`) and its `http.server` glue, proving parity with the accepted
worker-http-server BDD (scenarios A-I): authenticated render happy path,
readiness health, auth-before-sandbox ordering, version/schema fail-closed
gates, sandbox failure reported inside a 200, fail-closed startup, and
self-containment.

Environment note (same as packet 1): the sandbox runs generated code under
`python -I`, which excludes the user site. The matplotlib happy-path assertion
is `skipUnless`-gated; a non-matplotlib safe render (verbatim PNG through the
fixed output path) carries the real-artifact proof in every environment.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from http import HTTPStatus
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKER_DIR = REPO_ROOT / "worker"
sys.path.insert(0, str(WORKER_DIR))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from isolinear_worker import http_server  # noqa: E402
from isolinear_worker.http_server import (  # noqa: E402
    WorkerConfig,
    WorkerConfigError,
    create_worker_app,
    load_config_from_env,
)

from codegen_sandbox_fixtures import (  # noqa: E402
    PNG_SIGNATURE,
    broken_generated_python,
    matplotlib_generated_python,
    safe_generated_python,
    sample_codegen_render_request,
    sandbox_can_import_matplotlib,
    unsafe_generated_python_examples,
)


_SANDBOX_HAS_MATPLOTLIB = sandbox_can_import_matplotlib()
_NO_MATPLOTLIB_REASON = (
    "sandbox `python -I` cannot import matplotlib in this environment "
    "(user-site install excluded by isolated mode); runs on a worker container"
)

KNOWN_TOKEN = "isolinear-worker-test-token-0123456789"  # >= 24 chars
WRONG_TOKEN = "isolinear-worker-wrong-token-9876543210"


def _envelope(python_code: str) -> dict:
    return {
        "version": 1,
        "operation": "render_chart",
        "request_id": "http-server-anchor",
        "render_request": sample_codegen_render_request(python_code=python_code),
    }


class WorkerHTTPServerCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (REPO_ROOT / ".test-output").mkdir(exist_ok=True)

    def _app(self, work_root: str):
        return create_worker_app(WorkerConfig(token=KNOWN_TOKEN, work_root=work_root))

    def _run_dir(self):
        return tempfile.TemporaryDirectory(dir=REPO_ROOT / ".test-output")

    # Scenario A (anchor) — authenticated POST /v1/render writes a real PNG.
    def test_authenticated_render_writes_real_png_safe_variant(self):
        with self._run_dir() as run_directory:
            app = self._app(run_directory)
            response = app.handle_render(
                authorization=f"Bearer {KNOWN_TOKEN}",
                api_version="1",
                raw_body=json.dumps(_envelope(safe_generated_python())).encode("utf-8"),
            )
            render_result = response.body["render_result"]
            image_bytes = Path(render_result["image_path"]).read_bytes()

        self.assertEqual(response.status, HTTPStatus.OK)
        self.assertEqual(render_result["status"], "success", render_result.get("error"))
        self.assertEqual(image_bytes[:8], PNG_SIGNATURE)

    # Scenario A — matplotlib variant, Agg backend reported (skipUnless-gated).
    @unittest.skipUnless(_SANDBOX_HAS_MATPLOTLIB, _NO_MATPLOTLIB_REASON)
    def test_authenticated_render_matplotlib_reports_agg_backend(self):
        with self._run_dir() as run_directory:
            app = self._app(run_directory)
            response = app.handle_render(
                authorization=f"Bearer {KNOWN_TOKEN}",
                api_version="1",
                raw_body=json.dumps(
                    _envelope(matplotlib_generated_python())
                ).encode("utf-8"),
            )
            render_result = response.body["render_result"]
            image_bytes = Path(render_result["image_path"]).read_bytes()

        self.assertEqual(response.status, HTTPStatus.OK)
        self.assertEqual(render_result["status"], "success", render_result.get("error"))
        self.assertEqual(image_bytes[:8], PNG_SIGNATURE)
        self.assertIn(
            "matplotlib_backend:Agg", render_result["render_metadata"]["warnings"]
        )

    # Scenario B — health returns readiness; both branches are valid HTTP 200.
    def test_health_returns_readiness_envelope_http_200(self):
        with self._run_dir() as run_directory:
            app = self._app(run_directory)
            response = app.handle_health(
                authorization=f"Bearer {KNOWN_TOKEN}", api_version="1"
            )

        self.assertEqual(response.status, HTTPStatus.OK)
        health = response.body["health"]
        self.assertEqual(
            sorted(health),
            ["accepted", "capabilities", "checks", "code", "message", "status"],
        )
        self.assertTrue(health["accepted"])
        check_names = {check["name"] for check in health["checks"]}
        self.assertEqual(check_names, {"sandbox_policy", "matplotlib_import"})

        if _SANDBOX_HAS_MATPLOTLIB:
            self.assertEqual(health["status"], "ready")
            self.assertTrue(health["capabilities"]["rendering"])
        else:
            self.assertEqual(health["status"], "not_ready")
            self.assertFalse(health["capabilities"]["rendering"])
        # Either way the transport succeeded with HTTP 200 (readiness in body).

    # Scenario C — missing token → 401, no sandbox subprocess spawned.
    def test_missing_token_is_rejected_before_sandbox(self):
        subprocess_run = subprocess.run
        calls = []

        def spy(*args, **kwargs):
            calls.append(args)
            return subprocess_run(*args, **kwargs)

        with self._run_dir() as run_directory:
            app = self._app(run_directory)
            http_server.subprocess.run = spy  # type: ignore[assignment]
            try:
                response = app.handle_render(
                    authorization=None,
                    api_version="1",
                    raw_body=json.dumps(_envelope(safe_generated_python())).encode(),
                )
            finally:
                http_server.subprocess.run = subprocess_run  # type: ignore[assignment]
            self.assertEqual(list(Path(run_directory).iterdir()), [])

        self.assertEqual(response.status, HTTPStatus.UNAUTHORIZED)
        self.assertEqual(response.body["error"]["code"], "unauthorized")
        self.assertEqual(calls, [])  # no sandbox subprocess spawned
        self.assertNotIn(KNOWN_TOKEN, json.dumps(response.body))

    # Scenario D — wrong token / malformed header → 401, before the sandbox.
    def test_wrong_and_malformed_token_are_rejected(self):
        with self._run_dir() as run_directory:
            app = self._app(run_directory)
            body = json.dumps(_envelope(safe_generated_python())).encode()
            for label, authorization in (
                ("wrong_token", f"Bearer {WRONG_TOKEN}"),
                ("no_bearer_prefix", KNOWN_TOKEN),
                ("empty", ""),
            ):
                with self.subTest(label=label):
                    response = app.handle_render(
                        authorization=authorization, api_version="1", raw_body=body
                    )
                    self.assertEqual(response.status, HTTPStatus.UNAUTHORIZED)
                    self.assertEqual(response.body["error"]["code"], "unauthorized")
            self.assertEqual(list(Path(run_directory).iterdir()), [])

    # Scenario E — wrong/absent API version → 400 unsupported_api_version, on
    # both endpoints, before body parsing / sandbox.
    def test_unsupported_api_version_is_rejected(self):
        with self._run_dir() as run_directory:
            app = self._app(run_directory)
            body = json.dumps(_envelope(safe_generated_python())).encode()
            for api_version in ("2", None, "0"):
                with self.subTest(api_version=api_version):
                    render = app.handle_render(
                        authorization=f"Bearer {KNOWN_TOKEN}",
                        api_version=api_version,
                        raw_body=body,
                    )
                    self.assertEqual(render.status, HTTPStatus.BAD_REQUEST)
                    self.assertEqual(
                        render.body["error"]["code"], "unsupported_api_version"
                    )
                    health = app.handle_health(
                        authorization=f"Bearer {KNOWN_TOKEN}",
                        api_version=api_version,
                    )
                    self.assertEqual(health.status, HTTPStatus.BAD_REQUEST)
                    self.assertEqual(
                        health.body["error"]["code"], "unsupported_api_version"
                    )
            self.assertEqual(list(Path(run_directory).iterdir()), [])

    # Scenario F — malformed / schema-invalid body → 400 invalid_request, before
    # the sandbox.
    def test_malformed_body_is_rejected_before_sandbox(self):
        with self._run_dir() as run_directory:
            app = self._app(run_directory)
            cases = {
                "not_json": b"this is not json",
                "not_object": b"[1, 2, 3]",
                "wrong_version": json.dumps(
                    {**_envelope(safe_generated_python()), "version": 2}
                ).encode(),
                "wrong_operation": json.dumps(
                    {**_envelope(safe_generated_python()), "operation": "delete_all"}
                ).encode(),
                "missing_request_id": json.dumps(
                    {
                        "version": 1,
                        "operation": "render_chart",
                        "render_request": {},
                    }
                ).encode(),
                "missing_render_request": json.dumps(
                    {
                        "version": 1,
                        "operation": "render_chart",
                        "request_id": "x",
                    }
                ).encode(),
            }
            for label, raw_body in cases.items():
                with self.subTest(label=label):
                    response = app.handle_render(
                        authorization=f"Bearer {KNOWN_TOKEN}",
                        api_version="1",
                        raw_body=raw_body,
                    )
                    self.assertEqual(response.status, HTTPStatus.BAD_REQUEST)
                    self.assertEqual(
                        response.body["error"]["code"], "invalid_request"
                    )
            self.assertEqual(list(Path(run_directory).iterdir()), [])

    # Scenario G — sandbox-level failure is a 200 carrying a structured
    # RenderResult (unsafe_code and runtime_error variants).
    def test_sandbox_failure_is_reported_inside_http_200(self):
        with self._run_dir() as run_directory:
            app = self._app(run_directory)

            unsafe_code = next(iter(unsafe_generated_python_examples().values()))
            unsafe = app.handle_render(
                authorization=f"Bearer {KNOWN_TOKEN}",
                api_version="1",
                raw_body=json.dumps(_envelope(unsafe_code)).encode(),
            )
            self.assertEqual(unsafe.status, HTTPStatus.OK)
            self.assertEqual(unsafe.body["render_result"]["status"], "failed")
            self.assertEqual(
                unsafe.body["render_result"]["error"]["code"], "unsafe_code"
            )

            broken = app.handle_render(
                authorization=f"Bearer {KNOWN_TOKEN}",
                api_version="1",
                raw_body=json.dumps(
                    _envelope(broken_generated_python("boom"))
                ).encode(),
            )
            self.assertEqual(broken.status, HTTPStatus.OK)
            self.assertEqual(broken.body["render_result"]["status"], "failed")
            self.assertEqual(
                broken.body["render_result"]["error"]["code"], "runtime_error"
            )

    # Scenario H — startup fails closed without a valid token, binding no socket.
    def test_startup_fails_closed_on_missing_or_short_token(self):
        with self.assertRaises(WorkerConfigError):
            load_config_from_env({})
        with self.assertRaises(WorkerConfigError):
            load_config_from_env({"ISOLINEAR_WORKER_TOKEN": "   "})
        with self.assertRaises(WorkerConfigError):
            load_config_from_env({"ISOLINEAR_WORKER_TOKEN": "too-short"})

        # A valid token resolves without raising and never round-trips a socket.
        config = load_config_from_env({"ISOLINEAR_WORKER_TOKEN": KNOWN_TOKEN})
        self.assertEqual(config.token, KNOWN_TOKEN)
        self.assertEqual(config.bind_host, "0.0.0.0")
        self.assertEqual(config.bind_port, 8080)

    def test_entry_point_exits_nonzero_without_token(self):
        completed = subprocess.run(
            [sys.executable, "-m", "isolinear_worker.http_server"],
            cwd=str(WORKER_DIR),
            env={"PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("ISOLINEAR_WORKER_TOKEN", completed.stderr)
        # The failure message must not leak any token material.
        self.assertNotIn(KNOWN_TOKEN, completed.stderr)

    # Config resolution honors host/port overrides and rejects a bad port.
    def test_config_overrides_and_bad_port(self):
        config = load_config_from_env(
            {
                "ISOLINEAR_WORKER_TOKEN": KNOWN_TOKEN,
                "ISOLINEAR_WORKER_BIND_HOST": "127.0.0.1",
                "ISOLINEAR_WORKER_BIND_PORT": "9091",
                "ISOLINEAR_WORKER_WORK_ROOT": "/tmp/isolinear-work",
            }
        )
        self.assertEqual(config.bind_host, "127.0.0.1")
        self.assertEqual(config.bind_port, 9091)
        self.assertEqual(config.work_root, "/tmp/isolinear-work")

        with self.assertRaises(WorkerConfigError):
            load_config_from_env(
                {"ISOLINEAR_WORKER_TOKEN": KNOWN_TOKEN, "ISOLINEAR_WORKER_BIND_PORT": "nope"}
            )
        with self.assertRaises(WorkerConfigError):
            load_config_from_env(
                {"ISOLINEAR_WORKER_TOKEN": KNOWN_TOKEN, "ISOLINEAR_WORKER_BIND_PORT": "70000"}
            )

    # Self-containment — importing http_server pulls in nothing from
    # custom_components/isolinear or src/Isolinear.
    def test_http_server_is_self_contained(self):
        probe = (
            "import sys, json\n"
            "import isolinear_worker.http_server as m\n"
            "leaked = sorted(\n"
            "    name for name in sys.modules\n"
            "    if name == 'Isolinear' or name.startswith('Isolinear.')\n"
            "    or name.startswith('src.') or name.startswith('custom_components')\n"
            ")\n"
            "print(json.dumps({'leaked': leaked, 'module_file': m.__file__}))\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=str(WORKER_DIR),
            env={"PATH": "/usr/bin:/bin", "HOME": str(REPO_ROOT / ".test-output")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(payload["leaked"], [])
        self.assertIn(str(WORKER_DIR), payload["module_file"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
