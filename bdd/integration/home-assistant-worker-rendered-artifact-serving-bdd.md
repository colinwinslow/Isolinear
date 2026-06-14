# Home Assistant Integration: Worker-Rendered Artifact Serving - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-worker-rendered-artifact-serving.md](../../docs/specs/home-assistant-worker-rendered-artifact-serving.md).

## Why this BDD exists

This BDD pins down the point where the verified real prompt-to-chart path can
cross the worker/add-on rendering boundary and still return the same served
artifact URL that the dashboard card already understands.

## Scenarios

### Scenario A - happy path: worker PNG bytes become a served artifact

**Given** a configured Isolinear entry with one allowlisted numeric entity, an
Ollama-compatible planner, approved history, artifact serving, and a configured
worker renderer
**When** the dashboard card sends `isolinear/v1/job/start` and then
`isolinear/v1/job/snapshot`
**Then** the worker should receive one schema-valid ADR-0012 render request
with redacted evidence
**And** the returned complete snapshot should contain
`/api/isolinear/artifacts/<artifact_id>.png`
**And** the referenced file should exist on disk with PNG signature bytes.

### Scenario B - idempotence path: repeated snapshots reuse worker output

**Given** a worker-rendered real-slice job has already completed
**When** the card asks for the same job snapshot again
**Then** the integration should return the same complete snapshot and URL
**And** it should not call the worker again or write a second PNG.

### Scenario C - failure path: missing worker PNG bytes fail before storage

**Given** the worker returns a schema-valid successful `RenderResult` without
PNG bytes
**When** `job/snapshot` handles that worker response
**Then** the request should fail before artifact metadata, render-plan,
worker-dispatch, complete-snapshot, or file storage.

### Scenario D - failure path: worker render failure does not write an artifact

**Given** the worker returns a failed render result
**When** `job/snapshot` handles that worker response
**Then** the integration should return a sanitized failed snapshot
**And** no PNG artifact file should be written.

### Scenario E - security path: WebSocket responses expose no local paths

**Given** a worker-rendered job completed with a served artifact URL
**When** the registered WebSocket command response is inspected
**Then** it should not contain the integration artifact filesystem path
**And** it should not contain the worker-local `image_path`.

### Scenario F - failure path: oversized worker image bytes fail before decode

**Given** the worker returns a successful `RenderResult` whose
`image_bytes_base64` exceeds the schema bound
**When** `job/snapshot` handles that worker response
**Then** the request should fail schema validation before image decode
**And** no artifact, render plan, worker dispatch, or PNG file should be stored.

### Scenario G - rollback path: invalid progress cannot strand a PNG file

**Given** the worker returns valid PNG bytes but malformed progress payloads
**When** `job/snapshot` rejects the worker progress payload
**Then** any just-written PNG artifact should be removed
**And** artifact write metadata should be cleared.

## Evidence

The implementing slice produces evidence at
`bdd/integration/home-assistant-worker-rendered-artifact-serving-evidence.md`.
