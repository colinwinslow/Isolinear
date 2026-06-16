# Home Assistant Integration: Production Artifact Serving - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-production-artifact-serving.md](../../docs/specs/home-assistant-production-artifact-serving.md).

## Why this BDD exists

This BDD pins down the first production chart artifact delivery behavior:
trusted renderer PNG bytes are stored as integration-owned files and the
dashboard card receives a same-origin image URL instead of a WebSocket data URL.

## Scenarios

### Scenario A - setup path: artifact static path is registered

**Given** a configured Isolinear entry
**When** config-entry setup runs
**Then** Home Assistant serves the integration artifact directory from
`/api/isolinear/artifacts`.

### Scenario B - happy path: allowed prompt returns a served PNG artifact URL

**Given** a configured Isolinear entry with one allowlisted numeric entity, an
Ollama-compatible planner, and approved history for that entity
**When** the dashboard card sends `isolinear/v1/job/start` and then
`isolinear/v1/job/snapshot`
**Then** the returned complete snapshot contains
`/api/isolinear/artifacts/<artifact_id>.png`
**And** the referenced file exists on disk with PNG signature bytes.
**And** the registered command response does not expose a local artifact
filesystem path.

### Scenario C - idempotence path: repeated snapshots reuse the served artifact

**Given** a real-slice job has already completed with a served artifact URL
**When** the dashboard card asks for the same job snapshot again
**Then** the integration returns the same complete snapshot and URL
**And** it does not call the planner or renderer again or write a second PNG.

### Scenario D - failure path: hidden provider entity fails before file write

**Given** the same configured entry and history
**When** the planner result references a non-allowlisted entity anywhere in its
output
**Then** the snapshot request fails before rendering, artifact file write,
artifact metadata storage, or complete snapshot storage.

### Scenario E - failure path: complete snapshot validation rolls back artifact state

**Given** a trusted renderer has produced a valid served PNG artifact
**When** final complete snapshot validation fails before the snapshot is stored
**Then** the integration removes the PNG file and the related artifact metadata,
render-plan, and model-provider-plan bookkeeping for that job.

### Scenario F - card path: mounted card renders the served artifact URL

**Given** the dashboard card receives a delayed `planning` snapshot followed by
a `complete` snapshot with a served artifact URL
**When** the card polls `isolinear/v1/job/snapshot`
**Then** the final chart-first view uses the served artifact URL as the image
source.

### Scenario G - clarification path: selected entity renders a served PNG artifact

**Given** a configured Isolinear entry with multiple allowlisted numeric
entities, an Ollama-compatible planner, and approved history for each entity
**When** the dashboard card receives `clarification_needed`, sends
`isolinear/v1/clarification/answer`, and then polls
`isolinear/v1/job/snapshot`
**Then** the returned complete snapshot contains a rendered
`/api/isolinear/artifacts/<artifact_id>.png` URL for the selected entity
**And** the referenced file exists on disk with PNG signature bytes
**And** the snapshot does not report scaffold placeholder artifact success.

## Evidence

The implementing slice produces an evidence file at
`bdd/integration/home-assistant-production-artifact-serving-evidence.md`
containing raw outputs for each scenario.
