# History Normalization Evidence

Run timestamp: 2026-06-01 10:29:46 -07:00

BDD file:
`bdd/history-normalization/history-normalization-bdd.md`

Overall result: PASS

## Scenario: Numeric history converts string states and missing states

Raw eval command:

```powershell
C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals/numeric_history_normalization.py
```

Raw eval output:

```text
CASE numeric_history_normalization
{
  "case_id": "numeric_history_normalization",
  "given": {
    "raw_records": [
      {
        "attributes": {
          "unit_of_measurement": "\u00b0F"
        },
        "entity_id": "sensor.upstairs_temperature",
        "last_changed": "2026-05-28T15:00:00+00:00",
        "state": "70.8"
      },
      {
        "attributes": {
          "unit_of_measurement": "\u00b0F"
        },
        "entity_id": "sensor.upstairs_temperature",
        "last_changed": "2026-05-28T21:00:00+00:00",
        "state": "71.2"
      },
      {
        "attributes": {
          "unit_of_measurement": "\u00b0F"
        },
        "entity_id": "sensor.upstairs_temperature",
        "last_changed": "2026-05-29T03:00:00+00:00",
        "state": "unknown"
      },
      {
        "attributes": {
          "unit_of_measurement": "\u00b0F"
        },
        "entity_id": "sensor.upstairs_temperature",
        "last_changed": "2026-05-29T09:00:00+00:00",
        "state": "unavailable"
      },
      {
        "attributes": {
          "unit_of_measurement": "\u00b0F"
        },
        "entity_id": "sensor.upstairs_temperature",
        "last_changed": "2026-05-29T15:00:00+00:00",
        "state": "70.9"
      }
    ]
  },
  "then": {
    "entity_id": "sensor.upstairs_temperature",
    "qualities": [
      "ok",
      "ok",
      "unknown",
      "unavailable",
      "ok"
    ],
    "raw_states": [
      "70.8",
      "71.2",
      "unknown",
      "unavailable",
      "70.9"
    ],
    "series_id": "upstairs_temperature",
    "unit": "\u00b0F",
    "values": [
      70.8,
      71.2,
      null,
      null,
      70.9
    ],
    "warnings": [
      "State 'unknown' for sensor.upstairs_temperature normalized to missing value.",
      "State 'unavailable' for sensor.upstairs_temperature normalized to missing value."
    ]
  },
  "when": {
    "entity_id": "sensor.upstairs_temperature",
    "operation": "normalize_numeric_history_records",
    "series_id": "upstairs_temperature"
  }
}
PASS numeric_history_normalization
PASS numeric_history_normalization
```

## Scenario: Binary state history becomes active intervals

Raw eval command:

```powershell
C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals/binary_state_interval_extraction.py
```

Raw eval output:

```text
CASE binary_state_interval_extraction
{
  "case_id": "binary_state_interval_extraction",
  "given": {
    "active_values": [
      "on"
    ],
    "history_series": {
      "entity_id": "binary_sensor.dishwasher",
      "kind": "binary_state",
      "label": "Dishwasher",
      "points": [
        {
          "quality": "ok",
          "raw_state": "off",
          "ts": "2026-05-28T15:00:00+00:00",
          "value": "off"
        },
        {
          "quality": "ok",
          "raw_state": "on",
          "ts": "2026-05-28T23:00:00+00:00",
          "value": "on"
        },
        {
          "quality": "ok",
          "raw_state": "off",
          "ts": "2026-05-29T01:00:00+00:00",
          "value": "off"
        }
      ],
      "series_id": "dishwasher_state",
      "source_entity_ids": [
        "binary_sensor.dishwasher"
      ],
      "unit": null,
      "warnings": []
    }
  },
  "then": {
    "derived_interval": {
      "interval_id": "dishwasher_running",
      "intervals": [
        {
          "end": "2026-05-29T01:00:00+00:00",
          "reason": "State was on.",
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
    "overlays_plotted": [
      "dishwasher_running"
    ],
    "render_status": "success",
    "validation_status": "pass"
  },
  "when": {
    "operation": "extract_state_intervals_then_render",
    "range_end": "2026-05-29T15:00:00+00:00"
  }
}
PASS binary_state_interval_extraction
PASS binary_state_interval_extraction
```

## Scenario: Continuous sensor becomes threshold intervals after confirmation

Raw eval command:

```powershell
C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals/threshold_interval_extraction.py
```

Raw eval output:

```text
CASE threshold_interval_extraction
{
  "case_id": "threshold_interval_extraction",
  "given": {
    "history_series": {
      "entity_id": "sensor.dishwasher_power",
      "kind": "numeric",
      "label": "Dishwasher Power",
      "points": [
        {
          "quality": "ok",
          "raw_state": "0.4",
          "ts": "2026-05-28T15:00:00+00:00",
          "value": 0.4
        },
        {
          "quality": "ok",
          "raw_state": "0.6",
          "ts": "2026-05-28T21:00:00+00:00",
          "value": 0.6
        },
        {
          "quality": "ok",
          "raw_state": "9.8",
          "ts": "2026-05-28T23:00:00+00:00",
          "value": 9.8
        },
        {
          "quality": "ok",
          "raw_state": "42.0",
          "ts": "2026-05-29T00:00:00+00:00",
          "value": 42.0
        },
        {
          "quality": "ok",
          "raw_state": "3.2",
          "ts": "2026-05-29T01:00:00+00:00",
          "value": 3.2
        },
        {
          "quality": "ok",
          "raw_state": "0.5",
          "ts": "2026-05-29T15:00:00+00:00",
          "value": 0.5
        }
      ],
      "series_id": "dishwasher_power",
      "source_entity_ids": [
        "sensor.dishwasher_power"
      ],
      "unit": "W",
      "warnings": []
    },
    "threshold": {
      "operator": ">",
      "unit": "W",
      "value": 5
    }
  },
  "then": {
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
    "render_status": "success",
    "validation_status": "pass"
  },
  "when": {
    "operation": "extract_threshold_intervals_then_render",
    "range_end": "2026-05-29T15:00:00+00:00"
  }
}
PASS threshold_interval_extraction
PASS threshold_interval_extraction
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
