# Home Assistant Integration: Job Orchestration Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-job-orchestration-scaffold-spec.md](../../docs/specs/home-assistant-job-orchestration-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-job-orchestration-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the first integration-owned job orchestration scaffold. It
proves `job/start` can compose the approved entity catalog, approved history
retrieval, and job state surfaces while the integration still does not cross
worker, model, semantic-memory, mutation, token, rendering, or artifact
boundaries.

## Scenarios

### Scenario A - happy path: start job composes catalog, history, and job state

**Given** a config entry with visible approved catalog items and fake Home
Assistant history
**When** the registered `isolinear/v1/job/start` callback handles a prompt
that names approved entities
**Then** the callback should return a schema-valid scaffold-ready
`IntegrationJobSnapshot`
**And** the job store should contain deterministic planning, fetching-history,
and scaffold-ready snapshots
**And** the history store should contain only the selected approved entities

### Scenario B - failure path: non-catalog prompt entities fail before history

**Given** a config entry whose approved catalog does not include a prompt
entity ID
**When** `job/start` handles that prompt
**Then** the returned snapshot should be schema-valid and failed
**And** the failure code should be `entity_not_in_approved_catalog`
**And** Home Assistant history should not be read for that request

### Scenario C - failure path: missing approved history is structured

**Given** a config entry with an approved catalog entity whose fake history is
missing
**When** `job/start` handles a prompt for that approved entity
**Then** the returned snapshot should be schema-valid and failed
**And** the failure code should be `missing_approved_history`
**And** the run summary should include the missing approved entity ID

### Scenario C2 - regression path: unresolved allowlist entities are explicit

**Given** a config entry whose allowlist contains
`sensor.bathrrom_sensor_temperature`
**And** Home Assistant entity metadata and states cannot resolve that entity ID
**When** `job/start` handles a prompt for the bathroom temperature
**Then** the returned snapshot should be schema-valid and failed
**And** the failure code should be `unknown_allowlisted_entity`
**And** the run summary should include the missing allowlist entity ID
**And** Home Assistant history should not be read for that request
**When** the failed job is retried
**Then** the retry snapshot should preserve `unknown_allowlisted_entity`
**And** the retry run summary should include the same missing allowlist entity ID
**And** Home Assistant history should still not be read for that request

### Scenario D - isolation path: config entries stay scoped

**Given** two Isolinear config entries with different approved catalogs and
fake history requests
**When** each entry starts a job
**Then** each entry should receive deterministic job IDs scoped to that entry
**And** each history store and orchestration run summary should contain only
that entry's selected approved entities

### Scenario E - clarification path: ambiguous prompts ask instead of guessing

**Given** a config entry with multiple visible approved catalog entities that
match the same prompt token
**When** `job/start` handles a prompt that does not name a deterministic entity
**Then** the returned snapshot should be schema-valid and
`clarification_needed`
**And** the clarification should offer approved entity options
**And** Home Assistant history should not be read for that request

### Scenario F - setup path: setup stores orchestration state

**Given** an Isolinear config entry with visible approved entities
**When** `async_setup_entry` runs
**Then** the config-entry data should include an orchestration store and setup
result
**And** the setup result should identify whether the scaffold is enabled for
that entry

### Scenario G - boundary path: orchestration scaffold remains bounded

**Given** the orchestration scaffold has handled success and failure cases
**When** the anchor aggregates observed side effects
**Then** no worker, model-provider, semantic-memory persistence,
service/device/state mutation, token-generation, chart artifact write, chart
rendering, durable storage, or real production job orchestration should occur
**And** approved catalog reads, approved fake history reads, job state writes,
history store writes, orchestration bookkeeping, and WebSocket registration
should be reported as the allowed side effects

### Scenario H - schema path: returned snapshots validate before storage

**Given** every orchestration outcome is represented as an
`IntegrationJobSnapshot`
**When** the scaffold stores or returns planning, fetching-history,
scaffold-ready, and failed snapshots
**Then** every snapshot should validate against the schema before it is
observable

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_job_orchestration_scaffold.py` for each scenario.
