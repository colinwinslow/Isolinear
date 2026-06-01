# ADR 0001: Home Assistant integration plus isolated worker

## Status

Accepted

## Context

The product must feel native to Home Assistant while also executing potentially risky visualization code. Home Assistant should own configuration, entity access, prompt submission, and dashboard display. Rendering and sandboxed code execution should be isolated from Home Assistant tokens, secrets, and internal APIs.

Home Assistant add-ons are a user-friendly way to distribute containerized services for Home Assistant OS and supervised installs. Some users may run Home Assistant in modes that do not support add-ons, so the worker should also be runnable as a standalone service.

## Decision

Build the system as:

1. A Home Assistant custom integration.
2. A custom dashboard card.
3. An isolated worker service packaged as a Home Assistant add-on and also runnable standalone.
4. An Ollama-compatible model provider endpoint configured by the user.

The integration orchestrates entity access, prompt state, model calls, memory, and display. The worker renders charts and runs sandboxed generated code. The worker never receives a Home Assistant token.

## Consequences

Positive:

- Native Home Assistant UX.
- User-friendly add-on deployment for many users.
- Standalone worker path for advanced users.
- Stronger security boundary between Home Assistant and generated code.

Negative:

- More components than a single integration.
- Worker API versioning must be managed.
- Add-on and standalone deployment paths must both be tested.
