# Render family capability envelope — BDD evidence

**Spec:** `docs/specs/render-family-capability-envelope.md`
**BDD:** `bdd/rendering/render-family-capability-envelope-bdd.md`
**Version:** 0.1.44
**Date:** 2026-06-24

---

## Scenario A — happy path / anchor: "distribution" intent renders a histogram

```
Envelope computed for sensor.upstairs_temp: ["time_series", "histogram", "aggregate_bar"]
Planner chart_type enum (constrained decoding): ["time_series", "histogram", "bar"]
Model chose chart_type: histogram
Renderer: in_process_pillow
Status: success
PNG byte count: 36884
series_plotted: ["temp-dist"]
codegen_attempts: 0
```

Eval CASE `histogram_render` output:
```json
{
  "case_id": "histogram_render",
  "given": {"entity": "sensor.attic_temperature", "kind": "numeric", "n_points": 24},
  "when": {"operation": "render_in_process_chart(chart_type=histogram)"},
  "then": {
    "status": "success",
    "renderer": "in_process_pillow",
    "png_byte_count": 35360,
    "series_plotted": ["temp-dist"],
    "codegen_attempts": 0
  }
}
```

PNG eyes-on note: histogram shows 8 bins, x-axis labelled with temperature values (°C), y-axis labelled "Count", legend visible, bars legible at ~380px phone downscale. ✓

---

## Scenario B — same entity, different intent: "average per day" renders an aggregate bar

```
Envelope: ["time_series", "histogram", "aggregate_bar"]
Model chose chart_type: bar, group_by: day, operation: mean
Renderer: in_process_pillow
Status: success
PNG byte count: 46940
series_plotted: ["temp-avg"]
codegen_attempts: 0
```

Eval CASE `aggregate_bar_render` output:
```json
{
  "case_id": "aggregate_bar_render",
  "given": {"entity": "sensor.attic_temperature", "kind": "numeric", "operation": "mean", "group_by": "day"},
  "when": {"operation": "render_in_process_chart(chart_type=bar)"},
  "then": {
    "status": "success",
    "renderer": "in_process_pillow",
    "png_byte_count": 46336,
    "series_plotted": ["temp-avg"],
    "x_min": null,
    "x_max": null,
    "codegen_attempts": 0
  }
}
```

PNG eyes-on note: 5 bars (one per calendar day 06-14..06-18), x-axis date labels, y-axis temperature (°C), legend visible. Trend is clear and legible at ~380px phone downscale. ✓

---

## Scenario C — back-compat: "over time" still renders a time-series line

Confirmed by existing ADR-0022 tests (512 passing, 0 regressions). The single-numeric envelope has `time_series` as first member (`default_family`); when the model picks `time_series` the renderer dispatches to `_render_time_series_png` identically to the ADR-0022 path.

`validate_model_provider_chart_family` with `chart_type: time_series` in `["time_series", "histogram", "aggregate_bar"]` → `accepted: true`. ✓

---

## Scenario D — single-member envelope: binary still routes to timeline

Eval CASE `capability_envelope_routing`:
```
binary_families: ["timeline"]
```

Schema for `envelope=["timeline"]`: `chart_type enum = ["timeline"]`, `render_as enum = ["step"]` — identical to ADR-0022 single-family schema. Regression test `test_binary_timeline_schema_unchanged` confirms byte-equivalence. ✓

---

## Scenario E — out-of-envelope choice fails closed

Eval CASE `capability_envelope_routing`:
```json
{
  "gate_reject_scatter": true,
  "gate_reject_code": "model_provider_chart_family_out_of_envelope"
}
```

`validate_model_provider_chart_family({"chart_type": "scatter"}, envelope=single_numeric)` returns:
```json
{
  "accepted": false,
  "code": "model_provider_chart_family_out_of_envelope",
  "chosen_family": "scatter",
  "allowed_families": ["time_series", "histogram", "bar"]
}
```

Unit test `test_rejects_unknown_chart_type_in_multi_family` confirms no PNG, no artifact, no render plan stored (the gate fires before render). ✓

---

## Scenario F — fail-soft: sparse histogram renders thin, not an error

Sparse histogram (3 points, 8 bins — most bins count 0):
```
Status: in_process_render_succeeded
PNG byte count: 38854
series_plotted: ["temp-dist"]
```

PNG eyes-on note: 3 non-empty bins with count=1 visible as thin but correctly-sized bars; 5 empty bins remain at zero height; chart is readable. NOT `unsupported_chart_spec`. ✓

Unit test `test_sparse_fails_soft_not_error` confirms `accepted: true` with 3 history points. ✓

---

## Scenario G — fail-closed: no usable data is an honest failure

```python
history = {... "points": []}
result = render_in_process_chart(histogram_request)
# result["accepted"] == False
# result["code"] == "in_process_renderer_failed"
```

Unit tests `test_zero_points_fails_closed` (histogram) and `test_zero_points_fails_closed` (aggregate bar) confirm no empty PNG is produced. ✓

---

## Scenario H — entity enforcement unchanged regardless of family

Multi-family schema still pins `source.entity_id` to an enum of disclosed entity IDs:

```json
{
  "source": {
    "properties": {
      "entity_id": {"enum": ["sensor.upstairs_temp"]}
    }
  }
}
```

Unit test `test_entity_ids_still_pinned_in_multi_family_schema` confirms the enum pin is present. Structural entity gate (`validate_model_provider_output_entities`) is called after `validate_model_provider_chart_family` in the planning flow and remains unchanged (ADR-0022 0.1.27 structural gate). ✓

---

## Capability envelope routing summary

```json
{
  "case_id": "capability_envelope_routing",
  "then": {
    "single_numeric_families": ["time_series", "histogram", "aggregate_bar"],
    "single_numeric_shape": "single_numeric",
    "multi_numeric_families": ["time_series"],
    "binary_families": ["timeline"],
    "overlay_families": ["time_series_overlay"],
    "mixed_families": [],
    "multi_schema_chart_types": ["time_series", "histogram", "bar"],
    "gate_accept_histogram": true,
    "gate_reject_scatter": true,
    "gate_reject_code": "model_provider_chart_family_out_of_envelope"
  }
}
```

---

## Test suite

```
554 passed, 3 pre-existing codegen-sandbox flakes
42 new tests in tests/test_render_family_capability_envelope.py
All prior tests (512) unchanged
```

Eval: `evals/timeline_render_family_routing.py` extended with 3 new CASEs:
- `capability_envelope_routing` PASS
- `histogram_render` PASS
- `aggregate_bar_render` PASS
