Feature: History normalization
  Home Assistant history is converted into chart-ready time series and intervals.

  Scenario: Numeric history converts string states to numbers
    Given Home Assistant history for "sensor.temperature" includes state "71.2"
    When the normalizer processes the history
    Then the output history series should include numeric value 71.2
    And the raw state should be preserved as "71.2"

  Scenario: Unknown and unavailable states become missing values
    Given Home Assistant history includes states "unknown" and "unavailable"
    When the normalizer processes the history
    Then those points should have null numeric values
    And the data quality should explain the missing value

  Scenario: Binary state history becomes active intervals
    Given "binary_sensor.dishwasher" changes from "off" to "on" and later to "off"
    When the normalizer extracts intervals where state is "on"
    Then the output should contain one derived interval with the correct start and end timestamps

  Scenario: Continuous sensor becomes threshold intervals after confirmation
    Given "sensor.dishwasher_power" has a confirmed running rule "value > 5 W"
    When the normalizer processes the history
    Then it should output intervals where dishwasher power is greater than 5 watts
