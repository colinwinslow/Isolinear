# Composition membership: model-validated entity set — BDD Evidence

**Run timestamp:** 2026-06-27 UTC (ADR-0028, 0.1.48)

**BDD file:** `bdd/entity-clarification/model-validated-composition-membership-bdd.md`
**Spec:** `docs/specs/model-validated-composition-membership.md`

Raw outputs (not summaries) for each scenario. The live-model captures use the real
`gemma4:e4b` endpoint through the production `select_entity` payload + schema, with the
real allowlist entity IDs that produced the `0.1.47` live failures.

---

## Unit tests (orchestration wiring, fail-soft, gate)

```
python3 -m pytest tests/test_composition_membership.py -v
```

```
collected 9 items

CompositionPruneTests::test_door_prompt_prunes_temp_and_routes_to_timeline PASSED
CompositionPruneTests::test_identical_model_result_keeps_composition_source PASSED
CompositionPruneTests::test_model_abstain_keeps_deterministic_composition PASSED
CompositionPruneTests::test_no_planner_keeps_composition PASSED
CompositionPruneTests::test_no_shared_token_skips_model_call PASSED
CompositionPruneTests::test_out_of_allowlist_model_id_fails_closed_to_composition PASSED
CompositionPruneTests::test_temp_ac_prompt_prunes_spurious_door_and_keeps_overlay PASSED
SharedTokenGateTests::test_distinct_tokens_not_shared PASSED
SharedTokenGateTests::test_shared_location_token_detected PASSED

9 passed
```

## Eval CASE evidence

```
python3 evals/composition_membership_prune.py
```

```
CASE composition_prune_door_to_timeline
  given.prompt   = "when was the kitchen door open today"
  when.d1_source = "numeric_with_overlay"
  when.d1_set    = ["sensor.kitchen_ecobee_temperature", "binary_sensor.kitchen_door"]
  when.model_returns = ["binary_sensor.kitchen_door"]
  then.resolved_set    = ["binary_sensor.kitchen_door"]
  then.resolved_source = "model_entity_selection"
  then.render_family   = "timeline"
  then.model_calls     = 1
PASS composition_prune_door_to_timeline

CASE composition_prune_keeps_overlay
  given.prompt   = "show kitchen temp and when the AC was running"
  when.d1_set    = ["sensor.kitchen_ecobee_temperature", "binary_sensor.kitchen_door", "climate.kitchen_ecobee"]
  when.model_returns = ["sensor.kitchen_ecobee_temperature", "climate.kitchen_ecobee"]
  then.resolved_set  = ["climate.kitchen_ecobee", "sensor.kitchen_ecobee_temperature"]
  then.render_family = "time_series_overlay"
  then.model_calls   = 1
PASS composition_prune_keeps_overlay

CASE composition_gate_skips_distinct_tokens
  given.prompt = "kitchen temperature and the front door"
  when.d1_set  = ["sensor.kitchen_ecobee_temperature", "binary_sensor.front_door"]
  then.resolved_set = ["binary_sensor.front_door", "sensor.kitchen_ecobee_temperature"]
  then.model_calls  = 0
PASS composition_gate_skips_distinct_tokens

PASS composition_membership_prune
```

---

## Scenario A — subject is a binary entity; numeric noise match pruned (live model)

**Prompt:** `when was the kitchen door open today`
**Disclosed candidates:** `{"sensor.kitchen_ecobee_temperature": "Kitchen Temperature", "binary_sensor.kitchen_door": "Kitchen Door"}`
**D1 deterministic composition family (before prune):** `time_series_overlay` (temperature primary + door overlay — the bug)

**Live `gemma4:e4b` `select_entity` raw response:**

```json
{"status": "entity_selected", "entity_ids": ["binary_sensor.kitchen_door"], "reasoning_summary": "The user asks about the 'kitchen door' being open, which directly corresponds to the binary_sensor.kitchen_door entity."}
```

**Pruned set:** `["binary_sensor.kitchen_door"]` (temperature noise match dropped)
**Resolved family after prune:** `timeline`

This is the deterministic live failure from `0.1.47` (the planner returned
`clarification_needed` — "which entity should track the door's status?"); pruning the
temperature sensor routes the door to a standalone timeline instead.

## Scenario B — numeric primary + intentional overlay; binary noise match pruned (live model)

**Prompt:** `show kitchen temp and when the AC was running`
**Disclosed candidates:** `{"sensor.kitchen_ecobee_temperature": "Kitchen Temperature", "binary_sensor.kitchen_door": "Kitchen Door", "climate.kitchen_ecobee": "Kitchen ecobee"}`
**D1 deterministic composition family (before prune):** `time_series_overlay` (with the
spurious `binary_sensor.kitchen_door` second overlay)

**Live `gemma4:e4b` `select_entity` raw response:**

```json
{"status": "entity_selected", "entity_ids": ["sensor.kitchen_ecobee_temperature", "climate.kitchen_ecobee"], "reasoning_summary": "The user asks for 'kitchen temp' (mapped to sensor.kitchen_ecobee_temperature) and when the 'AC was running' (mapped to the climate entity, climate.kitchen_ecobee). Both entities are relevant to the request."}
```

**Pruned set:** `["sensor.kitchen_ecobee_temperature", "climate.kitchen_ecobee"]` (door dropped)
**Resolved family after prune:** `time_series_overlay` (temperature line + AC overlay)

The spurious door overlay that tipped the planner into clarification is removed; the
genuine temp + AC overlay is preserved.

## Scenario C — gate skips the prune when candidates share no token

Covered by eval CASE `composition_gate_skips_distinct_tokens` above:
`"kitchen temperature and the front door"` composes
`[sensor.kitchen_ecobee_temperature, binary_sensor.front_door]`, which share no prompt
token, so `_composition_has_shared_token` is false, **no `select_entity` call is made**
(`model_calls = 0`), and the deterministic composition is kept verbatim.

## Scenario D — genuine ambiguity still clarifies

Covered by unit test `test_model_abstain_keeps_deterministic_composition` and the
existing ADR-0024 D2 abstention path: when the model returns `clarification_needed`
(or a provider failure), `_prune_composition_with_model` returns the deterministic
composition unchanged; a genuinely ambiguous same-kind set continues to the
clarification card via the existing residue path.

## Scenario E — out-of-catalog model id fails closed

Covered by unit test `test_out_of_allowlist_model_id_fails_closed_to_composition`:
when the model returns `["binary_sensor.not_approved"]`, `_run_model_entity_selection`
rejects the off-catalog id (`model_entity_selection_out_of_allowlist`) and the
deterministic composition stands — the unapproved entity is never disclosed or
charted (invariant #1).
