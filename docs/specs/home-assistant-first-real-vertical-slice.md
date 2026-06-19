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
- Resolve the time window with the model, not a keyword parser (ADR-0020): the
  planner request carries `now` and the Home Assistant `time_zone`; the planner
  emits an absolute `chart_spec.time_range {start, end}`; the integration
  validates and clamps it (tz-normalize to UTC, require start < end, clamp
  end <= now, clamp span <= 366 days, floor 60 s). Any failure (no planner, or a
  missing / invalid / unclampable window) falls back to a fixed `now - 24h .. now`
  window. There is no keyword regex.
- Fetch history *after* planning, in the snapshot path, using the resolved
  window — so a window older than recorder retention is not rejected at start.
- Select the data source deterministically by window (ADR-0021): raw recorder
  states for recent/short windows, hourly long-term statistics up to 60 days,
  daily statistics beyond that. Each `HistorySeries` records its `source` and
  `resolution`.
- Fail closed with `no_long_term_statistics` when the window extends beyond
  recorder retention and the entity has no long-term statistics (no
  `state_class`), surfaced as a card-facing failed snapshot.
- Prefer real Home Assistant recorder history and statistics when running in a
  real Home Assistant runtime, while preserving explicit fake injection for
  tests.
- Normalize real or injected history into schema-valid `HistorySeries`
  records before planning/rendering; statistics buckets carry `value` (mean) and
  `value_min` / `value_max`.
- Choose the render family deterministically from each resolved entity's
  `_series_kind` *before* planning (ADR-0022): all-numeric entities use the
  numeric `time_series` / `line` family; all binary/categorical entities use the
  categorical `timeline` / `step` family; exactly one numeric primary + one or
  more binary/categorical entities use the `time_series_overlay` composition
  (numeric line + binary `shaded_intervals` overlay bands). The integration
  selects which per-family Ollama structured-output schema to send, so the model
  never picks `chart_type`. For the overlay composition the planner is disclosed
  only the numeric primary as a series; the integration injects the binary
  overlays deterministically after planning (`_compose_binary_overlays`). A set
  with two or more numeric series mixed with a binary still fails closed with
  `mixed_chart_composition_unsupported` (no deterministic primary). A fuzzy
  prompt matching one numeric + ≥1 binary resolves to the overlay composition
  rather than single-entity clarification.
- Call only the configured Ollama-compatible planner boundary for eligible
  jobs.
- Validate `PlannerResult`, nested `ChartSpec`, and referenced entity IDs
  before render-plan, artifact, or complete-snapshot storage.
- Return card-facing failed job snapshots for planner or provider chart-output
  validation failures instead of surfacing them as generic registered WebSocket
  command rejections.
- Render a safe-mode trusted Pillow PNG in-process when the first-real
  slice is enabled and no worker dispatch is used. Title, axis tick labels, axis
  titles, legend text, and the series line are sized large in source pixels so
  the chart stays legible when the PNG is downscaled to a phone-width card. When
  a series carries `value_min` / `value_max` (statistics buckets), shade a
  min/max band behind the mean line.
- Render `timeline` charts as on/off (binary) or multi-state (categorical) step
  tracks, one lane per series, from raw `binary_state` / `categorical_state`
  `HistorySeries` points (ADR-0022). Each state is held until the next change;
  "on"/active regions are filled. Lane labels, the time axis, and the state
  legend reuse the same large source-pixel sizing as the numeric renderer so the
  track stays legible on a phone-width card. The on-region geometry is produced
  by a shared `_binary_on_regions` primitive reused by the 0.1.26 overlay layer.
  Timelines are a raw-recorder-states family: a timeline window beyond recorder
  retention fails closed (no raw states, no statistics for a non-`state_class`
  entity).
- Render `shaded_intervals` overlays (ADR-0022 D4/D5) on a numeric `time_series`
  chart: each overlay's binary entity is shaded as vertical "on"-region bands
  across the full plot height behind the primary line, using the same
  `_binary_on_regions` primitive as the standalone timeline. Overlays are
  integration-composed (never model-emitted); the renderer accepts only
  `shaded_intervals` overlays with an entity source and rejects any other
  overlay shape with `unsupported_chart_spec`.
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
6a. Focused pytest + eval prove the deterministic window clamp/validate layer
   (ADR-0020): a valid model-supplied absolute window is honored; a future end
   clamps to now; an oversized span clamps to 366 days; inverted, unparseable,
   naive, missing, and relative ranges fall back to a 24-hour window.
6b. Focused pytest + eval prove tiered data-source selection (ADR-0021): recent
   short windows use raw recorder states; multi-day windows use hourly
   statistics; long windows use daily statistics; a beyond-retention window for
   an entity with statistics renders mean + `value_min`/`value_max`, while a
   beyond-retention window for an entity without statistics returns a
   card-facing `no_long_term_statistics` failed snapshot before rendering.
6c. Focused pytest proves renderer legibility: the rendered title paints a tall
   band of ink (large font in source pixels), a high-then-low series is plotted
   across both the upper and lower plot bands rather than collapsing to a flat
   row, and a statistics series paints a tinted min/max band behind the mean
   line.
6d. Focused pytest + eval prove deterministic render-family routing (ADR-0022):
   an all-binary resolved entity set classifies to `timeline` and is sent the
   timeline planner schema; an all-numeric set classifies to `time_series`; a
   mixed numeric + binary set fails closed with
   `mixed_chart_composition_unsupported` before the planner is called.
6e. Focused pytest proves the categorical timeline renderer: a `binary_sensor`
   `timeline` chart with raw on/off history renders a PNG whose decoded
   signature is valid, paints filled "on" regions (ink in the lane) and gaps for
   "off", reuses the shared `_binary_on_regions` primitive, and reports zero
   codegen attempts. A timeline window beyond recorder retention fails closed.
6f. Focused pytest proves failure-code disambiguation (ADR-0022): a provider
   chart spec referencing an entity absent from the approved catalog returns
   `model_provider_referenced_unapproved_entity`; one referencing an approved
   entity not disclosed for this job returns `model_provider_substituted_entity`;
   both still fail before rendering or artifact storage.
6g. Focused pytest + eval prove the numeric + binary overlay composition
   (ADR-0022 D4/D5, 0.1.26): one numeric + one binary entity resolves to the
   `time_series_overlay` family; the planner is disclosed only the numeric
   primary; `_compose_binary_overlays` injects a `shaded_intervals` overlay for
   the binary entity; the rendered PNG paints the AC-on shaded band behind the
   numeric line; a fuzzy "temperature and when the AC was running" prompt
   resolves to the composition; and two numeric + a binary still fails closed
   with `mixed_chart_composition_unsupported`.
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
