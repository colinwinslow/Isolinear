# Semantic Alias Live Wiring BDD

The integration loads saved semantic aliases from the per-config-entry store,
matches their natural names against the prompt by token overlap, and injects the
matched entities into the deterministic entity selection that feeds planning.
This is Tranche 1 (load → match → inject); saving aliases is out of scope.

Evidence file:
`bdd/semantic-memory/semantic-alias-live-wiring-evidence.md`

Related artifacts:

- Source feature: `docs/bdd/semantic-memory.feature`
- Spec: `docs/specs/semantic-alias-live-wiring.md`
- Memory contract: `docs/specs/semantic-memory-spec.md`
- ADR: `docs/decisions/0009-semantic-memory-storage.md`
- ADR: `docs/decisions/0010-semantic-memory-store-envelope.md`
- ADR: `docs/decisions/0024-*` (deterministic + model-driven entity selection, augmented)
- Schema: `docs/schemas/semantic-memory-store.schema.json`, `docs/schemas/semantic-alias.schema.json`
- Store-load/validity reuse: `bdd/semantic-memory/persistent-store-envelope-bdd.md`
- Code: `custom_components/isolinear/semantic_memory.py`,
  `custom_components/isolinear/job_orchestration.py` (`select_prompt_entity_ids`)
- Eval: `evals/semantic_memory_store_envelope.py` (extended with an injection CASE)

## Scenario: Saved AC alias injects the climate entity the prompt never named

Given a semantic memory store scoped to config entry `fake-config-entry`
And the store contains an enabled, valid alias `whole_house_ac` with natural names `["AC", "AC running"]` meaning state interval on `climate.kitchen_ecobee`
And `climate.kitchen_ecobee` is approved and visible to the agent in the current catalog
And `sensor.kitchen_temperature` is approved and visible to the agent in the current catalog
When the user prompts "show kitchen temp and when the AC was running"
Then the resolved entities should include `sensor.kitchen_temperature` from direct catalog matching
And the resolved entities should include `climate.kitchen_ecobee` from the matched semantic alias
And the resolution source should record `semantic_alias` with matched alias id `whole_house_ac`
And no clarification should be raised for the aliased concept

## Scenario: Token overlap below threshold does not match

Given a semantic memory store with an enabled, valid alias with natural names `["dishwasher running"]`
When the user prompts "show kitchen temperature today"
Then no semantic alias should match the prompt
And entity selection should resolve exactly as it would with no aliases present

## Scenario: A short two-character alias token still matches

Given a semantic memory store with an enabled, valid alias `whole_house_ac` with natural name `"AC"` meaning state interval on `climate.kitchen_ecobee`
When the user prompts "is the AC on right now?"
Then the alias `whole_house_ac` should match the prompt despite the two-character token
And the resolved entities should include `climate.kitchen_ecobee` with source `semantic_alias`

## Scenario: Disabled alias is never injected

Given a semantic memory store with a disabled alias `whole_house_ac` for `climate.kitchen_ecobee`
When the user prompts "show me when the AC was running"
Then the disabled alias should not match
And `climate.kitchen_ecobee` should not be injected into the resolved entities

## Scenario: Invalid alias (entity unavailable or not allowlisted) is never injected

Given a semantic memory store with an enabled alias `whole_house_ac` referencing `<entity_id>`
And that entity is `<entity_state>` in the current catalog
When the user prompts "show me when the AC was running"
Then the alias should be excluded as invalid with reason `<reason>`
And `<entity_id>` should not be injected into the resolved entities
And the prompt should resolve as if the alias were absent

Examples:
  | entity_id                  | entity_state          | reason                  |
  | climate.retired_ecobee     | absent from catalog   | entity_unavailable      |
  | climate.kitchen_ecobee     | present but hidden    | entity_not_allowlisted  |

## Scenario: Malformed store fails closed with no injection

Given a persisted semantic memory store that is schema-invalid or has an unsupported `store_version`
When the user prompts "show me when the AC was running"
Then no aliases should be loaded for matching
And the result should carry store error code `semantic_memory_store_invalid`
And entity selection should resolve exactly as it would with no aliases present

## Scenario: Aggregate alias injects all of its source entities

Given a semantic memory store with an enabled, valid alias `upstairs_temperature` meaning aggregate `mean` over three approved upstairs temperature sensors
When the user prompts "show upstairs temperature overnight"
Then all three source entity IDs should be injected into the resolved entities with source `semantic_alias`

## Proof Requirements

The evidence must include:

- A recent run timestamp.
- The exact targeted unit-test command and raw test output for the new
  `semantic_memory` module and the orchestration injection.
- The exact eval command and raw eval output.
- The seeded store document and the resolution result showing both entity IDs
  and `source: semantic_alias` (the anchor artifact on disk).
</content>
