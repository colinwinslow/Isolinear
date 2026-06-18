# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-17 (matplotlib loose-range requirement restoration)
**Phase:** `First real vertical slice accepted`
**Next bounded packet:** `Live HACS 0.1.19 dashboard verification`
**Current readiness:** `READY FOR LIVE TEST`

> **⚠️ Direction change (2026-06-12):** Before picking another scaffold packet,
> read [`docs/reality-pivot-review.md`](docs/reality-pivot-review.md). The next
> work is a **real vertical slice** (real recorder history + real Ollama +
> real matplotlib, rendered in-process) — not another simulated scaffold. Stop
> adding `*_anchor.py` verifiers; pytest is the single source of behavioral truth.

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-17** — `matplotlib loose-range requirement restoration` — Live `0.1.18` test confirmed the lazy-import fail-closed path fires correctly: the card showed `failure.stage: chart_rendering` / `RENDERER_DEPENDENCY_UNAVAILABLE` / "The trusted chart renderer dependency is not installed in this Home Assistant environment." Charts can never render on a fresh HA install without manually pip-installing matplotlib, so `matplotlib>=3.7,<4` is re-added to manifest `requirements`. The strict-pin `matplotlib==3.11.0` that caused the 0.1.16 config-flow 500 is not restored; a loose range lets pip's resolver pick a compatible version. The integration scaffold guard is narrowed from flagging any `matplotlib` prefix to flagging only `matplotlib==` exact pins. The HACS packaging spec, eval YAML, and proof assertions are updated to require the loose-range requirement. The visible package version is `0.1.19`. Verification: `11 passed` (focused HACS/scaffold tests), `350 passed` (full venv suite, 1 font-cache timing flake passes on rerun), HACS packaging eval `PASS`, integration scaffold eval `PASS`, architecture review `OK`, BDD-evidence review `OK`, `git diff --check` clean.
- **2026-06-17** — `Config-flow-safe renderer dependency rollback` — Live reinstall of `0.1.16` reached HACS download but failed before the first Isolinear setup form, spending about 30 seconds on `Please wait, starting configuration wizard for Isolinear` and then returning `Config flow could not be loaded: 500 Internal Server Error`. Home Assistant's manifest docs state that requirements are installed before startup/config-flow loading and failed installs make the component fail to load, so the heavy renderer-only `matplotlib==3.11.0` manifest requirement introduced in `0.1.15` was removed. The trusted in-process renderer still imports matplotlib lazily and fails closed as a sanitized chart-rendering job failure if unavailable. The visible package version is `0.1.17`, package-versioned dashboard resource proof now targets `?v=0.1.17`, and HACS/scaffold proof now fails if renderer-only config-flow-blocking requirements are reintroduced. Verification: focused config-flow/HACS/integration tests (`22 passed`), focused HACS/dashboard-resource/integration tests (`19 passed`), dashboard resource test (`8 passed`), HACS packaging eval `PASS`, dashboard resource registration eval `PASS`, integration scaffold eval `PASS`, config-flow eval `PASS`, `git diff --check` clean aside from normal CRLF warnings.
- **2026-06-17** — `Lovelace dependency cold-boot resource refresh fix` — Live HACS showed commit `18f95bd` installed, but after a full hardware reboot the dashboard resource metadata still pointed at `/api/isolinear/static/isolinear-card.js?v=0.1.14` instead of the `0.1.15` package URL. Local proof already showed stale query-string resources update in place when the Lovelace resource collection is available, so the likely live gap was Home Assistant cold-boot ordering: Isolinear can set up before Lovelace resource storage exists because the manifest declared no Lovelace dependency. The manifest now declares `dependencies: ["lovelace"]`, the visible package version is `0.1.16`, and HACS packaging proof now fails if the Lovelace dependency is omitted. Dashboard resource and HACS evidence were refreshed to prove the current package-versioned URL is `?v=0.1.16` and stale Isolinear resource metadata updates in place. Verification: focused HACS/dashboard-resource/integration tests (`19 passed`), HACS packaging eval `PASS`, dashboard resource registration eval `PASS`, integration scaffold eval `PASS`, `git diff --check` clean aside from normal CRLF warnings.
- **2026-06-17** — `Trusted renderer dependency and failure snapshot live fix` — Live `0.1.14` diagnostic logs after 9:10 PM showed the dashboard card reached real backend `job/snapshot` handling and was rejected as `code=in_process_renderer_failed` after recorder history access, which pointed at the trusted matplotlib renderer path rather than a frontend-only polling bug. The HACS manifest now declares the runtime renderer dependency `matplotlib==3.11.0`, the visible package version is `0.1.15`, and packaging/scaffold proof now fails if the renderer dependency is omitted. In-process renderer failures now append sanitized card-facing failed job snapshots with `failure.stage: chart_rendering` and `failure.code: in_process_renderer_failed` instead of rejecting snapshot polling as `SNAPSHOT_POLL_FAILED`; no PNG files or artifact/provider/render bookkeeping are written on that failure path. BDD/spec/evidence were refreshed for the renderer-failure scenario. Verification: full Python suite (`349 passed`), focused first-real/model-provider renderer suite (`23 passed`), first-real/HACS/integration focused suite (`23 passed`), HACS packaging eval `PASS`, integration scaffold eval `PASS`, architecture review `OK`, BDD-evidence review `OK`, `git diff --check` clean aside from normal CRLF warnings.
- **2026-06-17** — `WebSocket diagnostic logging live follow-up` — Live `0.1.13` still showed the card-local `SNAPSHOT_POLL_FAILED` state after repeated snapshot polling, so this packet prioritizes backend diagnostic signal over another speculative behavior change. Registered WebSocket command observability now logs and stores sanitized decision fields for message ID, command type, requested/resolved config entry, job ID, decision code, orchestration/result code, snapshot status, progress stage, failure code, and exception type where available. Unexpected registered handler exceptions are caught at the Home Assistant WebSocket boundary, returned as structured `isolinear_websocket_command_exception` errors, and logged without prompts, tokens, endpoints, raw history, generated code, generated images, local paths, or image bytes. Bumped the visible package version to `0.1.14` for HACS/Lovelace retest and refreshed WebSocket/HACS evidence. Verification: WebSocket registration tests (`18 passed`), WebSocket/resource/HACS/integration scaffold bundle (`37 passed`), dashboard long-running smoke plus first-real vertical slice tests (`15 passed`), WebSocket registration eval `PASS`, HACS packaging eval `PASS`, integration scaffold eval `PASS`, architecture review `OK`, BDD-evidence review `OK`, `git diff --check` clean aside from normal CRLF warnings.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `matplotlib loose-range requirement restoration`

- [x] Confirm live `0.1.18` RENDERER_DEPENDENCY_UNAVAILABLE failure path fires correctly
- [x] Re-add `matplotlib>=3.7,<4` to manifest `requirements` (loose range, not strict pin)
- [x] Narrow integration scaffold guard from any `matplotlib` prefix to `matplotlib==` only
- [x] Update HACS packaging test, eval, spec, and eval YAML to require the loose-range requirement
- [x] Bump visible integration package version to `0.1.19`

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
- (e) Redownload Isolinear `0.1.19` through HACS, restart Home Assistant,
  confirm the config-flow wizard renders (not a 500), confirm the registered
  Lovelace resource URL updates to `?v=0.1.19`, confirm the picker default is
  `config_entry_id: auto`, confirm the options flow uses the list-style entity
  selector and stores the exact selected entity IDs, run the served-artifact
  prompt path against live Home Assistant sensor history, and confirm a chart
  renders rather than returning RENDERER_DEPENDENCY_UNAVAILABLE. Capture HA
  logs for `Successfully installed matplotlib` or any pip install failure if
  the renderer still reports dependency unavailable.
- (f) Move setup-time schema file reads off the Home Assistant event loop; live
  `0.1.2` logs show blocking-call warnings in worker token lifecycle,
  readiness, and health polling validation.

## Blockers

- None.
