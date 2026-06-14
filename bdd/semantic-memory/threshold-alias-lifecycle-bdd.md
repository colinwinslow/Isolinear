# Threshold Alias Lifecycle BDD

Threshold confirmations can be used once, saved as deterministic semantic
aliases, and reused while their source entity remains available and allowlisted.

Evidence file:
`bdd/semantic-memory/threshold-alias-lifecycle-evidence.md`

Related artifacts:

- Source feature: `docs/bdd/semantic-memory.feature`
- Spec: `docs/specs/semantic-memory-spec.md`
- ADR: `docs/decisions/0009-semantic-memory-storage.md`
- Evals:
  - `evals/threshold_interval_use_once.py`
  - `evals/threshold_interval_use_and_remember.py`
  - `evals/threshold_interval_alias_reuse.py`

## Scenario: Do not save memory without confirmation

Given the planner has a confirmed threshold value for dishwasher running
When the user selects `Use once`
Then the chart job should continue
And no semantic alias should be saved
And deterministic validation should pass

## Scenario: Save threshold interval alias after clarification

Given the planner has a confirmed threshold value for dishwasher running
When the user selects `Use and remember as dishwasher running`
Then the chart job should continue
And the integration should save one semantic alias named `dishwasher running`
And the alias should use threshold interval `sensor.dishwasher_power > 5 W`
And deterministic validation should pass

## Scenario: Reuse saved threshold interval alias

Given a semantic alias named `dishwasher running` exists
When the user prompts `Mark when the dishwasher was running over the last day`
Then the planner should reuse the saved threshold without asking clarification
And the chart job should continue
And deterministic validation should pass

## Proof Requirements

The evidence must include:

- A recent run timestamp.
- The exact eval commands and raw eval outputs.
- The exact unit-test command and raw test output.
- The prompt, confirmation value, alias name, and saved alias fixtures.
- The observed planner statuses, saved alias collection, clarification result,
  plotted overlays, and validation statuses.
