# Home Assistant Integration: Job Orchestration Model-Provider Planning Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-job-orchestration-model-provider-planning-scaffold-spec.md](../../docs/specs/home-assistant-job-orchestration-model-provider-planning-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-job-orchestration-model-provider-planning-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the first integration-owned Ollama-compatible planner
boundary. It proves the integration can accept a provider-produced `ChartSpec`
only after schema and allowlist validation while staying inside the read-only,
non-rendering scaffold boundaries.

## Scenarios

### Scenario A - happy path: provider-produced chart spec records provider plan and render plan

**Given** a config entry has an orchestration job whose latest snapshot is a
schema-valid scaffold-ready planning snapshot
**And** the config entry has a deterministic fake Ollama-compatible planner
client configured
**When** the registered `isolinear/v1/job/snapshot` callback receives that job
ID
**Then** the orchestration store should contain one deterministic
model-provider planning envelope for that same job and source snapshot
**And** the render plan should use the provider-produced schema-valid
`ChartSpec`
**And** the callback should still return the schema-valid artifact-backed
`complete` `IntegrationJobSnapshot`

### Scenario B - idempotence path: repeated snapshot requests reuse provider plan

**Given** a provider-planned scaffold job already has a model-provider plan,
render plan, artifact metadata, and artifact-backed complete snapshot
**When** `job/snapshot` is requested again for the same job
**Then** the callback should return the existing complete snapshot
**And** no second provider call, model-provider plan, render plan, artifact
metadata, or complete snapshot should be created

### Scenario C - failure path: off-allowlist entity reference fails before storage

The entity gate is structural (ADR-0023): it rejects off-allowlist entities only
where they carry data-access or persistence meaning — chart-spec
`series`/`overlays` sources and `memory_proposals` entity references — and ignores
entity-shaped tokens in inert free-text fields.

**Given** a configured fake planner returns schema-valid provider output whose
chart-spec source or `memory_proposals` entity reference names an entity outside
the source snapshot's approved disclosure
**When** `job/snapshot` requests planning for that job
**Then** the command should fail closed with
`model_provider_referenced_unapproved_entity`
**And** no model-provider plan metadata, render-plan metadata, artifact
metadata, or complete snapshot should be stored
**And** provider output that merely contains an entity-shaped token in a
free-text field (e.g. `chart_id`, `title`, axis metadata, `notes`,
`reasoning_summary`) is not treated as a reference and renders to a complete
snapshot

### Scenario D - failure path: invalid provider chart spec fails before storage

**Given** a configured fake planner returns `chart_spec_ready` with a malformed
`ChartSpec`
**When** `job/snapshot` requests planning for that job
**Then** the command should fail closed with `invalid_model_provider_chart_spec`
**And** no model-provider plan metadata, render-plan metadata, artifact
metadata, or complete snapshot should be stored

### Scenario E - failure path: unknown job fails before provider call

**Given** a config entry has orchestration and job state stores but no matching
job
**When** `job/snapshot` receives an unknown job ID
**Then** the returned response should fail closed with `unknown_job`
**And** the configured planner should not be called
**And** no model-provider plan metadata, render-plan metadata, artifact
metadata, or complete snapshot should be stored

### Scenario F - isolation path: config entries cannot call providers for each other's jobs

**Given** two config entries each have their own job state, orchestration
store, and fake planner client
**When** the second config entry requests a snapshot for the first config
entry's job
**Then** the command should fail closed with `unknown_job`
**And** neither entry's planner should be called for the cross-entry request
**And** no model-provider plan metadata, render-plan metadata, artifact
metadata, or complete snapshot should be stored in the second entry

### Scenario G - isolation path: valid provider plans stay config-entry scoped

**Given** two config entries each have their own scaffold-ready orchestration
job and fake planner client
**When** each entry requests a snapshot for its own job
**Then** each entry should record only its own model-provider plan, render
plan, and artifact metadata
**And** each render plan should reference only its own provider-produced chart
spec and approved entity disclosure

### Scenario H - schema path: provider plans, planner results, chart specs, and render plans validate

**Given** accepted model-provider planning requests produce provider plans,
planner results, chart specs, and render plans
**When** the scaffold stores those records
**Then** every stored provider-plan envelope should validate against
`IntegrationModelProviderPlan`
**And** every stored planner result should validate against `PlannerResult`
**And** every stored provider-produced chart spec should validate against
`ChartSpec`
**And** every stored render-plan envelope should validate against
`IntegrationRenderPlan`

### Scenario I - boundary path: model-provider planning remains bounded

**Given** the model-provider planning scaffold has handled success and failure
cases
**When** the anchor aggregates observed side effects
**Then** exactly the eligible configured-planner cases should report planner
role calls
**And** no worker call, approved Home Assistant history read during
model-provider planning, semantic-memory persistence, service/device/state
mutation, token generation, real chart artifact file write, chart rendering,
durable storage, retry/backoff policy, automatic progress task, worker
streaming, or production orchestration should occur
**And** model-provider plan bookkeeping, render-plan bookkeeping, existing
artifact metadata bookkeeping, job state snapshot storage, and WebSocket
registration should be reported as the allowed side effects

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_job_orchestration_model_provider_planning_scaffold.py`
for each scenario.
