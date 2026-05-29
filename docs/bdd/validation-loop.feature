Feature: Validation loop
  The system validates chart plans, rendered outputs, and optional visual matches.

  Scenario: Plan validation rejects non-allowlisted entity
    Given a chart spec references "sensor.hidden_temperature"
    And that entity is not visible to the agent
    When plan validation runs
    Then validation should fail
    And rendering should not start

  Scenario: Render metadata validation confirms expected series
    Given the chart spec expects series "upstairs_temperature" and "downstairs_temperature"
    And the render metadata lists both series as plotted
    When render metadata validation runs
    Then the validation check should pass

  Scenario: Missing overlay fails validation
    Given the chart spec expects overlay "dishwasher_running"
    And the render metadata contains no plotted overlays
    When render metadata validation runs
    Then validation should fail with a missing overlay issue

  Scenario: Visual validation is advisory
    Given deterministic validation fails
    And visual validation says the chart appears correct
    When the final validation result is computed
    Then the final result should remain failed
    And the visual validation should be recorded as advisory
