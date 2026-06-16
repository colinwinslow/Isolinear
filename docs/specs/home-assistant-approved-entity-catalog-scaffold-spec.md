---
status: draft
date: 2026-06-08
depends-on-adrs:
  - 0001
  - 0003
  - 0005
  - 0006
  - 0008
---

# Home Assistant Integration: Approved Entity Catalog Scaffold Anchor

## Status

Draft. Defines the first production Home Assistant integration-owned approved
entity catalog surface per ADR-0001, ADR-0003, ADR-0005, ADR-0006, and
ADR-0008.

## Related Docs

- [bdd/integration/home-assistant-approved-entity-catalog-scaffold-bdd.md](../../bdd/integration/home-assistant-approved-entity-catalog-scaffold-bdd.md) - observable behavior
- [docs/specs/entity-resolution-spec.md](entity-resolution-spec.md) - entity resolution inputs
- [docs/specs/integration-spec.md](integration-spec.md) - integration responsibilities
- [docs/specs/home-assistant-config-flow-options-spec.md](home-assistant-config-flow-options-spec.md) - allowlist configuration
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The integration now has config-entry setup, options-driven entity allowlist
configuration, dashboard resource registration, registered WebSocket commands,
and config-entry-scoped job state. The next production anchor needs the first
inspectable approved entity catalog surface so later planning packets can give
the model only the Home Assistant metadata the user approved.

This packet must remain non-orchestrating. It may read current entity/state
metadata for allowlisted entities and keep a config-entry-scoped in-memory
catalog, but it must not fetch Home Assistant history, call the model provider,
call the worker, persist semantic memory, generate worker tokens, write chart
artifacts, or mutate Home Assistant state/services.

## Behavior Contract

The integration must add `custom_components/isolinear/entity_catalog.py` with a
small, inspectable catalog boundary.

The catalog boundary must:

- Build one config-entry-scoped in-memory catalog store under
  `hass.data["isolinear"][entry_id]`.
- Read the configured `entity_allowlist` from config-entry options.
- Produce only allowlisted `EntityCatalogItem` records.
- Populate each item from fake Home Assistant entity/state metadata in tests
  and from the Home Assistant state machine shape when present.
- Set `visible_to_agent` to `true` for every returned item.
- Validate every `EntityCatalogItem` against
  `docs/schemas/entity-catalog-item.schema.json` before storing or returning
  it.
- Store the catalog atomically only after every allowlisted item validates.
- Clear the config-entry catalog store on rejected rebuilds so stale
  previously approved metadata cannot remain visible after an allowlist or
  metadata failure.
- Preserve config-entry isolation when two entries have different allowlists.
- Fail closed with structured errors when allowlist data is malformed,
  allowlisted entities are missing from metadata/state sources, or normalized
  catalog items do not satisfy schema.
- Register a Home Assistant config-entry options update listener during setup
  when the runtime provides that API. After an allowlist edit, the listener must
  refresh the config-entry-scoped approved catalog plus the allowlist-derived
  history and orchestration setup metadata before the next dashboard command
  reads the catalog.
- Treat Home Assistant config-entry `data` and `options` as mapping-like
  values, not only plain `dict` instances, so read-only mapping options from a
  saved entity selector still build the runtime approved catalog.

Allowed side effects for this packet are limited to:

- Reading approved entity/state metadata.
- In-memory config-entry-scoped catalog store creation/update.
- Config-entry-scoped setup-result bookkeeping in `hass.data["isolinear"]`.

The catalog boundary must report that no worker, model-provider, Home Assistant
history, semantic-memory persistence, Home Assistant service/device/state
mutation, token-generation, chart artifact write, WebSocket command
registration, dashboard resource metadata write, or real job orchestration
occurred.

## Anchor Artifact

The anchor artifact is the inspectable
`custom_components/isolinear/entity_catalog.py` module plus
`src/Isolinear/entity_catalog_scaffold_anchor.py`, which verifies allowlist
filtering, schema-valid catalog items, setup-entry storage, missing entity
rejection, malformed catalog rejection before storage, config-entry isolation,
and side-effect boundaries against fake Home Assistant objects.

## Implementation Order

1. Create this spec and its paired BDD/evidence scaffold.
2. Add failing unit tests for allowlist filtering, schema validation,
   setup-entry storage, missing entity rejection, malformed catalog rejection,
   per-config-entry isolation, and side-effect boundaries.
3. Add `custom_components/isolinear/entity_catalog.py` and call it from
   `async_setup_entry`.
4. Add the Python verifier anchor and focused executable eval.
5. Verify the real files on disk.

## Proof Requirements

1. Unit tests in
   `tests/test_approved_entity_catalog_scaffold_anchor.py` are green.
2. Existing integration scaffold, config-flow/options, dashboard-resource,
   WebSocket registration, and job-state tests remain green.
3. `evals/home_assistant_approved_entity_catalog_scaffold.py` emits raw `CASE`
   evidence for the BDD scenarios.
4. Evidence confirms only allowlisted entities are returned even when metadata
   contains additional entities.
5. Evidence confirms every returned item validates against
   `EntityCatalogItem` before storage/return.
6. Evidence confirms `async_setup_entry` stores a config-entry-scoped catalog
   store and setup result.
7. Evidence confirms an options update from an empty allowlist to two approved
   entities rebuilds the runtime catalog, refreshes the allowlist-derived
   orchestration setup metadata, and validates the new catalog items.
8. Evidence confirms Home Assistant read-only mapping options build the same
   runtime catalog as plain dict options instead of falling back to an empty
   allowlist.
9. Evidence confirms two config entries receive isolated catalogs based on
   their own allowlists.
10. Evidence confirms unknown allowlisted entities fail closed before catalog
   storage and clear any previous catalog for the entry.
11. Evidence confirms malformed allowlist inputs fail closed without raising an
   exception.
12. Evidence confirms malformed normalized catalog items fail closed before
   storage.
13. Evidence confirms no worker, model provider, Home Assistant history,
    semantic-memory persistence, Home Assistant service/device/state mutation,
    token-generation, chart artifact write, WebSocket command registration,
    dashboard-resource metadata write, or real job orchestration occurs.
14. Real artifacts are verified on disk: production catalog module,
    integration setup wiring, BDD, eval outline, tests, eval, and evidence.

## Non-Goals

- Home Assistant history retrieval or history normalization.
- Model-provider calls or prompt construction.
- Worker HTTP calls, worker token generation, or artifact storage.
- Semantic-memory persistence, migration, or alias repair UI.
- Production entity registry/device registry/area registry adapters beyond the
  scaffold-compatible metadata shape.
- Entity selection UI or allowlist editing UI beyond existing options flow.
- Job orchestration, subscriptions, retries, progress streaming, or rendering.
- Creating, editing, or deleting Home Assistant dashboards, devices, services,
  automations, scenes, helpers, or state.

## References

- [docs/decisions/0001-home-assistant-integration-plus-worker.md](../decisions/0001-home-assistant-integration-plus-worker.md)
- [docs/decisions/0003-entity-allowlist-semantic-resolution-memory.md](../decisions/0003-entity-allowlist-semantic-resolution-memory.md)
- [docs/decisions/0005-schema-driven-contracts-and-history-normalization.md](../decisions/0005-schema-driven-contracts-and-history-normalization.md)
- [docs/decisions/0006-validation-and-repair-loop.md](../decisions/0006-validation-and-repair-loop.md)
- [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../decisions/0008-read-only-mvp-and-sandbox-security.md)
- [docs/specs/entity-resolution-spec.md](entity-resolution-spec.md)
- [docs/specs/integration-spec.md](integration-spec.md)
- [docs/specs/home-assistant-config-flow-options-spec.md](home-assistant-config-flow-options-spec.md)
- [docs/schemas/entity-catalog-item.schema.json](../schemas/entity-catalog-item.schema.json)
