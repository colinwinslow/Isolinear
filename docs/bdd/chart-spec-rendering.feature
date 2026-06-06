Feature: Chart spec rendering
  The trusted renderer turns validated chart specs and normalized data into chart images.

  Scenario: Render a multi-series time chart
    Given a valid chart spec with two numeric time-series
    And normalized history exists for both series
    When the worker renders in safe mode
    Then it should create a PNG image
    And the render metadata should list both plotted series
    And the render metadata should include the requested time range

  Scenario: Reject unsupported safe-mode chart
    Given a valid chart spec that requires an unsupported chart primitive
    When the worker renders in safe mode
    Then the worker should return an "unsupported_chart_spec" error
    And the worker should not attempt codegen
    And the dashboard card should show a useful explanation

  Scenario: Render shaded intervals
    Given a valid chart spec with a numeric series and a state interval overlay
    And derived intervals exist for the overlay
    When the worker renders in safe mode
    Then the render metadata should list the overlay as plotted
