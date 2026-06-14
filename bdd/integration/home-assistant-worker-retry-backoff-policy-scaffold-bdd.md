# Home Assistant Integration: Worker Retry/Backoff Policy Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-worker-retry-backoff-policy-scaffold-spec.md](../../docs/specs/home-assistant-worker-retry-backoff-policy-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-worker-retry-backoff-policy-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the smallest worker retry/backoff policy scaffold. It proves
the integration can record a schema-valid, redacted manual retry decision for a
worker render failure while preserving the existing fail-closed worker
boundary.

## Scenarios

### Scenario A - happy path: worker render failure records retry/backoff policy

**Given** a config entry has a scaffold-ready orchestration job
**And** the config entry has a deterministic fake worker client configured
that returns a schema-valid failed render result
**When** the registered `isolinear/v1/job/snapshot` callback receives that job
ID
**Then** the fake worker should receive one schema-valid worker transport
request
**And** the orchestration store should contain one schema-valid
`IntegrationWorkerRetryPolicy` envelope for that job
**And** the command should still fail closed before worker dispatch metadata,
render-plan metadata, artifact metadata, worker progress metadata, or a
complete snapshot is stored

### Scenario B - schema path: retry/backoff policy contracts validate

**Given** accepted worker failure policy recording has produced retry/backoff
metadata, worker transport requests, render requests, and failed render
results
**When** the scaffold validates those records
**Then** every worker retry/backoff policy should validate against
`IntegrationWorkerRetryPolicy`
**And** the worker transport, render request, and render result contracts
should still validate

### Scenario C - security path: worker authorization is redacted

**Given** a configured fake worker client uses an integration-owned bearer
token
**When** retry/backoff policy metadata and eval evidence are inspected
**Then** the fake worker should have received a bearer authorization header
**And** stored retry/backoff metadata and evidence should contain only
`Bearer <redacted>`
**And** a worker-originated failure code containing bearer material should be
normalized before it is stored or returned
**And** the raw token should not appear in the result payload

### Scenario D - failure path: unknown job fails before retry/backoff policy

**Given** a config entry has orchestration and job state stores but no matching
job
**When** `job/snapshot` receives an unknown job ID
**Then** the returned response should fail closed with `unknown_job`
**And** the configured worker should not be called
**And** no retry/backoff policy should be stored

### Scenario E - isolation path: config entries cannot record policies for each other's jobs

**Given** two config entries each have their own job state, orchestration
store, and fake worker client
**When** the second config entry requests a snapshot for the first config
entry's job
**Then** the command should fail closed with `unknown_job`
**And** neither entry's worker should be called for the cross-entry request
**And** no retry/backoff policy should be stored in the second entry

### Scenario F - isolation path: valid retry/backoff policies stay config-entry scoped

**Given** two config entries each have their own scaffold-ready job and fake
worker client
**When** each worker returns a failed render result for its own job
**Then** each entry should record only its own retry/backoff policy
**And** each policy should reference only that entry's job, source snapshot,
worker metadata, and redacted request

### Scenario G - boundary path: retry/backoff policy remains bounded

**Given** the worker retry/backoff scaffold has handled success and failure
cases
**When** the anchor aggregates observed side effects
**Then** exactly the eligible worker-failure cases should report worker calls,
chart rendering through the worker boundary, and retry/backoff policy
bookkeeping
**And** no Home Assistant history read during worker retry/backoff handling,
semantic-memory persistence, service/device/state mutation, token generation,
token rotation, token leakage, real chart artifact file write, durable retry
queue/storage, worker health check, automatic retry, scheduler, automatic
progress task, new worker transport, or production orchestration should occur

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_worker_retry_backoff_policy_scaffold.py` for each
scenario.
