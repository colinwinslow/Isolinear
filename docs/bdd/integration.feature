Feature: Home Assistant integration anchors
  The integration package should provide production Home Assistant integration
  surfaces without bypassing schema, worker, allowlist, or read-only safety
  boundaries.

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

  Scenario: Config flow is visible to Home Assistant
    Given the integration scaffold package exists
    When the config-flow anchor inspects custom_components/isolinear
    Then the manifest should enable config_flow
    And the package should expose config-flow and options-flow classes

  Scenario: User config flow creates validated local-first data
    Given a user submits model and worker endpoint settings through the config flow
    When the config-flow validator normalizes the user input
    Then the result should be accepted
    And blank optional model fields should become null
    And the result should contain only validated config-entry data

  Scenario: Options flow persists safe options
    Given an existing config entry has valid local-first config data
    When the options-flow validator receives render-mode, repair-attempt, and entity-allowlist input
    Then the result should be accepted
    And user-facing allowlist text should become a deterministic entity ID list

  Scenario: Invalid setup flow input fails closed
    Given config-flow or options-flow input contains invalid or secret-bearing material
    When the setup flow validator checks the input
    Then the input should be rejected before persistence
    And no worker, model-provider, history, semantic-memory, mutation, token-generation, or dashboard-resource registration call should occur
