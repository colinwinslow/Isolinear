# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-18 (Categorical timeline render family — 0.1.25)
**Phase:** `First real vertical slice accepted`
**Next bounded packet:** `0.1.26 fast-follow: numeric line + binary shaded_intervals overlay (mixed composition + multi-entity resolution) — ADR-0022 D4/D5, BDD Scenario M (PENDING). Night mode (item (h)) and live HACS retests (item (e)) still open.`
**Current readiness:** `READY FOR LIVE TEST`

> **⚠️ Direction change (2026-06-12):** Before picking another scaffold packet,
> read [`docs/reality-pivot-review.md`](docs/reality-pivot-review.md). The next
> work is a **real vertical slice** (real recorder history + real Ollama +
> real matplotlib, rendered in-process) — not another simulated scaffold. Stop
> adding `*_anchor.py` verifiers; pytest is the single source of behavioral truth.

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-18** — `Categorical timeline render family (0.1.25)` — Diagnosed why the user's `binary_sensor.kitchen_door` test failed with the misleading `model_provider_chart_spec_hidden_entity` instead of the intended `no_long_term_statistics`: a binary entity can't satisfy the numeric-only planner schema, so the model substituted an entity and the entity-validation gate fired **before** history retrieval (the ADR-0020 reorder puts history after planning). Rather than dead-end binary entities, this packet (**ADR-0022**) makes them chart. **Deterministic 3-way render-family routing** (`_resolve_render_family` in `job_orchestration.py`, by `_series_kind` *before* planning): all-numeric → `time_series`/`line`; all binary/categorical → new `timeline`/`step` family; mixed → fails closed with `mixed_chart_composition_unsupported` (overlay deferred to 0.1.26). The integration selects the per-family Ollama structured-output schema (`load_planner_result_schema(family)`), so the model never picks `chart_type`. The live Pillow renderer gained `_render_timeline_png` (one lane per series, on/off + categorical bands, phone-legible) built on a shared `_binary_on_regions` primitive reused by the 0.1.26 overlay. Also split the misleading hidden-entity code into honest `model_provider_referenced_unapproved_entity` (absent from catalog) vs `model_provider_substituted_entity` (approved but not disclosed). No **core** schema change (chart-spec already allows `timeline`/`step` + `overlays[]`). Verification: full suite `388 passed` (renderer, routing, e2e binary timeline, beyond-retention-binary, disambiguation, mixed-fail; reds confirmed), new eval `timeline_render_family_routing` PASS + 51 prior evals PASS, anchor two-lane timeline PNG eyes-on verified legible at 380px phone downscale, architecture review `OK` (no invariant violations; new invariant #9 added to CLAUDE.md/AGENTS.md), BDD-evidence review `OK`, `git diff --check` clean, bump to `0.1.25`. **Caveat:** unit-verified; the live HACS `0.1.25` retest should confirm a real `binary_sensor` prompt renders an on/off timeline instead of the old hidden-entity failure.
- **2026-06-18** — `Card-facing failure logging (0.1.24)` — Open-queue item (g) part (1): card-facing **failed** snapshots returned on *accepted* WebSocket commands were logged at `INFO`, so failure codes (e.g. the `0.1.22` `binary_sensor.kitchen_door` "not on the approved list", plus `no_long_term_statistics` / `in_process_renderer_failed`) were not visible for diagnosis. `_record_websocket_decision` in `websocket_api.py` now escalates the visible log to `WARNING` when a command is rejected **or** an accepted command returns a snapshot with `status: failed` (or any captured `failure_code`); the rejection-only `WARNING` path is unchanged. The visible log line also now carries `failure_stage` alongside `failure_code` (both were already in the runtime observability record; only the code was previously printed). No schema/contract change — log level + format only, so no ADR and below the architecture-review bar. The ws-registration spec's observability bullet now documents the per-outcome log level + `failure_stage`. Item (g) part (2) (per-entity vs all-or-nothing catalog rebuild) is still open. Verification: full suite `378 passed` (370 + 2 new in `test_websocket_command_registration_anchor.py`: accepted+failed→WARNING, accepted+success→INFO; red confirmed before the fix), ws-registration + dashboard-resource + HACS-packaging + integration-scaffold evals `PASS`, `git diff --check` clean, bump to `0.1.24`. **Caveat:** the WARNING escalation is unit-verified; the live `0.1.24` retest (item (e)) should confirm the kitchen_door-class failure now produces a visible HA WARNING log line.
- **2026-06-18** — `Event-loop / executor hygiene (0.1.23)` — Live `0.1.22` testing surfaced two classes of Home Assistant blocking-call/threading warnings (open-queue item (f), now with concrete evidence). (1) Bundled JSON Schema files were read+parsed on the event loop on **every** contract validation (`read_text`/`open` warnings during `entity_catalog`/`worker_token_lifecycle`/`worker_readiness`/`worker_health_polling` setup). Added a memoized `load_schema_document()` + `preload_schema_documents()` in `_paths.py`; replaced all **24** read sites across 10 modules; `async_setup_entry` now warms the cache via an executor (`hass.async_add_executor_job`) before the first validating setup step, so first reads are off-loop and later validations are cache hits. The loader returns a `deepcopy` so the prior per-call-fresh-dict contract holds. (2) Recorder reads ran on HA's **general** executor, not the recorder DB executor (`get_significant_states` / `statistics_during_period` "accesses the database without the database executor" warnings) — also the first **live** confirmation those ADR-0021 statistics calls actually fire. Added `_read_via_recorder_executor()` in `history_retrieval.py`: because orchestration runs synchronously on a general-executor worker thread (`async_handle_registered_ws_command`), it bounces the read through the loop onto `recorder.get_instance(hass).async_add_executor_job(...)` via `asyncio.run_coroutine_threadsafe(...).result(timeout=60)`, falling back to inline when no recorder/loop is present (repo tests, non-recorder installs). Both recorder calls (incl. the older-signature fallback) route through it. Also created the missing `.claude/agents/code-reviewer.md` subagent definition — the architecture-review protocol referenced `subagent_type: "code-reviewer"` but no agent file existed (a Codex-port dangling reference); it now resolves. Verification: full suite `376 passed` (370 + 6 new in `tests/test_event_loop_executor_hygiene.py`: cached-loader parse-once/isolated-copies/preload-warms-all, recorder seam inline-fallback + true cross-thread dispatch), `51/51` evals `PASS`, dashboard-resource URL now `?v=0.1.23`, HACS packaging `PASS`, no schema files changed (no schema-first drift), architecture review `OK` (cross-thread dispatch sound, no deadlock, no ADR needed; two recommendations applied: bounded `.result(timeout=60)` and a thread-distinctness assertion in the seam test), `git diff --check` clean, bump to `0.1.23`. **Caveat:** the seam's real-HA leg (`recorder.get_instance` + the live `async_add_executor_job` signature) is `# pragma: no cover` (same as the recorder calls themselves) — the test exercises the threading mechanism with a fake recorder on a real background loop, but confirming the warnings are actually gone needs a live `0.1.23` retest.
- **2026-06-18** — `Model-resolved time window + tiered history data source` — Live `0.1.20` confirmed the Pillow renderer works end-to-end, but the chart was illegible on a phone and the time window was wrong. `0.1.21` (committed earlier this session) enlarged renderer fonts/strokes for the mobile downscale and added a regex that honored "last N hours/days/weeks". The user then redirected the window design: window determination should be **model-driven**, not a regex, and should reach beyond recorder retention via long-term statistics. This packet (`0.1.22`) implements that across **ADR-0020** (model-resolved window) and **ADR-0021** (tiered data source). The planner request now carries `now` + HA `time_zone`; the model emits an absolute `chart_spec.time_range {start,end}`; the integration validates/clamps it deterministically (tz-normalize, `start<end`, clamp `end<=now`, span `<=366d`, floor `60s`) and falls back to a fixed last-24h window on any failure — the regex is **removed entirely**. For the first-real-slice path history is now fetched **after** planning with the resolved window (so beyond-retention windows are not rejected at `job/start`); the legacy scaffold path keeps raw start-time fetch (`allow_statistics` opt-in). Data source is tiered by window: raw recorder states (recent/short), hourly statistics (`<=60d`), daily statistics (longer), single-source-per-window. Each `HistorySeries` records `source`/`resolution`; statistics points carry `value` (mean) + `value_min`/`value_max`; the Pillow renderer shades a min/max band behind the mean line. Entities without long-term statistics over a beyond-retention window fail closed with a card-facing `no_long_term_statistics` snapshot. Schema: HistorySeries gains band point fields + `source`/`resolution`; planner request gains `now`/`time_zone` (propagated to the model-provider plan and retry-policy schemas); all synced copies byte-identical. Verification: full suite `370 passed`, `52` evals `PASS` (incl. new `model_resolved_window_data_source`), HACS packaging eval `PASS`, anchor statistics-band PNG verified on disk (`in_process_pillow`, 1400×800, valid signature), architecture review `CONCERNS→resolved` (ADR-0021 executor wording reconciled; no invariant violations), BDD-evidence review `OK` (scenarios A–H with raw outputs), `git diff --check` clean. **Caveat:** the live `statistics_during_period`/`keep_days` recorder calls are behind `# pragma: no cover` import guards (same pattern as the existing recorder read) and are exercised only via injected fakes — the live call signature needs a real HACS `0.1.22` retest to confirm.
- **2026-06-17** — `Pillow in-process renderer (matplotlib requirement removed)` — Live `0.1.19` install showed the integration as **"not loaded"** with the dashboard resource stuck at `?v=0.1.18`. HA logs gave the decisive cause: `Unable to install package matplotlib>=3.7,<4` → the loose range resolved to `matplotlib==3.11.0`, which has **no wheel for the runtime CPython 3.14**, so pip built from source and failed with `PermissionError: [Errno 13] Permission denied: 'meson'`. A failed manifest-requirement install makes the integration fail to load, which also explains the stale resource (setup never reached the resource-registration step). matplotlib-via-manifest is therefore a dead end in this environment. Per **ADR-0019**, the trusted in-process renderer now draws with **Pillow** (already shipped by HA core) instead of matplotlib: the manifest `requirements` is now `[]`, the renderer identifier is `in_process_pillow` (artifact-metadata schema enum updated in both synced copies), the scaffold guard forbids **any** `matplotlib` requirement (not just `==` pins), and the renderer imports Pillow lazily and still fails closed as `renderer_dependency_unavailable`. The render interface, supported scope (safe numeric `time_series` lines), failure codes, and PNG artifact contract are unchanged. Anchor verified: a two-series ChartSpec produced a valid 25 KB PNG (correct signature, reopenable at 1400×800). The visible package version is `0.1.20`. Verification: full suite `351 passed` (venv Python 3.14.5 / Pillow 12.2.0, matching the live runtime), HACS packaging eval `PASS` (`requirements: []`), integration scaffold eval `PASS`, schema copies byte-identical, `git diff --check` clean.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Categorical timeline render family (0.1.25)`

- [x] ADR-0022 (accepted): deterministic render-family routing + categorical timeline via the model-driven path; new invariant #9 added to CLAUDE.md/AGENTS.md
- [x] Spec + BDD updated (first-real-slice spec contract/proofs; Scenarios I–L active, M pending 0.1.26)
- [x] Pre-planning `_resolve_render_family` routing by `_series_kind` (numeric→time_series, binary/categorical→timeline, mixed→`mixed_chart_composition_unsupported`)
- [x] `load_planner_result_schema(family)` timeline variant (locks `chart_type=timeline`/`render_as=step`); prompt derives family from schema
- [x] Pillow `_render_timeline_png` + shared `_binary_on_regions`/`_state_segments` primitive (reused by 0.1.26 overlay); anchor PNG eyes-on verified at phone scale
- [x] Split misleading hidden-entity code → `model_provider_referenced_unapproved_entity` vs `model_provider_substituted_entity`
- [x] Verify: `388 passed`, new `timeline_render_family_routing` eval + 51 prior evals `PASS`, architecture review `OK`, BDD-evidence review `OK`, `git diff --check` clean, bump to `0.1.25`

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
- (e) Live HACS `0.1.23` retest of the model-resolved window + statistics path
  (the `0.1.20` Pillow load + render was already confirmed live; `0.1.21`
  legibility/fonts shipped on top; live `0.1.22` confirmed single-entity
  long-term-statistics charts render correctly). Confirm: a fuzzy/relative
  prompt (e.g. "attic temperature last weekend") resolves a sane bounded window
  and renders; a long window (e.g. "last 90 days") against a `state_class`
  sensor renders a **daily statistics** chart with a min/max band (not 24h, not
  empty); a **numeric** non-`state_class` entity over a beyond-retention window
  shows a card-facing `no_long_term_statistics` failure (not a silent empty
  chart). Also confirm the `0.1.23` executor hygiene fixes landed: the
  setup-time schema `read_text`/`open` blocking warnings and the recorder
  "accesses the database without the database executor" warnings
  (`get_significant_states`, `statistics_during_period`) **no longer appear** in
  HA logs. Capture HA logs for any `statistics_during_period` TypeError/signature
  mismatch.
- (f) ~~Move setup-time schema file reads off the Home Assistant event loop~~
  **(done in `0.1.23`)** — schema reads are now memoized + executor-preloaded
  and recorder reads run on the recorder DB executor; pending only live `0.1.23`
  confirmation that the warnings are gone (folded into item (e)).
- (g) Diagnose the `binary_sensor.kitchen_door` "not on the approved list"
  failure seen during `0.1.22` live testing. Catalog was **not** wiped (other
  requests still worked), so the all-or-nothing catalog rebuild was not the
  cause; no isolinear log line was captured because card-facing failures are
  written to runtime-only diagnostic records, not surfaced as visible logs.
  Likely a planner-emitted entity-id mismatch (`entity_not_in_approved_catalog`)
  or non-numeric binary-sensor history downstream. Worth: (1) surfacing
  card-facing failure codes as visible WARNING logs for diagnosability, and
  (2) deciding whether the all-or-nothing catalog rebuild (one unresolvable
  allowlist entry clears the whole catalog) should fail per-entity instead.
  **Part (1) done in `0.1.24`** (card-facing failed snapshots now log at
  WARNING with `failure_code`/`failure_stage`); the `kitchen_door` failure
  itself was diagnosed and fixed in `0.1.25` (it was
  `model_provider_chart_spec_hidden_entity` from a binary entity forced down the
  numeric path; binary entities now render as timelines — ADR-0022). Part (2)
  (per-entity vs all-or-nothing catalog rebuild) still open.
- (i) **0.1.26 — numeric line + binary `shaded_intervals` overlay** (ADR-0022
  D4/D5, BDD Scenario M, **PENDING**). "Show me the temperature and when the AC
  was running": resolve a numeric **and** a binary entity from one prompt,
  classify each, render the numeric as the primary line with the binary as a
  `shaded_intervals` overlay band behind it. The renderer primitive
  (`_binary_on_regions`) and the `overlays[]` schema already exist; the work is
  multi-entity prompt resolution + deterministic overlay injection + the numeric
  renderer overlay pass. Until then mixed prompts fail closed with
  `mixed_chart_composition_unsupported`.
- (h) **Night mode (dark theme)** — new feature, decisions captured 2026-06-18.
  Scope: **chart PNG + card UI**. Theme source: **auto-follow Home Assistant
  theme** (no user toggle / no options-flow surface). Two coupled surfaces:
  (1) the Pillow renderer (`in_process_renderer.py`) bakes a white background
  `(255,255,255)` + dark text/grid at render time, so a dark variant needs a
  second palette **and** the resolved theme plumbed card → `job/start` →
  planner/render request (schema-touching: add a theme/appearance field to the
  job-start command + render path); (2) the Lit card (`isolinear-card.ts`)
  already consumes HA theme CSS vars with light *fallbacks* plus a few
  hardcoded light values (e.g. `#f7f9fb`) to clean up, and must detect HA
  dark/light (e.g. `hass.themes.darkMode` / `prefers-color-scheme`) to pass the
  chosen theme through each request. Needs a spec (and likely an ADR for how
  the theme is resolved/plumbed) per invariant #8 + the BDD-first workflow
  before implementation. Pushed here because the night-mode context gate
  (≥70% context remaining) was not met when the logging packet closed.

## Blockers

- None.
