# Worker HTTP server — evidence

**Status:** filled by the packet-2 implementing slice with **raw** outputs.
Paired with [worker-http-server-bdd.md](worker-http-server-bdd.md) and
[docs/specs/worker-http-server.md](../../docs/specs/worker-http-server.md).

**Run date:** 2026-07-01 · branch `adr-0029-worker-codegen-eval` · Python 3.12.3.

> Environment note: this dev box's `python -I` (isolated mode) cannot import
> matplotlib (user-site-only install, excluded by `-I`). The matplotlib-render
> assertion in scenario A therefore **skips**, and health reports `not_ready`
> here (both branches proven below). The non-matplotlib safe-render path writes a
> real PNG on disk and runs unconditionally.

---

## Scenario A — happy path: authenticated `POST /v1/render` returns a PNG

Rendered by an authenticated `POST /v1/render` (safe verbatim-PNG variant),
verified on disk by signature bytes:

```
image_path: /tmp/tmpz1rq0b1t/codegen-sandbox-anchor.png
size_bytes: 74
first_8_bytes_hex: 89504e470d0a1a0a
expected_png_sig_hex: 89504e470d0a1a0a
is_valid_png: True
```

Over a real socket (see raw HTTP capture below):
```
HTTP 200
{"render_result_status": "success", "image_id": "codegen-sandbox-anchor.png"}
```

The matplotlib variant (Agg backend, scenario A note) is `skipUnless`-gated on
this box and runs on a worker container where `-I` can import matplotlib
(`test_authenticated_render_matplotlib_reports_agg_backend SKIPPED`).

## Scenario B — health: authenticated `GET /v1/health` returns readiness

Raw `GET /v1/health` over a real socket — `not_ready` branch on this dev box
(HTTP 200 either way; readiness lives in the body):

```
HTTP 200
{"health": {"accepted": true, "status": "not_ready", "code": "worker_not_ready", "message": "Worker cannot render: sandbox rendering is unavailable.", "checks": [{"name": "sandbox_policy", "status": "ok"}, {"name": "matplotlib_import", "status": "unavailable"}], "capabilities": {"rendering": false}}}
```

The unit test `test_health_returns_readiness_envelope_http_200` asserts the
`ready` branch (`status == "ready"`, `capabilities.rendering == true`,
`matplotlib_import: ok`) on any environment where `-I` can import matplotlib, and
the `not_ready` branch otherwise — both keep HTTP 200. The health object matches
the `response` sub-schema of `integration-worker-health.schema.json` (keys
`accepted`, `status`, `code`, `message`, `checks`, `capabilities`).

## Scenario C — auth rejection: missing token → 401

```
HTTP 401
{"error": {"code": "unauthorized", "message": "Missing or malformed Authorization header."}}
```

`test_missing_token_is_rejected_before_sandbox` spies on
`http_server.subprocess.run` and asserts **zero** sandbox subprocesses were
spawned and that the work_root stayed empty, and that the response body contains
no token material.

## Scenario D — auth rejection: wrong / malformed token → 401

```
HTTP 401
{"error": {"code": "unauthorized", "message": "Bearer token is not authorized."}}
```

`test_wrong_and_malformed_token_are_rejected` covers wrong token, a value with no
`Bearer ` prefix, and an empty header — all 401 `unauthorized`, work_root empty.
Comparison uses `hmac.compare_digest` (constant-time).

## Scenario E — version rejection: wrong API version → 400

```
HTTP 400
{"error": {"code": "unsupported_api_version", "message": "Unsupported worker API version; expected 1."}}
```

`test_unsupported_api_version_is_rejected` asserts this for `"2"`, absent, and
`"0"` on **both** `POST /v1/render` and `GET /v1/health`, and that the work_root
stays empty (rejected before body parsing / sandbox).

## Scenario F — schema rejection: malformed body → 400

Non-JSON body over a real socket:
```
HTTP 400
{"error": {"code": "invalid_request", "message": "Request body must be valid JSON."}}
```

`test_malformed_body_is_rejected_before_sandbox` covers non-JSON, a non-object
JSON array, wrong `version`, wrong `operation`, missing `request_id`, and missing
`render_request` — all 400 `invalid_request`, work_root empty (no sandbox call).

## Scenario G — sandbox-level failure is a 200 carrying a structured RenderResult

```
HTTP 200
{"render_result_status": "failed", "error_code": "runtime_error"}
```

`test_sandbox_failure_is_reported_inside_http_200` asserts HTTP 200 for both an
`unsafe_code` static rejection and a `runtime_error` (code that raises), each
carried inside `{"render_result": {..., "status": "failed", "error": {"code":
...}}}`. HTTP non-200 is reserved for transport faults only.

## Scenario H — startup fails closed without a valid token

```
$ ISOLINEAR_WORKER_TOKEN= python3 -m isolinear_worker.http_server
isolinear worker startup failed: ISOLINEAR_WORKER_TOKEN is required; refusing to start without a bearer token.
exit=1

$ ISOLINEAR_WORKER_TOKEN=short python3 -m isolinear_worker.http_server
isolinear worker startup failed: ISOLINEAR_WORKER_TOKEN must be at least 24 characters; refusing to start with a weak token.
exit=1
```

Non-zero exit, clear non-leaking message; `serve()` is never reached, so no
socket is bound. `test_entry_point_exits_nonzero_without_token` asserts exit code
1, the `ISOLINEAR_WORKER_TOKEN` message, and that no token material leaks.

## Scenario I — wire interoperability with the real integration client

`evals/worker_http_server.py` boots the real `WorkerHTTPServer` on an ephemeral
port and drives the real `HttpJsonWorkerRenderClient` +
`build_worker_transport_request` / `build_worker_health_request` across the HTTP
boundary. Render call (authorization redacted in the captured request):

```
CASE render_result_received_over_http
  "then": {
    "authorization_sent": "Bearer <redacted>",
    "client_code": "worker_render_result_received",
    "render_result_status": "success",
    "image_signature_hex": "89504e470d0a1a0a"
  }
PASS render_result_received_over_http
```

Health call (`not_ready` branch on this dev box; request captured redacted):

```
CASE health_result_received_over_http
  "given": { "request": { "headers": { "authorization": "Bearer <redacted>", "accept": "application/json", "x_isolinear_worker_api_version": "1" }, "method": "GET", "path": "/v1/health", "protocol_version": 1 } }
  "then": {
    "authorization_sent": "Bearer <redacted>",
    "client_code": "worker_health_result_received",
    "health_result": {
      "accepted": true, "status": "not_ready", "code": "worker_not_ready",
      "checks": [{"name": "sandbox_policy", "status": "ok"},
                 {"name": "matplotlib_import", "status": "unavailable"}],
      "capabilities": {"rendering": false}
    }
  }
PASS health_result_received_over_http
PASS worker_http_server
```

The client accepts both outcomes, proving the independently-written server and
integration client interoperate on the wire.

## Self-containment (proof requirement 5)

```
$ cd worker && env PATH=/usr/bin:/bin HOME=.../.test-output \
    python3 -c "import isolinear_worker.http_server as m; print(leaked, m.__file__)"
{
  "leaked": [],
  "module_file": "/home/claude/repos/isolinear/worker/isolinear_worker/http_server.py"
}
```

Importing `isolinear_worker.http_server` pulls in nothing from
`custom_components/isolinear/` or `src/Isolinear/`
(`test_http_server_is_self_contained`).

## Suite + dependency posture (proof requirements 1, 6)

```
$ python3 -m pytest tests/test_worker_http_server.py -v
collected 12 items
... 11 passed, 1 skipped in 0.64s

$ python3 -m pytest tests/ -q
595 passed, 3 skipped in 16.56s
```

584 pre-existing + 11 new tests; skips: 2 from packet 1 + 1 new
matplotlib-render skip on this dev box.

`worker/requirements.txt` gained **no** new runtime dependency — the server is
stdlib-only (`http.server`, `hmac`, `json`), satisfying invariant #8.
Existing eval `evals/codegen_sandbox.py` still prints `PASS codegen_sandbox`.
