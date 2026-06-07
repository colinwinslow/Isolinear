# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-06 (trusted renderer scatter/correlation follow-up)
**Phase:** `Seed phase — Design-heavy MVP planning before production integration`  
**Next bounded packet:** `MVP design closeout/readiness review`
**Current readiness:** `READY-FOR-NEXT-PACKET`

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-06** — `Trusted renderer scatter/correlation follow-up` — Extended the chart-spec rendering spec, BDD, eval outlines, evidence, and Python anchor so safe mode now supports `scatter` charts with exactly two numeric entity-backed series. Scatter rendering requires explicit `x_axis.source_series_id` and `y_axis.source_series_id`, pairs numeric points by exact matching timestamps inside the chart time range, emits deterministic absolute time-range metadata, writes PNG output, and reports zero codegen attempts. Added fail-closed guards for unsupported scatter series counts, mismatched axis source IDs, unsupported sources/history kinds, missing source history, and no paired numeric points before artifact creation. Standalone architecture review timed out; inline architecture review OK; BDD-evidence review OK. Python tests green; full eval sweep green.
- **2026-06-06** — `Trusted renderer event markers + distribution/histogram follow-up` — Extended the chart-spec rendering spec, schema, BDD, eval outlines, evidence, and Python anchor so safe mode now supports `markers` overlays on numeric time-series charts and `histogram` charts with one numeric entity-backed series. Marker overlays derive point-in-time events from validated `HistorySeries` records using `active_values`, threshold crossings, or event-kind points; histograms render deterministic fixed-count value bins from `x_axis.bin_count`. Added fail-closed guards for unsupported marker rules, unsupported histogram bin counts, missing marker/histogram source history, no matching marker events, and no numeric histogram points before artifact creation. Standalone architecture review PASS; BDD-evidence review OK. Python tests green; full eval sweep green.
- **2026-06-06** — `Trusted renderer calendar/hour heatmap follow-up` — Extended the chart-spec rendering spec, schema, BDD, eval outline, evidence, and Python anchor so safe mode now supports `heatmap` charts with one numeric entity-backed series rendered as weekday-by-hour mean cells from `x_axis.group_by: hour` and `y_axis.group_by: weekday`. Added deterministic PNG output, absolute time-range metadata, and zero codegen attempts. Added fail-closed guards for unsupported heatmap grouping, multiple heatmap series, missing source history, and no numeric points before artifact creation. Standalone architecture review via `codex exec` timed out; inline architecture review OK; BDD-evidence review OK. Python tests green after rerun; calendar/hour heatmap, aggregate, timeline, primitive, prompt, and shaded-interval evals green.
- **2026-06-06** — `Trusted renderer aggregate bar chart follow-up` — Aligned the startup protocol so `/startup` reads both `STATUS.md` and `HANDOFF.md`. Extended the chart-spec rendering spec, BDD, eval outline, evidence, and Python anchor so safe mode now supports `bar` charts with aggregate numeric series from `source.type: aggregate`, one bar per source entity, `mean`/`min`/`max`/`sum`/`count` operations, PNG output, deterministic time-range metadata, and zero codegen attempts. Added chart-family-specific source checks so time-series/timeline remain entity-backed while bars require aggregate sources. Added fail-closed guards for missing aggregate source history or aggregate sources with no numeric points before artifact creation. Standalone architecture review OK; BDD-evidence review OK. Python tests green; aggregate, timeline, primitive, prompt, and shaded-interval evals green.
- **2026-06-06** — `Trusted renderer state interval timeline follow-up` — Selected `state_interval_timeline` as the first trusted-renderer follow-up family. Extended the chart-spec rendering spec, BDD, eval outline, evidence, and Python anchor so safe mode now supports `timeline` charts with binary/categorical `step` tracks rendered from matching `DerivedInterval` records, PNG output, absolute time-range metadata, and zero codegen attempts. Added chart-family-specific unsupported checks so `time_series` remains limited to numeric `line` series and `timeline` rejects numeric/line specs. Added a fail-closed guard for mismatched `DerivedInterval.source_entity_id` before artifact creation. Standalone architecture review via `codex exec` timed out; inline architecture review OK; BDD-evidence review OK. Python tests green; timeline and renderer evals green.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Trusted renderer scatter/correlation follow-up`

- [x] Define the scatter/correlation primitive contract in the chart-spec rendering spec
- [x] Extend the paired rendering BDD, evidence, and eval outlines
- [x] Render deterministic paired numeric scatter charts from matching validated `HistorySeries` records in safe mode
- [x] Require explicit scatter x/y axis source series IDs and exact timestamp pairing
- [x] Keep unsupported scatter specs fail-closed with zero codegen attempts
- [x] Guard scatter charts against missing source history or no paired numeric points before artifact creation
- [x] Run Python tests and full eval sweep

## Open queue (non-blocking)

> Things worth doing that don't gate the current packet. Pull from here when the active packet closes.

- (a) MVP design closeout/readiness review before production integration scaffolding
- (b) Post-MVP floorplan heatmap renderer requiring explicit user-provided room
  geometry and area/entity mappings
- (c) Home Assistant custom integration scaffolding once MVP design phase closes

## Blockers

- None.
