# ADR 0005: Schema-driven contracts and deterministic history normalization

## Status

Accepted

## Context

Home Assistant history is not chart-ready. Entity states may be strings, `unknown`, `unavailable`, attributes, irregular state changes, categorical values, or continuous measurements. The model should not have to clean this data directly.

## Decision

The product will define internal JSON schemas for core contracts:

- Entity catalog items.
- Semantic aliases.
- Clarifying questions.
- Chart specs.
- History series.
- Derived intervals.
- Render requests.
- Render results.
- Validation results.

The integration and worker will normalize Home Assistant history into these contracts before rendering.

Users will not write JSON. Schemas are internal developer and runtime contracts.

## Consequences

Positive:

- Runtime validation catches malformed model output.
- Tests can use the same contracts as production.
- History quirks are handled deterministically.
- Codegen mode receives clean data.

Negative:

- Schema evolution must be managed.
- Normalization behavior must be thoroughly tested.
- Some Home Assistant entity patterns will require later adapters.
