# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-12 (Durable polling maintainability refactor complete)
**Phase:** `Durable worker health polling maintainability refactor complete`
**Next bounded packet:** `Choose next worker/orchestration follow-up`
**Current readiness:** `READY-FOR-NEXT-PACKET`

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-12** — `Durable polling maintainability refactor` — Split the large durable worker health polling production module into focused constants, contract-validation, storage, and state/redaction helpers while keeping `custom_components/isolinear/worker_health_polling.py` as the public orchestration facade. Split the large Python verifier anchor into fixtures, scenario cases, and aggregate verifier helpers while keeping `src/Isolinear/worker_health_polling_anchor.py` as the compatibility facade. No schema, BDD scenario, eval, or dashboard-card contract behavior changed; the existing BDD evidence note was refreshed with the refactor verification posture. Verification: focused polling tests (`17 passed`), focused durable polling eval (`PASS home_assistant_durable_worker_health_polling_scaffold`), adjacent worker regression bundle (`81 passed`), module `py_compile`, BDD-evidence review OK, `git diff --check` clean except the normal CRLF warning, and standalone architecture review with no invariant violations or code recommendations. Full `tests/` rerun hit the known unrelated codegen sandbox matplotlib flake once (`267 passed, 1 failed`) and the exact failed test passed on rerun.
- **2026-06-12** — `Durable polling refactor follow-up queued` — Added a non-blocking follow-up packet to split the large durable worker health polling production and verifier modules into smaller, behavior-preserving units. The refactor target is maintainability only: preserve ADR-0015 behavior, schemas, BDD/evidence, eval output, dashboard-card safety, and all existing tests while reducing the 1500-line module/anchor density. No code, spec, schema, BDD, or eval behavior changed in this closeout.
- **2026-06-12** — `Durable worker health polling checkpoint rescue audit` — Inspected checkpoint commit `553c06c` after the interrupted durable polling packet and repaired `STATUS.md`/`HANDOFF.md` drift so startup no longer points at pre-checkpoint work. The checkpoint had already promoted ADR-0015 to accepted and added the durable polling spec, BDD/evidence, eval outline, `IntegrationWorkerHealthPollingState` schema, executable eval, verifier anchor, focused tests, and production setup/unload polling module. Rescue verification reran focused polling tests in `.venv` (`17 passed`), adjacent worker regression tests (`98 passed`), focused durable polling eval (`PASS home_assistant_durable_worker_health_polling_scaffold`), full Python suite (`268 passed`), and checkpoint diff formatting (`git diff --check HEAD~1..HEAD` clean). BDD-evidence review OK: all scenarios A-K have matching `CASE`/`PASS` evidence plus command output and redaction scan output. Standalone architecture review OK: no invariant violations, no scope/discipline flags, and no recommendations. The known codegen sandbox matplotlib subprocess flake remains historical only for this rescue pass because the rerun full suite passed cleanly.
- **2026-06-10** — `Home Assistant durable worker health polling ADR anchor` — Added draft ADR-0015 and indexed it in `docs/decisions/README.md`. The ADR records the durable worker health polling decision before implementation: polling is an integration-owned diagnostic loop over ADR-0014 `GET /v1/health`, stores only schema-valid redacted config-entry-scoped latest health summary/scheduler metadata in a Home Assistant storage helper, starts only by enqueuing post-setup/reload work when worker endpoint/readiness/token/client preconditions are satisfied, uses a 300 second ready cadence and bounded 30/60/120/300/900 second failure backoff, and preserves dashboard-card safety by exposing no worker endpoint, token material, health internals, scheduler internals, repair recommendations, or durable polling metadata. The ADR keeps health state diagnostic rather than an authorization gate and forbids automatic token provisioning, token rotation, token repair, worker render calls, model-provider calls, Home Assistant history reads, semantic-memory persistence, Home Assistant mutation services, chart rendering, artifact writes, external databases, queues, Recorder, config-entry option storage, or automatic repair. The ADR explicitly reconciles ADR-0014's setup-time no-automatic-poller constraint by allowing only scheduler bookkeeping during setup and worker health calls after setup completes. On-disk verification complete; `git diff --check` clean aside from the existing CRLF warning on `docs/decisions/README.md`; standalone architecture review OK. No unit tests or evals were run because this was docs-only ADR work. The full-suite codegen sandbox matplotlib subprocess flake remains known and unrelated.
- **2026-06-10** — `Home Assistant worker token rotation/repair scaffold anchor` — Added the paired worker token rotation/repair scaffold spec, BDD, eval outline, raw evidence, executable eval, Python verifier anchor, focused tests, and production config-entry-scoped explicit token rotation/repair functions in `worker_readiness.py`. Rotation now requires an existing valid same-entry worker token, generates a new in-memory integration-owned token, invalidates the old token and renderer client, validates/stores redacted ready `IntegrationWorkerReadiness` metadata, and refreshes same-entry worker renderer setup without worker render or health calls. Repair explicitly creates a valid token for known no-token entries with configured worker endpoints and enables renderer setup. Validation/storage failures restore the old token, readiness metadata/setup, renderer client, and renderer setup; unknown and cross-entry requests fail before token generation or state changes. The packet remains read-only and bounded: no Home Assistant history read, semantic-memory persistence, service/state mutation, worker render/health call, chart rendering, artifact write, durable token/health/retry storage, scheduler, automatic retry/progress task, new worker transport, or dashboard-card exposure of worker endpoint, token material, readiness/health metadata, or repair internals occurs. Focused rotation tests green (`8 passed`), adjacent worker regression tests green (`81 passed`), focused rotation eval green, adjacent worker token/health/dispatch/progress/retry/transport/failure evals green, token scan empty, BDD-evidence review OK, standalone architecture review OK, and on-disk verification complete. Full `tests\` currently has an unrelated codegen sandbox flake (`249 passed, 2 failed` in `tests/test_codegen_sandbox_anchor.py`, moving between allowlisted matplotlib timeout/image-path cases on rerun).
## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Durable worker health polling maintainability refactor`

- [x] Preserve ADR-0015 behavior, schemas, BDD/evidence, eval output, and dashboard-card safety
- [x] Split production polling constants/contract/storage/state helpers from the public orchestration facade
- [x] Split verifier fixtures, scenario cases, and aggregate verifier from the public anchor facade
- [x] Re-run focused polling tests in `.venv` (`17 passed`)
- [x] Re-run focused durable polling eval in `.venv` (`PASS home_assistant_durable_worker_health_polling_scaffold`)
- [x] Re-run adjacent worker regression tests in `.venv` (`81 passed`)
- [x] Run module `py_compile` for all touched/new polling modules
- [x] Re-run full Python suite and preserve known codegen sandbox flake posture (`267 passed, 1 failed`; failed test passed on rerun)
- [x] Run inline BDD-evidence review against the durable polling scenarios
- [x] Check diff formatting (`git diff --check` clean aside from normal CRLF warning)
- [x] Run standalone architecture review against the refactor diff

## Open queue (non-blocking)

> Things worth doing that don't gate the current packet. Pull from here when the active packet closes.

- (a) Aggregate-style ambiguous entity clarification executable eval
- (b) Aggregate alias creation/reuse executable eval
- (c) Post-MVP floorplan heatmap renderer requiring explicit user-provided room
  geometry and area/entity mappings
- (d) Keep remaining worker/orchestration work split into smaller packets:
  token rotation UI/persistence/automatic repair, provider health/retry
  policy, durable retry queue/scheduler behavior, and any durable polling
  production-hardening follow-up requested by review should each land
  separately.

## Blockers

- None.
