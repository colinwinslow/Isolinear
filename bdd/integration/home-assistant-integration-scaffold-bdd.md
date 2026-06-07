# Home Assistant Integration: Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-integration-scaffold-spec.md](../../docs/specs/home-assistant-integration-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-integration-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the first real Home Assistant integration surface. It proves
that the repository now has an inspectable `custom_components/isolinear`
package without allowing the scaffold to bypass the existing schema,
allowlist, worker, and read-only safety boundaries.

## Scenarios

### Scenario A - happy path: scaffold package is visible to Home Assistant

**Given** the repository has entered the production integration scaffold packet
**When** the integration scaffold verifier inspects `custom_components/isolinear`
**Then** the manifest should declare domain `isolinear`
**And** the package should expose stable domain constants and supported
`isolinear/v1/` command names

### Scenario B - happy path: local-first configuration shape is inspectable

**Given** the integration owns model, worker, render-mode, repair-attempt, and
entity-allowlist configuration
**When** the scaffold validates the default configuration/options shape
**Then** the shape should be accepted
**And** malformed render modes or secret-bearing configuration should be
rejected before setup work continues

### Scenario C - happy path: known card commands are accepted as stubs

**Given** schema-valid card-facing WebSocket commands under `isolinear/v1/`
**When** the scaffold command boundary handles each supported command type
**Then** each command should be accepted
**And** each accepted result should include a schema-valid `IntegrationJobSnapshot`
**And** the result should report that orchestration is not implemented yet

### Scenario D - failure path: unknown or unsupported commands fail closed

**Given** a card-facing command with an unknown command name or unsupported
version
**When** the scaffold command boundary validates it
**Then** the command should be rejected before orchestration
**And** the rejection should use a structured failure code

### Scenario E - boundary path: leaky or mutating card payloads fail closed

**Given** a card-facing command containing worker credentials, raw history,
semantic-memory records, Home Assistant tokens, or service-mutation material
**When** the scaffold command boundary validates it
**Then** the command should be rejected before orchestration
**And** the evidence should show no worker, model-provider, history,
semantic-memory, or mutation calls

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_integration_scaffold.py` for each scenario.
