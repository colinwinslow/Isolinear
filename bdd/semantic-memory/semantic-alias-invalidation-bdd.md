# Semantic Alias Invalidation BDD

Saved semantic aliases are reused only while their source entities remain
available and allowlisted.

Evidence file:
`bdd/semantic-memory/semantic-alias-invalidation-evidence.md`

Related artifacts:

- Source feature: `docs/bdd/semantic-memory.feature`
- Spec: `docs/specs/semantic-memory-spec.md`
- ADR: `docs/decisions/0009-semantic-memory-storage.md`
- Eval: `evals/semantic_alias_invalidation.py`

## Scenario: Invalid threshold alias references unavailable entity

Given a saved semantic alias named `dishwasher running`
And the alias references `sensor.retired_dishwasher_power`
And `sensor.retired_dishwasher_power` is not present in the current entity catalog
When the user prompts `Mark when the dishwasher was running over the last day`
Then the planner should not reuse the saved semantic alias
And the planner should return `clarification_needed`
And the invalid alias reason should be `entity_unavailable`
And no render request, render result, or chart validation should be produced from stale memory

## Scenario: Invalid threshold alias references non-allowlisted entity

Given a saved semantic alias named `dishwasher running`
And the alias references `sensor.dishwasher_power`
And `sensor.dishwasher_power` is present but no longer visible to the agent
When the user prompts `Mark when the dishwasher was running over the last day`
Then the planner should not reuse the saved semantic alias
And the planner should return `cannot_resolve`
And the invalid alias reason should be `entity_not_allowlisted`
And no render request, render result, or chart validation should be produced from stale memory

## Proof Requirements

The evidence must include:

- A recent run timestamp.
- The exact eval command and raw eval output.
- The exact targeted unit-test command and raw test output.
- The saved alias fixture for each scenario.
- The observed planner status and invalid alias reason for each scenario.
- Raw proof that `render_request`, `render_result`, and `validation_result` are `null`.
