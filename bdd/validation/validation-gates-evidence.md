# Validation Gates Evidence

Run timestamp: 2026-06-01 10:29:46 -07:00

BDD file:
`bdd/validation/validation-gates-bdd.md`

Overall result: PASS

## Scenario: Plan validation rejects non-allowlisted entity

Raw eval command:

```powershell
C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals/plan_validation_rejects_hidden_entity.py
```

Raw eval output:

```text
CASE plan_validation_rejects_hidden_entity
{
  "case_id": "plan_validation_rejects_hidden_entity",
  "given": {
    "chart_spec": {
      "chart_id": "hidden_temperature",
      "chart_type": "time_series",
      "notes": [],
      "overlays": [],
      "series": [
        {
          "label": "Hidden Temperature",
          "render_as": "line",
          "role": "primary",
          "series_id": "hidden_temperature",
          "source": {
            "attribute": null,
            "entity_id": "sensor.hidden_temperature",
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
      "title": "Hidden Temperature",
      "x_axis": {
        "type": "time"
      },
      "y_axis": {
        "label": "\u00b0F"
      }
    },
    "visible_entity_ids": [
      "sensor.upstairs_temperature",
      "sensor.downstairs_temperature",
      "binary_sensor.dishwasher",
      "sensor.dishwasher_power"
    ]
  },
  "then": {
    "allowlist_check": {
      "details": {
        "missing_entity_ids": [
          "sensor.hidden_temperature"
        ]
      },
      "message": "Chart spec references non-allowlisted entities.",
      "name": "allowlisted_entities",
      "status": "fail"
    },
    "artifact_count": 0,
    "render_request": null,
    "render_result": null,
    "validation_status": "fail"
  },
  "when": {
    "operation": "invoke_validated_chart_plan",
    "request_id": "hidden-temperature"
  }
}
PASS plan_validation_rejects_hidden_entity
PASS plan_validation_rejects_hidden_entity
```

## Scenario: Render metadata validation confirms expected series

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

## Scenario: Missing overlay fails validation

Raw eval command:

```powershell
C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals/missing_overlay_validation.py
```

Raw eval output:

```text
CASE missing_overlay_validation
{
  "case_id": "missing_overlay_validation",
  "given": {
    "chart_spec": {
      "chart_id": "temperature_with_dishwasher_overlay",
      "chart_type": "time_series",
      "notes": [],
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
          "transform": null,
          "unit": "\u00b0F"
        }
      ],
      "time_range": {
        "duration": "24h",
        "type": "relative"
      },
      "title": "Temperature With Dishwasher Running",
      "x_axis": {
        "type": "time"
      },
      "y_axis": {
        "label": "\u00b0F"
      }
    },
    "render_metadata": {
      "codegen_attempts": 0,
      "overlays_plotted": [],
      "series_plotted": [
        "upstairs_temperature"
      ],
      "title": "Temperature With Dishwasher Running",
      "warnings": [],
      "x_max": "2026-05-29T15:00:00+00:00",
      "x_min": "2026-05-28T15:00:00+00:00"
    }
  },
  "then": {
    "overlay_check": {
      "details": {
        "missing_overlay_ids": [
          "dishwasher_running"
        ]
      },
      "message": "Render metadata is missing expected overlays.",
      "name": "rendered_overlays",
      "status": "fail"
    },
    "validation_status": "fail"
  },
  "when": {
    "expected_end": "2026-05-29T15:00:00+00:00",
    "expected_start": "2026-05-28T15:00:00+00:00",
    "operation": "validate_chart_job"
  }
}
PASS missing_overlay_validation
PASS missing_overlay_validation
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
