Feature: Prompt to chart
  The user can submit a natural-language prompt and receive a chart based on approved Home Assistant entity history.

  Background:
    Given the following entities are visible to the agent:
      | entity_id                       | name                    | device_class | unit | area        | labels      |
      | sensor.upstairs_temperature     | Upstairs Temperature    | temperature  | °F   | Hallway     | upstairs    |
      | sensor.downstairs_temperature   | Downstairs Temperature  | temperature  | °F   | Living Room | downstairs  |
    And normalized history exists for the last 24 hours for those entities

  Scenario: Compare two temperature entities over the last 24 hours
    When the user prompts "Compare upstairs and downstairs temperatures over the last 24 hours"
    Then the system should create a chart spec with chart type "time_series"
    And the chart spec should include "sensor.upstairs_temperature" as a series
    And the chart spec should include "sensor.downstairs_temperature" as a series
    And the chart spec should use a 24 hour relative time range
    And the worker should render a chart image
    And the validation result should pass
