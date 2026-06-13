# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-12 (Model-provider health diagnostics scaffold complete)
**Phase:** `Model-provider health diagnostics scaffold complete`
**Next bounded packet:** `Choose next worker/orchestration follow-up`
**Current readiness:** `READY-FOR-NEXT-PACKET`

> **⚠️ Direction change (2026-06-12):** Before picking another scaffold packet,
> read [`docs/reality-pivot-review.md`](docs/reality-pivot-review.md). The next
> work is a **real vertical slice** (real recorder history + real Ollama +
> real matplotlib, rendered in-process) — not another simulated scaffold. Stop
> adding `*_anchor.py` verifiers; pytest is the single source of behavioral truth.

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-12** — `Model-provider health diagnostics scaffold` — Added a bounded explicit model-provider health diagnostics scaffold for configured Ollama-compatible planner clients. Setup now records provider-health probe availability without calling the provider; explicit checks validate a `ModelProviderHealthRequest` for `GET /api/tags`, call only the same-entry planner client, store one schema-valid `IntegrationModelProviderHealth` envelope for `ready`, `not_ready`, and `unavailable` results, and fail closed before storage for malformed or secret-bearing accepted responses, unknown entries, and unconfigured entries. Dashboard-card payloads stay unchanged and do not expose provider endpoint/request/response/health internals. The packet deliberately did not add provider health polling, automatic retry, durable retry queues/storage, worker behavior, rendering, provider token persistence, dashboard UI, or Home Assistant mutation. Verification: module `py_compile`, focused provider health tests (`11 passed`), focused provider health eval (`PASS home_assistant_model_provider_health_diagnostics_scaffold`), broader integration/provider/worker regression tests (`128 passed`), adjacent model-provider planning/retry and worker health evals, `git diff --check` clean aside from normal CRLF warnings plus a clean new-file trailing-whitespace scan, inline BDD-evidence review OK for scenarios A-J, and standalone architecture review OK with no recommendations.
- **2026-06-12** — `Model-provider retry/backoff policy scaffold` — Added a bounded provider-failure follow-up behind the existing `isolinear/v1/job/snapshot` model-provider planning path. Retry-safe planner failures now record one schema-valid config-entry-scoped `IntegrationModelProviderRetryPolicy` envelope with sanitized failure metadata, manual-retry/backoff decision metadata, and `automatic_retry_scheduled: false`, then return only a schema-valid failed `IntegrationJobSnapshot` to the dashboard card. Malformed retry metadata, secret-like provider failure text, unknown jobs, and cross-config-entry jobs fail before provider retry-policy storage. The packet deliberately did not add provider health polling, automatic retry, durable retry queues, worker behavior, rendering, token persistence, dashboard UI, or Home Assistant mutation. Verification: module `py_compile`, focused provider retry tests (`10 passed`), focused provider retry eval (`PASS home_assistant_model_provider_retry_backoff_policy_scaffold`), adjacent model-provider/worker retry/transport tests (`30 passed`), adjacent model-provider planning and worker retry evals, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK for scenarios A-H, and standalone architecture review OK with no recommendations.
- **2026-06-12** — `Durable polling maintainability refactor` — Split the large durable worker health polling production module into focused constants, contract-validation, storage, and state/redaction helpers while keeping `custom_components/isolinear/worker_health_polling.py` as the public orchestration facade. Split the large Python verifier anchor into fixtures, scenario cases, and aggregate verifier helpers while keeping `src/Isolinear/worker_health_polling_anchor.py` as the compatibility facade. No schema, BDD scenario, eval, or dashboard-card contract behavior changed; the existing BDD evidence note was refreshed with the refactor verification posture. Verification: focused polling tests (`17 passed`), focused durable polling eval (`PASS home_assistant_durable_worker_health_polling_scaffold`), adjacent worker regression bundle (`81 passed`), module `py_compile`, BDD-evidence review OK, `git diff --check` clean except the normal CRLF warning, and standalone architecture review with no invariant violations or code recommendations. Full `tests/` rerun hit the known unrelated codegen sandbox matplotlib flake once (`267 passed, 1 failed`) and the exact failed test passed on rerun.
- **2026-06-12** — `Durable polling refactor follow-up queued` — Added a non-blocking follow-up packet to split the large durable worker health polling production and verifier modules into smaller, behavior-preserving units. The refactor target is maintainability only: preserve ADR-0015 behavior, schemas, BDD/evidence, eval output, dashboard-card safety, and all existing tests while reducing the 1500-line module/anchor density. No code, spec, schema, BDD, or eval behavior changed in this closeout.
- **2026-06-12** — `Durable worker health polling checkpoint rescue audit` — Inspected checkpoint commit `553c06c` after the interrupted durable polling packet and repaired `STATUS.md`/`HANDOFF.md` drift so startup no longer points at pre-checkpoint work. The checkpoint had already promoted ADR-0015 to accepted and added the durable polling spec, BDD/evidence, eval outline, `IntegrationWorkerHealthPollingState` schema, executable eval, verifier anchor, focused tests, and production setup/unload polling module. Rescue verification reran focused polling tests in `.venv` (`17 passed`), adjacent worker regression tests (`98 passed`), focused durable polling eval (`PASS home_assistant_durable_worker_health_polling_scaffold`), full Python suite (`268 passed`), and checkpoint diff formatting (`git diff --check HEAD~1..HEAD` clean). BDD-evidence review OK: all scenarios A-K have matching `CASE`/`PASS` evidence plus command output and redaction scan output. Standalone architecture review OK: no invariant violations, no scope/discipline flags, and no recommendations. The known codegen sandbox matplotlib subprocess flake remains historical only for this rescue pass because the rerun full suite passed cleanly.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Model-provider health diagnostics scaffold`

- [x] Add spec, BDD, eval outline, schemas, verifier anchor, focused tests, executable eval, and evidence
- [x] Record setup-only model-provider health availability without provider calls
- [x] Explicitly validate `GET /api/tags` health requests and store schema-valid config-entry-scoped health envelopes for `ready`, `not_ready`, and `unavailable` outcomes
- [x] Reject malformed and secret-bearing accepted health responses before storage
- [x] Reject unknown and unconfigured config entries before provider calls or health metadata storage
- [x] Keep dashboard-card payloads free of provider endpoint/request/response/health internals
- [x] Preserve non-goals: no provider polling, automatic retry, durable retry queue/storage, worker behavior, rendering, provider token persistence, dashboard UI, or Home Assistant mutation
- [x] Run focused provider health tests in `.venv` (`11 passed`)
- [x] Run focused provider health eval in `.venv` (`PASS home_assistant_model_provider_health_diagnostics_scaffold`)
- [x] Run broader integration/provider/worker regression tests in `.venv` (`128 passed`)
- [x] Run adjacent model-provider planning/retry and worker health evals in `.venv`
- [x] Run inline BDD-evidence review against scenarios A-J
- [x] Check diff formatting (`git diff --check` clean aside from normal CRLF warnings; new-file trailing-whitespace scan clean)
- [x] Run standalone architecture review against the packet diff

## Open queue (non-blocking)

> Things worth doing that don't gate the current packet. Pull from here when the active packet closes.

- (a) Aggregate-style ambiguous entity clarification executable eval
- (b) Aggregate alias creation/reuse executable eval
- (c) Post-MVP floorplan heatmap renderer requiring explicit user-provided room
  geometry and area/entity mappings
- (d) Keep remaining worker/orchestration work split into smaller packets:
  token rotation UI/persistence/automatic repair, automatic/durable provider
  retry semantics, durable retry queue/scheduler behavior, and any durable
  polling production-hardening follow-up requested by review should each land
  separately.

## Blockers

- None.
