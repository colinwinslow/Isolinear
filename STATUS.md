# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-13 (Durable worker token lifecycle scaffold complete)
**Phase:** `Durable worker token lifecycle scaffold complete`
**Next bounded packet:** `Choose next worker/orchestration follow-up`
**Current readiness:** `READY-FOR-NEXT-PACKET`

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-13** — `Durable worker token lifecycle scaffold` — Added ADR-0016 plus the durable integration-owned worker token lifecycle scaffold. Config-entry setup now loads the lifecycle store before readiness/renderer setup, restores only valid same-entry persisted tokens after schema-valid lifecycle storage succeeds, fails closed before readiness/renderer setup when lifecycle storage rejects, records redacted repair-issue metadata when no valid token can be restored, records disabled lifecycle state when no worker endpoint exists, and keeps explicit provision/rotation/repair wrappers durable with rollback on lifecycle validation/storage failure. The packet deliberately did not add dashboard-card token controls, real Home Assistant Repairs flows, setup-time token generation, automatic repair execution, worker health/render calls, provider calls, durable retry queues, scheduler tasks, Home Assistant mutation, or token/endpoint leakage. Verification: red focused test failed before the production module; focused lifecycle tests (`11 passed`); focused lifecycle eval (`PASS home_assistant_durable_worker_token_lifecycle_scaffold`); adjacent worker regression bundle (`109 passed`); module `py_compile`; adjacent worker/orchestration evals passed; inline BDD-evidence review OK for scenarios A-J; standalone architecture review OK with no recommendations; and `git diff --cached --check` clean. Full `tests/` previously hit the known unrelated codegen sandbox matplotlib subprocess flake once (`298 passed, 1 failed`), and the exact failed test passed on rerun.
- **2026-06-12** — `Durable polling cancelled-state hardening` — Added a narrow durable worker health polling production-hardening follow-up: persisted `IntegrationWorkerHealthPollingState` entries whose scheduler metadata is marked `cancelled` are now rejected during storage-helper load/resume so unload-cancelled timer metadata cannot resurrect after restart. The spec, BDD, eval outline, evidence, verifier anchor, and focused tests now prove cancelled persisted polling state is skipped before merge while valid persisted entries, token-missing diagnostics, and unsaved in-memory state remain intact. Verification: red focused storage-load test failed before the guard, then passed; module `py_compile`; focused polling tests (`17 passed`); focused durable polling eval (`PASS home_assistant_durable_worker_health_polling_scaffold`); adjacent worker regression bundle (`98 passed`); inline BDD-evidence review OK for scenarios A-K; standalone architecture review OK with no recommendations; and `git diff --check` clean aside from normal CRLF warnings. The packet deliberately did not add worker calls during setup, new scheduler semantics, token repair/rotation, durable retry queues, dashboard-card commands, Home Assistant mutation, or worker render behavior.
- **2026-06-12** — `Model-provider health diagnostics scaffold` — Added a bounded explicit model-provider health diagnostics scaffold for configured Ollama-compatible planner clients. Setup now records provider-health probe availability without calling the provider; explicit checks validate a `ModelProviderHealthRequest` for `GET /api/tags`, call only the same-entry planner client, store one schema-valid `IntegrationModelProviderHealth` envelope for `ready`, `not_ready`, and `unavailable` results, and fail closed before storage for malformed or secret-bearing accepted responses, unknown entries, and unconfigured entries. Dashboard-card payloads stay unchanged and do not expose provider endpoint/request/response/health internals. The packet deliberately did not add provider health polling, automatic retry, durable retry queues/storage, worker behavior, rendering, provider token persistence, dashboard UI, or Home Assistant mutation. Verification: module `py_compile`, focused provider health tests (`11 passed`), focused provider health eval (`PASS home_assistant_model_provider_health_diagnostics_scaffold`), broader integration/provider/worker regression tests (`128 passed`), adjacent model-provider planning/retry and worker health evals, `git diff --check` clean aside from normal CRLF warnings plus a clean new-file trailing-whitespace scan, inline BDD-evidence review OK for scenarios A-J, and standalone architecture review OK with no recommendations.
- **2026-06-12** — `Model-provider retry/backoff policy scaffold` — Added a bounded provider-failure follow-up behind the existing `isolinear/v1/job/snapshot` model-provider planning path. Retry-safe planner failures now record one schema-valid config-entry-scoped `IntegrationModelProviderRetryPolicy` envelope with sanitized failure metadata, manual-retry/backoff decision metadata, and `automatic_retry_scheduled: false`, then return only a schema-valid failed `IntegrationJobSnapshot` to the dashboard card. Malformed retry metadata, secret-like provider failure text, unknown jobs, and cross-config-entry jobs fail before provider retry-policy storage. The packet deliberately did not add provider health polling, automatic retry, durable retry queues, worker behavior, rendering, token persistence, dashboard UI, or Home Assistant mutation. Verification: module `py_compile`, focused provider retry tests (`10 passed`), focused provider retry eval (`PASS home_assistant_model_provider_retry_backoff_policy_scaffold`), adjacent model-provider/worker retry/transport tests (`30 passed`), adjacent model-provider planning and worker retry evals, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK for scenarios A-H, and standalone architecture review OK with no recommendations.
- **2026-06-12** — `Durable polling maintainability refactor` — Split the large durable worker health polling production module into focused constants, contract-validation, storage, and state/redaction helpers while keeping `custom_components/isolinear/worker_health_polling.py` as the public orchestration facade. Split the large Python verifier anchor into fixtures, scenario cases, and aggregate verifier helpers while keeping `src/Isolinear/worker_health_polling_anchor.py` as the compatibility facade. No schema, BDD scenario, eval, or dashboard-card contract behavior changed; the existing BDD evidence note was refreshed with the refactor verification posture. Verification: focused polling tests (`17 passed`), focused durable polling eval (`PASS home_assistant_durable_worker_health_polling_scaffold`), adjacent worker regression bundle (`81 passed`), module `py_compile`, BDD-evidence review OK, `git diff --check` clean except the normal CRLF warning, and standalone architecture review with no invariant violations or code recommendations. Full `tests/` rerun hit the known unrelated codegen sandbox matplotlib flake once (`267 passed, 1 failed`) and the exact failed test passed on rerun.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Durable worker token lifecycle scaffold`

- [x] Record ADR-0016 for integration-owned durable worker token lifecycle persistence and restore boundaries
- [x] Add paired spec, BDD, eval outline, evidence, lifecycle-state schema, verifier anchor, and focused tests
- [x] Add production lifecycle storage helper and setup wiring before worker readiness/renderer setup
- [x] Restore only valid same-entry persisted tokens after lifecycle state validates and storage accepts the write
- [x] Record redacted repair-issue metadata for configured entries without valid tokens
- [x] Record disabled lifecycle state for entries without worker endpoints
- [x] Persist explicit provision, rotation, and repair wrapper results privately and roll back on lifecycle validation/storage failure
- [x] Prove invalid persisted entries, setup storage failures, config-entry isolation, no leakage, and bounded side effects
- [x] Preserve non-goals: no dashboard token commands, real Repairs flow, setup-time token generation, automatic repair execution, worker calls, provider calls, durable retry queues, scheduler tasks, Home Assistant mutation, or token/endpoint leakage
- [x] Run red focused test before the production module existed
- [x] Run focused lifecycle tests in `.venv` (`11 passed`)
- [x] Run focused lifecycle eval in `.venv` (`PASS home_assistant_durable_worker_token_lifecycle_scaffold`)
- [x] Run adjacent worker regression tests in `.venv` (`109 passed`)
- [x] Run module `py_compile`
- [x] Run adjacent worker/orchestration evals
- [x] Run inline BDD-evidence review against scenarios A-J
- [x] Run standalone architecture review against the staged packet diff
- [x] Check staged diff formatting (`git diff --cached --check` clean)

## Open queue (non-blocking)

> Things worth doing that don't gate the current packet. Pull from here when the active packet closes.

- (a) Aggregate-style ambiguous entity clarification executable eval
- (b) Aggregate alias creation/reuse executable eval
- (c) Post-MVP floorplan heatmap renderer requiring explicit user-provided room
  geometry and area/entity mappings
- (d) Keep remaining worker/orchestration work split into smaller packets:
  token rotation UI or real Home Assistant Repairs/automatic repair semantics,
  automatic/durable provider retry semantics, durable retry queue/scheduler
  behavior, and any additional durable polling production-hardening follow-up
  requested by review should each land separately.

## Blockers

- None.
