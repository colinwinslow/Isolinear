# Home Assistant Integration: Dashboard Resource Registration Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-dashboard-resource-registration-spec.md](../../docs/specs/home-assistant-dashboard-resource-registration-spec.md).

Evidence file:

- `bdd/integration/home-assistant-dashboard-resource-registration-evidence.md`

## Why This BDD Exists

This BDD pins down the first production link between the Home Assistant
integration and the existing Isolinear dashboard card bundle. It proves the
integration can serve and register the card resource without crossing worker,
model, history, semantic-memory, token, or job-orchestration boundaries.

## Scenarios

### Scenario A - happy path: card bundle is served from an integration static path

**Given** the packaged card bundle exists at
`custom_components/isolinear/frontend/dist/isolinear-card.js`
**When** the dashboard resource anchor registers static assets
**Then** the bundle directory should be registered through the async static-path
API
**And** the dashboard resource URL should be the current package-versioned
`/api/isolinear/static/isolinear-card.js?v=<version>` URL

### Scenario B - happy path: config entry setup registers resource metadata

**Given** an Isolinear config entry is set up
**When** `async_setup_entry` runs the dashboard resource registration boundary
**Then** the config-entry scoped setup data should include the registration
result
**And** the Lovelace resource collection should include one module resource for
the Isolinear card URL

### Scenario C - idempotence path: repeated setup does not duplicate metadata

**Given** the Isolinear card resource has already been registered
**When** dashboard resource registration runs again for the same config entry
**Then** the existing resource metadata should be reused
**And** no duplicate resource entry should be created

### Scenario D - idempotence path: pre-existing matching metadata is reused

**Given** Home Assistant already has a module resource for the Isolinear card
URL
**When** dashboard resource registration runs
**Then** the pre-existing resource metadata should be accepted
**And** no create operation should be issued

### Scenario E - update path: stale Isolinear metadata is updated in place

**Given** Home Assistant already has a module resource for the legacy
unversioned Isolinear card URL
**When** dashboard resource registration runs
**Then** the existing resource metadata should be updated to the current
package-versioned Isolinear card URL
**And** no duplicate resource entry should be created

### Scenario F - failure path: missing bundle fails closed

**Given** the Isolinear card bundle path is missing
**When** dashboard resource registration validates the artifact
**Then** registration should be rejected before dashboard resource metadata is
created
**And** the rejection should include a structured failure code

### Scenario G - boundary path: registration remains non-orchestrating

**Given** dashboard resource registration has handled success and failure cases
**When** the anchor aggregates observed side effects
**Then** no worker, model-provider, history, semantic-memory,
service/device/state mutation, token-generation, job-orchestration, or extra
WebSocket command handling call should occur
**And** dashboard resource metadata creation, reuse, or stale-resource update
should be reported as the allowed Home Assistant metadata write

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_dashboard_resource_registration.py` for each scenario.
