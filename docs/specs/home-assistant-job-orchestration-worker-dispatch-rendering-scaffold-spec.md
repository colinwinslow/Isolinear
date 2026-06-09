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

# Home Assistant Integration: Job Orchestration Worker Dispatch/Rendering Scaffold Anchor

## Status

Draft. Defines the first production Home Assistant integration-owned worker
dispatch boundary after validated render-plan storage per ADR-0001, ADR-0003,
ADR-0004, ADR-0005, ADR-0006, ADR-0008, and ADR-0012.

## Related Docs

- [bdd/integration/home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-bdd.md](../../bdd/integration/home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-bdd.md) - observable behavior
- [docs/specs/integration-api-transport-auth-spec.md](integration-api-transport-auth-spec.md) - worker HTTP envelope and bearer-token contract
- [docs/specs/home-assistant-job-orchestration-model-provider-planning-scaffold-spec.md](home-assistant-job-orchestration-model-provider-planning-scaffold-spec.md) - adjacent provider planning boundary
- [docs/specs/home-assistant-job-orchestration-render-planning-scaffold-spec.md](home-assistant-job-orchestration-render-planning-scaffold-spec.md) - adjacent render-plan boundary
- [docs/specs/home-assistant-job-orchestration-artifact-storage-scaffold-spec.md](home-assistant-job-orchestration-artifact-storage-scaffold-spec.md) - adjacent artifact bookkeeping boundary
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The integration can create config-entry-scoped jobs, stage approved
`HistorySeries`, create provider-produced or placeholder `ChartSpec` render
plans, and create placeholder artifact metadata. The next smallest worker
behavior is to dispatch one validated render plan through ADR-0012's worker
transport envelope when an integration-owned worker client is configured.

This packet does not generate or rotate tokens. Tests and evals install a
deterministic fake worker client to prove the production boundary without
network access. Production setup remains disabled unless a future setup packet
provides an integration-owned worker bearer token.

## Behavior Contract

The integration must extend the existing `isolinear/v1/job/snapshot`
orchestration path with a small worker dispatch/rendering boundary.

The worker dispatch boundary must:

- Route only after deterministic WebSocket command validation and config-entry
  scope validation.
- Operate only on an existing job in the targeted config entry.
- Reject unknown jobs and cross-config-entry jobs before worker calls, worker
  dispatch metadata, render-plan metadata, artifact metadata, or complete
  snapshots are stored.
- Require a schema-valid latest source snapshot and a schema-valid render plan.
- Build a schema-valid `RenderRequest` from the validated render plan and
  already-staged config-entry-scoped approved `HistorySeries` records.
- Build a schema-valid `WorkerTransportRequest` with ADR-0012 headers and an
  integration-owned bearer token supplied by the worker client.
- Send the worker transport request only to the configured worker client for
  the same config entry.
- Validate worker `RenderResult` responses against
  `docs/schemas/render-result.schema.json` before storage.
- Record one deterministic in-memory config-entry-scoped worker dispatch
  envelope after successful worker response validation.
- Store only a redacted worker authorization header in worker dispatch
  metadata and evidence.
- Preserve the existing no-worker placeholder artifact/render-plan path when
  no worker client is configured.
- Be idempotent: repeated `job/snapshot` calls for an already completed
  worker-dispatched scaffold job return the existing complete snapshot and
  existing provider plan, render plan, artifact metadata, and worker dispatch
  without another worker call.
- Preserve per-config-entry isolation for worker clients, worker dispatches,
  render plans, artifacts, jobs, orchestration stores, and returned snapshots.

The worker dispatch envelope must include:

- `dispatch_id`
- `config_entry_id`
- `job_id`
- `source_snapshot_id`
- `render_plan_id`
- `artifact_id`
- `status: "render_succeeded"`
- `worker`
- redacted `request`
- `render_result`
- `validation`
- `warnings`

Allowed side effects for this packet are limited to:

- Reading the targeted config-entry job state.
- Reading staged config-entry-scoped approved history already stored by the
  approved history retrieval boundary.
- Reading the configured worker client object and its integration-owned bearer
  token.
- One worker render call for eligible scaffold-ready jobs that do not already
  have a complete snapshot and worker dispatch.
- Existing in-memory config-entry-scoped provider-plan, render-plan, artifact,
  and job-state bookkeeping after successful validation.
- New in-memory config-entry-scoped worker dispatch bookkeeping after
  successful worker response validation.
- Returning or erroring a WebSocket response for the current command.
- The already-anchored global WebSocket command registration.

The packet remains bounded: it must not read Home Assistant history during
worker dispatch, persist semantic memory, mutate Home Assistant
services/devices/state/configuration, generate worker tokens, write real chart
artifact files from the integration, add durable storage, add retry/backoff
policy, add automatic progress tasks, or add worker streaming.

## Anchor Artifact

The anchor artifact is the inspectable worker dispatch/rendering behavior in
`custom_components/isolinear/job_orchestration.py`,
`custom_components/isolinear/worker_renderer.py`, and
`src/Isolinear/job_orchestration_worker_dispatch_rendering_anchor.py`, which
verifies worker request/response validation, token redaction, worker dispatch
metadata storage, idempotent worker-dispatch reuse, worker failure handling,
unknown job rejection, cross-entry rejection, per-config-entry isolation,
schema validity, setup/routing, and side-effect boundaries against fake Home
Assistant objects and deterministic fake worker clients.

## Implementation Order

1. Create this spec, paired BDD/evidence scaffold, eval outline, and worker
   dispatch schema.
2. Add failing unit tests and a Python verifier anchor for accepted worker
   dispatch, token redaction, idempotent reuse, worker failure handling,
   unknown job rejection, cross-entry rejection, isolation, schema validity,
   and side-effect boundaries.
3. Add the focused executable eval.
4. Add the smallest production worker client surface and injectable worker
   boundary.
5. Extend production orchestration so eligible `job/snapshot` calls dispatch
   validated render work when a worker client is configured, while preserving
   the no-worker placeholder path.
6. Verify the real files on disk.

## Proof Requirements

1. Unit tests in
   `tests/test_job_orchestration_worker_dispatch_rendering_anchor.py` are
   green.
2. Existing Home Assistant model-provider planning, render-planning,
   artifact-storage, subscription, retry, clarification continuation,
   job-state, WebSocket registration, approved-entity-catalog, and
   approved-history tests remain green.
3. `evals/home_assistant_job_orchestration_worker_dispatch_rendering_scaffold.py`
   emits raw `CASE` evidence for the BDD scenarios.
4. Evidence confirms a scaffold-ready job with a configured fake worker records
   deterministic worker dispatch metadata and returns the existing
   artifact-backed complete snapshot.
5. Evidence confirms repeated `job/snapshot` requests do not call the worker a
   second time or create duplicate worker dispatch, provider plan, render plan,
   artifact, or complete-snapshot records.
6. Evidence confirms worker transport requests, render requests, render
   results, render plans, chart specs, history series, and worker dispatch
   envelopes validate before storage.
7. Evidence confirms worker authorization material is redacted in stored
   dispatch metadata and eval output.
8. Evidence confirms worker failures fail closed before worker dispatch
   metadata, render-plan metadata, artifact metadata, or complete snapshots are
   stored.
9. Evidence confirms unknown jobs and cross-config-entry jobs fail closed
   before worker calls, worker dispatch metadata, render-plan metadata,
   artifact metadata, or complete snapshots are stored.
10. Evidence confirms two config entries keep worker clients, worker
    dispatches, render plans, artifact metadata, jobs, and orchestration stores
    isolated.
11. Evidence confirms no Home Assistant history read during worker dispatch,
    semantic-memory persistence, Home Assistant service/device/state mutation,
    token generation, real chart artifact file write, durable storage,
    retry/backoff policy, automatic progress task, worker streaming, or
    production orchestration beyond bounded provider/render/artifact/worker
    bookkeeping occurs.
12. Real artifacts are verified on disk: production orchestration module,
    worker renderer module, WebSocket snapshot result routing, worker dispatch
    schema, BDD, eval outline, tests, eval, evidence, and verifier anchor.

## Non-Goals

- Worker token generation, rotation, storage repair, or UI.
- Worker health checks, readiness probes, streaming progress, or long-running
  worker progress semantics.
- Durable job, render-plan, dispatch, or artifact persistence.
- Integration-side chart file writes or public artifact download routes.
- Semantic-memory persistence, migrations, alias reuse, or repair UI.
- Background progress tasks, retry/backoff policy, or automatic retries.
- Changing the card-facing WebSocket command schema.
- Codegen, model-generated Python, sandbox execution, or code repair.
- Visual validation.
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
- [docs/schemas/worker-transport-request.schema.json](../schemas/worker-transport-request.schema.json)
- [docs/schemas/render-request.schema.json](../schemas/render-request.schema.json)
- [docs/schemas/render-result.schema.json](../schemas/render-result.schema.json)
- [docs/schemas/integration-worker-dispatch.schema.json](../schemas/integration-worker-dispatch.schema.json)
