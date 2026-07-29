"""Live proof for spec `deployment-worker-token` (ADR-0032).

Drives the REAL `HttpJsonWorkerRenderClient.check_health()` against the live
CT103 compose-managed worker with the deployment token supplied via env —
`ISOLINEAR_EVAL_WORKER_TOKEN` (from the homelab SOPS store; never committed,
never printed). Skips cleanly when the env/worker is unavailable so the eval
is safe in any environment.

Run:
    ISOLINEAR_EVAL_WORKER_TOKEN=$(sops -d .../docker-host.enc.yaml | ...) \
        python3 evals/deployment_worker_token.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from custom_components.isolinear.worker_renderer import (  # noqa: E402
    HttpJsonWorkerRenderClient,
    build_worker_health_request,
    redacted_worker_health_request,
)

WORKER_ENDPOINT = os.environ.get("ISOLINEAR_EVAL_WORKER_ENDPOINT", "http://10.0.1.46:8080")


def main() -> int:
    token = os.environ.get("ISOLINEAR_EVAL_WORKER_TOKEN", "").strip()
    if len(token) < 24:
        print("SKIP deployment_worker_token (ISOLINEAR_EVAL_WORKER_TOKEN not set)")
        return 0

    client = HttpJsonWorkerRenderClient(
        endpoint_url=WORKER_ENDPOINT, worker_token=token, timeout_seconds=10
    )
    request = build_worker_health_request(
        request_id="deployment-worker-token-eval", worker_token=token
    )
    print("request:", json.dumps(redacted_worker_health_request(request), indent=2))

    result = client.check_health(request)
    rendered = json.dumps(result, indent=2)
    if token in rendered:
        print("FAIL deployment_worker_token (token material surfaced in result)")
        return 1
    print("result:", rendered)

    if not result.get("accepted"):
        print("FAIL deployment_worker_token (health call rejected)")
        return 1
    health = result.get("health_result") or {}
    if health.get("status") != "ready":
        print("FAIL deployment_worker_token (worker not ready)")
        return 1

    # Wrong token must be a surfaced 401 fault, not an exception.
    bad = HttpJsonWorkerRenderClient(
        endpoint_url=WORKER_ENDPOINT,
        worker_token="wrong-token-000000000000000000",
        timeout_seconds=10,
    )
    bad_result = bad.check_health(
        build_worker_health_request(
            request_id="deployment-worker-token-eval-401",
            worker_token="wrong-token-000000000000000000",
        )
    )
    print("wrong-token result code:", bad_result.get("code"))
    if bad_result.get("accepted") or bad_result.get("code") != "worker_health_http_error":
        print("FAIL deployment_worker_token (wrong token did not fail closed)")
        return 1

    print("PASS deployment_worker_token")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
