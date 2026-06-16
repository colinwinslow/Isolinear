---
status: draft
date: 2026-06-13
depends-on-adrs:
  - 0001
  - 0003
  - 0005
  - 0008
  - 0011
  - 0012
  - 0017
  - 0018
---

# Home Assistant Integration: Production Artifact Serving

## Status

Draft. Defines the production artifact-serving hardening slice for the first
real vertical slice per ADR-0018.

## Related docs

- [bdd/integration/home-assistant-production-artifact-serving-bdd.md](../../bdd/integration/home-assistant-production-artifact-serving-bdd.md) - observable behavior
- [docs/specs/home-assistant-first-real-vertical-slice.md](home-assistant-first-real-vertical-slice.md) - source real-slice behavior
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The accepted first real vertical slice returns a real PNG chart, but it embeds
the PNG as a base64 data URL in the card-facing WebSocket snapshot. The next
production hardening step is to keep the same prompt-to-chart path while
writing the PNG to integration-owned storage and returning a stable same-origin
artifact URL.

## Behavior contract

The production artifact-serving slice must:

- Register a Home Assistant static path at `/api/isolinear/artifacts` during
  config-entry setup.
- Store rendered chart PNG files in an integration-owned artifact directory.
- Keep artifact filenames derived only from sanitized integration artifact IDs.
- Reject invalid artifact IDs, non-byte payloads, non-PNG payloads, and
  oversized PNG payloads before artifact metadata or complete snapshot storage.
- Continue to validate `PlannerResult`, `ChartSpec`, `RenderRequest`,
  `RenderResult`, `IntegrationArtifactMetadata`, and `IntegrationJobSnapshot`
  before storage or return.
- Return complete snapshots whose `chart.image_url` is
  `/api/isolinear/artifacts/<artifact_id>.png`, not a `data:` URL.
- Do not expose local artifact filesystem paths in the registered WebSocket
  command response.
- Store artifact metadata with `status: "rendered"` and the same served
  `image_url`.
- Record side-effect accounting that a chart artifact file was written only on
  the successful trusted-renderer path.
- If final complete snapshot validation fails after a trusted-renderer PNG is
  written, roll back the PNG file plus related artifact metadata, render-plan,
  and model-provider-plan bookkeeping for that job before returning the
  validation failure.
- Keep idempotence: repeated snapshot requests for a completed job reuse the
  same complete snapshot, artifact metadata, and on-disk PNG path without
  calling the planner or renderer again.
- Preserve the existing hidden-entity failure path: planner output that
  references a non-allowlisted entity fails before rendering, artifact file
  write, artifact metadata storage, or complete snapshot storage.
- Preserve clarification continuation: after a user selects one allowlisted
  entity from a clarification prompt, the next snapshot request must either
  call the configured planner and return a rendered served PNG artifact for
  that selected entity, or fail before artifact metadata storage. It must not
  complete with scaffold placeholder artifact metadata when the real render
  path is active.

Allowed side effects are limited to approved metadata/history reads, the
configured planner call, trusted in-process rendering, writing the PNG artifact
file, registering the static artifact path, in-memory config-entry
bookkeeping, and returning WebSocket snapshots. The slice must not mutate Home
Assistant state, services, devices, automations, scenes, or configuration; must
not execute generated Python; must not call the worker when the in-process
route is active; and must not expose tokens or secrets.

## Anchor artifact

The anchor artifact is a focused pytest that drives one config-entry-scoped
prompt through the existing WebSocket command helpers, using injected
Home-Assistant-shaped metadata/history and an injected Ollama-compatible
planner, and verifies that the returned chart URL points at an on-disk PNG
served from `/api/isolinear/artifacts`.

## Implementation order

1. Add this spec, paired BDD, and draft ADR.
2. Add focused pytest coverage for static artifact path registration, served
   PNG URL behavior, on-disk PNG bytes, idempotent reuse, rollback on failed
   complete snapshot validation, and hidden-entity failure boundaries.
3. Add the integration-owned artifact-serving module.
4. Wire config-entry setup and in-process render orchestration through artifact
   serving.
5. Update dashboard-card smoke expectations and evidence.
6. Verify the real artifact on disk.

## Proof requirements

1. Focused pytest proves setup registers `/api/isolinear/artifacts`.
2. Focused pytest proves a real-slice prompt returns a complete snapshot whose
   `chart.image_url` starts with `/api/isolinear/artifacts/` and ends with
   `.png`.
3. Focused pytest reads the referenced PNG from disk and verifies the PNG
   signature.
4. Focused pytest proves repeated snapshot requests reuse the same URL and do
   not rewrite a second artifact or call the planner again.
5. Focused pytest proves hidden provider entity references fail before artifact
   file write or artifact metadata storage.
6. Focused pytest proves registered WebSocket responses expose the served URL
   but not local artifact filesystem paths.
7. Focused pytest proves failed complete snapshot validation rolls back the
   already-written PNG and related artifact/render/provider job indexes.
8. The mounted dashboard-card smoke proves the card renders the served artifact
   URL as the chart image source.
9. Focused pytest proves clarification answer continuation returns a rendered
   served PNG artifact URL for the selected entity, not scaffold placeholder
   metadata.
10. Focused pytest proves a missing planner on the real render path fails
    before artifact metadata storage instead of creating placeholder success.
11. Evidence contains raw command/result snippets, artifact path/URL, and PNG
   signature bytes.

## Non-goals

- Worker/add-on rendering or worker artifact ingestion.
- Sandboxed codegen or generated Python execution.
- Durable artifact metadata persistence.
- Artifact retention or cleanup policy.
- User-facing artifact browser or download manager.
- Changing the card-facing WebSocket command schema.
- Home Assistant mutation of any kind.

## References

- [docs/decisions/0018-production-artifact-serving.md](../decisions/0018-production-artifact-serving.md)
- [docs/decisions/0017-first-real-vertical-slice.md](../decisions/0017-first-real-vertical-slice.md)
- [docs/specs/home-assistant-first-real-vertical-slice.md](home-assistant-first-real-vertical-slice.md)
- [docs/schemas/integration-artifact-metadata.schema.json](../schemas/integration-artifact-metadata.schema.json)
- [docs/schemas/integration-job-snapshot.schema.json](../schemas/integration-job-snapshot.schema.json)
