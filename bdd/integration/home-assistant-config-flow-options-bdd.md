# Home Assistant Integration: Config Flow and Options Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-config-flow-options-spec.md](../../docs/specs/home-assistant-config-flow-options-spec.md).

Evidence file:

- `bdd/integration/home-assistant-config-flow-options-evidence.md`

## Why This BDD Exists

This BDD pins down the first user setup surface for the production Home
Assistant integration. It proves a config flow and options flow can create
validated local-first configuration without crossing worker, model, history,
semantic-memory, or mutation boundaries.

## Scenarios

### Scenario A - happy path: config flow is visible to Home Assistant

**Given** the integration scaffold package exists
**When** the config-flow anchor inspects `custom_components/isolinear`
**Then** the manifest should set `config_flow` to `true`
**And** `custom_components/isolinear/config_flow.py` should expose a config
flow class and an options flow class

### Scenario B - happy path: user config flow creates validated local-first data

**Given** a user submits model and worker endpoint settings through the config
flow
**When** the config-flow validator normalizes the user input
**Then** the result should be accepted
**And** blank optional model fields should become `null`
**And** the result should contain only the validated config-entry data shape

### Scenario C - happy path: options flow persists safe options

**Given** an existing config entry has valid local-first config data
**When** the options-flow validator receives render-mode, repair-attempt, and
entity-allowlist input
**Then** the result should be accepted
**And** the user-facing allowlist text should become a deterministic entity ID
list

### Scenario C2 - regression path: live allowlist input variants are accepted

**Given** a user reports allowlisting `sensor.family_room_sensor_temperature`
through a HACS-installed integration
**When** the options-flow validator receives the value as plain entity text or
JSON-style pasted list text
**Then** both inputs should be accepted
**And** both inputs should normalize to the same deterministic entity ID list
**And** the options flow should retain the Home Assistant config entry passed
to `async_get_options_flow`

### Scenario C3 - regression path: missing stored setup data does not block options edits

**Given** an existing config entry reaches the options flow with missing stored
setup data
**When** the user submits `sensor.family_room_sensor_temperature` as an
allowlist edit
**Then** the options flow should accept the edit
**And** validation should use safe local-first defaults instead of returning a
base-level `must_be_object` error

### Scenario D - failure path: invalid config flow input fails closed

**Given** config-flow input contains a credential-bearing endpoint or
secret-like value
**When** the config-flow validator checks the input
**Then** the input should be rejected before config-entry creation
**And** the rejection should include structured field errors

### Scenario E - failure path: invalid options flow input fails closed

**Given** options-flow input contains an unsupported render mode, duplicate
entity ID, malformed entity ID, or forbidden secret material
**When** the options-flow validator checks the input
**Then** the input should be rejected before options persistence
**And** the rejection should include structured field errors

### Scenario F - boundary path: setup flow remains non-orchestrating

**Given** config-flow and options-flow inputs have been handled
**When** the anchor aggregates observed side effects
**Then** no worker, model-provider, history, semantic-memory, mutation,
token-generation, or dashboard-resource registration call should occur

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_config_flow_options.py` for each scenario.
