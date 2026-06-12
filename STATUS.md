# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-12 (Durable polling cancelled-state hardening complete)
**Phase:** `Durable polling cancelled-state hardening complete`
**Next bounded packet:** `Choose next worker/orchestration follow-up`
**Current readiness:** `READY-FOR-NEXT-PACKET`

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-12** — `Durable polling cancelled-state hardening` — Added a narrow durable worker health polling production-hardening follow-up: persisted `IntegrationWorkerHealthPollingState` entries whose scheduler metadata is marked `cancelled` are now rejected during storage-helper load/resume so unload-cancelled timer metadata cannot resurrect after restart. The spec, BDD, eval outline, evidence, verifier anchor, and focused tests now prove cancelled persisted polling state is skipped before merge while valid persisted entries, token-missing diagnostics, and unsaved in-memory state remain intact. Verification: red focused storage-load test failed before the guard, then passed; module `py_compile`; focused polling tests (`17 passed`); focused durable polling eval (`PASS home_assistant_durable_worker_health_polling_scaffold`); adjacent worker regression bundle (`98 passed`); inline BDD-evidence review OK for scenarios A-K; standalone architecture review OK with no recommendations; and `git diff --check` clean aside from normal CRLF warnings. The packet deliberately did not add worker calls during setup, new scheduler semantics, token repair/rotation, durable retry queues, dashboard-card commands, Home Assistant mutation, or worker render behavior.
- **2026-06-12** — `Model-provider health diagnostics scaffold` — Added a bounded explicit model-provider health diagnostics scaffold for configured Ollama-compatible planner clients. Setup now records provider-health probe availability without calling the provider; explicit checks validate a `ModelProviderHealthRequest` for `GET /api/tags`, call only the same-entry planner client, store one schema-valid `IntegrationModelProviderHealth` envelope for `ready`, `not_ready`, and `unavailable` results, and fail closed before storage for malformed or secret-bearing accepted responses, unknown entries, and unconfigured entries. Dashboard-card payloads stay unchanged and do not expose provider endpoint/request/response/health internals. The packet deliberately did not add provider health polling, automatic retry, durable retry queues/storage, worker behavior, rendering, provider token persistence, dashboard UI, or Home Assistant mutation. Verification: module `py_compile`, focused provider health tests (`11 passed`), focused provider health eval (`PASS home_assistant_model_provider_health_diagnostics_scaffold`), broader integration/provider/worker regression tests (`128 passed`), adjacent model-provider planning/retry and worker health evals, `git diff --check` clean aside from normal CRLF warnings plus a clean new-file trailing-whitespace scan, inline BDD-evidence review OK for scenarios A-J, and standalone architecture review OK with no recommendations.
- **2026-06-12** — `Model-provider retry/backoff policy scaffold` — Added a bounded provider-failure follow-up behind the existing `isolinear/v1/job/snapshot` model-provider planning path. Retry-safe planner failures now record one schema-valid config-entry-scoped `IntegrationModelProviderRetryPolicy` envelope with sanitized failure metadata, manual-retry/backoff decision metadata, and `automatic_retry_scheduled: false`, then return only a schema-valid failed `IntegrationJobSnapshot` to the dashboard card. Malformed retry metadata, secret-like provider failure text, unknown jobs, and cross-config-entry jobs fail before provider retry-policy storage. The packet deliberately did not add provider health polling, automatic retry, durable retry queues, worker behavior, rendering, token persistence, dashboard UI, or Home Assistant mutation. Verification: module `py_compile`, focused provider retry tests (`10 passed`), focused provider retry eval (`PASS home_assistant_model_provider_retry_backoff_policy_scaffold`), adjacent model-provider/worker retry/transport tests (`30 passed`), adjacent model-provider planning and worker retry evals, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK for scenarios A-H, and standalone architecture review OK with no recommendations.
- **2026-06-12** — `Durable polling maintainability refactor` — Split the large durable worker health polling production module into focused constants, contract-validation, storage, and state/redaction helpers while keeping `custom_components/isolinear/worker_health_polling.py` as the public orchestration facade. Split the large Python verifier anchor into fixtures, scenario cases, and aggregate verifier helpers while keeping `src/Isolinear/worker_health_polling_anchor.py` as the compatibility facade. No schema, BDD scenario, eval, or dashboard-card contract behavior changed; the existing BDD evidence note was refreshed with the refactor verification posture. Verification: focused polling tests (`17 passed`), focused durable polling eval (`PASS home_assistant_durable_worker_health_polling_scaffold`), adjacent worker regression bundle (`81 passed`), module `py_compile`, BDD-evidence review OK, `git diff --check` clean except the normal CRLF warning, and standalone architecture review with no invariant violations or code recommendations. Full `tests/` rerun hit the known unrelated codegen sandbox matplotlib flake once (`267 passed, 1 failed`) and the exact failed test passed on rerun.
- **2026-06-12** — `Durable polling refactor follow-up queued` — Added a non-blocking follow-up packet to split the large durable worker health polling production and verifier modules into smaller, behavior-preserving units. The refactor target is maintainability only: preserve ADR-0015 behavior, schemas, BDD/evidence, eval output, dashboard-card safety, and all existing tests while reducing the 1500-line module/anchor density. No code, spec, schema, BDD, or eval behavior changed in this closeout.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Durable polling cancelled-state hardening`

- [x] Update durable polling spec, BDD, eval outline, and evidence for cancelled persisted-state rejection
- [x] Add verifier/test proof that persisted `scheduler.cancelled: true` polling state is skipped before merge
- [x] Reject cancelled persisted polling state during storage-helper load/resume
- [x] Preserve valid persisted entries, token-missing diagnostic entries, and unsaved in-memory entries during storage load
- [x] Preserve non-goals: no setup worker calls, token repair/rotation, durable retry queues, dashboard-card commands, Home Assistant mutation, worker render calls, or new scheduler semantics
- [x] Run red focused storage-load test before the production guard
- [x] Run focused polling tests in `.venv` (`17 passed`)
- [x] Run focused durable polling eval in `.venv` (`PASS home_assistant_durable_worker_health_polling_scaffold`)
- [x] Run adjacent worker regression tests in `.venv` (`98 passed`)
- [x] Run module `py_compile`
- [x] Run inline BDD-evidence review against scenarios A-K
- [x] Run standalone architecture review against the packet diff
- [x] Check diff formatting (`git diff --check` clean aside from normal CRLF warnings)

## Open queue (non-blocking)

> Things worth doing that don't gate the current packet. Pull from here when the active packet closes.

- (a) Aggregate-style ambiguous entity clarification executable eval
- (b) Aggregate alias creation/reuse executable eval
- (c) Post-MVP floorplan heatmap renderer requiring explicit user-provided room
  geometry and area/entity mappings
- (d) Keep remaining worker/orchestration work split into smaller packets:
  token rotation UI/persistence/automatic repair, automatic/durable provider
  retry semantics, durable retry queue/scheduler behavior, and any additional
  durable polling production-hardening follow-up requested by review should
  each land separately.

## Blockers

- None.
