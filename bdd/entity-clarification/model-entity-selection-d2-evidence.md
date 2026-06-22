# Model-Driven Entity Selection D2 — BDD Evidence

**Run timestamp:** 2026-06-22 01:53 UTC

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

## Full suite

```
python3 -m pytest tests/ -q
420 passed, 3 failed
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

---

## Evals

```
python3 evals/timeline_render_family_routing.py         → PASS
python3 evals/prompt_to_chart_basic.py                  → PASS
python3 evals/home_assistant_job_orchestration_model_provider_planning_scaffold.py → PASS
```
