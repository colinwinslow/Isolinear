# Home Assistant Job Orchestration Scaffold Evidence

Run timestamp: 2026-06-08T18:38:42+00:00

BDD file:
`bdd/integration/home-assistant-job-orchestration-scaffold-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: start job composes catalog, history, and job state -> `CASE start_job_composes_catalog_history_and_job_state`
- Scenario B: non-catalog prompt entities fail before history -> `CASE non_catalog_prompt_entities_fail_before_history`
- Scenario C: missing approved history is structured -> `CASE missing_approved_history_returns_failed_snapshot`
- Scenario D: config entries stay scoped -> `CASE config_entries_keep_orchestration_scoped`
- Scenario E: ambiguous prompts ask for clarification -> `CASE ambiguous_prompt_requests_clarification`
- Scenario F: setup stores orchestration state -> `CASE setup_entry_stores_orchestration_state`
- Scenario G: orchestration scaffold remains bounded -> `CASE job_orchestration_scaffold_remains_bounded`
- Scenario H: returned snapshots validate before storage -> `CASE orchestration_snapshots_validate_before_storage`

## Focused Unit Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_job_orchestration_scaffold_anchor.py
```

Raw output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 9 items

tests\test_job_orchestration_scaffold_anchor.py .........                [100%]

============================== 9 passed in 0.68s ==============================
```

## Full Unit Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/
```

Raw output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 119 items

tests\test_approved_entity_catalog_scaffold_anchor.py .........          [  7%]
tests\test_approved_history_retrieval_scaffold_anchor.py .........       [ 15%]
tests\test_codegen_sandbox_anchor.py ..........                          [ 23%]
tests\test_config_flow_options_anchor.py .....                           [ 27%]
tests\test_dashboard_card_anchor.py .......                              [ 33%]
tests\test_dashboard_resource_registration_anchor.py .......             [ 39%]
tests\test_fake_vertical_slice.py .....................................  [ 70%]
tests\test_integration_scaffold_anchor.py .....                          [ 74%]
tests\test_job_orchestration_scaffold_anchor.py .........                [ 82%]
tests\test_job_state_scaffold_anchor.py .........                        [ 89%]
tests\test_transport_auth_anchor.py .....                                [ 94%]
tests\test_websocket_command_registration_anchor.py .......              [100%]

============================ 119 passed in 53.07s =============================
```

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_scaffold.py
```

Raw output summary:

```text
CASE start_job_composes_catalog_history_and_job_state
PASS start_job_composes_catalog_history_and_job_state
CASE non_catalog_prompt_entities_fail_before_history
PASS non_catalog_prompt_entities_fail_before_history
CASE missing_approved_history_returns_failed_snapshot
PASS missing_approved_history_returns_failed_snapshot
CASE config_entries_keep_orchestration_scoped
PASS config_entries_keep_orchestration_scoped
CASE ambiguous_prompt_requests_clarification
PASS ambiguous_prompt_requests_clarification
CASE setup_entry_stores_orchestration_state
PASS setup_entry_stores_orchestration_state
CASE job_orchestration_scaffold_remains_bounded
PASS job_orchestration_scaffold_remains_bounded
CASE orchestration_snapshots_validate_before_storage
PASS orchestration_snapshots_validate_before_storage
PASS home_assistant_job_orchestration_scaffold
```

## Scenario Evidence Excerpts

These excerpts are copied from the `CASE` payloads emitted by the eval run.

### Scenario A

```text
case_id: start_job_composes_catalog_history_and_job_state
given.config_entry_id: orchestration-entry
when.operation: dispatch_registered_start_job
then.success.dispatch.accepted: true
then.success.snapshot.job_id: orchestration-entry-job-001
then.success.snapshot.snapshot_id: orchestration-entry-job-001-snapshot-003
then.success.snapshot.status: planning
then.success.snapshot.progress.stage: job_orchestration_scaffold_ready
then.success.job_snapshot_statuses:
- planning
- fetching_history
- planning
then.success.history_store.entity_ids:
- sensor.upstairs_temperature
- binary_sensor.office_window
then.success.orchestration_store.latest_result_code: approved_history_ready
then.success.snapshot_validation.*.accepted: true
```

### Scenario B

```text
case_id: non_catalog_prompt_entities_fail_before_history
given.prompt_entity_id: light.kitchen
when.operation: dispatch_registered_start_job
then.non_catalog.dispatch.accepted: true
then.non_catalog.snapshot.status: failed
then.non_catalog.snapshot.failure.code: entity_not_in_approved_catalog
then.non_catalog.run.requested_entity_ids:
- light.kitchen
then.non_catalog.run.rejected_entity_ids:
- light.kitchen
then.non_catalog.orchestration.home_assistant_history_read: false
then.non_catalog.history_store.series_count: 0
then.non_catalog.snapshot_validation.accepted: true
```

### Scenario C

```text
case_id: missing_approved_history_returns_failed_snapshot
given.missing_entity_id: sensor.downstairs_temperature
when.operation: dispatch_registered_start_job
then.missing_history.dispatch.accepted: true
then.missing_history.snapshot.status: failed
then.missing_history.snapshot.failure.code: missing_approved_history
then.missing_history.run.missing_entity_ids:
- sensor.downstairs_temperature
then.missing_history.orchestration.home_assistant_history_read: true
then.missing_history.snapshot_validation.accepted: true
```

### Scenario D

```text
case_id: config_entries_keep_orchestration_scoped
given.entry_ids:
- orch-entry-a
- orch-entry-b
when.operation: dispatch_start_job_for_each_entry
then.isolation.entry_a.snapshot.job_id: orch-entry-a-job-001
then.isolation.entry_b.snapshot.job_id: orch-entry-b-job-001
then.isolation.entry_a.history_store.entity_ids:
- sensor.upstairs_temperature
then.isolation.entry_b.history_store.entity_ids:
- binary_sensor.office_window
then.isolation.entry_a.orchestration_store.latest_requested_entity_ids:
- sensor.upstairs_temperature
then.isolation.entry_b.orchestration_store.latest_requested_entity_ids:
- binary_sensor.office_window
```

### Scenario E

```text
case_id: ambiguous_prompt_requests_clarification
given.approved_entity_ids:
- sensor.upstairs_temperature
- sensor.downstairs_temperature
given.prompt: Show thermostat history
when.operation: dispatch_registered_start_job
then.ambiguous.dispatch.accepted: true
then.ambiguous.snapshot.status: clarification_needed
then.ambiguous.snapshot.clarification.question_id: select_approved_entity
then.ambiguous.snapshot.clarification.options.option_id:
- sensor_upstairs_temperature
- sensor_downstairs_temperature
then.ambiguous.orchestration.home_assistant_history_read: false
then.ambiguous.history_store.series_count: 0
then.ambiguous.snapshot_validation.accepted: true
```

### Scenario F

```text
case_id: setup_entry_stores_orchestration_state
given.entry_id: setup-orchestration-entry
when.operation: async_setup_entry
then.setup.setup_accepted: true
then.setup.setup_result.accepted: true
then.setup.setup_result.enabled: true
then.setup.entry_data_keys:
- job_orchestration
- job_orchestration_setup
then.setup.store.entry_id: setup-orchestration-entry
then.setup.catalog_entity_ids:
- sensor.upstairs_temperature
```

### Scenario G

```text
case_id: job_orchestration_scaffold_remains_bounded
when.operation: aggregate_observed_side_effects
then.side_effects.forbidden_aggregate.worker_called: false
then.side_effects.forbidden_aggregate.model_provider_called: false
then.side_effects.forbidden_aggregate.semantic_memory_called: false
then.side_effects.forbidden_aggregate.home_assistant_service_or_state_mutation_called: false
then.side_effects.forbidden_aggregate.token_generated: false
then.side_effects.forbidden_aggregate.chart_artifact_written: false
then.side_effects.forbidden_aggregate.chart_rendering_called: false
then.side_effects.forbidden_aggregate.durable_storage_written: false
then.side_effects.forbidden_aggregate.job_orchestration_called: false
then.side_effects.allowed_aggregate.approved_entity_catalog_read: true
then.side_effects.allowed_aggregate.home_assistant_history_read: true
then.side_effects.allowed_aggregate.history_retrieval_scaffold_written: true
then.side_effects.allowed_aggregate.job_state_scaffold_written: true
then.side_effects.allowed_aggregate.job_orchestration_scaffold_written: true
then.side_effects.allowed_aggregate.websocket_command_registered: true
```

### Scenario H

```text
case_id: orchestration_snapshots_validate_before_storage
given.schema: docs/schemas/integration-job-snapshot.schema.json
when.operation: validate_observed_orchestration_snapshots
then.snapshot_validation.success.all_snapshots_valid: true
then.snapshot_validation.non_catalog.snapshot_validation.accepted: true
then.snapshot_validation.missing_history.snapshot_validation.accepted: true
```

## Adjacent Home Assistant Eval Verification

Raw commands:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_job_state_scaffold.py
.\.venv\Scripts\python.exe evals\home_assistant_approved_entity_catalog_scaffold.py
.\.venv\Scripts\python.exe evals\home_assistant_approved_history_retrieval_scaffold.py
.\.venv\Scripts\python.exe evals\home_assistant_websocket_command_registration.py
```

Raw output endings:

```text
PASS home_assistant_job_state_scaffold
PASS home_assistant_approved_entity_catalog_scaffold
PASS home_assistant_approved_history_retrieval_scaffold
PASS home_assistant_websocket_command_registration
```

## On-Disk Verification

Raw command:

```powershell
Select-String -LiteralPath custom_components/isolinear/job_orchestration.py -Pattern "handle_job_orchestration_start_ws_command","missing_approved_history","job_orchestration_scaffold_ready","job_orchestration_side_effects"
Select-String -LiteralPath custom_components/isolinear/job_orchestration.py -Pattern "select_approved_entity"
Select-String -LiteralPath custom_components/isolinear/websocket_api.py -Pattern "has_enabled_job_orchestration","handle_job_orchestration_start_ws_command","job_orchestration"
Select-String -LiteralPath custom_components/isolinear/__init__.py -Pattern "setup_job_orchestration","job_orchestration_setup"
```

Verified on disk:

- `custom_components/isolinear/job_orchestration.py` contains the start handler,
  missing-history failure, ready snapshot stage, and side-effect accounting.
- `custom_components/isolinear/job_orchestration.py` contains the
  `select_approved_entity` clarification gate for ambiguous prompts.
- `custom_components/isolinear/websocket_api.py` routes enabled `job/start`
  commands through the orchestration scaffold and returns the run summary.
- `custom_components/isolinear/__init__.py` stores
  `job_orchestration_setup` during config-entry setup.
