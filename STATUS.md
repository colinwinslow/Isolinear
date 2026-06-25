# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-25 (impl session — ADR-0027 card-owned legend + model summary/overlay labels 0.1.47; climate-overlay fixes 0.1.45; card declutter 0.1.46)
**Phase:** `First real vertical slice accepted`
**Next bounded packet:** `Live HACS retest of 0.1.47 (card legend + summary caption + AC split swatch via real Ollama). Then: extend legend manifest to timeline/histogram/aggregate_bar families (discussed, deferred); night mode spec+ADR (schema-touching).`
**Current readiness:** `0.1.47 DEPLOYED (pushed origin/main 7ceddc5) — card-owned legend, model summary caption, model overlay labels; in-PNG legend removed for time_series/overlay. 565 Python + 21 frontend tests pass. Awaiting live HACS retest.`

> **⚠️ Direction change (2026-06-12):** Before picking another scaffold packet,
> read [`docs/reality-pivot-review.md`](docs/reality-pivot-review.md). The next
> work is a **real vertical slice** (real recorder history + real Ollama +
> real matplotlib, rendered in-process) — not another simulated scaffold. Stop
> adding `*_anchor.py` verifiers; pytest is the single source of behavioral truth.

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-25** — `ADR-0027 card-owned legend + model summary/overlay labels (0.1.47); climate-overlay fixes (0.1.45); card declutter (0.1.46)` — **Session opened with live overlay bugfixes:** (a) climate overlay rendered one stale block because history points were timestamped by `last_changed`, which is frozen for a climate entity (state constant "cool" all day) while only the `hvac_action` attribute cycles — fixed by timestamping points by `last_updated` (advances per recorder write), with `last_changed` fallback; regression tests in `ClimateAttributeTimestampTests`. Earlier in the same thread: overlay bands keyed off `hvac_action` attribute (added `attrs` to categorical history points + schema), `attrs` schema gate fix, en-dash→ASCII legend char, and a `device_class` type-hint filter so "temperatures" prompts drop a power sensor sharing a location token (`_filter_numerics_by_type_hint`). **Main packet — ADR-0027 (0.1.47):** moved the chart legend out of the PNG into an interactive card legend fed by a renderer color manifest (single source of truth for colors). Renderer (`in_process_renderer.py`) builds `render_metadata.legend` — `{label, entity_id, color, kind, states?}`, overlays carry per-state child colors — and stops drawing the in-PNG legend for `time_series`/`time_series_overlay` (timeline/histogram/aggregate keep theirs, deferred). Model (`model_provider.py`) now authors `chart_spec.summary` (required in constrained-decoding schema → card caption, replaces prompt echo) and `planner_result.overlay_labels` `{entity_id: label}`. Orchestration: `_compose_state_overlays` applies the model overlay label with deterministic fallback (model → friendly name → `"<id> — running state"`); summary + legend threaded through artifact into `snapshot.chart`; alias display entries gain `entity_id` so the card shows a matched alias inside the right legend row. Card (`isolinear-card.ts`): caption = summary↦title; "Entities and aliases" → interactive **Legend** (swatch + label, flip-down with entity_id + matched alias, split swatch + per-state children for multi-state overlays, label guard, graceful empty state). **6 schemas** extended (all optional/back-compat, docs + cc copies synced). **Verify:** 565 Python tests pass (3 pre-existing matplotlib-sandbox flakes excluded), 21 frontend tests (8 new legend/caption); anchor PNG eyes-on = clean chart, manifest carries `#1f77b4` series + `#b8d4ee`/`#ffcf9e` overlay states; BDD-evidence review OK; architecture review OK (no invariant violations — model gains a string + label map only, allowlist/composition/colors stay deterministic). ADR-0027/spec/BDD promoted draft→accepted; evidence file written. Kept in-PNG chart **title** (ADR open item). **Open:** (l) live HACS retest of card legend/caption/split-swatch; (m) extend manifest to the other 3 families. **Memory:** saved `design-lean-on-model` (Colin wants less hard determinism; prefer model+hints for new features).

- **2026-06-24** — `ADR-0023 render-family capability envelope — histogram + aggregate_bar (0.1.44)` — Implemented ADR-0023 in full across three files. **Architecture:** `_resolve_render_envelope` (job_orchestration.py) wraps the existing `_resolve_render_family` to compute a 1–3-family envelope from entity data shape — single_numeric → `[time_series, histogram, aggregate_bar]`, multi_numeric / overlay / timeline / mixed → unchanged single-member. `validate_model_provider_chart_family` gate fires after `validate_chart_spec_contract`, rejects model-chosen `chart_type` not in the computed set, fires before any render (`model_provider_chart_family_out_of_envelope`). `load_planner_result_schema` now accepts `envelope` arg — 1-member: identical to ADR-0022 single-family schema (backward compat); >1-member: widens `chart_type` enum to all families, allows `source.type: aggregate` when aggregate_bar in envelope; entity_id pin unchanged (invariant #1). Multi-family prompt guidance replaces single rule with intent-based direction. **Renderers:** `_render_histogram_png` bins numeric entity history into N bins (default 8), draws bars+axes with Pillow; `_render_aggregate_bar_png` groups history by `group_by` (day/hour), applies `_apply_aggregate` (mean/min/max/sum/count), draws one bar per period. **Fail-soft:** zero points fails closed (`in_process_renderer_failed`); any non-zero count renders a valid thin PNG. **Verify:** `554 passed, 3 pre-existing codegen-sandbox flakes`; all 7 eval CASEs PASS (including 3 new: `capability_envelope_routing`, `histogram_render`, `aggregate_bar_render`); BDD-evidence review OK (minor: no live reasoning_summary — unit-test context only). **Artifacts (eyes-on):** histogram 8-bin PNG ✓, aggregate daily-bar PNG ✓, sparse 3-point histogram (fail-soft) ✓. Spec/BDD promoted draft→accepted. Bump `0.1.44`. **Next:** live HACS retest (histogram + aggregate_bar via real Ollama); night mode spec+ADR.

- **2026-06-24** — `ADR-0026 entity selection in pollable planning phase (0.1.43)` — Live `0.1.42` diagnosis (gemma4:e4b @ 10.0.1.39): `job/start` blocked **15.2s** running D2 model entity selection synchronously, so the card sat inert with no feedback and selection reasoning never streamed — ADR-0025 D7 ("continuous reasoning submit→chart") was unsatisfiable as wired because D2 ran in the blocking `job/start` handler, not the pollable phase. **Fix:** moved model entity selection (D1 + semantic alias + D2 + the D3 decision) out of `job/start`/`job/retry` into the first `job/snapshot` poll, behind the existing `planning_lock`, so `job/start` returns `planning` immediately and reasoning streams via `apply_live_reasoning`. New stage `ENTITY_SELECTION_PENDING_STAGE` (artifact-source); helpers `_defer_selection_to_planning`, `_resolve_pending_entity_selection`, `_synchronous_empty_catalog_failure`. Resolution logic unchanged — relocation only. Empty catalog stays a synchronous `job/start` rejection. **Deviation:** deferral gated on `first_real_vertical_slice_enabled` (legacy scaffold path keeps synchronous selection — smaller blast radius). Implemented Opus (Phase 1) + Sonnet subagent migrated 8 existing terminal-`job/start` assertions to first-poll (Phase 2). **Verify:** new `tests/test_entity_selection_pollable_phase.py` (7), full suite `519 passed, 3 pre-existing codegen-sandbox flakes`, affected evals PASS. **Deployed + live-confirmed:** pushed origin/main `7466ee5`, HACS install + HA restart via API; live retest proved `job/start` 0.01s, "Selecting entities…" then "Planning chart…" reasoning streams, completes with real PNG. ADR-0026/spec/BDD written as **draft** — promote at next closeout. **Next:** ADR-0023 capability envelope.

- **2026-06-23** — `D2 expansion (0.1.41) + Semantic alias Tranche 2 (0.1.42)` — Two packets implemented back-to-back. **(1) ADR-0024 D2 expansion (0.1.41):** D2 model entity selection now also runs after a confident single-entity D1 result, re-querying the full catalog with the D1 pick as `already_selected_entity_ids` to add concepts token scoring missed (the "AC" gap). New `_resolve_entity_selection_with_model` helper unifies both orchestration call sites; `_run_model_entity_selection` gained `d1_selected_ids`. Safe fall-back: model abstain/absent/off-catalog → D1's result stands (never downgrades to clarification; off-catalog fails closed). Skipped for explicit-id/overlay/semantic_alias sources and when D1 covers the whole catalog. HA domain hint added to `select_entity` prompt. Spec + ADR-0024 + BDD (Scenarios F–I) + evidence updated. 11 new tests. **(2) Semantic alias Tranche 2 (0.1.42):** "Use and remember" on an entity clarification saves a `SemanticAlias`. `can_remember` opt-in per clarification type; `job["alias_suggestions"]` precomputed at question-build; `derive_alias_natural_names`/`_entity_id_to_alias_id`/`_sanitize_prompt_for_storage` + synchronous `SemanticMemoryStorageHelper.save_alias` (executor-thread safe, mirrors worker_token_lifecycle — spec's async premise corrected in acceptance notes); `_maybe_save_semantic_alias` wired into the answer handler (non-blocking); complete snapshot `aliases` display via `_alias_display_entries` (schema field already existed). Spec accepted; BDD evidence written. 17 new tests; eval CASE `semantic_alias_save_and_reuse`. Review-pass suggestions applied (can_remember gated by param; `_schedule_save` delay=0 documented). **Verify:** full suite `512 passed, 3 pre-existing codegen-sandbox failures`; semantic-memory/planning/clarification evals PASS; architecture review OK (no invariant violations); BDD-evidence review OK. Bump `0.1.41` then `0.1.42`. **Next:** ADR-0023 capability envelope; night mode spec+ADR.

- **2026-06-23** — `Semantic alias live wiring Tranche 1 (0.1.40)` — New feature: the integration now loads a persisted per-config-entry `SemanticMemoryStore` envelope, matches valid enabled aliases against the prompt by token overlap, and injects matched entity IDs into entity selection before planning. **Architecture:** `SemanticMemoryStorageHelper` — dual-backend (HA `Store` in production, in-memory in tests/scaffold), per-config-entry scoped. `prepare_semantic_memory_for_planning` — use-time validity against the current catalog (unavailable / not-allowlisted); never mutates the store. `alias_matches_prompt` — `[a-z0-9_]+` tokenization, `MATCH_RATIO=0.6`, no min-length floor (unlike entity selector), trivial stop words stripped. `_inject_semantic_aliases` — pure function composing alias-injected entities with direct results, de-duplicated, `source: "semantic_alias"` recorded. Wired into `job_orchestration.py` after `select_prompt_entity_ids`; wired into `async_setup_entry` via `async_setup_semantic_memory`. **Invariant compliance:** injected entities already validated `visible_to_agent: true` (allowlist boundary preserved, invariant #1); no store write (Tranche 2); deterministic (invariant #7). **Proof:** 33 new unit tests (all passing), 7 BDD scenarios in `bdd/semantic-memory/semantic-alias-live-wiring-bdd.md`, eval anchor CASE (`semantic_alias_injection`) added to `evals/semantic_memory_store_envelope.py` showing `climate.kitchen_ecobee` injected from prompt "show kitchen temp and when the AC was running" with `matched_alias_ids: ["whole_house_ac"]`. Architecture review: 9 invariants checked, no violations. **Full suite:** `484 passed, 3 failed` (pre-existing codegen-sandbox flake). Spec status: `accepted`. Bump `0.1.40`. **Next:** render-family capability envelope (#2); night mode spec+ADR (#3); semantic alias Tranche 2 (propose/confirm/save).

_(older sessions — 0.1.39 and earlier, and the 2026-06-23 Tranche 2 spec/D2-decision session — live in git history)_
## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `ADR-0027 card-owned legend + model summary/overlay labels (0.1.47)` — SHIPPED

- [x] Renderer emits `render_metadata.legend` manifest (`{label, entity_id, color, kind, states?}`); in-PNG legend removed for `time_series`/`time_series_overlay`
- [x] Model authors `chart_spec.summary` (required in constrained-decoding schema) and `planner_result.overlay_labels` `{entity_id: label}`; prompt updated
- [x] `_compose_state_overlays` applies model overlay label with deterministic fallback (model → friendly name → `"<id> — running state"`)
- [x] `summary` + `legend` threaded through artifact into `snapshot.chart`; alias display entries gain `entity_id`
- [x] Card: caption = summary↦title (no prompt echo); interactive **Legend** (swatch + label, flip-down with entity_id + matched alias, split swatch + per-state children, label guard, graceful empty state)
- [x] 6 schemas extended (chart-spec, planner-result, render-result, artifact-metadata, job-snapshot; docs + cc copies synced; all optional/back-compat)
- [x] ADR-0027 + spec + BDD + evidence written, promoted draft→accepted; doc indexes updated
- [x] 565 Python tests pass (3 pre-existing matplotlib flakes excluded); 21 frontend tests (8 new); anchor PNG eyes-on clean; BDD-evidence + architecture reviews OK
- [x] Version bumped to `0.1.47`; pushed origin/main `7ceddc5`
- [ ] **Live HACS retest:** confirm summary caption reads as a sentence, the AC overlay row's split swatch expands to cooling/heating children, and the legend labels are descriptive
- [ ] **Follow-up (deferred, discussed):** extend the legend manifest + external legend to `timeline` / `histogram` / `aggregate_bar`

### `ADR-0023 render-family capability envelope — histogram + aggregate_bar (0.1.44)` — SHIPPED

- [x] `_resolve_render_envelope` in `job_orchestration.py` — wraps `_resolve_render_family`, produces `families` / `shape` / `default_family`; single_numeric → 3-family; all others → existing single-member
- [x] `validate_model_provider_chart_family` gate — rejects out-of-envelope `chart_type` post `validate_chart_spec_contract`, no-op for single-member (backward compat)
- [x] `load_planner_result_schema` extended with `envelope` arg — multi-family: widens `chart_type`+`render_as` enums, allows `source.type: aggregate` when aggregate_bar in envelope; entity_id pin unchanged
- [x] Multi-family prompt guidance in `_chat_payload` — intent-based family guidance replaces hardcoded single rule
- [x] `_render_histogram_png` — bins numeric history, Pillow bars+axes, fail-soft (zero points → failure, any other count → thin valid PNG)
- [x] `_render_aggregate_bar_png` — groups by day/hour, applies 5 operations (mean/min/max/sum/count), Pillow bars, same fail-soft rule
- [x] `render_in_process_chart` dispatch extended: histogram branch + bar branch alongside existing time_series/timeline
- [x] Spec+BDD promoted draft→accepted; `bdd/rendering/render-family-capability-envelope-evidence.md` written (8 scenarios A–H)
- [x] 42 new tests in `tests/test_render_family_capability_envelope.py`; 3 new eval CASEs in `evals/timeline_render_family_routing.py`
- [x] Full suite `554 passed, 3 pre-existing codegen-sandbox flakes`; all 7 eval CASEs PASS
- [x] Version bumped to `0.1.44`
- [ ] **Live HACS retest:** ask "show distribution of upstairs temp" and "average temp per day" — confirm histogram and bar PNGs complete via real Ollama

### `Semantic alias Tranche 2 — propose/confirm/save (0.1.42)` — SHIPPED

- [x] `derive_alias_natural_names` + `_entity_id_to_alias_id` + `_sanitize_prompt_for_storage` + `validate_semantic_alias_contract` in `semantic_memory.py`
- [x] `SemanticMemoryStorageHelper.save_alias` — synchronous (executor-thread safe), validates store envelope, updates in-memory, `async_delay_save(…,0)`; module `save_semantic_alias`
- [x] `can_remember` opt-in param on `_clarification_option_for_item` (entity selection passes `True`; other types default `False`); `job["alias_suggestions"]` precomputed in `_append_clarification_snapshot`
- [x] `_maybe_save_semantic_alias` wired into clarification-answer handler (remember:true, non-blocking on failure)
- [x] Complete snapshot `aliases` display via `_alias_display_entries` + `append_validated_job_snapshot` passthrough (schema field pre-existing; no schema change)
- [x] Spec accepted with deviation notes (sync save, schema already present, version 0.1.42); BDD evidence written
- [x] 17 unit/integration tests; eval CASE `semantic_alias_save_and_reuse`
- [x] Architecture review OK; review suggestions applied (can_remember gate, `_schedule_save` delay=0 comment)
- [x] Full suite `512 passed, 3 pre-existing codegen-sandbox failures`; bump `0.1.42`
- [ ] **Live HACS `0.1.42` retest:** answer an entity clarification with "Use and remember", then confirm the same concept reworded skips clarification next time

### `ADR-0024 D2 expansion (0.1.41)` — SHIPPED

- [x] `_resolve_entity_selection_with_model` unifies residue + expansion gating at both orchestration call sites; `_run_model_entity_selection` gained `d1_selected_ids`
- [x] Expansion runs after confident `catalog_label`/`catalog_label_specificity` D1 results against the full catalog; skipped for explicit-id/overlay/semantic_alias and full-catalog-covered cases
- [x] Safe fall-back: model abstain/absent/off-catalog → D1 result stands (off-catalog fails closed, invariant #1)
- [x] HA domain hint added to `select_entity` prompt (`model_provider.py`)
- [x] Spec + ADR-0024 expansion note + BDD Scenarios F–I + evidence updated
- [x] 11 new tests; full suite `495 passed, 3 pre-existing failures` at packet close; bump `0.1.41`
- [x] Architecture review OK
- [ ] **Live HACS `0.1.41` retest:** "show kitchen temp and when the AC was running" resolves both the temp sensor and `climate.kitchen_ecobee` with no clarification (no alias needed)

### `Semantic alias live wiring Tranche 1 (0.1.40)` — SHIPPED

- [x] `SemanticMemoryStorageHelper` — dual-backend (HA Store / in-memory), per-entry scoped, `async_load` + `store_for` + `seed_store`
- [x] `prepare_semantic_memory_for_planning` — schema + duplicate-alias-ID validation, use-time validity (unavailable/not-allowlisted), never mutates store
- [x] `alias_matches_prompt` — `[a-z0-9_]+` tokenization, `MATCH_RATIO=0.6`, no 4-char length floor, trivial stop words stripped
- [x] `resolve_alias_injection` — full pipeline; `_inject_semantic_aliases` composes with direct selection, de-duplicated, `source: "semantic_alias"` recorded
- [x] Wired into `async_setup_entry` via `async_setup_semantic_memory`; wired into `job_orchestration.py` after `select_prompt_entity_ids`
- [x] 33 unit tests passing; 7 BDD scenarios; eval anchor CASE `semantic_alias_injection` in `evals/semantic_memory_store_envelope.py`
- [x] Architecture review: 9 invariants checked, no violations (allowlist boundary preserved, no store write, deterministic)
- [x] Spec `docs/specs/semantic-alias-live-wiring.md` status updated to `accepted`
- [x] Evidence file `bdd/semantic-memory/semantic-alias-live-wiring-evidence.md` written
- [x] Full suite: `484 passed, 3 failed` (pre-existing codegen-sandbox flake); bump `0.1.40`

### `Concurrent polling fix — reasoning now visible in card (0.1.38)` — SHIPPED

- [x] Root cause: snapshot poll loop was sequential (await response → schedule next); first post-submit poll acquires `planning_lock` for ~40 s → no second poll during think pass → in-progress snapshots never delivered
- [x] Fix (`isolinear-card.ts`): call `scheduleSnapshotPoll(generation)` before `await getSnapshot()` so polls fire at 1 s intervals regardless of response time; concurrent polls hit held lock, return in-progress snapshot with reasoning
- [x] Tests: bump smoke test poll interval 5 ms → 20 ms so mock response (5 ms) always resolves before pre-scheduled poll fires
- [x] Drift: ADR-0025 D3 unchanged; evidence file updated with 0.1.38 fix note
- [x] Architecture review: not run (frontend-only polling bug fix, no invariant affected, no new decision)
- [x] Verify: `451 passed, 3 failed` (pre-existing codegen flake), frontend `13 passed`, `prompt_to_chart_basic` + `dashboard_card_anchor` evals PASS, BDD-evidence review OK, bump `0.1.38`
- [x] **Live HACS `0.1.38` retest (Edge/Windows):** temperature+AC prompt still failed — `climate.kitchen_ecobee` IS in the allowlist but entity name has no token overlap with "AC"; temperature sensor wins specificity scoring (3 tokens vs 2). Reasoning streaming still not visible — polling code IS correct in deployed bundle; most likely cause is Edge serving cached pre-0.1.38 JS despite `?v=0.1.38`. Diagnostic: Edge DevTools → Network → filter "isolinear" to confirm URL. Root fixes: semantic alias live wiring (packet #1) for AC; browser cache investigation for streaming.

### `Planning rules fix — clarify on unavailable entities (0.1.37)` — SHIPPED

- [x] Root cause: `_chat_payload` planning rule 2 said "Return status chart_spec_ready with a ChartSpec for this packet" unconditionally; with the 0.1.36 format-constrained pass the model satisfied it on out-of-allowlist prompts by relabeling/reusing one approved entity into two series (e.g. one temperature sensor → "Room Temperature" + "Kitchen AC Status")
- [x] Fix (`model_provider.py` `_chat_payload` rules): replaced the unconditional rule with three — (1) `clarification_needed` when the prompt references a device/sensor/concept not represented by any approved entity (never invent/relabel/reuse); (2) `chart_spec_ready` only if every requested piece is satisfiable with approved entities; (3) each series must be a distinct approved entity, never multiple series for the same `entity_id`
- [x] Drift: none — `plan_chart` docstring documents the two-pass streaming mechanism, not the prompt rule content; statuses + clarify-not-guess behavior already documented (Invariant 1, entity-clarification/allowlist BDD). No schema/spec/ADR/BDD change for a prompt-engineering fix
- [x] Verify: tested live against Ollama (the "maren's room temperature and when the AC was running" out-of-allowlist prompt now returns `clarification_needed`); full suite `451 passed, 3 failed` (pre-existing codegen flake), model-provider planning eval PASS, BDD-evidence review OK, bump `0.1.37`

### `Two-pass reasoning streaming (0.1.36)` — SHIPPED

- [x] Root cause: 0.1.35 dropped `format` from streaming calls to unblock `think`, but without constrained decoding the model produced structurally invalid JSON on harder prompts → `invalid_planner_result` on out-of-allowlist prompts
- [x] Fix (`model_provider.py`): two-pass approach when `on_reasoning` is provided — Pass 1 `stream:true, think:true, no format` (reasoning, content discarded, failures non-fatal); Pass 2 `stream:false, format:result_schema, no think` (reliable validated result). Applied to both `plan_chart` and `select_entity`
- [x] `on_reasoning is None` path unchanged (sole call = Pass 2 / D6 fallback)
- [x] Drift: ADR-0025 D1 "two-pass correction (0.1.36)" note + streaming spec "Streaming planner transport (D1)" section rewritten for two-pass; no contract/schema/BDD change
- [x] Tests: updated 5 cases in `tests/test_live_planner_reasoning_streaming.py` for the two-call pattern (route fake_urlopen on the `stream` flag); `30 passed`
- [x] Verify: full suite `451 passed, 3 failed` (pre-existing codegen flake, identical on clean baseline via `git stash`), planning eval PASS, BDD-evidence review OK, bump `0.1.36`
- [ ] **Live HACS `0.1.36` retest (non-blocking):** confirm the previously-failing "show me temperature and when the AC was running" out-of-allowlist prompt now returns valid structure (Pass 2 constrained decoding) while reasoning still streams (Pass 1)

### `Reasoning-streaming think/format fix + temperature stopword fix (0.1.35)` — SHIPPED

- [x] Fix 1 (`model_provider.py`): make `think` and `format` mutually exclusive — streaming (reasoning) calls send `think: true` only; non-streaming calls keep `format`. Ollama suppresses thinking when `format` is set, so this was the last blocker to live reasoning streaming for thinking-capable models
- [x] Fix 1: add `_strip_markdown_json` to strip code fences thinking-mode models wrap around JSON when `format` is absent (applied in both planner + entity-selector JSON parse sites)
- [x] Fix 2 (`job_orchestration.py`): remove `"temperature"` from the distinctive-token exclusion set so it counts toward specificity scoring (ecobee temp sensor outscores a co-located door sensor instead of tying)
- [x] Drift: correction note added to ADR-0025 D1 + streaming spec line 94 (the `format`-governs-content claim the discovery invalidated); entity-resolution ADRs/spec needed no change (scoring described abstractly, stopword set not enumerated)
- [x] Refresh live-planner-reasoning BDD evidence raw block (`30 passed`, was stale at `23`) + 0.1.35 fix note
- [x] Verify: full suite `451 passed, 3 failed` (pre-existing codegen flake, identical on clean baseline), model-provider/streaming/entity-resolution evals PASS, BDD-evidence review OK, bump `0.1.35`
- [ ] **Live HACS `0.1.35` retest (non-blocking):** confirm reasoning text appears in the chart slot during planning with a thinking-capable Ollama model; "last 4 hours" resolves to a 4-hour window

### `ADR-0025 live planner reasoning streaming (0.1.32) + bug fixes (0.1.33) + redaction hardening (0.1.34)` — SHIPPED

- [x] 0.1.32: streaming planner (`stream: true`), `sanitize_reasoning` + 2000-char rolling cap, per-job live-reasoning slot, `progress.reasoning` + phase label on planning snapshot, replaced by chart on completion, never persisted; spans both model calls; Lit card chart-slot rendering; frontend bundle rebuilt + synced
- [x] 0.1.33 bug fix 1: send `"think": true` on streaming planner + entity-selector requests so thinking-capable Ollama models actually stream
- [x] 0.1.33 bug fix 2: `_parse_window_timestamp` treats naive ISO 8601 datetimes as UTC instead of forcing the 24h fallback
- [x] 0.1.34 (closeout): `sanitize_reasoning` now also redacts named secret vocabulary (`access_token`/`*_token`/`ollama_api_key`/`api_key`) + bare `sk-…`/JWT tokens (architecture-review finding; invariant-3 / ADR-0025 D5 gap); 4 new redaction tests
- [x] Verify: full suite `451 passed, 3 failed` (pre-existing codegen flake), all evals PASS, BDD-evidence review OK, architecture review CONCERNS→resolved, bump `0.1.34`

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
- (j) **Multi-concept planning failure on `gemma4:e4b`** — live `0.1.43` testing:
  the prompt "show kitchen temp and when the AC was running" reaches planning
  (entity selection + reasoning streaming both work) but fails at
  `model_provider_planner_not_chart_spec_ready` — the model streams ~21s of
  planning reasoning then does not emit a `chart_spec_ready` result for the
  numeric+binary overlay composition. Not an ADR-0026 issue (that packet only
  moved *where* selection runs). Likely planner-prompt/model-capability: the
  overlay-family planning prompt may need tightening, or the model needs more
  guidance to emit the overlay ChartSpec. Worth: capture the raw Pass-2 planner
  output for this prompt and decide between prompt-engineering vs. a stronger
  model for overlay prompts.
- (k) **Cosmetic: planning-phase label during deferred selection** — after
  ADR-0026, some in-progress polls during the planning phase show
  `progress.message` = "Approved entities are staged for model planning." (the
  static deferral-snapshot message) instead of "Planning chart…"; reasoning
  still streams. `apply_live_reasoning` should also normalize the message/stage
  to the active phase label on the entities-bearing planning snapshot.

## Blockers

- None.
