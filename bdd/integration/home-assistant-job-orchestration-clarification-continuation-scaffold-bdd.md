# Home Assistant Integration: Job Orchestration Clarification Continuation Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-job-orchestration-clarification-continuation-scaffold-spec.md](../../docs/specs/home-assistant-job-orchestration-clarification-continuation-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-job-orchestration-clarification-continuation-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the first integration-owned continuation path after an
ambiguous `job/start` response. It proves the integration can accept one
returned approved clarification option, resume the same job through approved
history retrieval, and remain inside the read-only scaffold boundaries.

## Scenarios

### Scenario A - happy path: accepted clarification resumes the same job

**Given** a config entry has an existing job whose latest snapshot is
`clarification_needed` with approved entity options
**When** the registered `isolinear/v1/clarification/answer` callback receives a
returned approved option ID for that job and question
**Then** the callback should return a schema-valid scaffold-ready
`IntegrationJobSnapshot`
**And** the job store should contain deterministic clarification-accepted,
fetching-history, and scaffold-ready continuation snapshots for the same job
**And** the history store should contain only the selected approved entity

### Scenario B - failure path: unknown option fails before history

**Given** a config entry has a pending approved-entity clarification
**When** `clarification/answer` receives an option ID that was not returned in
that clarification
**Then** the returned response should fail closed with `unknown_clarification_option`
**And** Home Assistant history should not be read for that request
**And** no continuation snapshot should be appended to the job

### Scenario C - failure path: wrong question fails before history

**Given** a config entry has a pending approved-entity clarification
**When** `clarification/answer` receives the right option ID for a different
question ID
**Then** the returned response should fail closed with
`clarification_question_mismatch`
**And** Home Assistant history should not be read for that request
**And** no continuation snapshot should be appended to the job

### Scenario D - failure path: colliding option fails before history

**Given** a config entry has a pending approved-entity clarification whose
returned option ID collides across multiple current approved entities
**When** `clarification/answer` receives the colliding option ID
**Then** the returned response should fail closed with
`ambiguous_clarification_option`
**And** Home Assistant history should not be read for that request
**And** no continuation snapshot should be appended to the job

### Scenario E - isolation path: config entries cannot answer each other's jobs

**Given** two config entries each have their own job and pending clarification
**When** the second config entry answers the first config entry's job
**Then** the command should fail closed with `unknown_job`
**And** no Home Assistant history should be read
**And** both entries' pending clarification state should remain scoped

### Scenario F - isolation path: valid continuations stay config-entry scoped

**Given** two config entries each have a pending clarification with different
approved options
**When** each entry answers its own clarification
**Then** each entry should continue only its own job
**And** each history store and continuation run summary should contain only its
selected approved entity

### Scenario G - schema path: continuation snapshots validate before storage

**Given** accepted clarification continuation produces scaffold snapshots
**When** the continuation appends clarification-accepted, fetching-history, and
scaffold-ready snapshots
**Then** every returned and stored snapshot should validate against
`IntegrationJobSnapshot` before it is observable

### Scenario H - boundary path: continuation scaffold remains bounded

**Given** the continuation scaffold has handled success and failure cases
**When** the anchor aggregates observed side effects
**Then** no worker, model-provider, semantic-memory persistence,
service/device/state mutation, token-generation, chart artifact write, chart
rendering, durable storage, retry behavior, subscription progress streaming, or
production orchestration should occur
**And** approved catalog reads, approved fake history reads, job state writes,
history store writes, continuation bookkeeping, and WebSocket registration
should be reported as the allowed side effects

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_job_orchestration_clarification_continuation_scaffold.py`
for each scenario.
