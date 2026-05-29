# ADR 0006: Layered validation and capped repair loop

## Status

Accepted

## Context

The system should not return a broken or obviously incorrect chart. In codegen mode, matplotlib code may fail at runtime. In both trusted and codegen modes, the rendered image may fail to answer the user's request.

## Decision

Validation will be layered:

1. Plan validation before history fetch and rendering.
2. Static code safety validation for codegen mode.
3. Runtime execution validation.
4. Capped stack-trace repair loop for codegen failures.
5. Render metadata validation.
6. Optional visual validation using a multimodal model.

The repair loop must have a configured maximum attempt count. After repeated failure, the system should return a useful failure message or fall back to trusted rendering when possible.

## Consequences

Positive:

- Failures become inspectable.
- Codegen can self-repair without unlimited loops.
- Deterministic validation remains primary.
- Visual validation can catch obvious chart mismatches.

Negative:

- More states in the dashboard card.
- Need clear user messaging for partial failures.
- Visual validation may be wrong and cannot be treated as proof.
