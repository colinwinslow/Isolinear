# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-13 (ADR-0017 promotion completed)
**Phase:** `First real vertical slice accepted`
**Next bounded packet:** `Choose next real-slice hardening packet`
**Current readiness:** `READY FOR NEXT PACKET`

> **⚠️ Direction change (2026-06-12):** Before picking another scaffold packet,
> read [`docs/reality-pivot-review.md`](docs/reality-pivot-review.md). The next
> work is a **real vertical slice** (real recorder history + real Ollama +
> real matplotlib, rendered in-process) — not another simulated scaffold. Stop
> adding `*_anchor.py` verifiers; pytest is the single source of behavioral truth.

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-13** — `ADR-0017 promotion` — Promoted ADR-0017, the paired first-real-slice spec, and the paired BDD from draft to accepted using the captured manual real Home Assistant + Ollama evidence. The ADR now records the accepted in-process real-slice decision, live verification path, returned PNG data URL, zero worker dispatches, and runtime drift fixes for Home Assistant WebSocket async handling plus the narrowed Ollama structured-output schema. `HANDOFF.md` and the ADR index now point at accepted ADR-0017 and no longer list promotion as a next packet. Verification: focused first-real-slice tests via repo venv (`4 passed`), `git diff --check` clean aside from normal CRLF warnings. The global Python path currently lacks pytest, so the focused run used `.\.venv\Scripts\python.exe`.
- **2026-06-13** — `Manual real HA + Ollama verification` — Loaded the current custom integration into real Home Assistant core (`2025.1.4`) with a real SQLite recorder database and synthetic allowlisted recorder history, configured the network Ollama endpoint at `http://10.0.1.39:11434` with `gemma4:e4b`, and dispatched `isolinear/v1/job/start` plus `isolinear/v1/job/snapshot` through the registered Home Assistant WebSocket handlers. The snapshot completed with a PNG `data:image/png;base64,...` chart, one provider plan, one render plan, one rendered artifact, zero worker dispatches, and only `sensor.isolinear_probe_temperature` history. Runtime drift closed in this packet: registered WebSocket commands now use Home Assistant's `async_response` scheduler and offload blocking orchestration through Home Assistant's executor, and the Ollama structured-output schema now narrows `chart_spec` to the first-slice `time_series` ChartSpec shape after the live model initially produced a graph-shaped payload. Verification: focused first-real-slice tests (`4 passed`), focused WebSocket registration tests (`8 passed`), targeted regression bundle (`40 passed`), full Python suite (`305 passed`), module `py_compile`, `git diff --check` clean aside from normal CRLF warnings, manual evidence captured in `bdd/integration/home-assistant-first-real-vertical-slice-evidence.md`, and standalone architecture review OK with no recommendations.
- **2026-06-13** — `First real vertical slice pivot` — Merged the reality-pivot guidance into draft ADR-0017 plus paired spec, BDD, and evidence. Added best-effort real Home Assistant registry/state metadata enrichment, best-effort recorder-history retrieval, a trusted in-process matplotlib renderer for safe numeric `time_series` ChartSpecs, schema evolution for rendered artifacts, and a first-real-slice route in the existing `job/start` -> `job/snapshot` flow that returns a PNG data URL when no worker dispatch is used. Hidden provider entity references still fail before render/artifact storage, completed snapshots are reused idempotently, and no new `*_anchor.py` verifier was added. The packet deliberately did not manually verify against a real HA dev instance or real Ollama endpoint, add generated Python/codegen, call the worker in the in-process route, add durable artifact serving, or mutate Home Assistant. Verification: focused first-real-slice tests (`3 passed`), adjacent integration/orchestration bundle (`57 passed`), full Python suite (`303 passed`), module `py_compile`, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK, and standalone architecture review OK with no invariant violations.
- **2026-06-13** — `Durable worker token lifecycle scaffold` — Added ADR-0016 plus the durable integration-owned worker token lifecycle scaffold. Config-entry setup now loads the lifecycle store before readiness/renderer setup, restores only valid same-entry persisted tokens after schema-valid lifecycle storage succeeds, fails closed before readiness/renderer setup when lifecycle storage rejects, records redacted repair-issue metadata when no valid token can be restored, records disabled lifecycle state when no worker endpoint exists, and keeps explicit provision/rotation/repair wrappers durable with rollback on lifecycle validation/storage failure. The packet deliberately did not add dashboard-card token controls, real Home Assistant Repairs flows, setup-time token generation, automatic repair execution, worker health/render calls, provider calls, durable retry queues, scheduler tasks, Home Assistant mutation, or token/endpoint leakage. Verification: red focused test failed before the production module; focused lifecycle tests (`11 passed`); focused lifecycle eval (`PASS home_assistant_durable_worker_token_lifecycle_scaffold`); adjacent worker regression bundle (`109 passed`); module `py_compile`; adjacent worker/orchestration evals passed; inline BDD-evidence review OK for scenarios A-J; standalone architecture review OK with no recommendations; and `git diff --cached --check` clean. Full `tests/` previously hit the known unrelated codegen sandbox matplotlib subprocess flake once (`298 passed, 1 failed`), and the exact failed test passed on rerun.
- **2026-06-12** — `Durable polling cancelled-state hardening` — Added a narrow durable worker health polling production-hardening follow-up: persisted `IntegrationWorkerHealthPollingState` entries whose scheduler metadata is marked `cancelled` are now rejected during storage-helper load/resume so unload-cancelled timer metadata cannot resurrect after restart. The spec, BDD, eval outline, evidence, verifier anchor, and focused tests now prove cancelled persisted polling state is skipped before merge while valid persisted entries, token-missing diagnostics, and unsaved in-memory state remain intact. Verification: red focused storage-load test failed before the guard, then passed; module `py_compile`; focused polling tests (`17 passed`); focused durable polling eval (`PASS home_assistant_durable_worker_health_polling_scaffold`); adjacent worker regression bundle (`98 passed`); inline BDD-evidence review OK for scenarios A-K; standalone architecture review OK with no recommendations; and `git diff --check` clean aside from normal CRLF warnings. The packet deliberately did not add worker calls during setup, new scheduler semantics, token repair/rotation, durable retry queues, dashboard-card commands, Home Assistant mutation, or worker render behavior.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `ADR-0017 promotion`

- [x] Promote ADR-0017 from draft to accepted
- [x] Promote the paired first-real-slice spec and BDD from draft to accepted
- [x] Record acceptance evidence in ADR-0017 using the captured live HA/Ollama run
- [x] Sync ADR index and `HANDOFF.md` next-packet guidance
- [x] Re-run focused first-real-slice pytest and diff checks

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
