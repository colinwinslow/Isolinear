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

  Scenario: Do not save memory without confirmation
    Given the model proposes a new semantic alias
    When the user selects "Use once"
    Then the integration should not save the alias for future prompts
