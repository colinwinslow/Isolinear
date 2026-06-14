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

# Home Assistant Integration: Job Orchestration Clarification Continuation Scaffold Anchor

## Status

Draft. Defines the first production Home Assistant integration-owned
clarification-answer continuation path behind `isolinear/v1/clarification/answer`
per ADR-0001, ADR-0003, ADR-0005, ADR-0006, ADR-0008, ADR-0011, and ADR-0012.

## Related Docs

- [bdd/integration/home-assistant-job-orchestration-clarification-continuation-scaffold-bdd.md](../../bdd/integration/home-assistant-job-orchestration-clarification-continuation-scaffold-bdd.md) - observable behavior
- [docs/specs/home-assistant-job-orchestration-scaffold-spec.md](home-assistant-job-orchestration-scaffold-spec.md) - parent `job/start` orchestration scaffold
- [docs/specs/home-assistant-job-state-scaffold-spec.md](home-assistant-job-state-scaffold-spec.md) - job state dependency
- [docs/specs/home-assistant-approved-entity-catalog-scaffold-spec.md](home-assistant-approved-entity-catalog-scaffold-spec.md) - approved entity catalog dependency
- [docs/specs/home-assistant-approved-history-retrieval-scaffold-spec.md](home-assistant-approved-history-retrieval-scaffold-spec.md) - approved history dependency
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The current orchestration scaffold can return a schema-valid
`clarification_needed` snapshot when `job/start` cannot deterministically select
one approved entity. The card-facing command contract already includes
`isolinear/v1/clarification/answer`, but that command only records a job-state
scaffold snapshot. The next smallest orchestration behavior is to resume the
same config-entry-scoped job after the user selects one of the approved options
from the prior clarification.

This packet remains a scaffold. It accepts only returned approved option IDs,
resumes approved history retrieval, records schema-valid continuation
snapshots, and then stops before model, worker, renderer, memory, artifact,
durable storage, retry, or streaming behavior.

## Behavior Contract

The integration must extend `custom_components/isolinear/job_orchestration.py`
with a small clarification-answer continuation boundary.

The continuation boundary must:

- Route enabled `isolinear/v1/clarification/answer` commands through
  orchestration only after deterministic command validation and config-entry
  scope validation.
- Operate only on an existing job in the targeted config entry.
- Require the job's latest orchestration-relevant snapshot to be
  `clarification_needed` with a matching `question_id`.
- Accept only a returned approved `option_id` from the stored clarification
  options.
- Resolve the approved option to one approved entity ID before any history
  read.
- Reject unknown options, wrong question IDs, non-clarification jobs, unknown
  jobs, and cross-config-entry jobs before Home Assistant history is read.
- Append deterministic schema-valid continuation snapshots to the same job:
  clarification accepted, fetching approved history, and scaffold-ready or
  failed.
- Retrieve history only through the approved history retrieval boundary.
- Store one continuation run summary under the targeted config entry only.
- Validate every `IntegrationJobSnapshot` before storage/return.
- Preserve per-config-entry isolation for pending clarification state, job
  state, history stores, and run summaries.
- Preserve the `remember` field as accepted command input only; semantic memory
  persistence is not implemented in this packet.

Allowed side effects for this packet are limited to:

- Reading config-entry-scoped pending clarification state.
- Reading the config-entry approved entity catalog.
- Reading approved fake Home Assistant history through the history retrieval
  scaffold after a valid approved option is selected.
- In-memory config-entry-scoped history retrieval store updates.
- In-memory config-entry-scoped job state updates.
- In-memory config-entry-scoped orchestration continuation bookkeeping.
- Returning or erroring a WebSocket response for the current command.
- The already-anchored global WebSocket command registration.

The continuation scaffold must report that no worker, model-provider,
semantic-memory persistence, Home Assistant service/device/state mutation,
token-generation, chart artifact write, chart rendering, durable storage,
retry behavior, subscription progress streaming, or production orchestration
occurred.

## Anchor Artifact

The anchor artifact is the inspectable continuation behavior in
`custom_components/isolinear/job_orchestration.py` plus
`src/Isolinear/job_orchestration_clarification_continuation_anchor.py`, which
verifies accepted clarification continuation, unknown option failure,
question mismatch failure, cross-config-entry/job rejection, no history read
before a valid approved option is selected, per-config-entry isolation,
schema-valid snapshots, setup/routing, and side-effect boundaries against fake
Home Assistant objects.

## Implementation Order

1. Create this spec, paired BDD/evidence scaffold, and eval outline.
2. Add failing unit tests and a Python verifier anchor for accepted
   continuation, unknown option failure, question mismatch failure, cross-entry
   rejection, isolation, schema validity, and side-effect boundaries.
3. Add the focused executable eval.
4. Extend the production orchestration module and WebSocket routing with the
   smallest continuation path.
5. Verify the real files on disk.

## Proof Requirements

1. Unit tests in
   `tests/test_job_orchestration_clarification_continuation_anchor.py` are
   green.
2. Existing Home Assistant orchestration, job-state, WebSocket registration,
   approved-entity-catalog, and approved-history tests remain green.
3. `evals/home_assistant_job_orchestration_clarification_continuation_scaffold.py`
   emits raw `CASE` evidence for the BDD scenarios.
4. Evidence confirms a returned approved option ID resumes the same job through
   approved history retrieval and appends deterministic continuation snapshots.
5. Evidence confirms unknown options and wrong question IDs fail closed before
   history is read.
6. Evidence confirms colliding returned option IDs fail closed before history
   is read.
7. Evidence confirms unknown jobs and cross-config-entry jobs fail closed
   before history is read.
8. Evidence confirms two config entries keep pending clarification state,
   history stores, and run summaries isolated.
9. Evidence confirms every returned and stored continuation snapshot validates
   against `IntegrationJobSnapshot`.
10. Evidence confirms no worker, model provider, semantic-memory persistence,
   Home Assistant service/device/state mutation, token-generation, chart
   artifact write, chart rendering, durable storage, retry behavior,
   subscription progress streaming, or production orchestration occurs.
11. Real artifacts are verified on disk: production orchestration module,
    WebSocket answer routing, BDD, eval outline, tests, eval, evidence, and
    verifier anchor.

## Non-Goals

- Model-provider calls or prompt-to-plan generation.
- Worker HTTP calls, worker token generation, or artifact storage.
- Chart rendering or chart artifact writes.
- Semantic-memory persistence, migrations, alias reuse, or repair UI.
- Retry continuation behavior.
- Subscription progress streaming.
- Durable job persistence.
- Production natural-language entity resolution beyond returned approved
  clarification options.
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
