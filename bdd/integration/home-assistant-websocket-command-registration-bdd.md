# Home Assistant Integration: WebSocket Command Registration Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-websocket-command-registration-spec.md](../../docs/specs/home-assistant-websocket-command-registration-spec.md).

Evidence file:

- `bdd/integration/home-assistant-websocket-command-registration-evidence.md`

## Why This BDD Exists

This BDD pins down the first production Home Assistant WebSocket registration
surface. It proves the accepted `isolinear/v1/` command names are registered
through Home Assistant's WebSocket API while the implementation remains a
schema-first, config-entry-scoped scaffold that does not cross worker, model,
history, semantic-memory, token, or mutation boundaries.

## Scenarios

### Scenario A - happy path: command names are registered with Home Assistant

**Given** the accepted Isolinear WebSocket command set from ADR-0012
**When** the integration registers its WebSocket API
**Then** all five `isolinear/v1/` command names should be registered through
the WebSocket command boundary
**And** each registered handler should carry a command schema

### Scenario B - happy path: config entry setup stores registration metadata

**Given** an Isolinear config entry is set up
**When** `async_setup_entry` runs the WebSocket registration boundary
**Then** the config-entry scoped setup data should include the registration
result
**And** the command registration should be global and idempotent for the Home
Assistant runtime

### Scenario C - happy path: registered callbacks return scaffold snapshots

**Given** schema-valid card-facing WebSocket commands for a known config entry
**When** the registered callbacks handle each supported command type
**Then** each command should send a schema-valid `IntegrationJobSnapshot`
payload
**And** the payload should report that orchestration is not implemented yet

### Scenario D - failure path: malformed or unsafe commands fail closed

**Given** wrong-version, leaky, or mutating card-facing command payloads
**When** the registered command boundary validates them
**Then** each command should send a structured WebSocket error
**And** no scaffold snapshot should be returned

### Scenario E - failure path: missing config-entry scope fails closed

**Given** a schema-valid command referencing an unknown config entry
**When** the registered command boundary handles it
**Then** the command should be rejected before orchestration
**And** the error should identify the missing config-entry scope

### Scenario F - live path: Home Assistant routing accepts card envelopes

**Given** the dashboard card sends a Home Assistant WebSocket message with
transport `id`, command `type`, `version`, `config_entry_id`, and command
payload fields
**When** Home Assistant dispatches the registered Isolinear command
**Then** the Home Assistant routing schema should not reject the message as
having extra keys
**And** Isolinear should strip transport `id` before validating
`IntegrationWsCommand`
**And** unexpected card payload keys should still fail closed in Isolinear's
internal validator before orchestration

### Scenario G - scope path: auto config-entry resolution is deterministic

**Given** a registered command uses `config_entry_id: auto`
**When** exactly one Isolinear config entry exists in runtime setup data or the
Home Assistant config-entry registry
**Then** the command should resolve to that entry ID
**And** when zero or multiple Isolinear entries exist, the command should fail
closed before job state, history, planning, rendering, worker, or mutation
capable code runs

### Scenario H - observability path: registered command decisions are visible

**Given** registered commands are accepted or rejected at the WebSocket
boundary
**When** the command handler records backend observability
**Then** each decision should include command type, requested config-entry ID,
resolved config-entry ID, accepted state, message ID, decision code, and job ID
when present
**And** accepted snapshot decisions should include the result code, snapshot
status, and progress stage
**And** unexpected registered handler exceptions should return
`isolinear_websocket_command_exception` while recording the exception type
**And** prompts, tokens, endpoints, raw history, generated code, and generated
image bytes should not be recorded

### Scenario I - live regression: configured orchestration does not return the job-state scaffold

**Given** a Home Assistant config entry has completed the orchestration setup
boundary
**And** the approved entity catalog is empty or unavailable
**When** the dashboard card sends a registered `job/start` command
**Then** the command should route through the orchestration boundary
**And** the returned snapshot should fail at the approved-entity gate instead
of reporting `orchestration_not_implemented`
**And** registered follow-up commands for unknown jobs should fail at the
orchestration job boundary without returning job-state scaffold snapshots

### Scenario J - idempotence path: repeated setup does not duplicate commands

**Given** the Isolinear WebSocket command set has already been registered
**When** registration runs again in the same Home Assistant runtime
**Then** no duplicate command handlers should be registered
**And** the existing command registration metadata should be reused

### Scenario K - boundary path: registration without orchestration setup remains non-orchestrating

**Given** WebSocket registration has handled success and failure cases for
entries that have not completed orchestration setup
**When** the anchor aggregates observed side effects
**Then** no worker, model-provider, history, semantic-memory,
service/device/state mutation, token-generation, job-orchestration, or
dashboard-resource metadata write should occur
**And** WebSocket command registration should be reported as the allowed Home
Assistant registration side effect

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_websocket_command_registration.py` for each scenario.
