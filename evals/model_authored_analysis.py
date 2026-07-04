"""Local end-to-end eval for the answer channel (ADR-0031 tranche 1, packet 1).

Boots the real packet-2 `isolinear_worker.http_server` on an ephemeral port and
drives a codegen render across the actual HTTP boundary, proving the grounded
analysis answer rides render_metadata.answer_text alongside the PNG. NO CT103 /
remote host is touched.

The sample history is 71.2 and 71.8, so a render body that computes the mean and
f-strings it MUST return exactly "The average reading is 71.50 degF." — the
number is the computation, not a literal (ADR-0031 D3 grounding).

Scenarios:
  A. Grounded answer over the wire: fake model emits a body that computes the
     mean -> worker renders a real PNG AND returns the computed answer_text.
  B. Chart-only render: a body with no answer -> PNG, and render_metadata
     carries NO answer_text (the field is additive).
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
    grounded_answer_generated_python,
    safe_generated_python,
    sample_codegen_render_request,
)


KNOWN_TOKEN = "isolinear-analysis-eval-token-0123456789"  # >= 24 chars
GROUNDED_ANSWER = "The average reading is 71.50 degF."


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def _dispatch(worker_client, python_code, *, request_id):
    render_request = sample_codegen_render_request(python_code=python_code)
    transport = build_worker_transport_request(
        render_request, request_id=request_id, worker_token=KNOWN_TOKEN
    )
    return transport, worker_client.render_chart(transport)


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

            # --- A. Grounded answer over the wire ---------------------------
            transport_a, response_a = _dispatch(
                client, grounded_answer_generated_python(), request_id="analysis-eval-a"
            )
            result_a = response_a["render_result"]
            assert_true(result_a["status"] == "success", f"A failed: {result_a!r}")
            signature_a = Path(result_a["image_path"]).read_bytes()[:8].hex()
            assert_true(signature_a == PNG_SIGNATURE.hex(), "A: not a PNG")
            answer_a = result_a["render_metadata"].get("answer_text")
            assert_true(answer_a == GROUNDED_ANSWER, f"A answer not grounded: {answer_a!r}")
            print_case(
                "grounded_answer_rides_render_metadata_over_http",
                given={
                    "run_timestamp": run_timestamp,
                    "endpoint_url": endpoint_url,
                    "history_values": [71.2, 71.8],
                    "request": redacted_worker_transport_request(transport_a),
                },
                when={"operation": "generate(compute-mean body) -> POST /v1/render (render_mode=codegen)"},
                then={
                    "render_status": result_a["status"],
                    "image_signature_hex": signature_a,
                    "answer_text": answer_a,
                    "grounded": answer_a == GROUNDED_ANSWER,
                    "authorization_sent": redact_authorization(
                        transport_a["headers"]["authorization"]
                    ),
                },
            )

            # --- B. Chart-only render carries no answer ---------------------
            transport_b, response_b = _dispatch(
                client, safe_generated_python(), request_id="analysis-eval-b"
            )
            result_b = response_b["render_result"]
            assert_true(result_b["status"] == "success", f"B failed: {result_b!r}")
            signature_b = Path(result_b["image_path"]).read_bytes()[:8].hex()
            assert_true(signature_b == PNG_SIGNATURE.hex(), "B: not a PNG")
            assert_true(
                "answer_text" not in result_b["render_metadata"],
                f"B should carry no answer: {result_b['render_metadata']!r}",
            )
            print_case(
                "chart_only_render_carries_no_answer",
                given={"generated_code": "safe body, no answer_text returned"},
                when={"operation": "generate -> POST /v1/render (render_mode=codegen)"},
                then={
                    "render_status": result_b["status"],
                    "image_signature_hex": signature_b,
                    "answer_text_present": "answer_text" in result_b["render_metadata"],
                },
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    print("PASS model_authored_analysis")


if __name__ == "__main__":
    main()
