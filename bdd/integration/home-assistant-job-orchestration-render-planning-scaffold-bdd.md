# Home Assistant Integration: Job Orchestration Render Planning Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-job-orchestration-render-planning-scaffold-spec.md](../../docs/specs/home-assistant-job-orchestration-render-planning-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-job-orchestration-render-planning-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the first integration-owned render planning scaffold. It
proves the integration can create an inspectable planned-render record for a
future trusted renderer while staying inside the read-only, non-rendering,
non-model-provider scaffold boundaries.

## Scenarios

### Scenario A - happy path: scaffold-ready snapshot records a render plan

**Given** a config entry has an orchestration job whose latest snapshot is a
schema-valid scaffold-ready planning snapshot
**When** the registered `isolinear/v1/job/snapshot` callback receives that job
ID
**Then** the orchestration store should contain one deterministic render-plan
envelope for that same job and source snapshot
**And** the render plan should reference the placeholder artifact metadata for
the same job
**And** the callback should still return the schema-valid artifact-backed
`complete` `IntegrationJobSnapshot`

### Scenario B - idempotence path: repeated snapshot requests reuse the render plan

**Given** a scaffold-ready job already has a render plan, artifact metadata,
and artifact-backed complete snapshot
**When** `job/snapshot` is requested again for the same job
**Then** the callback should return the existing complete snapshot
**And** no second render-plan envelope or artifact metadata envelope should be
stored

### Scenario C - failure path: unknown job fails before render planning side effects

**Given** a config entry has orchestration and job state stores but no matching
job
**When** `job/snapshot` receives an unknown job ID
**Then** the returned response should fail closed with `unknown_job`
**And** no render-plan metadata, artifact metadata, or complete snapshot
should be stored

### Scenario D - isolation path: config entries cannot retrieve each other's render plans

**Given** two config entries each have their own job state and orchestration
store
**When** the second config entry requests a snapshot for the first config
entry's job
**Then** the command should fail closed with `unknown_job`
**And** no render-plan metadata, artifact metadata, or complete snapshot
should be stored in the second entry

### Scenario E - isolation path: valid render plans stay config-entry scoped

**Given** two config entries each have their own scaffold-ready orchestration
job
**When** each entry requests a snapshot for its own job
**Then** each entry should record only its own render plan and artifact
metadata
**And** each render plan should reference only its own job, artifact metadata,
and approved entity disclosure

### Scenario F - schema path: render plans and chart specs validate before storage

**Given** accepted render planning requests produce render plans and
placeholder chart specs
**When** the scaffold stores those render plans
**Then** every stored render-plan envelope should validate against
`IntegrationRenderPlan`
**And** every stored placeholder chart spec should validate against `ChartSpec`

### Scenario G - boundary path: render planning scaffold remains bounded

**Given** the render planning scaffold has handled success and failure cases
**When** the anchor aggregates observed side effects
**Then** no model-provider/Ollama call, worker call, approved Home Assistant
history read during render planning, semantic-memory persistence,
service/device/state mutation, token generation, real chart artifact file
write, chart rendering, durable storage, retry/backoff policy, automatic
progress task, worker streaming, or production orchestration should occur
**And** render-plan bookkeeping, existing artifact metadata bookkeeping, job
state snapshot storage, and WebSocket registration should be reported as the
allowed side effects

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_job_orchestration_render_planning_scaffold.py` for each
scenario.
