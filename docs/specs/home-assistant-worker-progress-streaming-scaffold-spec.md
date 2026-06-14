---
status: draft
date: 2026-06-09
depends-on-adrs:
  - 0001
  - 0003
  - 0004
  - 0005
  - 0006
  - 0008
  - 0012
---

# Home Assistant Integration: Worker Progress Streaming Scaffold Anchor

## Status

Draft. Defines the first production Home Assistant integration-owned worker
progress streaming scaffold after worker token readiness and worker
dispatch/rendering per ADR-0001, ADR-0003, ADR-0004, ADR-0005, ADR-0006,
ADR-0008, and ADR-0012.

## Related Docs

- [bdd/integration/home-assistant-worker-progress-streaming-scaffold-bdd.md](../../bdd/integration/home-assistant-worker-progress-streaming-scaffold-bdd.md) - observable behavior
- [docs/specs/integration-api-transport-auth-spec.md](integration-api-transport-auth-spec.md) - worker HTTP envelope and bearer-token contract
- [docs/specs/home-assistant-job-orchestration-subscription-progress-streaming-scaffold-spec.md](home-assistant-job-orchestration-subscription-progress-streaming-scaffold-spec.md) - card-facing subscription scaffold
- [docs/specs/home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-spec.md](home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-spec.md) - adjacent worker dispatch boundary
- [docs/specs/home-assistant-worker-token-provisioning-readiness-scaffold-spec.md](home-assistant-worker-token-provisioning-readiness-scaffold-spec.md) - worker readiness/token gate
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The integration can create scaffold-ready jobs, record validated render plans,
dispatch one render request through an ADR-0012 worker client, and record a
complete snapshot after a successful worker render result. The card-facing
`isolinear/v1/job/subscribe` path can also record a latest-snapshot progress
event for a config-entry-scoped job.

The next smallest worker-streaming behavior is not a durable stream, polling
loop, retry policy, health check, or new worker transport. This packet records
bounded worker progress events returned through the existing worker render
client response, validates them before storage, appends schema-valid rendering
snapshots, and links those snapshots to any existing config-entry-scoped card
subscriptions for the job. A dashboard card still sees only integration-owned
job snapshots and never receives worker bearer tokens.

## Behavior Contract

The integration must extend the existing worker dispatch/rendering path with a
bounded worker progress event surface.

The worker progress boundary must:

- Route only after deterministic WebSocket command validation, config-entry
  scope validation, and the existing worker readiness/renderer gate.
- Operate only on an existing job in the targeted config entry.
- Reuse the existing ADR-0012 `POST /v1/render` worker request and bearer-token
  header contract; do not add a new transport, worker endpoint, durable queue,
  retry/backoff policy, health check, or automatic progress task.
- Accept worker progress payloads only from the configured worker client for
  the same config entry as part of the worker render response.
- Limit the scaffold to at most five worker progress payloads per render
  response.
- Validate every worker progress payload before appending a job snapshot or
  storing progress metadata.
- Append one schema-valid `IntegrationJobSnapshot` with status `rendering` for
  each accepted worker progress payload before the final complete snapshot.
- Record one schema-valid `IntegrationWorkerProgress` envelope for each
  accepted worker progress payload.
- Include existing job-state subscription IDs for the same job so the progress
  event is visibly tied to the card-facing subscription scaffold.
- Redact worker bearer authorization as `Bearer <redacted>` in stored progress
  metadata and evidence.
- Preserve idempotence: repeated `job/snapshot` calls for an already completed
  worker-progress job return the existing complete snapshot and do not create
  more worker progress events, worker dispatches, render plans, artifacts, or
  worker calls.
- Reject invalid worker progress payloads before worker progress metadata,
  worker dispatch metadata, render-plan metadata, artifact metadata, or
  complete snapshots are stored.
- Reject unknown jobs and cross-config-entry jobs before worker calls or worker
  progress metadata storage.
- Preserve per-config-entry isolation for worker progress events,
  subscriptions, worker clients, dispatches, render plans, artifacts, jobs, and
  returned snapshots.

The `IntegrationWorkerProgress` envelope must include:

- `event_id`
- `type: "isolinear_worker_progress"`
- `config_entry_id`
- `job_id`
- `worker`
- `request_id`
- `sequence`
- `stage`
- `message`
- `percent_complete`
- `subscription_ids`
- `snapshot_id`
- `snapshot`
- `validation`
- `warnings`

Allowed side effects for this packet are limited to:

- Reading the targeted config-entry job state.
- Reading existing config-entry-scoped job-state subscriptions for the same
  job.
- Reading staged config-entry-scoped approved history already stored by the
  approved history retrieval boundary.
- Reading the configured worker client object and its integration-owned bearer
  token.
- One worker render call for eligible scaffold-ready jobs that do not already
  have a complete snapshot and worker dispatch.
- Appending bounded in-memory config-entry-scoped rendering snapshots after
  worker progress validation.
- New in-memory config-entry-scoped worker progress event bookkeeping after
  worker progress validation.
- Existing in-memory config-entry-scoped provider-plan, render-plan, artifact,
  worker-dispatch, and job-state bookkeeping after successful validation.
- Returning or erroring a WebSocket response for the current command.
- The already-anchored global WebSocket command registration.

The packet remains bounded: it must not read Home Assistant history during
worker progress handling, persist semantic memory, mutate Home Assistant
services/devices/state/configuration, generate or rotate worker tokens, leak
worker authorization to the dashboard card or model provider, write real chart
artifact files from the integration, add durable storage, add retry/backoff
policy, add worker health checks, add automatic progress tasks, or add a new
worker streaming transport.

## Anchor Artifact

The anchor artifact is the inspectable worker progress behavior in
`custom_components/isolinear/job_orchestration.py`,
`custom_components/isolinear/worker_renderer.py`, and
`src/Isolinear/worker_progress_streaming_anchor.py`, which verifies accepted
worker progress recording, subscription linkage, schema validation, redaction,
idempotent reuse, invalid progress rejection, unknown job rejection,
cross-entry rejection, per-config-entry isolation, setup/routing, and
side-effect boundaries against fake Home Assistant objects and deterministic
fake worker clients.

## Implementation Order

1. Create this spec, paired BDD/evidence scaffold, eval outline, and worker
   progress schema.
2. Add failing unit tests and a Python verifier anchor for accepted worker
   progress, subscription linkage, schema validity, redaction, idempotent
   reuse, invalid progress rejection, unknown job rejection, cross-entry
   rejection, isolation, and side-effect boundaries.
3. Add the focused executable eval.
4. Extend the worker renderer response surface to carry bounded progress
   payloads without changing the ADR-0012 request contract.
5. Extend production orchestration so eligible worker-dispatched
   `job/snapshot` calls append validated rendering snapshots and store
   `IntegrationWorkerProgress` envelopes before the complete snapshot.
6. Verify the real files on disk.

## Proof Requirements

1. Unit tests in `tests/test_worker_progress_streaming_anchor.py` are green.
2. Existing Home Assistant worker token/readiness, worker dispatch/rendering,
   subscription/progress, model-provider planning, render-planning,
   artifact-storage, job-state, WebSocket registration, approved-entity-catalog,
   and approved-history tests remain green.
3. `evals/home_assistant_worker_progress_streaming_scaffold.py` emits raw
   `CASE` evidence for the BDD scenarios.
4. Evidence confirms a subscribed scaffold-ready job with a configured fake
   worker records schema-valid worker progress events and rendering snapshots
   before the complete snapshot.
5. Evidence confirms worker progress events include existing subscription IDs
   for the same config-entry-scoped job and never include raw worker tokens.
6. Evidence confirms repeated `job/snapshot` requests do not call the worker a
   second time or create duplicate worker progress, worker dispatch, render
   plan, artifact, or complete-snapshot records.
7. Evidence confirms worker progress payloads, worker progress envelopes, job
   snapshots, worker transport requests, render requests, render results,
   render plans, chart specs, history series, and worker dispatch envelopes
   validate before storage.
8. Evidence confirms invalid worker progress payloads, including malformed
   non-list `progress_events` values from HTTP worker responses, fail closed
   before worker progress metadata, worker dispatch metadata, render-plan
   metadata, artifact metadata, or complete snapshots are stored.
9. Evidence confirms unknown jobs and cross-config-entry jobs fail closed
   before worker calls or worker progress metadata storage.
10. Evidence confirms two config entries keep worker progress events,
    subscriptions, worker clients, worker dispatches, render plans, artifact
    metadata, jobs, and orchestration stores isolated.
11. Evidence confirms no Home Assistant history read during worker progress,
    semantic-memory persistence, Home Assistant service/device/state mutation,
    token generation, token rotation, token leakage, real chart artifact file
    write, durable storage, retry/backoff policy, worker health check,
    automatic progress task, or new worker streaming transport occurs.
12. Real artifacts are verified on disk: production orchestration module,
    worker renderer module, worker progress schema, BDD, eval outline, tests,
    eval, evidence, and verifier anchor.

## Non-Goals

- A new worker streaming transport, WebSocket-to-worker bridge, server-sent
  events, persistent stream connection, polling loop, or durable queue.
- Worker token generation, rotation, durable storage, repair, or UI.
- Worker health checks or readiness HTTP probes.
- Retry/backoff policy or automatic retry loops.
- Durable job, progress, render-plan, dispatch, or artifact persistence.
- Integration-side chart file writes or public artifact download routes.
- Semantic-memory persistence, migrations, alias reuse, or repair UI.
- Changing card-facing WebSocket command schemas.
- Passing worker endpoint or token material to the dashboard card or model
  provider.
- Creating, editing, or deleting Home Assistant dashboards, devices, services,
  automations, scenes, helpers, or state.

## References

- [docs/decisions/0001-home-assistant-integration-plus-worker.md](../decisions/0001-home-assistant-integration-plus-worker.md)
- [docs/decisions/0003-entity-allowlist-semantic-resolution-memory.md](../decisions/0003-entity-allowlist-semantic-resolution-memory.md)
- [docs/decisions/0004-chart-spec-first-rendering-with-codegen-option.md](../decisions/0004-chart-spec-first-rendering-with-codegen-option.md)
- [docs/decisions/0005-schema-driven-contracts-and-history-normalization.md](../decisions/0005-schema-driven-contracts-and-history-normalization.md)
- [docs/decisions/0006-validation-and-repair-loop.md](../decisions/0006-validation-and-repair-loop.md)
- [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../decisions/0008-read-only-mvp-and-sandbox-security.md)
- [docs/decisions/0012-worker-transport-and-authentication.md](../decisions/0012-worker-transport-and-authentication.md)
- [docs/schemas/integration-worker-progress.schema.json](../schemas/integration-worker-progress.schema.json)
- [docs/schemas/integration-worker-dispatch.schema.json](../schemas/integration-worker-dispatch.schema.json)
- [docs/schemas/worker-transport-request.schema.json](../schemas/worker-transport-request.schema.json)
- [docs/schemas/render-request.schema.json](../schemas/render-request.schema.json)
- [docs/schemas/render-result.schema.json](../schemas/render-result.schema.json)
- [docs/schemas/integration-job-snapshot.schema.json](../schemas/integration-job-snapshot.schema.json)
