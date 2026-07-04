---
status: accepted
date: 2026-07-04
depends-on-adrs: ["ADR-0032"]
---

# deployment-worker-token: user-supplied worker token + durability machinery retirement

## Status

Accepted. Defines the contract surface for ADR-0032: the worker bearer token
becomes deployment configuration entered by the user; the ADR-0015/0016
runtime machinery is deleted.

## Related docs

- [bdd/integration/deployment-worker-token-bdd.md](../../bdd/integration/deployment-worker-token-bdd.md)
- [docs/decisions/0032-deployment-configured-worker-token.md](../decisions/0032-deployment-configured-worker-token.md)

## Context

See ADR-0032. The live CT103 worker (homelab `isolinear-worker-service`)
authenticates against a SOPS-managed deployment token; the integration's
self-provisioned ADR-0016 token can never match it. The self-provisioning
machinery (~3.1K LOC, six modules) is deprecated, untested since the purge,
and unneeded under ADR-0030's surfaced Pillow fallback.

## Behavior contract

### 1. Token storage (`worker_token_storage.py`, new)

- `WorkerTokenStorageHelper` — ONE HA Store document
  (`isolinear_worker_deployment_token`) holding every config entry's token
  keyed by `config_entry_id`, versioned — the semantic-memory storage shape.
  *(Deviation from the first draft's per-entry-store sketch, recorded at
  implementation: the house precedent is one keyed document.)*
- `async_load` on setup; synchronous `save_token` / `clear_token` +
  `async_delay_save` (options handler may run off-loop — same executor-thread
  reality semantic memory hit).
- `stored_worker_token(hass, entry_id) -> str | None` — the single read
  surface `setup_worker_renderer` uses.
- Token validity: same floor as the worker (**≥24 chars**, stripped,
  non-empty). Invalid values are rejected at the options flow, never stored.

### 2. Options flow (`config_flow.py`)

- New write-only password field `worker_api_token` (voluptuous
  `str`, selector `{"type": "text", "input_type": "password"}` — match the
  existing selector metadata style).
- Semantics: empty/absent → stored token unchanged; a valid token → stored
  (overwrites); the literal `clear` → stored token removed; anything else
  (1–23 chars) → form error `worker_token_too_short`.
- The submitted value is **dropped from the persisted options** before
  validation/storage of the options payload — `config_schema.py`'s
  secret-vocabulary fail-closed check stays intact and still rejects any
  secret-bearing options/config data.
- The field is never pre-filled. *(Deviation: the draft's "form description
  states whether a token is stored" is deferred — it needs strings/translations
  plumbing; presence is observable via the renderer setup code
  (`worker_renderer_configured` vs `worker_renderer_token_missing`).)*

### 3. Renderer wiring (`worker_renderer.py`)

- `setup_worker_renderer` builds `HttpJsonWorkerRenderClient` from
  `entry.data["worker_endpoint_url"]` + `stored_worker_token(...)`.
  `DATA_WORKER_RENDER_TOKEN`/lifecycle reads are gone.
- Either piece missing/invalid → the existing disabled setup
  (`worker_renderer_token_missing`), and `render_path: auto` renders via
  Pillow with the ADR-0030 surfaced fallback. No new failure mode.
- A save/clear action rebuilds the renderer client **directly in the options
  flow** (invalidate `DATA_WORKER_RENDER_CLIENT` + re-run setup): HA fires
  update listeners only when options changed, and a token-only re-paste leaves
  options identical (architecture-review finding). The listener also rebuilds
  on ordinary options edits.
- The client gains `check_health()` (GET `/v1/health`, bearer + version
  headers, returns the health envelope or a transport-fault dict) — on-demand
  replacement for the deleted polling; consumed by diagnostics/tests only in
  this slice.

### 4. Deletions

- Modules: `worker_token_lifecycle.py`, `worker_readiness.py`,
  `worker_health.py`, `worker_health_polling.py`,
  `worker_health_polling_constants.py`, `worker_health_polling_contract.py`,
  `worker_health_polling_state.py`, `worker_health_polling_storage.py`.
- `__init__.py`: the lifecycle await + abort, readiness/health/polling setup
  steps, polling unload hook.
- Schemas (all bundled copies, docs + packaged):
  `integration-worker-token-lifecycle-state`,
  `integration-worker-health-polling-state`, `integration-worker-health`,
  `integration-worker-readiness`, `worker-health-request` (verify no other
  reference first; the worker's own bundled schemas are untouched).
- HACS packaging test entries for the deleted schemas.
- Dead imports/constants throughout (`worker_client_token` stays — the
  dispatch metadata uses it).

## Anchor artifact

With a token pasted through the options flow, `setup_worker_renderer`
produces an enabled client whose `check_health()` against the **live CT103
worker** returns `status: "ready"` — proven in an eval
(`evals/deployment_worker_token.py`) that reads the token from env
(`ISOLINEAR_EVAL_WORKER_TOKEN`, never committed), plus a unit-level anchor
against the packet-2 in-process server.

## Implementation order

1. Anchor: `worker_token_storage.py` + renderer wiring + `check_health()`,
   proven against an in-process packet-2 server (and live CT103 via the eval,
   env-token).
2. Options-flow field + semantics + tests.
3. The deletion (modules, `__init__` chain, schemas, packaging test).
4. Evidence + doc-index sync + version bump.

## Proof requirements

1. Unit tests green: storage helper round-trip/clear/invalid; options-flow
   set/keep/clear/too-short + "options payload never carries the token";
   renderer enabled/disabled matrix; `check_health()` against the in-process
   server (ready + 401 + transport fault).
2. BDD scenarios A–F pass; evidence file with raw outputs at
   `bdd/integration/deployment-worker-token-evidence.md`.
3. Full suite green; schema byte-parity green for the *remaining* schemas;
   no `custom_components` import of the deleted modules (grep-clean).
4. Live proof: eval `check_health()` → `ready` against CT103 with the SOPS
   token (raw output in evidence, token redacted).
5. Architecture review (fresh-context) OK; BDD-evidence review OK.

## Non-goals

- Token rotation UI / HA Repairs (retired with the machinery; deployment
  rotates by re-paste).
- Multi-worker or per-job worker selection.
- HA add-on packaging (its token story is the add-on wrapper's ADR).
- Worker-side changes of any kind.

## References

- ADR-0032, ADR-0030 (surfaced fallback), ADR-0029 (worker server contract)
- homelab `docs/specs/isolinear-worker-service.md` (deployment side)
