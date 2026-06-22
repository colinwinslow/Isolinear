# Model-Driven Entity Selection D2 BDD

ADR-0024 D2: when the deterministic specificity fast-path cannot resolve (a
top-score tie or zero matches), ask the model to select the entity before
showing the user a clarification card.

Status: **accepted** — implementation anchor landed 2026-06-22.

Evidence file: `bdd/entity-clarification/model-entity-selection-d2-evidence.md`

Related artifacts:

- Source feature: `docs/bdd/entity-clarification.feature`
- ADR: `docs/decisions/0024-model-driven-entity-selection.md`
- Spec: `docs/specs/entity-resolution-spec.md`

## Scenario A: Model resolves a top-score tie (entity selected)

Given two thermostats that tie on the shared token "thermostat"
And a model provider is configured
When the user prompts "show upstairs thermostat history"
Then `select_prompt_entity_ids` returns `entity_selection_requires_clarification`
  with both thermostats as `candidate_items`
And `_run_model_entity_selection` calls `planner.select_entity`
  with the two candidate entity IDs
And the model returns `status: entity_selected`, `entity_ids: [climate.upstairs_thermostat]`
And the selection is accepted with `source: model_entity_selection`
And the job proceeds to chart rendering without a clarification snapshot

## Scenario B: Model abstains; clarification is shown

Given two thermostats that tie on "thermostat"
And a model provider is configured
When the user prompts "show thermostat history"
And the model returns `status: clarification_needed`
Then `_run_model_entity_selection` returns `code: model_entity_selection_abstained`
And the orchestration falls through to the clarification path
And the job snapshot has `status: clarification_needed`
  with both thermostats as options

## Scenario C: No model configured; clarification is shown immediately

Given two thermostats that tie on "thermostat"
And no model provider is configured for the config entry
When the user prompts "show thermostat history"
Then `_run_model_entity_selection` returns `code: no_model_provider_for_entity_selection`
  without making any network call
And the job snapshot has `status: clarification_needed`

## Scenario D: Model returns entity outside candidate set; fail closed

Given two thermostats that tie on "thermostat"
And a model provider configured to return an entity ID not in the candidate set
When the user prompts "show thermostat history"
Then `_run_model_entity_selection` returns `code: model_entity_selection_out_of_allowlist`
And the job snapshot has `status: clarification_needed`

## Scenario E: Zero catalog matches; model picks from the full catalog

Given a catalog with `sensor.attic_temperature` and `binary_sensor.front_door`
And a model provider is configured
When the user prompts "show humidity"
Then `select_prompt_entity_ids` finds zero matches and returns
  `entity_selection_requires_clarification` with both entities as `candidate_items`
And `_run_model_entity_selection` calls `planner.select_entity`
  with both entity IDs as candidates
And the model selects `sensor.attic_temperature`
And the job proceeds to chart rendering without a clarification snapshot

## Proof Requirements

The evidence must include:

- A recent run timestamp.
- The exact pytest command and raw output (all new D2 tests passing).
- For each scenario: the input catalog, prompt, observed selection source, and
  final snapshot status.
- Confirmation that the existing D1 tests still pass unchanged (no regression).
- Full suite pass count.
