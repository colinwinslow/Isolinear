# Home Assistant Integration: Job Orchestration Retry Continuation Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-job-orchestration-retry-continuation-scaffold-spec.md](../../docs/specs/home-assistant-job-orchestration-retry-continuation-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-job-orchestration-retry-continuation-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the first integration-owned continuation path after a failed
scaffold job. It proves the integration can accept a user-triggered retry for a
retryable failed job, reuse the same config-entry-scoped job and approved
history boundaries, and stay inside the read-only scaffold boundaries.

## Scenarios

### Scenario A - happy path: accepted retry resumes the same failed job

**Given** a config entry has an existing job whose latest snapshot is failed
with `retry_allowed: true`
**When** the registered `isolinear/v1/job/retry` callback receives that job ID
and the approved history source can now satisfy the original prompt
**Then** the callback should return a schema-valid scaffold-ready
`IntegrationJobSnapshot`
**And** the job store should contain deterministic retry-accepted,
fetching-history, and scaffold-ready continuation snapshots for the same job
**And** the history store should contain only the retried approved entity

### Scenario B - failure path: unknown job fails before retry side effects

**Given** a config entry has an orchestration store but no matching job
**When** `job/retry` receives an unknown job ID
**Then** the returned response should fail closed with `unknown_job`
**And** Home Assistant history should not be read for that request
**And** no retry continuation snapshot should be appended

### Scenario C - failure path: non-retryable job fails before retry side effects

**Given** a config entry has an existing job whose latest snapshot is not a
retryable failed snapshot
**When** `job/retry` receives that job ID
**Then** the returned response should fail closed with `job_not_retryable`
**And** Home Assistant history should not be read for that request
**And** no retry continuation snapshot should be appended

### Scenario D - isolation path: config entries cannot retry each other's jobs

**Given** two config entries each have their own job state and orchestration
store
**When** the second config entry retries the first config entry's job
**Then** the command should fail closed with `unknown_job`
**And** no Home Assistant history should be read
**And** both entries' job state should remain scoped

### Scenario E - isolation path: valid retries stay config-entry scoped

**Given** two config entries each have a retryable failed job with different
approved entities
**When** each entry retries its own job
**Then** each entry should continue only its own job
**And** each history store and retry run summary should contain only its
selected approved entity

### Scenario F - schema path: retry snapshots validate before storage

**Given** accepted retry continuation produces scaffold snapshots
**When** the continuation appends retry-accepted, fetching-history, and
scaffold-ready snapshots
**Then** every returned and stored snapshot should validate against
`IntegrationJobSnapshot` before it is observable

### Scenario G - boundary path: retry scaffold remains bounded

**Given** the retry continuation scaffold has handled success and failure cases
**When** the anchor aggregates observed side effects
**Then** no worker, model-provider, semantic-memory persistence,
service/device/state mutation, token-generation, chart artifact write, chart
rendering, durable storage, subscription progress streaming, automatic retry
loop, worker retry behavior, or production orchestration should occur
**And** approved catalog reads, approved fake history reads, job state writes,
history store writes, retry continuation bookkeeping, user-triggered retry
continuation, and WebSocket registration should be reported as the allowed side
effects

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_job_orchestration_retry_continuation_scaffold.py` for each
scenario.
