# Home Assistant Job Orchestration Clarification Continuation Scaffold Evidence

Run timestamp: 2026-06-08T19:31:01+00:00

BDD file:
`bdd/integration/home-assistant-job-orchestration-clarification-continuation-scaffold-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: accepted clarification resumes the same job -> `CASE accepted_clarification_resumes_same_job`
- Scenario B: unknown option fails before history -> `CASE unknown_option_fails_before_history`
- Scenario C: wrong question fails before history -> `CASE wrong_question_fails_before_history`
- Scenario D: colliding option fails before history -> `CASE colliding_option_fails_before_history`
- Scenario E: config entries cannot answer each other's jobs -> `CASE cross_config_entry_answer_rejected`
- Scenario F: valid continuations stay config-entry scoped -> `CASE valid_continuations_stay_config_entry_scoped`
- Scenario G: continuation snapshots validate before storage -> `CASE continuation_snapshots_validate_before_storage`
- Scenario H: continuation scaffold remains bounded -> `CASE clarification_continuation_remains_bounded`

## Focused Unit Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_job_orchestration_clarification_continuation_anchor.py
```

Raw output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 9 items

tests\test_job_orchestration_clarification_continuation_anchor.py ...... [ 66%]
...                                                                      [100%]

============================== 9 passed in 1.01s ==============================
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
collected 128 items

tests\test_approved_entity_catalog_scaffold_anchor.py .........          [  7%]
tests\test_approved_history_retrieval_scaffold_anchor.py .........       [ 14%]
tests\test_codegen_sandbox_anchor.py ..........                          [ 21%]
tests\test_config_flow_options_anchor.py .....                           [ 25%]
tests\test_dashboard_card_anchor.py .......                              [ 31%]
tests\test_dashboard_resource_registration_anchor.py .......             [ 36%]
tests\test_fake_vertical_slice.py .....................................  [ 65%]
tests\test_integration_scaffold_anchor.py .....                          [ 69%]
tests\test_job_orchestration_clarification_continuation_anchor.py ...... [ 74%]
...                                                                      [ 76%]
tests\test_job_orchestration_scaffold_anchor.py .........                [ 83%]
tests\test_job_state_scaffold_anchor.py .........                        [ 90%]
tests\test_transport_auth_anchor.py .....                                [ 94%]
tests\test_websocket_command_registration_anchor.py .......              [100%]

============================ 128 passed in 39.35s =============================
```

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_clarification_continuation_scaffold.py
```

Raw output summary:

```text
CASE accepted_clarification_resumes_same_job
PASS accepted_clarification_resumes_same_job
CASE unknown_option_fails_before_history
PASS unknown_option_fails_before_history
CASE wrong_question_fails_before_history
PASS wrong_question_fails_before_history
CASE colliding_option_fails_before_history
PASS colliding_option_fails_before_history
CASE cross_config_entry_answer_rejected
PASS cross_config_entry_answer_rejected
CASE valid_continuations_stay_config_entry_scoped
PASS valid_continuations_stay_config_entry_scoped
CASE continuation_snapshots_validate_before_storage
PASS continuation_snapshots_validate_before_storage
CASE clarification_continuation_remains_bounded
PASS clarification_continuation_remains_bounded
PASS home_assistant_job_orchestration_clarification_continuation_scaffold
```

## Scenario Evidence Excerpts

These excerpts are copied from the `CASE` payloads emitted by the eval run.

### Scenario A

```text
case_id: accepted_clarification_resumes_same_job
given.config_entry_id: clarification-entry
when.operation: dispatch_registered_clarification_answer
when.option_id: sensor_upstairs_temperature
then.accepted.answer.accepted: true
then.accepted.same_job_id: true
then.accepted.answer_snapshot.job_id: clarification-entry-job-001
then.accepted.answer_snapshot.snapshot_id: clarification-entry-job-001-snapshot-005
then.accepted.answer_snapshot.progress.stage: job_orchestration_clarification_continuation_ready
then.accepted.job_progress_stages:
- job_state_scaffold
- entity_selection_clarification
- clarification_answer_accepted
- approved_history_retrieval
- job_orchestration_clarification_continuation_ready
then.accepted.history_store.entity_ids:
- sensor.upstairs_temperature
then.accepted.run.result_code: clarification_approved_history_ready
then.accepted.run.requested_entity_ids:
- sensor.upstairs_temperature
then.accepted.snapshot_validation.*.accepted: true
```

### Scenario B

```text
case_id: unknown_option_fails_before_history
given.option_id: sensor_basement_temperature
when.operation: dispatch_registered_clarification_answer
then.unknown_option.answer.accepted: false
then.unknown_option.error_codes:
- unknown_clarification_option
then.unknown_option.snapshot_count_before: 2
then.unknown_option.snapshot_count_after: 2
then.unknown_option.answer.orchestration.home_assistant_history_read: false
then.unknown_option.history_store.series_count: 0
then.unknown_option.run.result_code: unknown_clarification_option
```

### Scenario C

```text
case_id: wrong_question_fails_before_history
given.question_id: select_different_question
when.operation: dispatch_registered_clarification_answer
then.wrong_question.answer.accepted: false
then.wrong_question.error_codes:
- clarification_question_mismatch
then.wrong_question.snapshot_count_before: 2
then.wrong_question.snapshot_count_after: 2
then.wrong_question.answer.orchestration.home_assistant_history_read: false
then.wrong_question.history_store.series_count: 0
then.wrong_question.run.result_code: clarification_question_mismatch
```

### Scenario D

```text
case_id: colliding_option_fails_before_history
given.option_id: sensor_foo_bar
given.approved_entity_ids:
- sensor.foo_bar
- sensor_foo.bar
when.operation: dispatch_registered_clarification_answer
then.collision.answer.accepted: false
then.collision.error_codes:
- ambiguous_clarification_option
then.collision.start_options.option_id:
- sensor_foo_bar
- sensor_foo_bar
then.collision.snapshot_count_before: 2
then.collision.snapshot_count_after: 2
then.collision.answer.orchestration.home_assistant_history_read: false
then.collision.history_store.series_count: 0
then.collision.run.result_code: ambiguous_clarification_option
```

### Scenario E

```text
case_id: cross_config_entry_answer_rejected
given.entry_ids:
- answer-entry-a
- answer-entry-b
when.operation: answer_entry_a_job_from_entry_b
then.cross_entry.cross_answer.accepted: false
then.cross_entry.error_codes:
- unknown_job
then.cross_entry.cross_answer.orchestration.home_assistant_history_read: false
then.cross_entry.entry_a_history_store.series_count: 0
then.cross_entry.entry_b_history_store.series_count: 0
then.cross_entry.entry_a_orchestration_store.latest_result_code: entity_selection_requires_clarification
then.cross_entry.entry_b_orchestration_store.latest_result_code: entity_selection_requires_clarification
```

### Scenario F

```text
case_id: valid_continuations_stay_config_entry_scoped
given.entry_ids:
- continuation-entry-a
- continuation-entry-b
when.operation: answer_each_entry_own_clarification
then.isolation.entry_a.answer.accepted: true
then.isolation.entry_b.answer.accepted: true
then.isolation.entry_a.snapshot.job_id: continuation-entry-a-job-001
then.isolation.entry_b.snapshot.job_id: continuation-entry-b-job-001
then.isolation.entry_a.history_store.entity_ids:
- sensor.upstairs_temperature
then.isolation.entry_b.history_store.entity_ids:
- binary_sensor.office_window
then.isolation.entry_a.run.requested_entity_ids:
- sensor.upstairs_temperature
then.isolation.entry_b.run.requested_entity_ids:
- binary_sensor.office_window
```

### Scenario G

```text
case_id: continuation_snapshots_validate_before_storage
given.schema: docs/schemas/integration-job-snapshot.schema.json
when.operation: validate_observed_continuation_snapshots
then.snapshot_validation.success.all_snapshots_valid: true
then.snapshot_validation.isolation_entry_a.all_snapshots_valid: true
then.snapshot_validation.isolation_entry_b.all_snapshots_valid: true
then.snapshot_validation.success.snapshot_validation.progress_stage:
- job_state_scaffold
- entity_selection_clarification
- clarification_answer_accepted
- approved_history_retrieval
- job_orchestration_clarification_continuation_ready
```

### Scenario H

```text
case_id: clarification_continuation_remains_bounded
when.operation: aggregate_observed_side_effects
then.side_effects.forbidden_aggregate.worker_called: false
then.side_effects.forbidden_aggregate.model_provider_called: false
then.side_effects.forbidden_aggregate.semantic_memory_called: false
then.side_effects.forbidden_aggregate.home_assistant_service_or_state_mutation_called: false
then.side_effects.forbidden_aggregate.token_generated: false
then.side_effects.forbidden_aggregate.chart_artifact_written: false
then.side_effects.forbidden_aggregate.chart_rendering_called: false
then.side_effects.forbidden_aggregate.durable_storage_written: false
then.side_effects.forbidden_aggregate.retry_behavior_called: false
then.side_effects.forbidden_aggregate.subscription_progress_streaming_called: false
then.side_effects.forbidden_aggregate.job_orchestration_called: false
then.side_effects.allowed_aggregate.approved_entity_catalog_read: true
then.side_effects.allowed_aggregate.home_assistant_history_read: true
then.side_effects.allowed_aggregate.history_retrieval_scaffold_written: true
then.side_effects.allowed_aggregate.job_state_scaffold_written: true
then.side_effects.allowed_aggregate.job_orchestration_scaffold_written: true
then.side_effects.allowed_aggregate.websocket_command_registered: true
```

## Adjacent Home Assistant Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_job_orchestration_scaffold_anchor.py tests/test_job_state_scaffold_anchor.py tests/test_websocket_command_registration_anchor.py tests/test_approved_entity_catalog_scaffold_anchor.py tests/test_approved_history_retrieval_scaffold_anchor.py
```

Raw output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 43 items

tests\test_job_orchestration_scaffold_anchor.py .........                [ 20%]
tests\test_job_state_scaffold_anchor.py .........                        [ 41%]
tests\test_websocket_command_registration_anchor.py .......              [ 58%]
tests\test_approved_entity_catalog_scaffold_anchor.py .........          [ 79%]
tests\test_approved_history_retrieval_scaffold_anchor.py .........       [100%]

============================= 43 passed in 1.46s ==============================
```

Adjacent eval raw output endings:

```text
PASS home_assistant_job_orchestration_scaffold
PASS home_assistant_job_state_scaffold
PASS home_assistant_approved_entity_catalog_scaffold
PASS home_assistant_approved_history_retrieval_scaffold
PASS home_assistant_websocket_command_registration
```

## On-Disk Verification

Raw command:

```powershell
Select-String -LiteralPath custom_components/isolinear/job_orchestration.py -Pattern "handle_job_orchestration_clarification_answer_ws_command","clarification_answer_accepted","job_orchestration_clarification_continuation_ready","unknown_clarification_option","clarification_question_mismatch","ambiguous_clarification_option"
Select-String -LiteralPath custom_components/isolinear/websocket_api.py -Pattern "handle_job_orchestration_clarification_answer_ws_command","answer_clarification","orchestration_enabled"
Select-String -LiteralPath src/Isolinear/job_orchestration_clarification_continuation_anchor.py -Pattern "verify_accepted_clarification_resumes_same_job","verify_unknown_option_fails_before_history","verify_colliding_option_fails_before_history","verify_cross_config_entry_answer_rejected","verify_valid_continuations_stay_config_entry_scoped"
git diff --check
```

Verified on disk:

- `custom_components/isolinear/job_orchestration.py` contains the clarification
  answer handler, accepted-continuation stage, ready stage, unknown-option
  gate, question-mismatch gate, and colliding-option gate.
- `custom_components/isolinear/websocket_api.py` routes enabled
  `clarification/answer` commands through the orchestration continuation
  scaffold.
- `src/Isolinear/job_orchestration_clarification_continuation_anchor.py`
  contains the continuation verifier cases, including the option-ID collision
  proof.
- `git diff --check` reported no whitespace errors; it only printed Git's
  LF-to-CRLF working-copy warnings for touched Python files.
