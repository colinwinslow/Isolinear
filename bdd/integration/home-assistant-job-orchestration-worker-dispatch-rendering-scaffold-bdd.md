# Home Assistant Integration: Job Orchestration Worker Dispatch/Rendering Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-spec.md](../../docs/specs/home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the first integration-owned worker dispatch boundary. It
proves the integration can send a validated render plan and staged approved
history to an ADR-0012 worker client while redacting worker credentials and
staying inside bounded, read-only orchestration semantics.

## Scenarios

### Scenario A - happy path: worker dispatch records render result

**Given** a config entry has an orchestration job whose latest snapshot is a
schema-valid scaffold-ready planning snapshot
**And** the config entry has a deterministic fake worker client configured
**When** the registered `isolinear/v1/job/snapshot` callback receives that job
ID
**Then** the fake worker should receive one schema-valid worker transport
request
**And** the orchestration store should contain one deterministic worker
dispatch envelope for that same job, render plan, artifact, and source snapshot
**And** the callback should still return the schema-valid artifact-backed
`complete` `IntegrationJobSnapshot`

### Scenario B - idempotence path: repeated snapshot requests reuse worker dispatch

**Given** a worker-dispatched scaffold job already has a worker dispatch,
render plan, artifact metadata, and artifact-backed complete snapshot
**When** `job/snapshot` is requested again for the same job
**Then** the callback should return the existing complete snapshot
**And** no second worker call, worker dispatch, render plan, artifact metadata,
or complete snapshot should be created

### Scenario C - schema path: worker request, response, and dispatch validate

**Given** accepted worker dispatch requests produce worker transport requests,
render requests, render results, render plans, chart specs, history series, and
worker dispatch envelopes
**When** the scaffold validates those records
**Then** every stored worker dispatch should validate against
`IntegrationWorkerDispatch`
**And** every worker transport request should validate against
`WorkerTransportRequest`
**And** every render request, render result, render plan, chart spec, and
history series should validate against its JSON Schema before storage

### Scenario D - security path: worker authorization is redacted

**Given** a configured fake worker client uses an integration-owned bearer
token
**When** worker dispatch metadata and eval evidence are inspected
**Then** the fake worker should have received a bearer authorization header
**And** stored worker dispatch metadata and evidence should contain only
`Bearer <redacted>`
**And** the raw token should not appear in the result payload

### Scenario E - failure path: worker failure fails before storage

**Given** a configured fake worker client returns a failed render response
**When** `job/snapshot` requests worker dispatch for that job
**Then** the command should fail closed with the worker failure code
**And** no worker dispatch metadata, render-plan metadata, artifact metadata,
or complete snapshot should be stored

### Scenario F - failure path: unknown job fails before worker call

**Given** a config entry has orchestration and job state stores but no matching
job
**When** `job/snapshot` receives an unknown job ID
**Then** the returned response should fail closed with `unknown_job`
**And** the configured worker should not be called
**And** no worker dispatch metadata, render-plan metadata, artifact metadata,
or complete snapshot should be stored

### Scenario G - isolation path: config entries cannot dispatch workers for each other's jobs

**Given** two config entries each have their own job state, orchestration
store, and fake worker client
**When** the second config entry requests a snapshot for the first config
entry's job
**Then** the command should fail closed with `unknown_job`
**And** neither entry's worker should be called for the cross-entry request
**And** no worker dispatch metadata, render-plan metadata, artifact metadata,
or complete snapshot should be stored in the second entry

### Scenario H - isolation path: valid worker dispatches stay config-entry scoped

**Given** two config entries each have their own scaffold-ready orchestration
job and fake worker client
**When** each entry requests a snapshot for its own job
**Then** each entry should record only its own worker dispatch, render plan,
and artifact metadata
**And** each worker request should contain only that entry's staged approved
history and render plan

### Scenario I - boundary path: worker dispatch remains bounded

**Given** the worker dispatch scaffold has handled success and failure cases
**When** the anchor aggregates observed side effects
**Then** exactly the eligible configured-worker cases should report worker
calls and chart rendering through the worker boundary
**And** no Home Assistant history read during worker dispatch,
semantic-memory persistence, service/device/state mutation, token generation,
real chart artifact file write, durable storage, retry/backoff policy,
automatic progress task, worker streaming, or production orchestration should
occur
**And** worker dispatch bookkeeping, render-plan bookkeeping, existing artifact
metadata bookkeeping, job state snapshot storage, and WebSocket registration
should be reported as the allowed side effects

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_job_orchestration_worker_dispatch_rendering_scaffold.py`
for each scenario.
