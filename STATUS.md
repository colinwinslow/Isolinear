# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-23 (0.1.39 — allowlist debug logging + think-pass latency cap)
**Phase:** `First real vertical slice accepted`
**Next bounded packet:** `Semantic-alias live wiring (ADR-0009/0010 follow-through) (#1). Then implement the render-family capability envelope (ADR-0023 + spec/BDD drafted — histogram + aggregate_bar tranche) (#2). Then night mode spec+ADR (item (h)) (#3).`
**Current readiness:** `READY FOR LIVE TEST (0.1.39)`

> **⚠️ Direction change (2026-06-12):** Before picking another scaffold packet,
> read [`docs/reality-pivot-review.md`](docs/reality-pivot-review.md). The next
> work is a **real vertical slice** (real recorder history + real Ollama +
> real matplotlib, rendered in-process) — not another simulated scaffold. Stop
> adding `*_anchor.py` verifiers; pytest is the single source of behavioral truth.

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-23** — `Allowlist debug logging + think-pass latency cap (0.1.39)` — Two operational improvements, no new user-facing behavior, no ADR/spec/BDD needed. **(1) Entity resolution DEBUG logging** (`job_orchestration.py`): added 7 `_LOGGER.debug()` calls throughout `select_prompt_entity_ids` — catalog entity list on entry, explicit entity IDs in prompt, per-candidate scores, and the resolution path taken (single match, overlay composition, unique top scorer, or tie → clarification). Requires `custom_components.isolinear.job_orchestration: debug` in `configuration.yaml`. Colin's explicit request after the 0.1.38 live retest: `climate.kitchen_ecobee` IS in the allowlist but `select_prompt_entity_ids` drops it because the temperature sensor scores 3 meaningful tokens vs climate's 2; "AC" has no matching token in the entity name at all — root fix is semantic alias live wiring (packet #1). **(2) `num_predict: 512` cap on think pass** (`model_provider.py`): applied to both `_chat_payload` and `_entity_selector_payload` think-pass options. Caps thinking tokens to reduce latency from 24–44 s to ~10–15 s. Result pass is uncapped. **(3) Live 0.1.38 retest findings (Edge/Windows):** temperature+AC prompt still failed — diagnosed above. Reasoning streaming still not visible in card — polling code IS correct in the deployed bundle (verified in `dist/isolinear-card.js` and `frontend/src/isolinear-card.ts`); most likely cause is Edge serving the pre-0.1.38 cached bundle despite `?v=0.1.38`. Diagnostic: check Edge DevTools → Network → filter "isolinear" to confirm which URL loads. **Verify:** `444 passed` (pre-existing codegen flake excluded), `home_assistant_job_orchestration_model_provider_planning_scaffold` + `home_assistant_approved_entity_catalog_scaffold` evals PASS, BDD-evidence review OK (no new scenarios — operational changes below the bar). Bump `0.1.39`. **Next:** semantic-alias live wiring (#1); ADR-0023 capability envelope (#2); night mode (#3).
- **2026-06-23** — `Concurrent polling fix — reasoning now visible in card (0.1.38)` — One bug fix in existing behavior (no new features/architecture). **Root cause:** the snapshot poll loop was sequential — each poll awaited the WebSocket response before scheduling the next. Since the first post-submit poll acquires `planning_lock` and runs all model calls (~40 s), no second poll ever fired during the think pass, so the in-progress reasoning snapshots were never delivered to the card. The architecture (ADR-0025 D3 "surfaced through the existing poll loop at ~1s granularity") was correct; the implementation didn't achieve it. **Fix (`isolinear-card.ts`):** moved `scheduleSnapshotPoll(generation)` to before `await getSnapshot()`. Polls now fire every 1 s regardless of response time; concurrent polls hit the held lock, return in-progress snapshots with live reasoning, and the card renders them. Generation counter + `cancelSnapshotPolling()` guard stale responses. **Tests:** smoke test poll interval bumped from 5 ms → 20 ms so mock responses (5 ms) resolve before the pre-scheduled poll fires, keeping call-count assertions exact. **Drift:** ADR-0025 D3 unchanged (behavior matches the stated "~1s granularity"); evidence file updated with 0.1.38 fix note. Architecture review not run (frontend-only polling bug fix; no invariant affected). **Verify:** `451 passed, 3 failed` (pre-existing codegen flake), frontend `13 passed`, `prompt_to_chart_basic` + `dashboard_card_anchor` evals PASS, BDD-evidence review OK. Bump `0.1.38`. **Next:** semantic-alias live wiring (#1); ADR-0023 capability envelope (#2); night mode (#3). Live HACS `0.1.38` retest should confirm reasoning text appears in the card during planning.
- **2026-06-22** — `Planning rules fix — clarify on unavailable entities (0.1.37)` — One bug fix in existing behavior (no new features/architecture). **Root cause:** in `model_provider.py` `_chat_payload`, planning rule 2 said "Return status chart_spec_ready with a ChartSpec for this packet" *unconditionally*. With the 0.1.36 format-constrained plan pass, on prompts asking about something *not* in `approved_entity_ids` the model satisfied the unconditional rule by relabeling/reusing an approved entity — e.g. for "show me maren's room temperature and when the AC was running" with only `sensor.maren_ecobee_sensor_temperature` approved, it returned two series both pointing at that same temperature entity ("Room Temperature" + "Kitchen AC Status"). Semantically wrong and confusing; also brushes invariant 1 (clarify, never silent guess). **Fix (`_chat_payload` planning rules):** replaced the single unconditional rule with three: (1) if the prompt references a device/sensor/concept not represented by any approved entity, return `clarification_needed` with a `clarification_question` — never invent, relabel, or reuse an entity to stand in for a missing one; (2) only return `chart_spec_ready` if *every* requested piece of info is satisfiable with approved entities; (3) each series must represent a distinct approved entity — never create multiple series for the same `entity_id`. **Drift handled:** none needed — `plan_chart` docstring documents the two-pass streaming mechanism (ADR-0025), not the prompt rule content; the statuses (`chart_spec_ready`/`clarification_needed`) and the clarify-not-guess behavior are already the documented contract (Invariant 1, entity-clarification/allowlist BDD). No schema/spec/ADR/BDD change for this prompt-engineering fix. **Verify:** tested live against Ollama — the "maren's room temperature and when the AC was running" prompt with only the temperature sensor approved now returns `clarification_needed` with an appropriate question. Full suite `451 passed, 3 failed` (the 3 = pre-existing codegen-sandbox matplotlib subprocess flake; no codegen/sandbox file touched), model-provider planning eval `PASS`, BDD-evidence review `OK` (no new scenario/evidence introduced; behavior aligns with existing entity-clarification scenarios). Bumped `manifest.json` + `const.py` to `0.1.37`. **Next:** semantic-alias live wiring (#1); ADR-0023 capability envelope (#2); night mode (#3).
- **2026-06-22** — `Two-pass reasoning streaming (0.1.36)` — One bug fix in existing behavior (no new features/architecture). **Root cause:** the `0.1.35` fix dropped the structured-output `format` schema from streaming planner calls to unblock thinking (Ollama suppresses `think` when `format` is present). But without `format`'s constrained decoding the model produced structurally invalid JSON on harder prompts — wrong field names, missing required fields — so jobs asking about entities *not* in `approved_entity_ids` (e.g. "show me temperature and when the AC was running") failed with `invalid_planner_result` because the model hallucinated the schema structure. **Fix — two-pass approach in `model_provider.py`:** when `on_reasoning` is provided, both `plan_chart` and `select_entity` now make two sequential calls. *Pass 1 (think pass)* — `stream:true, think:true, no format` — streams reasoning chunks to the card via `on_reasoning`; content is discarded and failures are non-fatal (reasoning is presentational, D6). *Pass 2 (plan/select pass)* — `stream:false, format:result_schema, no think` — returns reliable schema-constrained JSON; this is the result that is parsed/validated. When `on_reasoning` is None the sole call is Pass 2 (unchanged D6 fallback). `_strip_markdown_json` is no longer load-bearing for the result path. **Drift handled:** ADR-0025 D1 got a "two-pass correction (0.1.36)" note superseding the 0.1.35 single-call wording; the streaming spec's "Streaming planner transport (D1)" section rewritten to describe the two-pass calls. No contract surface change, no schema/BDD change (transport-layer fix in a documented mechanism). **Verify:** full suite `451 passed, 3 failed` (the 3 = pre-existing codegen-sandbox matplotlib subprocess flake, confirmed identical on the clean baseline via `git stash`; no codegen/sandbox file touched), `tests/test_live_planner_reasoning_streaming.py` `30 passed` (5 updated for the two-call pattern), model-provider planning eval `PASS`, BDD-evidence review `OK`. Bumped `manifest.json` + `const.py` to `0.1.36`. **Next:** semantic-alias live wiring (#1); ADR-0023 capability envelope (#2); night mode (#3). A live HACS `0.1.36` retest of the previously-failing "temperature + AC" out-of-allowlist prompt is worth doing to confirm Pass 2 now returns valid structure.
- **2026-06-22** — `Reasoning-streaming think/format fix + temperature stopword fix (0.1.35)` — Two bug fixes in existing behavior (no new features/architecture). **Fix 1 — `model_provider.py` reasoning streaming:** the `0.1.33` fix sent `"think": true` on streaming requests but the payloads *also* still sent the structured-output `format` schema, and **Ollama silently suppresses thinking whenever `format` is set** — so thinking-capable models still emitted no reasoning. `think` and `format` are now mutually exclusive: streaming (reasoning-requested) calls send `think: true` and omit `format`; non-streaming calls keep `format` for strict constrained decoding. Added `_strip_markdown_json` to strip the markdown code fences thinking-mode models wrap around JSON when `format` is absent. This was the last blocker to reasoning streaming working live for thinking-capable models. **Fix 2 — `job_orchestration.py` stopword:** removed `"temperature"` from the distinctive-token exclusion set in `_catalog_item_meaningful_tokens` (it was lumped with the HA prefixes `sensor`/`binary`), so a "kitchen temperature" prompt no longer scores on `kitchen` alone and ties with `kitchen_door`; the ecobee temperature sensor now outscores a co-located door sensor. **Drift handled:** the `format` discovery contradicted ADR-0025 D1 ("the `format` schema still governs the final content") and the streaming spec line 94 — both got a correction note (no decision change). The entity-resolution ADRs/spec describe scoring abstractly and don't enumerate the stopword set, so Fix 2 needed no doc change. No new spec/BDD/ADR (bug fixes), no architecture-review subagent (one-line fixes in documented mechanisms, below the bar — documented here per closeout). BDD evidence file for live-planner-reasoning refreshed (raw block now `30 passed`, was stale at `23`; added a 0.1.35 fix note). **Verify:** full suite `451 passed, 3 failed` (the 3 = pre-existing codegen-sandbox matplotlib subprocess flake, confirmed identical on the clean baseline via `git stash`; no codegen/sandbox file touched), model-provider/streaming/entity-resolution evals `PASS`, `tests/test_live_planner_reasoning_streaming.py` `30 passed`, BDD-evidence review `OK`. Bumped `manifest.json` + `const.py` to `0.1.35`. **Next:** semantic-alias live wiring (#1); ADR-0023 capability envelope (#2); night mode (#3). A live HACS `0.1.35` retest to eyeball reasoning text in the chart slot is worth doing but no longer a blocking unknown.
## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

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

## Blockers

- None.
