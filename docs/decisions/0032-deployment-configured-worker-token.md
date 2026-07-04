# ADR-0032 — Deployment-configured worker token; retire the ADR-0015/0016 durability machinery

- Status: **accepted** (direction decided by Colin 2026-07-03; implemented + live-proven 2026-07-04)
- Date: 2026-07-04
- Deciders: Colin (direction), agent (design)
- Supersedes the *runtime machinery* of deprecated ADR-0015/ADR-0016
  (`docs/decisions/archive/`); their storage/durability patterns remain
  historical context.

## Context

The first live worker deployment (CT103 compose service, homelab spec
`isolinear-worker-service`) exposed a token mismatch designed into the
scaffold era: the integration **self-provisions** a worker bearer token
(ADR-0016 durable token lifecycle) that the real worker has never heard of —
the worker's token is 12-factor deployment config (`ISOLINEAR_WORKER_TOKEN`
from SOPS, per ADR-0029's packet-2 server contract). Every real dispatch
would 401. The packet-4/5 evals never hit this because they controlled both
ends of the wire.

The machinery carrying the self-provisioned token is ~3.1K LOC across six
modules (`worker_token_lifecycle` 626, `worker_readiness` 442,
`worker_health` 391, `worker_health_polling*` 1,645) built for the
*simulated* worker ADR-0015/0016 assumed: integration-owned token
provisioning/rotation/repair, durable health-polling checkpoints that survive
restarts. ADR-0015/0016 were deprecated at the 2026-07-02 consolidation
(commit `255b0c3`) with their runtime machinery "scheduled for
simplification." The scaffold purge (`f8f7760`) already deleted their anchor
tests — the machinery now runs essentially **uncovered**, and its only
load-bearing edges are the `__init__.py` setup chain (which aborts setup if
lifecycle storage fails) and `worker_renderer.setup_worker_renderer` reading
the self-provisioned token.

Meanwhile ADR-0030 made worker faults **fail-soft by design**: codegen
failures (including transport faults) fall back to the trusted Pillow
renderer, surfaced never silent. A pre-emptive health-polling subsystem
defends against nothing the fallback doesn't already handle.

## Decision

1. **The worker token is deployment configuration, owned by the deployment.**
   The worker (server side) keeps its 12-factor `ISOLINEAR_WORKER_TOKEN`. The
   integration is *given* that token by the user — it never generates,
   rotates, or repairs one.

2. **The token is entered through an options-flow password field and stored
   in an integration-owned HA Store — never in config-entry data or options.**
   The existing fail-closed posture stands: config/options data carrying
   secret vocabulary is still rejected (`config_schema.py` unchanged). The
   options flow accepts a write-only `worker_api_token` field, validates
   length (≥24 chars, matching the worker's own floor), writes it to a small
   dedicated Store (`isolinear_worker_deployment_token`, one document keyed by
   config entry), and drops it
   from the persisted options. The field is never pre-filled or echoed back;
   an empty submission leaves the stored token unchanged; entering the
   literal `clear` removes it. Redaction vocabulary already covers
   `worker_token`/bearer material everywhere it could surface.

3. **`setup_worker_renderer` builds the HTTP client from
   `worker_endpoint_url` (config) + the stored deployment token.** No
   readiness gate, no lifecycle restore. Missing either piece →
   `worker_renderer_token_missing` setup (disabled), exactly as today — with
   `render_path: auto` the job renders via Pillow (ADR-0030 fallback,
   surfaced).

4. **Delete the durability machinery wholesale:** `worker_token_lifecycle.py`,
   `worker_readiness.py`, `worker_health.py`, `worker_health_polling.py`,
   `worker_health_polling_constants.py`, `worker_health_polling_contract.py`,
   `worker_health_polling_state.py`, `worker_health_polling_storage.py`; their
   four schemas (`integration-worker-token-lifecycle-state`,
   `integration-worker-health-polling-state`, `integration-worker-health`,
   `integration-worker-readiness` — plus `worker-health-request` if nothing
   else references it) from all bundled copies; their `__init__.py` setup
   steps and unload hooks; their entries in the HACS packaging test. Worker
   health becomes **on-demand**: the render client keeps a
   `check_health()` using the existing `/v1/health` contract for diagnostics
   and future UI use — no polling loop, no checkpoint storage, no repair
   issues.

5. **No worker-side change.** The packet-2 HTTP server contract
   (auth → version → schema → sandbox) and the homelab deployment
   (SOPS token → compose env) are already correct.

## Consequences

- The live CT103 worker becomes reachable by the integration the moment the
  user pastes the deployment token — the last blocker to the first
  end-to-end live render.
- ~3.1K LOC of uncovered scaffold-era code is removed; `__init__.py` setup
  loses two await steps and an abort path; stale `.storage` keys
  (`isolinear_worker_token_lifecycle`, polling checkpoints) are simply no
  longer read (left in place, harmless — HA storage is namespaced).
- Token rotation becomes a *deployment* action (change SOPS + re-apply +
  paste the new token), matching how every other credential in the homelab
  works.
- The "token rotation UI / HA Repairs" open-queue item (d) is retired with
  the machinery it referred to.

## Kill criteria / revisit

If a future multi-user or add-on distribution needs integration-managed
worker credentials (e.g. the HA add-on wrapper provisioning its own token),
that is a new ADR on top of this deployment-configured baseline — not a
revival of ADR-0015/0016.
