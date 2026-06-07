---
status: accepted
date: 2026-06-05
depends-on-adrs:
  - 0001
  - 0008
  - 0011
  - 0012
---

# Integration API: Transport and Authentication

## Status

Accepted. Defines the contract surface for the card-facing Home Assistant
WebSocket API and the worker-facing transport/authentication envelope per
ADR-0012.

## Related Docs

- [bdd/dashboard-card/integration-api-transport-auth-bdd.md](../../bdd/dashboard-card/integration-api-transport-auth-bdd.md) - observable behavior
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The dashboard card has a thin adapter that sends user gestures through Home
Assistant WebSocket messages. The production integration now needs those
messages to become explicit versioned schemas, and it needs a worker
transport/authentication envelope that preserves the isolation boundary from
ADR-0001 and ADR-0008.

This spec is an anchor contract. It does not build the Home Assistant
integration or worker service, but it defines the messages those components
must accept and reject.

## Behavior Contract

### Card-Facing WebSocket Commands

The integration owns version `1` commands under the `isolinear/v1/` namespace.
Every command includes:

- `type` - exact command name.
- `version` - integer `1`.
- `config_entry_id` - Home Assistant config entry owning the Isolinear setup.

The command set is:

- `isolinear/v1/job/start` - submit a prompt and receive the first job snapshot.
- `isolinear/v1/clarification/answer` - answer a clarification for a job.
- `isolinear/v1/job/retry` - retry a failed or retryable job.
- `isolinear/v1/job/snapshot` - retrieve the latest snapshot for a job.
- `isolinear/v1/job/subscribe` - subscribe to future snapshots for a job.

The dashboard card may send only these integration commands. It must not send
worker URLs, worker credentials, model endpoints, entity allowlists, raw
history, generated code, generated images, or semantic-memory records.

Home Assistant authenticates the WebSocket session. The integration then
validates the command schema, validates the config-entry scope, and returns
`IntegrationJobSnapshot` records to the card.

### Worker-Facing Transport

The integration sends render requests to the worker with:

- Method: `POST`
- Path: `/v1/render`
- Header: `Content-Type: application/json`
- Header: `X-Isolinear-Worker-API-Version: 1`
- Header: `Authorization: Bearer <worker-token>`
- Body: a versioned worker transport request containing one validated
  `RenderRequest`

The worker must reject the request before rendering when:

- The bearer token is missing or incorrect.
- The transport version is unsupported.
- The request envelope does not match schema.
- The render request does not match `RenderRequest`.
- The request contains Home Assistant tokens, long-lived access tokens,
  model-provider credentials, semantic-memory storage, or browser-visible
  worker credentials.

Worker authorization values are integration-owned secrets. Evidence and logs
must redact them.

## Anchor Artifact

The anchor artifact is `src/Isolinear/transport_auth_anchor.py`. It builds
deterministic example WebSocket commands, a worker render request envelope, and
negative examples for missing auth, wrong auth, wrong version, and leaked Home
Assistant secrets.

## Implementation Order

1. Add schemas for `IntegrationWsCommand`, `IntegrationJobSnapshot`, and
   `WorkerTransportRequest`.
2. Add the Python anchor that validates the schemas and auth decisions.
3. Update the TypeScript card adapter command list to include the subscription
   command.
4. Add unit tests and an eval that produce inspectable evidence.

## Proof Requirements

1. Unit tests in `tests/test_transport_auth_anchor.py` are green.
2. `evals/integration_api_transport_auth.py` emits raw `CASE` evidence for the
   BDD scenarios.
3. The worker authorization token is redacted in evidence output.
4. Existing dashboard-card adapter tests remain green after adding the
   subscription command.
5. Real artifacts are verified on disk: schemas, ADR, spec, BDD, anchor, tests,
   and evidence.

## Non-Goals

- Building the production Home Assistant custom integration.
- Building the production worker HTTP server.
- Implementing token generation, rotation, storage repair, or UI.
- Defining worker health checks or streaming worker progress.
- Changing the render request/result schemas beyond the transport envelope.

## References

- [docs/decisions/0012-worker-transport-and-authentication.md](../decisions/0012-worker-transport-and-authentication.md)
- [docs/specs/dashboard-card-spec.md](dashboard-card-spec.md)
- [docs/specs/integration-spec.md](integration-spec.md)
- [docs/specs/security-spec.md](security-spec.md)
- [docs/specs/worker-sandbox-spec.md](worker-sandbox-spec.md)
- [docs/schemas/integration-ws-command.schema.json](../schemas/integration-ws-command.schema.json)
- [docs/schemas/integration-job-snapshot.schema.json](../schemas/integration-job-snapshot.schema.json)
- [docs/schemas/worker-transport-request.schema.json](../schemas/worker-transport-request.schema.json)
