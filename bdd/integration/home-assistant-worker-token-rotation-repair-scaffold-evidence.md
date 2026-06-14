# Home Assistant Worker Token Rotation/Repair Scaffold Evidence

Run timestamp: 2026-06-10T20:44:22+00:00

BDD file:
`bdd/integration/home-assistant-worker-token-rotation-repair-scaffold-bdd.md`

Overall result: PASS for worker token rotation/repair BDD scenarios.

Full-suite note: the packet-specific and adjacent worker regression tests are
green. A full `tests\` run exposed an unrelated codegen sandbox timeout/code
flap; details are recorded below rather than hidden.

## Scenario Mapping

- Scenario A: rotation invalidates old token and refreshes readiness -> `CASE rotation_invalidates_old_token_and_refreshes_readiness`
- Scenario B: missing token is repaired explicitly -> `CASE missing_token_repair_records_ready_state`
- Scenario C: readiness validation failure rolls back rotation -> `CASE readiness_validation_failure_rolls_back_rotation`
- Scenario D: unknown config entry fails before side effects -> `CASE unknown_config_entry_rejected_before_side_effects`
- Scenario E: cross-entry requests fail before side effects -> `CASE cross_entry_request_rejected_before_side_effects`
- Scenario F: rotated and repaired tokens do not leak -> `CASE rotated_and_repaired_tokens_do_not_leak`
- Scenario G: rotation and repair remain bounded -> `CASE worker_token_rotation_repair_remains_bounded`

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_worker_token_rotation_repair_scaffold.py
```

Raw output excerpt:

```text
CASE rotation_invalidates_old_token_and_refreshes_readiness
  rotation.rotation.accepted = true
  rotation.rotation.code = worker_token_rotated
  rotation.rotation.old_token_invalidated = true
  rotation.readiness.status = ready
  rotation.readiness.code = worker_token_rotated
  rotation.readiness.token.authorization = Bearer <redacted>
  rotation.readiness_validation.accepted = true
  rotation.renderer_client_refreshed = true
  rotation.renderer_client_uses_new_token = true
  rotation.renderer_setup.enabled = true
  rotation.rotation.orchestration.worker_called = false
  rotation.rotation.orchestration.worker_health_check_called = false
PASS rotation_invalidates_old_token_and_refreshes_readiness

CASE missing_token_repair_records_ready_state
  repair.initial_readiness.status = not_ready
  repair.repair.accepted = true
  repair.repair.code = worker_token_repaired
  repair.readiness.status = ready
  repair.readiness.token.authorization = Bearer <redacted>
  repair.readiness_validation.accepted = true
  repair.renderer_setup.enabled = true
  repair.renderer_client_uses_repaired_token = true
PASS missing_token_repair_records_ready_state

CASE readiness_validation_failure_rolls_back_rotation
  rollback.rotation.accepted = false
  rollback.rotation.code = invalid_integration_worker_readiness
  rollback.token_factory_call_count = 1
  rollback.stored_token_restored = true
  rollback.rotated_token_absent_after_failure = true
  rollback.old_renderer_client_restored = true
  rollback.stored_readiness_after_failure = rollback.stored_readiness_before_failure
  rollback.stored_renderer_setup_after_failure = rollback.stored_renderer_setup_before_failure
PASS readiness_validation_failure_rolls_back_rotation

CASE unknown_config_entry_rejected_before_side_effects
  unknown.rotation.accepted = false
  unknown.rotation.code = unknown_config_entry
  unknown.repair.accepted = false
  unknown.repair.code = unknown_config_entry
  unknown.rotation_token_factory_call_count = 0
  unknown.repair_token_factory_call_count = 0
  unknown.entry_created = false
  unknown.readiness_written = false
PASS unknown_config_entry_rejected_before_side_effects

CASE cross_entry_request_rejected_before_side_effects
  cross_entry.rotation.accepted = false
  cross_entry.rotation.code = cross_config_entry_worker_token_request
  cross_entry.token_factory_call_count = 0
  cross_entry.entry_a_token_unchanged = true
  cross_entry.entry_b_token_unchanged = true
  cross_entry.entry_a_readiness = cross_entry.entry_a_readiness_before
  cross_entry.entry_b_readiness = cross_entry.entry_b_readiness_before
PASS cross_entry_request_rejected_before_side_effects

CASE rotated_and_repaired_tokens_do_not_leak
  leakage.rotation_authorization = Bearer <redacted>
  leakage.repair_authorization = Bearer <redacted>
  leakage.tokens_absent_from_readiness = true
  leakage.tokens_absent_from_setup = true
  leakage.tokens_absent_from_dashboard_card_metadata = true
  leakage.tokens_absent_from_model_provider_metadata = true
  leakage.tokens_absent_from_evidence_payload = true
  leakage.rotation_internals_absent_from_dashboard_payload = true
  leakage.repair_internals_absent_from_dashboard_payload = true
PASS rotated_and_repaired_tokens_do_not_leak

CASE worker_token_rotation_repair_remains_bounded
  side_effects.allowed_aggregate.token_generated = true
  side_effects.allowed_aggregate.token_stored = true
  side_effects.allowed_aggregate.token_rotation_called = true
  side_effects.allowed_aggregate.readiness_bookkeeping_written = true
  side_effects.allowed_aggregate.worker_renderer_setup_gated = true
  side_effects.forbidden_aggregate.home_assistant_history_read = false
  side_effects.forbidden_aggregate.semantic_memory_called = false
  side_effects.forbidden_aggregate.home_assistant_service_or_state_mutation_called = false
  side_effects.forbidden_aggregate.worker_called = false
  side_effects.forbidden_aggregate.worker_health_check_called = false
  side_effects.forbidden_aggregate.chart_rendering_called = false
  side_effects.forbidden_aggregate.chart_artifact_written = false
  side_effects.forbidden_aggregate.durable_token_storage_written = false
  side_effects.forbidden_aggregate.retry_behavior_called = false
  side_effects.forbidden_aggregate.automatic_progress_task_called = false
PASS worker_token_rotation_repair_remains_bounded
PASS home_assistant_worker_token_rotation_repair_scaffold
```

Token scan:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_worker_token_rotation_repair_scaffold.py | Select-String -Pattern "test-worker-readiness-token"
```

Raw output:

```text
```

## Additional Verification

```text
.\.venv\Scripts\python.exe -m pytest tests/test_worker_token_rotation_repair_anchor.py
8 passed

.\.venv\Scripts\python.exe -m pytest tests/test_worker_token_rotation_repair_anchor.py tests/test_worker_token_provisioning_readiness_anchor.py tests/test_worker_health_readiness_endpoint_anchor.py tests/test_job_orchestration_worker_dispatch_rendering_anchor.py tests/test_worker_progress_streaming_anchor.py tests/test_worker_retry_backoff_policy_anchor.py tests/test_worker_transport_failure_classification_anchor.py tests/test_worker_failure_snapshot_manual_retry_anchor.py
81 passed

.\.venv\Scripts\python.exe evals\home_assistant_worker_token_rotation_repair_scaffold.py
PASS home_assistant_worker_token_rotation_repair_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_worker_token_provisioning_readiness_scaffold.py
PASS home_assistant_worker_token_provisioning_readiness_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_worker_health_readiness_endpoint_scaffold.py
PASS home_assistant_worker_health_readiness_endpoint_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_worker_dispatch_rendering_scaffold.py
PASS home_assistant_job_orchestration_worker_dispatch_rendering_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_worker_progress_streaming_scaffold.py
PASS home_assistant_worker_progress_streaming_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_worker_retry_backoff_policy_scaffold.py
PASS home_assistant_worker_retry_backoff_policy_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_worker_transport_failure_retry_classification_scaffold.py
PASS home_assistant_worker_transport_failure_retry_classification_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_worker_failure_snapshot_manual_retry_integration_scaffold.py
PASS home_assistant_worker_failure_snapshot_manual_retry_integration_scaffold

.\.venv\Scripts\python.exe -m pytest tests\
249 passed, 2 failed
Failures were in tests/test_codegen_sandbox_anchor.py:
- test_allowlisted_matplotlib_pyplot_cannot_read_arbitrary_files expected runtime_error but observed timeout.
- test_codegen_sandbox_anchor_verification_passes reported "Allowlisted matplotlib file read failed with the wrong code."

.\.venv\Scripts\python.exe -m pytest tests/test_codegen_sandbox_anchor.py
9 passed, 1 failed
Failure was in test_allowlisted_matplotlib_pyplot_code_renders_png_in_sandbox because the sandbox result had image_path = None.

.\.venv\Scripts\python.exe -m pytest tests/test_codegen_sandbox_anchor.py
9 passed, 1 failed
Failure was in test_codegen_sandbox_anchor_verification_passes with "Allowlisted matplotlib generated code did not complete successfully."
```

## Review Passes

Architecture review:

```text
## Verdict
OK

## Invariant violations
None.

The diff stays inside the integration-owned worker token/readiness boundary.
It does not add HA state/service/device mutation, worker render or health
calls, semantic-memory behavior, chart rendering, durable storage, queues,
schedulers, or new transports. Readiness metadata is still schema-validated
before storage and authorization is redacted.

## Scope / discipline flags
None.

The new spec is paired with BDD under `bdd/integration/...` rather than
inlining scenarios in the spec. The anchor artifact exists in the production
readiness module plus verifier/eval/tests. Evidence notes unrelated full-suite
sandbox failures, but this diff does not change sandbox behavior.

## ADR-relevance
No new ADR required. The change implements a bounded spec under existing
ADR-0001, ADR-0005, ADR-0008, ADR-0012, and ADR-0014. It does not introduce a
new external service, storage mechanism, framework, queue, scheduler, or
transport.

## Recommendations
None.
```

BDD-evidence review:

```text
## Verdict
OK

## Per-scenario findings
- Scenario A "rotation invalidates old token and refreshes readiness": PASS - evidence includes `CASE rotation_invalidates_old_token_and_refreshes_readiness`, old-token invalidation, ready readiness validation, renderer refresh, and no worker render/health calls.
- Scenario B "missing token is repaired explicitly": PASS - evidence includes `CASE missing_token_repair_records_ready_state`, initial `not_ready`, repair code, ready validation, and enabled renderer setup.
- Scenario C "readiness validation failure rolls back rotation": PASS - evidence includes `CASE readiness_validation_failure_rolls_back_rotation`, schema failure code, restored token, restored renderer client, and restored readiness/setup state.
- Scenario D "unknown config entry fails before side effects": PASS - evidence includes `CASE unknown_config_entry_rejected_before_side_effects`, both rotation and repair rejecting as `unknown_config_entry`, zero token-factory calls, and no entry/readiness writes.
- Scenario E "cross-entry requests fail before side effects": PASS - evidence includes `CASE cross_entry_request_rejected_before_side_effects`, cross-entry rejection code, zero token-factory calls, unchanged tokens, and unchanged readiness for both entries.
- Scenario F "rotated and repaired tokens do not leak": PASS - evidence includes `CASE rotated_and_repaired_tokens_do_not_leak`, redacted authorization, token absence from readiness/setup/dashboard/model/evidence payloads, and no rotation/repair internals in dashboard payloads.
- Scenario G "rotation and repair remain bounded": PASS - evidence includes `CASE worker_token_rotation_repair_remains_bounded`, expected allowed bookkeeping/gating side effects, and forbidden side effects all false.

## Drift / hygiene flags
None for the BDD scenarios. The evidence explicitly records an unrelated
codegen sandbox full-suite failure instead of claiming full-suite success.

## Recommendations
None.
```
