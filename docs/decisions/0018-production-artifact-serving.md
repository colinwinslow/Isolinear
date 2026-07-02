---
id: 0018
title: Production artifact serving
status: accepted
date: 2026-06-13
supersedes: []
superseded-by: null
tags:
  - home-assistant
  - artifacts
  - vertical-slice
---

# ADR-0018: Production artifact serving

## Context

ADR-0017 proved the first real prompt-to-chart spine by returning a trusted
matplotlib PNG as a `data:image/png;base64,...` URL in the WebSocket snapshot.
That kept the reality proof small, but it is not the right production delivery
shape: large binary payloads should not travel repeatedly through the
card-facing WebSocket response, and the dashboard card should receive a stable
same-origin image URL it can render like a normal Home Assistant asset.

The existing artifact scaffold already reserved the URL shape
`/api/isolinear/artifacts/<artifact_id>.png`; the missing decision is where
those PNG bytes live and how they become reachable without exposing secrets or
introducing a new service.

## Decision

**Rendered chart PNGs are stored as integration-owned files and served through
Home Assistant's static HTTP path at `/api/isolinear/artifacts`; WebSocket
snapshots return only the same-origin artifact URL.**

The artifact-serving path is registered during config-entry setup. The first
real in-process renderer writes only schema-validated PNG bytes for the
already-created artifact ID, then stores artifact metadata whose `image_url`
points at the served file.

## Rationale

- Keeps the existing card-facing WebSocket schema stable while removing large
  binary data URLs from normal responses.
- Reuses Home Assistant's HTTP serving surface instead of adding an external
  server, database, queue, or worker requirement.
- Preserves config-entry orchestration and allowlist validation: artifact files
  are written only after `PlannerResult`, `ChartSpec`, `RenderRequest`,
  `RenderResult`, and artifact metadata validation pass.
- Gives manual and automated evidence a real on-disk artifact to inspect.

## Consequences

**Enables:**
- Normal `<img src="/api/isolinear/artifacts/...png">` rendering in the Lit
  dashboard card.
- Direct on-disk PNG signature verification for the first real slice.
- A cleaner future path for durable artifact retention or worker-produced
  artifact ingestion.

**Constrains:**
- Artifact IDs used as filenames must be sanitized and cannot contain path
  separators.
- Artifact writes are limited to PNG bytes produced by the trusted renderer for
  the current config-entry job.
- The static artifact route must not expose Home Assistant tokens, model
  provider endpoints, raw history, generated code, or arbitrary local files.
- The in-process trusted renderer remains the only production writer in this
  packet; worker/add-on artifact ingestion is still a later hardening step.

**Open:**
- Retention and cleanup policy for old chart artifacts.
- Durable job/artifact metadata persistence across Home Assistant restarts.
- Worker/add-on artifact upload or handoff semantics.

## References

- ADR-0001: Home Assistant integration plus isolated worker
- ADR-0003: Entity allowlist, semantic resolution, memory
- ADR-0005: Schema-driven contracts and history normalization
- ADR-0008: Read-only MVP and sandbox security
- ADR-0011: Dashboard card implementation technology
- ADR-0012: Worker transport and authentication
- ADR-0017: First real vertical slice
- [Production artifact serving spec](../specs/home-assistant-production-artifact-serving.md)
