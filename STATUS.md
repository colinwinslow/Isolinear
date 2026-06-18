# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-18 (Model-resolved time window + tiered history data source)
**Phase:** `First real vertical slice accepted`
**Next bounded packet:** `Live HACS 0.1.22 verification (model-resolved window + statistics)`
**Current readiness:** `READY FOR LIVE TEST`

> **⚠️ Direction change (2026-06-12):** Before picking another scaffold packet,
> read [`docs/reality-pivot-review.md`](docs/reality-pivot-review.md). The next
> work is a **real vertical slice** (real recorder history + real Ollama +
> real matplotlib, rendered in-process) — not another simulated scaffold. Stop
> adding `*_anchor.py` verifiers; pytest is the single source of behavioral truth.

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-18** — `Model-resolved time window + tiered history data source` — Live `0.1.20` confirmed the Pillow renderer works end-to-end, but the chart was illegible on a phone and the time window was wrong. `0.1.21` (committed earlier this session) enlarged renderer fonts/strokes for the mobile downscale and added a regex that honored "last N hours/days/weeks". The user then redirected the window design: window determination should be **model-driven**, not a regex, and should reach beyond recorder retention via long-term statistics. This packet (`0.1.22`) implements that across **ADR-0020** (model-resolved window) and **ADR-0021** (tiered data source). The planner request now carries `now` + HA `time_zone`; the model emits an absolute `chart_spec.time_range {start,end}`; the integration validates/clamps it deterministically (tz-normalize, `start<end`, clamp `end<=now`, span `<=366d`, floor `60s`) and falls back to a fixed last-24h window on any failure — the regex is **removed entirely**. For the first-real-slice path history is now fetched **after** planning with the resolved window (so beyond-retention windows are not rejected at `job/start`); the legacy scaffold path keeps raw start-time fetch (`allow_statistics` opt-in). Data source is tiered by window: raw recorder states (recent/short), hourly statistics (`<=60d`), daily statistics (longer), single-source-per-window. Each `HistorySeries` records `source`/`resolution`; statistics points carry `value` (mean) + `value_min`/`value_max`; the Pillow renderer shades a min/max band behind the mean line. Entities without long-term statistics over a beyond-retention window fail closed with a card-facing `no_long_term_statistics` snapshot. Schema: HistorySeries gains band point fields + `source`/`resolution`; planner request gains `now`/`time_zone` (propagated to the model-provider plan and retry-policy schemas); all synced copies byte-identical. Verification: full suite `370 passed`, `52` evals `PASS` (incl. new `model_resolved_window_data_source`), HACS packaging eval `PASS`, anchor statistics-band PNG verified on disk (`in_process_pillow`, 1400×800, valid signature), architecture review `CONCERNS→resolved` (ADR-0021 executor wording reconciled; no invariant violations), BDD-evidence review `OK` (scenarios A–H with raw outputs), `git diff --check` clean. **Caveat:** the live `statistics_during_period`/`keep_days` recorder calls are behind `# pragma: no cover` import guards (same pattern as the existing recorder read) and are exercised only via injected fakes — the live call signature needs a real HACS `0.1.22` retest to confirm.
- **2026-06-17** — `Pillow in-process renderer (matplotlib requirement removed)` — Live `0.1.19` install showed the integration as **"not loaded"** with the dashboard resource stuck at `?v=0.1.18`. HA logs gave the decisive cause: `Unable to install package matplotlib>=3.7,<4` → the loose range resolved to `matplotlib==3.11.0`, which has **no wheel for the runtime CPython 3.14**, so pip built from source and failed with `PermissionError: [Errno 13] Permission denied: 'meson'`. A failed manifest-requirement install makes the integration fail to load, which also explains the stale resource (setup never reached the resource-registration step). matplotlib-via-manifest is therefore a dead end in this environment. Per **ADR-0019**, the trusted in-process renderer now draws with **Pillow** (already shipped by HA core) instead of matplotlib: the manifest `requirements` is now `[]`, the renderer identifier is `in_process_pillow` (artifact-metadata schema enum updated in both synced copies), the scaffold guard forbids **any** `matplotlib` requirement (not just `==` pins), and the renderer imports Pillow lazily and still fails closed as `renderer_dependency_unavailable`. The render interface, supported scope (safe numeric `time_series` lines), failure codes, and PNG artifact contract are unchanged. Anchor verified: a two-series ChartSpec produced a valid 25 KB PNG (correct signature, reopenable at 1400×800). The visible package version is `0.1.20`. Verification: full suite `351 passed` (venv Python 3.14.5 / Pillow 12.2.0, matching the live runtime), HACS packaging eval `PASS` (`requirements: []`), integration scaffold eval `PASS`, schema copies byte-identical, `git diff --check` clean.
- **2026-06-17** — `matplotlib loose-range requirement restoration` — Live `0.1.18` test confirmed the lazy-import fail-closed path fires correctly: the card showed `failure.stage: chart_rendering` / `RENDERER_DEPENDENCY_UNAVAILABLE` / "The trusted chart renderer dependency is not installed in this Home Assistant environment." Charts can never render on a fresh HA install without manually pip-installing matplotlib, so `matplotlib>=3.7,<4` is re-added to manifest `requirements`. The strict-pin `matplotlib==3.11.0` that caused the 0.1.16 config-flow 500 is not restored; a loose range lets pip's resolver pick a compatible version. The integration scaffold guard is narrowed from flagging any `matplotlib` prefix to flagging only `matplotlib==` exact pins. The HACS packaging spec, eval YAML, and proof assertions are updated to require the loose-range requirement. The visible package version is `0.1.19`. Verification: `11 passed` (focused HACS/scaffold tests), `350 passed` (full venv suite, 1 font-cache timing flake passes on rerun), HACS packaging eval `PASS`, integration scaffold eval `PASS`, architecture review `OK`, BDD-evidence review `OK`, `git diff --check` clean.
- **2026-06-17** — `Config-flow-safe renderer dependency rollback` — Live reinstall of `0.1.16` reached HACS download but failed before the first Isolinear setup form, spending about 30 seconds on `Please wait, starting configuration wizard for Isolinear` and then returning `Config flow could not be loaded: 500 Internal Server Error`. Home Assistant's manifest docs state that requirements are installed before startup/config-flow loading and failed installs make the component fail to load, so the heavy renderer-only `matplotlib==3.11.0` manifest requirement introduced in `0.1.15` was removed. The trusted in-process renderer still imports matplotlib lazily and fails closed as a sanitized chart-rendering job failure if unavailable. The visible package version is `0.1.17`, package-versioned dashboard resource proof now targets `?v=0.1.17`, and HACS/scaffold proof now fails if renderer-only config-flow-blocking requirements are reintroduced. Verification: focused config-flow/HACS/integration tests (`22 passed`), focused HACS/dashboard-resource/integration tests (`19 passed`), dashboard resource test (`8 passed`), HACS packaging eval `PASS`, dashboard resource registration eval `PASS`, integration scaffold eval `PASS`, config-flow eval `PASS`, `git diff --check` clean aside from normal CRLF warnings.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Model-resolved time window + tiered history data source (0.1.22)`

- [x] `0.1.21`: enlarge renderer fonts/strokes for mobile downscale (committed earlier this session)
- [x] ADR-0020: model resolves an absolute window (`now`+`time_zone` in request); deterministic clamp/validate; last-24h fallback; regex retired
- [x] ADR-0021: tiered data source (raw / hourly / daily statistics); `no_long_term_statistics` fail-closed; min/max band rendering
- [x] Reorder first-real-slice: fetch history after planning with resolved window; scaffold path keeps raw start-time fetch (`allow_statistics` opt-in)
- [x] Schema: HistorySeries band fields + `source`/`resolution`; planner request `now`/`time_zone` (plan + retry-policy schemas); synced copies byte-identical
- [x] Verify: `370 passed`, `52` evals `PASS`, anchor band PNG on disk, both reviews, bump to `0.1.22`, commit `f36775c`

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
- (e) Live HACS `0.1.22` retest of the model-resolved window + statistics path
  (the `0.1.20` Pillow load + render was already confirmed live; `0.1.21`
  legibility/fonts shipped on top). Confirm: a fuzzy/relative prompt (e.g.
  "attic temperature last weekend") resolves a sane bounded window and renders;
  a long window (e.g. "last 90 days") against a `state_class` sensor renders a
  **daily statistics** chart with a min/max band (not 24h, not empty); a
  non-`state_class` entity over a beyond-retention window shows a card-facing
  `no_long_term_statistics` failure (not a silent empty chart). This is the only
  path whose live recorder calls (`statistics_during_period`, `keep_days`) are
  not exercised by unit tests — capture HA logs for any
  `statistics_during_period` TypeError/signature mismatch.
- (f) Move setup-time schema file reads off the Home Assistant event loop; live
  `0.1.2` logs show blocking-call warnings in worker token lifecycle,
  readiness, and health polling validation.

## Blockers

- None.
