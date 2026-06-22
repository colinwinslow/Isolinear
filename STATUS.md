# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-22 (ADR-0025 live planner reasoning shipped 0.1.32, bug-fixed 0.1.33, redaction hardened 0.1.34)
**Phase:** `First real vertical slice accepted`
**Next bounded packet:** `Live HACS 0.1.33 retest (#1). Then implement the render-family capability envelope (ADR-0023 + spec/BDD drafted — histogram + aggregate_bar tranche) (#2). Then night mode spec+ADR (item (h)) (#3).`
**Current readiness:** `READY FOR LIVE TEST (0.1.33/0.1.34)`

> **⚠️ Direction change (2026-06-12):** Before picking another scaffold packet,
> read [`docs/reality-pivot-review.md`](docs/reality-pivot-review.md). The next
> work is a **real vertical slice** (real recorder history + real Ollama +
> real matplotlib, rendered in-process) — not another simulated scaffold. Stop
> adding `*_anchor.py` verifiers; pytest is the single source of behavioral truth.

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-22** — `ADR-0025 live planner reasoning shipped (0.1.32) + bug fixes (0.1.33) + redaction hardening (0.1.34)` — Closeout for two already-committed packets plus one closeout-discovered fix. **0.1.32** (`9783cc2`): full ADR-0025 workflow — the Ollama planner now streams (`stream: true`), the model thinking trace is sanitized + length-capped (2000-char rolling tail) into a per-job live-reasoning slot, surfaced as `progress.reasoning` + a coarse phase label ("Selecting entities…" / "Planning chart…") on the active planning snapshot through the existing poll loop, then replaced by the chart (or failure card) on completion; reasoning is never persisted (stored snapshot never mutated, slot cleared in `finally` on terminal state); spans both model calls (D2 `select_entity` + `plan_chart`); non-streaming/non-thinking providers fall back gracefully (D6); Lit card renders a `data-testid="planning-reasoning"` monospace block. **0.1.33** (`0e48995`): two live-found bugs — (1) `"think": true` was never sent so thinking-capable models never streamed (now sent on streaming planner + entity-selector requests only); (2) naive ISO 8601 model timestamps forced the 24h fallback (now `_parse_window_timestamp` treats naive datetimes as UTC). **0.1.34** (this session): closeout architecture review (fresh subagent) found `sanitize_reasoning` redacted URLs/`Bearer`/paths but **not** the named secret vocabulary the rest of the card-facing surface already guards (`access_token`, `*_token`, `ollama_api_key`, `api_key`) nor bare `sk-…`/JWT tokens — an invariant-3 / ADR-0025 D5 gap since the thinking trace is unsanitized model echo. Hardened `sanitize_reasoning` to mirror `FORBIDDEN_WORKER_PROGRESS_TEXT` plus `sk-…`/JWT patterns (4 new redaction tests; entity IDs + prompt still retained); no core schema change. Verification: full suite `451 passed, 3 failed` (3 = pre-existing codegen-sandbox subprocess flake, identical on clean baseline), **all 51 evals PASS** (incl. `timeline_render_family_routing` + `prompt_to_chart_basic` + `home_assistant_job_orchestration_model_provider_planning_scaffold`), BDD-evidence review `OK` (schema + bundle md5 parity re-verified; both bug-fixes test-covered), architecture review CONCERNS → resolved by 0.1.34, bump to `0.1.34`. **Next:** live HACS `0.1.33` retest (#1) — reasoning streams across both calls, no secrets in trace, naive-timestamp windows resolve correctly; then ADR-0023 capability envelope (#2); then night mode (#3).
- **2026-06-22** — `Model-driven entity selection D2 (0.1.31)` — Implemented ADR-0024 D2: when the deterministic specificity fast-path cannot resolve (top-score tie or zero matches), the integration now asks the model to pick the entity before showing the user a clarification card. `_run_model_entity_selection` calls `planner.select_entity` with the candidate entity IDs pinned to a structured-output enum (`load_entity_selector_schema`); the model returns either `entity_selected + entity_ids` or `clarification_needed`. Chosen IDs are validated against the allowlist (both candidate set and full catalog) — any off-allowlist choice fails closed and falls through to user clarification. Wired into both `handle_job_orchestration_start_ws_command` and `handle_job_orchestration_retry_continuation`. Planners without `select_entity` silently skip D2 (no regression for existing `FakePlanner` tests). BDD Scenarios A–E accepted with evidence (`bdd/entity-clarification/model-entity-selection-d2-bdd.md`). Architecture review (inline) OK — all 9 invariants verified; no violation. Verification: full suite `420 passed, 3 failed` (3 = pre-existing codegen-sandbox subprocess flake, identical on clean baseline; +14 new D2 tests), evals `timeline_render_family_routing` + `prompt_to_chart_basic` + `model_provider_planning_scaffold` PASS, `git diff --check` clean, bump to `0.1.31`. **Next:** live HACS `0.1.31` retest; then ADR-0025 (live planner reasoning).
- **2026-06-21** — `Overlay composite detection + duplicate-source series fix (0.1.30)` — Live `0.1.29` retest confirmed disambiguation is working (kitchen-door prompt skips clarification). Tested `time_series_overlay` path with "show me the kitchen temperature yesterday and when the AC was running" — surfaced two bugs. **(1) Composite detection blocked by categorical noise match:** `climate.kitchen_ecobee` in the allowlist matched "kitchen" alongside the numeric temperature sensor and binary door sensor; the old guard required all non-numeric matches to be binary, so the categorical blocked the composite path entirely and the specificity scorer dropped the temperature sensor. Fix: relax the guard to `1 numeric + ≥1 binary` regardless of categorical co-matches; categoricals are silently discarded (documented in ADR-0022 D4). **(2) Duplicate-source series not caught:** when constrained to only `binary_sensor.kitchen_door`, the model returned two series from the same source — one hallucinated as "Kitchen Temperature" — producing two identical timeline lanes in different colors. Fix: `validate_chart_spec_contract` now calls `_check_chart_spec_no_duplicate_series_sources` and rejects any chart spec where two series share the same `(type, entity_id, attribute)` source key. Architecture review: CONCERNS → addressed by amending ADR-0022 D4 to document the categorical-noise-discard decision. Verification: full suite `406 passed, 3 failed` (the 3 = pre-existing codegen-sandbox subprocess flake), evals `timeline_render_family_routing` + `prompt_to_chart_basic` + `model_provider_planning_scaffold` `PASS`, `git diff --check` clean, bump to `0.1.30`. **Next:** live HACS `0.1.30` retest to confirm the numeric+binary overlay renders correctly (temperature sensor + binary door sensor in allowlist).
- **2026-06-21** — `Entity-selection specificity + timeout + timeline readability (0.1.29)` — Live `0.1.28` retest **confirmed the structural gate fix**: the binary-door prompt ("show me when the kitchen door was open this morning") now renders a timeline end-to-end (DEBUG log shows gemma returning `chart_id: binary_sensor.kitchen_door_timeline`, accepted by the structural gate, `snapshot_status=complete`). Three issues surfaced and were fixed. **(1) Entity-disambiguation rigidity (the headline):** every multi-entity prompt forced a clarification because `_catalog_item_matches_prompt` matched on *any* shared meaningful token — "kitchen door" matched both `binary_sensor.kitchen_door` and `climate.kitchen_ecobee` on the lone shared token `kitchen`. **ADR-0024 accepted**; implemented **D1**: `select_prompt_entity_ids` now scores each candidate by *how many* of its distinctive tokens the prompt contains and, when the set isn't an overlay composition, selects the uniquely top-scoring approved entity (`source: catalog_label_specificity`) instead of clarifying; a top-score *tie* (e.g. "show thermostat history" with two thermostats) still clarifies, offering only the tied candidates. Invariant #1 refined in CLAUDE.md/AGENTS.md (clarification is the fallback; allowlist boundary unchanged). **D2** (model-driven selection on residual ambiguity) is staged as the next packet (needs spec/BDD + a pre-routing model call; ties into ADR-0023). **(2) Ollama timeout:** the one successful live call took 29.8s against the hard 30s cap; mixed/overlay prompts timed out at exactly 30s. `DEFAULT_OLLAMA_TIMEOUT_SECONDS` 30 → 90. **(3) Timeline readability:** a door closed all morning rendered as a near-blank lane; the binary timeline now draws a light "off" track across the full window with the "on" regions on top and an on/off legend (`_TIMELINE_OFF_FILL`; verified on disk with a mostly-closed-door PNG). Also **drafted ADR-0025** (live planner reasoning streamed into the chart slot as wait-feedback — `stream:true` + bounded sanitized `progress.reasoning` on the active planning snapshot, surfaced through the existing 1s poll loop, ephemeral/replaced by the chart; Tier-1 "reasoning on the finished card" rejected per Colin — no clutter; impl deferred until after ADR-0024 D2 so it streams across both model calls). Verification: full suite `404 passed, 3 failed` (the 3 = pre-existing codegen-sandbox subprocess flake, identical on clean baseline; +2 new selection tests), evals `timeline_render_family_routing` + `prompt_to_chart_basic` + dashboard-resource + HACS-packaging + orchestration-scaffold + clarification-continuation + integration-scaffold `PASS`, renderer eyes-on, architecture review (inline) `OK` (refines invariant #1, no violation), `git diff --check` clean, bump to `0.1.29`. **Caveat:** D1 + timeout + renderer are unit/eval/artifact-verified; the live HACS `0.1.29` retest should confirm the kitchen-door prompt skips clarification, mixed prompts no longer time out, and the timeline reads clearly. Remaining cosmetic: the timeline lane label ("Kitchen Door") clips against the axis.
- **2026-06-21** — `Structural provider-output entity gate (0.1.28)` — Live `0.1.27` testing showed the binary-door prompt ("show me when the kitchen door was open today") *still* failed `model_provider_referenced_unapproved_entity` even though gemma returned a valid `timeline` spec referencing the approved entity. Root cause was **ours, not the model**: `validate_model_provider_output_entities` ran a regex (`ENTITY_ID_IN_PROMPT`) over **every string** in provider output and mistook the model's `chart_id` slug `binary_sensor.kitchen_door_timeline` for an off-allowlist entity reference (reproduced exactly from the captured DEBUG response). **Fix:** removed the broad textual scan (`_entity_ids_in_provider_output` / `_walk_provider_output_entity_ids` deleted); the gate is now **structural** — validates only chart-spec `series`/`overlays` sources (unchanged) plus a new `_memory_proposal_entity_ids` check (the one non-source field that persists a *reusable* reference). Entity-shaped tokens in inert free-text fields (`chart_id`/`title`/`notes`/axis/`reasoning_summary`) are no longer treated as references; the renderer never reads them, so this loses no real safety. The `ENTITY_ID_IN_PROMPT` regex stays for prompt parsing (`job_orchestration.py:1372`). Posture chosen with Colin: **structured-only** (inert mentions fail-soft / accepted; `memory_proposals` off-allowlist still fails closed). New `tests/test_provider_output_entity_gate.py` (7 cases); reworked the recursive anchor/test → `hidden_memory` (rejects) + `entity_named_chart_id` (renders end-to-end); updated the planning-scaffold spec, BDD Scenario C, evidence, and eval keys to the new posture. Verification: full suite `402 passed, 3 failed` (the 3 = pre-existing codegen-sandbox subprocess flake, identical on clean baseline), planning + `timeline_render_family_routing` + `prompt_to_chart_basic` + dashboard-resource + HACS-packaging + integration-scaffold evals `PASS`, architecture review (inline) `OK` (strengthens invariant #1; no violation), BDD-evidence review `OK`, `git diff --check` clean, bump to `0.1.28`. Also **drafted ADR-0023 + paired spec/BDD** (render-family capability envelope) for the flexibility direction — all `draft`, not yet implemented. **Caveat:** unit/eval-verified against the real renderer; the live HACS `0.1.28` retest should confirm a real binary-door prompt now renders a timeline instead of failing at planning.
## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `ADR-0025 live planner reasoning streaming (0.1.32) + bug fixes (0.1.33) + redaction hardening (0.1.34)` — SHIPPED

- [x] 0.1.32: streaming planner (`stream: true`), `sanitize_reasoning` + 2000-char rolling cap, per-job live-reasoning slot, `progress.reasoning` + phase label on planning snapshot, replaced by chart on completion, never persisted; spans both model calls; Lit card chart-slot rendering; frontend bundle rebuilt + synced
- [x] 0.1.33 bug fix 1: send `"think": true` on streaming planner + entity-selector requests so thinking-capable Ollama models actually stream
- [x] 0.1.33 bug fix 2: `_parse_window_timestamp` treats naive ISO 8601 datetimes as UTC instead of forcing the 24h fallback
- [x] 0.1.34 (closeout): `sanitize_reasoning` now also redacts named secret vocabulary (`access_token`/`*_token`/`ollama_api_key`/`api_key`) + bare `sk-…`/JWT tokens (architecture-review finding; invariant-3 / ADR-0025 D5 gap); 4 new redaction tests
- [x] Verify: full suite `451 passed, 3 failed` (pre-existing codegen flake), all evals PASS, BDD-evidence review OK, architecture review CONCERNS→resolved, bump `0.1.34`
- [ ] **Live HACS `0.1.33` retest (#1):** reasoning streams across both calls with a thinking-capable model; no secrets/URLs/paths/tokens in the trace; reasoning replaced by the PNG (or failure card) on completion; a naive model-timestamp window resolves correctly instead of silently falling back to 24h

### `Render-family capability envelope (ADR-0023) — ACCEPTED, not implemented`

- [x] ADR-0023 **accepted** (commit `5010302`); `docs/specs/render-family-capability-envelope.md` + `bdd/rendering/render-family-capability-envelope-bdd.md` remain `draft` (accept when the implementation anchor lands)
- [ ] Implement per the spec's order: histogram anchor → out-of-envelope gate → aggregate_bar → fail-soft/no-data coverage → single-member regression

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
- (i) ~~**0.1.26 — numeric line + binary `shaded_intervals` overlay**~~
  **(done in `0.1.26`)** — "temperature and when the AC was running" composes a
  numeric line + binary overlay band; multi-entity resolution + deterministic
  overlay injection + renderer overlay pass landed (ADR-0022 D4/D5, BDD
  Scenarios M–O). Follow-ups still open: overlay for ≥2 numeric (multi-axis),
  overlay on the `timeline` family, and a dedicated `timeline_history_unavailable`
  code for beyond-retention binary windows.
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
