---
status: accepted
date: 2026-06-13
depends-on-adrs:
  - 0001
  - 0003
  - 0004
  - 0005
  - 0007
  - 0008
  - 0011
  - 0012
  - 0017
---

# Home Assistant Integration: First Real Vertical Slice

## Status

Accepted. Defines the first real prompt-to-chart spine per ADR-0017 and is
backed by focused pytest evidence plus manual Home Assistant/Ollama verification
captured in the paired evidence file.

## Related docs

- [bdd/integration/home-assistant-first-real-vertical-slice-bdd.md](../../bdd/integration/home-assistant-first-real-vertical-slice-bdd.md) - observable behavior
- [docs/reality-pivot-review.md](../reality-pivot-review.md) - pivot rationale
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The current integration can validate card commands, build config-entry-scoped
jobs, store approved catalog/history scaffolds, call an Ollama-compatible
planner client, and create placeholder chart artifact metadata. The first real
vertical slice must make the smallest end-to-end user-visible chart path real:
approved Home Assistant metadata, approved Home Assistant history, a
provider-produced `ChartSpec`, and a trusted PNG returned to the
existing dashboard card. The in-process renderer draws with Pillow (shipped by
Home Assistant core); matplotlib is not used because it cannot be installed
through the integration manifest in a stock Home Assistant Python environment
(ADR-0019).

## Behavior contract

The first real vertical slice must:

- Run behind the existing `isolinear/v1/job/start` and
  `isolinear/v1/job/snapshot` WebSocket commands.
- Keep registered Home Assistant WebSocket handlers async-safe by using Home
  Assistant's async-response scheduling pattern and running the blocking
  orchestration path in Home Assistant's executor.
- Build catalog items only for configured allowlisted entities.
- Prefer real Home Assistant registry/state metadata when running in a real
  Home Assistant runtime, while preserving explicit fake metadata injection for
  tests.
- Retrieve history only for entities already visible in the approved catalog.
- Prefer real Home Assistant recorder history when running in a real Home
  Assistant runtime, while preserving explicit fake history injection for
  tests.
- Normalize real or injected history into schema-valid `HistorySeries`
  records before planning/rendering.
- Call only the configured Ollama-compatible planner boundary for eligible
  jobs.
- Validate `PlannerResult`, nested `ChartSpec`, and referenced entity IDs
  before render-plan, artifact, or complete-snapshot storage.
- Return card-facing failed job snapshots for planner or provider chart-output
  validation failures instead of surfacing them as generic registered WebSocket
  command rejections.
- Render a safe-mode trusted Pillow PNG in-process when the first-real
  slice is enabled and no worker dispatch is used.
- Return card-facing failed job snapshots for trusted in-process renderer
  failures instead of surfacing them as snapshot-poll command rejections.
- Return that PNG to the existing dashboard card as `chart.image_url`, using a
  `data:image/png;base64,...` URL for this first proof.
- Validate artifact metadata and the final `IntegrationJobSnapshot` before
  storage/return.
- Be idempotent: repeated snapshot requests for a completed real-slice job must
  reuse the existing planner result, render plan, artifact, and complete
  snapshot.

Allowed side effects are limited to reading approved metadata/history, calling
the configured planner, in-process trusted chart rendering, in-memory
config-entry bookkeeping, and returning WebSocket snapshots. The slice must not
mutate Home Assistant state, services, devices, automations, scenes, or
configuration; must not execute generated Python; must not call the worker when
the in-process route is active; and must not expose tokens or secrets.

## Anchor artifact

The anchor artifact is a focused pytest that drives one config-entry-scoped
prompt through the existing WebSocket command helpers, using injected
Home-Assistant-shaped metadata/history and an injected Ollama-compatible
planner, and verifies that the returned chart image is a real PNG data URL.

## Implementation order used

1. Record ADR-0017 and this paired BDD/spec.
2. Add a narrow in-process trusted Pillow renderer for numeric
   `time_series` line charts (originally matplotlib; replaced per ADR-0019).
3. Teach catalog/history retrieval to prefer real Home Assistant adapters when
   available while preserving test injection.
4. Wire an explicit first-real-slice route into `job/snapshot` when no worker
   dispatch is used.
5. Add focused pytest coverage and raw BDD evidence.
6. Run focused tests plus adjacent integration regressions.

## Proof requirements

1. Focused pytest proves a prompt returns a complete snapshot whose
   `chart.image_url` decodes to a PNG signature.
2. Focused pytest proves the real-slice path stores a provider plan, render
   plan, rendered artifact metadata, and no worker dispatch.
3. Focused pytest proves hidden provider entity references still fail before
   rendering or artifact storage.
4. Focused pytest proves invalid provider chart output returns a failed
   snapshot with model-provider failure details and still writes no PNG file.
5. Focused pytest proves trusted in-process renderer failures return
   card-facing failed snapshots with `failure.stage: chart_rendering` and still
   write no PNG file or artifact metadata.
6. Focused pytest proves repeated snapshot requests reuse the completed
   artifact without another planner call.
7. Evidence file contains raw command/result snippets and decoded PNG
   signature bytes.
8. Adjacent orchestration tests remain green.
9. Manual evidence proves the same registered Home Assistant WebSocket handler
   path can use real Home Assistant recorder history and a real
   Ollama-compatible planner without blocking the event loop.

All proof requirements are met by
[bdd/integration/home-assistant-first-real-vertical-slice-evidence.md](../../bdd/integration/home-assistant-first-real-vertical-slice-evidence.md).

## Non-goals

- Worker/add-on rendering.
- Sandboxed codegen or generated Python execution.
- Durable job/artifact persistence.
- Production artifact-serving HTTP endpoint.
- Automatic retries, worker polling, worker progress streaming, or token UI.
- Semantic-memory persistence changes.
- Home Assistant mutation of any kind.

## References

- [docs/decisions/0017-first-real-vertical-slice.md](../decisions/0017-first-real-vertical-slice.md)
- [docs/specs/chart-spec-rendering-spec.md](chart-spec-rendering-spec.md)
- [docs/specs/home-assistant-approved-entity-catalog-scaffold-spec.md](home-assistant-approved-entity-catalog-scaffold-spec.md)
- [docs/specs/home-assistant-approved-history-retrieval-scaffold-spec.md](home-assistant-approved-history-retrieval-scaffold-spec.md)
- [docs/specs/home-assistant-job-orchestration-model-provider-planning-scaffold-spec.md](home-assistant-job-orchestration-model-provider-planning-scaffold-spec.md)
- [docs/schemas/chart-spec.schema.json](../schemas/chart-spec.schema.json)
- [docs/schemas/history-series.schema.json](../schemas/history-series.schema.json)
- [docs/schemas/integration-artifact-metadata.schema.json](../schemas/integration-artifact-metadata.schema.json)
