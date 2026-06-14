---
status: draft
date: 2026-06-14
depends-on-adrs:
  - 0001
  - 0003
  - 0005
  - 0008
  - 0012
  - 0017
  - 0018
---

# Home Assistant Integration: Worker-Rendered Artifact Serving

## Status

Draft. Defines the real-slice worker/add-on rendering handoff that follows the
production artifact-serving slice.

## Related docs

- [bdd/integration/home-assistant-worker-rendered-artifact-serving-bdd.md](../../bdd/integration/home-assistant-worker-rendered-artifact-serving-bdd.md) - observable behavior
- [docs/specs/home-assistant-first-real-vertical-slice.md](home-assistant-first-real-vertical-slice.md) - source real-slice behavior
- [docs/specs/home-assistant-production-artifact-serving.md](home-assistant-production-artifact-serving.md) - served artifact URL contract
- [docs/specs/home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-spec.md](home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-spec.md) - existing worker dispatch boundary

## Context

The first real vertical slice renders trusted ChartSpecs in-process and serves
the resulting PNG from `/api/isolinear/artifacts`. The older worker dispatch
scaffold validates the ADR-0012 worker transport boundary, but still records
placeholder artifact metadata. The next hardening step is to let the same
real-slice prompt/history/planner path use the configured worker renderer while
preserving the served artifact URL contract.

## Behavior contract

The worker-rendered artifact slice must:

- Run behind the existing `isolinear/v1/job/start` and
  `isolinear/v1/job/snapshot` commands.
- Use the existing ADR-0012 worker transport request and integration-owned
  worker bearer token.
- Build the worker `RenderRequest` only from a schema-valid render plan and
  already-staged approved `HistorySeries` records.
- Accept worker success only when `RenderResult` validates, has
  `status: "success"`, `image_mime_type: "image/png"`, and carries bounded PNG
  bytes in `image_bytes_base64`.
- Reject missing, malformed, non-PNG, or oversized worker image bytes before
  artifact metadata, render-plan, worker-dispatch, complete-snapshot, or file
  state is stored.
- Write accepted worker PNG bytes to the integration-owned artifact directory
  using the existing sanitized artifact ID.
- Store rendered artifact metadata whose `image_url` is
  `/api/isolinear/artifacts/<artifact_id>.png`.
- Store redacted worker dispatch metadata only after the PNG payload and
  artifact metadata validate.
- Return a complete `IntegrationJobSnapshot` with the same served artifact URL.
- Be idempotent: repeated `job/snapshot` calls for a completed worker-rendered
  job reuse the existing snapshot, worker dispatch, artifact metadata, render
  plan, provider plan, and PNG file without another worker call or file write.
- Preserve the worker failure path: failed worker render results still return a
  sanitized failed snapshot and store retry policy metadata without writing an
  artifact.
- Preserve path safety: registered WebSocket responses must not expose local
  integration artifact paths or worker-local image paths.

Allowed side effects are limited to approved metadata/history reads, the
configured planner call, one configured worker render call, the PNG artifact
file write, and in-memory config-entry bookkeeping. The slice must not mutate
Home Assistant state, services, devices, automations, scenes, or configuration;
must not execute generated Python in the integration; must not expose worker
tokens; and must not let worker-returned paths choose integration filesystem
targets.

## Anchor artifact

The anchor artifact is focused pytest coverage that drives one config-entry
prompt through the registered WebSocket command helpers with an injected worker
renderer returning deterministic PNG bytes, then verifies the served artifact
URL and on-disk PNG.

## Implementation order

1. Add this spec and paired BDD/evidence files.
2. Add focused pytest coverage for worker PNG success, idempotence, missing
   worker bytes, worker failure, and registered WebSocket path safety.
3. Evolve `RenderResult` to carry optional bounded worker PNG bytes.
4. Wire worker-success orchestration through existing artifact serving before
   storing artifact/dispatch/complete-snapshot state.
5. Verify focused and adjacent worker/artifact tests.

## Proof requirements

1. Focused pytest proves a configured worker-rendered job returns a complete
   snapshot with `/api/isolinear/artifacts/<artifact_id>.png`.
2. Focused pytest reads the referenced artifact file and verifies PNG
   signature bytes.
3. Focused pytest proves worker transport authorization is redacted while the
   worker received a real bearer header.
4. Focused pytest proves repeated snapshots reuse the same worker dispatch,
   served URL, and PNG file without another worker call.
5. Focused pytest proves missing worker image bytes fail before artifact,
   render-plan, dispatch, complete-snapshot, or file storage.
6. Focused pytest proves failed worker render results still follow the
   existing sanitized worker-failure snapshot path without writing an artifact.
7. Focused pytest proves registered WebSocket responses omit local artifact
   paths and worker image paths.
8. Focused pytest proves oversized worker image bytes fail schema validation
   before image decode or file storage.
9. Focused pytest proves malformed worker progress payloads cannot strand a
   written PNG file or artifact-write metadata.
10. Adjacent worker dispatch and first-real-slice production artifact tests
   remain green.
11. Evidence contains raw pytest output and the worker-rendered evidence payload
   with token/path-safe summaries and PNG signature bytes.

## Non-goals

- Building the worker/add-on package.
- Calling a live Home Assistant instance or live worker.
- Sandboxed codegen or generated Python execution in this packet.
- Durable job/artifact persistence.
- Artifact retention or cleanup policy.
- Changing the card-facing WebSocket command schema.
- Home Assistant mutation of any kind.

## References

- [docs/decisions/0012-worker-transport-and-authentication.md](../decisions/0012-worker-transport-and-authentication.md)
- [docs/decisions/0017-first-real-vertical-slice.md](../decisions/0017-first-real-vertical-slice.md)
- [docs/decisions/0018-production-artifact-serving.md](../decisions/0018-production-artifact-serving.md)
- [docs/schemas/render-result.schema.json](../schemas/render-result.schema.json)
- [docs/schemas/integration-artifact-metadata.schema.json](../schemas/integration-artifact-metadata.schema.json)
- [docs/schemas/integration-worker-dispatch.schema.json](../schemas/integration-worker-dispatch.schema.json)
