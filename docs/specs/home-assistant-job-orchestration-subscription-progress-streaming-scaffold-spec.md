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

# Home Assistant Integration: Job Orchestration Subscription Progress Streaming Scaffold Anchor

## Status

Draft. Defines the first production Home Assistant integration-owned
subscription/progress streaming scaffold behind `isolinear/v1/job/subscribe`
per ADR-0001, ADR-0003, ADR-0005, ADR-0006, ADR-0008, ADR-0011, and ADR-0012.

## Related Docs

- [bdd/integration/home-assistant-job-orchestration-subscription-progress-streaming-scaffold-bdd.md](../../bdd/integration/home-assistant-job-orchestration-subscription-progress-streaming-scaffold-bdd.md) - observable behavior
- [docs/specs/home-assistant-job-orchestration-scaffold-spec.md](home-assistant-job-orchestration-scaffold-spec.md) - parent `job/start` orchestration scaffold
- [docs/specs/home-assistant-job-orchestration-clarification-continuation-scaffold-spec.md](home-assistant-job-orchestration-clarification-continuation-scaffold-spec.md) - sibling continuation path
- [docs/specs/home-assistant-job-orchestration-retry-continuation-scaffold-spec.md](home-assistant-job-orchestration-retry-continuation-scaffold-spec.md) - sibling retry path
- [docs/specs/home-assistant-job-state-scaffold-spec.md](home-assistant-job-state-scaffold-spec.md) - job state dependency
- [docs/specs/home-assistant-websocket-command-registration-spec.md](home-assistant-websocket-command-registration-spec.md) - registered command boundary
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The integration now owns job state, approved entity catalog, approved history
retrieval, `job/start` orchestration, clarification-answer continuation, and
retry continuation. The card-facing API already includes
`isolinear/v1/job/subscribe`, but enabled orchestration entries still fall back
to the generic job-state subscription scaffold.

The next smallest orchestration behavior is a config-entry-scoped subscription
and progress-event scaffold. This packet records that a dashboard card
subscribed to one existing job, validates the latest `IntegrationJobSnapshot`,
stores a deterministic progress event envelope for that targeted job, and
returns the latest snapshot immediately. It does not start a worker stream,
spawn a background progress task, call the model provider, call the worker,
render charts, persist memory, write artifacts, or implement durable
production streaming semantics.

## Behavior Contract

The integration must extend `custom_components/isolinear/job_orchestration.py`
with a small subscription/progress streaming scaffold boundary.

The subscription boundary must:

- Route enabled `isolinear/v1/job/subscribe` commands through orchestration
  only after deterministic command validation and config-entry scope
  validation.
- Operate only on an existing job in the targeted config entry.
- Reject unknown jobs and cross-config-entry jobs before subscription
  bookkeeping or progress-event storage.
- Reuse the existing job-state subscription bookkeeping surface so the
  subscription shape remains owned by the job state store.
- Validate the targeted job's latest `IntegrationJobSnapshot` before storing
  or returning a progress event.
- Store one deterministic in-memory progress event envelope under the targeted
  config entry's orchestration store.
- Return the latest schema-valid snapshot immediately for the subscribe
  command.
- Preserve per-config-entry isolation for jobs, subscriptions, progress
  events, and orchestration bookkeeping.

The progress event envelope is an inspectable scaffold shape, not a new public
schema. It must include:

- `event_id`
- `type: "isolinear_job_progress"`
- `config_entry_id`
- `job_id`
- `subscription_id`
- `message_id`
- `snapshot_id`
- `progress`
- `snapshot`

Allowed side effects for this packet are limited to:

- Reading the targeted config-entry job state.
- In-memory config-entry-scoped subscription bookkeeping.
- In-memory config-entry-scoped progress event bookkeeping.
- Returning or erroring a WebSocket response for the current command.
- The already-anchored global WebSocket command registration.

The subscription/progress scaffold must report that no worker, model-provider,
approved Home Assistant history read, semantic-memory persistence,
Home Assistant service/device/state mutation, token-generation, chart artifact
write, chart rendering, durable storage, retry behavior, automatic progress
task, worker streaming, or production orchestration occurred. It may report
the bounded subscription/progress scaffold event as the only progress streaming
behavior in this packet.

## Anchor Artifact

The anchor artifact is the inspectable subscription behavior in
`custom_components/isolinear/job_orchestration.py` plus
`src/Isolinear/job_orchestration_subscription_progress_anchor.py`, which
verifies accepted subscription, unknown job rejection, cross-config-entry
rejection, per-config-entry isolation, schema-valid returned and stored
snapshots, setup/routing, and side-effect boundaries against fake Home
Assistant objects.

## Implementation Order

1. Create this spec, paired BDD/evidence scaffold, and eval outline.
2. Add failing unit tests and a Python verifier anchor for accepted
   subscription, unknown job rejection, cross-entry rejection, isolation,
   schema validity, and side-effect boundaries.
3. Add the focused executable eval.
4. Extend the production orchestration module and WebSocket routing with the
   smallest subscription/progress path.
5. Verify the real files on disk.

## Proof Requirements

1. Unit tests in
   `tests/test_job_orchestration_subscription_progress_anchor.py` are green.
2. Existing Home Assistant orchestration, clarification continuation, retry
   continuation, job-state, WebSocket registration, approved-entity-catalog,
   and approved-history tests remain green.
3. `evals/home_assistant_job_orchestration_subscription_progress_scaffold.py`
   emits raw `CASE` evidence for the BDD scenarios.
4. Evidence confirms subscribing to an existing job records a deterministic
   job-state subscription and an orchestration progress event for the same
   config-entry-scoped job.
5. Evidence confirms the subscribe response immediately returns the latest
   schema-valid snapshot for that job.
6. Evidence confirms unknown jobs and cross-config-entry jobs fail closed
   before subscription or progress-event storage.
7. Evidence confirms two config entries keep subscriptions, progress events,
   jobs, and orchestration stores isolated.
8. Evidence confirms every returned and stored progress event snapshot
   validates against `IntegrationJobSnapshot`.
9. Evidence confirms no worker, model provider, approved Home Assistant
   history read, semantic-memory persistence, Home Assistant service/device/
   state mutation, token-generation, chart artifact write, chart rendering,
   durable storage, retry behavior, automatic progress task, worker streaming,
   or production orchestration occurs.
10. Real artifacts are verified on disk: production orchestration module,
    WebSocket subscribe routing, BDD, eval outline, tests, eval, evidence, and
    verifier anchor.

## Non-Goals

- Model-provider calls or prompt-to-plan generation.
- Worker HTTP calls, worker token generation, worker progress streaming, or
  artifact storage.
- Chart rendering or chart artifact writes.
- Semantic-memory persistence, migrations, alias reuse, or repair UI.
- Durable job persistence or durable subscriptions.
- Background progress tasks, automatic polling, worker streaming, or
  production long-running progress semantics.
- Changing the card-facing WebSocket command schema.
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
