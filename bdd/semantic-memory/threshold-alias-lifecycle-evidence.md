# Threshold Alias Lifecycle Evidence

Run timestamp: 2026-06-01 10:29:46 -07:00

BDD file:
`bdd/semantic-memory/threshold-alias-lifecycle-bdd.md`

Overall result: PASS

## Scenario: Do not save memory without confirmation

Raw eval command:

```powershell
C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals/threshold_interval_use_once.py
```

Raw eval output:

```text
CASE threshold_interval_use_once
{
  "case_id": "threshold_interval_use_once",
  "given": {
    "confirmation_value": {
      "entity_id": "sensor.dishwasher_power",
      "operator": ">",
      "type": "threshold_interval",
      "unit": "W",
      "value": 5
    },
    "prompt": "Mark when the dishwasher was running over the last day",
    "time_anchor": "2026-05-29T15:00:00+00:00"
  },
  "then": {
    "chart_id": "temperature_with_threshold_dishwasher_overlay",
    "derived_interval": {
      "interval_id": "dishwasher_running",
      "intervals": [
        {
          "end": "2026-05-29T01:00:00+00:00",
          "reason": "Threshold matched: value > 5 W.",
          "start": "2026-05-28T23:00:00+00:00",
          "state": true
        }
      ],
      "label": "Dishwasher Running",
      "rule": {
        "operator": ">",
        "unit": "W",
        "value": 5
      },
      "source_attribute": null,
      "source_entity_id": "sensor.dishwasher_power",
      "warnings": []
    },
    "overlays_plotted": [
      "dishwasher_running"
    ],
    "planner_status": "chart_spec_ready",
    "render_status": "success",
    "saved_semantic_aliases": [],
    "validation_status": "pass"
  },
  "when": {
    "operation": "invoke_threshold_confirmation_use_once"
  }
}
PASS threshold_interval_use_once
PASS threshold_interval_use_once
```

## Scenario: Save threshold interval alias after clarification

Raw eval command:

```powershell
C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals/threshold_interval_use_and_remember.py
```

Raw eval output:

```text
CASE threshold_interval_use_and_remember
{
  "case_id": "threshold_interval_use_and_remember",
  "given": {
    "alias_name": "dishwasher running",
    "confirmation_value": {
      "entity_id": "sensor.dishwasher_power",
      "operator": ">",
      "type": "threshold_interval",
      "unit": "W",
      "value": 5
    },
    "prompt": "Mark when the dishwasher was running over the last day",
    "time_anchor": "2026-05-29T15:00:00+00:00"
  },
  "then": {
    "overlays_plotted": [
      "dishwasher_running"
    ],
    "planner_status": "chart_spec_ready",
    "render_status": "success",
    "saved_semantic_aliases": [
      {
        "alias_id": "dishwasher_running",
        "created_at": "2026-05-29T15:00:00+00:00",
        "created_from_prompt": "Mark when the dishwasher was running over the last day",
        "enabled": true,
        "last_used_at": "2026-05-29T15:00:00+00:00",
        "meaning": {
          "entity_id": "sensor.dishwasher_power",
          "operator": ">",
          "type": "threshold_interval",
          "unit": "W",
          "value": 5
        },
        "natural_names": [
          "dishwasher running"
        ],
        "source": "user_confirmed"
      }
    ],
    "validation_status": "pass"
  },
  "when": {
    "operation": "invoke_threshold_confirmation_use_and_remember"
  }
}
PASS threshold_interval_use_and_remember
PASS threshold_interval_use_and_remember
```

## Scenario: Reuse saved threshold interval alias

Raw eval command:

```powershell
C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals/threshold_interval_alias_reuse.py
```

Raw eval output:

```text
CASE threshold_interval_alias_reuse
{
  "case_id": "threshold_interval_alias_reuse",
  "given": {
    "prompt": "Mark when the dishwasher was running over the last day",
    "semantic_alias": {
      "alias_id": "dishwasher_running",
      "created_at": "2026-05-29T15:00:00+00:00",
      "created_from_prompt": "Mark when the dishwasher was running over the last day",
      "enabled": true,
      "last_used_at": "2026-05-29T15:00:00+00:00",
      "meaning": {
        "entity_id": "sensor.dishwasher_power",
        "operator": ">",
        "type": "threshold_interval",
        "unit": "W",
        "value": 5
      },
      "natural_names": [
        "dishwasher running"
      ],
      "source": "user_confirmed"
    },
    "time_anchor": "2026-05-29T15:00:00+00:00"
  },
  "then": {
    "chart_id": "temperature_with_threshold_dishwasher_overlay",
    "clarification_question": null,
    "overlays_plotted": [
      "dishwasher_running"
    ],
    "planner_status": "chart_spec_ready",
    "render_status": "success",
    "validation_status": "pass"
  },
  "when": {
    "operation": "invoke_fake_prompt_to_chart"
  }
}
PASS threshold_interval_alias_reuse
PASS threshold_interval_alias_reuse
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
