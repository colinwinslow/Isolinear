# Home Assistant Job Orchestration Render Planning Scaffold Evidence

Run timestamp: 2026-06-08T23:38:29+00:00

BDD file:
`bdd/integration/home-assistant-job-orchestration-render-planning-scaffold-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: scaffold-ready snapshot records a render plan -> `CASE scaffold_ready_snapshot_records_render_plan`
- Scenario B: repeated snapshot requests reuse the render plan -> `CASE repeated_snapshot_requests_reuse_render_plan`
- Scenario C: unknown job fails before render planning side effects -> `CASE unknown_job_fails_before_render_planning`
- Scenario D: config entries cannot retrieve each other's render plans -> `CASE cross_config_entry_render_plan_rejected`
- Scenario E: valid render plans stay config-entry scoped -> `CASE valid_render_plans_stay_config_entry_scoped`
- Scenario F: render plans and chart specs validate before storage -> `CASE render_plans_and_chart_specs_validate_before_storage`
- Scenario G: render planning scaffold remains bounded -> `CASE render_planning_remains_bounded`

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_render_planning_scaffold.py
```

Raw output excerpt:

```text
CASE scaffold_ready_snapshot_records_render_plan
  accepted.snapshot_dispatch.accepted = true
  accepted.artifact_snapshot.status = complete
  accepted.artifact_snapshot.snapshot_id = render-plan-entry-job-001-snapshot-004
  accepted.render_plan.render_plan_id = render-plan-entry-render-plan-001
  accepted.render_plan.job_id = render-plan-entry-job-001
  accepted.render_plan.source_snapshot_id = render-plan-entry-job-001-snapshot-003
  accepted.render_plan.artifact_id = render-plan-entry-artifact-001
  accepted.render_plan.render_mode = safe
  accepted.render_plan.renderer = trusted_chart_spec
  accepted.render_plan.chart_spec.chart_id = render-plan-entry-render-plan-001-chart-spec
  accepted.render_plan.chart_spec.chart_type = time_series
  accepted.render_plan.chart_spec.series[0].source.entity_id = sensor.upstairs_temperature
  accepted.orchestration_store.render_plan_count = 1
  accepted.orchestration_store.artifact_count = 1
  accepted.snapshot_dispatch.orchestration.render_plan_bookkeeping_written = true
  accepted.snapshot_dispatch.orchestration.artifact_metadata_bookkeeping_written = true
PASS scaffold_ready_snapshot_records_render_plan

CASE repeated_snapshot_requests_reuse_render_plan
  idempotent.first.accepted = true
  idempotent.second.accepted = true
  idempotent.same_snapshot_returned = true
  idempotent.same_render_plan_returned = true
  idempotent.render_plan_count = 1
  idempotent.artifact_count = 1
  idempotent.complete_snapshot_count = 1
  idempotent.first_render_plan.render_plan_id = render-plan-idempotent-entry-render-plan-001
PASS repeated_snapshot_requests_reuse_render_plan

CASE unknown_job_fails_before_render_planning
  unknown_job.error_codes = ["unknown_job"]
  unknown_job.render_plans = []
  unknown_job.artifacts = []
  unknown_job.snapshot.orchestration.render_plan_bookkeeping_written = false
  unknown_job.snapshot.orchestration.artifact_metadata_bookkeeping_written = false
PASS unknown_job_fails_before_render_planning

CASE cross_config_entry_render_plan_rejected
  cross_entry.error_codes = ["unknown_job"]
  cross_entry.entry_a_render_plans = []
  cross_entry.entry_b_render_plans = []
  cross_entry.entry_b_artifacts = []
  cross_entry.entry_b_complete_snapshots = []
  cross_entry.cross_snapshot.orchestration.render_plan_bookkeeping_written = false
PASS cross_config_entry_render_plan_rejected

CASE valid_render_plans_stay_config_entry_scoped
  isolation.entry_a.render_plans[0].render_plan_id = valid-render-plan-entry-a-render-plan-001
  isolation.entry_a.render_plans[0].job_id = valid-render-plan-entry-a-job-001
  isolation.entry_a.render_plans[0].chart_spec.chart_type = time_series
  isolation.entry_a.render_plans[0].chart_spec.series[0].source.entity_id = sensor.upstairs_temperature
  isolation.entry_b.render_plans[0].render_plan_id = valid-render-plan-entry-b-render-plan-001
  isolation.entry_b.render_plans[0].job_id = valid-render-plan-entry-b-job-001
  isolation.entry_b.render_plans[0].chart_spec.chart_type = timeline
  isolation.entry_b.render_plans[0].chart_spec.series[0].source.entity_id = binary_sensor.office_window
PASS valid_render_plans_stay_config_entry_scoped

CASE render_plans_and_chart_specs_validate_before_storage
  validation.accepted.render_plan_valid = true
  validation.accepted.chart_spec_valid = true
  validation.idempotent.render_plan_valid = true
  validation.idempotent.chart_spec_valid = true
  validation.isolation_entry_a.render_plan_valid = true
  validation.isolation_entry_a.chart_spec_valid = true
  validation.isolation_entry_b.render_plan_valid = true
  validation.isolation_entry_b.chart_spec_valid = true
PASS render_plans_and_chart_specs_validate_before_storage

CASE render_planning_remains_bounded
  side_effects.allowed_aggregate.render_plan_bookkeeping_written = true
  side_effects.allowed_aggregate.artifact_metadata_bookkeeping_written = true
  side_effects.allowed_aggregate.job_state_scaffold_written = true
  side_effects.allowed_aggregate.job_orchestration_scaffold_written = true
  side_effects.allowed_aggregate.websocket_command_registered = true
  side_effects.forbidden_aggregate.model_provider_called = false
  side_effects.forbidden_aggregate.worker_called = false
  side_effects.forbidden_aggregate.home_assistant_history_read = false
  side_effects.forbidden_aggregate.semantic_memory_called = false
  side_effects.forbidden_aggregate.home_assistant_service_or_state_mutation_called = false
  side_effects.forbidden_aggregate.token_generated = false
  side_effects.forbidden_aggregate.chart_artifact_written = false
  side_effects.forbidden_aggregate.chart_rendering_called = false
  side_effects.forbidden_aggregate.durable_storage_written = false
  side_effects.forbidden_aggregate.retry_behavior_called = false
  side_effects.forbidden_aggregate.subscription_progress_streaming_called = false
  side_effects.forbidden_aggregate.job_orchestration_called = false
PASS render_planning_remains_bounded
PASS home_assistant_job_orchestration_render_planning_scaffold
```

## Additional Verification

```text
.\.venv\Scripts\python.exe -m pytest tests/test_job_orchestration_render_planning_anchor.py
8 passed

.\.venv\Scripts\python.exe -m pytest tests/
159 passed

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_artifact_storage_scaffold.py
PASS home_assistant_job_orchestration_artifact_storage_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_subscription_progress_scaffold.py
PASS home_assistant_job_orchestration_subscription_progress_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_scaffold.py
PASS home_assistant_job_orchestration_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_retry_continuation_scaffold.py
PASS home_assistant_job_orchestration_retry_continuation_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_clarification_continuation_scaffold.py
PASS home_assistant_job_orchestration_clarification_continuation_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_state_scaffold.py
PASS home_assistant_job_state_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_websocket_command_registration.py
PASS home_assistant_websocket_command_registration
```
