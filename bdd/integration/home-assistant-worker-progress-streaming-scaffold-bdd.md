# Home Assistant Integration: Worker Progress Streaming Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-worker-progress-streaming-scaffold-spec.md](../../docs/specs/home-assistant-worker-progress-streaming-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-worker-progress-streaming-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the first bounded worker progress streaming scaffold. It
proves the integration can record worker progress from the configured worker
client, link it to existing card subscriptions, return only schema-valid job
snapshots, redact worker credentials, and stay inside read-only scaffold
boundaries.

## Scenarios

### Scenario A - happy path: subscribed worker job records progress snapshots

**Given** a config entry has an existing subscribed orchestration job whose
latest snapshot is scaffold-ready
**And** the config entry has a deterministic fake worker client configured
that returns bounded progress payloads with its render result
**When** the registered `isolinear/v1/job/snapshot` callback receives that job
ID
**Then** the fake worker should receive one schema-valid worker transport
request
**And** the job should contain schema-valid `rendering` snapshots for each
worker progress payload before the final complete snapshot
**And** the orchestration store should contain one schema-valid worker progress
event for each rendering snapshot

### Scenario B - subscription path: worker progress links to card subscriptions

**Given** the dashboard card has subscribed to the same config-entry-scoped job
before worker rendering begins
**When** worker progress is recorded for that job
**Then** every worker progress event should include the existing subscription
ID for that job
**And** no progress event should include subscriptions from another config
entry or job

### Scenario C - schema path: worker progress contracts validate before storage

**Given** accepted worker progress requests produce progress payloads, worker
progress envelopes, rendering snapshots, worker transport requests, render
requests, render results, render plans, chart specs, history series, and worker
dispatch envelopes
**When** the scaffold validates those records
**Then** every worker progress envelope should validate against
`IntegrationWorkerProgress`
**And** every worker progress event snapshot should validate against
`IntegrationJobSnapshot`
**And** the worker transport, render request, render result, render plan, chart
spec, history series, and worker dispatch contracts should still validate

### Scenario D - security path: worker authorization is redacted

**Given** a configured fake worker client uses an integration-owned bearer
token
**When** worker progress metadata and eval evidence are inspected
**Then** the fake worker should have received a bearer authorization header
**And** stored worker progress metadata and evidence should contain only
`Bearer <redacted>`
**And** the raw token should not appear in the result payload

### Scenario E - idempotence path: repeated snapshot requests reuse progress

**Given** a worker-progress scaffold job already has worker progress events,
worker dispatch, render plan, artifact metadata, and an artifact-backed
complete snapshot
**When** `job/snapshot` is requested again for the same job
**Then** the callback should return the existing complete snapshot
**And** no second worker call, worker progress event, worker dispatch, render
plan, artifact metadata, or complete snapshot should be created

### Scenario F - failure path: invalid worker progress fails before storage

**Given** a configured fake worker client returns an invalid progress payload
with an otherwise successful render result
**And** an HTTP worker response with non-list `progress_events` is forwarded to
the same progress validator
**When** `job/snapshot` requests worker dispatch for that job
**Then** the command should fail closed with `invalid_integration_worker_progress`
**And** no worker progress metadata, worker dispatch metadata, render-plan
metadata, artifact metadata, or complete snapshot should be stored

### Scenario G - failure path: unknown job fails before worker progress

**Given** a config entry has orchestration and job state stores but no matching
job
**When** `job/snapshot` receives an unknown job ID
**Then** the returned response should fail closed with `unknown_job`
**And** the configured worker should not be called
**And** no worker progress event should be stored

### Scenario H - isolation path: config entries cannot stream progress for each other's jobs

**Given** two config entries each have their own job state, orchestration
store, subscription, and fake worker client
**When** the second config entry requests a snapshot for the first config
entry's job
**Then** the command should fail closed with `unknown_job`
**And** neither entry's worker should be called for the cross-entry request
**And** no worker progress event should be stored in the second entry

### Scenario I - isolation path: valid worker progress stays config-entry scoped

**Given** two config entries each have their own subscribed scaffold-ready job
and fake worker client
**When** each entry requests a snapshot for its own job
**Then** each entry should record only its own worker progress events
**And** each progress event should reference only that entry's job,
subscription IDs, worker metadata, and snapshots

### Scenario J - boundary path: worker progress remains bounded

**Given** the worker progress scaffold has handled success and failure cases
**When** the anchor aggregates observed side effects
**Then** exactly the eligible configured-worker cases should report worker
calls, chart rendering through the worker boundary, and bounded worker progress
streaming bookkeeping
**And** no Home Assistant history read during worker progress,
semantic-memory persistence, service/device/state mutation, token generation,
token rotation, token leakage, real chart artifact file write, durable storage,
retry/backoff policy, worker health check, automatic progress task, new worker
streaming transport, or production orchestration should occur

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_worker_progress_streaming_scaffold.py` for each scenario.
