# Home Assistant Durable Worker Token Lifecycle Scaffold Evidence

Run timestamp: 2026-06-13T01:18:56+00:00

BDD file:
`bdd/integration/home-assistant-durable-worker-token-lifecycle-scaffold-bdd.md`

Overall result: PASS for durable worker token lifecycle BDD scenarios.

Scope note: this packet implements durable token persistence and automatic
restore from a valid persisted token. It records redacted repair issue metadata
when restore is impossible, but it does not register a real Home Assistant
Repairs flow, add dashboard-card token commands, execute health-polling repair
recommendations, or generate a worker token during setup.

## Scenario Mapping

- Scenario A: setup restores a persisted worker token before readiness -> `CASE setup_restores_persisted_token_before_readiness`
- Scenario B: missing persisted token records redacted issue metadata -> `CASE missing_persisted_token_records_repair_issue`
- Scenario C: missing worker endpoint records disabled lifecycle state -> `CASE missing_worker_endpoint_records_disabled_lifecycle`
- Scenario D: durable wrappers persist successful token operations -> `CASE durable_explicit_operations_persist_private_tokens`
- Scenario E: invalid persisted entries are skipped before restore -> `CASE invalid_persisted_entries_skipped_before_restore`
- Scenario F: setup lifecycle storage failure blocks restore -> `CASE setup_lifecycle_storage_failure_blocks_restore`
- Scenario G: lifecycle validation/storage failure rolls back -> `CASE lifecycle_validation_failure_rolls_back`
- Scenario H: lifecycle state stays config-entry scoped -> `CASE worker_token_lifecycle_stays_config_entry_scoped`
- Scenario I: lifecycle and repair issue details do not leak -> `CASE worker_token_lifecycle_details_do_not_leak`
- Scenario J: durable token lifecycle remains bounded -> `CASE worker_token_lifecycle_remains_bounded`

## Red Test

Raw command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_worker_token_lifecycle_anchor.py
```

Raw output excerpt before production module existed:

```text
E   ModuleNotFoundError: No module named 'custom_components.isolinear.worker_token_lifecycle'
ERROR tests/test_worker_token_lifecycle_anchor.py
```

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_durable_worker_token_lifecycle_scaffold.py
```

Raw output excerpt:

```text
CASE setup_restores_persisted_token_before_readiness
  restore.lifecycle.status = ready
  restore.lifecycle.code = worker_token_restored_from_storage
  restore.lifecycle.token.authorization = Bearer <redacted>
  restore.lifecycle.token.persisted = true
  restore.lifecycle.token.restored = true
  restore.lifecycle.orchestration.automatic_token_restore_called = true
  restore.lifecycle.orchestration.setup_time_token_generation_called = false
  restore.lifecycle.orchestration.worker_render_called = false
  restore.lifecycle.orchestration.worker_health_call = false
  restore.lifecycle_validation.accepted = true
  restore.stored_token_restored_to_memory = true
  restore.readiness.status = ready
  restore.renderer_setup.enabled = true
  restore.renderer_client_uses_restored_token = true
PASS setup_restores_persisted_token_before_readiness

CASE missing_persisted_token_records_repair_issue
  repair_issue.lifecycle.status = not_ready
  repair_issue.lifecycle.code = worker_token_repair_issue_created
  repair_issue.lifecycle.token.authorization = <missing>
  repair_issue.repair_issue.present = true
  repair_issue.repair_issue.surface = home_assistant_repairs_scaffold
  repair_issue.repair_issue.suggested_action = manual_token_repair
  repair_issue.token_present = false
  repair_issue.lifecycle.orchestration.token_generated = false
PASS missing_persisted_token_records_repair_issue

CASE missing_worker_endpoint_records_disabled_lifecycle
  disabled.lifecycle.status = disabled
  disabled.lifecycle.code = worker_endpoint_missing
  disabled.repair_issue.present = false
  disabled.token_present = false
PASS missing_worker_endpoint_records_disabled_lifecycle

CASE durable_explicit_operations_persist_private_tokens
  explicit.provision.accepted = true
  explicit.rotation.accepted = true
  explicit.repair.accepted = true
  explicit.private_provision_token_persisted = true
  explicit.private_repair_token_persisted = true
  explicit.rotation_replaced_private_token = true
  explicit.provision_lifecycle.token.authorization = Bearer <redacted>
  explicit.repair_lifecycle.token.authorization = Bearer <redacted>
  explicit.repair_issue_cleared_after_success = true
PASS durable_explicit_operations_persist_private_tokens

CASE invalid_persisted_entries_skipped_before_restore
  invalid.token_restored = false
  invalid.readiness.status = not_ready
  invalid.repair_issue.present = true
  invalid.lifecycle_validation.accepted = true
PASS invalid_persisted_entries_skipped_before_restore

CASE setup_lifecycle_storage_failure_blocks_restore
  setup_failure.setup_accepted = false
  setup_failure.lifecycle_setup.accepted = false
  setup_failure.lifecycle_setup.code = invalid_integration_worker_token_lifecycle
  setup_failure.token_restored = false
  setup_failure.readiness_written = false
  setup_failure.renderer_setup_written = false
  setup_failure.private_token_retained = true
PASS setup_lifecycle_storage_failure_blocks_restore

CASE lifecycle_validation_failure_rolls_back
  rollback.rotation.accepted = false
  rollback.rotation.code = invalid_integration_worker_token_lifecycle
  rollback.token_factory_call_count = 1
  rollback.private_token_restored = true
  rollback.rotated_token_absent_from_private_store = true
  rollback.in_memory_token_restored = true
  rollback.old_renderer_client_restored = true
  rollback.lifecycle_after_failure = rollback.lifecycle_before_failure
  rollback.readiness_after_failure = rollback.readiness_before_failure
  rollback.renderer_setup_after_failure = rollback.renderer_setup_before_failure
PASS lifecycle_validation_failure_rolls_back

CASE worker_token_lifecycle_stays_config_entry_scoped
  isolation.entry_a.private_token = true
  isolation.entry_a.renderer_client_uses_own_token = true
  isolation.entry_b.lifecycle = isolation.entry_b_before.lifecycle
  isolation.entry_b.readiness = isolation.entry_b_before.readiness
  isolation.entry_b.token_present = false
  isolation.entry_b.private_token = null
PASS worker_token_lifecycle_stays_config_entry_scoped

CASE worker_token_lifecycle_details_do_not_leak
  leakage.tokens_absent_from_lifecycle_state = true
  leakage.tokens_absent_from_setup_results = true
  leakage.tokens_absent_from_repair_issue_metadata = true
  leakage.tokens_absent_from_dashboard_card_metadata = true
  leakage.tokens_absent_from_model_provider_metadata = true
  leakage.tokens_absent_from_evidence_payload = true
  leakage.lifecycle_absent_from_dashboard_payload = true
  leakage.repair_issue_absent_from_dashboard_payload = true
  leakage.endpoint_absent_from_dashboard_payload = true
PASS worker_token_lifecycle_details_do_not_leak

CASE worker_token_lifecycle_remains_bounded
  side_effects.allowed_aggregate.durable_token_storage_loaded = true
  side_effects.allowed_aggregate.durable_token_storage_written = true
  side_effects.allowed_aggregate.in_memory_token_restored = true
  side_effects.allowed_aggregate.automatic_token_restore_called = true
  side_effects.allowed_aggregate.repair_issue_created = true
  side_effects.allowed_aggregate.repair_issue_deleted = true
  side_effects.forbidden_aggregate.home_assistant_history_read = false
  side_effects.forbidden_aggregate.semantic_memory_called = false
  side_effects.forbidden_aggregate.home_assistant_service_or_state_mutation_called = false
  side_effects.forbidden_aggregate.config_entry_options_written = false
  side_effects.forbidden_aggregate.recorder_called = false
  side_effects.forbidden_aggregate.worker_render_called = false
  side_effects.forbidden_aggregate.worker_health_call = false
  side_effects.forbidden_aggregate.model_provider_called = false
  side_effects.forbidden_aggregate.durable_retry_storage_written = false
  side_effects.forbidden_aggregate.scheduler_called = false
  side_effects.forbidden_aggregate.automatic_rotation_called = false
  side_effects.forbidden_aggregate.automatic_token_repair_execution_called = false
  side_effects.forbidden_aggregate.setup_time_token_generation_called = false
  side_effects.forbidden_aggregate.dashboard_command_registered = false
PASS worker_token_lifecycle_remains_bounded
PASS home_assistant_durable_worker_token_lifecycle_scaffold
```

## Focused Verification

```text
.\.venv\Scripts\python.exe -m pytest tests/test_worker_token_lifecycle_anchor.py
11 passed

.\.venv\Scripts\python.exe evals\home_assistant_durable_worker_token_lifecycle_scaffold.py
PASS home_assistant_durable_worker_token_lifecycle_scaffold

.\.venv\Scripts\python.exe -m pytest tests/test_worker_token_lifecycle_anchor.py tests/test_worker_token_provisioning_readiness_anchor.py tests/test_worker_token_rotation_repair_anchor.py tests/test_worker_health_readiness_endpoint_anchor.py tests/test_worker_health_polling_anchor.py tests/test_job_orchestration_worker_dispatch_rendering_anchor.py tests/test_worker_progress_streaming_anchor.py tests/test_worker_retry_backoff_policy_anchor.py tests/test_worker_transport_failure_classification_anchor.py tests/test_worker_failure_snapshot_manual_retry_anchor.py
109 passed

.\.venv\Scripts\python.exe evals\home_assistant_worker_token_provisioning_readiness_scaffold.py | Select-String -Pattern "PASS home_assistant_worker_token_provisioning_readiness_scaffold"
PASS home_assistant_worker_token_provisioning_readiness_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_worker_token_rotation_repair_scaffold.py | Select-String -Pattern "PASS home_assistant_worker_token_rotation_repair_scaffold"
PASS home_assistant_worker_token_rotation_repair_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_worker_health_readiness_endpoint_scaffold.py | Select-String -Pattern "PASS home_assistant_worker_health_readiness_endpoint_scaffold"
PASS home_assistant_worker_health_readiness_endpoint_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_durable_worker_health_polling_scaffold.py | Select-String -Pattern "PASS home_assistant_durable_worker_health_polling_scaffold"
PASS home_assistant_durable_worker_health_polling_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_worker_dispatch_rendering_scaffold.py | Select-String -Pattern "PASS home_assistant_job_orchestration_worker_dispatch_rendering_scaffold"
PASS home_assistant_job_orchestration_worker_dispatch_rendering_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_worker_progress_streaming_scaffold.py | Select-String -Pattern "PASS home_assistant_worker_progress_streaming_scaffold"
PASS home_assistant_worker_progress_streaming_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_worker_retry_backoff_policy_scaffold.py | Select-String -Pattern "PASS home_assistant_worker_retry_backoff_policy_scaffold"
PASS home_assistant_worker_retry_backoff_policy_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_worker_transport_failure_retry_classification_scaffold.py | Select-String -Pattern "PASS home_assistant_worker_transport_failure_retry_classification_scaffold"
PASS home_assistant_worker_transport_failure_retry_classification_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_worker_failure_snapshot_manual_retry_integration_scaffold.py | Select-String -Pattern "PASS home_assistant_worker_failure_snapshot_manual_retry_integration_scaffold"
PASS home_assistant_worker_failure_snapshot_manual_retry_integration_scaffold

.\.venv\Scripts\python.exe -m py_compile custom_components\isolinear\worker_token_lifecycle.py src\Isolinear\worker_token_lifecycle_anchor.py evals\home_assistant_durable_worker_token_lifecycle_scaffold.py
exit code 0

git diff --cached --check
exit code 0

.\.venv\Scripts\python.exe -m pytest tests\
298 passed, 1 failed
Failure: tests/test_codegen_sandbox_anchor.py::CodegenSandboxAnchorTests::test_allowlisted_matplotlib_pyplot_cannot_read_arbitrary_files returned timeout instead of runtime_error. This is the known unrelated codegen sandbox matplotlib subprocess flake documented in STATUS/HANDOFF.

.\.venv\Scripts\python.exe -m pytest tests/test_codegen_sandbox_anchor.py::CodegenSandboxAnchorTests::test_allowlisted_matplotlib_pyplot_cannot_read_arbitrary_files
1 passed
```
