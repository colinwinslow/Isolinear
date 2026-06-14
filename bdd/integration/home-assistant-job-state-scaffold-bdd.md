# Home Assistant Integration: Job State Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-job-state-scaffold-spec.md](../../docs/specs/home-assistant-job-state-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-job-state-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the first integration-owned job state surface behind the
registered WebSocket commands. It proves the dashboard card can work against
deterministic, config-entry-scoped `IntegrationJobSnapshot` state while the
integration still does not cross worker, model, history, memory, artifact,
token, or mutation boundaries.

## Scenarios

### Scenario A - happy path: starting a job creates deterministic state

**Given** a known Isolinear config entry with an initialized job state store
**When** the registered `isolinear/v1/job/start` callback handles a prompt
**Then** the callback should return a schema-valid `IntegrationJobSnapshot`
with deterministic job and snapshot IDs
**And** the snapshot should be stored under the targeted config entry

### Scenario B - happy path: snapshot, retry, and clarification update existing jobs

**Given** an existing job created by the targeted config entry
**When** the registered snapshot, retry, and clarification-answer callbacks
handle that job ID
**Then** each callback should return a schema-valid latest snapshot
**And** retry and clarification-answer should append deterministic snapshot IDs
without calling orchestration

### Scenario C - happy path: subscription records the callback shape

**Given** an existing job created by the targeted config entry
**When** the registered `isolinear/v1/job/subscribe` callback handles that job
**Then** the callback should return the latest schema-valid snapshot
**And** the job state store should record the subscription callback/event shape

### Scenario D - isolation path: config entries cannot see each other's jobs

**Given** two Isolinear config entries with separate job state stores
**When** the second config entry asks for the first config entry's job snapshot
**Then** the request should fail closed with an unknown-job WebSocket error
**And** no snapshot should be returned

### Scenario E - failure path: unknown jobs fail closed

**Given** a known Isolinear config entry
**When** snapshot, retry, clarification-answer, or subscribe commands reference
an unknown job ID
**Then** each command should send a structured WebSocket error
**And** no new scaffold snapshot should be created for that unknown job

### Scenario F - lifecycle path: unloading removes job state

**Given** an Isolinear config entry with stored job state and subscriptions
**When** `async_unload_entry` unloads that entry
**Then** the config-entry job state store should be removed from
`hass.data["isolinear"]`

### Scenario G - boundary path: job state remains non-orchestrating

**Given** job state has handled success and failure cases
**When** the anchor aggregates observed side effects
**Then** no worker, model-provider, history, semantic-memory persistence,
service/device/state mutation, token-generation, chart artifact write, or real
job orchestration should occur
**And** in-memory job state and subscription bookkeeping should be reported as
the allowed side effects

### Scenario H - schema path: malformed snapshots are rejected before storage

**Given** a malformed scaffold snapshot that does not satisfy
`IntegrationJobSnapshot`
**When** the job state store attempts to persist it
**Then** the snapshot should be rejected with a structured schema error
**And** the job's stored snapshots and latest snapshot should remain unchanged

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_job_state_scaffold.py` for each scenario.
