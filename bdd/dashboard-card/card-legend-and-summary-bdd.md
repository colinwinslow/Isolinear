# Card-Owned Legend and Model-Authored Summary BDD

ADR-0027: the renderer emits a color manifest as the single source of truth for
colors, the card renders an interactive legend from it (in place of the in-PNG
legend), and the model authors the chart summary caption and overlay labels.
Scope: `time_series` and `time_series_overlay` families.

Status: **accepted** — implemented in 0.1.47, 2026-06-25.

Evidence file: `bdd/dashboard-card/card-legend-and-summary-evidence.md`

Related artifacts:

- ADR: `docs/decisions/0027-card-owned-legend-and-model-authored-summary.md`
- Spec: `docs/specs/card-legend-and-summary.md`
- Renderer tests: `tests/test_first_real_vertical_slice.py`
- Orchestration tests: `tests/test_first_real_vertical_slice.py`
- Model-provider tests: `tests/test_first_real_vertical_slice.py`
- Card tests: `frontend/src/isolinear-card.long-running-smoke.test.ts`

## Scenario A: Renderer emits a legend manifest and draws no in-PNG legend (D1, D2)

Given an overlay render request (numeric temperature series + a climate overlay)
When the in-process renderer renders it
Then `render_metadata.legend` lists each series with its line color as lower-case hex
And the climate overlay entry has `kind: "overlay"` and a `states` list of cooling/heating with their band colors
And the rendered PNG contains no legend swatches or legend text

## Scenario B: Timeline/histogram/bar still draw their in-image legends (D2 scope)

Given a timeline render request (binary entities only)
When the renderer renders it
Then the PNG still contains the in-image legend
And `render_metadata.legend` is absent or empty for that family

## Scenario C: Overlay label comes from the model, with deterministic fallback (D4, C3)

Given a planner result whose `overlay_labels` maps the climate entity to "AC running"
When the integration composes the state overlay
Then the composed overlay's label is "AC running"
And when `overlay_labels` is missing or entity-id-shaped, the label falls back to the catalog friendly name
And the overlay source, color_map, and entity remain integration-composed (unchanged)

## Scenario D: Summary and legend are threaded into the complete snapshot (C2, C4)

Given a model that returns a `chart_spec.summary` sentence
When the job completes
Then `snapshot.chart.summary` equals the model's sentence
And `snapshot.chart.legend` carries the renderer manifest
And the complete snapshot re-validates against the job-snapshot schema

## Scenario E: Card caption shows the summary, then the title (C6)

Given a complete snapshot with a `chart.summary`
When the card renders the result view
Then the caption shows the summary
And the prompt is not echoed
And when `chart.summary` is absent, the caption falls back to `chart.title`

## Scenario F: Card legend renders swatches, flip-downs, and the matched alias (C5, C6)

Given a complete snapshot with a `chart.legend` and a matched alias for one entity
When the card renders the Legend section
Then each row shows a color swatch and its descriptive label
And expanding a row reveals its entity_id
And the row whose entity matched an alias shows that alias inside its disclosure

## Scenario G: Overlay row shows a split swatch and per-state children (C6, D6)

Given a complete snapshot whose legend has a two-state climate overlay
When the card renders that overlay row
Then the collapsed swatch is a split swatch built from the two state colors
And expanding the row reveals a per-state child list (cooling, heating), each with its own colored square

## Scenario H: Missing legend degrades gracefully (C4, C6)

Given a complete snapshot with no `chart.legend` (older artifact or out-of-scope family)
When the card renders the result view
Then no Legend section is shown
And the card does not error
