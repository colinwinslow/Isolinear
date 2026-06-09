# Home Assistant Job Orchestration Worker Dispatch/Rendering Scaffold Evidence

Run timestamp: 2026-06-09T16:56:46+00:00

BDD file:
`bdd/integration/home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: worker dispatch records render result -> `CASE worker_dispatch_records_render_result`
- Scenario B: repeated snapshot requests reuse worker dispatch -> `CASE repeated_snapshot_requests_reuse_worker_dispatch`
- Scenario C: worker request, response, and dispatch validate -> `CASE worker_dispatch_contracts_validate_before_storage`
- Scenario D: worker authorization is redacted -> `CASE worker_authorization_is_redacted`
- Scenario E: worker failure fails before storage -> `CASE worker_failure_rejected_before_storage`
- Scenario F: unknown job fails before worker call -> `CASE unknown_job_rejected_before_worker_call`
- Scenario G: config entries cannot dispatch workers for each other's jobs -> `CASE cross_config_entry_rejected_before_worker_call`
- Scenario H: valid worker dispatches stay config-entry scoped -> `CASE valid_worker_dispatches_stay_config_entry_scoped`
- Scenario I: worker dispatch remains bounded -> `CASE worker_dispatch_remains_bounded`

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_worker_dispatch_rendering_scaffold.py
```

Raw output excerpt:

```text
CASE worker_dispatch_records_render_result
  accepted.snapshot_dispatch.accepted = true
  accepted.worker_call_count = 1
  accepted.artifact_snapshot.status = complete
  accepted.artifact_snapshot.snapshot_id = worker-dispatch-entry-job-001-snapshot-004
  accepted.worker_dispatch.dispatch_id = worker-dispatch-entry-worker-dispatch-001
  accepted.worker_dispatch.job_id = worker-dispatch-entry-job-001
  accepted.worker_dispatch.source_snapshot_id = worker-dispatch-entry-job-001-snapshot-003
  accepted.worker_dispatch.render_plan_id = worker-dispatch-entry-render-plan-001
  accepted.worker_dispatch.artifact_id = worker-dispatch-entry-artifact-001
  accepted.worker_dispatch.status = render_succeeded
  accepted.worker_dispatch.request.headers.authorization = Bearer <redacted>
  accepted.worker_dispatch.render_result.status = success
  accepted.worker_calls[0].history_entity_ids = ["sensor.upstairs_temperature"]
  accepted.snapshot_dispatch.orchestration.worker_called = true
  accepted.snapshot_dispatch.orchestration.chart_rendering_called = true
  accepted.snapshot_dispatch.orchestration.worker_dispatch_bookkeeping_written = true
PASS worker_dispatch_records_render_result

CASE repeated_snapshot_requests_reuse_worker_dispatch
  idempotent.first.accepted = true
  idempotent.second.accepted = true
  idempotent.worker_call_count = 1
  idempotent.same_snapshot_returned = true
  idempotent.same_worker_dispatch_returned = true
  idempotent.worker_dispatch_count = 1
  idempotent.render_plan_count = 1
  idempotent.artifact_count = 1
  idempotent.complete_snapshot_count = 1
PASS repeated_snapshot_requests_reuse_worker_dispatch

CASE worker_dispatch_contracts_validate_before_storage
  validation.accepted.worker_dispatch_valid = true
  validation.accepted.worker_transport_valid = true
  validation.accepted.render_request_valid = true
  validation.accepted.render_result_valid = true
  validation.accepted.render_plan_valid = true
  validation.accepted.chart_spec_valid = true
  validation.accepted.history_series_valid = true
  validation.idempotent.worker_dispatch_valid = true
  validation.isolation_entry_a.worker_dispatch_valid = true
  validation.isolation_entry_b.worker_dispatch_valid = true
PASS worker_dispatch_contracts_validate_before_storage

CASE worker_authorization_is_redacted
  redaction.raw_worker_authorization_received = true
  redaction.stored_authorization = Bearer <redacted>
  redaction.stored_authorization_redacted = true
  redaction.worker_token_absent_from_evidence = true
PASS worker_authorization_is_redacted

CASE worker_failure_rejected_before_storage
  failure.error_codes = ["worker_safe_renderer_failed"]
  failure.worker_call_count = 1
  failure.worker_dispatches = []
  failure.render_plans = []
  failure.artifacts = []
  failure.complete_snapshots = []
  failure.snapshot.orchestration.worker_called = true
  failure.snapshot.orchestration.worker_dispatch_bookkeeping_written = false
  failure.snapshot.orchestration.render_plan_bookkeeping_written = false
  failure.snapshot.orchestration.artifact_metadata_bookkeeping_written = false
PASS worker_failure_rejected_before_storage

CASE unknown_job_rejected_before_worker_call
  unknown_job.error_codes = ["unknown_job"]
  unknown_job.worker_call_count = 0
  unknown_job.worker_dispatches = []
  unknown_job.render_plans = []
  unknown_job.artifacts = []
PASS unknown_job_rejected_before_worker_call

CASE cross_config_entry_rejected_before_worker_call
  cross_entry.error_codes = ["unknown_job"]
  cross_entry.entry_a_worker_call_count = 0
  cross_entry.entry_b_worker_call_count = 0
  cross_entry.entry_b_worker_dispatches = []
  cross_entry.entry_b_render_plans = []
  cross_entry.entry_b_artifacts = []
  cross_entry.entry_b_complete_snapshots = []
PASS cross_config_entry_rejected_before_worker_call

CASE valid_worker_dispatches_stay_config_entry_scoped
  isolation.entry_a.worker_call_count = 1
  isolation.entry_b.worker_call_count = 1
  isolation.entry_a.worker_dispatches[0].job_id = worker-isolation-entry-a-job-001
  isolation.entry_b.worker_dispatches[0].job_id = worker-isolation-entry-b-job-001
  isolation.entry_a.worker_calls[0].history_entity_ids = ["sensor.upstairs_temperature"]
  isolation.entry_b.worker_calls[0].history_entity_ids = ["binary_sensor.office_window"]
  isolation.entry_a.render_plans[0].chart_spec.chart_type = time_series
  isolation.entry_b.render_plans[0].chart_spec.chart_type = timeline
PASS valid_worker_dispatches_stay_config_entry_scoped

CASE worker_dispatch_remains_bounded
  side_effects.allowed_aggregate.worker_called = true
  side_effects.allowed_aggregate.chart_rendering_called = true
  side_effects.allowed_aggregate.worker_dispatch_bookkeeping_written = true
  side_effects.allowed_aggregate.render_plan_bookkeeping_written = true
  side_effects.allowed_aggregate.artifact_metadata_bookkeeping_written = true
  side_effects.allowed_aggregate.job_state_scaffold_written = true
  side_effects.allowed_aggregate.job_orchestration_scaffold_written = true
  side_effects.allowed_aggregate.websocket_command_registered = true
  side_effects.forbidden_aggregate.home_assistant_history_read = false
  side_effects.forbidden_aggregate.semantic_memory_called = false
  side_effects.forbidden_aggregate.home_assistant_service_or_state_mutation_called = false
  side_effects.forbidden_aggregate.token_generated = false
  side_effects.forbidden_aggregate.chart_artifact_written = false
  side_effects.forbidden_aggregate.durable_storage_written = false
  side_effects.forbidden_aggregate.retry_behavior_called = false
  side_effects.forbidden_aggregate.subscription_progress_streaming_called = false
  side_effects.forbidden_aggregate.job_orchestration_called = false
PASS worker_dispatch_remains_bounded
PASS home_assistant_job_orchestration_worker_dispatch_rendering_scaffold
```

## Additional Verification

```text
.\.venv\Scripts\python.exe -m pytest tests/test_job_orchestration_worker_dispatch_rendering_anchor.py
10 passed

.\.venv\Scripts\python.exe -m pytest tests/test_job_orchestration_model_provider_planning_anchor.py tests/test_job_orchestration_render_planning_anchor.py tests/test_job_orchestration_artifact_storage_anchor.py
27 passed

.\.venv\Scripts\python.exe -m pytest tests\
180 passed

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_worker_dispatch_rendering_scaffold.py
PASS home_assistant_job_orchestration_worker_dispatch_rendering_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_model_provider_planning_scaffold.py
PASS home_assistant_job_orchestration_model_provider_planning_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_render_planning_scaffold.py
PASS home_assistant_job_orchestration_render_planning_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_artifact_storage_scaffold.py
PASS home_assistant_job_orchestration_artifact_storage_scaffold
```
