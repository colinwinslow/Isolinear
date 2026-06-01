# Basic Prompt-to-Chart Evidence

Run timestamp: 2026-06-01 10:29:46 -07:00

BDD file:
`bdd/prompt-to-chart/basic-prompt-to-chart-bdd.md`

Overall result: PASS

## Scenario: Compare two temperature entities over the last 24 hours

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
