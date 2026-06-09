# Home Assistant Worker Token Provisioning/Readiness Scaffold Evidence

Run timestamp: 2026-06-09T17:58:47+00:00

BDD file:
`bdd/integration/home-assistant-worker-token-provisioning-readiness-scaffold-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: explicit token provisioning records ready state -> `CASE explicit_token_provisioning_records_ready_state`
- Scenario B: no token leaves worker not ready -> `CASE no_token_setup_reports_not_ready`
- Scenario C: missing worker endpoint is disabled -> `CASE missing_worker_endpoint_reports_disabled`
- Scenario D: repeated provisioning reuses token -> `CASE repeated_provisioning_reuses_token`
- Scenario E: unknown config entry fails before token generation -> `CASE unknown_config_entry_rejected_before_token_generation`
- Scenario F: readiness validation failure rolls back token -> `CASE readiness_validation_failure_rolls_back_token`
- Scenario G: readiness and tokens stay config-entry scoped -> `CASE readiness_and_tokens_stay_config_entry_scoped`
- Scenario H: worker token does not leak -> `CASE worker_token_does_not_leak`
- Scenario I: readiness remains bounded -> `CASE worker_readiness_remains_bounded`

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_worker_token_provisioning_readiness_scaffold.py
```

Raw output excerpt:

```text
CASE explicit_token_provisioning_records_ready_state
  accepted.initial_readiness.status = not_ready
  accepted.initial_readiness.token.authorization = <missing>
  accepted.provision.accepted = true
  accepted.provision.code = worker_token_provisioned
  accepted.provision.enabled = true
  accepted.readiness.status = ready
  accepted.readiness.token.present = true
  accepted.readiness.token.authorization = Bearer <redacted>
  accepted.readiness_validation.accepted = true
  accepted.renderer_setup.enabled = true
  accepted.renderer_client_present = true
  accepted.raw_token_stored = true
  accepted.token_factory_call_count = 1
PASS explicit_token_provisioning_records_ready_state

CASE no_token_setup_reports_not_ready
  no_token.setup.accepted = true
  no_token.readiness.status = not_ready
  no_token.readiness.token.present = false
  no_token.readiness.token.authorization = <missing>
  no_token.readiness_validation.accepted = true
  no_token.renderer_setup.enabled = false
  no_token.renderer_client_present = false
PASS no_token_setup_reports_not_ready

CASE missing_worker_endpoint_reports_disabled
  disabled.setup.accepted = true
  disabled.readiness.status = disabled
  disabled.readiness.worker.endpoint_configured = false
  disabled.readiness.token.present = false
  disabled.readiness_validation.accepted = true
  disabled.renderer_setup.enabled = false
  disabled.renderer_client_present = false
PASS missing_worker_endpoint_reports_disabled

CASE repeated_provisioning_reuses_token
  repeated.first.accepted = true
  repeated.first.code = worker_token_provisioned
  repeated.second.accepted = true
  repeated.second.code = worker_token_already_present
  repeated.token_factory_call_count = 1
  repeated.stored_token_unchanged = true
  repeated.second_readiness.status = ready
  repeated.second_readiness_validation.accepted = true
PASS repeated_provisioning_reuses_token

CASE unknown_config_entry_rejected_before_token_generation
  unknown.provision.accepted = false
  unknown.provision.code = unknown_config_entry
  unknown.token_factory_call_count = 0
  unknown.entry_created = false
  unknown.readiness_written = false
  unknown.provision.orchestration.token_generated = false
  unknown.provision.orchestration.readiness_bookkeeping_written = false
PASS unknown_config_entry_rejected_before_token_generation

CASE readiness_validation_failure_rolls_back_token
  validation_failure.provision.accepted = false
  validation_failure.provision.code = invalid_integration_worker_readiness
  validation_failure.token_factory_call_count = 1
  validation_failure.token_present_after_failure = false
  validation_failure.readiness_written_after_failure = false
  validation_failure.stored_readiness.status = not_ready
  validation_failure.provision.orchestration.token_generated = true
  validation_failure.provision.orchestration.token_stored = false
  validation_failure.provision.orchestration.readiness_bookkeeping_written = false
PASS readiness_validation_failure_rolls_back_token

CASE readiness_and_tokens_stay_config_entry_scoped
  isolation.entry_a.provision.accepted = true
  isolation.entry_a.readiness.status = ready
  isolation.entry_a.renderer_setup.enabled = true
  isolation.entry_a.token_present = true
  isolation.entry_b.readiness.status = not_ready
  isolation.entry_b.renderer_setup.enabled = false
  isolation.entry_b.token_present = false
  isolation.entry_a.readiness.config_entry_id = worker-ready-entry-a
  isolation.entry_b.readiness.config_entry_id = worker-ready-entry-b
  isolation.entry_a.readiness_validation.accepted = true
  isolation.entry_b.readiness_validation.accepted = true
PASS readiness_and_tokens_stay_config_entry_scoped

CASE worker_token_does_not_leak
  leakage.token_absent_from_readiness = true
  leakage.token_absent_from_setup = true
  leakage.token_absent_from_dashboard_card_metadata = true
  leakage.token_absent_from_model_provider_metadata = true
  leakage.token_absent_from_evidence_payload = true
  leakage.stored_authorization = Bearer <redacted>
PASS worker_token_does_not_leak

CASE worker_readiness_remains_bounded
  side_effects.allowed_aggregate.token_generated = true
  side_effects.allowed_aggregate.token_stored = true
  side_effects.allowed_aggregate.readiness_bookkeeping_written = true
  side_effects.allowed_aggregate.worker_renderer_setup_gated = true
  side_effects.forbidden_aggregate.home_assistant_history_read = false
  side_effects.forbidden_aggregate.semantic_memory_called = false
  side_effects.forbidden_aggregate.home_assistant_service_or_state_mutation_called = false
  side_effects.forbidden_aggregate.worker_called = false
  side_effects.forbidden_aggregate.chart_rendering_called = false
  side_effects.forbidden_aggregate.chart_artifact_written = false
  side_effects.forbidden_aggregate.durable_token_storage_written = false
  side_effects.forbidden_aggregate.token_rotation_called = false
  side_effects.forbidden_aggregate.worker_health_check_called = false
  side_effects.forbidden_aggregate.retry_behavior_called = false
  side_effects.forbidden_aggregate.automatic_progress_task_called = false
  side_effects.forbidden_aggregate.worker_streaming_called = false
PASS worker_readiness_remains_bounded
PASS home_assistant_worker_token_provisioning_readiness_scaffold
```

## Additional Verification

```text
.\.venv\Scripts\python.exe -m pytest tests/test_worker_token_provisioning_readiness_anchor.py
10 passed

.\.venv\Scripts\python.exe -m pytest tests/test_job_orchestration_worker_dispatch_rendering_anchor.py
10 passed

.\.venv\Scripts\python.exe -m pytest tests/test_job_orchestration_model_provider_planning_anchor.py tests/test_job_orchestration_render_planning_anchor.py tests/test_job_orchestration_artifact_storage_anchor.py
27 passed

.\.venv\Scripts\python.exe -m pytest tests\
190 passed

.\.venv\Scripts\python.exe evals\home_assistant_worker_token_provisioning_readiness_scaffold.py
PASS home_assistant_worker_token_provisioning_readiness_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_worker_dispatch_rendering_scaffold.py
PASS home_assistant_job_orchestration_worker_dispatch_rendering_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_model_provider_planning_scaffold.py
PASS home_assistant_job_orchestration_model_provider_planning_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_render_planning_scaffold.py
PASS home_assistant_job_orchestration_render_planning_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_artifact_storage_scaffold.py
PASS home_assistant_job_orchestration_artifact_storage_scaffold
```
