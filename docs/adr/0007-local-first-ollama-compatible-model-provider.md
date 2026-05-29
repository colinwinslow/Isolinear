# ADR 0007: Local-first Ollama-compatible model provider

## Status

Accepted

## Context

The product is intended to work with locally hosted multimodal LLMs through Ollama, while still allowing users with stronger local or cloud models to configure alternatives later.

## Decision

The first model provider interface will target an Ollama-compatible chat API. The architecture will separate model roles so deployments can choose one model or multiple models:

- Planner model.
- Optional codegen model.
- Optional visual validator model.

The integration should not assume the model runs on the Home Assistant host. The model endpoint may be on another machine.

## Consequences

Positive:

- Local-first default.
- Supports GPU hosts separate from Home Assistant.
- Allows model experimentation.
- Avoids hard-coding a single model role.

Negative:

- Model capabilities vary widely.
- Configuration and diagnostics must expose model failures clearly.
- Structured output support must be verified per provider.
