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
