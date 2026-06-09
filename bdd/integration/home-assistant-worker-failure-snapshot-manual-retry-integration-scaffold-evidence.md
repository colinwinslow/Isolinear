# Home Assistant Worker Failure Snapshot/Manual Retry Integration Scaffold Evidence

Run timestamp: 2026-06-09T23:03:12+00:00

BDD file:
`bdd/integration/home-assistant-worker-failure-snapshot-manual-retry-integration-scaffold-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: worker render failure returns failed snapshot -> `CASE worker_render_failure_returns_failed_snapshot`
- Scenario B: worker transport failure returns failed snapshot -> `CASE worker_transport_failure_returns_failed_snapshot`
- Scenario C: retryable worker failure resumes same job -> `CASE manual_retry_resumes_worker_failure_snapshot`
- Scenario D: non-retry-safe transport failure is not retryable -> `CASE non_retry_safe_transport_failure_rejects_manual_retry`
- Scenario E: failed snapshots and worker envelopes validate -> `CASE worker_failure_snapshot_contracts_validate`
- Scenario F: card-facing payload excludes worker internals -> `CASE card_payload_excludes_worker_internals`
- Scenario G: unknown job fails before worker failure snapshot -> `CASE unknown_job_rejected_before_worker_failure_snapshot`
- Scenario H: config entries cannot retry each other's worker failures -> `CASE cross_config_entry_rejected_before_worker_failure_snapshot`
- Scenario I: valid worker failure snapshots stay config-entry scoped -> `CASE valid_worker_failure_snapshots_stay_config_entry_scoped`
- Scenario J: worker failure snapshot/manual retry remains bounded -> `CASE worker_failure_snapshot_manual_retry_remains_bounded`

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_worker_failure_snapshot_manual_retry_integration_scaffold.py
```

Raw output excerpt:

```text
CASE worker_render_failure_returns_failed_snapshot
{
  "case_id": "worker_render_failure_returns_failed_snapshot",
  "then": {
    "artifact_count": 0,
    "card_snapshot": {
      "failure": {
        "code": "worker_safe_renderer_failed",
        "message": "Worker render failed before scaffold artifact metadata was accepted.",
        "stage": "worker_render"
      },
      "progress_stage": "worker_failure_snapshot_ready",
      "retry_allowed": true,
      "status": "failed"
    },
    "complete_snapshot_count": 0,
    "error_codes": [
      "worker_safe_renderer_failed"
    ],
    "render_plan_count": 0,
    "snapshot_accepted": true,
    "worker_call_count": 1,
    "worker_dispatch_count": 0,
    "worker_retry_policy_count": 1
  }
}
PASS worker_render_failure_returns_failed_snapshot

CASE worker_transport_failure_returns_failed_snapshot
{
  "case_id": "worker_transport_failure_returns_failed_snapshot",
  "then": {
    "artifact_count": 0,
    "card_snapshot": {
      "failure": {
        "code": "worker_connection_error",
        "message": "Fake worker transport failed before render result delivery.",
        "stage": "worker_transport"
      },
      "progress_stage": "worker_failure_snapshot_ready",
      "retry_allowed": true,
      "status": "failed"
    },
    "complete_snapshot_count": 0,
    "error_codes": [
      "worker_connection_error"
    ],
    "render_plan_count": 0,
    "snapshot_accepted": true,
    "transport_classification_count": 1,
    "worker_call_count": 1,
    "worker_dispatch_count": 0,
    "worker_retry_policy_count": 0
  }
}
PASS worker_transport_failure_returns_failed_snapshot

CASE manual_retry_resumes_worker_failure_snapshot
{
  "case_id": "manual_retry_resumes_worker_failure_snapshot",
  "then": {
    "failure_snapshot": {
      "failure": {
        "code": "worker_safe_renderer_failed",
        "stage": "worker_render"
      },
      "progress_stage": "worker_failure_snapshot_ready",
      "retry_allowed": true,
      "status": "failed"
    },
    "history_request_count_delta": 1,
    "job_progress_stages": [
      "job_state_scaffold",
      "approved_history_retrieval",
      "job_orchestration_scaffold_ready",
      "worker_failure_snapshot_ready",
      "job_orchestration_retry_accepted",
      "approved_history_retrieval",
      "job_orchestration_retry_continuation_ready"
    ],
    "retry_accepted": true,
    "retry_snapshot": {
      "progress_stage": "job_orchestration_retry_continuation_ready",
      "status": "planning"
    },
    "run_result_code": "retry_approved_history_ready",
    "same_job_id": true
  }
}
PASS manual_retry_resumes_worker_failure_snapshot

CASE non_retry_safe_transport_failure_rejects_manual_retry
{
  "case_id": "non_retry_safe_transport_failure_rejects_manual_retry",
  "then": {
    "classification_validation": [
      {
        "accepted": true,
        "delay_seconds": 0,
        "failure_code": "worker_response_error",
        "failure_family": "malformed_response",
        "retry_eligible": false
      }
    ],
    "failed_snapshot": {
      "failure": {
        "code": "worker_response_error",
        "stage": "worker_transport"
      },
      "progress_stage": "worker_failure_snapshot_ready",
      "retry_allowed": false,
      "status": "failed"
    },
    "history_request_count_delta": 0,
    "retry_accepted": false,
    "retry_error_codes": [
      "job_not_retryable"
    ],
    "snapshot_count_after_retry": 4,
    "snapshot_count_before_retry": 4
  }
}
PASS non_retry_safe_transport_failure_rejects_manual_retry

CASE worker_failure_snapshot_contracts_validate
{
  "case_id": "worker_failure_snapshot_contracts_validate",
  "then": {
    "validation": {
      "render_failure": {
        "failed_snapshot_valid": true,
        "worker_retry_policy_valid": true
      },
      "transport_failure": {
        "failed_snapshot_valid": true,
        "transport_classification_valid": true
      }
    }
  }
}
PASS worker_failure_snapshot_contracts_validate

CASE card_payload_excludes_worker_internals
{
  "case_id": "card_payload_excludes_worker_internals",
  "then": {
    "card_redaction": {
      "card_payloads_exclude_worker_internals": true,
      "internal_render_policy_authorization": "Bearer <redacted>",
      "internal_transport_classification_authorization": "Bearer <redacted>",
      "render_forbidden_hits": [],
      "transport_forbidden_hits": [],
      "worker_authorization_redacted_in_internal_metadata": true,
      "worker_token_absent_from_card_payloads": true
    }
  }
}
PASS card_payload_excludes_worker_internals

CASE unknown_job_rejected_before_worker_failure_snapshot
{
  "case_id": "unknown_job_rejected_before_worker_failure_snapshot",
  "then": {
    "error_codes": [
      "unknown_job"
    ],
    "snapshot_accepted": false,
    "transport_classification_count": 0,
    "worker_call_count": 0,
    "worker_dispatch_count": 0,
    "worker_retry_policy_count": 0
  }
}
PASS unknown_job_rejected_before_worker_failure_snapshot

CASE cross_config_entry_rejected_before_worker_failure_snapshot
{
  "case_id": "cross_config_entry_rejected_before_worker_failure_snapshot",
  "then": {
    "cross_retry_accepted": false,
    "cross_snapshot_accepted": false,
    "entry_a_worker_call_count": 0,
    "entry_b_failed_snapshot_count": 0,
    "entry_b_transport_classification_count": 0,
    "entry_b_worker_call_count": 0,
    "entry_b_worker_retry_policy_count": 0,
    "error_codes": [
      "unknown_job",
      "unknown_job"
    ]
  }
}
PASS cross_config_entry_rejected_before_worker_failure_snapshot

CASE valid_worker_failure_snapshots_stay_config_entry_scoped
{
  "case_id": "valid_worker_failure_snapshots_stay_config_entry_scoped",
  "then": {
    "entry_a": {
      "failed_snapshots": [
        {
          "failure": {
            "code": "entry_a_worker_failed",
            "stage": "worker_render"
          },
          "retry_allowed": true,
          "status": "failed"
        }
      ],
      "snapshot_accepted": true,
      "transport_classification_count": 0,
      "worker_call_count": 1,
      "worker_retry_policy_count": 1
    },
    "entry_b": {
      "failed_snapshots": [
        {
          "failure": {
            "code": "worker_http_error",
            "stage": "worker_transport"
          },
          "retry_allowed": true,
          "status": "failed"
        }
      ],
      "snapshot_accepted": true,
      "transport_classification_count": 1,
      "worker_call_count": 1,
      "worker_retry_policy_count": 0
    }
  }
}
PASS valid_worker_failure_snapshots_stay_config_entry_scoped

CASE worker_failure_snapshot_manual_retry_remains_bounded
{
  "case_id": "worker_failure_snapshot_manual_retry_remains_bounded",
  "then": {
    "allowed_aggregate": {
      "chart_rendering_called": true,
      "home_assistant_history_read_for_manual_retry": true,
      "job_orchestration_scaffold_written": true,
      "job_state_scaffold_written": true,
      "retry_behavior_called_for_manual_retry": true,
      "websocket_command_registered": true,
      "worker_called": true,
      "worker_retry_policy_bookkeeping_written": true,
      "worker_transport_failure_classification_bookkeeping_written": true
    },
    "card_payloads_exclude_worker_internals": true,
    "forbidden_aggregate": {
      "artifact_metadata_bookkeeping_written": false,
      "automatic_progress_task_called": false,
      "chart_artifact_written": false,
      "durable_retry_storage_written": false,
      "home_assistant_history_read": false,
      "home_assistant_service_or_state_mutation_called": false,
      "new_worker_transport_added": false,
      "retry_behavior_called": false,
      "semantic_memory_called": false,
      "token_generated": false,
      "token_leaked_to_card": false,
      "token_leaked_to_model_provider": false,
      "token_rotation_called": false,
      "worker_dispatch_bookkeeping_written": false,
      "worker_health_check_called": false,
      "worker_metadata_exposed_to_card": false
    },
    "worker_token_absent_from_card_payloads": true
  }
}
PASS worker_failure_snapshot_manual_retry_remains_bounded
PASS home_assistant_worker_failure_snapshot_manual_retry_integration_scaffold
```
