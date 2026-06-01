# Trusted Rendering Evidence

Run timestamp: 2026-06-01 10:29:46 -07:00

BDD file:
`bdd/rendering/trusted-rendering-bdd.md`

Overall result: PASS

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
C:\Users\c.winslow\AppData\Local\Python\bin\python.exe -m unittest tests.test_fake_vertical_slice
```

Raw unit-test output:

```text
....................
----------------------------------------------------------------------
Ran 20 tests in 0.404s

OK
```
