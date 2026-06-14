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

# Home Assistant Integration: Job Orchestration Artifact Storage Scaffold Anchor

## Status

Draft. Defines the first production Home Assistant integration-owned artifact
storage semantics path behind `isolinear/v1/job/snapshot` per ADR-0001,
ADR-0003, ADR-0005, ADR-0006, ADR-0008, ADR-0011, and ADR-0012.

## Related Docs

- [bdd/integration/home-assistant-job-orchestration-artifact-storage-scaffold-bdd.md](../../bdd/integration/home-assistant-job-orchestration-artifact-storage-scaffold-bdd.md) - observable behavior
- [docs/specs/home-assistant-job-orchestration-scaffold-spec.md](home-assistant-job-orchestration-scaffold-spec.md) - parent `job/start` orchestration scaffold
- [docs/specs/home-assistant-job-orchestration-subscription-progress-streaming-scaffold-spec.md](home-assistant-job-orchestration-subscription-progress-streaming-scaffold-spec.md) - sibling progress path
- [docs/specs/home-assistant-job-state-scaffold-spec.md](home-assistant-job-state-scaffold-spec.md) - job state dependency
- [docs/specs/integration-api-transport-auth-spec.md](integration-api-transport-auth-spec.md) - card-facing command contract
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The integration can now create config-entry-scoped jobs, resolve approved
entities, retrieve approved fake Home Assistant history, handle clarification
answers, handle retry continuations, and record a latest-snapshot progress
event. A scaffold-ready job proves the integration has enough approved data for
a future render packet, but the dashboard card still has no integration-owned
chart-result object to display or inspect.

The next smallest orchestration behavior is an in-memory artifact bookkeeping
surface. This packet turns a scaffold-ready job into a deterministic
placeholder artifact record when the card asks for the latest snapshot. It uses
only existing job state and scaffold metadata; it does not render a chart,
write an image file, call the worker, call the model provider, generate a
worker token, persist semantic memory, or mutate Home Assistant state.

## Behavior Contract

The integration must extend `custom_components/isolinear/job_orchestration.py`
with a small artifact storage scaffold boundary routed through enabled
`isolinear/v1/job/snapshot` commands.

The artifact storage boundary must:

- Route enabled `isolinear/v1/job/snapshot` commands through orchestration only
  after deterministic command validation and config-entry scope validation.
- Operate only on an existing job in the targeted config entry.
- Reject unknown jobs and cross-config-entry jobs before artifact bookkeeping
  or new snapshot storage.
- Require the job's latest snapshot to be a scaffold-ready planning snapshot
  or an existing scaffold-artifact complete snapshot.
- Validate the targeted job's latest `IntegrationJobSnapshot` before artifact
  metadata is created or returned.
- Store one deterministic in-memory artifact metadata envelope under the
  targeted config entry's orchestration store.
- Validate artifact metadata against
  `docs/schemas/integration-artifact-metadata.schema.json` before storage.
- Append and return a deterministic schema-valid `complete`
  `IntegrationJobSnapshot` with placeholder chart metadata for the same job.
- Be idempotent: repeated `job/snapshot` calls for the same completed scaffold
  job return the existing artifact-backed complete snapshot without creating a
  duplicate artifact record.
- Preserve per-config-entry isolation for jobs, artifact records,
  orchestration bookkeeping, and returned snapshots.

The artifact metadata envelope must include:

- `artifact_id`
- `config_entry_id`
- `job_id`
- `source_snapshot_id`
- `artifact_kind: "chart_image"`
- `status: "placeholder"`
- `title`
- `image_url`
- `time_range`
- `series`
- `overlays`
- `render_metadata`
- `validation`
- `warnings`

Allowed side effects for this packet are limited to:

- Reading the targeted config-entry job state.
- In-memory config-entry-scoped artifact bookkeeping.
- In-memory config-entry-scoped job state updates for the artifact-backed
  complete snapshot.
- Returning or erroring a WebSocket response for the current command.
- The already-anchored global WebSocket command registration.

The artifact storage scaffold must report that no worker, model-provider,
approved Home Assistant history read during artifact storage, semantic-memory
persistence, Home Assistant service/device/state mutation, token-generation,
real chart artifact file write, chart rendering, durable storage, retry
behavior, automatic progress task, worker streaming, or production
orchestration occurred. It may report bounded in-memory artifact bookkeeping
as the only artifact behavior in this packet.

## Anchor Artifact

The anchor artifact is the inspectable artifact storage behavior in
`custom_components/isolinear/job_orchestration.py` plus
`src/Isolinear/job_orchestration_artifact_storage_anchor.py`, which verifies
accepted artifact metadata creation, idempotent artifact snapshot retrieval,
unknown job rejection, cross-config-entry rejection, per-config-entry
isolation, schema-valid artifact metadata and snapshots, setup/routing, and
side-effect boundaries against fake Home Assistant objects.

## Implementation Order

1. Create this spec, paired BDD/evidence scaffold, eval outline, and artifact
   metadata schema.
2. Add failing unit tests and a Python verifier anchor for accepted artifact
   creation, idempotent snapshot retrieval, unknown job rejection, cross-entry
   rejection, isolation, schema validity, and side-effect boundaries.
3. Add the focused executable eval.
4. Extend the production orchestration module and WebSocket routing with the
   smallest artifact storage path.
5. Verify the real files on disk.

## Proof Requirements

1. Unit tests in
   `tests/test_job_orchestration_artifact_storage_anchor.py` are green.
2. Existing Home Assistant orchestration, clarification continuation, retry
   continuation, subscription/progress, job-state, WebSocket registration,
   approved-entity-catalog, and approved-history tests remain green.
3. `evals/home_assistant_job_orchestration_artifact_storage_scaffold.py` emits
   raw `CASE` evidence for the BDD scenarios.
4. Evidence confirms requesting `job/snapshot` for a scaffold-ready job records
   deterministic artifact metadata and returns an artifact-backed complete
   snapshot for the same config-entry-scoped job.
5. Evidence confirms repeated `job/snapshot` requests for that job do not
   create duplicate artifact records.
6. Evidence confirms unknown jobs and cross-config-entry jobs fail closed
   before artifact metadata or complete snapshots are stored.
7. Evidence confirms two config entries keep artifact metadata, jobs, and
   orchestration stores isolated.
8. Evidence confirms every returned and stored artifact-backed snapshot
   validates against `IntegrationJobSnapshot`.
9. Evidence confirms every stored artifact metadata envelope validates against
   `IntegrationArtifactMetadata`.
10. Evidence confirms no worker, model provider, approved Home Assistant
    history read during artifact storage, semantic-memory persistence, Home
    Assistant service/device/state mutation, token-generation, real chart
    artifact file write, chart rendering, durable storage, retry behavior,
    automatic progress task, worker streaming, or production orchestration
    occurs.
11. Real artifacts are verified on disk: production orchestration module,
    WebSocket snapshot routing, artifact metadata schema, BDD, eval outline,
    tests, eval, evidence, and verifier anchor.

## Non-Goals

- Model-provider calls or prompt-to-plan generation.
- Worker HTTP calls, worker token generation, worker progress streaming, or
  real worker artifact ingestion.
- Chart rendering or image file writes.
- Public artifact download routes or dashboard image hosting.
- Semantic-memory persistence, migrations, alias reuse, or repair UI.
- Durable job or artifact persistence.
- Background progress tasks, retry/backoff policy, or production long-running
  orchestration semantics.
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
- [docs/schemas/integration-artifact-metadata.schema.json](../schemas/integration-artifact-metadata.schema.json)
