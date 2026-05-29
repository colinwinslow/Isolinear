Feature: Entity allowlist
  The model only sees and uses entities the user has explicitly approved.

  Scenario: Hidden entity is not sent to planner
    Given "sensor.private_office_temperature" exists in Home Assistant
    And "sensor.private_office_temperature" is not visible to the agent
    When the user prompts "Show office temperature"
    Then the planner context should not include "sensor.private_office_temperature"
    And the system should not use "sensor.private_office_temperature" in the chart spec

  Scenario: User sees which entities are visible
    Given the integration options page is open
    When the user edits visible entities
    Then the user should be able to select multiple entities for agent visibility
    And the saved allowlist should be used in subsequent prompt planning
