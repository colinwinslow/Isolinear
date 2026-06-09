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

# Home Assistant Integration: Worker Failure Snapshot/Manual Retry Integration Scaffold Anchor

## Status

Draft. Defines the smallest card-facing worker failure snapshot and manual
retry integration surface after worker retry/backoff policy and worker
transport failure classification metadata per ADR-0001, ADR-0005, ADR-0006,
ADR-0008, and ADR-0012.

## Related Docs

- [bdd/integration/home-assistant-worker-failure-snapshot-manual-retry-integration-scaffold-bdd.md](../../bdd/integration/home-assistant-worker-failure-snapshot-manual-retry-integration-scaffold-bdd.md) - observable behavior
- [docs/specs/home-assistant-worker-retry-backoff-policy-scaffold-spec.md](home-assistant-worker-retry-backoff-policy-scaffold-spec.md) - worker render failure policy envelope
- [docs/specs/home-assistant-worker-transport-failure-retry-classification-scaffold-spec.md](home-assistant-worker-transport-failure-retry-classification-scaffold-spec.md) - worker transport failure classification envelope
- [docs/specs/home-assistant-job-orchestration-retry-continuation-scaffold-spec.md](home-assistant-job-orchestration-retry-continuation-scaffold-spec.md) - existing manual retry command behavior
- [docs/specs/integration-api-transport-auth-spec.md](integration-api-transport-auth-spec.md) - ADR-0012 worker request contract
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The integration can record redacted worker retry/backoff policy metadata for
valid failed `RenderResult` envelopes and redacted transport failure
classification metadata for `accepted: false` worker-client responses. Those
internal records currently stop the snapshot command before the dashboard card
receives a failed `IntegrationJobSnapshot`.

The next smallest user-visible bridge is to convert those already-validated
worker failure envelopes into a schema-valid failed job snapshot that contains
only card-safe failure and retry-affordance fields. The existing
`isolinear/v1/job/retry` command can then target the failed snapshot when
manual retry is allowed.

## Behavior Contract

The worker failure snapshot/manual retry boundary must:

- Route only through the existing `isolinear/v1/job/snapshot` worker dispatch
  path after command validation, config-entry scope validation, worker
  readiness, render-request validation, worker transport validation, and
  existing worker failure metadata validation.
- Append one schema-valid failed `IntegrationJobSnapshot` when a worker render
  failure records an `IntegrationWorkerRetryPolicy` envelope.
- Append one schema-valid failed `IntegrationJobSnapshot` when a worker
  transport failure records an
  `IntegrationWorkerTransportFailureClassification` envelope.
- Use only sanitized failure stage/code/message values from those envelopes in
  the card-facing snapshot.
- Set `retry_allowed` from the existing manual retry decision:
  `IntegrationWorkerRetryPolicy.decision.manual_retry_allowed` for render
  failures and
  `IntegrationWorkerTransportFailureClassification.classification.manual_retry_allowed`
  for transport failures.
- Keep the dashboard-card payload limited to `IntegrationJobSnapshot`; worker
  endpoint, worker request body, bearer authorization, retry-policy metadata,
  transport-classification metadata, render-plan metadata, artifact metadata,
  and worker dispatch metadata must not be included in the card-facing
  snapshot or WebSocket result payload.
- Preserve existing unknown-job and cross-config-entry rejection before worker
  calls, worker failure metadata storage, failed snapshot append, or manual
  retry.
- Reuse the existing `isolinear/v1/job/retry` command for manual retry of
  retryable worker failure snapshots.
- Keep non-retry-safe worker transport failures non-retryable.
- Preserve per-config-entry isolation for jobs, failed snapshots, retry
  commands, retry policies, transport classifications, worker clients, and
  returned responses.

Allowed side effects for this packet are limited to:

- Reading the targeted config-entry job state.
- Reading staged config-entry-scoped approved history already stored by the
  approved history retrieval boundary during worker snapshot handling.
- Reading approved catalog/history through the existing retry-continuation
  path only after a user-triggered `job/retry` command targets a retryable
  failed worker snapshot.
- Reading the configured worker client object and its integration-owned bearer
  token.
- One worker render call for eligible scaffold-ready jobs that do not already
  have a successful complete or failed worker snapshot.
- Existing in-memory config-entry-scoped worker retry/backoff policy or worker
  transport failure classification bookkeeping after those contracts validate.
- One failed job snapshot append after the existing worker failure metadata
  contract validates.
- Returning a card-facing WebSocket result containing only the failed
  `IntegrationJobSnapshot`.
- The already-anchored global WebSocket command registration.

The packet remains bounded: it must not read Home Assistant history during
worker failure snapshot handling, persist semantic memory, mutate Home
Assistant services/devices/state/configuration, generate or rotate worker
tokens, leak worker authorization to the dashboard card or model provider,
write real chart artifact files, add durable retry queues/storage, add worker
health checks, start automatic progress tasks, perform automatic retries, add
a scheduler, introduce a new worker transport, or expose worker policy or
classification internals to the dashboard card.

## Anchor Artifact

The anchor artifact is the inspectable card-facing failed
`IntegrationJobSnapshot` behavior in
`custom_components/isolinear/job_orchestration.py` and
`src/Isolinear/worker_failure_snapshot_manual_retry_anchor.py`, which verifies
worker render failure snapshots, worker transport failure snapshots, manual
retry continuation, non-retry-safe transport behavior, schema validation,
redaction, unknown job rejection, cross-entry rejection, config-entry
isolation, and side-effect boundaries against fake Home Assistant objects and
deterministic fake worker clients.

## Implementation Order

1. Create this spec, paired BDD/evidence scaffold, and eval outline.
2. Add failing unit tests and a Python verifier anchor for failed snapshot
   creation, manual retry continuation, card-safe redaction, unknown job
   rejection, cross-entry rejection, isolation, and side-effect boundaries.
3. Add the focused executable eval.
4. Extend production orchestration so existing worker failure metadata records
   append one validated failed snapshot and return it to the dashboard card.
5. Update adjacent worker retry/backoff and transport classification anchors
   for the evolved card-facing behavior while preserving their metadata
   invariants.
6. Verify the real files on disk.

## Proof Requirements

1. Unit tests in
   `tests/test_worker_failure_snapshot_manual_retry_anchor.py` are green.
2. Adjacent worker retry/backoff policy, worker transport classification,
   worker progress, worker dispatch/rendering, worker readiness, retry
   continuation, subscription, render-planning, artifact-storage, job-state,
   WebSocket registration, approved-entity-catalog, and approved-history tests
   remain green.
3. `evals/home_assistant_worker_failure_snapshot_manual_retry_integration_scaffold.py`
   emits raw `CASE` evidence for the BDD scenarios.
4. Evidence confirms worker render failures and transport failures produce
   schema-valid failed `IntegrationJobSnapshot` payloads with sanitized
   failure details and manual retry affordance metadata.
5. Evidence confirms a user-triggered `job/retry` resumes a retryable worker
   failure snapshot through the existing retry-continuation path.
6. Evidence confirms non-retry-safe transport failures produce failed
   snapshots with `retry_allowed: false` and reject manual retry before
   history reads.
7. Evidence confirms the card-facing payload excludes worker endpoint, worker
   request body, bearer token, retry-policy metadata, transport
   classification metadata, render-plan metadata, artifact metadata, and
   worker dispatch metadata.
8. Evidence confirms unknown jobs and cross-config-entry jobs fail closed
   before worker calls, failed snapshot append, or manual retry.
9. Evidence confirms no Home Assistant history read during worker failure
   snapshot handling, semantic-memory persistence, Home Assistant mutation,
   token generation, token rotation, token leakage, real artifact write,
   durable retry queue/storage, worker health check, automatic retry,
   automatic progress task, scheduler, new worker transport, or worker
   metadata exposure to the card occurs.
10. Real artifacts are verified on disk: production orchestration module, BDD,
    eval outline, tests, eval, evidence, and verifier anchor.

## Non-Goals

- Automatic retry loops, timers, schedulers, delayed tasks, or durable queues.
- Worker health checks, readiness HTTP probes, token rotation, or repair UI.
- Changing the card-facing WebSocket command schema.
- Exposing worker endpoint, worker request bodies, bearer tokens, retry policy
  metadata, transport classification metadata, render-plan metadata, artifact
  metadata, or worker dispatch metadata to the dashboard card.
- Worker progress streaming changes.
- Durable job, render-plan, dispatch, retry-policy, classification, failed
  snapshot, or artifact persistence.
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
- [docs/schemas/integration-job-snapshot.schema.json](../schemas/integration-job-snapshot.schema.json)
- [docs/schemas/integration-worker-retry-policy.schema.json](../schemas/integration-worker-retry-policy.schema.json)
- [docs/schemas/integration-worker-transport-failure-classification.schema.json](../schemas/integration-worker-transport-failure-classification.schema.json)
