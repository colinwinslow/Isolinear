# Home Assistant Worker Transport Failure Retry Classification Scaffold Evidence

Run timestamp: 2026-06-09T22:22:05+00:00

BDD file:
`bdd/integration/home-assistant-worker-transport-failure-retry-classification-scaffold-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: connection failure records retry classification -> `CASE worker_connection_failure_records_retry_classification`
- Scenario B: HTTP and malformed responses map deterministically -> `CASE worker_transport_failure_families_map_deterministically`
- Scenario C: transport classification contracts validate -> `CASE worker_transport_failure_classification_contracts_validate`
- Scenario D: worker authorization and failure text are redacted -> `CASE worker_transport_failure_classification_redacts_sensitive_material`
- Scenario E: unknown job fails before transport classification -> `CASE unknown_job_rejected_before_worker_transport_classification`
- Scenario F: config entries cannot classify each other's jobs -> `CASE cross_config_entry_rejected_before_worker_transport_classification`
- Scenario G: valid classifications stay config-entry scoped -> `CASE valid_worker_transport_classifications_stay_config_entry_scoped`
- Scenario H: transport classification remains bounded -> `CASE worker_transport_classification_remains_bounded`

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_worker_transport_failure_retry_classification_scaffold.py
```

Raw output excerpt:

```text
CASE worker_connection_failure_records_retry_classification
  "error_codes": [
    "worker_connection_error"
  ],
  "worker_transport_failure_classification_count": 1,
  "worker_transport_failure_classification_ids": [
    "worker-transport-entry-worker-transport-failure-001"
  ],
  "classification_id": "worker-transport-entry-worker-transport-failure-001",
  "type": "isolinear_worker_transport_failure_classification",
  "job_id": "worker-transport-entry-job-001",
  "source_snapshot_id": "worker-transport-entry-job-001-snapshot-003",
  "failure": {
    "code": "worker_connection_error",
    "message": "Fake worker transport failed before render result delivery.",
    "retry_safe": true,
    "stage": "worker_transport"
  },
  "classification": {
    "automatic_retry_scheduled": false,
    "family": "connection",
    "manual_retry_allowed": true,
    "reason": "worker_transport_connection_retry_safe",
    "retry_eligible": true
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
  "worker_retry_policy_count": 0,
  "render_plan_count": 0,
  "artifact_count": 0,
  "complete_snapshots": []
PASS worker_connection_failure_records_retry_classification

CASE worker_transport_failure_families_map_deterministically
  "connection": {
    "classification": {
      "family": "connection",
      "retry_eligible": true
    },
    "error_codes": [
      "worker_connection_error"
    ]
  },
  "http": {
    "classification": {
      "family": "http",
      "retry_eligible": true
    },
    "error_codes": [
      "worker_http_error"
    ]
  },
  "malformed_response": {
    "classification": {
      "family": "malformed_response",
      "retry_eligible": false
    },
    "error_codes": [
      "worker_response_error"
    ]
  }
PASS worker_transport_failure_families_map_deterministically

CASE worker_transport_failure_classification_contracts_validate
  "worker_transport_classification_valid": true,
  "worker_transport_valid": true,
  "render_request_valid": true,
  "families": {
    "connection": {
      "observed_family": "connection",
      "retry_eligible": true,
      "worker_transport_classification_valid": true
    },
    "http": {
      "observed_family": "http",
      "retry_eligible": true,
      "worker_transport_classification_valid": true
    },
    "malformed_response": {
      "observed_family": "malformed_response",
      "retry_eligible": false,
      "worker_transport_classification_valid": true
    }
  }
PASS worker_transport_failure_classification_contracts_validate

CASE worker_transport_failure_classification_redacts_sensitive_material
  "raw_worker_authorization_received": true,
  "stored_authorization": "Bearer <redacted>",
  "stored_request_authorization": "Bearer <redacted>",
  "stored_authorization_redacted": true,
  "worker_token_absent_from_evidence": true,
  "secret_failure_text": {
    "classification_failure_code": "worker_transport_failed",
    "classification_failure_message": "Worker transport failed before a render result was accepted.",
    "error_codes": [
      "worker_transport_failed"
    ],
    "worker_token_absent_from_result": true
  }
PASS worker_transport_failure_classification_redacts_sensitive_material

CASE unknown_job_rejected_before_worker_transport_classification
  "error_codes": [
    "unknown_job"
  ],
  "worker_call_count": 0,
  "classifications": [],
  "worker_dispatches": []
PASS unknown_job_rejected_before_worker_transport_classification

CASE cross_config_entry_rejected_before_worker_transport_classification
  "error_codes": [
    "unknown_job"
  ],
  "entry_a_worker_call_count": 0,
  "entry_b_worker_call_count": 0,
  "entry_b_classifications": [],
  "entry_b_worker_dispatches": [],
  "entry_b_render_plans": [],
  "entry_b_artifacts": [],
  "entry_b_complete_snapshots": []
PASS cross_config_entry_rejected_before_worker_transport_classification

CASE valid_worker_transport_classifications_stay_config_entry_scoped
  "classifications": [
    {
      "classification_id": "worker-transport-isolation-entry-a-worker-transport-failure-001",
      "config_entry_id": "worker-transport-isolation-entry-a",
      "job_id": "worker-transport-isolation-entry-a-job-001"
    }
  ],
  "classifications": [
    {
      "classification_id": "worker-transport-isolation-entry-b-worker-transport-failure-001",
      "config_entry_id": "worker-transport-isolation-entry-b",
      "job_id": "worker-transport-isolation-entry-b-job-001"
    }
  ]
PASS valid_worker_transport_classifications_stay_config_entry_scoped

CASE worker_transport_classification_remains_bounded
  "allowed_aggregate": {
    "chart_rendering_called": true,
    "websocket_command_registered": true,
    "worker_called": true,
    "worker_transport_failure_classification_bookkeeping_written": true
  },
  "forbidden_aggregate": {
    "artifact_metadata_bookkeeping_written": false,
    "automatic_progress_task_called": false,
    "chart_artifact_written": false,
    "durable_retry_storage_written": false,
    "durable_storage_written": false,
    "home_assistant_history_read": false,
    "home_assistant_service_or_state_mutation_called": false,
    "model_provider_called": false,
    "new_worker_transport_added": false,
    "render_plan_bookkeeping_written": false,
    "retry_behavior_called": false,
    "scheduler_called": false,
    "semantic_memory_called": false,
    "token_generated": false,
    "token_leaked_to_card": false,
    "token_leaked_to_model_provider": false,
    "token_rotation_called": false,
    "worker_dispatch_bookkeeping_written": false,
    "worker_health_check_called": false,
    "worker_progress_bookkeeping_written": false,
    "worker_progress_streaming_called": false,
    "worker_render_result_retry_policy_changed": false,
    "worker_retry_policy_bookkeeping_written": false
  }
PASS worker_transport_classification_remains_bounded
PASS home_assistant_worker_transport_failure_retry_classification_scaffold
```

## On-Disk Verification

The implementing slice verifies these real artifacts on disk:

- `custom_components/isolinear/job_orchestration.py`
- `docs/schemas/integration-worker-transport-failure-classification.schema.json`
- `docs/specs/home-assistant-worker-transport-failure-retry-classification-scaffold-spec.md`
- `bdd/integration/home-assistant-worker-transport-failure-retry-classification-scaffold-bdd.md`
- `bdd/integration/home-assistant-worker-transport-failure-retry-classification-scaffold-evidence.md`
- `docs/evals/home_assistant_worker_transport_failure_retry_classification_scaffold.yaml`
- `src/Isolinear/worker_transport_failure_classification_anchor.py`
- `tests/test_worker_transport_failure_classification_anchor.py`
- `evals/home_assistant_worker_transport_failure_retry_classification_scaffold.py`
