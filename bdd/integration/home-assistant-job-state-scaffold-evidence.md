# Home Assistant Job State Scaffold Evidence

Run timestamp: 2026-06-08T05:22:12+00:00

BDD file:
`bdd/integration/home-assistant-job-state-scaffold-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: starting a job creates deterministic state -> `CASE start_job_creates_deterministic_state`
- Scenario B: snapshot, retry, and clarification update existing jobs -> `CASE existing_job_commands_update_latest_snapshot`
- Scenario C: subscription records the callback shape -> `CASE subscription_records_callback_event_shape`
- Scenario D: config entries cannot see each other's jobs -> `CASE config_entries_cannot_read_each_others_jobs`
- Scenario E: unknown jobs fail closed -> `CASE unknown_jobs_fail_closed`
- Scenario F: unloading removes job state -> `CASE unload_removes_config_entry_job_state`
- Scenario G: job state remains non-orchestrating -> `CASE job_state_remains_non_orchestrating`
- Scenario H: malformed snapshots are rejected before storage -> `CASE malformed_snapshots_are_rejected_before_storage`

## Focused Unit Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_job_state_scaffold_anchor.py
```

Raw output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 9 items

tests\test_job_state_scaffold_anchor.py .........                        [100%]

============================== 9 passed in 0.33s ==============================
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
collected 92 items

tests\test_codegen_sandbox_anchor.py ..........                          [ 10%]
tests\test_config_flow_options_anchor.py .....                           [ 16%]
tests\test_dashboard_card_anchor.py .......                              [ 23%]
tests\test_dashboard_resource_registration_anchor.py .......             [ 31%]
tests\test_fake_vertical_slice.py .....................................  [ 71%]
tests\test_integration_scaffold_anchor.py .....                          [ 77%]
tests\test_job_state_scaffold_anchor.py .........                        [ 86%]
tests\test_transport_auth_anchor.py .....                                [ 92%]
tests\test_websocket_command_registration_anchor.py .......              [100%]

============================= 92 passed in 33.97s =============================
```

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_job_state_scaffold.py
```

Raw output summary:

```text
CASE start_job_creates_deterministic_state
PASS start_job_creates_deterministic_state
CASE existing_job_commands_update_latest_snapshot
PASS existing_job_commands_update_latest_snapshot
CASE subscription_records_callback_event_shape
PASS subscription_records_callback_event_shape
CASE config_entries_cannot_read_each_others_jobs
PASS config_entries_cannot_read_each_others_jobs
CASE unknown_jobs_fail_closed
PASS unknown_jobs_fail_closed
CASE unload_removes_config_entry_job_state
PASS unload_removes_config_entry_job_state
CASE malformed_snapshots_are_rejected_before_storage
PASS malformed_snapshots_are_rejected_before_storage
CASE job_state_remains_non_orchestrating
PASS job_state_remains_non_orchestrating
PASS home_assistant_job_state_scaffold
```

## Scenario Evidence Excerpts

These excerpts are copied from the `CASE` payloads emitted by the eval run.

### Scenario A

```text
case_id: start_job_creates_deterministic_state
given.config_entry_id: fake-config-entry
when.operation: dispatch_registered_start_job
then.start.dispatch.accepted: true
then.start.dispatch.connection.errors: []
then.start.snapshot.job_id: fake-config-entry-job-001
then.start.snapshot.snapshot_id: fake-config-entry-job-001-snapshot-001
then.start.snapshot.status: planning
then.start.snapshot.progress.stage: job_state_scaffold
then.start.snapshot_validation.accepted: true
then.start.store.entry_id: fake-config-entry
then.start.store.job_ids:
- fake-config-entry-job-001
then.start.store.latest_snapshot_ids:
- fake-config-entry-job-001-snapshot-001
```

### Scenario B

```text
case_id: existing_job_commands_update_latest_snapshot
given.job_id: fake-config-entry-job-001
when.operation: dispatch_snapshot_retry_and_clarification
then.updates.start.accepted: true
then.updates.get_snapshot.accepted: true
then.updates.retry.accepted: true
then.updates.answer_clarification.accepted: true
then.updates.snapshot_ids:
- fake-config-entry-job-001-snapshot-001
- fake-config-entry-job-001-snapshot-001
- fake-config-entry-job-001-snapshot-002
- fake-config-entry-job-001-snapshot-003
then.updates.store.latest_snapshot_id: fake-config-entry-job-001-snapshot-003
then.updates.store.clarification_answers:
- question_id: clarify_upstairs_temperature
  option_id: average_upstairs_temperature
  remember: true
then.updates.answer_clarification.orchestration.job_state_scaffold_written: true
then.updates.answer_clarification.orchestration.job_orchestration_called: false
```

### Scenario C

```text
case_id: subscription_records_callback_event_shape
given.job_id: fake-config-entry-job-001
when.operation: dispatch_registered_subscribe_job
then.subscription.subscribe.accepted: true
then.subscription.connection.errors: []
then.subscription.connection.results[0].result.snapshot_id:
  fake-config-entry-job-001-snapshot-001
then.subscription.subscription.subscription_id:
  fake-config-entry-job-001-subscription-001
then.subscription.subscription.message_id: 21
then.subscription.subscription.event.type: isolinear_job_snapshot
then.subscription.subscription.event.job_id: fake-config-entry-job-001
then.subscription.subscription.event.snapshot.snapshot_id:
  fake-config-entry-job-001-snapshot-001
then.subscription.store.subscription_count: 1
then.subscription.subscribe.orchestration.subscription_bookkeeping_written: true
```

### Scenario D

```text
case_id: config_entries_cannot_read_each_others_jobs
given.entry_ids:
- entry-a
- entry-b
when.operation: entry_b_requests_entry_a_job
then.isolation.entry_a_start.accepted: true
then.isolation.entry_b_start.accepted: true
then.isolation.entry_a_store.job_ids:
- entry-a-job-001
then.isolation.entry_b_store.job_ids:
- entry-b-job-001
then.isolation.cross_entry_snapshot.accepted: false
then.isolation.cross_entry_snapshot.connection.errors[0].code: unknown_job
then.isolation.cross_entry_snapshot.connection.results: []
```

### Scenario E

```text
case_id: unknown_jobs_fail_closed
given.job_id: missing-job
given.commands:
- get_snapshot
- retry_job
- answer_clarification
- subscribe_job
when.operation: dispatch_unknown_job_commands
then.unknown.dispatch_results.get_snapshot.accepted: false
then.unknown.dispatch_results.get_snapshot.connection.errors[0].code: unknown_job
then.unknown.dispatch_results.retry_job.accepted: false
then.unknown.dispatch_results.retry_job.connection.errors[0].code: unknown_job
then.unknown.dispatch_results.answer_clarification.accepted: false
then.unknown.dispatch_results.answer_clarification.connection.errors[0].code: unknown_job
then.unknown.dispatch_results.subscribe_job.accepted: false
then.unknown.dispatch_results.subscribe_job.connection.errors[0].code: unknown_job
then.unknown.dispatch_results.*.connection.results: []
then.unknown.store.job_ids: []
```

### Scenario F

```text
case_id: unload_removes_config_entry_job_state
given.entry_id: fake-config-entry
when.operation: async_unload_entry
then.unload.setup_accepted: true
then.unload.start.accepted: true
then.unload.subscribe.accepted: true
then.unload.had_job_state_before_unload: true
then.unload.unload_accepted: true
then.unload.entry_present_after_unload: false
```

### Scenario G

```text
case_id: job_state_remains_non_orchestrating
when.operation: aggregate_observed_side_effects
then.side_effects.forbidden_aggregate.worker_called: false
then.side_effects.forbidden_aggregate.model_provider_called: false
then.side_effects.forbidden_aggregate.home_assistant_history_called: false
then.side_effects.forbidden_aggregate.semantic_memory_called: false
then.side_effects.forbidden_aggregate.home_assistant_service_or_state_mutation_called: false
then.side_effects.forbidden_aggregate.token_generated: false
then.side_effects.forbidden_aggregate.chart_artifact_written: false
then.side_effects.forbidden_aggregate.job_orchestration_called: false
then.side_effects.allowed_aggregate.job_state_scaffold_written: true
then.side_effects.allowed_aggregate.subscription_bookkeeping_written: true
then.side_effects.allowed_aggregate.websocket_command_registered: true
```

### Scenario H

```text
case_id: malformed_snapshots_are_rejected_before_storage
given.schema: docs/schemas/integration-job-snapshot.schema.json
given.malformed_snapshot.snapshot_id: malformed-job-001-snapshot-001
given.malformed_snapshot.job_id: malformed-job-001
given.malformed_snapshot.status: planning
when.operation: store_validated_job_snapshot
then.malformed.result.accepted: false
then.malformed.result.code: invalid_integration_job_snapshot
then.malformed.result.error: $.prompt is required.
then.malformed.snapshots_after_attempt: []
then.malformed.latest_snapshot_after_attempt: null
```

## Adjacent Home Assistant Eval Verification

Raw commands:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_integration_scaffold.py
.\.venv\Scripts\python.exe evals\home_assistant_config_flow_options.py
.\.venv\Scripts\python.exe evals\home_assistant_dashboard_resource_registration.py
.\.venv\Scripts\python.exe evals\home_assistant_websocket_command_registration.py
```

Raw output endings:

```text
PASS home_assistant_integration_scaffold
PASS home_assistant_config_flow_options
PASS home_assistant_dashboard_resource_registration
PASS home_assistant_websocket_command_registration
```
