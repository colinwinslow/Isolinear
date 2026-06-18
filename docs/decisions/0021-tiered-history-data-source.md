---
id: 0021
title: Tiered history data source (recorder states + long-term statistics)
status: accepted
date: 2026-06-18
supersedes: []
superseded-by: null
tags:
  - home-assistant
  - recorder
  - statistics
  - history
  - vertical-slice
---

# ADR-0021: Tiered history data source

## Context

The trusted history path fetches only raw recorder states via
`get_significant_states`, which purge at `purge_keep_days` (~10 by default).
ADR-0020 lets the model resolve windows up to 366 days. Raw recorder data cannot
serve windows older than retention, so seasonal queries ("since the spring
equinox" ≈ 90 days) would return empty.

Home Assistant retains **long-term statistics** (hourly/daily mean/min/max)
roughly indefinitely for entities that declare a `state_class`
(`measurement` / `total` / `total_increasing`). They are queryable through
`homeassistant.components.recorder.statistics.statistics_during_period`, a
read-only call. Like the existing raw `get_significant_states` read, it is
invoked synchronously from the history-retrieval path, which the WebSocket
boundary already dispatches off the event loop through
`hass.async_add_executor_job`, so it never blocks the loop.

## Decision

1. **Add a long-term-statistics source** alongside raw recorder states, queried
   read-only via `statistics_during_period` with `types={mean, min, max}`. For
   sensors the `statistic_id` is the entity_id. The call runs in the same
   off-event-loop executor context as the existing raw recorder read (the
   WebSocket boundary's `hass.async_add_executor_job` dispatch).

2. **Deterministic, single-source-per-window tier selection** (a pure function
   of the resolved window, the recorder retention horizon, and entity
   capability):
   - **raw recorder states** — the window is fully within retention
     (`start >= now − keep_days`) and its span is short (≤ 2 days);
   - **hourly statistics** — span ≤ 60 days, or any part of the window is older
     than retention;
   - **daily statistics** — span > 60 days (keeps point counts bounded: a
     1-year window is ~365 daily buckets, not ~8,760 hourly).
   One source covers the whole window; raw and statistics are never stitched
   within a single series.

3. **Statistics buckets normalize to `HistorySeries` points**: `value` carries
   the bucket mean, `value_min` / `value_max` carry the bucket min / max. Each
   series records `source` (`recorder_states` | `long_term_statistics`) and
   `resolution` (`raw` | `hourly` | `daily`).

4. **Fail closed for entities without statistics.** If the resolved window
   extends beyond recorder retention and the entity has no long-term statistics
   (no `state_class`), retrieval returns a structured
   `no_long_term_statistics` failure (entity id named), surfaced as a
   card-facing failed snapshot. The integration never silently shortens the
   window or fabricates data.

5. **Renderer represents statistics** by plotting the mean as the series line
   and shading a min/max band between the per-bucket min and max
   (`value_min` / `value_max`) behind it.

The recorder retention horizon is read best-effort from
`get_instance(hass).keep_days`, defaulting to 10 days when unavailable.

## Consequences

- Seasonal and historical windows work; provenance (`source`, `resolution`) is
  explicit on every series for transparency and eval.
- Point counts stay bounded by adaptive resolution.
- Mixed-fidelity charts are avoided by single-source-per-window selection.
- A new deterministic failure path (`no_long_term_statistics`) exists for
  non-statistics entities over long windows.
- Statistics access stays read-only and off the event loop through the recorder
  executor, consistent with the existing recorder-history read.

## New invariant

> **Data-source provenance** — every `HistorySeries` records its `source` and
> `resolution`. History beyond recorder retention is served only from long-term
> statistics; entities without a `state_class` cannot be charted beyond
> retention and fail closed with `no_long_term_statistics`. Statistics access is
> read-only and runs off the event loop. (ADR-0021)

## Alternatives considered

- *Stitch raw + statistics within one window* — rejected: mixed resolution,
  more complex, marginal benefit.
- *Always use statistics* — rejected: loses real state-change fidelity for
  recent/short charts.
- *Auto-clamp non-statistics entities to retention and render what exists* —
  rejected in favor of an explicit `no_long_term_statistics` failure so the card
  never shows a silently-shortened window.

## Follow-ups

- Per-entity statistics-capability probe caching.
- Live HACS retest of a ~90-day query against a `state_class` sensor.
