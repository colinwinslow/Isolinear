# Trusted Rendering Evidence

Run timestamp: 2026-06-06 13:54:49 -07:00

BDD file:
`bdd/rendering/trusted-rendering-bdd.md`

Overall result: PASS

## First trusted renderer primitive scope

The first trusted renderer release supports:

- `chart_type: time_series`
- Numeric history series rendered as `line`
- No transform, or `transform.operation: none`
- Entity-backed series sources
- Optional `shaded_intervals` overlays from supplied `DerivedInterval` records
- PNG output
- No fallback into codegen mode from trusted rendering

## Scenario: Reject unsupported safe-mode primitive without codegen

Raw eval command:

```powershell
C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals/trusted_renderer_primitives.py
```

Raw eval output:

```text
CASE trusted_renderer_primitives
{
  "case_id": "trusted_renderer_primitives",
  "given": {
    "derived_interval": {
      "interval_id": "dishwasher_running",
      "intervals": [
        {
          "end": "2026-05-29T01:00:00+00:00",
          "reason": "Fake dishwasher running interval.",
          "start": "2026-05-28T23:00:00+00:00",
          "state": "on"
        }
      ],
      "label": "Dishwasher Running",
      "rule": {
        "active_values": [
          "on"
        ]
      },
      "source_attribute": null,
      "source_entity_id": "binary_sensor.dishwasher",
      "warnings": []
    },
    "line_chart_spec": {
      "chart_id": "trusted_scope_temperature_lines",
      "chart_type": "time_series",
      "notes": [
        "First trusted renderer release scope fixture."
      ],
      "overlays": [],
      "series": [
        {
          "label": "Upstairs Temperature",
          "render_as": "line",
          "role": "primary",
          "series_id": "upstairs_temperature",
          "source": {
            "attribute": null,
            "entity_id": "sensor.upstairs_temperature",
            "type": "entity"
          },
          "transform": null,
          "unit": "\u00b0F"
        },
        {
          "label": "Downstairs Temperature",
          "render_as": "line",
          "role": "comparison",
          "series_id": "downstairs_temperature",
          "source": {
            "attribute": null,
            "entity_id": "sensor.downstairs_temperature",
            "type": "entity"
          },
          "transform": {
            "operation": "none",
            "window": null
          },
          "unit": "\u00b0F"
        }
      ],
      "time_range": {
        "duration": "24h",
        "type": "relative"
      },
      "title": "Trusted Scope Temperature Lines",
      "x_axis": {
        "type": "time"
      },
      "y_axis": {
        "label": "\u00b0F"
      }
    },
    "overlay_chart_spec": {
      "chart_id": "trusted_scope_temperature_overlay",
      "chart_type": "time_series",
      "notes": [
        "First trusted renderer release scope fixture."
      ],
      "overlays": [
        {
          "active_values": [
            "on"
          ],
          "label": "Dishwasher Running",
          "overlay_id": "dishwasher_running",
          "render_as": "shaded_intervals",
          "source": {
            "attribute": null,
            "entity_id": "binary_sensor.dishwasher",
            "type": "entity"
          }
        }
      ],
      "series": [
        {
          "label": "Upstairs Temperature",
          "render_as": "line",
          "role": "primary",
          "series_id": "upstairs_temperature",
          "source": {
            "attribute": null,
            "entity_id": "sensor.upstairs_temperature",
            "type": "entity"
          },
          "transform": null,
          "unit": "\u00b0F"
        }
      ],
      "time_range": {
        "duration": "24h",
        "type": "relative"
      },
      "title": "Trusted Scope Temperature Overlay",
      "x_axis": {
        "type": "time"
      },
      "y_axis": {
        "label": "\u00b0F"
      }
    },
    "primitive_scope": {
      "chart_types": [
        "time_series"
      ],
      "fallback_to_codegen": false,
      "output_formats": [
        "png"
      ],
      "overlay_render_as": [
        "shaded_intervals"
      ],
      "series_kinds": [
        "numeric"
      ],
      "series_render_as": [
        "line"
      ],
      "series_source_types": [
        "entity"
      ],
      "series_transforms": [
        "none"
      ]
    },
    "unsupported_chart_spec": {
      "chart_id": "trusted_scope_unsupported_area",
      "chart_type": "time_series",
      "notes": [
        "First trusted renderer release scope fixture."
      ],
      "overlays": [],
      "series": [
        {
          "label": "Upstairs Temperature",
          "render_as": "area",
          "role": "primary",
          "series_id": "upstairs_temperature",
          "source": {
            "attribute": null,
            "entity_id": "sensor.upstairs_temperature",
            "type": "entity"
          },
          "transform": null,
          "unit": "\u00b0F"
        },
        {
          "label": "Downstairs Temperature",
          "render_as": "line",
          "role": "comparison",
          "series_id": "downstairs_temperature",
          "source": {
            "attribute": null,
            "entity_id": "sensor.downstairs_temperature",
            "type": "entity"
          },
          "transform": {
            "operation": "none",
            "window": null
          },
          "unit": "\u00b0F"
        }
      ],
      "time_range": {
        "duration": "24h",
        "type": "relative"
      },
      "title": "Trusted Scope Unsupported Area",
      "x_axis": {
        "type": "time"
      },
      "y_axis": {
        "label": "\u00b0F"
      }
    }
  },
  "then": {
    "line_render_status": "success",
    "line_series_plotted": [
      "upstairs_temperature",
      "downstairs_temperature"
    ],
    "output_files": [
      "trusted-scope-lines.png",
      "trusted-scope-overlay.png"
    ],
    "overlay_plotted": [
      "dishwasher_running"
    ],
    "overlay_render_status": "success",
    "unsupported_codegen_attempts": 0,
    "unsupported_error_code": "unsupported_chart_spec",
    "unsupported_error_details": {
      "supported_scope": {
        "chart_types": [
          "time_series"
        ],
        "fallback_to_codegen": false,
        "output_formats": [
          "png"
        ],
        "overlay_render_as": [
          "shaded_intervals"
        ],
        "series_kinds": [
          "numeric"
        ],
        "series_render_as": [
          "line"
        ],
        "series_source_types": [
          "entity"
        ],
        "series_transforms": [
          "none"
        ]
      },
      "unsupported_primitives": [
        {
          "path": "$.chart_spec.series[0].render_as",
          "reason": "unsupported_series_render_as",
          "value": "area"
        }
      ]
    },
    "unsupported_render_status": "failed"
  },
  "when": {
    "operation": "invoke_trusted_renderer_for_first_release_scope",
    "render_mode": "safe"
  }
}
PASS trusted_renderer_primitives
PASS trusted_renderer_primitives
```

## Scenario: Render a multi-series time chart

Raw eval command:

```powershell
C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals/prompt_to_chart_basic.py
```

Raw eval output:

```text
CASE prompt_to_chart_basic
{
  "case_id": "prompt_to_chart_basic",
  "given": {
    "prompt": "Compare upstairs and downstairs temperatures over the last 24 hours",
    "time_anchor": "2026-05-29T15:00:00+00:00"
  },
  "then": {
    "chart_type": "time_series",
    "image_mime_type": "image/png",
    "planner_status": "chart_spec_ready",
    "render_mode": "safe",
    "render_status": "success",
    "series_entity_ids": [
      "sensor.upstairs_temperature",
      "sensor.downstairs_temperature"
    ],
    "series_plotted": [
      "upstairs_temperature",
      "downstairs_temperature"
    ],
    "time_range": {
      "duration": "24h",
      "type": "relative"
    },
    "validation_checks": [
      {
        "name": "chart_spec_shape",
        "status": "pass"
      },
      {
        "name": "allowlisted_entities",
        "status": "pass"
      },
      {
        "name": "render_status",
        "status": "pass"
      },
      {
        "name": "image_artifact",
        "status": "pass"
      },
      {
        "name": "rendered_series",
        "status": "pass"
      },
      {
        "name": "rendered_overlays",
        "status": "pass"
      },
      {
        "name": "rendered_time_range",
        "status": "pass"
      }
    ],
    "validation_status": "pass"
  },
  "when": {
    "operation": "invoke_fake_prompt_to_chart"
  }
}
PASS prompt_to_chart_basic
PASS prompt_to_chart_basic
```

## Scenario: Render shaded intervals

Raw eval command:

```powershell
C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals/shaded_interval_rendering.py
```

Raw eval output:

```text
CASE shaded_interval_rendering
{
  "case_id": "shaded_interval_rendering",
  "given": {
    "chart_spec": {
      "chart_id": "temperature_with_dishwasher_overlay",
      "chart_type": "time_series",
      "overlays": [
        {
          "active_values": [
            "on"
          ],
          "label": "Dishwasher Running",
          "overlay_id": "dishwasher_running",
          "render_as": "shaded_intervals",
          "source": {
            "attribute": null,
            "entity_id": "sensor.upstairs_temperature",
            "type": "entity"
          }
        }
      ],
      "series": [
        {
          "label": "Upstairs Temperature",
          "render_as": "line",
          "role": "primary",
          "series_id": "upstairs_temperature",
          "source": {
            "attribute": null,
            "entity_id": "sensor.upstairs_temperature",
            "type": "entity"
          },
          "unit": "\u00b0F"
        }
      ],
      "time_range": {
        "duration": "24h",
        "type": "relative"
      },
      "title": "Temperature With Dishwasher Running"
    },
    "derived_interval": {
      "interval_id": "dishwasher_running",
      "intervals": [
        {
          "end": "2026-05-29T01:00:00+00:00",
          "reason": "Fake dishwasher running interval.",
          "start": "2026-05-28T23:00:00+00:00",
          "state": "on"
        }
      ],
      "label": "Dishwasher Running",
      "rule": {
        "state": "on"
      },
      "source_attribute": null,
      "source_entity_id": "sensor.upstairs_temperature",
      "warnings": []
    },
    "output": {
      "format": "png",
      "height": 600,
      "width": 1000
    }
  },
  "then": {
    "image_mime_type": "image/png",
    "render_metadata": {
      "codegen_attempts": 0,
      "overlays_plotted": [
        "dishwasher_running"
      ],
      "series_plotted": [
        "upstairs_temperature"
      ],
      "title": "Temperature With Dishwasher Running",
      "warnings": [],
      "x_max": "2026-05-29T15:00:00+00:00",
      "x_min": "2026-05-28T15:00:00+00:00"
    },
    "render_status": "success",
    "validation_checks": [
      {
        "name": "chart_spec_shape",
        "status": "pass"
      },
      {
        "name": "allowlisted_entities",
        "status": "pass"
      },
      {
        "name": "render_status",
        "status": "pass"
      },
      {
        "name": "image_artifact",
        "status": "pass"
      },
      {
        "name": "rendered_series",
        "status": "pass"
      },
      {
        "name": "rendered_overlays",
        "status": "pass"
      },
      {
        "name": "rendered_time_range",
        "status": "pass"
      }
    ],
    "validation_status": "pass"
  },
  "when": {
    "operation": "invoke_trusted_renderer_then_validate_chart_job",
    "request_id": "fake-shaded-overlay"
  }
}
PASS shaded_interval_rendering
PASS shaded_interval_rendering
```

## Unit Test Evidence

Successful unit-test command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/
```

Raw unit-test output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 46 items

tests\test_codegen_sandbox_anchor.py ..........                          [ 21%]
tests\test_dashboard_card_anchor.py .......                              [ 36%]
tests\test_fake_vertical_slice.py ........................               [ 89%]
tests\test_transport_auth_anchor.py .....                                [100%]

============================= 46 passed in 39.03s =============================
```
