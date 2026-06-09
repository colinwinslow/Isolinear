# Home Assistant Worker Retry/Backoff Policy Scaffold Evidence

Run timestamp: 2026-06-09T21:30:17+00:00

BDD file:
`bdd/integration/home-assistant-worker-retry-backoff-policy-scaffold-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: worker render failure records retry/backoff policy -> `CASE worker_render_failure_records_retry_backoff_policy`
- Scenario B: retry/backoff policy contracts validate -> `CASE worker_retry_policy_contracts_validate`
- Scenario C: worker authorization is redacted -> `CASE worker_retry_policy_authorization_is_redacted`
- Scenario D: unknown job fails before retry/backoff policy -> `CASE unknown_job_rejected_before_worker_retry_policy`
- Scenario E: config entries cannot record policies for each other's jobs -> `CASE cross_config_entry_rejected_before_worker_retry_policy`
- Scenario F: valid retry/backoff policies stay config-entry scoped -> `CASE valid_worker_retry_policies_stay_config_entry_scoped`
- Scenario G: retry/backoff policy remains bounded -> `CASE worker_retry_policy_remains_bounded`

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_worker_retry_backoff_policy_scaffold.py
```

Raw output excerpt:

```text
CASE worker_render_failure_records_retry_backoff_policy
  "error_codes": [
    "worker_safe_renderer_failed"
  ],
  "worker_retry_policy_count": 1,
  "worker_retry_policy_ids": [
    "worker-retry-entry-worker-retry-policy-001"
  ],
  "policy_id": "worker-retry-entry-worker-retry-policy-001",
  "type": "isolinear_worker_retry_policy",
  "job_id": "worker-retry-entry-job-001",
  "source_snapshot_id": "worker-retry-entry-job-001-snapshot-003",
  "decision": {
    "automatic_retry_scheduled": false,
    "eligible": true,
    "manual_retry_allowed": true,
    "reason": "worker_failure_retry_safe"
  },
  "backoff": {
    "attempt_number": 1,
    "delay_seconds": 5,
    "jitter_applied": false,
    "max_delay_seconds": 60,
    "strategy": "bounded_exponential_scaffold"
  },
  "worker": {
    "api_version": 1,
    "authorization": "Bearer <redacted>",
    "endpoint_url": "http://worker.local:8765",
    "role": "renderer",
    "type": "http_json_worker"
  },
  "worker_dispatch_count": 0,
  "worker_progress_event_count": 0,
  "render_plan_count": 0,
  "artifact_count": 0,
  "complete_snapshots": []
PASS worker_render_failure_records_retry_backoff_policy

CASE worker_retry_policy_contracts_validate
  "worker_retry_policy_valid": true,
  "worker_transport_valid": true,
  "render_request_valid": true,
  "render_result_valid": true,
  "isolation_entry_a": {
    "worker_retry_policy_valid": true
  },
  "isolation_entry_b": {
    "worker_retry_policy_valid": true
  }
PASS worker_retry_policy_contracts_validate

CASE worker_retry_policy_authorization_is_redacted
  "raw_worker_authorization_received": true,
  "stored_authorization": "Bearer <redacted>",
  "stored_request_authorization": "Bearer <redacted>",
  "stored_authorization_redacted": true,
  "worker_token_absent_from_evidence": true,
  "secret_failure_code": {
    "error_codes": [
      "worker_render_failed"
    ],
    "policy_failure_code": "worker_render_failed",
    "worker_token_absent_from_result": true
  }
PASS worker_retry_policy_authorization_is_redacted

CASE unknown_job_rejected_before_worker_retry_policy
  "error_codes": [
    "unknown_job"
  ],
  "worker_call_count": 0,
  "worker_retry_policies": [],
  "worker_dispatches": []
PASS unknown_job_rejected_before_worker_retry_policy

CASE cross_config_entry_rejected_before_worker_retry_policy
  "error_codes": [
    "unknown_job"
  ],
  "entry_a_worker_call_count": 0,
  "entry_b_worker_call_count": 0,
  "entry_b_worker_retry_policies": [],
  "entry_b_worker_dispatches": [],
  "entry_b_render_plans": [],
  "entry_b_artifacts": [],
  "entry_b_complete_snapshots": []
PASS cross_config_entry_rejected_before_worker_retry_policy

CASE valid_worker_retry_policies_stay_config_entry_scoped
  "worker_retry_policies": [
    {
      "config_entry_id": "worker-retry-isolation-entry-a",
      "job_id": "worker-retry-isolation-entry-a-job-001",
      "policy_id": "worker-retry-isolation-entry-a-worker-retry-policy-001"
    }
  ],
  "worker_retry_policies": [
    {
      "config_entry_id": "worker-retry-isolation-entry-b",
      "job_id": "worker-retry-isolation-entry-b-job-001",
      "policy_id": "worker-retry-isolation-entry-b-worker-retry-policy-001"
    }
  ]
PASS valid_worker_retry_policies_stay_config_entry_scoped

CASE worker_retry_policy_remains_bounded
  "allowed_aggregate": {
    "chart_rendering_called": true,
    "websocket_command_registered": true,
    "worker_called": true,
    "worker_retry_policy_bookkeeping_written": true
  },
  "forbidden_aggregate": {
    "artifact_metadata_bookkeeping_written": false,
    "automatic_progress_task_called": false,
    "chart_artifact_written": false,
    "durable_storage_written": false,
    "home_assistant_history_read": false,
    "home_assistant_service_or_state_mutation_called": false,
    "model_provider_called": false,
    "render_plan_bookkeeping_written": false,
    "retry_behavior_called": false,
    "semantic_memory_called": false,
    "token_generated": false,
    "worker_dispatch_bookkeeping_written": false,
    "worker_progress_bookkeeping_written": false,
    "worker_progress_streaming_called": false
  }
PASS worker_retry_policy_remains_bounded
PASS home_assistant_worker_retry_backoff_policy_scaffold
```

## On-Disk Verification

The implementing slice verifies these real artifacts on disk:

- `custom_components/isolinear/job_orchestration.py`
- `docs/schemas/integration-worker-retry-policy.schema.json`
- `docs/specs/home-assistant-worker-retry-backoff-policy-scaffold-spec.md`
- `bdd/integration/home-assistant-worker-retry-backoff-policy-scaffold-bdd.md`
- `bdd/integration/home-assistant-worker-retry-backoff-policy-scaffold-evidence.md`
- `docs/evals/home_assistant_worker_retry_backoff_policy_scaffold.yaml`
- `src/Isolinear/worker_retry_backoff_policy_anchor.py`
- `tests/test_worker_retry_backoff_policy_anchor.py`
- `evals/home_assistant_worker_retry_backoff_policy_scaffold.py`
