# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-23 (spec session — Tranche 2 spec + D2 expansion decision)
**Phase:** `First real vertical slice accepted`
**Next bounded packet:** `Semantic alias Tranche 2 propose/confirm/save (spec+BDD done, implementation next) — but implement D2 expansion (ADR-0024 D2 expansion note) first or in parallel, since it reduces clarification frequency. Then capability envelope (#2). Then night mode spec+ADR (#3).`
**Current readiness:** `READY FOR LIVE TEST (0.1.40) — reasoning streaming and AC prompt fix still pending live verification`

> **⚠️ Direction change (2026-06-12):** Before picking another scaffold packet,
> read [`docs/reality-pivot-review.md`](docs/reality-pivot-review.md). The next
> work is a **real vertical slice** (real recorder history + real Ollama +
> real matplotlib, rendered in-process) — not another simulated scaffold. Stop
> adding `*_anchor.py` verifiers; pytest is the single source of behavioral truth.

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-23** — `Tranche 2 spec + D2 expansion decision (no version bump — spec-only session)` — Design session: no code shipped. (1) Wrote `docs/specs/semantic-alias-save-tranche2.md` (draft) defining the propose/confirm/save flow via the existing `clarification/answer` + `remember: true` path: `can_remember: true` for entity-selection options, alias suggestion stored in `job["alias_suggestions"]` at question-build time, `async_save_alias` write method on `SemanticMemoryStorageHelper`, natural name derivation via `derive_alias_natural_names`, save failure non-blocking, `aliases` field added to `IntegrationJobSnapshot` schema for complete snapshot display. (2) Wrote paired `bdd/semantic-memory/semantic-alias-save-tranche2-bdd.md`. (3) Captured **D2 expansion decision** in ADR-0024: D2 should run as a validation+expansion pass after ALL D1 results (not only on tie/zero), because D1 can "succeed" with a partial answer when the prompt contains multiple concepts and one concept's entity has no token overlap with its name (e.g., "AC" → `climate.kitchen_ecobee`). Add HA domain hint to `select_entity` prompt: *"climate entities represent HVAC systems."* D2 expansion is a prerequisite or parallel companion to Tranche 2 (reduces how often clarification is needed). No code changed; no version bump. **Next:** implement D2 expansion + Tranche 2; live test 0.1.40 (reasoning streaming + AC prompt).

- **2026-06-23** — `Semantic alias live wiring Tranche 1 (0.1.40)` — New feature: the integration now loads a persisted per-config-entry `SemanticMemoryStore` envelope, matches valid enabled aliases against the prompt by token overlap, and injects matched entity IDs into entity selection before planning. **Architecture:** `SemanticMemoryStorageHelper` — dual-backend (HA `Store` in production, in-memory in tests/scaffold), per-config-entry scoped. `prepare_semantic_memory_for_planning` — use-time validity against the current catalog (unavailable / not-allowlisted); never mutates the store. `alias_matches_prompt` — `[a-z0-9_]+` tokenization, `MATCH_RATIO=0.6`, no min-length floor (unlike entity selector), trivial stop words stripped. `_inject_semantic_aliases` — pure function composing alias-injected entities with direct results, de-duplicated, `source: "semantic_alias"` recorded. Wired into `job_orchestration.py` after `select_prompt_entity_ids`; wired into `async_setup_entry` via `async_setup_semantic_memory`. **Invariant compliance:** injected entities already validated `visible_to_agent: true` (allowlist boundary preserved, invariant #1); no store write (Tranche 2); deterministic (invariant #7). **Proof:** 33 new unit tests (all passing), 7 BDD scenarios in `bdd/semantic-memory/semantic-alias-live-wiring-bdd.md`, eval anchor CASE (`semantic_alias_injection`) added to `evals/semantic_memory_store_envelope.py` showing `climate.kitchen_ecobee` injected from prompt "show kitchen temp and when the AC was running" with `matched_alias_ids: ["whole_house_ac"]`. Architecture review: 9 invariants checked, no violations. **Full suite:** `484 passed, 3 failed` (pre-existing codegen-sandbox flake). Spec status: `accepted`. Bump `0.1.40`. **Next:** render-family capability envelope (#2); night mode spec+ADR (#3); semantic alias Tranche 2 (propose/confirm/save).
- **2026-06-23** — `Allowlist debug logging + think-pass latency cap (0.1.39)` — Two operational improvements, no new user-facing behavior, no ADR/spec/BDD needed. **(1) Entity resolution DEBUG logging** (`job_orchestration.py`): added 7 `_LOGGER.debug()` calls throughout `select_prompt_entity_ids` — catalog entity list on entry, explicit entity IDs in prompt, per-candidate scores, and the resolution path taken (single match, overlay composition, unique top scorer, or tie → clarification). Requires `custom_components.isolinear.job_orchestration: debug` in `configuration.yaml`. Colin's explicit request after the 0.1.38 live retest: `climate.kitchen_ecobee` IS in the allowlist but `select_prompt_entity_ids` drops it because the temperature sensor scores 3 meaningful tokens vs climate's 2; "AC" has no matching token in the entity name at all — root fix is semantic alias live wiring (packet #1). **(2) `num_predict: 512` cap on think pass** (`model_provider.py`): applied to both `_chat_payload` and `_entity_selector_payload` think-pass options. Caps thinking tokens to reduce latency from 24–44 s to ~10–15 s. Result pass is uncapped. **(3) Live 0.1.38 retest findings (Edge/Windows):** temperature+AC prompt still failed — diagnosed above. Reasoning streaming still not visible in card — polling code IS correct in the deployed bundle (verified in `dist/isolinear-card.js` and `frontend/src/isolinear-card.ts`); most likely cause is Edge serving the pre-0.1.38 cached bundle despite `?v=0.1.38`. Diagnostic: check Edge DevTools → Network → filter "isolinear" to confirm which URL loads. **Verify:** `444 passed` (pre-existing codegen flake excluded), `home_assistant_job_orchestration_model_provider_planning_scaffold` + `home_assistant_approved_entity_catalog_scaffold` evals PASS, BDD-evidence review OK (no new scenarios — operational changes below the bar). Bump `0.1.39`. **Next:** semantic-alias live wiring (#1); ADR-0023 capability envelope (#2); night mode (#3).
- **2026-06-23** — `Concurrent polling fix — reasoning now visible in card (0.1.38)` — One bug fix in existing behavior (no new features/architecture). **Root cause:** the snapshot poll loop was sequential — each poll awaited the WebSocket response before scheduling the next. Since the first post-submit poll acquires `planning_lock` and runs all model calls (~40 s), no second poll ever fired during the think pass, so the in-progress reasoning snapshots were never delivered to the card. The architecture (ADR-0025 D3 "surfaced through the existing poll loop at ~1s granularity") was correct; the implementation didn't achieve it. **Fix (`isolinear-card.ts`):** moved `scheduleSnapshotPoll(generation)` to before `await getSnapshot()`. Polls now fire every 1 s regardless of response time; concurrent polls hit the held lock, return in-progress snapshots with live reasoning, and the card renders them. Generation counter + `cancelSnapshotPolling()` guard stale responses. **Tests:** smoke test poll interval bumped from 5 ms → 20 ms so mock responses (5 ms) resolve before the pre-scheduled poll fires, keeping call-count assertions exact. **Drift:** ADR-0025 D3 unchanged (behavior matches the stated "~1s granularity"); evidence file updated with 0.1.38 fix note. Architecture review not run (frontend-only polling bug fix; no invariant affected). **Verify:** `451 passed, 3 failed` (pre-existing codegen flake), frontend `13 passed`, `prompt_to_chart_basic` + `dashboard_card_anchor` evals PASS, BDD-evidence review OK. Bump `0.1.38`. **Next:** semantic-alias live wiring (#1); ADR-0023 capability envelope (#2); night mode (#3). Live HACS `0.1.38` retest should confirm reasoning text appears in the card during planning.
- **2026-06-22** — `Planning rules fix — clarify on unavailable entities (0.1.37)` — One bug fix in existing behavior (no new features/architecture). **Root cause:** in `model_provider.py` `_chat_payload`, planning rule 2 said "Return status chart_spec_ready with a ChartSpec for this packet" *unconditionally*. With the 0.1.36 format-constrained plan pass, on prompts asking about something *not* in `approved_entity_ids` the model satisfied the unconditional rule by relabeling/reusing an approved entity — e.g. for "show me maren's room temperature and when the AC was running" with only `sensor.maren_ecobee_sensor_temperature` approved, it returned two series both pointing at that same temperature entity ("Room Temperature" + "Kitchen AC Status"). Semantically wrong and confusing; also brushes invariant 1 (clarify, never silent guess). **Fix (`_chat_payload` planning rules):** replaced the single unconditional rule with three: (1) if the prompt references a device/sensor/concept not represented by any approved entity, return `clarification_needed` with a `clarification_question` — never invent, relabel, or reuse an entity to stand in for a missing one; (2) only return `chart_spec_ready` if *every* requested piece of info is satisfiable with approved entities; (3) each series must represent a distinct approved entity — never create multiple series for the same `entity_id`. **Drift handled:** none needed — `plan_chart` docstring documents the two-pass streaming mechanism (ADR-0025), not the prompt rule content; the statuses (`chart_spec_ready`/`clarification_needed`) and the clarify-not-guess behavior are already the documented contract (Invariant 1, entity-clarification/allowlist BDD). No schema/spec/ADR/BDD change for this prompt-engineering fix. **Verify:** tested live against Ollama — the "maren's room temperature and when the AC was running" prompt with only the temperature sensor approved now returns `clarification_needed` with an appropriate question. Full suite `451 passed, 3 failed` (the 3 = pre-existing codegen-sandbox matplotlib subprocess flake; no codegen/sandbox file touched), model-provider planning eval `PASS`, BDD-evidence review `OK` (no new scenario/evidence introduced; behavior aligns with existing entity-clarification scenarios). Bumped `manifest.json` + `const.py` to `0.1.37`. **Next:** semantic-alias live wiring (#1); ADR-0023 capability envelope (#2); night mode (#3).
## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

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

## Blockers

- None.
