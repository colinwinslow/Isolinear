# Trusted Rendering Evidence

Run timestamp: 2026-06-06 21:42:36 -07:00

BDD file:
`bdd/rendering/trusted-rendering-bdd.md`

Overall result: PASS

## Trusted renderer primitive scope

The trusted renderer supports:

- `chart_type: time_series`
- Numeric history series rendered as `line`
- No transform, or `transform.operation: none`
- Entity-backed series sources
- Optional `shaded_intervals` overlays from supplied `DerivedInterval` records
- Optional `markers` overlays derived from supplied validated `HistorySeries`
  records
- `chart_type: timeline`
- Binary or categorical state tracks rendered as `step`
- Timeline tracks rendered from matching supplied `DerivedInterval` records
- `chart_type: bar`
- Aggregate numeric series rendered as `bar`
- Aggregate bar sources using `source.type: aggregate`
- One bar per aggregate source entity
- Aggregate operations: `mean`, `min`, `max`, `sum`, and `count`
- `chart_type: heatmap`
- One numeric entity history series rendered as `heatmap`
- Heatmap `x_axis.group_by: hour` and `y_axis.group_by: weekday`
- Heatmap cells use fixed `mean` aggregation
- `chart_type: histogram`
- One numeric entity history series rendered as `histogram`
- Histogram bins use `x_axis.bin_count`, or deterministic default 8 bins
- PNG output
- No fallback into codegen mode from trusted rendering

## Regression Scenarios

### Scenario: Render a multi-series time chart

Raw eval command:

```powershell
.\.venv\Scripts\python.exe evals/trusted_renderer_primitives.py
```

Raw eval output:

```text
CASE trusted_renderer_primitives
then.line_render_status: success
then.line_series_plotted: ["upstairs_temperature", "downstairs_temperature"]
then.output_files includes: ["trusted-scope-lines.png"]
PASS trusted_renderer_primitives
PASS trusted_renderer_primitives
```

### Scenario: Render shaded intervals

Raw eval command:

```powershell
.\.venv\Scripts\python.exe evals/shaded_interval_rendering.py
```

Raw eval output:

```text
CASE shaded_interval_rendering
then.render_status: success
then.image_mime_type: image/png
then.render_metadata.series_plotted: ["upstairs_temperature"]
then.render_metadata.overlays_plotted: ["dishwasher_running"]
then.render_metadata.codegen_attempts: 0
then.validation_status: pass
PASS shaded_interval_rendering
PASS shaded_interval_rendering
```

### Scenario: Reject unsupported safe-mode primitive without codegen

Raw eval command:

```powershell
.\.venv\Scripts\python.exe evals/trusted_renderer_primitives.py
```

Raw eval output:

```text
CASE trusted_renderer_primitives
then.unsupported_render_status: failed
then.unsupported_error_code: unsupported_chart_spec
then.unsupported_codegen_attempts: 0
then.unsupported_error_details.unsupported_primitives includes:
  {"path": "$.chart_spec.series[0].render_as", "reason": "unsupported_series_render_as", "value": "area"}
PASS trusted_renderer_primitives
PASS trusted_renderer_primitives
```

### Scenario: Render a state interval timeline

Raw eval command:

```powershell
.\.venv\Scripts\python.exe evals/state_interval_timeline.py
```

Raw eval output:

```text
CASE state_interval_timeline
then.render_status: success
then.image_mime_type: image/png
then.series_plotted: ["dishwasher_state"]
then.overlays_plotted: []
then.x_min: 2026-05-28T15:00:00+00:00
then.x_max: 2026-05-29T15:00:00+00:00
then.codegen_attempts: 0
then.validation_status: pass
PASS state_interval_timeline
PASS state_interval_timeline
```

### Scenario: Render an aggregate bar chart

Raw eval command:

```powershell
.\.venv\Scripts\python.exe evals/aggregate_bar_chart.py
```

Raw eval output:

```text
CASE aggregate_bar_chart
then.render_status: success
then.image_mime_type: image/png
then.series_plotted: ["average_temperature_by_room"]
then.overlays_plotted: []
then.x_min: 2026-05-28T15:00:00+00:00
then.x_max: 2026-05-29T15:00:00+00:00
then.codegen_attempts: 0
then.validation_status: pass
PASS aggregate_bar_chart
PASS aggregate_bar_chart
```

### Scenario: Render a calendar hour heatmap

Raw eval command:

```powershell
.\.venv\Scripts\python.exe evals/calendar_hour_heatmap.py
```

Raw eval output:

```text
CASE calendar_hour_heatmap
then.render_status: success
then.image_mime_type: image/png
then.series_plotted: ["dishwasher_power_heatmap"]
then.overlays_plotted: []
then.x_min: 2026-05-28T15:00:00+00:00
then.x_max: 2026-05-29T15:00:00+00:00
then.codegen_attempts: 0
then.validation_status: pass
PASS calendar_hour_heatmap
PASS calendar_hour_heatmap
```

## Current Packet Scenarios

### Scenario: Render event markers over a time-series chart

Selected family: `event_markers`

Raw eval command:

```powershell
.\.venv\Scripts\python.exe evals/event_markers.py
```

Raw eval output:

```text
CASE event_markers
then.render_status: success
then.image_mime_type: image/png
then.series_plotted: ["upstairs_temperature"]
then.overlays_plotted: ["dishwasher_started"]
then.x_min: 2026-05-28T15:00:00+00:00
then.x_max: 2026-05-29T15:00:00+00:00
then.codegen_attempts: 0
then.validation_status: pass
then.output_files: ["event-markers.png"]
PASS event_markers
PASS event_markers
```

Fixture summary:

- `chart_type: time_series`
- Series `upstairs_temperature` references `sensor.upstairs_temperature`
- Overlay `dishwasher_started` references `binary_sensor.dishwasher`
- Overlay `render_as: markers`
- Overlay `active_values: ["on"]`
- Marker source history has a deterministic transition to `on` at
  `2026-05-28T23:00:00+00:00`

### Scenario: Render a distribution histogram

Selected family: `distribution_histogram`

Raw eval command:

```powershell
.\.venv\Scripts\python.exe evals/distribution_histogram.py
```

Raw eval output:

```text
CASE distribution_histogram
then.render_status: success
then.image_mime_type: image/png
then.series_plotted: ["dishwasher_power_distribution"]
then.overlays_plotted: []
then.x_min: 2026-05-28T15:00:00+00:00
then.x_max: 2026-05-29T15:00:00+00:00
then.codegen_attempts: 0
then.validation_status: pass
then.output_files: ["distribution-histogram.png"]
PASS distribution_histogram
PASS distribution_histogram
```

Fixture summary:

- `chart_type: histogram`
- Series `dishwasher_power_distribution` references
  `sensor.dishwasher_power`
- Series `render_as: histogram`
- `x_axis.bin_count: 6`
- Numeric source history has six deterministic points in the requested range

## Regression Eval Evidence

Raw eval commands:

```powershell
.\.venv\Scripts\python.exe evals/trusted_renderer_primitives.py
.\.venv\Scripts\python.exe evals/state_interval_timeline.py
.\.venv\Scripts\python.exe evals/aggregate_bar_chart.py
.\.venv\Scripts\python.exe evals/calendar_hour_heatmap.py
.\.venv\Scripts\python.exe evals/shaded_interval_rendering.py
.\.venv\Scripts\python.exe evals/prompt_to_chart_basic.py
```

Raw eval outputs:

```text
PASS trusted_renderer_primitives
PASS trusted_renderer_primitives
PASS state_interval_timeline
PASS state_interval_timeline
PASS aggregate_bar_chart
PASS aggregate_bar_chart
PASS calendar_hour_heatmap
PASS calendar_hour_heatmap
PASS shaded_interval_rendering
PASS shaded_interval_rendering
PASS prompt_to_chart_basic
PASS prompt_to_chart_basic
```

Full eval sweep also passed:

```text
PASS binary_state_interval_extraction
PASS codegen_sandbox
PASS dashboard_card_anchor
PASS integration_api_transport_auth
PASS missing_overlay_validation
PASS numeric_history_normalization
PASS plan_validation_rejects_hidden_entity
PASS semantic_alias_invalidation
PASS semantic_memory_store_envelope
PASS threshold_interval_alias_reuse
PASS threshold_interval_extraction
PASS threshold_interval_inference
PASS threshold_interval_use_and_remember
PASS threshold_interval_use_once
```

## Unit Test Evidence

Focused unit-test command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_fake_vertical_slice.py
```

Raw focused unit-test output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 34 items

tests\test_fake_vertical_slice.py ..................................     [100%]

============================= 34 passed in 1.16s ==============================
```

Full unit-test command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/
```

Raw full unit-test output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 56 items

tests\test_codegen_sandbox_anchor.py ..........                          [ 17%]
tests\test_dashboard_card_anchor.py .......                              [ 30%]
tests\test_fake_vertical_slice.py ..................................     [ 91%]
tests\test_transport_auth_anchor.py .....                                [100%]

============================= 56 passed in 34.96s =============================
```
