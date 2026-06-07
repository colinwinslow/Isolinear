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

  Scenario: Render a state interval timeline
    Given a valid timeline chart spec with one binary-state track
    And derived intervals exist for that track
    When the worker renders in safe mode
    Then it should create a PNG image
    And the render metadata should list the timeline track as plotted
    And the worker should not attempt codegen

  Scenario: Render an aggregate bar chart
    Given a valid bar chart spec with one aggregate numeric series
    And normalized numeric history exists for every aggregate source entity
    When the worker renders in safe mode
    Then it should create a PNG image
    And the render metadata should list the aggregate series as plotted
    And the worker should not attempt codegen

  Scenario: Render a calendar hour heatmap
    Given a valid heatmap chart spec with one numeric entity series
    And normalized numeric history exists for that entity
    When the worker renders in safe mode
    Then it should create a PNG image
    And the render metadata should list the heatmap series as plotted
    And the worker should not attempt codegen

  Scenario: Render event markers over a time-series chart
    Given a valid time-series chart spec with a marker overlay
    And normalized history exists for the numeric series and marker source
    When the worker renders in safe mode
    Then it should create a PNG image
    And the render metadata should list the marker overlay as plotted
    And the worker should not attempt codegen

  Scenario: Render a distribution histogram
    Given a valid histogram chart spec with one numeric entity series
    And normalized numeric history exists for that entity
    When the worker renders in safe mode
    Then it should create a PNG image
    And the render metadata should list the histogram series as plotted
    And the worker should not attempt codegen

  Scenario: Render a scatter/correlation chart
    Given a valid scatter chart spec with two numeric entity series
    And normalized numeric history exists with paired timestamps for both entities
    When the worker renders in safe mode
    Then it should create a PNG image
    And the render metadata should list both scatter series as plotted
    And the worker should not attempt codegen
