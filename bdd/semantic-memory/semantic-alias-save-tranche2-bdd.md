# Semantic Alias Save — Tranche 2 BDD

Propose and save a semantic alias when a user answers an entity-selection
clarification with "Use and remember."

Evidence file:
`bdd/semantic-memory/semantic-alias-save-tranche2-evidence.md`

Related artifacts:

- Spec: `docs/specs/semantic-alias-save-tranche2.md`
- Tranche 1 BDD: `bdd/semantic-memory/semantic-alias-live-wiring-bdd.md`
- ADR: `docs/decisions/0009-semantic-memory-storage.md`

## Scenario: Use once — no alias saved

Given an entity-selection clarification question is pending with `can_remember: true`
When the user answers with `remember: false`
Then the job continues with the selected entity
And no alias is written to the semantic memory store

## Scenario: Use and remember — alias saved

Given an entity-selection clarification question is pending for `climate.kitchen_ecobee`
And the prompt was "show kitchen temp and when the AC was running"
When the user answers with `remember: true`
Then the job continues with the selected entity
And the semantic memory store contains one new alias
And the alias `alias_id` is `climate_kitchen_ecobee`
And the alias `natural_names` includes tokens derived from the prompt
And the alias `meaning` is `{"type": "entity", "entity_id": "climate.kitchen_ecobee"}`
And the alias `source` is `user_confirmed`

## Scenario: Duplicate alias_id is replaced

Given the semantic memory store already contains an alias with `alias_id: climate_kitchen_ecobee`
When the user answers a new clarification for `climate.kitchen_ecobee` with `remember: true`
Then the store contains exactly one alias with `alias_id: climate_kitchen_ecobee`
And the alias record is the newly saved one (replaced, not duplicated)

## Scenario: Save failure is non-blocking

Given the HA Store write fails (simulated)
And an entity-selection clarification question is pending with `remember: true`
When the user answers the clarification
Then the job continues with the selected entity
And a WARNING is logged describing the save failure
And the job does not return a failed snapshot

## Scenario: Saved alias is matched on next request (Tranche 1 + 2 integration)

Given the semantic memory store contains the alias saved in "Use and remember"
When the user submits the same conceptual prompt in a new job
Then `_inject_semantic_aliases` matches the saved alias
And `climate.kitchen_ecobee` is injected into entity selection
And no clarification question is surfaced

## Scenario: Complete snapshot shows matched aliases

Given a job completed using a matched semantic alias
When the complete snapshot is returned
Then `snapshot.aliases` contains one entry
And the entry `name` matches the alias natural name
And the entry `meaning` describes the alias entity and type

## Proof requirements

Evidence must include:

- A recent run timestamp.
- The unit-test command and raw output (all new tests passing).
- The eval command and output showing the clarification → save → inject round trip.
- The raw in-memory store state after save, showing the alias record.
- The alias natural_names for the AC prompt example.
- Validation that a second request using the saved alias skips clarification.
- Full suite result (484+ passed, ≤3 pre-existing codegen-sandbox failures).
