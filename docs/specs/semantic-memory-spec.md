# Semantic Memory Spec

## Purpose

Semantic memory stores user-confirmed mappings from natural-language concepts to entities, aggregates, thresholds, or other derived meanings.

## Principle

Memory is product-owned, not model-owned. The model may propose memory, but the integration decides what to save, and only after user confirmation.

## Memory examples

### Aggregate alias

`upstairs temperature` may mean the mean of three approved upstairs temperature sensors.

### Threshold interval alias

`dishwasher running` may mean `sensor.dishwasher_power > 5 W`.

### State interval alias

`AC running` may mean `binary_sensor.air_conditioning == on`.

## Save policy

The card should offer:

- Use once.
- Use and remember.

Saved memory should include:

- Alias ID.
- Natural names.
- Meaning.
- Source entities.
- Confirmation source.
- Created timestamp.
- Last used timestamp.

## Read policy

The integration injects relevant semantic aliases into each planning prompt. The model does not read memory files directly.

## Update policy

If a saved alias references entities that are no longer approved or no longer exist, the alias should be marked invalid and not used without user repair.

## Delete policy

Users must be able to delete saved semantic aliases through integration options or a future memory-management UI.

## Persistent store envelope

Semantic aliases persist inside a versioned integration-owned store document,
scoped to a single Home Assistant config entry.

Architecture decision: `docs/decisions/0010-semantic-memory-store-envelope.md`.

The store envelope must include:

- Store schema version.
- Config entry ID.
- Created timestamp.
- Updated timestamp.
- Alias records.

The store envelope must validate against `docs/schemas/semantic-memory-store.schema.json`.
Each alias record inside the store must validate against the `SemanticAlias`
contract.

The store envelope must not contain:

- Home Assistant tokens or secrets.
- Raw history.
- Generated chart images.
- Generated code.
- Unapproved entity metadata beyond the entity IDs already present in saved
  alias meanings.

## Store version and migration policy

The first persisted store version is `1`.

On load, the integration validates the envelope version and migrates older
supported versions before exposing aliases to planning. Unsupported future
versions, malformed JSON, or schema-invalid stores must fail closed: no aliases
are injected into planner context, and the integration records a repairable
store error for user-visible diagnostics.

Schema migrations may update envelope shape or alias shape, but they must not
invent new user meanings. If a migration cannot preserve a user-confirmed
meaning deterministically, the alias should be omitted from planner context and
surfaced for repair.

## Invalidity policy

Alias invalidity is computed at use time from the current entity catalog and
allowlist. The store does not persist invalid status or invalid reasons.

An enabled alias is valid for planning only when all entity IDs referenced by
its meaning are present in the current entity catalog and visible to the agent.

If an enabled alias references a missing entity, the computed invalid reason is
`entity_unavailable`.

If an enabled alias references an entity that exists but is not visible to the
agent, the computed invalid reason is `entity_not_allowlisted`.

Invalid aliases must not be injected into planner context and must not trigger
rendering. Computing invalidity must not mutate the persisted store.

Disabled aliases are user-suppressed. They are not injected into planner
context, and they are not treated as invalid solely because they are disabled.

## Duplicate and lifecycle policy

`alias_id` is the stable identity for a saved semantic alias within one config
entry store.

Saving a new alias with an existing `alias_id` must be handled
deterministically before persistence, either by replacing the existing alias
through an explicit repair/update flow or by rejecting the save with a useful
conflict message. Silent duplicate records are not allowed.

Deleting an alias removes it from the store. Disabling an alias keeps the alias
record with `enabled: false`. Repairing an alias updates the user-confirmed
meaning and timestamps through an integration-owned flow.
