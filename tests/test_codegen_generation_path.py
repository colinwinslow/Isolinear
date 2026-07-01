"""TDD for ADR-0029 packet 4 — model codegen generation + integration repair.

Spec: docs/specs/codegen-generation-path.md
BDD:  bdd/codegen-generation-path/codegen-generation-path-bdd.md

Covers the integration side of the codegen render path, proven LOCALLY (no
CT103 / remote host):

  * config surface (codegen_enabled toggle, codegen_model default-to-planner);
  * the model-provider generate_chart_code / repair_chart_code contract
    (freeform Python, markdown-stripped, no constrained `format`) against a
    fake Ollama;
  * the integration-orchestrated repair loop in job_orchestration (generate ->
    worker /v1/render render_mode=codegen -> retryable-repair -> serve PNG, or
    fail-closed codegen_render_failed on unsafe_code / exhaustion);
  * the data boundary (no token/secret crosses into the codegen prompt).

Rendering is exercised two ways:
  * an in-process renderer that runs the *real* packet-1 sandbox and returns the
    PNG bytes base64 (so the integration can serve the artifact) — for the full
    orchestration/serving tests; and
  * a locally-booted packet-2 HTTP worker on an ephemeral port for the wire
    end-to-end anchor (base64 artifact transfer over HTTP is deferred to packet
    5, so the wire test asserts the render succeeds with a real PNG on disk).

The `-I` sandbox cannot import matplotlib on the dev box (documented packet-1
limitation); matplotlib-specific assertions are skipUnless-gated. A safe
(non-matplotlib) generated body carries the real-PNG proof everywhere.
"""

from __future__ import annotations

import base64
import json
import sys
import tempfile
import threading
import unittest
import unittest.mock
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import io


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "worker"))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from custom_components.isolinear import model_provider  # noqa: E402
from custom_components.isolinear.model_provider import (  # noqa: E402
    OllamaCompatiblePlannerClient,
    codegen_enabled,
    configured_codegen_model,
    get_model_provider_codegen,
    setup_model_provider_codegen,
    DATA_MODEL_PROVIDER_CODEGEN,
)
from custom_components.isolinear.config_schema import (  # noqa: E402
    default_options_data,
    validate_config_and_options,
    default_config_data,
)
from custom_components.isolinear.config_flow import (  # noqa: E402
    normalize_options_user_input,
    OPTIONS_FLOW_FIELDS,
)
from custom_components.isolinear.const import DOMAIN  # noqa: E402
from custom_components.isolinear.worker_renderer import (  # noqa: E402
    DATA_WORKER_RENDER_CLIENT,
    HttpJsonWorkerRenderClient,
    build_worker_transport_request,
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

from isolinear_worker.codegen_sandbox import invoke_codegen_sandbox  # noqa: E402
from isolinear_worker.http_server import WorkerConfig, WorkerHTTPServer  # noqa: E402

# Reuse the real-slice + worker-artifact harnesses.
from tests.test_first_real_vertical_slice import (  # noqa: E402
    FakeHass,
    FakeEntry,
    FakePlanner,
    configured_real_slice_hass,
    _orchestration_store,
    _snapshot_job,
    _start_job,
)


_SANDBOX_HAS_MATPLOTLIB = sandbox_can_import_matplotlib()
_NO_MATPLOTLIB_REASON = (
    "sandbox `python -I` cannot import matplotlib in this environment; "
    "runs on the worker container"
)
WORKER_TOKEN = "isolinear-codegen-path-token-0123456789"  # >= 24 chars


class _FakeUrlopenCtx:
    def __init__(self, fp: io.BytesIO) -> None:
        self._fp = fp

    def __enter__(self):
        return self._fp

    def __exit__(self, *exc):
        return False


# ---------------------------------------------------------------------------
# 1. Config surface: codegen_enabled toggle + codegen_model default-to-planner.
# ---------------------------------------------------------------------------
class CodegenConfigSurfaceTests(unittest.TestCase):
    def test_codegen_enabled_defaults_false(self):
        self.assertFalse(default_options_data()["codegen_enabled"])

    def test_codegen_enabled_is_an_options_field(self):
        self.assertIn("codegen_enabled", OPTIONS_FLOW_FIELDS)

    def test_valid_options_accept_codegen_enabled_true(self):
        options = {**default_options_data(), "codegen_enabled": True}
        result = validate_config_and_options(default_config_data(), options)
        self.assertTrue(result["accepted"], result)
        self.assertTrue(result["options"].codegen_enabled)

    def test_non_boolean_codegen_enabled_rejected(self):
        options = {**default_options_data(), "codegen_enabled": "yes-please"}
        result = validate_config_and_options(default_config_data(), options)
        self.assertFalse(result["accepted"], result)
        self.assertTrue(
            any(e["path"] == "$.options_data.codegen_enabled" for e in result["errors"]),
            result,
        )

    def test_options_form_normalizes_string_boolean(self):
        options = normalize_options_user_input(
            {
                "default_render_mode": "safe",
                "max_codegen_repair_attempts": 1,
                "codegen_enabled": "true",
                "entity_allowlist": [],
            }
        )
        self.assertIs(options["codegen_enabled"], True)

    def test_codegen_helper_reads_toggle(self):
        self.assertTrue(codegen_enabled({"codegen_enabled": True}))
        self.assertFalse(codegen_enabled({"codegen_enabled": False}))
        self.assertFalse(codegen_enabled({}))

    def test_codegen_model_defaults_to_planner_when_unset(self):
        config = {**default_config_data(), "planner_model": "llama3.1", "codegen_model": None}
        self.assertEqual(configured_codegen_model(config), "llama3.1")

    def test_codegen_model_honored_when_set(self):
        config = {
            **default_config_data(),
            "planner_model": "llama3.1",
            "codegen_model": "qwen2.5-coder",
        }
        self.assertEqual(configured_codegen_model(config), "qwen2.5-coder")


class CodegenSetupTests(unittest.TestCase):
    def _entry(self, *, codegen_enabled_value: bool, codegen_model: Any) -> tuple[FakeHass, FakeEntry]:
        hass = FakeHass()
        entry = FakeEntry("codegen-setup-entry")
        entry.data["codegen_model"] = codegen_model
        entry.options["codegen_enabled"] = codegen_enabled_value
        hass.data[DOMAIN].setdefault(entry.entry_id, {})["entry"] = entry
        return hass, entry

    def test_disabled_installs_no_codegen_client(self):
        hass, entry = self._entry(codegen_enabled_value=False, codegen_model=None)
        setup = setup_model_provider_codegen(hass, entry)
        self.assertFalse(setup["enabled"])
        self.assertIsNone(get_model_provider_codegen(hass, entry.entry_id))

    def test_enabled_installs_codegen_client_defaulting_to_planner(self):
        hass, entry = self._entry(codegen_enabled_value=True, codegen_model=None)
        setup = setup_model_provider_codegen(hass, entry)
        self.assertTrue(setup["enabled"], setup)
        self.assertEqual(setup["codegen_model"], entry.data["planner_model"])
        self.assertTrue(setup["codegen_model_defaulted_to_planner"])
        self.assertIsNotNone(get_model_provider_codegen(hass, entry.entry_id))

    def test_enabled_honors_separate_codegen_model(self):
        hass, entry = self._entry(codegen_enabled_value=True, codegen_model="qwen2.5-coder")
        setup = setup_model_provider_codegen(hass, entry)
        self.assertTrue(setup["enabled"], setup)
        self.assertEqual(setup["codegen_model"], "qwen2.5-coder")
        self.assertFalse(setup["codegen_model_defaulted_to_planner"])
        # The planner model is unchanged.
        self.assertEqual(entry.data["planner_model"], "llama3.1")


# ---------------------------------------------------------------------------
# 2. Model-provider generate/repair contract (fake Ollama).
# ---------------------------------------------------------------------------
class CodegenModelProviderTests(unittest.TestCase):
    def _client(self) -> OllamaCompatiblePlannerClient:
        return OllamaCompatiblePlannerClient(
            endpoint_url="http://localhost:11434", planner_model="llama3.1"
        )

    def _chat_response(self, content: str) -> bytes:
        return json.dumps({"message": {"content": content}, "done": True, "model": "llama3.1"}).encode("utf-8")

    def test_generate_chart_code_returns_stripped_freeform_code(self):
        client = self._client()
        captured: dict[str, Any] = {}
        fenced = "```python\n" + safe_generated_python() + "\n```"

        def fake_urlopen(req, timeout=None):
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return _FakeUrlopenCtx(io.BytesIO(self._chat_response(fenced)))

        with unittest.mock.patch.object(model_provider.urllib.request, "urlopen", fake_urlopen):
            result = client.generate_chart_code(sample_codegen_render_request())

        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["code"], "model_provider_chart_code_received")
        # Fences stripped, real code returned.
        self.assertTrue(result["python_code"].startswith("def render_chart"))
        self.assertNotIn("```", result["python_code"])
        # Freeform code path: no constrained-decoding `format`.
        self.assertNotIn("format", captured["body"])
        self.assertFalse(captured["body"]["stream"])
        self.assertEqual(captured["body"]["model"], "llama3.1")

    def test_generate_chart_code_uses_model_override(self):
        client = self._client()
        captured: dict[str, Any] = {}

        def fake_urlopen(req, timeout=None):
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return _FakeUrlopenCtx(io.BytesIO(self._chat_response(safe_generated_python())))

        with unittest.mock.patch.object(model_provider.urllib.request, "urlopen", fake_urlopen):
            result = client.generate_chart_code(sample_codegen_render_request(), model="qwen2.5-coder")

        self.assertEqual(captured["body"]["model"], "qwen2.5-coder")
        self.assertEqual(result["provider"]["model"], "qwen2.5-coder")
        self.assertEqual(result["provider"]["role"], "codegen")

    def test_repair_chart_code_feeds_previous_code_and_error(self):
        client = self._client()
        captured: dict[str, Any] = {}
        sandbox_error = {
            "code": "runtime_error",
            "message": "boom",
            "details": {"traceback": "Traceback (most recent call last): RuntimeError: boom"},
        }

        def fake_urlopen(req, timeout=None):
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return _FakeUrlopenCtx(io.BytesIO(self._chat_response(safe_generated_python())))

        with unittest.mock.patch.object(model_provider.urllib.request, "urlopen", fake_urlopen):
            result = client.repair_chart_code(
                broken_generated_python("boom"), sandbox_error, sample_codegen_render_request()
            )

        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["code"], "model_provider_chart_code_repaired")
        prompt = captured["body"]["messages"][1]["content"]
        # Prior code and the sandbox error/traceback are fed to the model.
        self.assertIn("boom", prompt)
        self.assertIn("runtime_error", prompt)
        self.assertIn("Traceback", prompt)

    def test_generate_empty_response_is_retry_safe_failure(self):
        client = self._client()

        def fake_urlopen(req, timeout=None):
            return _FakeUrlopenCtx(io.BytesIO(self._chat_response("   ")))

        with unittest.mock.patch.object(model_provider.urllib.request, "urlopen", fake_urlopen):
            result = client.generate_chart_code(sample_codegen_render_request())

        self.assertFalse(result["accepted"], result)
        self.assertEqual(result["code"], "model_provider_empty_response")
        self.assertTrue(result["retry_safe"])

    def test_generate_transport_error_is_provider_failure(self):
        client = self._client()

        def fake_urlopen(req, timeout=None):
            raise urllib.error.URLError("connection refused")

        with unittest.mock.patch.object(model_provider.urllib.request, "urlopen", fake_urlopen):
            result = client.generate_chart_code(sample_codegen_render_request())

        self.assertFalse(result["accepted"], result)
        self.assertEqual(result["code"], "model_provider_connection_error")

    def test_data_boundary_no_secret_in_codegen_prompt(self):
        """No HA/worker/model token or secret may cross into the codegen prompt."""
        client = self._client()
        captured: dict[str, Any] = {}
        # A request that (incorrectly) carries transport/secret material alongside
        # the chart data — the prompt projection must drop everything but the
        # validated chart_spec + render data.
        request = sample_codegen_render_request()
        request["request_id"] = "codegen-secret-req"
        request["worker_token"] = "super-secret-worker-token-should-never-cross"
        request["authorization"] = "Bearer leaked-bearer-token-value"

        def fake_urlopen(req, timeout=None):
            captured["raw"] = req.data.decode("utf-8")
            return _FakeUrlopenCtx(io.BytesIO(self._chat_response(safe_generated_python())))

        with unittest.mock.patch.object(model_provider.urllib.request, "urlopen", fake_urlopen):
            client.generate_chart_code(request)

        raw = captured["raw"]
        self.assertNotIn("super-secret-worker-token", raw)
        self.assertNotIn("leaked-bearer-token", raw)
        self.assertNotIn("codegen-secret-req", raw)
        self.assertNotIn(WORKER_TOKEN, raw)


# ---------------------------------------------------------------------------
# In-process worker that runs the REAL sandbox and returns base64 PNG bytes so
# the integration can serve the artifact. This proves the full orchestration
# (generate -> render_mode=codegen -> repair -> serve / fail-closed) without a
# socket. It mirrors HttpJsonWorkerRenderClient's response envelope.
# ---------------------------------------------------------------------------
class SandboxWorkerRenderer:
    provider_type = "http_json_worker"
    role = "renderer"
    api_version = 1

    def __init__(self) -> None:
        self.endpoint_url = "http://worker.local:8765"
        self.worker_token = WORKER_TOKEN
        self.calls: list[dict[str, Any]] = []

    def provider_metadata(self) -> dict[str, Any]:
        return {
            "type": self.provider_type,
            "role": self.role,
            "endpoint_url": self.endpoint_url,
            "api_version": self.api_version,
        }

    def render_chart(self, transport_request: dict[str, Any]) -> dict[str, Any]:
        render_request = transport_request["body"]["render_request"]
        self.calls.append(render_request)
        if render_request.get("render_mode") != "codegen":
            # Trusted safe path: return a verbatim PNG (the sandbox is codegen-
            # only). This lets the disabled-path test prove the safe path is
            # unchanged and still serves a real artifact.
            png_bytes = PNG_SIGNATURE + b"safe-worker"
            return {
                "accepted": True,
                "code": "worker_render_result_received",
                "worker": self.provider_metadata(),
                "render_result": {
                    "request_id": render_request["request_id"],
                    "status": "success",
                    "image_id": f"{render_request['request_id']}-image",
                    "image_mime_type": "image/png",
                    "image_path": f"worker://{render_request['request_id']}",
                    "image_bytes_base64": base64.b64encode(png_bytes).decode("ascii"),
                    "error": None,
                    "render_metadata": {
                        "title": render_request["chart_spec"]["title"],
                        "series_plotted": [
                            s["series_id"] for s in render_request["chart_spec"]["series"]
                        ],
                        "overlays_plotted": [],
                        "warnings": ["safe_worker"],
                        "codegen_attempts": 0,
                    },
                },
            }
        with tempfile.TemporaryDirectory() as work_root:
            render_result = invoke_codegen_sandbox(render_request, work_root=work_root)
            render_result = dict(render_result)
            image_path = render_result.get("image_path")
            if render_result.get("status") == "success" and image_path:
                png_bytes = Path(image_path).read_bytes()
                render_result["image_bytes_base64"] = base64.b64encode(png_bytes).decode("ascii")
                render_result["image_path"] = f"worker://{render_result.get('image_id')}"
        return {
            "accepted": True,
            "code": "worker_render_result_received",
            "worker": self.provider_metadata(),
            "render_result": render_result,
        }


class FakeCodegenClient:
    """Fake Ollama codegen client: scripted generation + repair, records calls."""

    def __init__(self, *, generate_code: str, repair_codes: list[str] | None = None,
                 generate_result: dict[str, Any] | None = None) -> None:
        self._generate_code = generate_code
        self._repair_codes = list(repair_codes or [])
        self._generate_result = generate_result
        self.generate_calls: list[dict[str, Any]] = []
        self.repair_calls: list[dict[str, Any]] = []

    def generate_chart_code(self, request, *, model=None):
        self.generate_calls.append({"request": request, "model": model})
        if self._generate_result is not None:
            return self._generate_result
        return {
            "accepted": True,
            "code": "model_provider_chart_code_received",
            "provider": {"type": "ollama_compatible", "role": "codegen", "model": model or "llama3.1"},
            "python_code": self._generate_code,
            "provider_response": {"model": model or "llama3.1", "done": True},
        }

    def repair_chart_code(self, previous_code, sandbox_error, request, *, model=None):
        self.repair_calls.append(
            {"previous_code": previous_code, "sandbox_error": sandbox_error, "model": model}
        )
        if not self._repair_codes:
            return {
                "accepted": False,
                "code": "model_provider_empty_response",
                "provider_role": "planner",
                "retry_safe": True,
                "message": "no repair scripted",
            }
        return {
            "accepted": True,
            "code": "model_provider_chart_code_repaired",
            "provider": {"type": "ollama_compatible", "role": "codegen", "model": model or "llama3.1"},
            "python_code": self._repair_codes.pop(0),
            "provider_response": {"model": model or "llama3.1", "done": True},
        }


def _configured_codegen_hass(
    *,
    codegen_client: Any,
    worker: Any,
    artifact_dir: Path,
    max_repair_attempts: int = 1,
    codegen_model: Any = None,
) -> tuple[FakeHass, FakeEntry]:
    hass, entry = configured_real_slice_hass(planner=FakePlanner(), artifact_dir=artifact_dir)
    entry.data["codegen_model"] = codegen_model
    entry.options["codegen_enabled"] = True
    entry.options["max_codegen_repair_attempts"] = max_repair_attempts
    entry_data = hass.data[DOMAIN][entry.entry_id]
    entry_data[DATA_WORKER_RENDER_CLIENT] = worker
    entry_data[DATA_MODEL_PROVIDER_CODEGEN] = codegen_client
    return hass, entry


# ---------------------------------------------------------------------------
# 3. Integration-orchestrated codegen render + repair loop.
# ---------------------------------------------------------------------------
class CodegenOrchestrationTests(unittest.TestCase):
    def test_disabled_leaves_trusted_path_untouched(self):
        """codegen disabled: no codegen client, render_mode stays safe (worker path)."""
        worker = SandboxWorkerRenderer()
        codegen = FakeCodegenClient(generate_code=safe_generated_python())
        with tempfile.TemporaryDirectory() as temp_dir:
            hass, entry = configured_real_slice_hass(
                planner=FakePlanner(), artifact_dir=Path(temp_dir)
            )
            entry.options["codegen_enabled"] = False
            entry_data = hass.data[DOMAIN][entry.entry_id]
            entry_data[DATA_WORKER_RENDER_CLIENT] = worker
            # No codegen client installed (disabled) -> safe path.
            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

        self.assertEqual(snapshot["snapshot"]["status"], "complete")
        # Trusted safe path: render_mode was "safe", codegen never invoked.
        self.assertEqual(worker.calls[0]["render_mode"], "safe")
        self.assertEqual(codegen.generate_calls, [])

    def test_enabled_happy_path_generates_renders_and_serves_png(self):
        worker = SandboxWorkerRenderer()
        codegen = FakeCodegenClient(generate_code=safe_generated_python())
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = _configured_codegen_hass(
                codegen_client=codegen, worker=worker, artifact_dir=artifact_dir
            )
            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertTrue(start["accepted"], start)
            self.assertEqual(snapshot["snapshot"]["status"], "complete", snapshot)
            # Codegen render path: render_mode codegen, code attached.
            self.assertEqual(len(codegen.generate_calls), 1)
            self.assertEqual(codegen.repair_calls, [])
            self.assertEqual(worker.calls[0]["render_mode"], "codegen")
            self.assertEqual(worker.calls[0]["codegen"]["python_code"], safe_generated_python())
            # A real PNG was served through the existing artifact path.
            store = _orchestration_store(hass, entry)
            artifact = store["latest_artifact"]
            artifact_path = artifact_dir / f"{artifact['artifact_id']}.png"
            self.assertTrue(artifact_path.is_file(), artifact)
            self.assertEqual(artifact_path.read_bytes()[:8], PNG_SIGNATURE)
            image_url = snapshot["snapshot"]["chart"]["image_url"]
            self.assertTrue(image_url.endswith(".png"), image_url)

    def test_retryable_failure_repairs_to_success(self):
        # First code raises at runtime (retryable); repair returns working code.
        worker = SandboxWorkerRenderer()
        codegen = FakeCodegenClient(
            generate_code=broken_generated_python("first attempt fails"),
            repair_codes=[safe_generated_python()],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = _configured_codegen_hass(
                codegen_client=codegen,
                worker=worker,
                artifact_dir=artifact_dir,
                max_repair_attempts=1,
            )
            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertEqual(snapshot["snapshot"]["status"], "complete", snapshot)
            self.assertEqual(len(codegen.generate_calls), 1)
            self.assertEqual(len(codegen.repair_calls), 1)
            # Repair was fed the retryable sandbox error.
            self.assertEqual(codegen.repair_calls[0]["sandbox_error"]["code"], "runtime_error")
            # Two dispatches: initial + repaired.
            self.assertEqual(len(worker.calls), 2)
            self.assertEqual(worker.calls[1]["codegen"]["python_code"], safe_generated_python())
            store = _orchestration_store(hass, entry)
            artifact_path = artifact_dir / f"{store['latest_artifact']['artifact_id']}.png"
            self.assertEqual(artifact_path.read_bytes()[:8], PNG_SIGNATURE)

    def test_repair_exhausted_fails_closed(self):
        # Every attempt fails at runtime; budget exhausted -> codegen_render_failed.
        worker = SandboxWorkerRenderer()
        codegen = FakeCodegenClient(
            generate_code=broken_generated_python("always fails"),
            repair_codes=[
                broken_generated_python("still fails 1"),
                broken_generated_python("still fails 2"),
            ],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            hass, entry = _configured_codegen_hass(
                codegen_client=codegen,
                worker=worker,
                artifact_dir=Path(temp_dir),
                max_repair_attempts=2,
            )
            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

        self.assertEqual(snapshot["snapshot"]["status"], "failed", snapshot)
        self.assertEqual(snapshot["snapshot"]["failure"]["code"], "codegen_render_failed")
        # initial + 2 repairs = 3 dispatches; 2 repair calls.
        self.assertEqual(len(worker.calls), 3)
        self.assertEqual(len(codegen.repair_calls), 2)
        # No silent fallback: the trusted renderer never produced this card.
        self.assertNotIn("in_process", str(snapshot["snapshot"].get("failure", {})))

    def test_unsafe_code_fails_closed_immediately_without_repair(self):
        worker = SandboxWorkerRenderer()
        unsafe_code = unsafe_generated_python_examples()["requests_import"]
        codegen = FakeCodegenClient(
            generate_code=unsafe_code,
            repair_codes=[safe_generated_python()],  # available but must NOT be used
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            hass, entry = _configured_codegen_hass(
                codegen_client=codegen,
                worker=worker,
                artifact_dir=Path(temp_dir),
                max_repair_attempts=2,
            )
            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

        self.assertEqual(snapshot["snapshot"]["status"], "failed", snapshot)
        self.assertEqual(snapshot["snapshot"]["failure"]["code"], "codegen_render_failed")
        # unsafe_code is terminal: exactly one dispatch, zero repair calls.
        self.assertEqual(len(worker.calls), 1)
        self.assertEqual(codegen.repair_calls, [])

    def test_generation_failure_fails_closed_without_dispatch(self):
        worker = SandboxWorkerRenderer()
        codegen = FakeCodegenClient(
            generate_code="",
            generate_result={
                "accepted": False,
                "code": "model_provider_connection_error",
                "provider_role": "planner",
                "retry_safe": True,
                "message": "down",
            },
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            hass, entry = _configured_codegen_hass(
                codegen_client=codegen, worker=worker, artifact_dir=Path(temp_dir)
            )
            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

        self.assertEqual(snapshot["snapshot"]["status"], "failed", snapshot)
        self.assertEqual(snapshot["snapshot"]["failure"]["code"], "codegen_render_failed")
        # Generation failed before any worker dispatch.
        self.assertEqual(worker.calls, [])

    def test_codegen_model_default_and_override_are_threaded_to_client(self):
        # Default (unset): the planner model is passed to generate_chart_code.
        worker = SandboxWorkerRenderer()
        codegen = FakeCodegenClient(generate_code=safe_generated_python())
        with tempfile.TemporaryDirectory() as temp_dir:
            hass, entry = _configured_codegen_hass(
                codegen_client=codegen, worker=worker, artifact_dir=Path(temp_dir),
                codegen_model=None,
            )
            start = _start_job(hass, entry)
            _snapshot_job(hass, entry, start["snapshot"]["job_id"])
        self.assertEqual(codegen.generate_calls[0]["model"], entry.data["planner_model"])

        # Override: the distinct codegen_model is passed.
        worker2 = SandboxWorkerRenderer()
        codegen2 = FakeCodegenClient(generate_code=safe_generated_python())
        with tempfile.TemporaryDirectory() as temp_dir:
            hass2, entry2 = _configured_codegen_hass(
                codegen_client=codegen2, worker=worker2, artifact_dir=Path(temp_dir),
                codegen_model="qwen2.5-coder",
            )
            start2 = _start_job(hass2, entry2)
            _snapshot_job(hass2, entry2, start2["snapshot"]["job_id"])
        self.assertEqual(codegen2.generate_calls[0]["model"], "qwen2.5-coder")


# ---------------------------------------------------------------------------
# 4. Local end-to-end anchor over the real packet-2 HTTP worker (ephemeral port).
#    Base64 artifact transfer over HTTP is deferred to packet 5, so this asserts
#    the generate -> dispatch -> render succeeds with a real PNG on disk.
# ---------------------------------------------------------------------------
class CodegenLocalWorkerWireTests(unittest.TestCase):
    def _boot_worker(self, work_root: str) -> tuple[WorkerHTTPServer, threading.Thread, str]:
        config = WorkerConfig(
            token=WORKER_TOKEN, bind_host="127.0.0.1", bind_port=0, work_root=work_root
        )
        server = WorkerHTTPServer(config)
        host, port = server.server_address[0], server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread, f"http://{host}:{port}"

    @unittest.skipUnless(_SANDBOX_HAS_MATPLOTLIB, _NO_MATPLOTLIB_REASON)
    def test_generated_matplotlib_renders_over_local_worker(self):
        client = OllamaCompatiblePlannerClient(
            endpoint_url="http://localhost:11434", planner_model="llama3.1"
        )
        matplotlib_code = matplotlib_generated_python()

        def fake_urlopen(req, timeout=None):
            body = json.dumps(
                {"message": {"content": matplotlib_code}, "done": True, "model": "llama3.1"}
            ).encode("utf-8")
            return _FakeUrlopenCtx(io.BytesIO(body))

        with tempfile.TemporaryDirectory() as work_root:
            server, thread, endpoint = self._boot_worker(work_root)
            try:
                # 1. Generate freeform matplotlib code from a fake model.
                with unittest.mock.patch.object(
                    model_provider.urllib.request, "urlopen", fake_urlopen
                ):
                    gen = client.generate_chart_code(sample_codegen_render_request())
                self.assertTrue(gen["accepted"], gen)

                # 2. Dispatch a render_mode=codegen request to the REAL worker.
                render_request = sample_codegen_render_request(python_code=gen["python_code"])
                transport = build_worker_transport_request(
                    render_request, request_id="codegen-wire", worker_token=WORKER_TOKEN
                )
                worker_client = HttpJsonWorkerRenderClient(
                    endpoint_url=endpoint, worker_token=WORKER_TOKEN
                )
                response = worker_client.render_chart(transport)
                self.assertEqual(response["code"], "worker_render_result_received", response)
                render_result = response["render_result"]
                self.assertEqual(render_result["status"], "success", render_result)
                png = Path(render_result["image_path"]).read_bytes()
                self.assertEqual(png[:8], PNG_SIGNATURE)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_safe_generated_body_renders_over_local_worker(self):
        """Environment-independent wire proof using the safe (non-matplotlib) body."""
        client = OllamaCompatiblePlannerClient(
            endpoint_url="http://localhost:11434", planner_model="llama3.1"
        )

        def fake_urlopen(req, timeout=None):
            body = json.dumps(
                {"message": {"content": safe_generated_python()}, "done": True, "model": "llama3.1"}
            ).encode("utf-8")
            return _FakeUrlopenCtx(io.BytesIO(body))

        with tempfile.TemporaryDirectory() as work_root:
            server, thread, endpoint = self._boot_worker(work_root)
            try:
                with unittest.mock.patch.object(
                    model_provider.urllib.request, "urlopen", fake_urlopen
                ):
                    gen = client.generate_chart_code(sample_codegen_render_request())
                render_request = sample_codegen_render_request(python_code=gen["python_code"])
                transport = build_worker_transport_request(
                    render_request, request_id="codegen-wire-safe", worker_token=WORKER_TOKEN
                )
                worker_client = HttpJsonWorkerRenderClient(
                    endpoint_url=endpoint, worker_token=WORKER_TOKEN
                )
                response = worker_client.render_chart(transport)
                render_result = response["render_result"]
                self.assertEqual(render_result["status"], "success", render_result)
                self.assertEqual(
                    Path(render_result["image_path"]).read_bytes()[:8], PNG_SIGNATURE
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
