# Chart Spec Rendering Spec

## Purpose

A `ChartSpec` is a structured visualization plan. It tells the renderer what to draw without requiring the model to write arbitrary Python.

## Default rendering path

```text
User prompt
  -> entity resolution
  -> ChartSpec
  -> normalized history and derived intervals
  -> trusted renderer
  -> RenderResult
  -> validation
  -> dashboard card
```

## Trusted renderer responsibilities

The trusted renderer should support chart primitives such as:

- Numeric time-series line.
- Multiple numeric time-series lines.
- Rolling average.
- Min/max/mean annotations.
- Binary/state interval overlays.
- Threshold-derived interval overlays.
- Categorical state bands.
- Event markers.
- Hourly or daily aggregations.

## First trusted renderer release scope

The first trusted renderer release intentionally supports a narrow, inspectable
primitive set:

- `chart_type: time_series`.
- One or more numeric history series rendered as `line`.
- No series transform, or `transform.operation: none`.
- Entity-backed series sources only.
- Optional overlays rendered as `shaded_intervals` from supplied
  `DerivedInterval` records.
- PNG output.

The first release does not support `bar`, `histogram`, `scatter`, `timeline`,
`multi_panel`, `step`, `area`, rolling/resampling transforms, aggregate or alias
sources, marker overlays, band overlays, categorical state bands, event markers,
or SVG output in trusted mode.

Unsupported but schema-valid chart specs must fail closed with
`unsupported_chart_spec` in safe mode. They must not silently fall into codegen
mode; codegen remains an explicitly requested advanced path.

## Trusted renderer roadmap

After the first release, expand trusted rendering with focused slices for these
chart families:

- State interval timeline (selected first follow-up): binary or categorical state over time, such as
  doors, occupancy, appliance cycles, HVAC modes, or automation states.
- Aggregate bar chart: one value per entity, area, device class, or time bucket,
  such as average temperature by room, runtime by appliance, or daily energy by
  source.
- Calendar/hour heatmap: values grouped by hour, day, or weekday for questions
  like when HVAC, energy use, or occupancy most often occurs.
- Event markers: point-in-time annotations over a time-series chart for state
  changes, automation runs, threshold crossings, or user-confirmed events.
- Distribution or histogram: value frequency over a selected period, such as
  how often temperature, humidity, or power draw stayed inside a range.
- Scatter or correlation chart: paired numeric values for relationships such as
  outdoor temperature versus HVAC runtime or solar production versus load.

Each family needs its own BDD/eval slice before implementation. Support should
enter the trusted renderer only when the required `ChartSpec`, normalized data,
render metadata, and validation behavior are deterministic.

## State interval timeline follow-up scope

The first follow-up trusted renderer family is `state_interval_timeline`.

This slice supports:

- `chart_type: timeline`.
- One or more binary or categorical state tracks rendered as `step`.
- Entity-backed series sources only.
- No series transform, or `transform.operation: none`.
- One supplied `DerivedInterval` per rendered track, with
  `DerivedInterval.interval_id` matching the chart `series_id` and
  `DerivedInterval.source_entity_id` matching the chart series source entity.
- Absolute chart time ranges for deterministic `x_min` and `x_max` metadata.
- PNG output.

This slice does not support timeline overlays, aggregate or alias sources,
numeric timelines, marker overlays, SVG output, or codegen fallback. Unsupported
but schema-valid timeline specs must fail closed with `unsupported_chart_spec`
before writing output artifacts. Missing derived intervals fail before writing
output artifacts.

## Floorplan heatmap deferral

Floorplan-style views are useful but intentionally deferred until after the MVP.
Home Assistant provides floors and areas as logical organization, but it does
not natively provide room geometry. A trusted floorplan renderer will therefore
need an explicit user-provided geometry contract, such as:

- A floorplan SVG or image.
- Room or area IDs mapped to SVG paths, rectangles, or polygons.
- Entity mappings for each area metric, such as temperature, occupancy, power,
  or energy.
- Deterministic color scales, legends, missing-data styling, and allowlist
  validation for every referenced entity.

The likely first floorplan slice is `floorplan_heatmap`: one floor, one metric,
one value per mapped area, no Home Assistant mutation, and no codegen fallback.

## ChartSpec requirements

A valid chart spec must identify:

- Chart type.
- Title.
- Time range.
- Series.
- Overlays, if any.
- Axis intent.
- Source references.
- Transformations.

## Safe mode

In safe mode, the worker renders only supported chart primitives. Unsupported requests should produce a clear failure or ask the user to enable codegen mode.

## Auto mode

In auto mode, the system should prefer safe rendering. It may use codegen only when the validated chart spec requires unsupported behavior and the user/configuration permits codegen.

## Codegen mode

In codegen mode, the model writes matplotlib code to implement the validated chart spec. Codegen does not bypass the chart spec contract.
