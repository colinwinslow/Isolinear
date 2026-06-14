# Home Assistant Approved History Retrieval Scaffold Evidence

Run timestamp: 2026-06-08T15:22:42+00:00

BDD file:
`bdd/integration/home-assistant-approved-history-retrieval-scaffold-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: approved entities produce schema-valid history -> `CASE approved_entities_retrieve_schema_valid_history`
- Scenario B: setup stores a config-entry-scoped history store -> `CASE setup_entry_stores_config_entry_scoped_history_store`
- Scenario C: config entries receive separate history -> `CASE config_entries_receive_isolated_history`
- Scenario D: non-catalog entities fail closed -> `CASE non_catalog_entities_fail_closed_before_history_read`
- Scenario E: rejected retrieval clears existing history -> `CASE rejected_retrieval_clears_existing_history`
- Scenario F: malformed raw history fails closed -> `CASE malformed_raw_history_fails_closed`
- Scenario G: malformed history series are rejected before storage -> `CASE malformed_history_series_rejected_before_storage`
- Scenario H: history retrieval remains non-orchestrating -> `CASE history_retrieval_remains_non_orchestrating`

## Verification

## Focused Unit Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_approved_history_retrieval_scaffold_anchor.py
```

Raw output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 9 items

tests\test_approved_history_retrieval_scaffold_anchor.py .........       [100%]

============================== 9 passed in 0.39s ==============================
```

## Full Unit Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\
```

Raw output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 110 items

tests\test_approved_entity_catalog_scaffold_anchor.py .........          [  8%]
tests\test_approved_history_retrieval_scaffold_anchor.py .........       [ 16%]
tests\test_codegen_sandbox_anchor.py ..........                          [ 25%]
tests\test_config_flow_options_anchor.py .....                           [ 30%]
tests\test_dashboard_card_anchor.py .......                              [ 36%]
tests\test_dashboard_resource_registration_anchor.py .......             [ 42%]
tests\test_fake_vertical_slice.py .....................................  [ 76%]
tests\test_integration_scaffold_anchor.py .....                          [ 80%]
tests\test_job_state_scaffold_anchor.py .........                        [ 89%]
tests\test_transport_auth_anchor.py .....                                [ 93%]
tests\test_websocket_command_registration_anchor.py .......              [100%]

============================ 110 passed in 38.66s =============================
```

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_approved_history_retrieval_scaffold.py
```

Raw output summary:

```text
CASE approved_entities_retrieve_schema_valid_history
PASS approved_entities_retrieve_schema_valid_history
CASE setup_entry_stores_config_entry_scoped_history_store
PASS setup_entry_stores_config_entry_scoped_history_store
CASE config_entries_receive_isolated_history
PASS config_entries_receive_isolated_history
CASE non_catalog_entities_fail_closed_before_history_read
PASS non_catalog_entities_fail_closed_before_history_read
CASE rejected_retrieval_clears_existing_history
PASS rejected_retrieval_clears_existing_history
CASE malformed_raw_history_fails_closed
PASS malformed_raw_history_fails_closed
CASE malformed_history_series_rejected_before_storage
PASS malformed_history_series_rejected_before_storage
CASE history_retrieval_remains_non_orchestrating
PASS history_retrieval_remains_non_orchestrating
PASS home_assistant_approved_history_retrieval_scaffold
```

## Scenario Evidence Excerpts

These excerpts are copied from the `CASE` payloads emitted by the eval run.

### Scenario A

```text
case_id: approved_entities_retrieve_schema_valid_history
given.schema: docs/schemas/history-series.schema.json
given.history_source_entity_ids:
- binary_sensor.office_window
- light.kitchen
- sensor.downstairs_temperature
- sensor.upstairs_temperature
when.operation: retrieve_approved_history
then.retrieval.result.accepted: true
then.retrieval.returned_entity_ids:
- sensor.upstairs_temperature
- binary_sensor.office_window
then.retrieval.series_validation[0].accepted: true
then.retrieval.series_validation[0].kind: numeric
then.retrieval.series_validation[1].accepted: true
then.retrieval.series_validation[1].kind: binary_state
then.retrieval.store.entity_ids:
- sensor.upstairs_temperature
- binary_sensor.office_window
then.retrieval.store.point_counts:
- 4
- 3
```

### Scenario B

```text
case_id: setup_entry_stores_config_entry_scoped_history_store
given.entry_id: setup-history-entry
when.operation: async_setup_entry
then.setup.setup_accepted: true
then.setup.setup_result.accepted: true
then.setup.entry_data_keys:
- dashboard_resource
- entity_catalog
- entity_catalog_setup
- entry
- history_retrieval
- history_retrieval_setup
- job_state
- websocket_api
then.setup.store.entry_id: setup-history-entry
then.setup.store.series_count: 0
then.setup.catalog_store.entity_ids:
- sensor.upstairs_temperature
- binary_sensor.office_window
```

### Scenario C

```text
case_id: config_entries_receive_isolated_history
given.entry_ids:
- history-entry-a
- history-entry-b
when.operation: retrieve_approved_history_for_each_entry
then.isolation.entry_a.accepted: true
then.isolation.entry_a_store.entity_ids:
- sensor.upstairs_temperature
then.isolation.entry_b.accepted: true
then.isolation.entry_b_store.entity_ids:
- binary_sensor.office_window
then.isolation.entry_a_validation[0].accepted: true
then.isolation.entry_b_validation[0].accepted: true
```

### Scenario D

```text
case_id: non_catalog_entities_fail_closed_before_history_read
given.requested_entity_id: light.kitchen
when.operation: retrieve_approved_history
then.non_catalog.result.accepted: false
then.non_catalog.result.code: entity_not_in_approved_catalog
then.non_catalog.result.rejected_entity_ids:
- light.kitchen
then.non_catalog.result.orchestration.approved_entity_catalog_read: true
then.non_catalog.result.orchestration.home_assistant_history_read: false
then.non_catalog.store.series_count: 0
```

### Scenario E

```text
case_id: rejected_retrieval_clears_existing_history
given.initial_entity_ids:
- sensor.upstairs_temperature
given.rejected_entity_ids:
- light.kitchen
when.operation: retrieve_approved_history_after_rejected_request
then.stale.accepted.accepted: true
then.stale.store_after_success.entity_ids:
- sensor.upstairs_temperature
then.stale.rejected.accepted: false
then.stale.rejected.code: entity_not_in_approved_catalog
then.stale.store_after_rejection.series_count: 0
then.stale.store_after_rejection.entity_ids: []
```

### Scenario F

```text
case_id: malformed_raw_history_fails_closed
given.malformed_field: last_changed
when.operation: retrieve_approved_history
then.malformed_raw.result.accepted: false
then.malformed_raw.result.code: invalid_history_records
then.malformed_raw.result.errors:
- path: $.history_by_entity.sensor.upstairs_temperature[0].last_changed
  reason: must_be_datetime
then.malformed_raw.result.orchestration.home_assistant_history_read: true
then.malformed_raw.store.series_count: 0
```

### Scenario G

```text
case_id: malformed_history_series_rejected_before_storage
given.schema: docs/schemas/history-series.schema.json
given.malformed_series.series_id: bad_history_series
given.malformed_series.kind: numeric
when.operation: store_validated_history_series
then.malformed_series.result.accepted: false
then.malformed_series.result.code: invalid_history_series
then.malformed_series.result.error: $.label is required.
then.malformed_series.result.item_index: 0
then.malformed_series.raw_series_after_attempt: []
then.malformed_series.store_after_attempt.series_count: 0
```

### Scenario H

```text
case_id: history_retrieval_remains_non_orchestrating
when.operation: aggregate_observed_side_effects
then.side_effects.forbidden_aggregate.worker_called: false
then.side_effects.forbidden_aggregate.model_provider_called: false
then.side_effects.forbidden_aggregate.semantic_memory_called: false
then.side_effects.forbidden_aggregate.home_assistant_service_or_state_mutation_called: false
then.side_effects.forbidden_aggregate.token_generated: false
then.side_effects.forbidden_aggregate.chart_artifact_written: false
then.side_effects.forbidden_aggregate.chart_rendering_called: false
then.side_effects.forbidden_aggregate.job_orchestration_called: false
then.side_effects.forbidden_aggregate.websocket_command_registered: false
then.side_effects.forbidden_aggregate.dashboard_resource_metadata_written_or_reused: false
then.side_effects.allowed_aggregate.approved_entity_catalog_read: true
then.side_effects.allowed_aggregate.home_assistant_history_read: true
then.side_effects.allowed_aggregate.history_retrieval_scaffold_written: true
```

## Adjacent Home Assistant Eval Verification

Raw commands:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_integration_scaffold.py
.\.venv\Scripts\python.exe evals\home_assistant_config_flow_options.py
.\.venv\Scripts\python.exe evals\home_assistant_dashboard_resource_registration.py
.\.venv\Scripts\python.exe evals\home_assistant_websocket_command_registration.py
.\.venv\Scripts\python.exe evals\home_assistant_job_state_scaffold.py
.\.venv\Scripts\python.exe evals\home_assistant_approved_entity_catalog_scaffold.py
```

Raw output endings:

```text
PASS home_assistant_integration_scaffold
PASS home_assistant_config_flow_options
PASS home_assistant_dashboard_resource_registration
PASS home_assistant_websocket_command_registration
PASS home_assistant_job_state_scaffold
PASS home_assistant_approved_entity_catalog_scaffold
```
