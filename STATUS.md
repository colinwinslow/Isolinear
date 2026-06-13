# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-13 (First real vertical slice pivot closed; manual verification next)
**Phase:** `First real vertical slice manual verification`
**Next bounded packet:** `Manual real HA + Ollama verification of in-process slice`
**Current readiness:** `READY FOR MANUAL VERIFICATION`

> **⚠️ Direction change (2026-06-12):** Before picking another scaffold packet,
> read [`docs/reality-pivot-review.md`](docs/reality-pivot-review.md). The next
> work is a **real vertical slice** (real recorder history + real Ollama +
> real matplotlib, rendered in-process) — not another simulated scaffold. Stop
> adding `*_anchor.py` verifiers; pytest is the single source of behavioral truth.

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-13** — `First real vertical slice pivot` — Merged the reality-pivot guidance into draft ADR-0017 plus paired spec, BDD, and evidence. Added best-effort real Home Assistant registry/state metadata enrichment, best-effort recorder-history retrieval, a trusted in-process matplotlib renderer for safe numeric `time_series` ChartSpecs, schema evolution for rendered artifacts, and a first-real-slice route in the existing `job/start` -> `job/snapshot` flow that returns a PNG data URL when no worker dispatch is used. Hidden provider entity references still fail before render/artifact storage, completed snapshots are reused idempotently, and no new `*_anchor.py` verifier was added. The packet deliberately did not manually verify against a real HA dev instance or real Ollama endpoint, add generated Python/codegen, call the worker in the in-process route, add durable artifact serving, or mutate Home Assistant. Verification: focused first-real-slice tests (`3 passed`), adjacent integration/orchestration bundle (`57 passed`), full Python suite (`303 passed`), module `py_compile`, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK, and standalone architecture review OK with no invariant violations.
- **2026-06-13** — `Durable worker token lifecycle scaffold` — Added ADR-0016 plus the durable integration-owned worker token lifecycle scaffold. Config-entry setup now loads the lifecycle store before readiness/renderer setup, restores only valid same-entry persisted tokens after schema-valid lifecycle storage succeeds, fails closed before readiness/renderer setup when lifecycle storage rejects, records redacted repair-issue metadata when no valid token can be restored, records disabled lifecycle state when no worker endpoint exists, and keeps explicit provision/rotation/repair wrappers durable with rollback on lifecycle validation/storage failure. The packet deliberately did not add dashboard-card token controls, real Home Assistant Repairs flows, setup-time token generation, automatic repair execution, worker health/render calls, provider calls, durable retry queues, scheduler tasks, Home Assistant mutation, or token/endpoint leakage. Verification: red focused test failed before the production module; focused lifecycle tests (`11 passed`); focused lifecycle eval (`PASS home_assistant_durable_worker_token_lifecycle_scaffold`); adjacent worker regression bundle (`109 passed`); module `py_compile`; adjacent worker/orchestration evals passed; inline BDD-evidence review OK for scenarios A-J; standalone architecture review OK with no recommendations; and `git diff --cached --check` clean. Full `tests/` previously hit the known unrelated codegen sandbox matplotlib subprocess flake once (`298 passed, 1 failed`), and the exact failed test passed on rerun.
- **2026-06-12** — `Durable polling cancelled-state hardening` — Added a narrow durable worker health polling production-hardening follow-up: persisted `IntegrationWorkerHealthPollingState` entries whose scheduler metadata is marked `cancelled` are now rejected during storage-helper load/resume so unload-cancelled timer metadata cannot resurrect after restart. The spec, BDD, eval outline, evidence, verifier anchor, and focused tests now prove cancelled persisted polling state is skipped before merge while valid persisted entries, token-missing diagnostics, and unsaved in-memory state remain intact. Verification: red focused storage-load test failed before the guard, then passed; module `py_compile`; focused polling tests (`17 passed`); focused durable polling eval (`PASS home_assistant_durable_worker_health_polling_scaffold`); adjacent worker regression bundle (`98 passed`); inline BDD-evidence review OK for scenarios A-K; standalone architecture review OK with no recommendations; and `git diff --check` clean aside from normal CRLF warnings. The packet deliberately did not add worker calls during setup, new scheduler semantics, token repair/rotation, durable retry queues, dashboard-card commands, Home Assistant mutation, or worker render behavior.
- **2026-06-12** — `Model-provider health diagnostics scaffold` — Added a bounded explicit model-provider health diagnostics scaffold for configured Ollama-compatible planner clients. Setup now records provider-health probe availability without calling the provider; explicit checks validate a `ModelProviderHealthRequest` for `GET /api/tags`, call only the same-entry planner client, store one schema-valid `IntegrationModelProviderHealth` envelope for `ready`, `not_ready`, and `unavailable` results, and fail closed before storage for malformed or secret-bearing accepted responses, unknown entries, and unconfigured entries. Dashboard-card payloads stay unchanged and do not expose provider endpoint/request/response/health internals. The packet deliberately did not add provider health polling, automatic retry, durable retry queues/storage, worker behavior, rendering, provider token persistence, dashboard UI, or Home Assistant mutation. Verification: module `py_compile`, focused provider health tests (`11 passed`), focused provider health eval (`PASS home_assistant_model_provider_health_diagnostics_scaffold`), broader integration/provider/worker regression tests (`128 passed`), adjacent model-provider planning/retry and worker health evals, `git diff --check` clean aside from normal CRLF warnings plus a clean new-file trailing-whitespace scan, inline BDD-evidence review OK for scenarios A-J, and standalone architecture review OK with no recommendations.
- **2026-06-12** — `Model-provider retry/backoff policy scaffold` — Added a bounded provider-failure follow-up behind the existing `isolinear/v1/job/snapshot` model-provider planning path. Retry-safe planner failures now record one schema-valid config-entry-scoped `IntegrationModelProviderRetryPolicy` envelope with sanitized failure metadata, manual-retry/backoff decision metadata, and `automatic_retry_scheduled: false`, then return only a schema-valid failed `IntegrationJobSnapshot` to the dashboard card. Malformed retry metadata, secret-like provider failure text, unknown jobs, and cross-config-entry jobs fail before provider retry-policy storage. The packet deliberately did not add provider health polling, automatic retry, durable retry queues, worker behavior, rendering, token persistence, dashboard UI, or Home Assistant mutation. Verification: module `py_compile`, focused provider retry tests (`10 passed`), focused provider retry eval (`PASS home_assistant_model_provider_retry_backoff_policy_scaffold`), adjacent model-provider/worker retry/transport tests (`30 passed`), adjacent model-provider planning and worker retry evals, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK for scenarios A-H, and standalone architecture review OK with no recommendations.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Manual real HA + Ollama verification of in-process slice`

- [ ] Load the current integration into a real Home Assistant dev instance with a configured `entity_allowlist`
- [ ] Enable the first-real-slice in-process render route for that entry
- [ ] Configure a real Ollama-compatible planner endpoint and model
- [ ] Run `isolinear/v1/job/start` and `isolinear/v1/job/snapshot` through the real Home Assistant WebSocket/dashboard path
- [ ] Verify the returned `chart.image_url` decodes to a PNG and references only allowlisted entity history
- [ ] Capture schema/runtime drift discovered by real HA registry, recorder, or Ollama output
- [ ] Revisit async recorder/aiohttp production ergonomics based on the real manual run

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
