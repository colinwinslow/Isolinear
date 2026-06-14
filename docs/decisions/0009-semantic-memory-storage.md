# ADR 0009: Semantic memory storage

## Status

Accepted

## Context

Semantic memory stores user-confirmed meanings such as aggregate aliases, state interval aliases, and threshold interval aliases. These records need to persist across Home Assistant restarts, remain auditable by the user, and stay coupled to the approved entity catalog that protects Home Assistant privacy.

ADR 0001 assigns semantic memory ownership to the Home Assistant integration. ADR 0003 requires memory to be user-confirmed. ADR 0008 keeps the MVP read-only with respect to Home Assistant devices and services. The remaining decision is where the integration persists semantic aliases.

Home Assistant provides config entries for integration configuration and a storage helper for integration-owned JSON-serializable data. Semantic aliases are durable product data, not setup configuration, and may change as users confirm, disable, delete, or repair remembered meanings.

## Decision

Persist semantic memory inside the Home Assistant custom integration using Home Assistant's versioned storage helper for JSON-serializable integration data.

The integration will own:

1. Loading and migrating the semantic-memory store.
2. Validating stored aliases against the semantic-alias contract.
3. Filtering aliases against the current approved entity catalog before use.
4. Marking or ignoring aliases whose source entities no longer exist or are no longer allowlisted.
5. Injecting only relevant, valid aliases into planning context.
6. Saving, disabling, deleting, or repairing aliases only through integration-owned flows or APIs.

Config entries and options flows remain responsible for integration setup and user configuration such as model endpoint, worker endpoint, render defaults, and entity allowlist. They may expose controls for managing semantic memory, but semantic alias records themselves should not be stored as config-entry data or options.

The model provider and worker must never read, write, or own semantic-memory storage directly. The dashboard card must access semantic memory through integration APIs rather than reading storage files. The store must not contain Home Assistant tokens, secrets, unrelated entity metadata, raw history, generated images, or generated code.

The initial implementation should use a versioned store document scoped to the integration config entry. If the integration later supports multiple independent config entries, each entry's semantic memory must remain isolated from the others.

## Consequences

Positive:

- Keeps semantic memory local to Home Assistant and under integration control.
- Avoids adding a new database, queue, external service, or worker responsibility.
- Aligns storage with the allowlist and entity-registry context needed to invalidate stale aliases.
- Supports schema validation and future migrations.
- Keeps the worker isolated from Home Assistant credentials and durable user memory.

Negative:

- The integration must implement store load/save, migration, and corruption handling.
- The semantic-memory spec and schemas need a persisted store envelope before storage code is added.
- Memory-management UI or options flows are still needed for delete, disable, and repair workflows.
- Tests must cover stale aliases, deleted entities, allowlist changes, and store migration.

## Rejected alternatives

### Store aliases in config-entry data or options

Rejected because semantic aliases are user-confirmed product data that can change independently from integration setup. Config entries and options should configure the integration, not act as the primary store for frequently updated memory records.

### Store aliases in the worker or add-on

Rejected because the worker is an isolation boundary for rendering and sandboxed code execution. It should not own Home Assistant semantic context, entity allowlists, or durable user memory.

### Store aliases in browser or dashboard-card local storage

Rejected because memory must be authoritative across browsers and sessions, and because the integration must validate aliases against current Home Assistant entity visibility before injecting them into planner context.

### Add a vector database or external database

Rejected for the MVP because semantic aliases are small, structured, user-confirmed records. Adding a database or service would increase deployment and security complexity without a current need.

## References

- Home Assistant config entries: https://developers.home-assistant.io/docs/config_entries_index/
- Home Assistant storage helper generics: https://developers.home-assistant.io/blog/2022/07/08/generic-store
