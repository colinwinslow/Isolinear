Feature: Dashboard card
  The dashboard card supports prompt entry, clarification, result display, and retry.

  Scenario: User submits prompt and sees progress
    Given the dashboard card is idle
    When the user submits "Compare upstairs and downstairs temperatures"
    Then the card should show a planning state
    And the card should disable duplicate submission for the active job

  Scenario: Dashboard loads the Isolinear custom card
    Given the Isolinear card module is registered as a dashboard resource
    When a dashboard card is configured as "custom:isolinear-card"
    Then the card should render prompt entry and idle job state
    And the prompt area should be the primary initial surface
    And the card should expose a graphical configuration surface

  Scenario: User answers clarification
    Given the system asks whether to average three upstairs temperature sensors
    When the user chooses "Use once"
    Then the card should send the clarification answer
    And the job should continue without saving semantic memory

  Scenario: User accepts threshold clarification once
    Given the system asks whether dishwasher running means "sensor.dishwasher_power > 5 W"
    When the user chooses "Use once"
    Then the job should continue with a shaded dishwasher-running overlay
    And the job should not save semantic memory

  Scenario: User views chart result
    Given a chart job completes successfully
    When the card displays the result
    Then the chart image should be visible
    And the chart should use most of the card's available content area
    And the card should show which entities and aliases were used
    And the card should show validation status
    And a compact prompt area should remain available at the bottom for a new request

  Scenario: User sees failure details
    Given a chart job fails during rendering
    When the card displays the failure
    Then the card should show the failure stage
    And the card should offer retry or prompt revision when appropriate

  Scenario: Card keeps orchestration inside the integration
    Given the card is configured with an Isolinear integration config entry
    When the user submits "Compare upstairs and downstairs temperatures"
    Then the card should send a versioned Isolinear request to the Home Assistant integration
    And the card should not call the worker, model provider, Home Assistant history API, or semantic-memory storage directly

  Scenario: Card auto-selects the only Isolinear config entry
    Given Home Assistant has exactly one configured Isolinear integration entry
    And the card is configured with config entry "auto"
    When the user submits "Show the family room temperature"
    Then the integration should resolve the command to the configured Isolinear entry
    And the card should not require the user to copy a Home Assistant config entry id

  Scenario: Card commands match the integration API schema
    Given the card is configured with an Isolinear integration config entry
    When the user submits a prompt, answers clarification, retries, retrieves a snapshot, and subscribes to job updates
    Then each message should match the versioned Isolinear WebSocket command schema
    And each message should stay under "isolinear/v1/"

  Scenario: Worker render requests use integration-owned authentication
    Given the integration has a configured worker endpoint and bearer token
    When it submits a render request to the worker
    Then the worker should accept only a schema-valid request with the expected bearer token and worker API version
    And worker auth material should be redacted from evidence

  Scenario: Worker render requests fail closed on bad auth or version
    Given a worker render request has missing auth, incorrect auth, an unsupported version, or leaked Home Assistant token material
    When the worker validates the transport envelope
    Then the worker should reject the request before rendering
    And the failure should include a structured code
