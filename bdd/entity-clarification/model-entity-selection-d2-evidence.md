# Model-Driven Entity Selection D2 — BDD Evidence

**Run timestamp:** 2026-06-23 19:25 UTC (D2 expansion, 0.1.41) — earlier
residue-path run preserved below.

**BDD file:** `bdd/entity-clarification/model-entity-selection-d2-bdd.md`

---

## Test command and output

```
python3 -m pytest tests/test_first_real_vertical_slice.py -k "EntitySelection" -v
```

```
collected 14 items

EntitySelectionD2Tests::test_clarification_result_includes_candidate_items_on_tie PASSED
EntitySelectionD2Tests::test_clarification_result_includes_candidate_items_on_zero_match PASSED
EntitySelectionD2Tests::test_invalid_entity_from_model_falls_back_to_clarification PASSED
EntitySelectionD2Tests::test_model_abstains_returns_rejection PASSED
EntitySelectionD2Tests::test_model_picks_entity_not_in_allowlist_fail_closed PASSED
EntitySelectionD2Tests::test_model_picks_entity_not_in_candidate_set_fail_closed PASSED
EntitySelectionD2Tests::test_model_picks_valid_entity_accepted PASSED
EntitySelectionD2Tests::test_model_without_select_entity_returns_rejection PASSED
EntitySelectionD2Tests::test_no_model_provider_returns_rejection PASSED
EntitySelectionD2Tests::test_no_model_shows_clarification_without_selector_call PASSED
EntitySelectionD2Tests::test_selector_schema_pins_entity_ids_to_enum PASSED
EntitySelectionD2Tests::test_tie_model_abstains_clarification_shown PASSED
EntitySelectionD2Tests::test_tie_model_picks_proceeds_to_render PASSED
EntitySelectionD2Tests::test_zero_matches_model_picks_from_full_catalog PASSED

14 passed in 0.36s
```

---

## D2 expansion run (0.1.41, 2026-06-23)

```
python3 -m pytest tests/test_first_real_vertical_slice.py -k "EntitySelection" -v
25 passed, 57 deselected in 0.40s
```

All 11 D2-expansion tests pass alongside the 14 original residue-path tests
(no regression):

```
test_d1_confidently_resolves_then_misses_ac_concept PASSED
test_d2_expansion_adds_missed_entity PASSED
test_d2_expansion_confirms_d1_unchanged PASSED
test_d2_expansion_falls_back_to_d1_when_model_abstains PASSED
test_d2_expansion_integration_renders_both_entities PASSED
test_d2_expansion_off_catalog_pick_falls_back_to_d1 PASSED
test_d2_expansion_skipped_for_explicit_entity_id PASSED
test_d2_expansion_skipped_for_overlay_composition PASSED
test_d2_expansion_skipped_for_semantic_alias PASSED
test_d2_expansion_skipped_when_d1_covers_whole_catalog PASSED
test_d2_expansion_skipped_without_model PASSED
```

## Full suite

```
python3 -m pytest tests/ -q
495 passed, 3 failed   (0.1.41, 2026-06-23)
420 passed, 3 failed   (earlier residue-path run)
```

The 3 failures are the pre-existing codegen-sandbox matplotlib subprocess flake
(confirmed identical on clean baseline; not introduced by this packet).

---

## Scenario evidence

### Scenario A: Model resolves a top-score tie

- Catalog: `climate.upstairs_thermostat` + `climate.downstairs_thermostat`
- Prompt: `"show thermostat history"` → both score 1 on "thermostat" → tie
- D2 selector called with `candidate_entity_ids: [climate.upstairs_thermostat, climate.downstairs_thermostat]`
- Model returns `status: entity_selected, entity_ids: [climate.upstairs_thermostat]`
- Selection source: `model_entity_selection`
- Final snapshot: `status: complete` (renders without clarification)
- Test: `test_tie_model_picks_proceeds_to_render` ✓

### Scenario B: Model abstains; clarification is shown

- Same catalog + prompt
- Model returns `status: clarification_needed`
- `_run_model_entity_selection` code: `model_entity_selection_abstained`
- Final snapshot: `status: clarification_needed`
  with options for both thermostats
- `select_calls: 1`, `plan_calls: 0`
- Test: `test_tie_model_abstains_clarification_shown` ✓

### Scenario C: No model configured; clarification shown immediately

- No planner in `hass.data`
- `_run_model_entity_selection` code: `no_model_provider_for_entity_selection`
- Final snapshot: `status: clarification_needed` (no model call)
- Test: `test_no_model_shows_clarification_without_selector_call` ✓

### Scenario D: Model returns entity outside candidate set; fail closed

- Model returns `sensor.unlisted_entity` (not in catalog)
- `_run_model_entity_selection` code: `model_entity_selection_out_of_allowlist`
- Final snapshot: `status: clarification_needed`
- `select_calls: 1`, `plan_calls: 0`
- Test: `test_invalid_entity_from_model_falls_back_to_clarification` ✓

### Scenario E: Zero matches; model picks from full catalog

- Catalog: `sensor.upstairs_temperature`
- Prompt: `"show humidity"` → zero matches
- Full catalog passed as `candidate_entity_ids`
- Model picks `sensor.upstairs_temperature`
- Final snapshot: `status: complete`
- Tests: `test_zero_matches_model_picks_from_full_catalog` ✓

### Scenario F: D2 expansion adds a concept D1 missed

- Catalog: `sensor.kitchen_temperature` + `climate.kitchen_ecobee`
- Prompt: `"show kitchen temperature and when the AC was running"`
- D1: `source: catalog_label_specificity`, `entity_ids: [sensor.kitchen_temperature]`
  (verified by `test_d1_confidently_resolves_then_misses_ac_concept`)
- D2 invoked against full catalog with
  `already_selected_entity_ids: [sensor.kitchen_temperature]`
- Model returns both entities → resolved `source: model_entity_selection`,
  `entity_ids: {sensor.kitchen_temperature, climate.kitchen_ecobee}`
- Integration: both entities forwarded to planning, `status: complete`,
  `select_calls: 1`, `plan_calls: 1`
- Tests: `test_d2_expansion_adds_missed_entity`,
  `test_d2_expansion_integration_renders_both_entities` ✓

### Scenario G: D2 expansion confirms D1 and adds nothing

- Prompt: `"show kitchen temperature"`; model returns only the temp sensor
- Resolved selection: exactly `[sensor.kitchen_temperature]`, accepted
- Test: `test_d2_expansion_confirms_d1_unchanged` ✓

### Scenario H: D2 expansion falls back to the confident D1 result

- Model abstains / absent / off-catalog → D1's confident result stands; no
  clarification surfaced
- Tests: `test_d2_expansion_falls_back_to_d1_when_model_abstains`,
  `test_d2_expansion_skipped_without_model`,
  `test_d2_expansion_off_catalog_pick_falls_back_to_d1` ✓

### Scenario I: D2 expansion skipped where it cannot help

- No `select_entity` call for sources `explicit_entity_id`,
  `numeric_with_overlay`, `semantic_alias`, nor when D1 covers the whole catalog
- Tests: `test_d2_expansion_skipped_for_explicit_entity_id`,
  `test_d2_expansion_skipped_for_overlay_composition`,
  `test_d2_expansion_skipped_for_semantic_alias`,
  `test_d2_expansion_skipped_when_d1_covers_whole_catalog` ✓

---

## Evals

```
python3 evals/timeline_render_family_routing.py         → PASS
python3 evals/prompt_to_chart_basic.py                  → PASS
python3 evals/home_assistant_job_orchestration_model_provider_planning_scaffold.py → PASS
```
