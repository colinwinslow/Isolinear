---
status: accepted
date: 2026-07-01
depends-on-adrs: [0029, 0012, 0014, 0008, 0001]
---

# Worker HTTP server: the ADR-0012 transport in front of the codegen sandbox

## Status

Accepted. Implemented in `worker/isolinear_worker/http_server.py` with unit
tests (`tests/test_worker_http_server.py`), a wire-interop eval
(`evals/worker_http_server.py`), and raw evidence at
[bdd/worker-http-server/worker-http-server-evidence.md](../../bdd/worker-http-server/worker-http-server-evidence.md).
Defines the contract surface for the standalone worker HTTP service per
ADR-0029 (revive the isolated worker for codegen evaluation), speaking the
ADR-0012 worker transport and the ADR-0014 `GET /v1/health` readiness endpoint.
This is ADR-0029 **packet 2**. It wraps the packet-1 public API
(`worker/isolinear_worker/codegen_sandbox.py`) in a long-running HTTP process;
it does not change the sandbox security model (inherited from
[worker-sandbox-spec.md](worker-sandbox-spec.md)).

## Related docs

- [bdd/worker-http-server/worker-http-server-bdd.md](../../bdd/worker-http-server/worker-http-server-bdd.md) — observable behavior
- [codegen-sandbox-module-promotion.md](codegen-sandbox-module-promotion.md) — packet 1, the public API this wraps
- [worker-sandbox-spec.md](worker-sandbox-spec.md) — the sandbox security model (inherited, unchanged)
- ADR-0012 — worker transport and authentication (the wire contract)
- ADR-0014 — worker health/readiness endpoint
- ADR-0029 — revive the worker for codegen evaluation
- [STATUS.md](../../STATUS.md) — current phase and active work

## Context

Packet 1 promoted the proven codegen sandbox into a self-contained, HA-agnostic
worker package (`worker/isolinear_worker/`) exposing `invoke_codegen_sandbox`,
`invoke_codegen_with_repair`, `default_codegen_sandbox_policy`, and
`static_safety_check`. What is still missing — the one piece ADR-0029 names as
the whole gap — is the **worker service**: a long-running process that answers
the ADR-0012 transport contract (`POST /v1/render`, `GET /v1/health`, bearer
auth, versioned headers) and drives the sandbox.

The integration side already exists and is the mirror of this contract. Its
client (`custom_components/isolinear/worker_renderer.py`) already:

- POSTs to `<endpoint>/v1/render` with headers `Content-Type: application/json`,
  `X-Isolinear-Worker-API-Version: 1`, `Authorization: Bearer <token>`, and a
  JSON **envelope body** `{version, operation, request_id, render_request}`
  (see `worker-transport-request.schema.json`);
- reads the render outcome from `payload["render_result"]` in the response;
- GETs `<endpoint>/v1/health` with `Accept: application/json`,
  `X-Isolinear-Worker-API-Version: 1`, `Authorization: Bearer <token>`, and
  reads the readiness outcome from `payload["health"]`.

So packet 2 has a fully specified wire contract on both ends already. This spec
pins the *server* side of it. Nothing here is user-visible yet; the value is a
running service that packets 3 (container image), 4 (codegen generation + repair
model), and 5 (end-to-end + reliability eval) build on.

## Framework choice

**Use the standard-library `http.server` (`ThreadingHTTPServer` +
`BaseHTTPRequestHandler`).** Justification:

- **Zero new dependencies, no new ADR.** Invariant #8 forbids silent
  framework/service adoption; `http.server` is stdlib, so packet 2 stays inside
  the existing ADRs. `worker/requirements.txt` already carries only `matplotlib`
  and `jsonschema`; adding Flask/FastAPI+uvicorn would be a new external
  dependency and, by the letter of invariant #8, wants its own ADR. It also
  bloats the packet-3 container image for no functional gain.
- **The surface is two endpoints and one auth check.** The transport is already
  fully schema-defined (`worker-transport-request.schema.json`,
  `worker-health-request.schema.json`) and the render work is entirely delegated
  to the packet-1 sandbox. There is no routing complexity, no ORM, no template
  layer, no async fan-out — nothing FastAPI/Flask would earn its weight on.
- **12-factor / HA-agnostic by construction.** `http.server` binds a plain
  socket from config; it pulls in nothing that assumes an ASGI server, an event
  loop, or a deployment framework. This keeps standalone-first honest (ADR-0029)
  and keeps the packet-3 image minimal.
- **Sandbox concurrency model fits threads.** Each render spends its time
  blocked on a `subprocess.run(...)` call inside the sandbox (the generated code
  runs in a separate `-I` process). `ThreadingHTTPServer` lets health probes and
  a small number of concurrent renders proceed without an async runtime; the CPU
  work is already out-of-process.

The cost is that we hand-write request parsing, header extraction, and JSON
error bodies — but those are small, and writing them explicitly keeps the
auth-before-sandbox ordering (below) auditable, which is the security-relevant
property here.

## Behavior contract

### Module and entry point

- New module `worker/isolinear_worker/http_server.py`.
- A factory `create_worker_app(config) -> handler/server` that is
  unit-testable **without binding a socket** (construct the request-handling
  logic and exercise it against synthetic requests), plus a thin
  `serve(config)` / `python -m isolinear_worker.http_server` entry point that
  binds the socket and calls `serve_forever()`.
- The server imports **only** the packet-1 sandbox public API and stdlib. It
  must not import from `custom_components/isolinear/` or `src/Isolinear/`
  (invariant: the worker knows nothing about Home Assistant — ADR-0012/0029).

### Configuration (12-factor)

Config is read from the environment (a mounted env file is equivalent; no HA
Supervisor token or API is consulted — ADR-0029 constraint):

| Env var | Meaning | Default |
|---|---|---|
| `ISOLINEAR_WORKER_TOKEN` | Required bearer token. If unset/empty, the server refuses to start. | *(required)* |
| `ISOLINEAR_WORKER_BIND_HOST` | Bind address. | `0.0.0.0` |
| `ISOLINEAR_WORKER_BIND_PORT` | Bind port. | `8080` |
| `ISOLINEAR_WORKER_WORK_ROOT` | Directory rendered PNGs are written into (passed as `work_root` to the sandbox). | a per-process temp dir |

Startup fails closed (non-zero exit, clear message) when `ISOLINEAR_WORKER_TOKEN`
is missing or shorter than the integration's minimum (24 chars, matching
`MIN_WORKER_RENDER_TOKEN_LENGTH`). The token is never logged; log lines that
would include it emit `Bearer <redacted>` (ADR-0012 redaction).

### `GET /v1/health`

Request headers per `worker-health-request.schema.json`: `Accept:
application/json`, `X-Isolinear-Worker-API-Version: 1`, `Authorization: Bearer
<token>`.

- **Auth is checked first** (see ordering below). On success returns HTTP `200`
  with body `{"health": {...}}`, where the health object matches the
  `response` sub-object the integration validates in
  `integration-worker-health.schema.json`:
  ```json
  {
    "accepted": true,
    "status": "ready",
    "code": "worker_ready",
    "message": "Worker is ready to render.",
    "checks": [
      {"name": "sandbox_policy", "status": "ok"},
      {"name": "matplotlib_import", "status": "ok" | "unavailable"}
    ],
    "capabilities": {"rendering": true}
  }
  ```
- Readiness reflects whether the sandbox can actually render: it probes that
  `default_codegen_sandbox_policy()` loads and that the sandbox `-I` subprocess
  can import matplotlib. If matplotlib is unavailable in the `-I` subprocess
  (the dev-box limitation documented in packet 1), `status` is `not_ready`,
  `capabilities.rendering` is `false`, and the `matplotlib_import` check is
  `unavailable` — still HTTP `200` (the transport succeeded; readiness is in the
  body, matching how the integration health probe distinguishes
  ready/not_ready).

### `POST /v1/render`

Request per `worker-transport-request.schema.json`: headers `Content-Type:
application/json`, `X-Isolinear-Worker-API-Version: 1`, `Authorization: Bearer
<token>`; body envelope `{version: 1, operation: "render_chart", request_id,
render_request}`.

Processing order (each stage below is fail-closed and happens **only after the
one before it passed**):

1. **Auth** — validate the bearer token (constant-time compare). Wrong/missing →
   `401` (see below), before anything else.
2. **API version** — validate `X-Isolinear-Worker-API-Version: 1`. Mismatch →
   `400` with `error.code = "unsupported_api_version"`, before parsing the body.
3. **Envelope schema** — parse JSON and validate against
   `worker-transport-request.schema.json`'s `body` (must have `version: 1`,
   `operation: "render_chart"`, `request_id`, `render_request`). Malformed JSON
   or a body that fails validation → `400` with
   `error.code = "invalid_request"`, before touching the sandbox.
4. **Render** — call `invoke_codegen_sandbox(render_request, work_root=...)`
   from packet 1. Its returned `RenderResult` dict (already
   `render-result.schema.json`-shaped, including its own structured `error` on
   sandbox-level failures such as `unsafe_code` / `runtime_error` / `timeout` /
   `output_too_large`) is returned verbatim.

On success (transport + envelope valid, regardless of whether the *render*
succeeded or the sandbox rejected the code) the HTTP status is `200` and the
body is `{"render_result": <RenderResult>}`. A sandbox-level failure is a valid
transport outcome: the integration client reads `payload["render_result"]` and
inspects `render_result.status` / `render_result.error`, so sandbox rejections
are reported *inside* a `200`, not as an HTTP error. HTTP non-`200` is reserved
for transport-layer faults (auth, version, malformed envelope).

The PNG bytes: `invoke_codegen_sandbox` writes the PNG to `work_root` and
returns `image_path` / `image_id`. This spec returns the RenderResult as-is
(with `image_path`), matching the packet-1 contract; base64 inlining
(`image_bytes_base64`, already in `render-result.schema.json`) is **deferred**
to whichever packet wires artifact transfer end-to-end (packet 5) and is called
out as an open question below.

### Auth rejection

- Missing `Authorization` header, malformed header (not `Bearer <token>`), or a
  token that does not match `ISOLINEAR_WORKER_TOKEN` → HTTP `401` with body
  `{"error": {"code": "unauthorized", "message": "..."}}`.
- Auth is checked **before** API-version validation, before body parsing, and
  before any sandbox call, on **both** endpoints. No sandbox subprocess is ever
  spawned for an unauthenticated request (ADR-0012 consequence: "the worker must
  authenticate the request before attempting render validation or sandbox
  execution").
- Token comparison uses `hmac.compare_digest` (constant-time). The token and
  the raw `Authorization` value never appear in responses or logs.

### API version rejection

- `X-Isolinear-Worker-API-Version` absent or != `1` → HTTP `400` with
  `error.code = "unsupported_api_version"`. Checked after auth, before body
  parsing / sandbox (ADR-0012: "explicit transport versions make incompatible
  integration/worker upgrades fail closed with structured errors").

### Schema / malformed-body rejection

- Non-JSON body, wrong `Content-Type`, or a body that fails the envelope schema
  (`version`/`operation`/`request_id`/`render_request`) → HTTP `400` with
  `error.code = "invalid_request"` and a redacted, non-leaking message. No
  sandbox call is made.

### Error body shape

All transport-layer (non-`200`) errors share one shape:
```json
{"error": {"code": "<code>", "message": "<safe message>"}}
```
where `code` is one of `unauthorized`, `unsupported_api_version`,
`invalid_request`, `method_not_allowed` (wrong verb/path), or
`internal_error` (unexpected server fault; the worker still returns structured
JSON, never a stack trace, and logs the detail server-side).

## Anchor artifact

The simplest concrete observable version: start `create_worker_app` with a known
token, drive one **authenticated** `POST /v1/render` carrying a real
matplotlib-generating `render_request` through the handler, and assert the
response is `200` with `render_result.status == "success"` and a real PNG on
disk at `render_result.image_path` (valid PNG signature). This is the happy path
end to end through the HTTP layer into the packet-1 sandbox — built before the
rejection paths.

(On the dev box the `-I` sandbox cannot import matplotlib — the documented
packet-1 limitation — so the matplotlib happy-path assertion is
`skipUnless`-gated the same way packet 1 gates it, and a non-matplotlib safe
render, writing a verbatim PNG through the fixed output path, carries the
real-artifact proof in every environment.)

## Implementation order

Concrete-first:

1. **Anchor:** `create_worker_app` + the request-handling core, and a real test
   driving one authenticated `POST /v1/render` happy path through it into the
   sandbox, asserting `200` + on-disk PNG.
2. **Auth gate** (both endpoints), before version/body/sandbox; constant-time
   compare; redaction.
3. **API-version gate** and **envelope-schema gate**, with their structured
   `400`s.
4. **`GET /v1/health`** with the readiness probe (sandbox policy + matplotlib
   import check) returning the `integration-worker-health.schema.json` `response`
   shape under `{"health": ...}`.
5. **Config + entry point**: env parsing, fail-closed startup on missing/short
   token, `serve(config)` / `python -m isolinear_worker.http_server`.
6. **Real, unit-testable server tests** in `tests/` covering every BDD scenario;
   an eval (`evals/`) that boots the app on an ephemeral port and drives the
   real integration client (`HttpJsonWorkerRenderClient`) against it to prove
   the two sides interoperate on the wire.

## Proof requirements

1. Unit tests in `tests/test_worker_http_server.py` green, covering: happy-path
   render (matplotlib variant `skipUnless`-gated; non-matplotlib safe-render PNG
   unconditional), health `ready`/`not_ready`, missing-token `401`, wrong-token
   `401`, wrong/absent API-version `400`, malformed-body `400`,
   auth-before-sandbox ordering (no subprocess spawned for an unauthenticated
   request), and startup fail-closed on missing/short token.
2. BDD scenarios in
   [bdd/worker-http-server/worker-http-server-bdd.md](../../bdd/worker-http-server/worker-http-server-bdd.md)
   pass; an evidence file with **raw** outputs is written at
   `bdd/worker-http-server/worker-http-server-evidence.md`.
3. **Wire-interop proof:** an eval boots the server and drives the real
   `HttpJsonWorkerRenderClient` (and `build_worker_transport_request` /
   `build_worker_health_request`) against it, showing a successful render and a
   successful health probe cross the actual HTTP boundary (raw request/response
   captured, authorization redacted).
4. **Real-artifact proof:** a PNG produced by a render served over HTTP exists
   on disk and is a valid PNG (eyes-on confirmed).
5. **Self-containment proof:** importing `isolinear_worker.http_server` pulls in
   nothing from `custom_components/isolinear/` or `src/Isolinear/` (import-graph
   check, matching the packet-1 check).
6. Full `python3 -m pytest tests/` green; no new runtime dependency added to
   `worker/requirements.txt` (stdlib-only server).

## Non-goals

- The **container image / Dockerfile** and standalone deployment — ADR-0029
  packet 3.
- The **model codegen generation path** (planner emitting matplotlib) and a real
  **repair model** — ADR-0029 packet 4. This packet exposes
  `invoke_codegen_sandbox`; it does not call `invoke_codegen_with_repair` from
  the HTTP path yet (no repair model to inject — packet 4 decides how repair is
  driven server-side vs. integration-side).
- **Artifact byte transfer** (base64 inlining / artifact fetch endpoint)
  end-to-end into the integration's artifact store — packet 5.
- **TLS termination** (assumed handled by the deployment/reverse proxy per
  ADR-0012's `http(s)://` endpoint), **streaming progress** (ADR-0012 open),
  **multi-arch images** and **Supervisor ingress/discovery** (deferred by
  ADR-0029).
- Any change to the sandbox **security model** (inherited from
  worker-sandbox-spec.md) or the packet-1 public API.
- Home Assistant add-on packaging (a later thin wrapper over the same image,
  ADR-0029).

## References

- ADR-0012 — worker transport and authentication
- ADR-0014 — worker health/readiness endpoint
- ADR-0029 — revive worker for codegen evaluation
- ADR-0008 — read-only MVP and sandbox security
- [codegen-sandbox-module-promotion.md](codegen-sandbox-module-promotion.md) — packet 1
- [worker-sandbox-spec.md](worker-sandbox-spec.md) — sandbox security model
- [docs/schemas/worker-transport-request.schema.json](../schemas/worker-transport-request.schema.json)
- [docs/schemas/worker-health-request.schema.json](../schemas/worker-health-request.schema.json)
- [docs/schemas/render-request.schema.json](../schemas/render-request.schema.json)
- [docs/schemas/render-result.schema.json](../schemas/render-result.schema.json)
- [docs/schemas/integration-worker-health.schema.json](../schemas/integration-worker-health.schema.json)
- Client side being mirrored: `custom_components/isolinear/worker_renderer.py`
