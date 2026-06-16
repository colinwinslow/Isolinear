# Home Assistant Integration: Approved Entity Catalog Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-approved-entity-catalog-scaffold-spec.md](../../docs/specs/home-assistant-approved-entity-catalog-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-approved-entity-catalog-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the first integration-owned approved entity catalog surface.
It proves the integration can expose schema-valid metadata for only allowlisted
entities while the broader planning, history, worker, model, memory, artifact,
token, and mutation boundaries remain untouched.

## Scenarios

### Scenario A - happy path: allowlisted metadata becomes schema-valid catalog items

**Given** a config entry with two allowlisted entities and fake Home Assistant
metadata containing additional non-allowlisted entities
**When** the approved entity catalog scaffold builds the catalog
**Then** only the allowlisted entities should be returned
**And** every returned item should validate against `EntityCatalogItem`
**And** every returned item should be visible to the agent

### Scenario B - setup path: setup stores a config-entry-scoped catalog

**Given** an Isolinear config entry with an entity allowlist
**When** `async_setup_entry` runs
**Then** the config-entry data should include an approved entity catalog store
**And** the setup result should identify the targeted config entry

### Scenario C - isolation path: config entries receive separate catalogs

**Given** two Isolinear config entries with different allowlists
**When** each config entry builds its approved entity catalog
**Then** each catalog should contain only that entry's allowlisted entities
**And** neither store should expose the other entry's entities

### Scenario C2 - regression path: options update rebuilds runtime catalog

**Given** an Isolinear config entry was set up with an empty allowlist
**And** Home Assistant later updates options with two approved entities
**When** the registered options update listener runs
**Then** the config-entry-scoped approved catalog should contain the two new
entity IDs
**And** the allowlist-derived history and orchestration setup metadata should
reflect the same approved entity IDs before the next dashboard command

### Scenario D - failure path: unknown allowlisted entities fail closed

**Given** a config entry whose allowlist references an entity missing from fake
Home Assistant metadata and state
**When** the approved entity catalog scaffold builds the catalog
**Then** the build should fail closed with a structured missing-entity error
**And** no catalog items should be stored for that entry

### Scenario E - regression path: rejected rebuild clears existing catalog

**Given** a config entry whose existing catalog was built from a previous
allowlist
**And** the config entry's new allowlist references an entity missing from fake
Home Assistant metadata and state
**When** the approved entity catalog scaffold rebuilds the catalog
**Then** the build should fail closed with a structured missing-entity error
**And** the previous catalog items should be removed from the entry store

### Scenario F - failure path: malformed allowlists fail closed

**Given** a config entry whose entity allowlist contains malformed non-string
items
**When** the approved entity catalog scaffold builds the catalog
**Then** the build should fail closed with a structured invalid-allowlist error
**And** no catalog items should be stored for that entry

### Scenario G - schema path: malformed catalog items are rejected before storage

**Given** a malformed normalized catalog item that does not satisfy
`EntityCatalogItem`
**When** the catalog store attempts to persist it
**Then** the item should be rejected with a structured schema error
**And** the catalog store should remain unchanged

### Scenario H - boundary path: catalog construction remains non-orchestrating

**Given** catalog construction has handled success and failure cases
**When** the anchor aggregates observed side effects
**Then** no worker, model-provider, Home Assistant history, semantic-memory
persistence, service/device/state mutation, token-generation, chart artifact
write, WebSocket command registration, dashboard-resource metadata write, or
real job orchestration should occur
**And** approved metadata reads and in-memory catalog writes should be reported
as the allowed side effects

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_approved_entity_catalog_scaffold.py` for each scenario.
