# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-17 (Pillow in-process renderer; matplotlib requirement removed)
**Phase:** `First real vertical slice accepted`
**Next bounded packet:** `Live HACS 0.1.20 dashboard verification`
**Current readiness:** `READY FOR LIVE TEST`

> **⚠️ Direction change (2026-06-12):** Before picking another scaffold packet,
> read [`docs/reality-pivot-review.md`](docs/reality-pivot-review.md). The next
> work is a **real vertical slice** (real recorder history + real Ollama +
> real matplotlib, rendered in-process) — not another simulated scaffold. Stop
> adding `*_anchor.py` verifiers; pytest is the single source of behavioral truth.

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-17** — `Pillow in-process renderer (matplotlib requirement removed)` — Live `0.1.19` install showed the integration as **"not loaded"** with the dashboard resource stuck at `?v=0.1.18`. HA logs gave the decisive cause: `Unable to install package matplotlib>=3.7,<4` → the loose range resolved to `matplotlib==3.11.0`, which has **no wheel for the runtime CPython 3.14**, so pip built from source and failed with `PermissionError: [Errno 13] Permission denied: 'meson'`. A failed manifest-requirement install makes the integration fail to load, which also explains the stale resource (setup never reached the resource-registration step). matplotlib-via-manifest is therefore a dead end in this environment. Per **ADR-0019**, the trusted in-process renderer now draws with **Pillow** (already shipped by HA core) instead of matplotlib: the manifest `requirements` is now `[]`, the renderer identifier is `in_process_pillow` (artifact-metadata schema enum updated in both synced copies), the scaffold guard forbids **any** `matplotlib` requirement (not just `==` pins), and the renderer imports Pillow lazily and still fails closed as `renderer_dependency_unavailable`. The render interface, supported scope (safe numeric `time_series` lines), failure codes, and PNG artifact contract are unchanged. Anchor verified: a two-series ChartSpec produced a valid 25 KB PNG (correct signature, reopenable at 1400×800). The visible package version is `0.1.20`. Verification: full suite `351 passed` (venv Python 3.14.5 / Pillow 12.2.0, matching the live runtime), HACS packaging eval `PASS` (`requirements: []`), integration scaffold eval `PASS`, schema copies byte-identical, `git diff --check` clean.
- **2026-06-17** — `matplotlib loose-range requirement restoration` — Live `0.1.18` test confirmed the lazy-import fail-closed path fires correctly: the card showed `failure.stage: chart_rendering` / `RENDERER_DEPENDENCY_UNAVAILABLE` / "The trusted chart renderer dependency is not installed in this Home Assistant environment." Charts can never render on a fresh HA install without manually pip-installing matplotlib, so `matplotlib>=3.7,<4` is re-added to manifest `requirements`. The strict-pin `matplotlib==3.11.0` that caused the 0.1.16 config-flow 500 is not restored; a loose range lets pip's resolver pick a compatible version. The integration scaffold guard is narrowed from flagging any `matplotlib` prefix to flagging only `matplotlib==` exact pins. The HACS packaging spec, eval YAML, and proof assertions are updated to require the loose-range requirement. The visible package version is `0.1.19`. Verification: `11 passed` (focused HACS/scaffold tests), `350 passed` (full venv suite, 1 font-cache timing flake passes on rerun), HACS packaging eval `PASS`, integration scaffold eval `PASS`, architecture review `OK`, BDD-evidence review `OK`, `git diff --check` clean.
- **2026-06-17** — `Config-flow-safe renderer dependency rollback` — Live reinstall of `0.1.16` reached HACS download but failed before the first Isolinear setup form, spending about 30 seconds on `Please wait, starting configuration wizard for Isolinear` and then returning `Config flow could not be loaded: 500 Internal Server Error`. Home Assistant's manifest docs state that requirements are installed before startup/config-flow loading and failed installs make the component fail to load, so the heavy renderer-only `matplotlib==3.11.0` manifest requirement introduced in `0.1.15` was removed. The trusted in-process renderer still imports matplotlib lazily and fails closed as a sanitized chart-rendering job failure if unavailable. The visible package version is `0.1.17`, package-versioned dashboard resource proof now targets `?v=0.1.17`, and HACS/scaffold proof now fails if renderer-only config-flow-blocking requirements are reintroduced. Verification: focused config-flow/HACS/integration tests (`22 passed`), focused HACS/dashboard-resource/integration tests (`19 passed`), dashboard resource test (`8 passed`), HACS packaging eval `PASS`, dashboard resource registration eval `PASS`, integration scaffold eval `PASS`, config-flow eval `PASS`, `git diff --check` clean aside from normal CRLF warnings.
- **2026-06-17** — `Lovelace dependency cold-boot resource refresh fix` — Live HACS showed commit `18f95bd` installed, but after a full hardware reboot the dashboard resource metadata still pointed at `/api/isolinear/static/isolinear-card.js?v=0.1.14` instead of the `0.1.15` package URL. Local proof already showed stale query-string resources update in place when the Lovelace resource collection is available, so the likely live gap was Home Assistant cold-boot ordering: Isolinear can set up before Lovelace resource storage exists because the manifest declared no Lovelace dependency. The manifest now declares `dependencies: ["lovelace"]`, the visible package version is `0.1.16`, and HACS packaging proof now fails if the Lovelace dependency is omitted. Dashboard resource and HACS evidence were refreshed to prove the current package-versioned URL is `?v=0.1.16` and stale Isolinear resource metadata updates in place. Verification: focused HACS/dashboard-resource/integration tests (`19 passed`), HACS packaging eval `PASS`, dashboard resource registration eval `PASS`, integration scaffold eval `PASS`, `git diff --check` clean aside from normal CRLF warnings.
- **2026-06-17** — `Trusted renderer dependency and failure snapshot live fix` — Live `0.1.14` diagnostic logs after 9:10 PM showed the dashboard card reached real backend `job/snapshot` handling and was rejected as `code=in_process_renderer_failed` after recorder history access, which pointed at the trusted matplotlib renderer path rather than a frontend-only polling bug. The HACS manifest now declares the runtime renderer dependency `matplotlib==3.11.0`, the visible package version is `0.1.15`, and packaging/scaffold proof now fails if the renderer dependency is omitted. In-process renderer failures now append sanitized card-facing failed job snapshots with `failure.stage: chart_rendering` and `failure.code: in_process_renderer_failed` instead of rejecting snapshot polling as `SNAPSHOT_POLL_FAILED`; no PNG files or artifact/provider/render bookkeeping are written on that failure path. BDD/spec/evidence were refreshed for the renderer-failure scenario. Verification: full Python suite (`349 passed`), focused first-real/model-provider renderer suite (`23 passed`), first-real/HACS/integration focused suite (`23 passed`), HACS packaging eval `PASS`, integration scaffold eval `PASS`, architecture review `OK`, BDD-evidence review `OK`, `git diff --check` clean aside from normal CRLF warnings.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Pillow in-process renderer (matplotlib requirement removed)`

- [x] Diagnose `0.1.19` "not loaded": matplotlib build failed (no CPython 3.14 wheel; meson permission denied)
- [x] ADR-0019: render in-process with Pillow (shipped by HA core) instead of matplotlib
- [x] Reimplement `_render_time_series_png` with Pillow; rename renderer to `in_process_pillow`
- [x] Remove `matplotlib` from manifest `requirements` (now `[]`); bump version to `0.1.20`
- [x] Forbid any `matplotlib` requirement in the scaffold guard + HACS/scaffold proof
- [x] Update artifact-metadata schema enum (both synced copies), specs, BDD evidence, HACS eval
- [x] Verify: anchor PNG on disk, full suite `351 passed`, HACS + scaffold evals `PASS`

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
- (e) Redownload Isolinear `0.1.20` through HACS, restart Home Assistant, and
  confirm the integration now **loads** (no "not loaded", no manifest
  requirement install — Pillow ships with HA core). Confirm the config-flow
  wizard renders (not a 500), the registered Lovelace resource URL updates to
  `?v=0.1.20`, the picker default is `config_entry_id: auto`, the options flow
  stores the exact selected entity IDs, the served-artifact prompt path runs
  against live sensor history, and a Pillow chart renders (not
  RENDERER_DEPENDENCY_UNAVAILABLE). If the renderer still reports dependency
  unavailable, capture HA logs for any `PIL`/`Pillow` import error.
- (f) Move setup-time schema file reads off the Home Assistant event loop; live
  `0.1.2` logs show blocking-call warnings in worker token lifecycle,
  readiness, and health polling validation.

## Blockers

- None.
