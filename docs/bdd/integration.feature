Feature: Home Assistant integration scaffold
  The integration package should provide the first production Home Assistant
  custom integration surface without bypassing schema, worker, allowlist, or
  read-only safety boundaries.

  Scenario: Scaffold package is visible to Home Assistant
    Given the repository has entered the production integration scaffold packet
    When the integration scaffold verifier inspects custom_components/isolinear
    Then the manifest should declare domain "isolinear"
    And the package should expose stable domain constants
    And the package should expose supported isolinear/v1 command names

  Scenario: Local-first configuration shape is inspectable
    Given the integration owns model endpoint, worker endpoint, render mode, repair attempt, and entity allowlist configuration
    When the scaffold validates the default configuration and options shape
    Then the shape should be accepted
    And malformed render modes should be rejected before setup work continues
    And secret-bearing configuration should be rejected before setup work continues

  Scenario: Known card commands are accepted as stubs
    Given schema-valid card-facing WebSocket commands under isolinear/v1
    When the scaffold command boundary handles each supported command type
    Then each command should be accepted
    And each accepted result should include a schema-valid IntegrationJobSnapshot
    And the result should report that orchestration is not implemented yet

  Scenario: Unknown or unsupported commands fail closed
    Given a card-facing command with an unknown command name or unsupported version
    When the scaffold command boundary validates it
    Then the command should be rejected before orchestration
    And the rejection should use a structured failure code

  Scenario: Leaky or mutating card payloads fail closed
    Given a card-facing command containing forbidden boundary or service mutation material
    When the scaffold command boundary validates it
    Then the command should be rejected before orchestration
    And no worker, model-provider, history, semantic-memory, or mutation call should occur
