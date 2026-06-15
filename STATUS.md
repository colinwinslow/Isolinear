# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-15 (Dashboard card auto config-entry resolution)
**Phase:** `First real vertical slice accepted`
**Next bounded packet:** `Live HACS 0.1.2 dashboard auto-entry verification`
**Current readiness:** `READY FOR LIVE TEST`

> **⚠️ Direction change (2026-06-12):** Before picking another scaffold packet,
> read [`docs/reality-pivot-review.md`](docs/reality-pivot-review.md). The next
> work is a **real vertical slice** (real recorder history + real Ollama +
> real matplotlib, rendered in-process) — not another simulated scaffold. Stop
> adding `*_anchor.py` verifiers; pytest is the single source of behavioral truth.

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-15** — `Dashboard card auto config-entry resolution` — Live dashboard use showed the card picker stub retained `config_entry_id: fake-config-entry`, making `Ask` look inert because the backend rejected the WebSocket command before the card surfaced an error. The card now defaults to `config_entry_id: auto`, start-command rejections render a visible failed snapshot, and the registered WebSocket boundary resolves `auto` to the only configured Isolinear entry while failing closed for zero or multiple entries before orchestration. Bumped the visible integration package version to `0.1.2`, rebuilt the packaged card bundle, refreshed bundled schema byte parity, and documented the explicit config-entry lookup fallback. Verification: focused dashboard/WebSocket/HACS/integration pytest via repo venv (`28 passed`), frontend tests (`7 passed`), frontend build passed, dashboard-card/WebSocket/HACS/integration evals all `PASS`, module `compileall` passed, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK for the new raw eval case, standalone architecture review OK.
- **2026-06-15** — `HACS options missing config-entry data regression` — Live HACS redownload/restart confirmed the prior commit but options editing still returned base-level `must_be_object` for both plain `sensor.family_room_sensor_temperature` and JSON-style list text. Added a regression proving an options flow whose existing config entry has missing stored setup data accepts the allowlist edit by validating against safe local-first config defaults, while explicit malformed/secret-bearing config data still fails closed. Bumped the visible integration package version to `0.1.1`, anchored manifest/constant version parity, and added the default future packet norm that completed implementation packets increment the patch version unless the human says otherwise. Verification: focused config-flow/integration-scaffold pytest via repo venv (`14 passed`), config-flow/options eval (`PASS`), integration scaffold eval (`PASS`, reports `0.1.1`), module `compileall` passed, stale-version search found no `0.1.0`/`0.2.0` package references, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK, standalone architecture review OK.
- **2026-06-15** — `HACS allowlist options regression` — During live HACS-installed options editing, allowlisting `sensor.family_room_sensor_temperature` exposed two config-flow/options rough edges: a plain entity text submission could surface a base `must_be_object` when the options flow lacked the passed config entry, and JSON-style pasted list text was treated as a literal invalid entity ID. The options-flow factory now retains the Home Assistant config entry, the options normalizer accepts a raw single entity string and JSON-style pasted list text before the existing schema validation gate, and the paired config-flow/options spec, BDD, eval outline, eval, and evidence now capture the regression. Verification: focused config-flow pytest via repo venv (`8 passed`), config-flow/options eval (`PASS`), module `compileall` passed, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK, standalone architecture review OK with no recommendations.
- **2026-06-14** — `HACS install packaging` — Made the Home Assistant integration installable as a HACS custom repository of type `integration`. Added root `hacs.json`, the HACS-required `issue_tracker` manifest field, package-local path helpers, bundled runtime schemas under `custom_components/isolinear/schemas`, bundled dashboard card assets under `custom_components/isolinear/frontend/dist`, and updated `scripts/frontend.ps1 build` so frontend builds refresh the packaged card bundle. Runtime validators now resolve JSON Schemas from the installed integration package instead of repo-root `docs/schemas`, and dashboard resource registration serves the packaged card while preserving `/api/isolinear/static/isolinear-card.js`. Added the paired spec, BDD, eval outline, eval, evidence, README install/update docs, and focused packaging pytest. Verification: frontend build passed, focused HACS/dashboard-resource/first-real-slice/worker-rendered pytest (`25 passed`), HACS packaging eval (`PASS`), module `compileall` passed, `git diff --check` clean aside from normal CRLF warnings, inline BDD-evidence review OK, standalone architecture review OK with no blocking findings.
- **2026-06-14** — `Worker-rendered artifact serving` — Added the paired worker-rendered artifact-serving spec, BDD, and evidence. The first-real-slice prompt/history/planner path can now use a configured worker renderer: worker `RenderResult` may carry bounded `image_bytes_base64`, the integration validates PNG bytes, writes them to integration-owned artifact storage, stores rendered artifact metadata with `/api/isolinear/artifacts/<artifact_id>.png`, stores redacted worker dispatch metadata only after artifact validation, and strips worker/local image paths plus base64 bytes from registered WebSocket responses. Missing worker image bytes now fail before artifact/render/dispatch storage or file writes; failed worker render results keep the sanitized worker-failure path. The architecture review found two blockers, now fixed: schema `maxLength` is enforced for oversized worker image bytes, and post-write worker progress rejection rolls back the PNG plus artifact-write metadata. The older worker dispatch scaffold remains scoped to no-file placeholder behavior when no model-provider real-slice plan exists. Verification: focused worker-rendered pytest (`6 passed`), adjacent first-real-slice/worker-dispatch/dashboard-smoke bundle (`18 passed`), full Python suite (`315 passed`), worker-dispatch scaffold eval (`PASS`), rerun standalone architecture review (`No blocking findings`).
## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Dashboard card auto config-entry resolution`

- [x] Confirm `fake-config-entry` causes live card start rejection
- [x] Default new card configs to `config_entry_id: auto`
- [x] Resolve `auto` to the only configured Isolinear entry before orchestration
- [x] Fail closed for zero or multiple configured Isolinear entries
- [x] Surface start-command WebSocket rejections as visible card failure snapshots
- [x] Bump visible integration package version to `0.1.2` and rebuild packaged card bundle
- [x] Update dashboard-card/API specs, BDD, eval evidence, README fallback docs, and tests
- [x] Prove focused pytest, frontend tests/build, evals, compile, diff hygiene, BDD-evidence, and architecture-review checks

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
- (e) Redownload Isolinear `0.1.2` through HACS, restart Home Assistant,
  recreate or update the dashboard card with `config_entry_id: auto`, and run
  the served-artifact prompt path against live Home Assistant sensor history.

## Blockers

- None.
