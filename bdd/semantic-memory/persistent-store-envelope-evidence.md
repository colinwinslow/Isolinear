# Persistent Store Envelope Evidence

Run timestamp: 2026-06-01 12:34:13 -07:00

BDD file:
`bdd/semantic-memory/persistent-store-envelope-bdd.md`

Overall result: PASS

## Scenario: Compute persisted alias invalidity at use time

Raw eval command:

```powershell
C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals/semantic_memory_store_envelope.py
```

Raw eval output:

```text
CASE semantic_memory_store_envelope
{
  "case_id": "semantic_memory_store_envelope",
  "given": {
    "entity_catalog": [
      {
        "area": "Hallway",
        "attributes": {},
        "current_state": 70.9,
        "device_class": "temperature",
        "device_name": "Fake Upstairs Thermometer",
        "domain": "sensor",
        "entity_id": "sensor.upstairs_temperature",
        "friendly_name": "Upstairs Temperature",
        "integration": "fake_provider",
        "labels": [
          "upstairs"
        ],
        "state_class": "measurement",
        "unit_of_measurement": "\u00b0F",
        "visible_to_agent": true
      },
      {
        "area": "Living Room",
        "attributes": {},
        "current_state": 69.3,
        "device_class": "temperature",
        "device_name": "Fake Downstairs Thermometer",
        "domain": "sensor",
        "entity_id": "sensor.downstairs_temperature",
        "friendly_name": "Downstairs Temperature",
        "integration": "fake_provider",
        "labels": [
          "downstairs"
        ],
        "state_class": "measurement",
        "unit_of_measurement": "\u00b0F",
        "visible_to_agent": true
      },
      {
        "area": "Kitchen",
        "attributes": {},
        "current_state": "off",
        "device_class": "running",
        "device_name": "Fake Dishwasher",
        "domain": "binary_sensor",
        "entity_id": "binary_sensor.dishwasher",
        "friendly_name": "Dishwasher",
        "integration": "fake_provider",
        "labels": [
          "dishwasher"
        ],
        "state_class": null,
        "unit_of_measurement": null,
        "visible_to_agent": true
      },
      {
        "area": "Kitchen",
        "attributes": {},
        "current_state": 0.5,
        "device_class": "power",
        "device_name": "Fake Dishwasher",
        "domain": "sensor",
        "entity_id": "sensor.dishwasher_power",
        "friendly_name": "Dishwasher Power",
        "integration": "fake_provider",
        "labels": [
          "dishwasher"
        ],
        "state_class": "measurement",
        "unit_of_measurement": "W",
        "visible_to_agent": true
      }
    ],
    "semantic_memory_store": {
      "aliases": [
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
        },
        {
          "alias_id": "retired_dishwasher_running",
          "created_at": "2026-05-29T15:00:00+00:00",
          "created_from_prompt": "Mark when the dishwasher was running over the last day",
          "enabled": true,
          "last_used_at": "2026-05-29T15:00:00+00:00",
          "meaning": {
            "entity_id": "sensor.retired_dishwasher_power",
            "operator": ">",
            "type": "threshold_interval",
            "unit": "W",
            "value": 5
          },
          "natural_names": [
            "retired dishwasher running"
          ],
          "source": "user_confirmed"
        },
        {
          "alias_id": "disabled_dishwasher_running",
          "created_at": "2026-05-29T15:00:00+00:00",
          "created_from_prompt": "Mark when the dishwasher was running over the last day",
          "enabled": false,
          "last_used_at": "2026-05-29T15:00:00+00:00",
          "meaning": {
            "entity_id": "sensor.retired_dishwasher_power",
            "operator": ">",
            "type": "threshold_interval",
            "unit": "W",
            "value": 5
          },
          "natural_names": [
            "disabled dishwasher running"
          ],
          "source": "user_confirmed"
        }
      ],
      "config_entry_id": "fake-config-entry",
      "created_at": "2026-05-29T15:00:00+00:00",
      "store_version": 1,
      "updated_at": "2026-05-29T15:00:00+00:00"
    }
  },
  "then": {
    "invalid_semantic_aliases": [
      {
        "alias_id": "retired_dishwasher_running",
        "entity_id": "sensor.retired_dishwasher_power",
        "reason": "entity_unavailable"
      }
    ],
    "invalidity_persisted": false,
    "store_unchanged_after_filter": true,
    "valid_alias_ids": [
      "dishwasher_running"
    ]
  },
  "when": {
    "operation": "prepare_semantic_memory_for_planning"
  }
}
PASS semantic_memory_store_envelope
CASE unsupported_store_version_fails_closed
{
  "case_id": "unsupported_store_version_fails_closed",
  "given": {
    "entity_catalog": [
      {
        "area": "Hallway",
        "attributes": {},
        "current_state": 70.9,
        "device_class": "temperature",
        "device_name": "Fake Upstairs Thermometer",
        "domain": "sensor",
        "entity_id": "sensor.upstairs_temperature",
        "friendly_name": "Upstairs Temperature",
        "integration": "fake_provider",
        "labels": [
          "upstairs"
        ],
        "state_class": "measurement",
        "unit_of_measurement": "\u00b0F",
        "visible_to_agent": true
      },
      {
        "area": "Living Room",
        "attributes": {},
        "current_state": 69.3,
        "device_class": "temperature",
        "device_name": "Fake Downstairs Thermometer",
        "domain": "sensor",
        "entity_id": "sensor.downstairs_temperature",
        "friendly_name": "Downstairs Temperature",
        "integration": "fake_provider",
        "labels": [
          "downstairs"
        ],
        "state_class": "measurement",
        "unit_of_measurement": "\u00b0F",
        "visible_to_agent": true
      },
      {
        "area": "Kitchen",
        "attributes": {},
        "current_state": "off",
        "device_class": "running",
        "device_name": "Fake Dishwasher",
        "domain": "binary_sensor",
        "entity_id": "binary_sensor.dishwasher",
        "friendly_name": "Dishwasher",
        "integration": "fake_provider",
        "labels": [
          "dishwasher"
        ],
        "state_class": null,
        "unit_of_measurement": null,
        "visible_to_agent": true
      },
      {
        "area": "Kitchen",
        "attributes": {},
        "current_state": 0.5,
        "device_class": "power",
        "device_name": "Fake Dishwasher",
        "domain": "sensor",
        "entity_id": "sensor.dishwasher_power",
        "friendly_name": "Dishwasher Power",
        "integration": "fake_provider",
        "labels": [
          "dishwasher"
        ],
        "state_class": "measurement",
        "unit_of_measurement": "W",
        "visible_to_agent": true
      }
    ],
    "semantic_memory_store": {
      "aliases": [
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
      "config_entry_id": "fake-config-entry",
      "created_at": "2026-05-29T15:00:00+00:00",
      "store_version": 99,
      "updated_at": "2026-05-29T15:00:00+00:00"
    }
  },
  "then": {
    "invalid_semantic_aliases": [],
    "store_error": {
      "code": "semantic_memory_store_invalid",
      "message": "$.store_version must equal 1."
    },
    "valid_alias_ids": []
  },
  "when": {
    "operation": "prepare_semantic_memory_for_planning"
  }
}
PASS unsupported_store_version_fails_closed
CASE duplicate_alias_ids_fail_closed
{
  "case_id": "duplicate_alias_ids_fail_closed",
  "given": {
    "entity_catalog": [
      {
        "area": "Hallway",
        "attributes": {},
        "current_state": 70.9,
        "device_class": "temperature",
        "device_name": "Fake Upstairs Thermometer",
        "domain": "sensor",
        "entity_id": "sensor.upstairs_temperature",
        "friendly_name": "Upstairs Temperature",
        "integration": "fake_provider",
        "labels": [
          "upstairs"
        ],
        "state_class": "measurement",
        "unit_of_measurement": "\u00b0F",
        "visible_to_agent": true
      },
      {
        "area": "Living Room",
        "attributes": {},
        "current_state": 69.3,
        "device_class": "temperature",
        "device_name": "Fake Downstairs Thermometer",
        "domain": "sensor",
        "entity_id": "sensor.downstairs_temperature",
        "friendly_name": "Downstairs Temperature",
        "integration": "fake_provider",
        "labels": [
          "downstairs"
        ],
        "state_class": "measurement",
        "unit_of_measurement": "\u00b0F",
        "visible_to_agent": true
      },
      {
        "area": "Kitchen",
        "attributes": {},
        "current_state": "off",
        "device_class": "running",
        "device_name": "Fake Dishwasher",
        "domain": "binary_sensor",
        "entity_id": "binary_sensor.dishwasher",
        "friendly_name": "Dishwasher",
        "integration": "fake_provider",
        "labels": [
          "dishwasher"
        ],
        "state_class": null,
        "unit_of_measurement": null,
        "visible_to_agent": true
      },
      {
        "area": "Kitchen",
        "attributes": {},
        "current_state": 0.5,
        "device_class": "power",
        "device_name": "Fake Dishwasher",
        "domain": "sensor",
        "entity_id": "sensor.dishwasher_power",
        "friendly_name": "Dishwasher Power",
        "integration": "fake_provider",
        "labels": [
          "dishwasher"
        ],
        "state_class": "measurement",
        "unit_of_measurement": "W",
        "visible_to_agent": true
      }
    ],
    "semantic_memory_store": {
      "aliases": [
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
        },
        {
          "alias_id": "dishwasher_running",
          "created_at": "2026-05-29T15:00:00+00:00",
          "created_from_prompt": "Mark when the dishwasher was running over the last day",
          "enabled": true,
          "last_used_at": "2026-05-29T15:00:00+00:00",
          "meaning": {
            "entity_id": "sensor.retired_dishwasher_power",
            "operator": ">",
            "type": "threshold_interval",
            "unit": "W",
            "value": 5
          },
          "natural_names": [
            "alternate dishwasher running"
          ],
          "source": "user_confirmed"
        }
      ],
      "config_entry_id": "fake-config-entry",
      "created_at": "2026-05-29T15:00:00+00:00",
      "store_version": 1,
      "updated_at": "2026-05-29T15:00:00+00:00"
    }
  },
  "then": {
    "invalid_semantic_aliases": [],
    "store_error": {
      "code": "semantic_memory_store_invalid",
      "message": "Duplicate semantic alias IDs: dishwasher_running."
    },
    "valid_alias_ids": []
  },
  "when": {
    "operation": "prepare_semantic_memory_for_planning"
  }
}
PASS duplicate_alias_ids_fail_closed
PASS semantic_memory_store_envelope
```

## Scenario: Unsupported store version fails closed

The second raw eval case above is the direct proof for this scenario:

```text
CASE unsupported_store_version_fails_closed
...
"store_error": {
  "code": "semantic_memory_store_invalid",
  "message": "$.store_version must equal 1."
},
"valid_alias_ids": []
...
PASS unsupported_store_version_fails_closed
```

## Scenario: Duplicate alias IDs fail closed

The third raw eval case above is the direct proof for this scenario:

```text
CASE duplicate_alias_ids_fail_closed
...
"aliases": [
  {
    "alias_id": "dishwasher_running",
    ...
  },
  {
    "alias_id": "dishwasher_running",
    ...
  }
],
...
"store_error": {
  "code": "semantic_memory_store_invalid",
  "message": "Duplicate semantic alias IDs: dishwasher_running."
},
"valid_alias_ids": []
...
PASS duplicate_alias_ids_fail_closed
```

## Unit Test Evidence

Targeted unit-test command:

```powershell
C:\Users\c.winslow\AppData\Local\Python\bin\python.exe -m unittest tests.test_fake_vertical_slice.FakeVerticalSliceTests.test_semantic_memory_store_filters_valid_aliases_and_computes_invalidity tests.test_fake_vertical_slice.FakeVerticalSliceTests.test_semantic_memory_store_unsupported_version_fails_closed tests.test_fake_vertical_slice.FakeVerticalSliceTests.test_semantic_memory_store_duplicate_alias_ids_fail_closed
```

Raw unit-test output:

```text
...
----------------------------------------------------------------------
Ran 3 tests in 0.021s

OK
```
