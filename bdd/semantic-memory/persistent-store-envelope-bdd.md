# Persistent Store Envelope BDD

Semantic memory persists as a versioned store envelope owned by the Home
Assistant integration. Alias invalidity is computed from the current entity
catalog and allowlist when aliases are prepared for planning.

Evidence file:
`bdd/semantic-memory/persistent-store-envelope-evidence.md`

Related artifacts:

- Source feature: `docs/bdd/semantic-memory.feature`
- Spec: `docs/specs/semantic-memory-spec.md`
- ADR: `docs/decisions/0009-semantic-memory-storage.md`
- ADR: `docs/decisions/0010-semantic-memory-store-envelope.md`
- Schema: `docs/schemas/semantic-memory-store.schema.json`
- Eval: `evals/semantic_memory_store_envelope.py`

## Scenario: Compute persisted alias invalidity at use time

Given a semantic memory store scoped to config entry `fake-config-entry`
And the store contains a valid threshold alias for `sensor.dishwasher_power`
And the store contains a threshold alias for `sensor.retired_dishwasher_power`
When the integration prepares semantic memory for planning against the current entity catalog
Then the valid alias should be returned for planner context
And the retired-entity alias should be reported with reason `entity_unavailable`
And the persisted store should not contain invalid status or invalid reasons
And computing invalidity should not mutate the persisted store

## Scenario: Unsupported store version fails closed

Given a semantic memory store has unsupported `store_version` 99
And the store contains an otherwise valid threshold alias
When the integration prepares semantic memory for planning
Then no aliases should be returned for planner context
And no invalid alias reasons should be computed
And the result should include store error code `semantic_memory_store_invalid`

## Scenario: Duplicate alias IDs fail closed

Given a semantic memory store contains two enabled aliases with the same `alias_id`
And the aliases point at different entity meanings
When the integration prepares semantic memory for planning
Then no aliases should be returned for planner context
And no invalid alias reasons should be computed
And the result should include store error code `semantic_memory_store_invalid`
And the store error should name the duplicate `alias_id`

## Proof Requirements

The evidence must include:

- A recent run timestamp.
- The exact eval command and raw eval output.
- The exact targeted unit-test command and raw test output.
- The semantic memory store fixture.
- The current entity catalog fixture.
- The observed valid aliases and computed invalid alias reasons.
- Raw proof that the store fixture has no persisted invalid status and remains
  unchanged after filtering.
- The unsupported-version store fixture and raw proof that it fails closed
  without injecting aliases.
- The duplicate-alias-ID store fixture and raw proof that it fails closed
  without injecting aliases.
