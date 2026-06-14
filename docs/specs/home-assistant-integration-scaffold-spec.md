---
status: draft
date: 2026-06-07
depends-on-adrs:
  - 0001
  - 0005
  - 0006
  - 0008
  - 0011
  - 0012
---

# Home Assistant Integration: Scaffold Anchor

## Status

Draft. Defines the first production Home Assistant custom integration scaffold
per ADR-0001, ADR-0005, ADR-0006, ADR-0008, ADR-0011, and ADR-0012.

## Related Docs

- [bdd/integration/home-assistant-integration-scaffold-bdd.md](../../bdd/integration/home-assistant-integration-scaffold-bdd.md) - observable behavior
- [docs/specs/integration-spec.md](integration-spec.md) - integration responsibilities
- [docs/specs/integration-api-transport-auth-spec.md](integration-api-transport-auth-spec.md) - command and worker boundary contract
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The MVP design phase is closed. The next production packet needs the smallest
real Home Assistant custom integration package so later slices have a stable
place to attach setup flows, entity allowlists, WebSocket orchestration,
history retrieval, semantic memory, worker calls, and dashboard resource
serving.

This scaffold must preserve the existing safety boundaries. It may define
configuration shapes and command stubs, but it must not call the worker, model
provider, Home Assistant history APIs, semantic-memory storage helpers, or Home
Assistant mutation services.

## Behavior Contract

The scaffold package lives at `custom_components/isolinear/` and defines:

- A Home Assistant `manifest.json` with domain `isolinear`.
- Domain constants for the integration name, WebSocket version, supported
  render modes, and supported command names.
- A local-first configuration/options data shape for:
  - model provider type,
  - model endpoint URL,
  - planner model name,
  - optional codegen model name,
  - optional visual validator model name,
  - worker endpoint URL,
  - default render mode,
  - maximum codegen repair attempts,
  - entity allowlist.
- Pure validation helpers that accept the configured shape and reject malformed
  or secret-bearing configuration, including endpoint URLs with embedded
  credentials, before orchestration exists.
- WebSocket command-boundary stubs for the versioned `isolinear/v1/` command
  names defined by the accepted integration API transport/authentication spec.

Command stubs must:

- Accept only schema-valid `IntegrationWsCommand` payloads.
- Reject unknown command names.
- Reject unsupported versions.
- Reject card payloads containing worker URLs, worker tokens, model endpoints,
  entity allowlists, raw history, generated code, generated images,
  semantic-memory records, Home Assistant tokens, or mutation-service material.
- Return schema-valid `IntegrationJobSnapshot` records when a command is
  accepted.
- Report that orchestration is not implemented yet without calling the worker,
  model provider, Home Assistant history APIs, semantic-memory helpers, or Home
  Assistant services.

## Anchor Artifact

The anchor artifact is the inspectable `custom_components/isolinear/` package
plus `src/Isolinear/integration_scaffold_anchor.py`, which verifies the package
manifest, configuration shape, command-boundary decisions, and scaffold
non-orchestration behavior.

## Implementation Order

1. Create this spec and its paired BDD/evidence scaffold.
2. Add `custom_components/isolinear/` with manifest, constants, configuration
   shape, and WebSocket command-boundary stubs.
3. Add the Python verifier anchor and focused unit tests.
4. Add an executable eval that emits raw `CASE` evidence for each BDD scenario.
5. Verify the real files on disk.

## Proof Requirements

1. Unit tests in `tests/test_integration_scaffold_anchor.py` are green.
2. `evals/home_assistant_integration_scaffold.py` emits raw `CASE` evidence for
   the BDD scenarios.
3. Accepted command stubs return `IntegrationJobSnapshot` schema-valid payloads.
4. Unknown, wrong-version, leaky, and mutating command payloads are rejected
   before orchestration.
5. Evidence confirms no worker, model provider, Home Assistant history,
   semantic-memory, or Home Assistant mutation calls occur in the scaffold.
6. Real artifacts are verified on disk: manifest, constants, config shape,
   WebSocket stubs, BDD, eval outline, tests, eval, and evidence.

## Non-Goals

- Implementing the production Home Assistant config flow UI.
- Registering the dashboard card resource.
- Fetching Home Assistant entity metadata or history.
- Calling the model provider.
- Calling the worker.
- Persisting semantic memory.
- Implementing job orchestration, subscriptions, streaming, retries, or artifact
  storage.
- Creating or mutating Home Assistant devices, services, automations, scenes,
  helpers, or configuration.

## References

- [docs/decisions/0001-home-assistant-integration-plus-worker.md](../decisions/0001-home-assistant-integration-plus-worker.md)
- [docs/decisions/0005-schema-driven-contracts-and-history-normalization.md](../decisions/0005-schema-driven-contracts-and-history-normalization.md)
- [docs/decisions/0006-validation-and-repair-loop.md](../decisions/0006-validation-and-repair-loop.md)
- [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../decisions/0008-read-only-mvp-and-sandbox-security.md)
- [docs/decisions/0011-dashboard-card-implementation-technology.md](../decisions/0011-dashboard-card-implementation-technology.md)
- [docs/decisions/0012-worker-transport-and-authentication.md](../decisions/0012-worker-transport-and-authentication.md)
- [docs/specs/integration-spec.md](integration-spec.md)
- [docs/specs/integration-api-transport-auth-spec.md](integration-api-transport-auth-spec.md)
- [docs/schemas/integration-ws-command.schema.json](../schemas/integration-ws-command.schema.json)
- [docs/schemas/integration-job-snapshot.schema.json](../schemas/integration-job-snapshot.schema.json)
