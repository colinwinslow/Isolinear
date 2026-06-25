---
status: accepted
date: 2026-06-25
accepted: 2026-06-25
depends-on-adrs: [0027, 0023, 0022, 0019, 0009, 0005]
---

# Card-owned legend, model-authored summary, and overlay labels

## Status

Accepted. Implemented in 0.1.47. Defines the contract surface for ADR-0027. Scope: the `time_series` and
`time_series_overlay` render families only (the `timeline`, `histogram`, and
`aggregate_bar` families keep their in-image legends pending a follow-up packet).

## Related docs

- [docs/decisions/0027-card-owned-legend-and-model-authored-summary.md](../decisions/0027-card-owned-legend-and-model-authored-summary.md) — the decision
- [bdd/dashboard-card/card-legend-and-summary-bdd.md](../../bdd/dashboard-card/card-legend-and-summary-bdd.md) — observable behavior
- [STATUS.md](../../STATUS.md) — current phase and active work

## Context

The complete-view card bakes the legend into the PNG, captions the chart with a
prompt echo, and lists entities as `"<label>: <entity_id>"` with no color and a
weak label source. The renderer assigns colors deterministically but exposes none
of them, so the card cannot be the legend. ADR-0027 moves the legend to the card,
makes the renderer the single source of truth for colors via a manifest, and has
the model author the chart summary and overlay labels. This spec pins the
contracts.

## Behavior contract

### C1 — Legend manifest (renderer → render metadata)

For the `time_series` and `time_series_overlay` families, `render_metadata`
carries a `legend` array. Each entry:

```
{
  "label": "<descriptive label>",          // series label, or overlay label
  "entity_id": "<entity id>",
  "color": "#RRGGBB",                        // series line color, or split-swatch primary
  "kind": "series" | "overlay",
  "states": [                                // overlays only; omitted for series
    { "label": "<state>", "color": "#RRGGBB" }
  ]
}
```

Rules:
- Order matches draw order: series first (in series order), then overlays.
- `color` is the exact color the renderer drew, lower-case hex. For a series it is
  the line color; for a multi-state overlay it is the first state's color (the card
  uses `states` to build the split swatch).
- `states` is present only for `kind: "overlay"`, listing each running state the
  overlay shaded (skip states never drawn — e.g. `idle`/`off`), each with the band
  color. A single-state overlay has a one-element `states`.
- The renderer no longer draws a legend onto the PNG for these two families.

### C2 — Model summary (chart spec)

`chart_spec.summary` (optional string): one sentence describing what the chart
shows, optionally a brief observation. The model is instructed to write it; the
schema permits but does not require it (back-compat). The orchestrator surfaces it
as `snapshot.chart.summary`. When absent/blank, the card falls back to
`snapshot.chart.title`.

### C3 — Overlay labels (planner result → overlay composition)

`planner_result.overlay_labels` (optional object, `additionalProperties: string`),
keyed by entity_id, for the overlay entities disclosed in the request. The model
writes a short human label anchored on the prompt's wording. `_compose_state_overlays`
applies it to the composed overlay's `label`, with fallback order:
1. `overlay_labels[entity_id]` if non-empty and not entity-id-shaped;
2. catalog `friendly_name`;
3. `"<friendly_name> — running state"` derivation when only the entity_id is known.

Overlay structure, source, color_map, and entity remain integration-composed
(ADR-0022 D4/D5). The model supplies only the label string.

### C4 — Snapshot chart fields

`snapshot.chart` gains:
- `summary` (optional string) — from C2.
- `legend` (optional array) — the C1 manifest, threaded through unchanged.

Both are optional for back-compat; older artifacts and out-of-scope families omit
them and the card degrades gracefully (no caption summary, no card legend).

### C5 — Alias display entries gain entity_id

`snapshot.aliases[]` entries gain an optional `entity_id` so the card can match a
matched alias to its legend row and show it inside that row's disclosure, instead
of a separate list.

### C6 — Card presentation

- **Caption**: `chart.summary` if present, else `chart.title`. The prompt echo is
  gone.
- **Legend section** (renamed from "Entities and aliases"): one row per
  `chart.legend` entry — a color swatch + the descriptive label. Each row is a
  disclosure (flip-down) revealing the `entity_id` and any matched alias
  (`aliases[]` whose `entity_id` equals the row's).
- **Overlay rows**: collapsed swatch is a split/multi-color swatch built from
  `states` (half blue / half orange for cooling/heating); the disclosure adds a
  per-state child list, each child a colored square + `"<state>"`. A single-state
  overlay shows a solid swatch and no child list.
- **Label guard**: the card never shows a raw entity-id-shaped string as a primary
  label; if `label` is empty or matches `^\w+\.\w+`, it falls back to the
  entity_id's friendly tail or the entity_id in the disclosure only.
- **Empty state**: when `chart.legend` is absent, the card shows no legend section
  (no crash, no placeholder rows).

## Proof requirements

- **Anchor artifact**: a rendered overlay chart PNG with **no in-image legend**,
  plus the `render_metadata.legend` manifest JSON showing the three temperature
  series with their hex colors and the climate overlay with `states` cooling/heating
  and their colors. (Eyes-on: the PNG is clean; the manifest carries the colors.)
- **Unit (Python)**: manifest shape + colors for time_series and overlay; in-PNG
  legend suppressed for both families but still drawn for timeline/histogram/bar;
  `_compose_state_overlays` applies `overlay_labels` with each fallback tier;
  summary + legend threaded into `snapshot.chart`; alias entries carry entity_id.
- **Unit (frontend, Vitest)**: caption uses summary then title; legend rows render
  swatches; overlay row exposes split swatch + per-state children in the
  disclosure; matched alias appears in the right row; empty-legend degrades.
- **Schema**: every changed schema validates its new fields; existing fixtures
  without the new fields still validate (optional/back-compat).

## Out of scope

- The `timeline`, `histogram`, `aggregate_bar` families' legends (follow-up).
- Dropping the in-PNG chart *title* (ADR-0027 open item; kept for now).
- Home HVAC-config clarification/memory (deferred; ADR-0027 D4 is compatible).
