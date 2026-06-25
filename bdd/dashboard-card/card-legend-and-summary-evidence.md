# Card-Owned Legend and Model-Authored Summary — Evidence

Evidence for `bdd/dashboard-card/card-legend-and-summary-bdd.md` (ADR-0027).

**Run timestamp:** 2026-06-25
**Suites:** `tests/test_first_real_vertical_slice.py` (Python), `frontend/src/isolinear-card-legend.test.ts` (Vitest)
**Result:** 565 Python tests pass (3 pre-existing matplotlib-sandbox flakes excluded); 21 frontend tests pass.

---

## Scenario A — Renderer emits a legend manifest and draws no in-PNG legend (D1, D2)

`InProcessOverlayRendererTests::test_legend_manifest_climate_overlay_has_per_state_colors PASSED`
`InProcessOverlayRendererTests::test_legend_manifest_lists_series_then_binary_overlay_with_colors PASSED`

Raw manifest from `render_metadata` for the climate-overlay request:

```json
[{"label": "Living Room Temperature", "entity_id": "sensor.living_room_temperature", "color": "#1f77b4", "kind": "series"},
 {"label": "AC running", "entity_id": "climate.kitchen_ecobee", "color": "#b8d4ee", "kind": "overlay",
  "states": [{"label": "cooling", "color": "#b8d4ee"}, {"label": "heating", "color": "#ffcf9e"}]}]
```

`render_metadata` keys: `['codegen_attempts', 'legend', 'overlays_plotted', 'series_plotted', 'summary', 'title', 'warnings', 'x_max', 'x_min']`

Anchor PNG (eyes-on, generated 2026-06-25): clean chart — temperature line, blue
cooling band, orange heating band, title, axes — **no legend swatches or legend
text drawn into the image**. (See session screenshot of `/tmp/adr0027_anchor.png`.)

## Scenario B — Timeline/histogram/bar still draw their in-image legends (D2 scope)

`InProcessOverlayRendererTests::test_timeline_family_emits_no_legend_manifest PASSED`

Raw: `TIMELINE legend key present: False` — the timeline renderer returns no
`legend` in `render_metadata` (keeps its in-image legend, out of ADR-0027 scope).

## Scenario C — Overlay label from the model, with deterministic fallback (D4, C3)

`RenderFamilyRoutingTests::test_compose_state_overlays_applies_model_overlay_label PASSED`

Asserts the three fallback tiers: model label `"AC running"` applied verbatim;
entity-id-shaped model label rejected → friendly name `"Kitchen Ecobee"`; no
friendly name + no model label → derived `"climate.kitchen_ecobee — running state"`.
Overlay `source`/`color_map`/entity unchanged (composition stays integration-owned).

## Scenario D — Summary and legend threaded into the complete snapshot (C2, C4)

`RenderFamilyRoutingTests::test_explicit_mixed_prompt_renders_overlay_png PASSED`
`InProcessOverlayRendererTests::test_chart_spec_summary_flows_into_render_metadata PASSED`
`FirstRealVerticalSliceTests::test_planner_schema_requires_summary_and_permits_overlay_labels PASSED`

The e2e overlay test asserts `snapshot["chart"]["legend"]` contains a `series` row
and an `overlay` row whose `entity_id == "binary_sensor.kitchen_door"` with a `#`
color. The renderer test asserts `chart_spec.summary` reaches
`render_metadata.summary`. The schema test asserts `summary` is required and
`overlay_labels` permitted in the constrained-decoding schema.

## Scenario E — Card caption shows the summary, then the title (C6)

`uses the model summary as the caption, not the prompt ✓`
`falls back to the title when there is no summary ✓`

Caption renders `"Family room temperature with AC running overlaid."` (the summary)
and does not contain the prompt text; with `summary: undefined` it renders
`"Temperature History"` (the title).

## Scenario F — Card legend renders swatches, flip-downs, and the matched alias (C5, C6)

`renders a Legend section with a swatch per row ✓`
`reveals the entity id inside the row disclosure ✓`
`shows a matched alias inside its row's disclosure ✓`

Legend section labelled "Legend"; 2 rows, 1 summary swatch each; the disclosure
exposes `sensor.family_room_temperature`; the alias `air conditioning` appears in
the overlay row (matched by `entity_id`), and not in the unrelated series row.

## Scenario G — Overlay row shows a split swatch and per-state children (C6, D6)

`gives an overlay row a split swatch and per-state children ✓`

The overlay row's swatch style contains `linear-gradient` (split swatch), and the
disclosure lists 2 per-state children with text `cooling` and `heating`.

## Scenario H — Missing legend degrades gracefully (C4, C6)

`renders no Legend section when the legend is absent ✓`

With `legend: undefined`, `.legend` is absent from the DOM and the caption still
renders (no error). Also covered: `never shows a raw entity-id as the primary
label ✓` — `"sensor.attic_temp"` renders as `"attic temp"`.
