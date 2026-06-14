# Home Assistant Model-Provider Retry/Backoff Policy Scaffold Evidence

Run timestamp: 2026-06-12T18:00:23+00:00

BDD file:
`bdd/integration/home-assistant-model-provider-retry-backoff-policy-scaffold-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: retry-safe provider failure records retry policy -> `CASE provider_failure_records_retry_policy`
- Scenario B: provider retry policies validate -> `CASE provider_retry_policy_contracts_validate`
- Scenario C: provider failure details stay internal and sanitized -> `CASE provider_retry_policy_failure_details_are_sanitized`
- Scenario D: malformed provider failure metadata fails before policy storage -> `CASE malformed_provider_failure_rejected_before_policy`
- Scenario E: unknown job fails before provider retry policy -> `CASE unknown_job_rejected_before_provider_retry_policy`
- Scenario F: cross-config-entry jobs fail before provider retry policy -> `CASE cross_config_entry_rejected_before_provider_retry_policy`
- Scenario G: valid provider retry policies stay config-entry scoped -> `CASE valid_provider_retry_policies_stay_config_entry_scoped`
- Scenario H: model-provider retry policy remains bounded -> `CASE model_provider_retry_policy_remains_bounded`

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_model_provider_retry_backoff_policy_scaffold.py
```

Raw output excerpt:

```text
CASE provider_failure_records_retry_policy
  accepted.card_snapshot.status = failed
  accepted.card_snapshot.retry_allowed = true
  accepted.card_snapshot.failure.stage = model_provider_planning
  accepted.card_snapshot.failure.code = model_provider_connection_error
  accepted.planner_call_count = 1
  accepted.model_provider_retry_policy.policy_id = provider-retry-entry-model-provider-retry-policy-001
  accepted.model_provider_retry_policy.type = isolinear_model_provider_retry_policy
  accepted.model_provider_retry_policy.job_id = provider-retry-entry-job-001
  accepted.model_provider_retry_policy.source_snapshot_id = provider-retry-entry-job-001-snapshot-003
  accepted.model_provider_retry_policy.decision.manual_retry_allowed = true
  accepted.model_provider_retry_policy.decision.automatic_retry_scheduled = false
  accepted.model_provider_retry_policy.backoff.delay_seconds = 5
  accepted.provider_plans = []
  accepted.render_plans = []
  accepted.artifacts = []
  accepted.complete_snapshots = []
PASS provider_failure_records_retry_policy

CASE provider_retry_policy_contracts_validate
  validation.accepted.model_provider_retry_policy_valid = true
  validation.isolation_entry_a.model_provider_retry_policy_valid = true
  validation.isolation_entry_b.model_provider_retry_policy_valid = true
PASS provider_retry_policy_contracts_validate

CASE provider_retry_policy_failure_details_are_sanitized
  sanitization.card_snapshot_excludes_provider_endpoint = true
  sanitization.card_snapshot_excludes_provider_model = true
  sanitization.card_snapshot_excludes_policy_id = true
  sanitization.card_snapshot_excludes_policy_type = true
  secret.error_codes = ["model_provider_failure_forbidden_material"]
  secret.model_provider_retry_policies = []
PASS provider_retry_policy_failure_details_are_sanitized

CASE malformed_provider_failure_rejected_before_policy
  malformed.error_codes = ["invalid_model_provider_failure"]
  malformed.model_provider_retry_policies = []
  malformed.provider_plans = []
  malformed.render_plans = []
  malformed.artifacts = []
  malformed.complete_snapshots = []
PASS malformed_provider_failure_rejected_before_policy

CASE unknown_job_rejected_before_provider_retry_policy
  unknown_job.error_codes = ["unknown_job"]
  unknown_job.planner_call_count = 0
  unknown_job.model_provider_retry_policies = []
PASS unknown_job_rejected_before_provider_retry_policy

CASE cross_config_entry_rejected_before_provider_retry_policy
  cross_entry.error_codes = ["unknown_job"]
  cross_entry.entry_a_planner_call_count = 0
  cross_entry.entry_b_planner_call_count = 0
  cross_entry.entry_b_model_provider_retry_policies = []
PASS cross_config_entry_rejected_before_provider_retry_policy

CASE valid_provider_retry_policies_stay_config_entry_scoped
  isolation.entry_a.model_provider_retry_policies[0].config_entry_id = provider-retry-isolation-entry-a
  isolation.entry_b.model_provider_retry_policies[0].config_entry_id = provider-retry-isolation-entry-b
PASS valid_provider_retry_policies_stay_config_entry_scoped

CASE model_provider_retry_policy_remains_bounded
  side_effects.allowed_aggregate.model_provider_called = true
  side_effects.allowed_aggregate.model_provider_retry_policy_bookkeeping_written = true
  side_effects.allowed_aggregate.job_state_scaffold_written = true
  side_effects.allowed_aggregate.job_orchestration_scaffold_written = true
  side_effects.allowed_aggregate.websocket_command_registered = true
  side_effects.forbidden_aggregate.model_provider_plan_bookkeeping_written = false
  side_effects.forbidden_aggregate.render_plan_bookkeeping_written = false
  side_effects.forbidden_aggregate.artifact_metadata_bookkeeping_written = false
  side_effects.forbidden_aggregate.worker_called = false
  side_effects.forbidden_aggregate.chart_rendering_called = false
  side_effects.forbidden_aggregate.durable_storage_written = false
  side_effects.forbidden_aggregate.retry_behavior_called = false
PASS model_provider_retry_policy_remains_bounded
PASS home_assistant_model_provider_retry_backoff_policy_scaffold
```

## Additional Verification

```text
.\.venv\Scripts\python.exe -m py_compile custom_components/isolinear/job_orchestration.py src/Isolinear/model_provider_retry_backoff_policy_anchor.py evals/home_assistant_model_provider_retry_backoff_policy_scaffold.py
PASS

.\.venv\Scripts\python.exe -m pytest tests/test_model_provider_retry_backoff_policy_anchor.py
10 passed

.\.venv\Scripts\python.exe evals/home_assistant_model_provider_retry_backoff_policy_scaffold.py
PASS home_assistant_model_provider_retry_backoff_policy_scaffold

.\.venv\Scripts\python.exe -m pytest tests/test_job_orchestration_model_provider_planning_anchor.py tests/test_worker_retry_backoff_policy_anchor.py tests/test_worker_transport_failure_classification_anchor.py
30 passed

.\.venv\Scripts\python.exe evals/home_assistant_job_orchestration_model_provider_planning_scaffold.py
PASS home_assistant_job_orchestration_model_provider_planning_scaffold

.\.venv\Scripts\python.exe evals/home_assistant_worker_retry_backoff_policy_scaffold.py
PASS home_assistant_worker_retry_backoff_policy_scaffold

git diff --check
PASS (no whitespace errors; normal CRLF warnings for touched Python files)

codex exec architecture review
OK - no invariant violations, scope/discipline flags, ADR requirement, or recommendations.
```

## On-Disk Verification

The implementing slice verifies these real artifacts on disk:

- `custom_components/isolinear/job_orchestration.py`
- `src/Isolinear/contracts.py`
- `docs/schemas/integration-model-provider-retry-policy.schema.json`
- `docs/specs/home-assistant-model-provider-retry-backoff-policy-scaffold-spec.md`
- `bdd/integration/home-assistant-model-provider-retry-backoff-policy-scaffold-bdd.md`
- `bdd/integration/home-assistant-model-provider-retry-backoff-policy-scaffold-evidence.md`
- `docs/evals/home_assistant_model_provider_retry_backoff_policy_scaffold.yaml`
- `src/Isolinear/model_provider_retry_backoff_policy_anchor.py`
- `tests/test_model_provider_retry_backoff_policy_anchor.py`
- `evals/home_assistant_model_provider_retry_backoff_policy_scaffold.py`
