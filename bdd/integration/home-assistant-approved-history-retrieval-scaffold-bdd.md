# Home Assistant Integration: Approved History Retrieval Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-approved-history-retrieval-scaffold-spec.md](../../docs/specs/home-assistant-approved-history-retrieval-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-approved-history-retrieval-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the first integration-owned approved history retrieval
surface. It proves the integration can read and normalize history only for
entities visible in the approved catalog while the broader worker, model,
memory, artifact, token, rendering, job-orchestration, and mutation boundaries
remain untouched.

## Scenarios

### Scenario A - happy path: approved entities produce schema-valid history

**Given** a config entry with approved catalog items and fake Home Assistant
history that also contains non-approved entities
**When** the approved history retrieval scaffold retrieves selected approved
entities
**Then** only the selected approved entities should be returned
**And** every returned series should validate against `HistorySeries`
**And** no non-approved history should be returned

### Scenario B - setup path: setup stores a config-entry-scoped history store

**Given** an Isolinear config entry with an approved entity catalog
**When** `async_setup_entry` runs
**Then** the config-entry data should include an approved history retrieval
store
**And** the setup result should identify the targeted config entry

### Scenario C - isolation path: config entries receive separate history

**Given** two Isolinear config entries with different approved catalogs
**When** each config entry retrieves approved history
**Then** each history store should contain only that entry's requested
approved entities
**And** neither store should expose the other entry's history

### Scenario D - failure path: non-catalog entities fail closed

**Given** a config entry whose approved catalog does not include a requested
entity
**When** the approved history retrieval scaffold handles the request
**Then** the request should fail closed with a structured catalog error
**And** Home Assistant history should not be read for that request
**And** no history series should be stored for that entry

### Scenario E - regression path: rejected retrieval clears existing history

**Given** a config entry whose existing history store was populated by a
previous approved request
**And** a later request asks for an entity outside the approved catalog
**When** the approved history retrieval scaffold handles the later request
**Then** the request should fail closed with a structured catalog error
**And** the previous history series should be removed from the entry store

### Scenario F - failure path: malformed raw history fails closed

**Given** a config entry with an approved entity
**And** fake Home Assistant history for that entity has malformed raw records
**When** the approved history retrieval scaffold normalizes the history
**Then** the request should fail closed with a structured history-record error
**And** no history series should be stored for that entry

### Scenario G - schema path: malformed history series are rejected before storage

**Given** a malformed normalized history series that does not satisfy
`HistorySeries`
**When** the history store attempts to persist it
**Then** the series should be rejected with a structured schema error
**And** the history store should remain unchanged

### Scenario H - boundary path: history retrieval remains non-orchestrating

**Given** approved history retrieval has handled success and failure cases
**When** the anchor aggregates observed side effects
**Then** no worker, model-provider, semantic-memory persistence,
service/device/state mutation, token-generation, chart artifact write, chart
rendering, WebSocket command registration, dashboard-resource metadata write,
or real job orchestration should occur
**And** approved catalog reads, approved fake history reads, and in-memory
history-store writes should be reported as the allowed side effects

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_approved_history_retrieval_scaffold.py` for each
scenario.
