# Home Assistant Integration: Job Orchestration Artifact Storage Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-job-orchestration-artifact-storage-scaffold-spec.md](../../docs/specs/home-assistant-job-orchestration-artifact-storage-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-job-orchestration-artifact-storage-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the first integration-owned artifact storage scaffold. It
proves the integration can turn a scaffold-ready job into an inspectable
placeholder chart-result object for the dashboard card while staying inside
the read-only, non-rendering scaffold boundaries.

## Scenarios

### Scenario A - happy path: scaffold-ready snapshot records placeholder artifact

**Given** a config entry has an orchestration job whose latest snapshot is a
schema-valid scaffold-ready planning snapshot
**When** the registered `isolinear/v1/job/snapshot` callback receives that job
ID
**Then** the callback should return a schema-valid `complete`
`IntegrationJobSnapshot`
**And** that snapshot should contain placeholder chart metadata for the same
job
**And** the orchestration store should contain one deterministic artifact
metadata envelope for that same job and source snapshot

### Scenario B - idempotence path: repeated snapshot requests reuse the artifact

**Given** a scaffold-ready job already has an artifact-backed complete snapshot
and artifact metadata
**When** `job/snapshot` is requested again for the same job
**Then** the callback should return the existing complete snapshot
**And** no second artifact metadata envelope should be stored

### Scenario C - failure path: unknown job fails before artifact side effects

**Given** a config entry has orchestration and job state stores but no matching
job
**When** `job/snapshot` receives an unknown job ID
**Then** the returned response should fail closed with `unknown_job`
**And** no artifact metadata or complete snapshot should be stored

### Scenario D - isolation path: config entries cannot retrieve each other's artifacts

**Given** two config entries each have their own job state and orchestration
store
**When** the second config entry requests a snapshot for the first config
entry's job
**Then** the command should fail closed with `unknown_job`
**And** no artifact metadata or complete snapshot should be stored in the
second entry

### Scenario E - isolation path: valid artifacts stay config-entry scoped

**Given** two config entries each have their own scaffold-ready orchestration
job
**When** each entry requests a snapshot for its own job
**Then** each entry should record only its own artifact metadata
**And** each returned complete snapshot should reference only its own job,
artifact metadata, and approved entity disclosure

### Scenario F - schema path: artifact metadata and snapshots validate before storage

**Given** accepted artifact snapshot requests produce artifact metadata and
complete snapshots
**When** the scaffold stores those artifacts and snapshots
**Then** every returned and stored snapshot should validate against
`IntegrationJobSnapshot`
**And** every stored artifact metadata envelope should validate against
`IntegrationArtifactMetadata`

### Scenario G - boundary path: artifact storage scaffold remains bounded

**Given** the artifact storage scaffold has handled success and failure cases
**When** the anchor aggregates observed side effects
**Then** no worker, model-provider, approved Home Assistant history read
during artifact storage, semantic-memory persistence, service/device/state
mutation, token-generation, real chart artifact file write, chart rendering,
durable storage, retry behavior, automatic progress task, worker streaming, or
production orchestration should occur
**And** job state snapshot storage, artifact metadata bookkeeping, and
WebSocket registration should be reported as the allowed side effects

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_job_orchestration_artifact_storage_scaffold.py` for each
scenario.
