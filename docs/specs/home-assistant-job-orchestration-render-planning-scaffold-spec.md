---
status: draft
date: 2026-06-08
depends-on-adrs:
  - 0001
  - 0003
  - 0004
  - 0005
  - 0006
  - 0008
  - 0012
---

# Home Assistant Integration: Job Orchestration Render Planning Scaffold Anchor

## Status

Draft. Defines the first production Home Assistant integration-owned render
planning scaffold behind `isolinear/v1/job/snapshot` per ADR-0001, ADR-0003,
ADR-0004, ADR-0005, ADR-0006, ADR-0008, and ADR-0012.

## Related Docs

- [bdd/integration/home-assistant-job-orchestration-render-planning-scaffold-bdd.md](../../bdd/integration/home-assistant-job-orchestration-render-planning-scaffold-bdd.md) - observable behavior
- [docs/specs/home-assistant-job-orchestration-artifact-storage-scaffold-spec.md](home-assistant-job-orchestration-artifact-storage-scaffold-spec.md) - adjacent artifact bookkeeping boundary
- [docs/specs/home-assistant-job-orchestration-scaffold-spec.md](home-assistant-job-orchestration-scaffold-spec.md) - parent `job/start` orchestration scaffold
- [docs/specs/chart-spec-rendering-spec.md](chart-spec-rendering-spec.md) - trusted chart-spec-first renderer contract
- [docs/specs/integration-api-transport-auth-spec.md](integration-api-transport-auth-spec.md) - card-facing and worker-facing command contracts
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The integration can create config-entry-scoped jobs, resolve approved entities,
retrieve approved fake Home Assistant history, resume clarification and retry
paths, record latest-snapshot progress events, and create placeholder artifact
metadata for scaffold-ready jobs. The next smallest orchestration behavior is a
render-planning record that pins down what a future renderer should consume
without calling the model provider, worker, or renderer.

This packet does not implement Ollama/model-provider planning. It creates the
validated in-memory slot that a future provider-produced `ChartSpec` can fill.
For the scaffold, the integration deterministically derives a placeholder safe
mode `ChartSpec` from the approved entity disclosure already present on a
schema-valid scaffold-ready job snapshot.

## Behavior Contract

The integration must extend `custom_components/isolinear/job_orchestration.py`
with a small render planning scaffold boundary routed through enabled
`isolinear/v1/job/snapshot` commands.

The render planning boundary must:

- Route enabled `isolinear/v1/job/snapshot` commands through orchestration only
  after deterministic command validation and config-entry scope validation.
- Operate only on an existing job in the targeted config entry.
- Reject unknown jobs and cross-config-entry jobs before render-plan
  bookkeeping, artifact bookkeeping, or new snapshot storage.
- Validate the targeted job's latest `IntegrationJobSnapshot` before render
  planning.
- Require a scaffold-ready source snapshot before creating a new render plan.
- Derive a deterministic placeholder safe-mode `ChartSpec` from only approved
  entity disclosure already present on the source snapshot.
- Validate the placeholder `ChartSpec` against
  `docs/schemas/chart-spec.schema.json` before render-plan storage.
- Store one deterministic in-memory render-plan envelope under the targeted
  config entry's orchestration store.
- Validate render-plan metadata against
  `docs/schemas/integration-render-plan.schema.json` before storage.
- Preserve the existing artifact storage behavior by allowing the same
  `job/snapshot` request to continue creating the placeholder artifact-backed
  complete snapshot after the render plan validates.
- Be idempotent: repeated `job/snapshot` calls for the same completed scaffold
  job return the existing complete snapshot and existing render plan without
  creating duplicate render-plan or artifact records.
- Preserve per-config-entry isolation for jobs, render plans, artifact records,
  orchestration bookkeeping, and returned snapshots.

The render-plan envelope must include:

- `render_plan_id`
- `config_entry_id`
- `job_id`
- `source_snapshot_id`
- `artifact_id`
- `status: "planned"`
- `render_mode: "safe"`
- `renderer: "trusted_chart_spec"`
- `chart_spec`
- `history_entity_ids`
- `output`
- `validation`
- `warnings`

Allowed side effects for this packet are limited to:

- Reading the targeted config-entry job state.
- In-memory config-entry-scoped render-plan bookkeeping.
- Existing in-memory config-entry-scoped artifact bookkeeping.
- Existing in-memory config-entry-scoped job state updates for the
  artifact-backed complete snapshot.
- Returning or erroring a WebSocket response for the current command.
- The already-anchored global WebSocket command registration.

The render planning scaffold must report that no model-provider/Ollama call,
worker call, approved Home Assistant history read during render planning,
semantic-memory persistence, Home Assistant service/device/state mutation,
token generation, real chart artifact file write, chart rendering, durable
storage, retry/backoff policy, automatic progress task, worker streaming, or
production orchestration occurred.

## Anchor Artifact

The anchor artifact is the inspectable render planning behavior in
`custom_components/isolinear/job_orchestration.py` plus
`src/Isolinear/job_orchestration_render_planning_anchor.py`, which verifies
accepted render-plan creation, idempotent render-plan reuse, unknown job
rejection, cross-config-entry rejection, per-config-entry isolation,
schema-valid render plans and chart specs, setup/routing, and side-effect
boundaries against fake Home Assistant objects.

## Implementation Order

1. Create this spec, paired BDD/evidence scaffold, eval outline, and render
   plan schema.
2. Add failing unit tests and a Python verifier anchor for accepted render-plan
   creation, idempotent reuse, unknown job rejection, cross-entry rejection,
   isolation, schema validity, and side-effect boundaries.
3. Add the focused executable eval.
4. Extend the production orchestration module and WebSocket result envelope
   with the smallest render planning path.
5. Verify the real files on disk.

## Proof Requirements

1. Unit tests in
   `tests/test_job_orchestration_render_planning_anchor.py` are green.
2. Existing Home Assistant orchestration, artifact storage, subscription,
   retry, clarification continuation, job-state, WebSocket registration,
   approved-entity-catalog, and approved-history tests remain green.
3. `evals/home_assistant_job_orchestration_render_planning_scaffold.py` emits
   raw `CASE` evidence for the BDD scenarios.
4. Evidence confirms requesting `job/snapshot` for a scaffold-ready job records
   deterministic render-plan metadata and returns the artifact-backed complete
   snapshot for the same config-entry-scoped job.
5. Evidence confirms repeated `job/snapshot` requests for that job do not
   create duplicate render-plan or artifact records.
6. Evidence confirms unknown jobs and cross-config-entry jobs fail closed
   before render-plan metadata, artifact metadata, or complete snapshots are
   stored.
7. Evidence confirms two config entries keep render plans, artifact metadata,
   jobs, and orchestration stores isolated.
8. Evidence confirms every stored render-plan envelope validates against
   `IntegrationRenderPlan`.
9. Evidence confirms every stored placeholder chart spec validates against
   `ChartSpec`.
10. Evidence confirms no model-provider/Ollama call, worker call, approved
    Home Assistant history read during render planning, semantic-memory
    persistence, Home Assistant service/device/state mutation, token
    generation, real chart artifact file write, chart rendering, durable
    storage, retry/backoff policy, automatic progress task, worker streaming,
    or production orchestration occurs.
11. Real artifacts are verified on disk: production orchestration module,
    WebSocket snapshot result routing, render-plan schema, BDD, eval outline,
    tests, eval, evidence, and verifier anchor.

## Non-Goals

- Ollama/model-provider calls, prompt construction, provider streaming,
  provider retries, or provider transport.
- Worker HTTP calls, worker token generation, worker progress streaming, or
  real worker artifact ingestion.
- Chart rendering or image file writes.
- Changing the dashboard card UI.
- Semantic-memory persistence, migrations, alias reuse, or repair UI.
- Durable job, render-plan, or artifact persistence.
- Background progress tasks, retry/backoff policy, or production long-running
  orchestration semantics.
- Changing the card-facing WebSocket command schema.
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
- [docs/schemas/integration-job-snapshot.schema.json](../schemas/integration-job-snapshot.schema.json)
- [docs/schemas/integration-artifact-metadata.schema.json](../schemas/integration-artifact-metadata.schema.json)
- [docs/schemas/integration-render-plan.schema.json](../schemas/integration-render-plan.schema.json)
- [docs/schemas/chart-spec.schema.json](../schemas/chart-spec.schema.json)
