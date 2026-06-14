---
status: draft
date: 2026-06-08
depends-on-adrs:
  - 0001
  - 0003
  - 0005
  - 0006
  - 0008
  - 0011
  - 0012
---

# Home Assistant Integration: Job Orchestration Retry Continuation Scaffold Anchor

## Status

Draft. Defines the first production Home Assistant integration-owned retry
continuation path behind `isolinear/v1/job/retry` per ADR-0001, ADR-0003,
ADR-0005, ADR-0006, ADR-0008, ADR-0011, and ADR-0012.

## Related Docs

- [bdd/integration/home-assistant-job-orchestration-retry-continuation-scaffold-bdd.md](../../bdd/integration/home-assistant-job-orchestration-retry-continuation-scaffold-bdd.md) - observable behavior
- [docs/specs/home-assistant-job-orchestration-scaffold-spec.md](home-assistant-job-orchestration-scaffold-spec.md) - parent `job/start` orchestration scaffold
- [docs/specs/home-assistant-job-orchestration-clarification-continuation-scaffold-spec.md](home-assistant-job-orchestration-clarification-continuation-scaffold-spec.md) - sibling continuation path
- [docs/specs/home-assistant-job-state-scaffold-spec.md](home-assistant-job-state-scaffold-spec.md) - job state dependency
- [docs/specs/home-assistant-approved-entity-catalog-scaffold-spec.md](home-assistant-approved-entity-catalog-scaffold-spec.md) - approved entity catalog dependency
- [docs/specs/home-assistant-approved-history-retrieval-scaffold-spec.md](home-assistant-approved-history-retrieval-scaffold-spec.md) - approved history dependency
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The integration now owns job state, approved entity catalog, approved history
retrieval, `job/start` orchestration, and the first clarification-answer
continuation path. Failed scaffold snapshots can already carry
`retry_allowed: true`, and the card-facing API already includes
`isolinear/v1/job/retry`, but retry currently stops at the generic job-state
scaffold.

The next smallest orchestration behavior is to let a user retry a failed
scaffold job inside the same config entry. This packet remains a scaffold. It
does not implement model repair, worker retries, durable retry queues,
streaming progress, rendering, or artifact lifecycle. It only accepts a
targeted retry for a failed retryable job, reuses the job's original prompt and
current approved catalog/history boundaries, appends schema-valid retry
continuation snapshots, and then stops.

## Behavior Contract

The integration must extend `custom_components/isolinear/job_orchestration.py`
with a small retry continuation boundary.

The retry continuation boundary must:

- Route enabled `isolinear/v1/job/retry` commands through orchestration only
  after deterministic command validation and config-entry scope validation.
- Operate only on an existing job in the targeted config entry.
- Require the job's latest snapshot to be `failed` with `retry_allowed: true`.
- Reject unknown jobs, cross-config-entry jobs, and non-retryable jobs before
  appending retry continuation snapshots or reading Home Assistant history.
- Reuse the existing job prompt as the deterministic retry input.
- Re-run approved entity selection through the current approved entity catalog.
- Retrieve history only through the approved history retrieval boundary after
  entity selection passes the approved catalog gate.
- Append deterministic schema-valid retry continuation snapshots to the same
  job: retry accepted, fetching approved history when the catalog gate passes,
  and scaffold-ready or failed.
- Store one retry continuation run summary under the targeted config entry
  only.
- Validate every `IntegrationJobSnapshot` before storage/return.
- Preserve per-config-entry isolation for jobs, history stores, and
  orchestration run summaries.

Allowed side effects for this packet are limited to:

- Reading the targeted config-entry job state.
- Reading the config-entry approved entity catalog for retryable jobs.
- Reading approved fake Home Assistant history through the history retrieval
  scaffold after the approved catalog gate passes.
- In-memory config-entry-scoped history retrieval store updates.
- In-memory config-entry-scoped job state updates.
- In-memory config-entry-scoped retry continuation bookkeeping.
- Returning or erroring a WebSocket response for the current command.
- The already-anchored global WebSocket command registration.

The retry continuation scaffold must report that no worker, model-provider,
semantic-memory persistence, Home Assistant service/device/state mutation,
token-generation, chart artifact write, chart rendering, durable storage,
subscription progress streaming, or production orchestration occurred. It may
report the user-triggered retry continuation as the only retry behavior in this
packet; it must not implement automatic retry loops, repair retries, or worker
retry behavior.

## Anchor Artifact

The anchor artifact is the inspectable retry continuation behavior in
`custom_components/isolinear/job_orchestration.py` plus
`src/Isolinear/job_orchestration_retry_continuation_anchor.py`, which verifies
accepted retry continuation, unknown job rejection, cross-config-entry
rejection, non-retryable job rejection, per-config-entry isolation,
schema-valid snapshots, setup/routing, and side-effect boundaries against fake
Home Assistant objects.

## Implementation Order

1. Create this spec, paired BDD/evidence scaffold, and eval outline.
2. Add failing unit tests and a Python verifier anchor for accepted retry,
   unknown job rejection, cross-entry rejection, non-retryable rejection,
   isolation, schema validity, and side-effect boundaries.
3. Add the focused executable eval.
4. Extend the production orchestration module and WebSocket routing with the
   smallest retry continuation path.
5. Verify the real files on disk.

## Proof Requirements

1. Unit tests in
   `tests/test_job_orchestration_retry_continuation_anchor.py` are green.
2. Existing Home Assistant orchestration, clarification continuation,
   job-state, WebSocket registration, approved-entity-catalog, and
   approved-history tests remain green.
3. `evals/home_assistant_job_orchestration_retry_continuation_scaffold.py`
   emits raw `CASE` evidence for the BDD scenarios.
4. Evidence confirms a retryable failed job resumes the same job through the
   approved catalog and approved history retrieval boundaries and appends
   deterministic retry continuation snapshots.
5. Evidence confirms unknown jobs and cross-config-entry jobs fail closed
   before history is read and before retry continuation snapshots are appended.
6. Evidence confirms non-retryable jobs fail closed before history is read and
   before retry continuation snapshots are appended.
7. Evidence confirms two config entries keep jobs, history stores, and retry
   run summaries isolated.
8. Evidence confirms every returned and stored retry continuation snapshot
   validates against `IntegrationJobSnapshot`.
9. Evidence confirms no worker, model provider, semantic-memory persistence,
   Home Assistant service/device/state mutation, token-generation, chart
   artifact write, chart rendering, durable storage, subscription progress
   streaming, automatic retry loop, worker retry behavior, or production
   orchestration occurs.
10. Real artifacts are verified on disk: production orchestration module,
    WebSocket retry routing, BDD, eval outline, tests, eval, evidence, and
    verifier anchor.

## Non-Goals

- Model-provider calls, prompt-to-plan generation, or model repair loops.
- Worker HTTP calls, worker token generation, worker retry behavior, or
  artifact storage.
- Chart rendering or chart artifact writes.
- Semantic-memory persistence, migrations, alias reuse, or repair UI.
- Clarification-answer continuation behavior.
- Subscription progress streaming.
- Durable job persistence or queued retry processing.
- Production retry/backoff policy.
- Creating, editing, or deleting Home Assistant dashboards, devices, services,
  automations, scenes, helpers, or state.

## References

- [docs/decisions/0001-home-assistant-integration-plus-worker.md](../decisions/0001-home-assistant-integration-plus-worker.md)
- [docs/decisions/0003-entity-allowlist-semantic-resolution-memory.md](../decisions/0003-entity-allowlist-semantic-resolution-memory.md)
- [docs/decisions/0005-schema-driven-contracts-and-history-normalization.md](../decisions/0005-schema-driven-contracts-and-history-normalization.md)
- [docs/decisions/0006-validation-and-repair-loop.md](../decisions/0006-validation-and-repair-loop.md)
- [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../decisions/0008-read-only-mvp-and-sandbox-security.md)
- [docs/decisions/0011-dashboard-card-implementation-technology.md](../decisions/0011-dashboard-card-implementation-technology.md)
- [docs/decisions/0012-worker-transport-and-authentication.md](../decisions/0012-worker-transport-and-authentication.md)
- [docs/schemas/integration-ws-command.schema.json](../schemas/integration-ws-command.schema.json)
- [docs/schemas/integration-job-snapshot.schema.json](../schemas/integration-job-snapshot.schema.json)
- [docs/schemas/history-series.schema.json](../schemas/history-series.schema.json)
- [docs/schemas/entity-catalog-item.schema.json](../schemas/entity-catalog-item.schema.json)
