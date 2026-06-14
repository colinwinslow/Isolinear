---
id: 0010
title: Semantic memory store envelope
status: accepted
date: 2026-06-01
supersedes: []
superseded-by: null
tags:
  - semantic-memory
  - storage
  - schema
---

# ADR-0010: Semantic memory store envelope

## Context

ADR-0009 decides that semantic memory is owned by the Home Assistant custom
integration and persisted with Home Assistant's versioned storage helper.
The next implementation slice needs a concrete v1 store envelope so aliases can
be validated, migrated, scoped to an integration config entry, and prepared for
planner context.

Saved aliases also need to remain coupled to the current entity allowlist. A
stored alias can become unsafe to reuse when its referenced entity disappears or
is no longer visible to the agent. Persisting that invalidity directly would
make the store stale whenever Home Assistant entities or allowlist settings
change.

## Decision

**Semantic memory store v1 is a versioned envelope scoped to one integration
config entry, and alias invalidity is computed at use time from the current
entity catalog and allowlist rather than persisted in the store.**

The v1 envelope contains:

- `store_version`
- `config_entry_id`
- `created_at`
- `updated_at`
- `aliases`

The envelope validates against
`docs/schemas/semantic-memory-store.schema.json`. Each alias in `aliases`
validates against the `SemanticAlias` contract.

Unsupported store versions, malformed stores, and schema-invalid stores fail
closed: no aliases are injected into planner context, and the integration
returns a repairable store error.

Duplicate `alias_id` records in a loaded store are also store-invalid and fail
closed before alias invalidity checks. Future save/update flows must prevent
silent duplicate records by rejecting the save or routing it through an explicit
update or repair flow.

## Rationale

- ADR-0009 already chooses the storage owner and Home Assistant storage helper;
  this ADR fills in the persisted document contract beneath that decision.
- Config-entry scoping keeps independent integration instances isolated.
- Computing invalidity at use time avoids persisting stale error state when
  entities are renamed, removed, restored, or re-allowlisted.
- Fail-closed validation preserves the entity allowlist invariant and prevents
  malformed durable memory from influencing planning.
- Treating duplicate `alias_id` records as store-invalid prevents ambiguous
  planner context and keeps alias reuse deterministic.
- A schema-first envelope gives migrations an explicit contract and keeps
  evidence inspectable before Home Assistant storage-helper plumbing exists.

## Consequences

**Enables:**

- A concrete anchor artifact for persistent semantic memory.
- Deterministic validation of stored alias documents before planner injection.
- Store migration tests and repair UI design to build on a stable envelope.

**Constrains:**

- The store must not persist invalidity status or invalid reasons.
- Planner context receives only enabled aliases that are valid against the
  current allowlist.
- Duplicate alias IDs must be resolved before planner injection.
- Future envelope changes must be represented as migrations from versioned
  store documents.

**Open:**

- Exact Home Assistant storage-helper key naming.
- Repair UI flow details for malformed stores and invalid aliases.

## References

- ADR-0003: Entity allowlist, semantic resolution, and confirmed memory
- ADR-0005: Schema-driven contracts and history normalization
- ADR-0008: Read-only MVP and sandbox security
- ADR-0009: Semantic memory storage
- `docs/specs/semantic-memory-spec.md`
- `docs/schemas/semantic-memory-store.schema.json`
- `bdd/semantic-memory/persistent-store-envelope-bdd.md`
