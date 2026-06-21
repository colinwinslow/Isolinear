# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-21 (Entity-selection specificity + Ollama timeout + timeline readability — 0.1.29; ADR-0024 accepted, ADR-0025 drafted)
**Phase:** `First real vertical slice accepted`
**Next bounded packet:** `Open: ADR-0024 D2 (model-driven entity selection on residual ambiguity — needs spec/BDD + pre-routing model call); then ADR-0025 (live planner reasoning in the chart slot, draft — impl after D2). Also still open: implement the render-family capability envelope (ADR-0023 + spec/BDD drafted — histogram + aggregate_bar tranche). Night mode spec+ADR (item (h)) still queued.`
**Current readiness:** `READY FOR LIVE TEST (0.1.29)`

> **⚠️ Direction change (2026-06-12):** Before picking another scaffold packet,
> read [`docs/reality-pivot-review.md`](docs/reality-pivot-review.md). The next
> work is a **real vertical slice** (real recorder history + real Ollama +
> real matplotlib, rendered in-process) — not another simulated scaffold. Stop
> adding `*_anchor.py` verifiers; pytest is the single source of behavioral truth.

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-21** — `Entity-selection specificity + timeout + timeline readability (0.1.29)` — Live `0.1.28` retest **confirmed the structural gate fix**: the binary-door prompt ("show me when the kitchen door was open this morning") now renders a timeline end-to-end (DEBUG log shows gemma returning `chart_id: binary_sensor.kitchen_door_timeline`, accepted by the structural gate, `snapshot_status=complete`). Three issues surfaced and were fixed. **(1) Entity-disambiguation rigidity (the headline):** every multi-entity prompt forced a clarification because `_catalog_item_matches_prompt` matched on *any* shared meaningful token — "kitchen door" matched both `binary_sensor.kitchen_door` and `climate.kitchen_ecobee` on the lone shared token `kitchen`. **ADR-0024 accepted**; implemented **D1**: `select_prompt_entity_ids` now scores each candidate by *how many* of its distinctive tokens the prompt contains and, when the set isn't an overlay composition, selects the uniquely top-scoring approved entity (`source: catalog_label_specificity`) instead of clarifying; a top-score *tie* (e.g. "show thermostat history" with two thermostats) still clarifies, offering only the tied candidates. Invariant #1 refined in CLAUDE.md/AGENTS.md (clarification is the fallback; allowlist boundary unchanged). **D2** (model-driven selection on residual ambiguity) is staged as the next packet (needs spec/BDD + a pre-routing model call; ties into ADR-0023). **(2) Ollama timeout:** the one successful live call took 29.8s against the hard 30s cap; mixed/overlay prompts timed out at exactly 30s. `DEFAULT_OLLAMA_TIMEOUT_SECONDS` 30 → 90. **(3) Timeline readability:** a door closed all morning rendered as a near-blank lane; the binary timeline now draws a light "off" track across the full window with the "on" regions on top and an on/off legend (`_TIMELINE_OFF_FILL`; verified on disk with a mostly-closed-door PNG). Also **drafted ADR-0025** (live planner reasoning streamed into the chart slot as wait-feedback — `stream:true` + bounded sanitized `progress.reasoning` on the active planning snapshot, surfaced through the existing 1s poll loop, ephemeral/replaced by the chart; Tier-1 "reasoning on the finished card" rejected per Colin — no clutter; impl deferred until after ADR-0024 D2 so it streams across both model calls). Verification: full suite `404 passed, 3 failed` (the 3 = pre-existing codegen-sandbox subprocess flake, identical on clean baseline; +2 new selection tests), evals `timeline_render_family_routing` + `prompt_to_chart_basic` + dashboard-resource + HACS-packaging + orchestration-scaffold + clarification-continuation + integration-scaffold `PASS`, renderer eyes-on, architecture review (inline) `OK` (refines invariant #1, no violation), `git diff --check` clean, bump to `0.1.29`. **Caveat:** D1 + timeout + renderer are unit/eval/artifact-verified; the live HACS `0.1.29` retest should confirm the kitchen-door prompt skips clarification, mixed prompts no longer time out, and the timeline reads clearly. Remaining cosmetic: the timeline lane label ("Kitchen Door") clips against the axis.
- **2026-06-21** — `Structural provider-output entity gate (0.1.28)` — Live `0.1.27` testing showed the binary-door prompt ("show me when the kitchen door was open today") *still* failed `model_provider_referenced_unapproved_entity` even though gemma returned a valid `timeline` spec referencing the approved entity. Root cause was **ours, not the model**: `validate_model_provider_output_entities` ran a regex (`ENTITY_ID_IN_PROMPT`) over **every string** in provider output and mistook the model's `chart_id` slug `binary_sensor.kitchen_door_timeline` for an off-allowlist entity reference (reproduced exactly from the captured DEBUG response). **Fix:** removed the broad textual scan (`_entity_ids_in_provider_output` / `_walk_provider_output_entity_ids` deleted); the gate is now **structural** — validates only chart-spec `series`/`overlays` sources (unchanged) plus a new `_memory_proposal_entity_ids` check (the one non-source field that persists a *reusable* reference). Entity-shaped tokens in inert free-text fields (`chart_id`/`title`/`notes`/axis/`reasoning_summary`) are no longer treated as references; the renderer never reads them, so this loses no real safety. The `ENTITY_ID_IN_PROMPT` regex stays for prompt parsing (`job_orchestration.py:1372`). Posture chosen with Colin: **structured-only** (inert mentions fail-soft / accepted; `memory_proposals` off-allowlist still fails closed). New `tests/test_provider_output_entity_gate.py` (7 cases); reworked the recursive anchor/test → `hidden_memory` (rejects) + `entity_named_chart_id` (renders end-to-end); updated the planning-scaffold spec, BDD Scenario C, evidence, and eval keys to the new posture. Verification: full suite `402 passed, 3 failed` (the 3 = pre-existing codegen-sandbox subprocess flake, identical on clean baseline), planning + `timeline_render_family_routing` + `prompt_to_chart_basic` + dashboard-resource + HACS-packaging + integration-scaffold evals `PASS`, architecture review (inline) `OK` (strengthens invariant #1; no violation), BDD-evidence review `OK`, `git diff --check` clean, bump to `0.1.28`. Also **drafted ADR-0023 + paired spec/BDD** (render-family capability envelope) for the flexibility direction — all `draft`, not yet implemented. **Caveat:** unit/eval-verified against the real renderer; the live HACS `0.1.28` retest should confirm a real binary-door prompt now renders a timeline instead of failing at planning.
- **2026-06-19** — `Planner entity_id enum pin + Ollama debug logging (0.1.27)` — Diagnosed a live `0.1.26` binary-door failure: the prompt reached `model_provider_planning` then failed with `model_provider_referenced_unapproved_entity` (not the routing — binary→`timeline` routing was confirmed live). Root cause: the Ollama structured-output schema left `source.entity_id` a free string (`{"type":"string"}`), so a small local model (gemma) could hallucinate an off-allowlist entity the post-plan gate then rejected. **Fix:** `load_planner_result_schema(family, *, entity_ids=...)` now pins `source.entity_id` to an `enum` of exactly the disclosed entities (deduped; blanks dropped); the planning call site passes `request["approved_entity_ids"]` so the enum matches the disclosure. Constrained decoding now makes an off-allowlist entity structurally impossible; the deterministic post-plan entity gate (Scenario L) stays as defence in depth. Also added **DEBUG request/response logging** on the `custom_components.isolinear.model_provider` logger (off by default; logs outgoing body + raw provider content + transport errors; no tokens/secrets on this path) to diagnose future chart families. BDD Scenario P + evidence added. Verification (real renderer this session — installed Pillow 10.2.0 + matplotlib via apt/pip in the sandbox): full suite `394 passed, 3 failed` — the 3 are the pre-existing codegen-sandbox subprocess flake, confirmed **identical on clean baseline** (stash); 4 new tests pass; `timeline_render_family_routing` + `prompt_to_chart_basic` evals `PASS`. Architecture review (inline) `OK` — strengthens invariant #1, no new ADR (schema tightening consistent with ADR-0022); BDD-evidence review `OK`. Bump to `0.1.27`. **Caveat:** unit/eval-verified against the real renderer; the live HACS `0.1.27` retest should confirm a real binary-door prompt now renders instead of failing at planning.
- **2026-06-18** — `Numeric + binary overlay composition (0.1.26)` — Fast-follow completing ADR-0022's target architecture (D4/D5): "show me the temperature and when the AC was running" now renders a **numeric line with the binary entity shaded as `shaded_intervals` overlay bands behind it**. `_resolve_render_family` gained a `time_series_overlay` family for **exactly one numeric primary + one or more binary** entities; the integration discloses **only** the numeric primary to the planner (new `entity_ids` arg on `_model_provider_planner_request`) and injects overlays deterministically after planning via `_compose_binary_overlays` (model never composes overlays — invariant #9 / D5). The Pillow numeric renderer gained an overlay pass: "on"-region vertical bands across the full plot height behind the line, reusing the `_binary_on_regions` primitive from 0.1.25; the numeric unsupported-gate now allows `shaded_intervals` entity overlays and rejects any other overlay shape. `select_prompt_entity_ids` auto-resolves a fuzzy prompt matching one numeric + ≥1 binary to the composition instead of single-entity clarification. **Scope guard (from architecture review):** overlay composition is **binary-only** — a non-binary categorical mixed with numeric has no "on" region, so it stays `mixed` (fail closed) rather than shading nothing; ≥2 numeric + binary also stays `mixed`. No core schema change (`overlays[]` already first-class). Verification: full suite `393 passed` (overlay renderer pixel checks, unit composition, fuzzy resolution, e2e overlay PNG with planner disclosed only the numeric primary, two-numeric+binary and categorical+numeric fail-closed; reds confirmed), `timeline_render_family_routing` eval extended (overlay routing + render CASE) + 51 prior evals `PASS`, temperature+AC overlay anchor PNG eyes-on verified legible at 380px phone downscale, architecture review `OK` (no invariant violations; the binary-only scope tightening applied per its one note), BDD-evidence review `OK`, `git diff --check` clean, bump to `0.1.26`. **Caveat:** unit/artifact-verified; live HACS `0.1.26` retest should confirm a real mixed prompt renders the overlay.
- **2026-06-18** — `Categorical timeline render family (0.1.25)` — Diagnosed why the user's `binary_sensor.kitchen_door` test failed with the misleading `model_provider_chart_spec_hidden_entity` instead of the intended `no_long_term_statistics`: a binary entity can't satisfy the numeric-only planner schema, so the model substituted an entity and the entity-validation gate fired **before** history retrieval (the ADR-0020 reorder puts history after planning). Rather than dead-end binary entities, this packet (**ADR-0022**) makes them chart. **Deterministic 3-way render-family routing** (`_resolve_render_family` in `job_orchestration.py`, by `_series_kind` *before* planning): all-numeric → `time_series`/`line`; all binary/categorical → new `timeline`/`step` family; mixed → fails closed with `mixed_chart_composition_unsupported` (overlay deferred to 0.1.26). The integration selects the per-family Ollama structured-output schema (`load_planner_result_schema(family)`), so the model never picks `chart_type`. The live Pillow renderer gained `_render_timeline_png` (one lane per series, on/off + categorical bands, phone-legible) built on a shared `_binary_on_regions` primitive reused by the 0.1.26 overlay. Also split the misleading hidden-entity code into honest `model_provider_referenced_unapproved_entity` (absent from catalog) vs `model_provider_substituted_entity` (approved but not disclosed). No **core** schema change (chart-spec already allows `timeline`/`step` + `overlays[]`). Verification: full suite `388 passed` (renderer, routing, e2e binary timeline, beyond-retention-binary, disambiguation, mixed-fail; reds confirmed), new eval `timeline_render_family_routing` PASS + 51 prior evals PASS, anchor two-lane timeline PNG eyes-on verified legible at 380px phone downscale, architecture review `OK` (no invariant violations; new invariant #9 added to CLAUDE.md/AGENTS.md), BDD-evidence review `OK`, `git diff --check` clean, bump to `0.1.25`. **Caveat:** unit-verified; the live HACS `0.1.25` retest should confirm a real `binary_sensor` prompt renders an on/off timeline instead of the old hidden-entity failure.
## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Entity-selection specificity + timeout + timeline readability (0.1.29)`

- [x] **ADR-0024 accepted** (model-driven entity selection); **D1 implemented**: `select_prompt_entity_ids` specificity tie-break selects the uniquely best-specified approved entity (`catalog_label_specificity`), ties still clarify; `_catalog_item_match_score` helper; invariant #1 refined in CLAUDE.md/AGENTS.md
- [x] Ollama `DEFAULT_OLLAMA_TIMEOUT_SECONDS` 30 → 90 (live calls were hitting the 30s wall)
- [x] Timeline binary lane now draws a light "off" track + on/off legend so a mostly-off entity isn't a blank lane (`_TIMELINE_OFF_FILL`); verified on disk
- [x] **ADR-0025 drafted** (live planner reasoning in the chart slot; impl deferred until after ADR-0024 D2); ADR index + invariant updated; version bump `0.1.29`
- [x] Verify: full suite `404 passed, 3 failed` (the 3 = pre-existing codegen-sandbox flake, identical on baseline; +2 selection tests), `timeline_render_family_routing` + `prompt_to_chart_basic` + dashboard-resource + HACS-packaging + orchestration/clarification/integration-scaffold evals `PASS`, renderer eyes-on, architecture review (inline) `OK`, BDD-evidence review N/A (no new BDD scenarios)
- [ ] **Next packet — ADR-0024 D2:** model-driven entity selection on residual ambiguity (top-score tie / zero match) — needs spec/BDD + a pre-routing model selection call; user sees clarification only when the model abstains
- [ ] **Then ADR-0025:** live planner reasoning (spec/BDD; `stream:true` + bounded sanitized `progress.reasoning` + card chart-slot rendering)

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
