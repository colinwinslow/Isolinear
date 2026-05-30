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
