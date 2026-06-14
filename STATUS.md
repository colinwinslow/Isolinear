# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-13 (production artifact serving completed)
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

- **2026-06-13** — `Production artifact serving` — Added ADR-0018 plus the paired production artifact-serving spec, BDD, and evidence. The first-real-slice trusted in-process renderer now writes validated PNG bytes to integration-owned artifact storage, registers `/api/isolinear/artifacts`, returns same-origin served chart URLs instead of WebSocket data URLs, reuses completed PNG artifacts idempotently, rejects hidden-entity planner output before rendering or file writes, rolls back written PNG files plus artifact/render/provider bookkeeping if final complete snapshot validation fails, and strips local filesystem paths from registered WebSocket responses. Updated the dashboard long-running smoke docs/tests from data URLs to served artifact URLs. Verification: focused production serving pytest (`7 passed`), dashboard smoke (`1 passed`), WebSocket registration-adjacent bundle (`16 passed`), full Python suite (`309 passed`), adjacent artifact-storage eval (`PASS home_assistant_job_orchestration_artifact_storage_scaffold`), frontend tests (`2 passed`, `5 tests`), frontend build passed, module `compileall` passed, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK, standalone architecture review OK with no recommendations.
- **2026-06-13** — `Dashboard card long-running smoke` — Added active-job polling to the Lit dashboard card so `planning`, `fetching_history`, `rendering`, and `validating` snapshots automatically continue through `isolinear/v1/job/snapshot` until a terminal result, with polling cancelled on disconnect, new prompt, retry, or terminal state. Added a mounted `happy-dom` Vitest smoke proving `job/start` is followed by automatic `job/snapshot`, duplicate submit is disabled while active, and the final card is chart-first with a PNG data URL. Added a focused registered WebSocket pytest proving the same command sequence returns a first-real-slice PNG snapshot, calls the planner once with only `sensor.upstairs_temperature`, and does not call the worker. Added the paired draft spec, BDD, evidence, harness page, docs index updates, and rebuilt `frontend/dist/isolinear-card.js`. Verification: frontend build passed, frontend tests (`2 passed`, `5 tests`), focused Python bundle (`12 passed`), `git diff --check` clean aside from normal CRLF warnings, BDD-evidence review OK, standalone architecture review OK with no recommendations.
- **2026-06-13** — `ADR-0017 promotion` — Promoted ADR-0017, the paired first-real-slice spec, and the paired BDD from draft to accepted using the captured manual real Home Assistant + Ollama evidence. The ADR now records the accepted in-process real-slice decision, live verification path, returned PNG data URL, zero worker dispatches, and runtime drift fixes for Home Assistant WebSocket async handling plus the narrowed Ollama structured-output schema. `HANDOFF.md` and the ADR index now point at accepted ADR-0017 and no longer list promotion as a next packet. Verification: focused first-real-slice tests via repo venv (`4 passed`), `git diff --check` clean aside from normal CRLF warnings. The global Python path currently lacks pytest, so the focused run used `.\.venv\Scripts\python.exe`.
- **2026-06-13** — `Manual real HA + Ollama verification` — Loaded the current custom integration into real Home Assistant core (`2025.1.4`) with a real SQLite recorder database and synthetic allowlisted recorder history, configured the network Ollama endpoint at `http://10.0.1.39:11434` with `gemma4:e4b`, and dispatched `isolinear/v1/job/start` plus `isolinear/v1/job/snapshot` through the registered Home Assistant WebSocket handlers. The snapshot completed with a PNG `data:image/png;base64,...` chart, one provider plan, one render plan, one rendered artifact, zero worker dispatches, and only `sensor.isolinear_probe_temperature` history. Runtime drift closed in this packet: registered WebSocket commands now use Home Assistant's `async_response` scheduler and offload blocking orchestration through Home Assistant's executor, and the Ollama structured-output schema now narrows `chart_spec` to the first-slice `time_series` ChartSpec shape after the live model initially produced a graph-shaped payload. Verification: focused first-real-slice tests (`4 passed`), focused WebSocket registration tests (`8 passed`), targeted regression bundle (`40 passed`), full Python suite (`305 passed`), module `py_compile`, `git diff --check` clean aside from normal CRLF warnings, manual evidence captured in `bdd/integration/home-assistant-first-real-vertical-slice-evidence.md`, and standalone architecture review OK with no recommendations.
- **2026-06-13** — `First real vertical slice pivot` — Merged the reality-pivot guidance into draft ADR-0017 plus paired spec, BDD, and evidence. Added best-effort real Home Assistant registry/state metadata enrichment, best-effort recorder-history retrieval, a trusted in-process matplotlib renderer for safe numeric `time_series` ChartSpecs, schema evolution for rendered artifacts, and a first-real-slice route in the existing `job/start` -> `job/snapshot` flow that returns a PNG data URL when no worker dispatch is used. Hidden provider entity references still fail before render/artifact storage, completed snapshots are reused idempotently, and no new `*_anchor.py` verifier was added. The packet deliberately did not manually verify against a real HA dev instance or real Ollama endpoint, add generated Python/codegen, call the worker in the in-process route, add durable artifact serving, or mutate Home Assistant. Verification: focused first-real-slice tests (`3 passed`), adjacent integration/orchestration bundle (`57 passed`), full Python suite (`303 passed`), module `py_compile`, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK, and standalone architecture review OK with no invariant violations.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Production artifact serving`

- [x] Add ADR-0018 plus paired spec, BDD, and raw evidence
- [x] Register `/api/isolinear/artifacts` during config-entry setup
- [x] Write validated trusted-renderer PNG bytes to integration-owned storage
- [x] Return served chart URLs and keep registered WebSocket responses path-safe
- [x] Prove hidden-entity, validation-failure rollback, idempotence, dashboard-card, full-suite, and architecture-review checks

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
