"""Local end-to-end eval for the codegen generation path (ADR-0029 packet 4).

Boots the real packet-2 `isolinear_worker.http_server` on an ephemeral port in a
background thread and drives the *integration-side* codegen render + repair loop
against it across the actual HTTP boundary — proving the two independently-
written sides interoperate on the wire. NO CT103 / remote host is touched
(packet 5 owns the live end-to-end).

A fake Ollama supplies the generated / repaired Python (the real model call is a
packet-5 concern); the worker runs the REAL packet-1 sandbox. Base64 artifact
transfer over HTTP is deferred to packet 5, so success is proven by a real PNG
on disk at the render result's `image_path`.

Scenarios:
  A. Generation happy path: fake model emits code -> worker renders a real PNG.
  B. Retryable repair: first code fails at runtime -> integration repairs ->
     the second dispatch renders a real PNG.
  C. unsafe_code is terminal: the sandbox rejects it and no repair is issued.

The safe (non-matplotlib) generated body carries the real-PNG proof in every
environment; the `-I` sandbox cannot import matplotlib on the dev box.
"""

import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "worker"))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from evidence import print_case  # noqa: E402

from isolinear_worker.http_server import WorkerConfig, WorkerHTTPServer, redact_authorization  # noqa: E402

from custom_components.isolinear.worker_renderer import (  # noqa: E402
    HttpJsonWorkerRenderClient,
    build_worker_transport_request,
    redacted_worker_transport_request,
)

from codegen_sandbox_fixtures import (  # noqa: E402
    PNG_SIGNATURE,
    broken_generated_python,
    safe_generated_python,
    sample_codegen_render_request,
    unsafe_generated_python_examples,
)


KNOWN_TOKEN = "isolinear-codegen-eval-token-0123456789"  # >= 24 chars
CODEGEN_TERMINAL_CODES = {"unsafe_code"}


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


class FakeModel:
    """Fake Ollama codegen: scripted generation + repair, records call shapes."""

    def __init__(self, *, generate_code, repair_codes=None):
        self._generate_code = generate_code
        self._repair_codes = list(repair_codes or [])
        self.generate_calls = 0
        self.repair_calls = []

    def generate_chart_code(self, request, *, model=None):
        self.generate_calls += 1
        return {"accepted": True, "code": "model_provider_chart_code_received", "python_code": self._generate_code}

    def repair_chart_code(self, previous_code, sandbox_error, request, *, model=None):
        self.repair_calls.append(sandbox_error.get("code"))
        return {"accepted": True, "code": "model_provider_chart_code_repaired", "python_code": self._repair_codes.pop(0)}


def _dispatch(worker_client, python_code, *, request_id):
    render_request = sample_codegen_render_request(python_code=python_code)
    transport = build_worker_transport_request(
        render_request, request_id=request_id, worker_token=KNOWN_TOKEN
    )
    return transport, worker_client.render_chart(transport)


def _run_loop(worker_client, model, *, max_repair_attempts):
    """The integration-orchestrated repair loop, distilled for the eval."""
    gen = model.generate_chart_code({}, model=None)
    code = gen["python_code"]
    dispatches = []
    final_error = None
    for attempt in range(1, max_repair_attempts + 2):
        transport, response = _dispatch(worker_client, code, request_id=f"codegen-eval-{attempt}")
        render_result = response["render_result"]
        dispatches.append((transport, render_result))
        if render_result["status"] == "success":
            return {"status": "success", "dispatches": dispatches, "repairs": model.repair_calls}
        final_error = render_result["error"]["code"]
        if final_error in CODEGEN_TERMINAL_CODES:
            return {"status": "failed", "final_error": final_error, "dispatches": dispatches, "repairs": model.repair_calls}
        if attempt > max_repair_attempts:
            break
        code = model.repair_chart_code(code, render_result["error"], {}, model=None)["python_code"]
    return {"status": "failed", "final_error": final_error, "dispatches": dispatches, "repairs": model.repair_calls}


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    output_root = REPO_ROOT / ".test-output"
    output_root.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory(dir=output_root) as work_root:
        config = WorkerConfig(
            token=KNOWN_TOKEN, bind_host="127.0.0.1", bind_port=0, work_root=work_root
        )
        server = WorkerHTTPServer(config)
        host, port = server.server_address[0], server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            endpoint_url = f"http://{host}:{port}"
            client = HttpJsonWorkerRenderClient(endpoint_url=endpoint_url, worker_token=KNOWN_TOKEN)

            # --- A. Generation happy path -----------------------------------
            model_a = FakeModel(generate_code=safe_generated_python())
            outcome_a = _run_loop(client, model_a, max_repair_attempts=2)
            assert_true(outcome_a["status"] == "success", f"A failed: {outcome_a!r}")
            transport_a, result_a = outcome_a["dispatches"][-1]
            signature_a = Path(result_a["image_path"]).read_bytes()[:8].hex()
            assert_true(signature_a == PNG_SIGNATURE.hex(), "A: not a PNG")
            assert_true(model_a.generate_calls == 1 and outcome_a["repairs"] == [], "A: unexpected calls")
            print_case(
                "generation_happy_path_renders_png_over_http",
                given={
                    "run_timestamp": run_timestamp,
                    "endpoint_url": endpoint_url,
                    "generate_calls": model_a.generate_calls,
                    "request": redacted_worker_transport_request(transport_a),
                },
                when={"operation": "generate -> POST /v1/render (render_mode=codegen)"},
                then={
                    "render_status": result_a["status"],
                    "image_signature_hex": signature_a,
                    "repair_calls": outcome_a["repairs"],
                    "authorization_sent": redact_authorization(
                        transport_a["headers"]["authorization"]
                    ),
                },
            )

            # --- B. Retryable failure repairs to success --------------------
            model_b = FakeModel(
                generate_code=broken_generated_python("first attempt fails"),
                repair_codes=[safe_generated_python()],
            )
            outcome_b = _run_loop(client, model_b, max_repair_attempts=1)
            assert_true(outcome_b["status"] == "success", f"B failed: {outcome_b!r}")
            assert_true(model_b.repair_calls == ["runtime_error"], f"B repairs: {model_b.repair_calls!r}")
            assert_true(len(outcome_b["dispatches"]) == 2, "B: expected 2 dispatches")
            signature_b = Path(outcome_b["dispatches"][-1][1]["image_path"]).read_bytes()[:8].hex()
            assert_true(signature_b == PNG_SIGNATURE.hex(), "B: not a PNG")
            print_case(
                "retryable_failure_repairs_to_success",
                given={
                    "initial_error_code": "runtime_error",
                    "max_repair_attempts": 1,
                },
                when={"operation": "generate -> render(fail) -> repair -> render(success)"},
                then={
                    "dispatch_count": len(outcome_b["dispatches"]),
                    "repair_error_codes_fed": outcome_b["repairs"],
                    "final_render_status": outcome_b["dispatches"][-1][1]["status"],
                    "image_signature_hex": signature_b,
                },
            )

            # --- C. unsafe_code is terminal (no repair) ---------------------
            model_c = FakeModel(
                generate_code=unsafe_generated_python_examples()["requests_import"],
                repair_codes=[safe_generated_python()],  # available but must NOT be used
            )
            outcome_c = _run_loop(client, model_c, max_repair_attempts=2)
            assert_true(outcome_c["status"] == "failed", f"C should fail: {outcome_c!r}")
            assert_true(outcome_c["final_error"] == "unsafe_code", f"C error: {outcome_c!r}")
            assert_true(model_c.repair_calls == [], f"C must not repair: {model_c.repair_calls!r}")
            assert_true(len(outcome_c["dispatches"]) == 1, "C: exactly one dispatch")
            print_case(
                "unsafe_code_is_terminal_no_repair",
                given={"generated_code": "import requests (forbidden import)"},
                when={"operation": "generate -> render(unsafe_code)"},
                then={
                    "final_render_status": "failed",
                    "final_error_code": outcome_c["final_error"],
                    "dispatch_count": len(outcome_c["dispatches"]),
                    "repair_calls": outcome_c["repairs"],
                },
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    print("PASS codegen_generation_path")


if __name__ == "__main__":
    main()
