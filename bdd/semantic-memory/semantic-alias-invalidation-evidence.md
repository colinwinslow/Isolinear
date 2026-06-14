# Semantic Alias Invalidation Evidence

Run timestamp: 2026-06-01 09:48:59 -07:00

BDD file:
`bdd/semantic-memory/semantic-alias-invalidation-bdd.md`

Overall result: PASS

## Scenario: Invalid threshold alias references unavailable entity

Given:

- Saved alias `dishwasher_running` references `sensor.retired_dishwasher_power`.
- The entity state is `unavailable` because the entity is absent from the current catalog.

When:

- Prompt: `Mark when the dishwasher was running over the last day`

Then:

- Planner status: `clarification_needed`
- Invalid alias reason: `entity_unavailable`
- `render_request`, `render_result`, and `validation_result` are `null`

Raw eval evidence:

```text
CASE unavailable_entity
{
  "case_id": "unavailable_entity",
  "given": {
    "entity_state": "unavailable",
    "semantic_alias": {
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
        "dishwasher running"
      ],
      "source": "user_confirmed"
    }
  },
  "then": {
    "clarification_question_id": "confirm_dishwasher_power_threshold",
    "invalid_semantic_aliases": [
      {
        "alias_id": "dishwasher_running",
        "entity_id": "sensor.retired_dishwasher_power",
        "reason": "entity_unavailable"
      }
    ],
    "planner_status": "clarification_needed",
    "render_request": null,
    "render_result": null,
    "validation_result": null
  },
  "when": {
    "prompt": "Mark when the dishwasher was running over the last day"
  }
}
PASS unavailable_entity
```

## Scenario: Invalid threshold alias references non-allowlisted entity

Given:

- Saved alias `dishwasher_running` references `sensor.dishwasher_power`.
- The entity state is `no longer allowlisted` because the catalog marks the entity as not visible to the agent.

When:

- Prompt: `Mark when the dishwasher was running over the last day`

Then:

- Planner status: `cannot_resolve`
- Invalid alias reason: `entity_not_allowlisted`
- `render_request`, `render_result`, and `validation_result` are `null`

Raw eval evidence:

```text
CASE non_allowlisted_entity
{
  "case_id": "non_allowlisted_entity",
  "given": {
    "entity_state": "no longer allowlisted",
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
    }
  },
  "then": {
    "clarification_question_id": null,
    "invalid_semantic_aliases": [
      {
        "alias_id": "dishwasher_running",
        "entity_id": "sensor.dishwasher_power",
        "reason": "entity_not_allowlisted"
      }
    ],
    "planner_status": "cannot_resolve",
    "render_request": null,
    "render_result": null,
    "validation_result": null
  },
  "when": {
    "prompt": "Mark when the dishwasher was running over the last day"
  }
}
PASS non_allowlisted_entity
PASS semantic_alias_invalidation
```

## Commands

Eval command:

```powershell
C:\Users\c.winslow\AppData\Local\Python\bin\python.exe evals/semantic_alias_invalidation.py
```

Targeted unit-test command:

```powershell
C:\Users\c.winslow\AppData\Local\Python\bin\python.exe -m unittest tests.test_fake_vertical_slice.FakeVerticalSliceTests.test_saved_threshold_alias_referencing_unavailable_entity_is_not_reused tests.test_fake_vertical_slice.FakeVerticalSliceTests.test_saved_threshold_alias_referencing_non_allowlisted_entity_is_not_reused
```

Targeted unit-test output:

```text
..
----------------------------------------------------------------------
Ran 2 tests in 0.033s

OK
```
