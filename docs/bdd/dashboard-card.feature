Feature: Dashboard card
  The dashboard card supports prompt entry, clarification, result display, and retry.

  Scenario: User submits prompt and sees progress
    Given the dashboard card is idle
    When the user submits "Compare upstairs and downstairs temperatures"
    Then the card should show a planning state
    And the card should disable duplicate submission for the active job

  Scenario: User answers clarification
    Given the system asks whether to average three upstairs temperature sensors
    When the user chooses "Use once"
    Then the card should send the clarification answer
    And the job should continue without saving semantic memory

  Scenario: User views chart result
    Given a chart job completes successfully
    When the card displays the result
    Then the chart image should be visible
    And the card should show which entities and aliases were used
    And the card should show validation status

  Scenario: User sees failure details
    Given a chart job fails during rendering
    When the card displays the failure
    Then the card should show the failure stage
    And the card should offer retry or prompt revision when appropriate
