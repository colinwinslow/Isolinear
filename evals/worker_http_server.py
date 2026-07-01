"""Wire-interop eval for the worker HTTP server (ADR-0029 packet 2, scenario I).

Boots the real `isolinear_worker.http_server` on an ephemeral port in a
background thread and drives the *real* integration client
(`HttpJsonWorkerRenderClient` + `build_worker_transport_request` /
`build_worker_health_request`) against it across the actual HTTP boundary. This
proves the two independently-written sides interoperate on the wire. The raw
request/response is captured with `Authorization` redacted.

The server and the integration client are deliberately imported from different
package roots (`worker/` and the repo root), matching how they are deployed:
the worker knows nothing about Home Assistant.
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

from isolinear_worker.http_server import (  # noqa: E402
    WorkerConfig,
    WorkerHTTPServer,
    redact_authorization,
)

from custom_components.isolinear.worker_renderer import (  # noqa: E402
    HttpJsonWorkerRenderClient,
    build_worker_health_request,
    build_worker_transport_request,
    redacted_worker_health_request,
    redacted_worker_transport_request,
)

from codegen_sandbox_fixtures import (  # noqa: E402
    PNG_SIGNATURE,
    safe_generated_python,
    sample_codegen_render_request,
    sandbox_can_import_matplotlib,
)


KNOWN_TOKEN = "isolinear-worker-eval-token-0123456789"  # >= 24 chars


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    output_root = REPO_ROOT / ".test-output"
    output_root.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory(dir=output_root) as work_root:
        # Bind on an ephemeral port (port 0) so the eval never collides.
        config = WorkerConfig(
            token=KNOWN_TOKEN, bind_host="127.0.0.1", bind_port=0, work_root=work_root
        )
        server = WorkerHTTPServer(config)
        host, port = server.server_address[0], server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            endpoint_url = f"http://{host}:{port}"
            client = HttpJsonWorkerRenderClient(
                endpoint_url=endpoint_url, worker_token=KNOWN_TOKEN
            )

            # --- Render call across the real HTTP boundary --------------------
            render_request = sample_codegen_render_request(
                python_code=safe_generated_python()
            )
            transport_request = build_worker_transport_request(
                render_request, request_id="wire-interop-render", worker_token=KNOWN_TOKEN
            )
            render_response = client.render_chart(transport_request)

            assert_true(
                render_response["code"] == "worker_render_result_received",
                f"client rejected render response: {render_response!r}",
            )
            render_result = render_response["render_result"]
            assert_true(
                render_result["status"] == "success",
                f"render failed over the wire: {render_result!r}",
            )
            image_signature = Path(render_result["image_path"]).read_bytes()[:8].hex()
            assert_true(
                image_signature == PNG_SIGNATURE.hex(),
                "render over the wire did not produce a PNG",
            )

            print_case(
                "render_result_received_over_http",
                given={
                    "run_timestamp": run_timestamp,
                    "endpoint_url": endpoint_url,
                    "request": redacted_worker_transport_request(transport_request),
                },
                when={"operation": "HttpJsonWorkerRenderClient.render_chart"},
                then={
                    "client_code": render_response["code"],
                    "render_result_status": render_result["status"],
                    "image_signature_hex": image_signature,
                    "authorization_sent": redact_authorization(
                        transport_request["headers"]["authorization"]
                    ),
                },
            )

            # --- Health call across the real HTTP boundary --------------------
            health_request = build_worker_health_request(
                request_id="wire-interop-health", worker_token=KNOWN_TOKEN
            )
            health_response = client.check_health(health_request)

            assert_true(
                health_response["code"] == "worker_health_result_received",
                f"client rejected health response: {health_response!r}",
            )
            health_result = health_response["health_result"]
            expected_status = "ready" if sandbox_can_import_matplotlib() else "not_ready"
            assert_true(
                health_result["status"] == expected_status,
                f"health status {health_result['status']!r} != {expected_status!r}",
            )
            assert_true(
                set(health_result)
                == {"accepted", "status", "code", "message", "checks", "capabilities"},
                f"health envelope shape mismatch: {sorted(health_result)!r}",
            )

            print_case(
                "health_result_received_over_http",
                given={
                    "endpoint_url": endpoint_url,
                    "request": redacted_worker_health_request(health_request),
                },
                when={"operation": "HttpJsonWorkerRenderClient.check_health"},
                then={
                    "client_code": health_response["code"],
                    "health_result": health_result,
                    "authorization_sent": redact_authorization(
                        health_request["headers"]["authorization"]
                    ),
                },
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    print("PASS worker_http_server")


if __name__ == "__main__":
    main()
