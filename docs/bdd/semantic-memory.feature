Feature: Semantic memory
  User-confirmed meanings can be remembered and reused in later prompts.

  Scenario: Save aggregate alias after clarification
    Given the system asked whether to average three upstairs temperature sensors
    When the user selects "Use and remember as upstairs temperature"
    Then the integration should save a semantic alias named "upstairs temperature"
    And the alias should contain the three source entity IDs
    And the alias should use operation "mean"

  Scenario: Save threshold interval alias after clarification
    Given the system asked whether dishwasher running means "sensor.dishwasher_power > 5 W"
    When the user selects "Use and remember as dishwasher running"
    Then the integration should save a semantic alias named "dishwasher running"
    And the alias should use threshold interval "sensor.dishwasher_power > 5 W"
    And the chart job should continue

  Scenario: Reuse saved aggregate alias
    Given a semantic alias named "upstairs temperature" exists
    When the user prompts "Show upstairs temperature overnight"
    Then the planner context should include the semantic alias
    And the chart spec should use the semantic alias without asking the same clarification again

  Scenario: Reuse saved threshold interval alias
    Given a semantic alias named "dishwasher running" exists
    When the user prompts "Mark when the dishwasher was running over the last day"
    Then the planner context should include the semantic alias
    And the chart spec should use the saved threshold without asking the same clarification again
    And the chart job should continue

  Scenario Outline: Do not reuse invalid threshold interval aliases
    Given a semantic alias named "dishwasher running" references "<entity_id>"
    And that entity is "<entity_state>"
    When the user prompts "Mark when the dishwasher was running over the last day"
    Then the planner should not reuse the saved semantic alias
    And the planner should ask for clarification or return cannot_resolve
    And no chart should be rendered from stale memory

    Examples:
      | entity_id                       | entity_state          |
      | sensor.retired_dishwasher_power | unavailable           |
      | sensor.dishwasher_power         | no longer allowlisted |

  Scenario: Do not save memory without confirmation
    Given the model proposes a new semantic alias
    When the user selects "Use once"
    Then the integration should not save the alias for future prompts

  # Live wiring (Tranche 1: load -> match -> inject). See
  # bdd/semantic-memory/semantic-alias-live-wiring-bdd.md and
  # docs/specs/semantic-alias-live-wiring.md.

  Scenario: Saved alias injects an entity the prompt never named by name
    Given a valid enabled alias "AC running" maps to "climate.kitchen_ecobee"
    And "climate.kitchen_ecobee" is approved and visible to the agent
    When the user prompts "show kitchen temp and when the AC was running"
    Then the resolved entities should include "climate.kitchen_ecobee" from the matched alias
    And the resolution source should be "semantic_alias"
    And no clarification should be raised for the aliased concept

  Scenario: Disabled or invalid aliases are not injected
    Given an alias for "climate.kitchen_ecobee" that is disabled or references a missing or hidden entity
    When the user prompts "show me when the AC was running"
    Then the alias should not be injected into the resolved entities
    And the prompt should resolve as if the alias were absent

  Scenario: A prompt with no alias token overlap is unaffected
    Given a valid enabled alias "dishwasher running"
    When the user prompts "show kitchen temperature today"
    Then no semantic alias should match
    And entity selection should resolve exactly as it would with no aliases present
