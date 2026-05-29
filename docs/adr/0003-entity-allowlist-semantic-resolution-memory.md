# ADR 0003: Entity allowlist, semantic resolution, and confirmed memory

## Status

Accepted

## Context

Home Assistant instances can contain many sensitive or irrelevant entities. The model should not receive unrestricted visibility into a user's home. At the same time, natural-language prompts require semantic matching using entity names, areas, labels, domains, device classes, units, and saved user preferences.

## Decision

The integration will maintain an explicit entity allowlist. The model receives only allowlisted entity metadata.

Entity resolution will combine:

1. Deterministic filtering.
2. Model-assisted ranking and interpretation.
3. Clarifying questions when multiple plausible mappings exist.
4. User-confirmed semantic memory for future prompts.

The model may propose semantic memory, but only the product can save it, and only after explicit user confirmation.

## Consequences

Positive:

- Reduces privacy and safety risk.
- Gives users control over what the agent can see.
- Allows the system to improve over time.
- Keeps durable memory auditable.

Negative:

- Users must configure visible entities.
- The first prompt may require clarification.
- Entity resolution needs careful tests and evals.
