# Home Assistant Job Orchestration Model-Provider Planning Scaffold Evidence

Run timestamp: 2026-06-09T00:50:48+00:00
Updated 2026-06-21: `CASE hidden_provider_entity_rejected_before_storage`
refreshed for the ADR-0023 structural entity gate — the broad textual scan was
removed, so the gate now rejects off-allowlist entities only in chart-spec
sources and `memory_proposals`, and entity-shaped tokens in free-text fields
render normally. Values captured from the current verifiers/eval.

BDD file:
`bdd/integration/home-assistant-job-orchestration-model-provider-planning-scaffold-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: provider-produced chart spec records provider plan and render plan -> `CASE provider_produced_chart_spec_records_provider_plan`
- Scenario B: repeated snapshot requests reuse provider plan -> `CASE repeated_snapshot_requests_reuse_provider_plan`
- Scenario C: hidden provider output entity fails before storage -> `CASE hidden_provider_entity_rejected_before_storage`
- Scenario D: invalid provider chart spec fails before storage -> `CASE invalid_provider_chart_spec_rejected_before_storage`
- Scenario E: unknown job fails before provider call -> `CASE unknown_job_rejected_before_provider_call`
- Scenario F: config entries cannot call providers for each other's jobs -> `CASE cross_config_entry_rejected_before_provider_call`
- Scenario G: valid provider plans stay config-entry scoped -> `CASE valid_provider_plans_stay_config_entry_scoped`
- Scenario H: provider plans, planner results, chart specs, and render plans validate -> `CASE provider_plans_and_chart_specs_validate_before_storage`
- Scenario I: model-provider planning remains bounded -> `CASE model_provider_planning_remains_bounded`

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_model_provider_planning_scaffold.py
```

Raw output excerpt:

```text
CASE provider_produced_chart_spec_records_provider_plan
  accepted.snapshot_dispatch.accepted = true
  accepted.planner_call_count = 1
  accepted.artifact_snapshot.status = complete
  accepted.artifact_snapshot.snapshot_id = model-provider-entry-job-001-snapshot-004
  accepted.provider_plan.provider_plan_id = model-provider-entry-provider-plan-001
  accepted.provider_plan.job_id = model-provider-entry-job-001
  accepted.provider_plan.source_snapshot_id = model-provider-entry-job-001-snapshot-003
  accepted.provider_plan.provider.type = ollama_compatible
  accepted.provider_plan.provider.role = planner
  accepted.provider_plan.status = chart_spec_ready
  accepted.provider_plan.request.prompt = Show sensor.upstairs_temperature
  accepted.provider_plan.request.approved_entity_ids = ["sensor.upstairs_temperature"]
  accepted.provider_plan.request.history_entity_ids = ["sensor.upstairs_temperature"]
  accepted.provider_plan.request.output_schema = PlannerResult
  accepted.render_plan.render_plan_id = model-provider-entry-render-plan-001
  accepted.render_plan.chart_spec.chart_id = provider-chart-001
  accepted.render_plan.chart_spec.title = Provider Upstairs Temperature
  accepted.render_plan.chart_spec.series[0].source.entity_id = sensor.upstairs_temperature
  accepted.snapshot_dispatch.orchestration.model_provider_called = true
  accepted.snapshot_dispatch.orchestration.model_provider_plan_bookkeeping_written = true
  accepted.snapshot_dispatch.orchestration.render_plan_bookkeeping_written = true
  accepted.snapshot_dispatch.orchestration.artifact_metadata_bookkeeping_written = true
PASS provider_produced_chart_spec_records_provider_plan

CASE repeated_snapshot_requests_reuse_provider_plan
  idempotent.first.accepted = true
  idempotent.second.accepted = true
  idempotent.planner_call_count = 1
  idempotent.same_snapshot_returned = true
  idempotent.same_provider_plan_returned = true
  idempotent.same_render_plan_returned = true
  idempotent.provider_plan_count = 1
  idempotent.render_plan_count = 1
  idempotent.artifact_count = 1
  idempotent.complete_snapshot_count = 1
PASS repeated_snapshot_requests_reuse_provider_plan

CASE hidden_provider_entity_rejected_before_storage
  hidden.error_codes = ["model_provider_referenced_unapproved_entity"]
  hidden.planner_call_count = 1
  hidden.provider_plans = []
  hidden.render_plans = []
  hidden.artifacts = []
  hidden.complete_snapshots = []
  hidden.snapshot.orchestration.model_provider_called = true
  hidden.snapshot.orchestration.model_provider_plan_bookkeeping_written = false
  hidden.snapshot.orchestration.render_plan_bookkeeping_written = false
  hidden.snapshot.orchestration.artifact_metadata_bookkeeping_written = false
  # Structural entity gate (ADR-0023): an off-allowlist entity in a persisted
  # memory_proposals reference still fails closed before any storage.
  hidden_memory.error_codes = ["model_provider_referenced_unapproved_entity"]
  hidden_memory.provider_plans = []
  hidden_memory.render_plans = []
  hidden_memory.artifacts = []
  hidden_memory.complete_snapshots = []
  # Entity-shaped tokens in inert free-text fields (here chart_id =
  # "sensor.upstairs_temperature_history" + a notes mention) are NOT entity
  # references; the chart renders end to end instead of being rejected.
  entity_named_chart_id.error_codes = []
  entity_named_chart_id.snapshot.status = "complete"
  entity_named_chart_id.provider_plans = 1
  entity_named_chart_id.complete_snapshots = 1
PASS hidden_provider_entity_rejected_before_storage

CASE invalid_provider_chart_spec_rejected_before_storage
  invalid.error_codes = ["invalid_model_provider_chart_spec"]
  invalid.planner_call_count = 1
  invalid.provider_plans = []
  invalid.render_plans = []
  invalid.artifacts = []
  invalid.complete_snapshots = []
PASS invalid_provider_chart_spec_rejected_before_storage

CASE unknown_job_rejected_before_provider_call
  unknown_job.error_codes = ["unknown_job"]
  unknown_job.planner_call_count = 0
  unknown_job.provider_plans = []
  unknown_job.render_plans = []
  unknown_job.artifacts = []
PASS unknown_job_rejected_before_provider_call

CASE cross_config_entry_rejected_before_provider_call
  cross_entry.error_codes = ["unknown_job"]
  cross_entry.entry_a_planner_call_count = 0
  cross_entry.entry_b_planner_call_count = 0
  cross_entry.entry_b_provider_plans = []
  cross_entry.entry_b_render_plans = []
  cross_entry.entry_b_artifacts = []
  cross_entry.entry_b_complete_snapshots = []
PASS cross_config_entry_rejected_before_provider_call

CASE valid_provider_plans_stay_config_entry_scoped
  isolation.entry_a.planner_call_count = 1
  isolation.entry_b.planner_call_count = 1
  isolation.entry_a.provider_plans[0].job_id = provider-isolation-entry-a-job-001
  isolation.entry_b.provider_plans[0].job_id = provider-isolation-entry-b-job-001
  isolation.entry_a.render_plans[0].chart_spec.series[0].source.entity_id = sensor.upstairs_temperature
  isolation.entry_b.render_plans[0].chart_spec.series[0].source.entity_id = binary_sensor.office_window
PASS valid_provider_plans_stay_config_entry_scoped

CASE provider_plans_and_chart_specs_validate_before_storage
  validation.accepted.provider_plan_valid = true
  validation.accepted.planner_result_valid = true
  validation.accepted.chart_spec_valid = true
  validation.accepted.render_plan_valid = true
  validation.idempotent.provider_plan_valid = true
  validation.idempotent.planner_result_valid = true
  validation.idempotent.chart_spec_valid = true
  validation.idempotent.render_plan_valid = true
  validation.isolation_entry_a.provider_plan_valid = true
  validation.isolation_entry_b.provider_plan_valid = true
PASS provider_plans_and_chart_specs_validate_before_storage

CASE model_provider_planning_remains_bounded
  side_effects.allowed_aggregate.model_provider_called = true
  side_effects.allowed_aggregate.model_provider_plan_bookkeeping_written = true
  side_effects.allowed_aggregate.render_plan_bookkeeping_written = true
  side_effects.allowed_aggregate.artifact_metadata_bookkeeping_written = true
  side_effects.allowed_aggregate.job_state_scaffold_written = true
  side_effects.allowed_aggregate.job_orchestration_scaffold_written = true
  side_effects.allowed_aggregate.websocket_command_registered = true
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
PASS model_provider_planning_remains_bounded
PASS home_assistant_job_orchestration_model_provider_planning_scaffold
```

## Additional Verification

```text
.\.venv\Scripts\python.exe -m pytest tests/test_job_orchestration_model_provider_planning_anchor.py
11 passed

.\.venv\Scripts\python.exe -m pytest tests/
170 passed

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_model_provider_planning_scaffold.py
PASS home_assistant_job_orchestration_model_provider_planning_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_render_planning_scaffold.py
PASS home_assistant_job_orchestration_render_planning_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_artifact_storage_scaffold.py
PASS home_assistant_job_orchestration_artifact_storage_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_scaffold.py
PASS home_assistant_job_orchestration_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_subscription_progress_scaffold.py
PASS home_assistant_job_orchestration_subscription_progress_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_retry_continuation_scaffold.py
PASS home_assistant_job_orchestration_retry_continuation_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_clarification_continuation_scaffold.py
PASS home_assistant_job_orchestration_clarification_continuation_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_websocket_command_registration.py
PASS home_assistant_websocket_command_registration
```
