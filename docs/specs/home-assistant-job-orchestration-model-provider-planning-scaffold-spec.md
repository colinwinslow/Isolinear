---
status: draft
date: 2026-06-09
depends-on-adrs:
  - 0001
  - 0003
  - 0004
  - 0005
  - 0006
  - 0007
  - 0008
  - 0012
---

# Home Assistant Integration: Job Orchestration Model-Provider Planning Scaffold Anchor

## Status

Draft. Defines the first production Home Assistant integration-owned
Ollama-compatible planner boundary after render-plan storage per ADR-0001,
ADR-0003, ADR-0004, ADR-0005, ADR-0006, ADR-0007, ADR-0008, and ADR-0012.

## Related Docs

- [bdd/integration/home-assistant-job-orchestration-model-provider-planning-scaffold-bdd.md](../../bdd/integration/home-assistant-job-orchestration-model-provider-planning-scaffold-bdd.md) - observable behavior
- [docs/specs/model-provider-spec.md](model-provider-spec.md) - model-provider role contract
- [docs/specs/home-assistant-job-orchestration-render-planning-scaffold-spec.md](home-assistant-job-orchestration-render-planning-scaffold-spec.md) - adjacent render-plan boundary
- [docs/specs/home-assistant-job-orchestration-scaffold-spec.md](home-assistant-job-orchestration-scaffold-spec.md) - parent `job/start` orchestration scaffold
- [docs/specs/chart-spec-rendering-spec.md](chart-spec-rendering-spec.md) - trusted chart-spec-first renderer contract
- [docs/specs/integration-api-transport-auth-spec.md](integration-api-transport-auth-spec.md) - card-facing and worker-facing command contracts
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The integration can create config-entry-scoped jobs, resolve approved entities,
retrieve approved fake Home Assistant history, and record placeholder render
plans from scaffold-ready snapshots. The next smallest model-provider behavior
is to let an integration-owned planner boundary call an Ollama-compatible
planner client, validate the returned `PlannerResult`, and replace the
placeholder `ChartSpec` in the render plan with a provider-produced
schema-valid `ChartSpec`.

Ollama's current chat API exposes `POST /api/chat`, accepts `stream: false`,
and supports structured output through a `format` field containing either
`json` or a JSON Schema object. This packet uses that shape for the production
client while the tests and evals inject a deterministic fake planner so no
network service is required for proof.

## Behavior Contract

The integration must extend the existing
`isolinear/v1/job/snapshot` orchestration path with a small
model-provider planning boundary.

The model-provider planning boundary must:

- Route only after deterministic WebSocket command validation and config-entry
  scope validation.
- Operate only on an existing job in the targeted config entry.
- Reject unknown jobs and cross-config-entry jobs before calling the model
  provider, writing model-provider planning metadata, writing render-plan
  metadata, writing artifact metadata, or appending complete snapshots.
- Validate the targeted job's latest `IntegrationJobSnapshot` before model
  provider planning.
- Require a scaffold-ready source snapshot before creating a provider-produced
  render plan.
- Use only integration-owned config-entry data for provider endpoint and
  planner model selection; the dashboard card must not send endpoint, model,
  token, worker, raw-history, or semantic-memory material.
- Build a deterministic planner request from the user prompt, source snapshot,
  approved entity disclosure, and available history entity IDs.
- Call an Ollama-compatible planner client only when one is configured for the
  config entry.
- Preserve the existing placeholder render-plan behavior when no planner
  client is configured.
- Validate provider output against `docs/schemas/planner-result.schema.json`
  before using it.
- Require provider output status `chart_spec_ready` with a non-null
  `chart_spec` for this packet.
- Validate the provider-produced `ChartSpec` against
  `docs/schemas/chart-spec.schema.json` before render-plan storage.
- Reject provider output, including the `PlannerResult` envelope and nested
  `ChartSpec`, that references entity IDs outside the source snapshot's
  approved entity disclosure before model-provider plan, render-plan, artifact,
  or complete snapshot storage.
- Store one deterministic in-memory model-provider planning envelope under the
  targeted config entry's orchestration store after successful provider output
  validation.
- Validate model-provider planning envelopes against
  `docs/schemas/integration-model-provider-plan.schema.json` before storage.
- Store the existing deterministic in-memory render-plan envelope under the
  targeted config entry, using the provider-produced `ChartSpec` instead of
  the placeholder chart spec.
- Validate render-plan metadata against
  `docs/schemas/integration-render-plan.schema.json` before storage.
- Validate the nested render-plan `ChartSpec` before storage.
- Preserve the existing artifact storage behavior by allowing the same
  `job/snapshot` request to continue creating the placeholder artifact-backed
  complete snapshot after model-provider planning and render-plan validation.
- Be idempotent: repeated `job/snapshot` calls for the same completed
  provider-planned scaffold job return the existing complete snapshot and
  existing model-provider plan, render plan, and artifact without another
  provider call.
- Preserve per-config-entry isolation for provider plans, render plans,
  artifact records, jobs, orchestration bookkeeping, provider clients, and
  returned snapshots.

The model-provider planning envelope must include:

- `provider_plan_id`
- `config_entry_id`
- `job_id`
- `source_snapshot_id`
- `provider`
- `request`
- `status: "chart_spec_ready"`
- `planner_result`
- `chart_spec`
- `validation`
- `warnings`

Allowed side effects for this packet are limited to:

- Reading the targeted config-entry job state.
- Reading integration-owned model-provider config and the configured planner
  client object.
- One planner role call to the configured Ollama-compatible client for eligible
  scaffold-ready jobs that do not already have a complete snapshot.
- In-memory config-entry-scoped model-provider planning bookkeeping after
  successful provider output validation.
- Existing in-memory config-entry-scoped render-plan bookkeeping.
- Existing in-memory config-entry-scoped artifact bookkeeping.
- Existing in-memory config-entry-scoped job state updates for the
  artifact-backed complete snapshot.
- Returning or erroring a WebSocket response for the current command.
- The already-anchored global WebSocket command registration.

The packet remains non-rendering and non-mutating. It must not call the worker,
read approved Home Assistant history during model-provider planning, persist
semantic memory, mutate Home Assistant services/devices/state/configuration,
generate worker tokens, write real chart artifact files, render charts, add
durable storage, add retry/backoff policy, add automatic progress tasks, or add
worker streaming.

## Anchor Artifact

The anchor artifact is the inspectable model-provider planning behavior in
`custom_components/isolinear/job_orchestration.py`,
`custom_components/isolinear/model_provider.py`, and
`src/Isolinear/job_orchestration_model_provider_planning_anchor.py`, which
verifies provider-produced render-plan creation, idempotent provider-plan
reuse, hidden-entity rejection, invalid chart-spec rejection, unknown job
rejection, cross-entry rejection, per-config-entry isolation, schema validity,
setup/routing, and side-effect boundaries against fake Home Assistant objects
and deterministic fake Ollama-compatible planner clients.

## Implementation Order

1. Create this spec, paired BDD/evidence scaffold, eval outline, and
   model-provider plan schema.
2. Add failing unit tests and a Python verifier anchor for accepted
   provider-produced planning, idempotent reuse, structural unapproved-entity
   rejection (chart-spec `series`/`overlays` sources + `memory_proposals` entity
   references; entity-shaped tokens in inert free-text fields are ignored —
   ADR-0023), invalid chart-spec rejection, unknown job rejection, cross-entry
   rejection, isolation, schema validity, and side-effect boundaries.
3. Add the focused executable eval.
4. Add the smallest production Ollama-compatible planner client surface and
   injectable planner boundary.
5. Extend production orchestration so eligible `job/snapshot` calls use a
   provider-produced `ChartSpec` when a planner client is configured, while
   preserving the no-provider placeholder path.
6. Verify the real files on disk.

## Proof Requirements

1. Unit tests in
   `tests/test_job_orchestration_model_provider_planning_anchor.py` are green.
2. Existing Home Assistant render-planning, artifact-storage, subscription,
   retry, clarification continuation, job-state, WebSocket registration,
   approved-entity-catalog, and approved-history tests remain green.
3. `evals/home_assistant_job_orchestration_model_provider_planning_scaffold.py`
   emits raw `CASE` evidence for the BDD scenarios.
4. Evidence confirms requesting `job/snapshot` for a scaffold-ready job with a
   configured fake Ollama-compatible planner records deterministic
   model-provider planning metadata and a render plan using the
   provider-produced `ChartSpec`.
5. Evidence confirms repeated `job/snapshot` requests for that job do not make
   a second provider call or create duplicate provider-plan, render-plan,
   artifact, or complete-snapshot records.
6. Evidence confirms provider output that references an off-allowlist entity in
   a chart-spec `series`/`overlays` source or a `memory_proposals` entity
   reference fails closed before model-provider plan metadata, render-plan
   metadata, artifact metadata, or complete snapshots are stored. Entity-shaped
   tokens in inert free-text fields (`chart_id`, `title`, axis metadata,
   `notes`, `reasoning_summary`) are not entity references and render normally
   (ADR-0023; the structural-gate fix).
7. Evidence confirms provider-produced schema-invalid chart specs fail closed
   before model-provider plan metadata, render-plan metadata, artifact
   metadata, or complete snapshots are stored.
8. Evidence confirms unknown jobs and cross-config-entry jobs fail closed
   before provider calls, model-provider plan metadata, render-plan metadata,
   artifact metadata, or complete snapshots are stored.
9. Evidence confirms two config entries keep provider clients, provider plans,
   render plans, artifact metadata, jobs, and orchestration stores isolated.
10. Evidence confirms every stored provider-plan envelope validates against
    `IntegrationModelProviderPlan`.
11. Evidence confirms every stored planner result validates against
    `PlannerResult`.
12. Evidence confirms every stored provider-produced chart spec validates
    against `ChartSpec`.
13. Evidence confirms every stored render-plan envelope validates against
    `IntegrationRenderPlan`.
14. Evidence confirms no worker call, approved Home Assistant history read
    during model-provider planning, semantic-memory persistence, Home Assistant
    service/device/state mutation, token generation, real chart artifact file
    write, chart rendering, durable storage, retry/backoff policy, automatic
    progress task, worker streaming, or production orchestration beyond the
    bounded provider/render/artifact bookkeeping occurs.
15. Real artifacts are verified on disk: production orchestration module,
    model-provider module, WebSocket snapshot result routing, provider-plan
    schema, BDD, eval outline, tests, eval, evidence, and verifier anchor.

## Non-Goals

- Worker HTTP calls, worker token generation, worker progress streaming, or
  real worker artifact ingestion.
- Chart rendering or image file writes.
- Changing the dashboard card UI.
- Semantic-memory persistence, migrations, alias reuse, or repair UI.
- Durable job, provider-plan, render-plan, or artifact persistence.
- Background progress tasks, retry/backoff policy, automatic retries, or
  production long-running orchestration semantics.
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
- [docs/decisions/0007-local-first-ollama-compatible-model-provider.md](../decisions/0007-local-first-ollama-compatible-model-provider.md)
- [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../decisions/0008-read-only-mvp-and-sandbox-security.md)
- [docs/decisions/0012-worker-transport-and-authentication.md](../decisions/0012-worker-transport-and-authentication.md)
- [docs/schemas/planner-result.schema.json](../schemas/planner-result.schema.json)
- [docs/schemas/chart-spec.schema.json](../schemas/chart-spec.schema.json)
- [docs/schemas/integration-model-provider-plan.schema.json](../schemas/integration-model-provider-plan.schema.json)
- [docs/schemas/integration-render-plan.schema.json](../schemas/integration-render-plan.schema.json)
- [Ollama API: Generate a chat message](https://docs.ollama.com/api/chat)
- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
