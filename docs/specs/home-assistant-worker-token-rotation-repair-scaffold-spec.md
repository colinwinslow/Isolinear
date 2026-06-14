---
status: draft
date: 2026-06-10
depends-on-adrs:
  - 0001
  - 0005
  - 0008
  - 0012
  - 0014
---

# Home Assistant Integration: Worker Token Rotation/Repair Scaffold Anchor

## Status

Draft. Defines the smallest explicit Home Assistant integration-owned worker
token rotation and repair scaffold per ADR-0001, ADR-0005, ADR-0008,
ADR-0012, and ADR-0014.

## Related Docs

- [bdd/integration/home-assistant-worker-token-rotation-repair-scaffold-bdd.md](../../bdd/integration/home-assistant-worker-token-rotation-repair-scaffold-bdd.md) - observable behavior
- [docs/specs/integration-api-transport-auth-spec.md](integration-api-transport-auth-spec.md) - worker HTTP envelope and bearer-token contract
- [docs/specs/home-assistant-worker-token-provisioning-readiness-scaffold-spec.md](home-assistant-worker-token-provisioning-readiness-scaffold-spec.md) - existing worker token/readiness gate
- [docs/specs/home-assistant-worker-health-readiness-endpoint-scaffold-spec.md](home-assistant-worker-health-readiness-endpoint-scaffold-spec.md) - adjacent explicit worker health probe
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The integration can explicitly provision one in-memory integration-owned worker
token, record redacted readiness metadata, gate worker renderer setup, and
explicitly probe worker health. The next bounded behavior is an explicit
config-entry-scoped rotation/repair surface that can replace stale or missing
in-memory token material, validate redacted readiness metadata, refresh the
same-entry worker renderer client, and roll back if validation/storage fails.

This packet does not add durable token storage, automatic rotation, a repair UI,
health polling, retry queues, schedulers, or dashboard-card commands. Rotation
and repair are direct integration-owned operations for future setup/repair
flows.

## Behavior Contract

The worker token rotation/repair boundary must:

- Provide an explicit config-entry-scoped rotation function that requires an
  existing valid worker token, generates a new integration-owned token,
  invalidates the old in-memory token and same-entry worker renderer client,
  validates/stores new redacted readiness metadata, and refreshes the
  same-entry worker renderer setup.
- Provide an explicit config-entry-scoped repair function that can create a
  valid token for a known entry with a configured worker endpoint when no valid
  token is present, then validate/store redacted readiness metadata and enable
  the same-entry worker renderer setup.
- Reject unknown config entries before token generation, token storage,
  readiness metadata, worker renderer setup, or health/render calls.
- Reject cross-entry token rotation or repair requests before token generation,
  token storage, readiness metadata, worker renderer setup, or health/render
  calls.
- Reject entries without a configured worker endpoint before token generation
  or token storage.
- Roll back the previous token, readiness metadata, readiness setup, worker
  renderer client, and worker renderer setup if readiness validation/storage
  fails after a candidate token is generated.
- Store only redacted bearer metadata as `Bearer <redacted>` in readiness
  metadata, setup results, eval output, and verifier output.
- Keep rotation/repair metadata, worker tokens, readiness, worker renderer
  clients, and setup results isolated per config entry.
- Avoid exposing worker endpoint, token material, readiness metadata, health
  metadata, repair internals, or rotation internals to dashboard-card WebSocket
  payloads.

Allowed side effects for this packet are limited to:

- Reading the targeted config entry and worker endpoint configuration.
- Reading and replacing one in-memory integration-owned worker token only
  during explicit rotation or repair.
- Reading and writing one in-memory config-entry-scoped readiness envelope
  after validation.
- Clearing and recreating the same-entry worker renderer client during
  successful rotation or repair.
- Existing setup bookkeeping for the targeted config entry.

The packet remains bounded: it must not mutate Home Assistant
services/devices/state/configuration, read Home Assistant history, persist
semantic memory, call worker render, call worker health, render charts, write
chart artifacts, add durable token storage, add durable health or retry
storage, schedule automatic health checks or retries, start automatic progress
tasks, introduce a new transport mechanism, or expose worker token/readiness
internals to the dashboard card.

## Anchor Artifact

The anchor artifact is the inspectable rotation/repair behavior in
`custom_components/isolinear/worker_readiness.py` and
`src/Isolinear/worker_token_rotation_repair_anchor.py`, which verifies old-token
invalidation, new-token readiness metadata, missing-token repair,
validation-failure rollback, unknown-entry rejection, cross-entry rejection,
redaction, card-safety, config-entry isolation, renderer refresh, and bounded
side effects against fake Home Assistant config entries and deterministic token
factories.

## Implementation Order

1. Create this spec, paired BDD/evidence scaffold, and eval outline.
2. Add failing unit tests and a Python verifier anchor for rotation, repair,
   rollback, unknown and cross-entry rejection, redaction, card-safety,
   isolation, renderer refresh, and side-effect boundaries.
3. Add the focused executable eval.
4. Add the smallest production worker token rotation/repair functions using
   the existing readiness schema.
5. Verify the real files on disk.

## Proof Requirements

1. Unit tests in `tests/test_worker_token_rotation_repair_anchor.py` are green.
2. Existing worker token/readiness, worker health/readiness, worker dispatch,
   worker progress, retry/backoff, transport-classification, and
   failure-snapshot/manual-retry tests remain green.
3. `evals/home_assistant_worker_token_rotation_repair_scaffold.py` emits raw
   `CASE` evidence for the BDD scenarios.
4. Evidence confirms explicit rotation invalidates the old in-memory worker
   token and old renderer client, stores one schema-valid `ready` readiness
   envelope for the new token, and refreshes same-entry worker renderer setup.
5. Evidence confirms explicit repair creates a valid token for a known
   no-token entry, stores schema-valid ready readiness metadata, and enables
   renderer setup.
6. Evidence confirms readiness validation/storage failure rolls back the old
   token, old readiness metadata, old readiness setup, old renderer client,
   and old renderer setup.
7. Evidence confirms unknown and cross-entry requests fail before token
   generation, token storage, readiness writes, renderer refresh, worker
   render calls, or worker health calls.
8. Evidence confirms no raw token appears in readiness metadata, setup
   results, eval output, dashboard WebSocket registration metadata, model
   provider setup metadata, or user-visible payloads.
9. Evidence confirms dashboard-card WebSocket payloads do not expose worker
   endpoint, token material, readiness metadata, health metadata, rotation
   internals, or repair internals.
10. Evidence confirms no Home Assistant history read, semantic-memory
    persistence, Home Assistant service/device/state mutation, worker render
    call, worker health call, chart rendering, chart artifact write, durable
    storage, retry queue, scheduler, automatic retry, or automatic progress
    task occurs.
11. Real artifacts are verified on disk: production readiness module, BDD,
    eval outline, tests, eval, evidence, and verifier anchor.

## Non-Goals

- Persistent worker token storage, migrations, or repair UI.
- Automatic or scheduled token rotation.
- Automatic or scheduled worker health polling.
- Durable health state, retry queues, or scheduler behavior.
- Worker render endpoint behavior changes.
- Changing card-facing WebSocket command schemas or adding dashboard
  rotation/repair commands.
- Passing worker endpoint, request details, readiness metadata, health
  metadata, or token material to the dashboard card or model provider.
- Creating, editing, or deleting Home Assistant dashboards, devices, services,
  automations, scenes, helpers, or state.

## References

- [docs/decisions/0001-home-assistant-integration-plus-worker.md](../decisions/0001-home-assistant-integration-plus-worker.md)
- [docs/decisions/0005-schema-driven-contracts-and-history-normalization.md](../decisions/0005-schema-driven-contracts-and-history-normalization.md)
- [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../decisions/0008-read-only-mvp-and-sandbox-security.md)
- [docs/decisions/0012-worker-transport-and-authentication.md](../decisions/0012-worker-transport-and-authentication.md)
- [docs/decisions/0014-worker-health-readiness-endpoint.md](../decisions/0014-worker-health-readiness-endpoint.md)
- [docs/schemas/integration-worker-readiness.schema.json](../schemas/integration-worker-readiness.schema.json)
