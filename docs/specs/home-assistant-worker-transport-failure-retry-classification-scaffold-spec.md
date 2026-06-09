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

# Home Assistant Integration: Worker Transport Failure Retry Classification Scaffold Anchor

## Status

Draft. Defines the first minimal integration-owned worker transport failure
retry classification surface after worker dispatch/rendering and worker
retry/backoff policy metadata per ADR-0001, ADR-0005, ADR-0006, ADR-0008, and
ADR-0012.

## Related Docs

- [bdd/integration/home-assistant-worker-transport-failure-retry-classification-scaffold-bdd.md](../../bdd/integration/home-assistant-worker-transport-failure-retry-classification-scaffold-bdd.md) - observable behavior
- [docs/specs/home-assistant-worker-retry-backoff-policy-scaffold-spec.md](home-assistant-worker-retry-backoff-policy-scaffold-spec.md) - adjacent valid worker render failure policy boundary
- [docs/specs/home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-spec.md](home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-spec.md) - adjacent worker dispatch boundary
- [docs/specs/integration-api-transport-auth-spec.md](integration-api-transport-auth-spec.md) - ADR-0012 worker request contract
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The integration can dispatch a validated render request to a configured
ADR-0012 worker client. Valid worker `RenderResult` envelopes that report
`status: "failed"` now record a schema-valid retry/backoff policy. The
remaining adjacent gap is a worker-client response that returns
`accepted: false` before a valid render result exists, such as HTTP errors,
connection errors, and malformed worker responses.

This packet records transport failure classification metadata only. It does
not perform an automatic retry, schedule background work, add durable retry
storage, probe worker health, rotate tokens, add a new worker transport, or
change the user-triggered retry command.

## Behavior Contract

The worker transport failure classification boundary must:

- Route only through the existing `isolinear/v1/job/snapshot` worker dispatch
  path after command validation, config-entry scope validation, worker
  readiness, render-request validation, and worker transport validation.
- Operate only after a configured worker client is called for the targeted
  config-entry job and returns `accepted: false`.
- Record a schema-valid config-entry-scoped
  `IntegrationWorkerTransportFailureClassification` envelope for connection,
  HTTP, malformed-response, and unknown transport failures.
- Store only redacted worker authorization in classification metadata and
  evidence.
- Sanitize worker-originated failure codes and messages before storing
  classification metadata or returning a command response.
- Compute deterministic bounded manual retry delays from the attempt number
  using the scaffold policy: 5 seconds, doubling per later recorded transport
  failure, capped at 60 seconds for retry-eligible failures; non-retry-eligible
  failures record a zero delay.
- Mark automatic retry scheduling as false.
- Reject unknown jobs and cross-config-entry jobs before worker calls or
  classification metadata storage.
- Preserve existing fail-closed worker behavior: no worker dispatch metadata,
  render-plan metadata, artifact metadata, worker progress metadata,
  worker-render retry policy, or complete snapshot is stored for a transport
  failure.
- Preserve per-config-entry isolation for transport failure classifications,
  worker clients, jobs, worker dispatches, retry policies, render plans,
  artifacts, and returned responses.

The `IntegrationWorkerTransportFailureClassification` envelope must include:

- `classification_id`
- `type: "isolinear_worker_transport_failure_classification"`
- `config_entry_id`
- `job_id`
- `source_snapshot_id`
- redacted `worker`
- redacted `request`
- sanitized `failure`
- `classification`
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
- New in-memory config-entry-scoped worker transport failure classification
  bookkeeping after classification validation for a worker transport failure.
- Returning or erroring a WebSocket response for the current command.
- The already-anchored global WebSocket command registration.

The packet remains bounded: it must not read Home Assistant history during
worker transport failure handling, persist semantic memory, mutate Home
Assistant services/devices/state/configuration, generate or rotate worker
tokens, leak worker authorization to the dashboard card or model provider,
write real chart artifact files, add durable retry queues/storage, add worker
health checks, start automatic progress tasks, perform automatic retries, add
a scheduler, introduce a new worker transport, or change worker render-result
retry policy behavior.

## Anchor Artifact

The anchor artifact is the inspectable transport failure classification
behavior in `custom_components/isolinear/job_orchestration.py` and
`src/Isolinear/worker_transport_failure_classification_anchor.py`, which
verifies classification recording, schema validation, failure-family mapping,
redaction, unknown job rejection, cross-entry rejection, config-entry
isolation, and side-effect boundaries against fake Home Assistant objects and
deterministic fake worker clients.

## Implementation Order

1. Create this spec, paired BDD/evidence scaffold, eval outline, and worker
   transport failure classification schema.
2. Add failing unit tests and a Python verifier anchor for accepted transport
   classification recording, schema validity, connection/HTTP/malformed
   failure-family mapping, redaction, unknown job rejection, cross-entry
   rejection, isolation, and side-effect boundaries.
3. Add the focused executable eval.
4. Extend production orchestration so `accepted: false` worker responses record
   one validated transport failure classification envelope before returning
   the existing fail-closed response.
5. Verify the real files on disk.

## Proof Requirements

1. Unit tests in
   `tests/test_worker_transport_failure_classification_anchor.py` are green.
2. Existing worker retry/backoff policy, worker progress, worker
   dispatch/rendering, worker readiness, retry continuation, subscription,
   render-planning, artifact-storage, job-state, WebSocket registration,
   approved-entity-catalog, and approved-history tests remain green.
3. `evals/home_assistant_worker_transport_failure_retry_classification_scaffold.py`
   emits raw `CASE` evidence for the BDD scenarios.
4. Evidence confirms `accepted: false` connection, HTTP, and malformed worker
   responses record schema-valid transport failure classifications.
5. Evidence confirms worker authorization and worker-originated secret-like
   failure codes/messages are redacted before classification storage and eval
   output.
6. Evidence confirms unknown jobs and cross-config-entry jobs fail closed
   before worker calls or classification metadata storage.
7. Evidence confirms two config entries keep transport classifications and
   worker clients isolated.
8. Evidence confirms no Home Assistant history read during worker transport
   failure handling, semantic-memory persistence, Home Assistant mutation,
   token generation, token rotation, token leakage, real artifact write,
   durable retry queue/storage, worker health check, automatic retry,
   automatic progress task, scheduler, new worker transport, or worker
   render-result retry policy change occurs.
9. Real artifacts are verified on disk: production orchestration module,
   worker transport failure classification schema, BDD, eval outline, tests,
   eval, evidence, and verifier anchor.

## Non-Goals

- Automatic retry loops, timers, schedulers, delayed tasks, or durable queues.
- Worker health checks, readiness HTTP probes, token rotation, or repair UI.
- Changing the card-facing WebSocket command schema.
- Appending a worker-failure job snapshot or changing the existing
  user-triggered `job/retry` continuation path.
- Replacing valid failed `RenderResult` retry/backoff policy behavior.
- Worker progress streaming changes.
- Durable job, render-plan, dispatch, retry-policy, classification, or
  artifact persistence.
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
- [docs/schemas/integration-worker-transport-failure-classification.schema.json](../schemas/integration-worker-transport-failure-classification.schema.json)
- [docs/schemas/worker-transport-request.schema.json](../schemas/worker-transport-request.schema.json)
- [docs/schemas/render-request.schema.json](../schemas/render-request.schema.json)
- [docs/schemas/render-result.schema.json](../schemas/render-result.schema.json)
