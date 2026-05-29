# ADR 0002: Dashboard card as the first user interface

## Status

Accepted

## Context

The user needs a simple way to enter a natural-language prompt, answer clarifying questions, and view a generated chart. Voice is desirable later but adds speech recognition, latency, and image presentation complexity.

## Decision

The first UI will be a Home Assistant dashboard card. The card will support:

- Prompt input.
- Clarifying questions.
- Display of selected entities and saved aliases used.
- Generated chart image.
- Validation status.
- Warnings.
- Retry or revise prompt.

Voice and full custom panel experiences are deferred.

## Consequences

Positive:

- Smaller MVP surface.
- Easy fit for exploratory Home Assistant analysis.
- Clarification flow can be visual and explicit.

Negative:

- The first release is not voice-first.
- Long-running chart jobs need visible progress state.
- Card state management must handle multi-step conversations.
