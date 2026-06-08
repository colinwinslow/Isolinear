# Home Assistant Integration: Job Orchestration Subscription Progress Streaming Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-job-orchestration-subscription-progress-streaming-scaffold-spec.md](../../docs/specs/home-assistant-job-orchestration-subscription-progress-streaming-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-job-orchestration-subscription-progress-streaming-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the first integration-owned subscription/progress scaffold.
It proves the integration can subscribe a dashboard card to one existing
config-entry-scoped job, expose the latest schema-valid job snapshot as a
progress event, and stay inside the read-only scaffold boundaries.

## Scenarios

### Scenario A - happy path: accepted subscribe records latest progress event

**Given** a config entry has an existing orchestration job with a latest
schema-valid snapshot
**When** the registered `isolinear/v1/job/subscribe` callback receives that job
ID
**Then** the callback should immediately return the latest
`IntegrationJobSnapshot`
**And** the job state store should contain one deterministic subscription for
that job
**And** the orchestration store should contain one deterministic progress event
for that same job and snapshot

### Scenario B - failure path: unknown job fails before subscription side effects

**Given** a config entry has orchestration and job state stores but no matching
job
**When** `job/subscribe` receives an unknown job ID
**Then** the returned response should fail closed with `unknown_job`
**And** no subscription or progress event should be stored

### Scenario C - isolation path: config entries cannot subscribe to each other's jobs

**Given** two config entries each have their own job state and orchestration
store
**When** the second config entry subscribes to the first config entry's job
**Then** the command should fail closed with `unknown_job`
**And** no subscription or progress event should be stored in the second entry

### Scenario D - isolation path: valid subscriptions stay config-entry scoped

**Given** two config entries each have their own orchestration job
**When** each entry subscribes to its own job
**Then** each entry should record only its own subscription and progress event
**And** each progress event should reference only its own job and latest
snapshot

### Scenario E - schema path: progress event snapshots validate before storage

**Given** accepted subscriptions produce progress event envelopes
**When** the scaffold stores those events
**Then** every returned snapshot and every stored event snapshot should
validate against `IntegrationJobSnapshot` before it is observable

### Scenario F - boundary path: subscription/progress scaffold remains bounded

**Given** the subscription/progress scaffold has handled success and failure
cases
**When** the anchor aggregates observed side effects
**Then** no worker, model-provider, approved Home Assistant history read,
semantic-memory persistence, service/device/state mutation, token-generation,
chart artifact write, chart rendering, durable storage, retry behavior,
automatic progress task, worker streaming, or production orchestration should
occur
**And** job state subscription bookkeeping, progress event bookkeeping, bounded
subscription/progress streaming, and WebSocket registration should be reported
as the allowed side effects

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_job_orchestration_subscription_progress_scaffold.py` for
each scenario.
