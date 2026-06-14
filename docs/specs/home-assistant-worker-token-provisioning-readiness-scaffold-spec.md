---
status: draft
date: 2026-06-09
depends-on-adrs:
  - 0001
  - 0005
  - 0008
  - 0012
---

# Home Assistant Integration: Worker Token Provisioning/Readiness Scaffold Anchor

## Status

Draft. Defines the first production Home Assistant integration-owned worker
token readiness surface per ADR-0001, ADR-0005, ADR-0008, and ADR-0012.

## Related Docs

- [bdd/integration/home-assistant-worker-token-provisioning-readiness-scaffold-bdd.md](../../bdd/integration/home-assistant-worker-token-provisioning-readiness-scaffold-bdd.md) - observable behavior
- [docs/specs/integration-api-transport-auth-spec.md](integration-api-transport-auth-spec.md) - worker HTTP envelope and bearer-token contract
- [docs/specs/home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-spec.md](home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-spec.md) - adjacent worker dispatch boundary
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The integration can dispatch validated render requests to an ADR-0012 worker
client only when an integration-owned bearer token is already present. The next
smallest production behavior is an inspectable, schema-backed readiness surface
that can explicitly provision one in-memory integration-owned scaffold token,
verify token presence, and report readiness without exposing credential
material to the dashboard card, model provider, evidence, or user-visible
metadata.

This packet does not add token rotation, durable token storage, a repair UI,
worker health checks, worker streaming, or retry/backoff behavior. Explicit
token provisioning is a scaffold operation owned by the integration; default
config-entry setup remains no-token/not-ready unless a token has already been
provided by integration/add-on setup.

## Behavior Contract

The worker token/readiness boundary must:

- Run during config-entry setup before worker renderer setup.
- Store one config-entry-scoped `IntegrationWorkerReadiness` envelope after
  schema validation.
- Report `disabled` when no worker endpoint is configured.
- Report `not_ready` when a worker endpoint is configured but no valid
  integration-owned worker token is present.
- Report `ready` when a worker endpoint is configured and a valid
  integration-owned worker token is present.
- Provide an explicit integration-owned token provisioning function that stores
  one valid in-memory token for a known config entry, validates the resulting
  readiness envelope before storage, and returns only redacted token metadata.
- Treat repeated provisioning as idempotent when a valid token is already
  present.
- Reject unknown config entries before token generation, token storage, worker
  readiness metadata, or worker renderer client setup.
- Keep readiness metadata, worker tokens, worker renderer clients, and setup
  results isolated per config entry.
- Allow worker renderer setup to create a client only when readiness has a
  valid token and endpoint.
- Redact bearer authorization as `Bearer <redacted>` in readiness metadata,
  setup results, eval evidence, and verifier output.
- Avoid leaking raw token material to dashboard WebSocket registration
  metadata, card-facing command payloads, model provider setup metadata, or
  user-visible failure details.

The `IntegrationWorkerReadiness` envelope must include:

- `readiness_id`
- `config_entry_id`
- `status`
- `worker`
- `token`
- `validation`
- `warnings`
- `orchestration`

Allowed side effects for this packet are limited to:

- Reading the targeted config entry and worker endpoint configuration.
- Reading or writing one in-memory integration-owned worker token only during
  explicit provisioning.
- Reading the in-memory integration-owned worker token during readiness setup.
- Writing one in-memory config-entry-scoped readiness envelope after validation.
- Existing worker renderer client setup only when a valid token and endpoint
  are present.
- Existing config-entry setup bookkeeping and WebSocket command registration.

The packet remains bounded: it must not mutate Home Assistant
services/devices/state/configuration, send worker tokens to the card or model
provider, call the worker, render charts, read Home Assistant history, persist
semantic memory, write chart artifacts, add durable token storage, add token
rotation, add worker health checks, add retry/backoff policy, add automatic
progress tasks, or add worker streaming.

## Anchor Artifact

The anchor artifact is the inspectable readiness behavior in
`custom_components/isolinear/worker_readiness.py`,
`custom_components/isolinear/worker_renderer.py`, and
`src/Isolinear/worker_token_provisioning_readiness_anchor.py`, which verifies
explicit token provisioning, no-token setup, disabled setup, schema validity,
redaction, unknown config-entry rejection, per-config-entry isolation, worker
renderer gating, and bounded side effects against fake Home Assistant config
entries.

## Implementation Order

1. Create this spec, paired BDD/evidence scaffold, eval outline, and worker
   readiness schema.
2. Add failing unit tests and a Python verifier anchor for explicit token
   provisioning, no-token setup, disabled setup, schema validity, redaction,
   unknown config-entry rejection, per-config-entry isolation, worker renderer
   gating, and side-effect boundaries.
3. Add the focused executable eval.
4. Add the smallest production worker readiness module and token validation
   helpers.
5. Wire worker readiness setup before worker renderer setup.
6. Verify the real files on disk.

## Proof Requirements

1. Unit tests in `tests/test_worker_token_provisioning_readiness_anchor.py` are
   green.
2. Existing Home Assistant worker dispatch/rendering, model-provider planning,
   render-planning, artifact-storage, job-state, WebSocket registration,
   approved-entity-catalog, and approved-history tests remain green.
3. `evals/home_assistant_worker_token_provisioning_readiness_scaffold.py`
   emits raw `CASE` evidence for the BDD scenarios.
4. Evidence confirms explicit token provisioning records one schema-valid ready
   envelope and enables worker renderer setup without exposing the raw token.
5. Evidence confirms no-token setup records a schema-valid not-ready envelope
   and leaves worker renderer setup disabled.
6. Evidence confirms missing worker endpoint setup records a schema-valid
   disabled envelope and leaves worker renderer setup disabled.
7. Evidence confirms repeated provisioning reuses the existing token and
   readiness without generating another token.
8. Evidence confirms unknown config entries fail closed before token generation
   or readiness metadata storage.
9. Evidence confirms readiness validation failures roll back newly generated
   token material before returning a failure.
10. Evidence confirms two config entries keep readiness metadata, worker tokens,
   and worker renderer clients isolated.
11. Evidence confirms no raw token appears in readiness metadata, setup
    results, eval evidence, dashboard WebSocket registration metadata, model
    provider setup metadata, or user-visible failure details.
12. Evidence confirms no Home Assistant history read, semantic-memory
    persistence, Home Assistant service/device/state mutation, worker call,
    chart rendering, chart artifact file write, durable token storage,
    rotation, health check, retry/backoff policy, automatic progress task, or
    worker streaming occurs.
13. Real artifacts are verified on disk: production readiness module, worker
    renderer token gate, integration setup wiring, worker readiness schema,
    BDD, eval outline, tests, eval, evidence, and verifier anchor.

## Non-Goals

- Persistent worker token storage, migration, repair, or UI.
- Token rotation semantics.
- Worker health checks or readiness HTTP probes.
- Worker streaming or long-running progress semantics.
- Worker dispatch/rendering behavior beyond the existing gated renderer setup.
- Changing card-facing WebSocket command schemas.
- Passing worker endpoint or token material to the dashboard card or model
  provider.
- Creating, editing, or deleting Home Assistant dashboards, devices, services,
  automations, scenes, helpers, or state.

## References

- [docs/decisions/0001-home-assistant-integration-plus-worker.md](../decisions/0001-home-assistant-integration-plus-worker.md)
- [docs/decisions/0005-schema-driven-contracts-and-history-normalization.md](../decisions/0005-schema-driven-contracts-and-history-normalization.md)
- [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../decisions/0008-read-only-mvp-and-sandbox-security.md)
- [docs/decisions/0012-worker-transport-and-authentication.md](../decisions/0012-worker-transport-and-authentication.md)
- [docs/schemas/integration-worker-readiness.schema.json](../schemas/integration-worker-readiness.schema.json)
