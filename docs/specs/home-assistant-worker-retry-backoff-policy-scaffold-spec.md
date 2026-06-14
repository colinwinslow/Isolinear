---
status: draft
date: 2026-06-09
depends-on-adrs:
  - 0001
  - 0005
  - 0006
  - 0008
  - 0012
---

# Home Assistant Integration: Worker Retry/Backoff Policy Scaffold Anchor

## Status

Draft. Defines the first minimal integration-owned worker retry/backoff policy
surface after worker dispatch/rendering and worker progress per ADR-0001,
ADR-0005, ADR-0006, ADR-0008, and ADR-0012.

## Related Docs

- [bdd/integration/home-assistant-worker-retry-backoff-policy-scaffold-bdd.md](../../bdd/integration/home-assistant-worker-retry-backoff-policy-scaffold-bdd.md) - observable behavior
- [docs/specs/home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-spec.md](home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-spec.md) - adjacent worker dispatch boundary
- [docs/specs/home-assistant-worker-progress-streaming-scaffold-spec.md](home-assistant-worker-progress-streaming-scaffold-spec.md) - adjacent worker progress boundary
- [docs/specs/integration-api-transport-auth-spec.md](integration-api-transport-auth-spec.md) - ADR-0012 worker request contract
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The integration can dispatch one validated render request to a configured
ADR-0012 worker client and can record bounded worker progress before a
successful complete snapshot. Worker failures currently fail closed before
dispatch, render-plan, artifact, or complete-snapshot metadata is stored.

The next smallest retry/backoff behavior is an inspectable metadata envelope
that records whether a worker/render failure is retry eligible and what bounded
manual retry delay the policy would apply. This packet records policy metadata
only. It does not perform an automatic retry, schedule background work, add a
durable queue, probe worker health, rotate tokens, or change worker transport.

## Behavior Contract

The retry/backoff policy boundary must:

- Route only through the existing `isolinear/v1/job/snapshot` worker dispatch
  path after command validation, config-entry scope validation, worker
  readiness, render-request validation, and worker transport validation.
- Operate only after a configured worker client is called for the targeted
  config-entry job.
- Record a schema-valid config-entry-scoped `IntegrationWorkerRetryPolicy`
  envelope when a valid worker render result reports `status: "failed"`.
- Store only redacted worker authorization in retry/backoff metadata and
  evidence.
- Compute deterministic bounded manual retry delays from the attempt number
  using the scaffold policy: 5 seconds, doubling per later recorded failure,
  capped at 60 seconds.
- Mark automatic retry scheduling as false.
- Reject unknown jobs and cross-config-entry jobs before worker calls or
  retry/backoff metadata storage.
- Preserve existing fail-closed worker behavior: no worker dispatch metadata,
  render-plan metadata, artifact metadata, worker progress metadata, or
  complete snapshot is stored for a failed worker render.
- Preserve per-config-entry isolation for retry/backoff policies, worker
  clients, jobs, worker dispatches, render plans, artifacts, and returned
  responses.

The `IntegrationWorkerRetryPolicy` envelope must include:

- `policy_id`
- `type: "isolinear_worker_retry_policy"`
- `config_entry_id`
- `job_id`
- `source_snapshot_id`
- redacted `worker`
- redacted `request`
- `failure`
- `decision`
- `backoff`
- `validation`
- `warnings`

Allowed side effects for this packet are limited to:

- Reading the targeted config-entry job state.
- Reading staged config-entry-scoped approved history already stored by the
  approved history retrieval boundary.
- Reading the configured worker client object and its integration-owned bearer
  token.
- One worker render call for eligible scaffold-ready jobs that do not already
  have a successful complete snapshot.
- New in-memory config-entry-scoped worker retry/backoff policy bookkeeping
  after policy validation for a worker render failure.
- Returning or erroring a WebSocket response for the current command.
- The already-anchored global WebSocket command registration.

The packet remains bounded: it must not read Home Assistant history during
worker retry/backoff handling, persist semantic memory, mutate Home Assistant
services/devices/state/configuration, generate or rotate worker tokens, leak
worker authorization to the dashboard card or model provider, write real chart
artifact files, add durable retry queues/storage, add worker health checks,
start automatic progress tasks, perform automatic retries, add a scheduler, or
introduce a new worker transport.

## Anchor Artifact

The anchor artifact is the inspectable retry/backoff behavior in
`custom_components/isolinear/job_orchestration.py` and
`src/Isolinear/worker_retry_backoff_policy_anchor.py`, which verifies worker
failure policy recording, schema validation, redaction, unknown job rejection,
cross-entry rejection, config-entry isolation, and side-effect boundaries
against fake Home Assistant objects and deterministic fake worker clients.

## Implementation Order

1. Create this spec, paired BDD/evidence scaffold, eval outline, and worker
   retry/backoff policy schema.
2. Add failing unit tests and a Python verifier anchor for accepted worker
   failure policy recording, schema validity, redaction, unknown job rejection,
   cross-entry rejection, isolation, and side-effect boundaries.
3. Add the focused executable eval.
4. Extend production orchestration so failed worker render results record one
   validated retry/backoff policy envelope before returning the existing
   fail-closed response.
5. Verify the real files on disk.

## Proof Requirements

1. Unit tests in `tests/test_worker_retry_backoff_policy_anchor.py` are green.
2. Existing worker progress, worker dispatch/rendering, worker readiness,
   retry continuation, subscription, render-planning, artifact-storage,
   job-state, WebSocket registration, approved-entity-catalog, and
   approved-history tests remain green.
3. `evals/home_assistant_worker_retry_backoff_policy_scaffold.py` emits raw
   `CASE` evidence for the BDD scenarios.
4. Evidence confirms a failed worker render result records one schema-valid
   retry/backoff policy and still fails closed before dispatch, render-plan,
   artifact, progress, or complete-snapshot metadata is stored.
5. Evidence confirms worker authorization is redacted in retry/backoff
   metadata and eval output.
6. Evidence confirms unknown jobs and cross-config-entry jobs fail closed
   before worker calls or retry/backoff metadata storage.
7. Evidence confirms two config entries keep retry/backoff policies and worker
   clients isolated.
8. Evidence confirms no Home Assistant history read during worker
   retry/backoff handling, semantic-memory persistence, Home Assistant
   mutation, token generation, token rotation, token leakage, real artifact
   write, durable retry queue/storage, worker health check, automatic retry,
   automatic progress task, scheduler, or new worker transport occurs.
9. Real artifacts are verified on disk: production orchestration module,
   worker retry/backoff schema, BDD, eval outline, tests, eval, evidence, and
   verifier anchor.

## Non-Goals

- Automatic retry loops, timers, schedulers, delayed tasks, or durable queues.
- Worker health checks, readiness HTTP probes, token rotation, or repair UI.
- Changing the card-facing WebSocket command schema.
- Appending a worker-failure job snapshot or changing the existing
  user-triggered `job/retry` continuation path.
- Worker progress streaming changes.
- Durable job, render-plan, dispatch, retry-policy, or artifact persistence.
- Integration-side chart file writes or public artifact download routes.
- Semantic-memory persistence, migrations, alias reuse, or repair UI.
- Creating, editing, or deleting Home Assistant dashboards, devices, services,
  automations, scenes, helpers, or state.

## References

- [docs/decisions/0001-home-assistant-integration-plus-worker.md](../decisions/0001-home-assistant-integration-plus-worker.md)
- [docs/decisions/0005-schema-driven-contracts-and-history-normalization.md](../decisions/0005-schema-driven-contracts-and-history-normalization.md)
- [docs/decisions/0006-validation-and-repair-loop.md](../decisions/0006-validation-and-repair-loop.md)
- [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../decisions/0008-read-only-mvp-and-sandbox-security.md)
- [docs/decisions/0012-worker-transport-and-authentication.md](../decisions/0012-worker-transport-and-authentication.md)
- [docs/schemas/integration-worker-retry-policy.schema.json](../schemas/integration-worker-retry-policy.schema.json)
- [docs/schemas/worker-transport-request.schema.json](../schemas/worker-transport-request.schema.json)
- [docs/schemas/render-request.schema.json](../schemas/render-request.schema.json)
- [docs/schemas/render-result.schema.json](../schemas/render-result.schema.json)
