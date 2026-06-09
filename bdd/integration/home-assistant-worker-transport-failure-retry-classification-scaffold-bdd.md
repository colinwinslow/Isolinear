# Home Assistant Integration: Worker Transport Failure Retry Classification Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-worker-transport-failure-retry-classification-scaffold-spec.md](../../docs/specs/home-assistant-worker-transport-failure-retry-classification-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-worker-transport-failure-retry-classification-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the smallest worker transport failure retry classification
surface. It proves the integration can classify worker-client failures that
happen before a valid render result exists while preserving redaction and the
existing fail-closed worker boundary.

## Scenarios

### Scenario A - happy path: connection failure records retry classification

**Given** a config entry has a scaffold-ready orchestration job
**And** the config entry has a deterministic fake worker client configured
that returns `accepted: false` with `code: "worker_connection_error"`
**When** the registered `isolinear/v1/job/snapshot` callback receives that job
ID
**Then** the fake worker should receive one schema-valid worker transport
request
**And** the orchestration store should contain one schema-valid
`IntegrationWorkerTransportFailureClassification` envelope for that job
**And** the failure family should be `connection`
**And** the command should still fail closed before worker dispatch metadata,
render-plan metadata, artifact metadata, worker progress metadata, worker
retry-policy metadata, or a complete snapshot is stored

### Scenario B - classification path: HTTP and malformed responses map deterministically

**Given** fake worker clients can return `accepted: false` transport failures
with `worker_http_error` and `worker_response_error`
**When** each failure is handled by its own config-entry job
**Then** the HTTP failure should classify as `http`
**And** the malformed-response failure should classify as `malformed_response`
**And** retry eligibility should follow the worker client's sanitized
`retry_safe` decision

### Scenario C - schema path: transport classification contracts validate

**Given** accepted transport failure classification has produced
classification metadata, worker transport requests, and render requests
**When** the scaffold validates those records
**Then** every worker transport failure classification should validate against
`IntegrationWorkerTransportFailureClassification`
**And** the worker transport and render request contracts should still
validate

### Scenario D - security path: worker authorization and failure text are redacted

**Given** a configured fake worker client uses an integration-owned bearer
token
**When** transport failure classification metadata and eval evidence are
inspected
**Then** the fake worker should have received a bearer authorization header
**And** stored classification metadata and evidence should contain only
`Bearer <redacted>`
**And** worker-originated failure codes or messages containing bearer material
should be normalized before they are stored or returned
**And** the raw token should not appear in the result payload

### Scenario E - failure path: unknown job fails before transport classification

**Given** a config entry has orchestration and job state stores but no matching
job
**When** `job/snapshot` receives an unknown job ID
**Then** the returned response should fail closed with `unknown_job`
**And** the configured worker should not be called
**And** no transport failure classification should be stored

### Scenario F - isolation path: config entries cannot classify each other's jobs

**Given** two config entries each have their own job state, orchestration
store, and fake worker client
**When** the second config entry requests a snapshot for the first config
entry's job
**Then** the command should fail closed with `unknown_job`
**And** neither entry's worker should be called for the cross-entry request
**And** no transport failure classification should be stored in the second
entry

### Scenario G - isolation path: valid classifications stay config-entry scoped

**Given** two config entries each have their own scaffold-ready job and fake
worker client
**When** each worker returns a transport failure for its own job
**Then** each entry should record only its own transport failure
classification
**And** each classification should reference only that entry's job, source
snapshot, worker metadata, and redacted request

### Scenario H - boundary path: transport classification remains bounded

**Given** the worker transport failure classification scaffold has handled
success and failure cases
**When** the anchor aggregates observed side effects
**Then** exactly the eligible transport-failure cases should report worker
calls, chart rendering through the worker boundary, and transport
classification bookkeeping
**And** no Home Assistant history read during worker transport failure
handling, semantic-memory persistence, service/device/state mutation, token
generation, token rotation, token leakage, real chart artifact file write,
durable retry queue/storage, worker health check, automatic retry, scheduler,
automatic progress task, new worker transport, worker render-result retry
policy write, or production orchestration should occur

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_worker_transport_failure_retry_classification_scaffold.py`
for each scenario.
