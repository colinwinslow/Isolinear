---
status: draft
date: 2026-06-09
depends-on-adrs:
  - 0001
  - 0005
  - 0008
  - 0012
  - 0014
---

# Home Assistant Integration: Worker Health/Readiness Endpoint Scaffold Anchor

## Status

Draft. Defines the first production Home Assistant integration-owned worker
health/readiness endpoint scaffold per ADR-0001, ADR-0005, ADR-0008, and
ADR-0012. ADR-0014 records the concrete `GET /v1/health` readiness endpoint
decision used by this packet.

## Related Docs

- [bdd/integration/home-assistant-worker-health-readiness-endpoint-scaffold-bdd.md](../../bdd/integration/home-assistant-worker-health-readiness-endpoint-scaffold-bdd.md) - observable behavior
- [docs/specs/integration-api-transport-auth-spec.md](integration-api-transport-auth-spec.md) - worker HTTP envelope and bearer-token contract
- [docs/specs/home-assistant-worker-token-provisioning-readiness-scaffold-spec.md](home-assistant-worker-token-provisioning-readiness-scaffold-spec.md) - existing worker token/readiness gate
- [docs/specs/home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-spec.md](home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-spec.md) - adjacent render dispatch boundary
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The integration can provision an in-memory integration-owned worker token and
gate worker rendering on that token. The next smallest worker behavior is an
explicit, inspectable health/readiness probe that checks a configured worker
endpoint through ADR-0012 bearer authentication and records only schema-valid,
redacted, config-entry-scoped health metadata.

This packet does not add automatic health polling, a scheduler, durable health
state, token rotation, retry queues, repair UI, worker render changes, or any
dashboard-card health command. The health probe is an integration-owned
internal operation that can be called directly by future setup/repair flows.

## Behavior Contract

The worker health/readiness endpoint boundary must:

- Define an authenticated worker health request shape for `GET /v1/health`
  using ADR-0012's worker transport version header and integration-owned
  bearer token.
- Run config-entry setup without calling the worker health endpoint.
- Enable the explicit health probe only when the existing worker
  token/readiness gate is `ready` and a same-entry worker client is configured.
- Reject unknown config entries before worker calls or health metadata storage.
- Reject entries without valid worker readiness, token, or worker client before
  worker calls or health metadata storage.
- Build and validate a schema-valid worker health request before a worker
  health call.
- Call only the worker client configured for the targeted config entry.
- Accept worker health responses that report `ready` or `not_ready`, sanitize
  code/message text, and record one schema-valid
  `IntegrationWorkerHealth` envelope after validation.
- Record schema-valid `unavailable` health metadata for worker transport
  failures without scheduling retries or writing retry policy metadata.
- Fail closed before health metadata storage when an accepted worker health
  response is malformed or fails validation.
- Store only redacted worker authorization as `Bearer <redacted>` in health
  metadata, setup results, eval output, and verifier output.
- Keep health metadata, setup results, worker clients, tokens, readiness, and
  health calls isolated per config entry.
- Avoid exposing worker endpoint, request details, bearer tokens, health
  response internals, or health metadata to dashboard-card WebSocket payloads.

The `IntegrationWorkerHealth` envelope must include:

- `health_id`
- `type`
- `config_entry_id`
- `status`
- `code`
- `worker`
- `request`
- `response`
- `validation`
- `warnings`
- `orchestration`

Allowed side effects for this packet are limited to:

- Reading the targeted config entry, existing worker readiness metadata,
  in-memory worker token, and same-entry worker client.
- One explicit worker health endpoint call for an eligible config entry.
- Writing one in-memory config-entry-scoped health envelope after validation.
- Existing config-entry setup bookkeeping.

The packet remains bounded: it must not mutate Home Assistant
services/devices/state/configuration, read Home Assistant history, persist
semantic memory, generate or rotate tokens, call worker render, render charts,
write chart artifacts, add durable health or retry storage, schedule automatic
health checks or retries, start automatic progress tasks, introduce a new
transport mechanism, or expose worker health metadata to the dashboard card.

## Anchor Artifact

The anchor artifact is the inspectable health/readiness endpoint behavior in
`custom_components/isolinear/worker_health.py`,
`custom_components/isolinear/worker_renderer.py`, and
`src/Isolinear/worker_health_readiness_endpoint_anchor.py`, which verifies
ready, not-ready, unavailable, malformed-response, no-token, unknown-entry,
config-entry isolation, redaction, card-safety, schema validity, and bounded
side effects against fake Home Assistant config entries and fake worker health
clients.

## Implementation Order

1. Create this spec, paired BDD/evidence scaffold, eval outline, and worker
   health schemas.
2. Add failing unit tests and a Python verifier anchor for health success,
   not-ready response, transport failure metadata, malformed-response
   rejection, no-token rejection, unknown-entry rejection, isolation,
   redaction, card-safety, schema validity, and side-effect boundaries.
3. Add the focused executable eval.
4. Add the smallest production health request/client helpers and
   config-entry-scoped worker health module.
5. Wire health setup bookkeeping into config-entry setup without calling the
   worker endpoint automatically.
6. Verify the real files on disk.

## Proof Requirements

1. Unit tests in `tests/test_worker_health_readiness_endpoint_anchor.py` are
   green.
2. Existing worker token/readiness, worker dispatch/rendering, worker progress,
   retry/backoff, transport-classification, failure-snapshot/manual-retry,
   WebSocket registration, job-state, and integration scaffold tests remain
   green.
3. `evals/home_assistant_worker_health_readiness_endpoint_scaffold.py` emits
   raw `CASE` evidence for the BDD scenarios.
4. Evidence confirms an eligible provisioned entry records one schema-valid
   `ready` health envelope with redacted authorization.
5. Evidence confirms a worker-reported `not_ready` result records a
   schema-valid internal health envelope without disabling or changing worker
   renderer setup.
6. Evidence confirms worker transport failure records schema-valid
   `unavailable` health metadata without retry/scheduler/durable side effects.
7. Evidence confirms malformed accepted health responses fail closed before
   health metadata storage.
8. Evidence confirms no-token and unknown config-entry health checks fail
   before worker calls or health metadata storage.
9. Evidence confirms two config entries keep health metadata, tokens, worker
   clients, readiness, and health calls isolated.
10. Evidence confirms no raw token appears in health metadata, setup results,
    eval output, dashboard WebSocket registration metadata, model provider
    setup metadata, or user-visible payloads.
11. Evidence confirms dashboard-card WebSocket payloads do not expose worker
    endpoint, request details, bearer authorization, health response internals,
    or internal health metadata.
12. Evidence confirms no Home Assistant history read, semantic-memory
    persistence, Home Assistant service/device/state mutation, token
    generation/rotation, worker render call, chart rendering, chart artifact
    write, durable storage, retry queue, scheduler, automatic retry, or
    automatic progress task occurs.
13. Real artifacts are verified on disk: production health module, worker
    renderer health helpers, integration setup wiring, worker health schemas,
    BDD, eval outline, tests, eval, evidence, and verifier anchor.

## Non-Goals

- Automatic or scheduled worker health polling.
- Durable health state, retry queues, or repair UI.
- Token generation, persistence, or rotation.
- Changing job retry behavior or recording retry/backoff policy metadata.
- Worker render endpoint behavior changes.
- Changing card-facing WebSocket command schemas or adding a dashboard health
  command.
- Passing worker endpoint, request details, health metadata, or token material
  to the dashboard card or model provider.
- Creating, editing, or deleting Home Assistant dashboards, devices, services,
  automations, scenes, helpers, or state.

## References

- [docs/decisions/0001-home-assistant-integration-plus-worker.md](../decisions/0001-home-assistant-integration-plus-worker.md)
- [docs/decisions/0005-schema-driven-contracts-and-history-normalization.md](../decisions/0005-schema-driven-contracts-and-history-normalization.md)
- [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../decisions/0008-read-only-mvp-and-sandbox-security.md)
- [docs/decisions/0012-worker-transport-and-authentication.md](../decisions/0012-worker-transport-and-authentication.md)
- [docs/decisions/0014-worker-health-readiness-endpoint.md](../decisions/0014-worker-health-readiness-endpoint.md)
- [docs/schemas/worker-health-request.schema.json](../schemas/worker-health-request.schema.json)
- [docs/schemas/integration-worker-health.schema.json](../schemas/integration-worker-health.schema.json)
