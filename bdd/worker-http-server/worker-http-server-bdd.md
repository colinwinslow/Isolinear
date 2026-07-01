# Worker HTTP server: the ADR-0012 transport in front of the sandbox — BDD

## Status

Draft. Paired with
[docs/specs/worker-http-server.md](../../docs/specs/worker-http-server.md).

Evidence file:

- `bdd/worker-http-server/worker-http-server-evidence.md`

## Why this BDD exists

This pins down the standalone worker **service** (ADR-0029 packet 2): a
long-running HTTP process that speaks the ADR-0012 transport (`POST /v1/render`,
`GET /v1/health`, bearer auth, versioned headers) and drives the packet-1
codegen sandbox. It proves the server authenticates *before* running any sandbox
code, fails closed on version/schema faults, and renders a real PNG for a valid
authenticated request — the interoperable server half of the contract the
integration client already implements.

## Scenarios

### Scenario A — happy path: authenticated `POST /v1/render` returns a PNG through the real sandbox

**Given** a worker server created with a known bearer token and a `work_root`
**And** a valid transport envelope `{version: 1, operation: "render_chart",
request_id, render_request}` whose `render_request` is `render_mode: "codegen"`
with generated Python that defines `render_chart(data, output_path)` and draws a
chart
**When** the request is sent to `POST /v1/render` with `Content-Type:
application/json`, `X-Isolinear-Worker-API-Version: 1`, and `Authorization:
Bearer <known-token>`
**Then** the response is HTTP `200`
**And** the body is `{"render_result": {...}}` with `render_result.status ==
"success"`
**And** a valid PNG (correct signature) exists on disk at
`render_result.image_path`
**And** the render metadata reports the `Agg` backend
*(The matplotlib-rendering assertion is `skipUnless`-gated where the `-I` sandbox
cannot import matplotlib — the documented packet-1 dev-box limitation. A
non-matplotlib safe render that writes a verbatim PNG through the fixed output
path carries the on-disk PNG proof in every environment.)*

### Scenario B — health: authenticated `GET /v1/health` returns readiness

**Given** a worker server created with a known bearer token
**When** `GET /v1/health` is sent with `Accept: application/json`,
`X-Isolinear-Worker-API-Version: 1`, and `Authorization: Bearer <known-token>`
**Then** the response is HTTP `200`
**And** the body is `{"health": {...}}` whose object matches the `response`
sub-schema of `integration-worker-health.schema.json`
(`accepted`, `status`, `code`, `message`, `checks`, `capabilities`)
**And** when the sandbox can render, `status` is `"ready"` and
`capabilities.rendering` is `true`
**And** when the `-I` sandbox cannot import matplotlib, `status` is
`"not_ready"`, `capabilities.rendering` is `false`, and the transport still
returns HTTP `200` (readiness lives in the body, not the HTTP status)

### Scenario C — auth rejection: missing token → 401, before the sandbox

**Given** a worker server created with a known bearer token
**When** `POST /v1/render` is sent with a valid envelope and valid version
header but **no** `Authorization` header
**Then** the response is HTTP `401`
**And** the body is `{"error": {"code": "unauthorized", ...}}`
**And** no sandbox subprocess was spawned (auth is checked before any sandbox
call)
**And** the response and any log line contain no token material

### Scenario D — auth rejection: wrong token → 401, before the sandbox

**Given** a worker server created with a known bearer token
**When** `POST /v1/render` is sent with a valid envelope and version header but
`Authorization: Bearer <wrong-token>`
**Then** the response is HTTP `401` with `error.code == "unauthorized"`
**And** the comparison is constant-time and no sandbox subprocess was spawned
**And** the same rejection holds for a malformed `Authorization` value (not
`Bearer <token>`)

### Scenario E — version rejection: wrong API version header → structured 400

**Given** a worker server created with a known bearer token
**When** an **authenticated** `POST /v1/render` is sent with
`X-Isolinear-Worker-API-Version: 2` (or the header absent)
**Then** the response is HTTP `400`
**And** the body is `{"error": {"code": "unsupported_api_version", ...}}`
**And** the version is rejected before the body is parsed and before any sandbox
call
**And** the same version gate applies to `GET /v1/health`

### Scenario F — schema rejection: malformed body → structured 400, before the sandbox

**Given** a worker server created with a known bearer token
**When** an **authenticated**, correctly-versioned `POST /v1/render` is sent with
a body that is (i) not JSON, or (ii) missing/wrong `version` / `operation` /
`request_id` / `render_request` per the transport envelope schema
**Then** the response is HTTP `400`
**And** the body is `{"error": {"code": "invalid_request", ...}}` with a
non-leaking message
**And** no sandbox call is made

### Scenario G — sandbox-level failure is a 200 carrying a structured RenderResult

**Given** a worker server created with a known bearer token
**When** an authenticated, correctly-versioned, schema-valid `POST /v1/render`
carries generated code that fails the sandbox (e.g. static safety rejects it →
`unsafe_code`, or it raises at runtime → `runtime_error`)
**Then** the response is HTTP `200` (the transport succeeded)
**And** the body is `{"render_result": {...}}` with `render_result.status ==
"failed"` and `render_result.error.code` set to the inherited sandbox code
**And** the integration client, reading `payload["render_result"]`, sees the
structured failure — HTTP non-`200` is reserved for transport faults only

### Scenario H — startup fails closed without a valid token

**Given** the environment has no `ISOLINEAR_WORKER_TOKEN` (or one shorter than
the 24-char minimum)
**When** the server entry point starts
**Then** it refuses to start with a clear, non-leaking error and a non-zero exit
**And** it binds no socket and answers no request

### Scenario I — wire interoperability with the real integration client

**Given** a worker server bound on an ephemeral port with a known token
**And** the real integration `HttpJsonWorkerRenderClient` +
`build_worker_transport_request` / `build_worker_health_request` configured with
the same endpoint and token
**When** the client performs a render call and a health call across the actual
HTTP boundary
**Then** the render call returns a RenderResult the client accepts
(`render_result_received`) and the health call returns a readiness envelope the
client accepts (`health_result_received`)
**And** the raw request/response is captured with `Authorization` redacted to
`Bearer <redacted>`

## Evidence

The implementing slice produces an evidence file at
`bdd/worker-http-server/worker-http-server-evidence.md` containing the **raw**
outputs (not summaries) for each scenario: the pytest run, the on-disk PNG
verification (`file` / signature bytes), raw HTTP status + JSON bodies for the
`401` / `400` / `200` paths, the import-graph self-containment check, the
fail-closed startup output, and the wire-interop eval run with redacted
authorization.
