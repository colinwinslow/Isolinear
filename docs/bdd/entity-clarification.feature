Feature: Entity clarification
  The system asks a clarifying question when multiple plausible entity mappings exist.

  Scenario: Multiple upstairs temperature sensors are proposed as an average
    Given the following entities are visible to the agent:
      | entity_id                              | name                         | device_class | unit | labels    |
      | sensor.upstairs_hall_temperature       | Upstairs Hall Temperature    | temperature  | °F   | upstairs  |
      | sensor.primary_bedroom_temperature     | Primary Bedroom Temperature  | temperature  | °F   | upstairs  |
      | sensor.family_room_temperature         | Family Room Temperature      | temperature  | °F   | upstairs  |
      | sensor.downstairs_temperature          | Downstairs Temperature       | temperature  | °F   | downstairs|
    When the user prompts "Compare upstairs temperature and downstairs temperature"
    Then the system should ask a clarifying question
    And the question should propose averaging the three upstairs temperature sensors
    And the question should offer to use the answer once or remember it

  Scenario: Multiple running indicators require a user choice
    Given the following entities are visible to the agent:
      | entity_id                    | name               | domain        | device_class | unit |
      | binary_sensor.air_conditioning| Air Conditioning   | binary_sensor |              |      |
      | sensor.hvac_current          | HVAC Current       | sensor        | current      | A    |
      | climate.main_floor           | Main Floor Climate | climate       |              |      |
    When the user prompts "Mark when the air conditioning was running"
    Then the system should ask which entity or rule represents air conditioning running

  Scenario: Continuous power sensor proposes a threshold confirmation
    Given "sensor.dishwasher_power" is visible to the agent
    When the user prompts "Mark when the dishwasher was running over the last day"
    Then the system should ask whether dishwasher running means "sensor.dishwasher_power > 5 W"
    And the question should offer to use the answer once or remember it

  # ADR-0024 D2 — model-driven entity selection on residual ambiguity (accepted 2026-06-22)

  Scenario: Model resolves a top-score tie without asking the user (D2)
    Given the following entities are visible to the agent:
      | entity_id                        | name                   |
      | climate.upstairs_thermostat      | Upstairs Thermostat    |
      | climate.downstairs_thermostat    | Downstairs Thermostat  |
    And a model provider is configured
    When the user prompts "show upstairs thermostat history"
    Then the deterministic fast-path ties on "thermostat"
    And the model selects "climate.upstairs_thermostat" from the tied candidates
    And the job proceeds to chart rendering without a clarification snapshot

  Scenario: Model abstains on genuine ambiguity; clarification is shown (D2)
    Given the following entities are visible to the agent:
      | entity_id                        | name                   |
      | climate.upstairs_thermostat      | Upstairs Thermostat    |
      | climate.downstairs_thermostat    | Downstairs Thermostat  |
    And a model provider is configured
    When the user prompts "show thermostat history"
    Then the deterministic fast-path ties on "thermostat"
    And the model returns clarification_needed
    And the user sees a clarification snapshot offering both thermostats

  Scenario: No model configured; clarification is shown immediately (D2 skipped)
    Given the following entities are visible to the agent:
      | entity_id                        | name                   |
      | climate.upstairs_thermostat      | Upstairs Thermostat    |
      | climate.downstairs_thermostat    | Downstairs Thermostat  |
    And no model provider is configured
    When the user prompts "show thermostat history"
    Then the user sees a clarification snapshot offering both thermostats without a model call

  Scenario: Model returns an entity outside the candidate set; clarification is shown (D2)
    Given the following entities are visible to the agent:
      | entity_id                        | name                   |
      | climate.upstairs_thermostat      | Upstairs Thermostat    |
      | climate.downstairs_thermostat    | Downstairs Thermostat  |
    And a model provider is configured
    When the user prompts "show thermostat history"
    And the model returns an entity_id not in the candidate set
    Then the model's choice is rejected (allowlist enforced)
    And the user sees a clarification snapshot offering the tied candidates

  Scenario: Zero catalog matches; model picks from the full catalog (D2)
    Given the following entities are visible to the agent:
      | entity_id                              | name                       |
      | sensor.attic_temperature               | Attic Temperature          |
      | binary_sensor.front_door               | Front Door                 |
    And a model provider is configured
    When the user prompts "show humidity"
    Then the deterministic fast-path finds zero matches
    And the model selects "sensor.attic_temperature" from the full catalog
    And the job proceeds to chart rendering without a clarification snapshot
