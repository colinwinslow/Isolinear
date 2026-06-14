---
status: draft
date: 2026-06-13
depends-on-adrs:
  - 0001
  - 0005
  - 0008
  - 0011
  - 0012
  - 0014
  - 0015
  - 0016
---

# Home Assistant Integration: Durable Worker Token Lifecycle Scaffold Anchor

## Status

Draft. Defines the first production Home Assistant integration-owned durable
worker token lifecycle scaffold per ADR-0001, ADR-0005, ADR-0008, ADR-0011,
ADR-0012, ADR-0014, ADR-0015, and draft ADR-0016.

## Related Docs

- [bdd/integration/home-assistant-durable-worker-token-lifecycle-scaffold-bdd.md](../../bdd/integration/home-assistant-durable-worker-token-lifecycle-scaffold-bdd.md) - observable behavior
- [docs/specs/home-assistant-worker-token-provisioning-readiness-scaffold-spec.md](home-assistant-worker-token-provisioning-readiness-scaffold-spec.md) - in-memory readiness gate
- [docs/specs/home-assistant-worker-token-rotation-repair-scaffold-spec.md](home-assistant-worker-token-rotation-repair-scaffold-spec.md) - explicit in-memory rotation/repair boundary
- [docs/specs/home-assistant-durable-worker-health-polling-scaffold-spec.md](home-assistant-durable-worker-health-polling-scaffold-spec.md) - adjacent durable polling boundary
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The integration can explicitly provision, rotate, and repair one
config-entry-scoped in-memory worker token and can poll worker health
durably. It does not yet restore worker tokens after Home Assistant restart or
record a safe user-facing repair issue when token repair cannot happen
automatically.

This packet adds the smallest durable lifecycle scaffold for integration-owned
worker tokens. It persists token material only inside an integration-owned
storage-helper surface, validates and stores only redacted lifecycle metadata,
restores a valid persisted token during setup before readiness is evaluated,
and records a schema-valid repair-issue envelope when no valid token can be
restored. It does not execute health-polling repair recommendations or
generate replacement tokens during setup.

## Behavior Contract

The durable worker token lifecycle boundary must:

- Define an `IntegrationWorkerTokenLifecycleState` JSON Schema for redacted,
  config-entry-scoped token lifecycle and repair-issue metadata.
- Initialize one integration-owned storage-helper surface for durable worker
  token entries. In production Home Assistant this wraps the Home Assistant
  versioned storage helper; verifier and fake-HA tests may use the same
  JSON-safe surface with in-memory storage.
- Keep raw worker token material only inside the private lifecycle store and
  in the existing in-memory worker renderer token slot. Raw token material must
  not appear in lifecycle state, setup results, repair issue metadata,
  evidence, dashboard WebSocket payloads, or model-provider metadata.
- During config-entry setup, load persisted lifecycle entries before worker
  readiness and worker renderer setup run.
- Restore a valid persisted same-entry worker token into memory when the entry
  has a configured worker endpoint and no valid in-memory worker token.
- Record schema-valid redacted `ready` lifecycle state for restored tokens
  and clear stale repair-issue metadata.
- Record schema-valid redacted `not_ready` lifecycle state with repair-issue
  metadata when a configured entry has no valid in-memory token and no valid
  persisted token.
- Record schema-valid redacted `disabled` lifecycle state without a repair
  issue when the entry has no configured worker endpoint.
- Skip persisted entries whose config entry id does not match, whose redacted
  lifecycle state fails schema validation, or whose raw token is malformed.
- Leave durable worker health polling `token_repair_available`
  recommendations diagnostic-only; this packet does not execute them.
- Provide durable explicit provisioning, rotation, and repair wrappers that
  call the existing in-memory operations, persist the resulting valid token
  only after success, validate redacted lifecycle state before durable writes,
  and leave old durable state intact if lifecycle validation/storage fails.
- Keep durable token lifecycle state, raw token entries, readiness, renderer
  clients, and repair issues isolated per config entry.
- Avoid exposing worker endpoint URLs, raw tokens, bearer authorization,
  lifecycle state, repair issue metadata, or rotation/repair internals to
  dashboard-card WebSocket payloads.

Allowed side effects for this packet are limited to:

- Reading the targeted config entry and worker endpoint configuration.
- Loading, reading, writing, and deleting integration-owned worker token
  lifecycle storage-helper entries.
- Restoring one valid persisted integration-owned worker token into the
  existing in-memory worker renderer token slot during setup.
- Calling the existing explicit in-memory provisioning, rotation, and repair
  functions only through new explicit durable lifecycle wrappers.
- Writing one redacted config-entry-scoped lifecycle state after schema
  validation. Setup-time restore from a valid persisted token is the only
  automatic repair-like behavior in this packet.
- Existing same-entry readiness and worker renderer setup after token restore
  or explicit durable token operations.

The packet remains bounded: it must not mutate Home Assistant
services/devices/state/configuration, write config-entry options, use Recorder,
read Home Assistant history, persist semantic memory, call worker render, call
worker health, call model providers, render charts, write chart artifacts,
create durable retry queues, start scheduler tasks, schedule automatic
rotation, generate new tokens during setup, register real Home Assistant
Repairs flows, add dashboard-card commands, or expose worker token lifecycle
internals to the dashboard card.

## Anchor Artifact

The anchor artifact is the inspectable durable token lifecycle behavior in
`custom_components/isolinear/worker_token_lifecycle.py` and
`src/Isolinear/worker_token_lifecycle_anchor.py`, which verifies durable token
restore before readiness setup, no-token repair-issue metadata, disabled
entries, durable explicit provision/rotation/repair persistence, invalid
persisted entry rejection, validation-failure rollback, redaction, card-safety,
config-entry isolation, and bounded side effects.

## Implementation Order

1. Create ADR-0016, this spec, paired BDD/evidence scaffold, eval outline, and
   lifecycle-state schema.
2. Add failing unit tests and a Python verifier anchor for setup restore,
   no-token repair issue metadata, disabled setup, durable explicit operations,
   invalid persisted state rejection, validation/storage rollback, redaction,
   card-safety, isolation, and side-effect boundaries.
3. Add the focused executable eval.
4. Add the smallest production worker token lifecycle module and setup wiring
   before worker readiness setup.
5. Verify the real files on disk.

## Proof Requirements

1. Unit tests in `tests/test_worker_token_lifecycle_anchor.py` are green.
2. Existing worker token/readiness, token rotation/repair, worker health,
   durable polling, worker dispatch, worker progress, retry/backoff,
   transport-classification, and failure-snapshot/manual-retry tests remain
   green.
3. `evals/home_assistant_durable_worker_token_lifecycle_scaffold.py` emits raw
   `CASE` evidence for the BDD scenarios.
4. Evidence confirms setup restores a valid persisted token before worker
   readiness setup and enables the same-entry worker renderer without
   generating a new token or calling the worker.
5. Evidence confirms configured entries without an in-memory or persisted
   token record schema-valid repair-issue metadata without generating a token.
6. Evidence confirms entries without worker endpoints record schema-valid
   disabled lifecycle state without repair issue metadata.
7. Evidence confirms durable explicit provision, rotation, and repair wrappers
   persist valid token material privately and store only redacted lifecycle
   metadata.
8. Evidence confirms invalid persisted tokens, mismatched entry ids, and
   malformed lifecycle metadata are skipped before memory restore.
9. Evidence confirms setup-time lifecycle storage failures block token restore
   before readiness or renderer setup while leaving previous durable token state
   intact.
10. Evidence confirms explicit operation lifecycle validation/storage failures
   leave previous durable token state and in-memory token/readiness/renderer
   state intact.
11. Evidence confirms two config entries keep raw token entries, redacted
    lifecycle state, readiness, renderer clients, and repair issues isolated.
12. Evidence confirms no raw token appears in lifecycle state, setup results,
    repair issue metadata, eval output, dashboard WebSocket registration
    metadata, model provider metadata, or user-visible payloads.
13. Evidence confirms dashboard-card WebSocket payloads do not expose worker
    endpoint URLs, token material, bearer authorization, lifecycle state,
    repair issue metadata, or rotation/repair internals.
14. Evidence confirms no Home Assistant history read, semantic-memory
    persistence, Home Assistant service/device/state mutation, config-entry
    option write, Recorder write, worker render call, worker health call,
    model-provider call, chart rendering, chart artifact write, durable retry
    queue, external queue/database, scheduler task, automatic rotation,
    automatic token repair execution, setup-time token generation, or
    dashboard-card command registration occurs.
15. Real artifacts are verified on disk: production lifecycle module,
    integration setup wiring, lifecycle-state schema, BDD, eval outline, tests,
    eval, evidence, and verifier anchor.

## Non-Goals

- Registering a real Home Assistant Repairs flow.
- Adding dashboard-card token lifecycle, repair, or rotation commands.
- Generating a new worker token automatically during config-entry setup.
- Executing durable health polling repair recommendations automatically.
- Token expiration, age policy, or scheduled token rotation.
- Add-on-mediated token exchange.
- Worker render or health endpoint behavior changes.
- Provider health/retry policy or durable job retry queues.
- Passing worker endpoint, request details, lifecycle metadata, repair issue
  metadata, or token material to the dashboard card or model provider.
- Creating, editing, or deleting Home Assistant dashboards, devices, services,
  automations, scenes, helpers, or state.

## References

- [docs/decisions/0001-home-assistant-integration-plus-worker.md](../decisions/0001-home-assistant-integration-plus-worker.md)
- [docs/decisions/0005-schema-driven-contracts-and-history-normalization.md](../decisions/0005-schema-driven-contracts-and-history-normalization.md)
- [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../decisions/0008-read-only-mvp-and-sandbox-security.md)
- [docs/decisions/0011-dashboard-card-implementation-technology.md](../decisions/0011-dashboard-card-implementation-technology.md)
- [docs/decisions/0012-worker-transport-and-authentication.md](../decisions/0012-worker-transport-and-authentication.md)
- [docs/decisions/0014-worker-health-readiness-endpoint.md](../decisions/0014-worker-health-readiness-endpoint.md)
- [docs/decisions/0015-durable-worker-health-polling.md](../decisions/0015-durable-worker-health-polling.md)
- [docs/decisions/0016-durable-worker-token-lifecycle.md](../decisions/0016-durable-worker-token-lifecycle.md)
- [docs/schemas/integration-worker-token-lifecycle-state.schema.json](../schemas/integration-worker-token-lifecycle-state.schema.json)
