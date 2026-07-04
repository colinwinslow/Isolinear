# BDD: deployment-worker-token

Paired with [docs/specs/deployment-worker-token.md](../../docs/specs/deployment-worker-token.md)
(ADR-0032). Evidence:
[deployment-worker-token-evidence.md](deployment-worker-token-evidence.md).

### Scenario A — pasted token enables the worker renderer

**Given** a config entry with `worker_endpoint_url` set and no stored token
**When** the user submits a valid (≥24 char) `worker_api_token` through the
options flow
**Then** the token is persisted to the integration-owned Store, the persisted
options payload does **not** contain it, and `setup_worker_renderer` (re-run by
the options listener) produces an enabled `HttpJsonWorkerRenderClient` carrying
that token.

### Scenario B — token never echoes back

**Given** a stored worker token
**When** the options form is rendered again
**Then** the token field is empty (the form may state only *that* a token is
stored), and no snapshot, diagnostic, log line, or options payload carries the
token value.

### Scenario C — empty keeps, `clear` clears, short rejects

**Given** a stored worker token
**When** the user submits the options form with the token field empty
**Then** the stored token is unchanged;
**When** the user submits the literal `clear`
**Then** the stored token is removed and the renderer setup becomes disabled
(`worker_renderer_token_missing`);
**When** the user submits a 1–23 char value
**Then** the form errors (`worker_token_too_short`) and nothing is stored.

### Scenario D — on-demand health against a real server

**Given** an enabled client pointed at a running worker (in-process packet-2
server; live CT103 for the eval)
**When** `check_health()` runs
**Then** it returns the `/v1/health` envelope (`status: "ready"`) with bearer +
API-version headers; with a wrong token it surfaces the 401 transport fault as
a dict (no exception, no token in the surfaced fault).

### Scenario E — machinery deleted, setup chain intact

**Given** the eight ADR-0015/0016 modules and their four schemas removed
**When** `async_setup_entry` runs (unit-level fake hass)
**Then** setup completes without the lifecycle abort path, no
`custom_components` module imports the deleted names (grep-clean assertion),
and the full suite is green.

### Scenario F — missing token stays fail-soft (ADR-0030)

**Given** `render_path: auto`, a configured `worker_endpoint_url`, and no
stored token
**When** a chart job runs
**Then** the job completes via the trusted Pillow renderer with the surfaced
fallback (`render_path` + `render_fallback_reason` on the artifact/snapshot) —
no new failure mode.
