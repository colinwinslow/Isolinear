# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-17 (Lovelace dependency cold-boot resource refresh fix)
**Phase:** `First real vertical slice accepted`
**Next bounded packet:** `Live HACS 0.1.16 dashboard resource verification`
**Current readiness:** `READY FOR LIVE TEST`

> **⚠️ Direction change (2026-06-12):** Before picking another scaffold packet,
> read [`docs/reality-pivot-review.md`](docs/reality-pivot-review.md). The next
> work is a **real vertical slice** (real recorder history + real Ollama +
> real matplotlib, rendered in-process) — not another simulated scaffold. Stop
> adding `*_anchor.py` verifiers; pytest is the single source of behavioral truth.

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-17** — `Lovelace dependency cold-boot resource refresh fix` — Live HACS showed commit `18f95bd` installed, but after a full hardware reboot the dashboard resource metadata still pointed at `/api/isolinear/static/isolinear-card.js?v=0.1.14` instead of the `0.1.15` package URL. Local proof already showed stale query-string resources update in place when the Lovelace resource collection is available, so the likely live gap was Home Assistant cold-boot ordering: Isolinear can set up before Lovelace resource storage exists because the manifest declared no Lovelace dependency. The manifest now declares `dependencies: ["lovelace"]`, the visible package version is `0.1.16`, and HACS packaging proof now fails if the Lovelace dependency is omitted. Dashboard resource and HACS evidence were refreshed to prove the current package-versioned URL is `?v=0.1.16` and stale Isolinear resource metadata updates in place. Verification: focused HACS/dashboard-resource/integration tests (`19 passed`), HACS packaging eval `PASS`, dashboard resource registration eval `PASS`, integration scaffold eval `PASS`, `git diff --check` clean aside from normal CRLF warnings.
- **2026-06-17** — `Trusted renderer dependency and failure snapshot live fix` — Live `0.1.14` diagnostic logs after 9:10 PM showed the dashboard card reached real backend `job/snapshot` handling and was rejected as `code=in_process_renderer_failed` after recorder history access, which pointed at the trusted matplotlib renderer path rather than a frontend-only polling bug. The HACS manifest now declares the runtime renderer dependency `matplotlib==3.11.0`, the visible package version is `0.1.15`, and packaging/scaffold proof now fails if the renderer dependency is omitted. In-process renderer failures now append sanitized card-facing failed job snapshots with `failure.stage: chart_rendering` and `failure.code: in_process_renderer_failed` instead of rejecting snapshot polling as `SNAPSHOT_POLL_FAILED`; no PNG files or artifact/provider/render bookkeeping are written on that failure path. BDD/spec/evidence were refreshed for the renderer-failure scenario. Verification: full Python suite (`349 passed`), focused first-real/model-provider renderer suite (`23 passed`), first-real/HACS/integration focused suite (`23 passed`), HACS packaging eval `PASS`, integration scaffold eval `PASS`, architecture review `OK`, BDD-evidence review `OK`, `git diff --check` clean aside from normal CRLF warnings.
- **2026-06-17** — `WebSocket diagnostic logging live follow-up` — Live `0.1.13` still showed the card-local `SNAPSHOT_POLL_FAILED` state after repeated snapshot polling, so this packet prioritizes backend diagnostic signal over another speculative behavior change. Registered WebSocket command observability now logs and stores sanitized decision fields for message ID, command type, requested/resolved config entry, job ID, decision code, orchestration/result code, snapshot status, progress stage, failure code, and exception type where available. Unexpected registered handler exceptions are caught at the Home Assistant WebSocket boundary, returned as structured `isolinear_websocket_command_exception` errors, and logged without prompts, tokens, endpoints, raw history, generated code, generated images, local paths, or image bytes. Bumped the visible package version to `0.1.14` for HACS/Lovelace retest and refreshed WebSocket/HACS evidence. Verification: WebSocket registration tests (`18 passed`), WebSocket/resource/HACS/integration scaffold bundle (`37 passed`), dashboard long-running smoke plus first-real vertical slice tests (`15 passed`), WebSocket registration eval `PASS`, HACS packaging eval `PASS`, integration scaffold eval `PASS`, architecture review `OK`, BDD-evidence review `OK`, `git diff --check` clean aside from normal CRLF warnings.
- **2026-06-16** — `Snapshot poll wrapper and provider failure live regression` — Live `0.1.12` retest still produced `SNAPSHOT_POLL_FAILED`; Edge showed the prior local snapshot-poll failure text, while the Home Assistant iPhone app showed the larger message `Isolinear WebSocket command rejected.`, proving at least one failure path was a registered WebSocket rejection rather than only a frontend timeout. The card now retries bounded active-job snapshot poll failures for Home Assistant-style generic `fail` wrappers whose message indicates timeout or connection loss, while still treating terminal Isolinear command errors such as `unknown_job` as visible failures. Model-provider output validation failures such as invalid provider ChartSpecs and hidden-entity provider output now append sanitized card-facing failed job snapshots with `model_provider_planning` details instead of surfacing as generic registered WebSocket command rejections; render/artifact validation failures still fail closed before PNG writes. Bumped the visible package version to `0.1.13` for HACS/Lovelace retest and rebuilt the packaged dashboard card bundle. Verification: frontend suite (`12 passed`), first-real vertical slice tests (`11 passed`), registered dashboard smoke (`4 passed` on rerun after one concurrent font-cache timeout), HACS/resource packaging tests (`14 passed`), HACS packaging eval `PASS`, frontend build passed, `git diff --check` clean aside from normal CRLF warnings; standalone architecture review timed out at 10 minutes, fallback inline architecture pass found no invariant violations.
- **2026-06-16** — `Snapshot poll timeout and single-flight live regression` — Live `0.1.11` retest showed the clarification continuation reached `job_orchestration_clarification_continuation_ready`, likely started the Ollama planner, then the dashboard card switched to local `SNAPSHOT_POLL_FAILED` while waiting for `job/snapshot`. The card now retries bounded transient snapshot poll failures such as Home Assistant frontend timeouts instead of immediately replacing an active job with a local failed snapshot, while terminal Isolinear rejections such as `unknown_job` still render visible failure. The backend snapshot artifact/render path now has per-job single-flight protection: overlapping snapshot polls during planner/render work return the current active planning snapshot with `job_orchestration_artifact_snapshot_in_progress` and do not start duplicate planner calls; later polls reuse the completed served PNG artifact. Bumped the visible package version to `0.1.12` for HACS/Lovelace retest and refreshed long-running card/artifact-serving evidence. Verification: focused frontend smoke (`7 passed`), full frontend suite (`11 passed`), focused registered-command smoke (`4 passed`), first-real artifact tests (`10 passed`), adjacent artifact/render/provider/clarification/HACS/resource/integration tests (`61 passed`), relevant evals `PASS`, frontend build passed, architecture review `OK`, BDD-evidence review `OK`, full Python suite (`345 passed`).
## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Lovelace dependency cold-boot resource refresh fix`

- [x] Inspect live HACS `18f95bd` install signal where resource metadata stayed on `?v=0.1.14` after hardware reboot
- [x] Identify Lovelace resource storage cold-boot ordering as the likely update gap
- [x] Declare Home Assistant `lovelace` as a manifest dependency
- [x] Bump the visible integration package version to `0.1.16`
- [x] Refresh HACS/dashboard-resource proof for `?v=0.1.16` and Lovelace dependency enforcement

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
- (e) Redownload Isolinear `0.1.16` through HACS, restart Home Assistant,
  recreate the dashboard card, confirm the registered Lovelace resource URL
  updates from the stale `?v=0.1.14` row to `?v=0.1.16`, confirm the picker default is `config_entry_id: auto`,
  confirm the options flow uses the list-style entity selector and stores the
  exact selected entity IDs,
  confirm HACS shows the repository-root Isolinear brand icon,
  run the served-artifact prompt path against live Home Assistant sensor
  history, and capture Isolinear log lines for `Isolinear WebSocket command
  accepted/rejected` if the dashboard still reaches `SNAPSHOT_POLL_FAILED`.
- (f) Move setup-time schema file reads off the Home Assistant event loop; live
  `0.1.2` logs show blocking-call warnings in worker token lifecycle,
  readiness, and health polling validation.

## Blockers

- None.
