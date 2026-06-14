---
status: draft
date: 2026-06-08
depends-on-adrs:
  - 0001
  - 0005
  - 0006
  - 0008
  - 0011
  - 0012
---

# Home Assistant Integration: WebSocket Command Registration Anchor

## Status

Draft. Defines the first production Home Assistant WebSocket command
registration surface for the Isolinear custom integration per ADR-0001,
ADR-0005, ADR-0006, ADR-0008, ADR-0011, and ADR-0012.

## Related Docs

- [bdd/integration/home-assistant-websocket-command-registration-bdd.md](../../bdd/integration/home-assistant-websocket-command-registration-bdd.md) - observable behavior
- [docs/specs/integration-api-transport-auth-spec.md](integration-api-transport-auth-spec.md) - accepted command contract
- [docs/specs/home-assistant-integration-scaffold-spec.md](home-assistant-integration-scaffold-spec.md) - existing scaffold boundary
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The production integration scaffold, config-flow/options surface, and
dashboard resource registration surface are anchored. The repository currently
has pure command-boundary stubs for the accepted `isolinear/v1/` command set,
but Home Assistant setup still needs to register real WebSocket handlers with
`websocket_api.async_register_command`.

This packet must keep command registration separate from job orchestration. It
may register handlers and return the existing scaffold snapshots, but it must
not fetch history, call the model provider, call the worker, persist semantic
memory, generate worker tokens, or mutate Home Assistant state/services.

## Behavior Contract

The integration must register the five accepted card-facing command names from
ADR-0012:

- `isolinear/v1/job/start`
- `isolinear/v1/clarification/answer`
- `isolinear/v1/job/retry`
- `isolinear/v1/job/snapshot`
- `isolinear/v1/job/subscribe`

Registration must:

- Use Home Assistant's `websocket_api.async_register_command` boundary.
- Attach a command schema for each registered command.
- Run from `async_setup_entry`.
- Store a registration result under the config-entry ID.
- Keep registration idempotent for repeated setup in the same Home Assistant
  runtime.
- Preserve the existing `IntegrationWsCommand` and `IntegrationJobSnapshot`
  schemas; Home Assistant's transport `id` is transport metadata and must not
  enter the internal command contract.
- Validate config-entry scope before returning a scaffold snapshot.
- Return the existing scaffold `IntegrationJobSnapshot` payload for accepted
  commands until a later orchestration packet replaces the scaffold behavior.
- Send a structured WebSocket error for invalid command payloads, unsupported
  versions, forbidden card boundary material, or missing config-entry scope.

Allowed side effects for this packet are limited to:

- Global Home Assistant WebSocket command registration.
- Config-entry-scoped bookkeeping in `hass.data["isolinear"][entry_id]`.
- Returning or erroring a WebSocket response for the current command.

The registration boundary must report that no worker, model-provider, Home
Assistant history, semantic-memory, Home Assistant service/device/state
mutation, token-generation, job-orchestration, or dashboard-resource metadata
write occurred. It must separately report WebSocket command registration as the
allowed Home Assistant registration side effect for this packet.

## Anchor Artifact

The anchor artifact is the inspectable
`custom_components/isolinear/websocket_api.py` module plus
`src/Isolinear/websocket_command_registration_anchor.py`, which verifies
registered command names, handler schemas, config-entry-scoped setup storage,
accepted snapshot responses, fail-closed invalid commands, idempotence, and
side-effect boundaries against fake Home Assistant objects.

## Implementation Order

1. Create this spec and its paired BDD/evidence scaffold.
2. Add failing unit tests for command registration, setup-entry storage,
   accepted callbacks, invalid callbacks, missing config-entry rejection,
   idempotence, and side-effect boundaries.
3. Replace scaffold-only command bookkeeping with real WebSocket command
   registration while preserving the pure validation helper.
4. Add the Python verifier anchor and focused executable eval.
5. Verify the real files on disk.

## Proof Requirements

1. Unit tests in `tests/test_websocket_command_registration_anchor.py` are
   green.
2. `evals/home_assistant_websocket_command_registration.py` emits raw `CASE`
   evidence for the BDD scenarios.
3. Evidence confirms all five `isolinear/v1/` command names are registered
   through the WebSocket command boundary.
4. Evidence confirms `async_setup_entry` stores the registration result under
   the config-entry ID.
5. Evidence confirms accepted registered callbacks return schema-valid
   `IntegrationJobSnapshot` payloads.
6. Evidence confirms unknown, wrong-version, leaky, mutating, and
   missing-config-entry command cases fail closed before orchestration.
7. Evidence confirms repeated setup does not duplicate WebSocket command
   registration.
8. Evidence confirms no worker, model provider, Home Assistant history,
   semantic-memory, Home Assistant service/device/state mutation,
   token-generation, job orchestration, or dashboard-resource metadata write is
   part of this command registration boundary.
9. Real artifacts are verified on disk: production WebSocket module,
   integration setup call, BDD, eval outline, tests, eval, and evidence.

## Non-Goals

- Job orchestration, subscriptions, progress streaming, retries, or artifact
  storage beyond returning scaffold snapshots.
- Home Assistant history access or entity catalog construction.
- Model-provider calls.
- Worker HTTP calls, worker token generation, rotation, storage, or repair UI.
- Semantic-memory persistence.
- Dashboard resource registration changes.
- Creating, editing, or deleting Home Assistant dashboards, devices, services,
  automations, scenes, helpers, or state.
- Persistent config-entry migration or repair flows.

## References

- [docs/decisions/0001-home-assistant-integration-plus-worker.md](../decisions/0001-home-assistant-integration-plus-worker.md)
- [docs/decisions/0005-schema-driven-contracts-and-history-normalization.md](../decisions/0005-schema-driven-contracts-and-history-normalization.md)
- [docs/decisions/0006-validation-and-repair-loop.md](../decisions/0006-validation-and-repair-loop.md)
- [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../decisions/0008-read-only-mvp-and-sandbox-security.md)
- [docs/decisions/0011-dashboard-card-implementation-technology.md](../decisions/0011-dashboard-card-implementation-technology.md)
- [docs/decisions/0012-worker-transport-and-authentication.md](../decisions/0012-worker-transport-and-authentication.md)
- [docs/specs/integration-api-transport-auth-spec.md](integration-api-transport-auth-spec.md)
- [docs/specs/home-assistant-integration-scaffold-spec.md](home-assistant-integration-scaffold-spec.md)
- [docs/schemas/integration-ws-command.schema.json](../schemas/integration-ws-command.schema.json)
- [docs/schemas/integration-job-snapshot.schema.json](../schemas/integration-job-snapshot.schema.json)
- Home Assistant Developer Docs: Extending the WebSocket API
  https://developers.home-assistant.io/docs/frontend/extending/websocket-api/
