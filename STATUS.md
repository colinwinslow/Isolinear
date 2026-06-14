# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-14 (HACS install packaging completed)
**Phase:** `First real vertical slice accepted`
**Next bounded packet:** `Live HACS install and worker-rendered served-artifact verification`
**Current readiness:** `READY FOR NEXT PACKET`

> **⚠️ Direction change (2026-06-12):** Before picking another scaffold packet,
> read [`docs/reality-pivot-review.md`](docs/reality-pivot-review.md). The next
> work is a **real vertical slice** (real recorder history + real Ollama +
> real matplotlib, rendered in-process) — not another simulated scaffold. Stop
> adding `*_anchor.py` verifiers; pytest is the single source of behavioral truth.

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-14** — `HACS install packaging` — Made the Home Assistant integration installable as a HACS custom repository of type `integration`. Added root `hacs.json`, the HACS-required `issue_tracker` manifest field, package-local path helpers, bundled runtime schemas under `custom_components/isolinear/schemas`, bundled dashboard card assets under `custom_components/isolinear/frontend/dist`, and updated `scripts/frontend.ps1 build` so frontend builds refresh the packaged card bundle. Runtime validators now resolve JSON Schemas from the installed integration package instead of repo-root `docs/schemas`, and dashboard resource registration serves the packaged card while preserving `/api/isolinear/static/isolinear-card.js`. Added the paired spec, BDD, eval outline, eval, evidence, README install/update docs, and focused packaging pytest. Verification: frontend build passed, focused HACS/dashboard-resource/first-real-slice/worker-rendered pytest (`25 passed`), HACS packaging eval (`PASS`), module `compileall` passed, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK, standalone architecture review OK with no blocking findings.
- **2026-06-14** — `Worker-rendered artifact serving` — Added the paired worker-rendered artifact-serving spec, BDD, and evidence. The first-real-slice prompt/history/planner path can now use a configured worker renderer: worker `RenderResult` may carry bounded `image_bytes_base64`, the integration validates PNG bytes, writes them to integration-owned artifact storage, stores rendered artifact metadata with `/api/isolinear/artifacts/<artifact_id>.png`, stores redacted worker dispatch metadata only after artifact validation, and strips worker/local image paths plus base64 bytes from registered WebSocket responses. Missing worker image bytes now fail before artifact/render/dispatch storage or file writes; failed worker render results keep the sanitized worker-failure path. The architecture review found two blockers, now fixed: schema `maxLength` is enforced for oversized worker image bytes, and post-write worker progress rejection rolls back the PNG plus artifact-write metadata. The older worker dispatch scaffold remains scoped to no-file placeholder behavior when no model-provider real-slice plan exists. Verification: focused worker-rendered pytest (`6 passed`), adjacent first-real-slice/worker-dispatch/dashboard-smoke bundle (`18 passed`), full Python suite (`315 passed`), worker-dispatch scaffold eval (`PASS`), rerun standalone architecture review (`No blocking findings`).
- **2026-06-13** — `Production artifact serving` — Added ADR-0018 plus the paired production artifact-serving spec, BDD, and evidence. The first-real-slice trusted in-process renderer now writes validated PNG bytes to integration-owned artifact storage, registers `/api/isolinear/artifacts`, returns same-origin served chart URLs instead of WebSocket data URLs, reuses completed PNG artifacts idempotently, rejects hidden-entity planner output before rendering or file writes, rolls back written PNG files plus artifact/render/provider bookkeeping if final complete snapshot validation fails, and strips local filesystem paths from registered WebSocket responses. Updated the dashboard long-running smoke docs/tests from data URLs to served artifact URLs. Verification: focused production serving pytest (`7 passed`), dashboard smoke (`1 passed`), WebSocket registration-adjacent bundle (`16 passed`), full Python suite (`309 passed`), adjacent artifact-storage eval (`PASS home_assistant_job_orchestration_artifact_storage_scaffold`), frontend tests (`2 passed`, `5 tests`), frontend build passed, module `compileall` passed, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK, standalone architecture review OK with no recommendations.
- **2026-06-13** — `Dashboard card long-running smoke` — Added active-job polling to the Lit dashboard card so `planning`, `fetching_history`, `rendering`, and `validating` snapshots automatically continue through `isolinear/v1/job/snapshot` until a terminal result, with polling cancelled on disconnect, new prompt, retry, or terminal state. Added a mounted `happy-dom` Vitest smoke proving `job/start` is followed by automatic `job/snapshot`, duplicate submit is disabled while active, and the final card is chart-first with a PNG data URL. Added a focused registered WebSocket pytest proving the same command sequence returns a first-real-slice PNG snapshot, calls the planner once with only `sensor.upstairs_temperature`, and does not call the worker. Added the paired draft spec, BDD, evidence, harness page, docs index updates, and rebuilt `frontend/dist/isolinear-card.js`. Verification: frontend build passed, frontend tests (`2 passed`, `5 tests`), focused Python bundle (`12 passed`), `git diff --check` clean aside from normal CRLF warnings, BDD-evidence review OK, standalone architecture review OK with no recommendations.
- **2026-06-13** — `ADR-0017 promotion` — Promoted ADR-0017, the paired first-real-slice spec, and the paired BDD from draft to accepted using the captured manual real Home Assistant + Ollama evidence. The ADR now records the accepted in-process real-slice decision, live verification path, returned PNG data URL, zero worker dispatches, and runtime drift fixes for Home Assistant WebSocket async handling plus the narrowed Ollama structured-output schema. `HANDOFF.md` and the ADR index now point at accepted ADR-0017 and no longer list promotion as a next packet. Verification: focused first-real-slice tests via repo venv (`4 passed`), `git diff --check` clean aside from normal CRLF warnings. The global Python path currently lacks pytest, so the focused run used `.\.venv\Scripts\python.exe`.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `HACS install packaging`

- [x] Add paired spec, BDD, eval outline, eval, and evidence for HACS install packaging
- [x] Add root `hacs.json` and HACS-ready manifest metadata
- [x] Bundle runtime JSON Schemas under `custom_components/isolinear/schemas`
- [x] Bundle the dashboard card under `custom_components/isolinear/frontend/dist`
- [x] Resolve runtime schemas and card assets from the installed integration package
- [x] Update frontend build helper to refresh the packaged card bundle
- [x] Document the HACS custom-repository install/update flow
- [x] Prove focused packaging, dashboard resource, first-real-slice, worker-rendered, eval, build, compile, BDD-evidence, and architecture-review checks

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
- (e) Install the integration through HACS as a custom repository and run the
  worker-rendered served-artifact path against live Home Assistant sensor
  history.

## Blockers

- None.
