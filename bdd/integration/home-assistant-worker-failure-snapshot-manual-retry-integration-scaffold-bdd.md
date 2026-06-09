# Home Assistant Integration: Worker Failure Snapshot/Manual Retry Integration Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-worker-failure-snapshot-manual-retry-integration-scaffold-spec.md](../../docs/specs/home-assistant-worker-failure-snapshot-manual-retry-integration-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-worker-failure-snapshot-manual-retry-integration-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the smallest user-visible worker failure bridge. It proves
that already-validated worker failure metadata becomes a card-facing failed
snapshot with a safe manual retry affordance, without exposing worker internals
or starting automatic retry work.

## Scenarios

### Scenario A - happy path: worker render failure returns failed snapshot

**Given** a config entry has a scaffold-ready orchestration job
**And** the config entry has a deterministic fake worker client configured
that returns a schema-valid failed render result
**When** the registered `isolinear/v1/job/snapshot` callback receives that job
ID
**Then** the dashboard-card result payload should be a schema-valid failed
`IntegrationJobSnapshot`
**And** the snapshot failure stage should be `worker_render`
**And** the snapshot should set `retry_allowed: true`
**And** the orchestration store should contain one schema-valid
`IntegrationWorkerRetryPolicy` envelope for that job

### Scenario B - happy path: worker transport failure returns failed snapshot

**Given** a config entry has a scaffold-ready orchestration job
**And** the config entry has a deterministic fake worker client configured
that returns `accepted: false` with `code: "worker_connection_error"`
**When** the registered `isolinear/v1/job/snapshot` callback receives that job
ID
**Then** the dashboard-card result payload should be a schema-valid failed
`IntegrationJobSnapshot`
**And** the snapshot failure stage should be `worker_transport`
**And** the snapshot should set `retry_allowed: true`
**And** the orchestration store should contain one schema-valid
`IntegrationWorkerTransportFailureClassification` envelope for that job

### Scenario C - manual retry path: retryable worker failure resumes same job

**Given** a worker render failure has produced a failed retryable snapshot
**When** the registered `isolinear/v1/job/retry` callback receives that job ID
**Then** the same job should append a retry-accepted snapshot
**And** approved history retrieval should run through the existing retry
continuation path
**And** the returned snapshot should be schema-valid and ready for future
planning

### Scenario D - failure path: non-retry-safe transport failure is not retryable

**Given** a worker transport failure classification has
`manual_retry_allowed: false`
**When** the registered `isolinear/v1/job/retry` callback receives that job ID
**Then** the command should fail closed with `job_not_retryable`
**And** no approved Home Assistant history should be read for the retry
command
**And** no additional job snapshot should be appended

### Scenario E - schema path: failed snapshots and worker envelopes validate

**Given** worker render and transport failures have produced failed snapshots
and their internal worker failure envelopes
**When** the scaffold validates those records
**Then** every failed snapshot should validate against `IntegrationJobSnapshot`
**And** the worker retry policy and worker transport classification contracts
should still validate

### Scenario F - security path: card-facing payload excludes worker internals

**Given** a configured fake worker client uses an integration-owned bearer
token
**When** worker failure snapshot payloads and eval evidence are inspected
**Then** the fake worker should have received a bearer authorization header
**And** the dashboard-card result payload should not contain the raw token,
`Bearer <redacted>`, worker endpoint, worker request body, retry-policy
metadata, transport-classification metadata, render-plan metadata, artifact
metadata, or worker dispatch metadata
**And** stored internal worker failure metadata should remain redacted

### Scenario G - failure path: unknown job fails before worker failure snapshot

**Given** a config entry has orchestration and job state stores but no matching
job
**When** `job/snapshot` receives an unknown job ID
**Then** the returned response should fail closed with `unknown_job`
**And** the configured worker should not be called
**And** no failed worker snapshot, retry policy, or transport classification
should be stored

### Scenario H - isolation path: config entries cannot retry each other's worker failures

**Given** two config entries each have their own job state, orchestration
store, and fake worker client
**When** the second config entry requests a snapshot or retry for the first
config entry's job
**Then** both commands should fail closed with `unknown_job`
**And** neither entry's worker should be called for the cross-entry request
**And** no failed worker snapshot should be stored in the second entry

### Scenario I - isolation path: valid worker failure snapshots stay config-entry scoped

**Given** two config entries each have their own scaffold-ready job and fake
worker client
**When** each worker returns a failure for its own job
**Then** each entry should append only its own failed worker snapshot
**And** each failed snapshot should reference only that entry's job and
sanitized failure details

### Scenario J - boundary path: worker failure snapshot/manual retry remains bounded

**Given** the worker failure snapshot/manual retry scaffold has handled success
and failure cases
**When** the anchor aggregates observed side effects
**Then** exactly the eligible worker-failure cases should report worker calls,
chart rendering through the worker boundary, internal worker failure metadata
bookkeeping, and failed snapshot bookkeeping
**And** only user-triggered retry of a retryable failed snapshot should report
retry behavior and approved history reads
**And** no semantic-memory persistence, service/device/state mutation, token
generation, token rotation, token leakage, real chart artifact file write,
durable retry queue/storage, worker health check, automatic retry, scheduler,
automatic progress task, new worker transport, or worker metadata exposure to
the card should occur

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_worker_failure_snapshot_manual_retry_integration_scaffold.py`
for each scenario.
