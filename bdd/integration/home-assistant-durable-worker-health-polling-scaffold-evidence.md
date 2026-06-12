# Home Assistant Durable Worker Health Polling Scaffold Evidence

Run timestamp: 2026-06-12T16:21:00+00:00

BDD file:
`bdd/integration/home-assistant-durable-worker-health-polling-scaffold-bdd.md`

Overall result: PASS for durable worker health polling BDD scenarios.

Refactor note: the durable polling maintainability refactor preserved the BDD
scenario behavior and reran the packet-specific eval unchanged. Focused
polling tests (`17 passed`), adjacent worker regressions (`81 passed`), and
the focused durable polling eval are green. The full Python suite rerun hit the
known unrelated codegen sandbox matplotlib subprocess flake once
(`267 passed, 1 failed`), and the exact failed test passed on immediate rerun.
Verifier runs use the fake-HA in-memory storage-helper surface; production
Home Assistant setup wraps the same polling contract in HA's versioned
storage helper before writing setup state.

## Scenario Mapping

- Scenario A: setup enqueues post-setup polling without a worker call -> `CASE setup_enqueues_post_setup_poll_without_worker_call`
- Scenario B: scheduled ready poll records cadence -> `CASE scheduled_ready_poll_records_cadence`
- Scenario C: not-ready and unavailable results back off -> `CASE failure_poll_results_use_bounded_backoff`
- Scenario D: missing preconditions block polling before worker calls -> `CASE missing_preconditions_block_before_worker_call`
- Scenario E: single-flight guard prevents overlapping polls -> `CASE single_flight_guard_prevents_overlapping_poll`
- Scenario F: unload removes durable polling state -> `CASE unload_removes_durable_polling_state`
- Scenario G: polling state stays config-entry scoped -> `CASE worker_health_polling_stays_config_entry_scoped`
- Scenario H: setup resumes persisted polling cadence -> `CASE setup_resumes_persisted_polling_cadence`
- Scenario I: polling details do not leak to the card -> `CASE worker_health_polling_details_do_not_leak_to_card`
- Scenario J: polling remains bounded -> `CASE worker_health_polling_remains_bounded`
- Scenario K: Home Assistant timer runs post-setup polling -> `CASE home_assistant_timer_schedules_post_setup_and_next_poll`

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_durable_worker_health_polling_scaffold.py
```

Raw output excerpt:

```text
CASE setup_enqueues_post_setup_poll_without_worker_call
  "case_id": "setup_enqueues_post_setup_poll_without_worker_call",
  "config_entry_id": "worker-polling-setup-entry",
  "status": "scheduled",
  "post_setup_poll_enqueued": true,
  "worker_health_check_called": false,
  "health_call_count": 0,
  "state_validation": {
    "accepted": true,
    "status": "scheduled"
  }
PASS setup_enqueues_post_setup_poll_without_worker_call

CASE scheduled_ready_poll_records_cadence
  "case_id": "scheduled_ready_poll_records_cadence",
  "config_entry_id": "worker-polling-ready-entry",
  "worker_response_status": "ready",
  "status": "ready",
  "consecutive_failures": 0,
  "next_poll_delay_seconds": 300,
  "explicit_health_state_written": false,
  "worker_health_setup_code": "worker_health_probe_available",
  "health_call_count": 1,
  "render_call_count": 0,
  "state_validation": {
    "accepted": true,
    "status": "ready"
  }
  "early_duplicate": {
    "code": "worker_health_poll_not_due",
    "health_call_count": 1,
    "next_poll_delay_seconds": 300
  }
  "lost_precondition_before_not_due": {
    "code": "worker_health_polling_blocked",
    "status": "blocked",
    "worker_health_check_called": false,
    "state_validation": {
      "accepted": true,
      "status": "blocked"
    }
  }
PASS scheduled_ready_poll_records_cadence

CASE home_assistant_timer_schedules_post_setup_and_next_poll
  "case_id": "home_assistant_timer_schedules_post_setup_and_next_poll",
  "config_entry_id": "worker-polling-scheduler-entry",
  "health_calls_after_setup": 0,
  "setup_timer": {
    "registered": true,
    "delay_seconds": 0
  },
  "state_after_fire": {
    "status": "ready",
    "scheduler": {
      "next_poll_not_before": "2026-06-11T12:05:00+00:00"
    }
  },
  "created_task_count": 1,
  "executor_job_count": 1,
  "next_timer": {
    "registered": true,
    "delay_seconds": 300
  },
  "unload": {
    "cancelled_scheduled_poll": true
  },
  "timer_absent_after_unload": true
PASS home_assistant_timer_schedules_post_setup_and_next_poll

CASE failure_poll_results_use_bounded_backoff
  "case_id": "failure_poll_results_use_bounded_backoff",
  "backoff_seconds": [
    30,
    60,
    120,
    300,
    900
  ],
  "not_ready": {
    "status": "not_ready",
    "consecutive_failures": 2,
    "backoff_seconds": 60,
    "state_validation": {
      "accepted": true,
      "status": "not_ready"
    }
  },
  "early_duplicate_not_ready": {
    "code": "worker_health_poll_not_due",
    "health_call_count": 1,
    "consecutive_failures": 1,
    "backoff_seconds": 30
  },
  "unavailable": {
    "status": "unavailable",
    "failure_family": "connection",
    "backoff_seconds": 30,
    "state_validation": {
      "accepted": true,
      "status": "unavailable"
    }
  }
PASS failure_poll_results_use_bounded_backoff

CASE missing_preconditions_block_before_worker_call
  "case_id": "missing_preconditions_block_before_worker_call",
  "config_entry_id": "worker-polling-blocked-entry",
  "worker_readiness_ready": false,
  "accepted": false,
  "code": "worker_health_polling_blocked",
  "status": "blocked",
  "worker_client_present": false,
  "worker_health_check_called": false,
  "state_validation": {
    "accepted": true,
    "status": "blocked"
  }
PASS missing_preconditions_block_before_worker_call

CASE single_flight_guard_prevents_overlapping_poll
  "case_id": "single_flight_guard_prevents_overlapping_poll",
  "config_entry_id": "worker-polling-single-flight-entry",
  "normal_poll": {
    "poll_in_flight_during_health_call": true,
    "poll_in_flight_after_poll": false,
    "health_call_count": 1,
    "state_validation": {
      "accepted": true,
      "status": "ready"
    }
  },
  "poll_in_flight": true,
  "accepted": false,
  "code": "worker_health_poll_already_in_flight",
  "health_call_count": 0,
  "single_flight_guard_checked": true
PASS single_flight_guard_prevents_overlapping_poll

CASE unload_removes_durable_polling_state
  "case_id": "unload_removes_durable_polling_state",
  "target_entry_id": "worker-polling-unload-entry-a",
  "before_unload": {
    "entry_ids": [
      "worker-polling-unload-entry-a",
      "worker-polling-unload-entry-b"
    ]
  },
  "entry_a_state": null,
  "after_unload": {
    "entry_ids": [
      "worker-polling-unload-entry-b"
    ]
  },
  "entry_b_validation": {
    "accepted": true
  }
  "unload_race": {
    "code": "worker_health_polling_entry_unloaded",
    "state_absent_after_poll": true,
    "entry_data_absent_after_poll": true,
    "health_call_count": 1
  }
  "reload_race": {
    "code": "worker_health_polling_entry_reloaded",
    "old_health_call_count": 1,
    "reloaded_health_call_count": 0,
    "new_entry_is_current": true,
    "old_worker_health_absent_from_reloaded_entry": true,
    "stale_ready_state_absent": true,
    "stale_old_token_absent": true,
    "state_validation": {
      "accepted": true,
      "status": "scheduled"
    }
  }
  "context_change": {
    "code": "worker_health_polling_context_changed",
    "rotation_accepted": true,
    "in_flight_cleared": true,
    "follow_up_result": {
      "code": "worker_health_ready",
      "accepted": true
    },
    "follow_up_used_replacement_client": true,
    "context_state_validation": {
      "accepted": true,
      "status": "scheduled"
    },
    "follow_up_state_validation": {
      "accepted": true,
      "status": "ready"
    }
  }
PASS unload_removes_durable_polling_state

CASE worker_health_polling_stays_config_entry_scoped
  "case_id": "worker_health_polling_stays_config_entry_scoped",
  "entry_a": {
    "config_entry_id": "worker-polling-isolation-entry-a",
    "status": "ready",
    "health_call_count": 1,
    "raw_request_uses_own_token": true,
    "other_token_absent_from_request": true
  },
  "entry_b": {
    "config_entry_id": "worker-polling-isolation-entry-b",
    "status": "not_ready",
    "health_call_count": 1,
    "raw_request_uses_own_token": true,
    "other_token_absent_from_request": true
  }
  "storage_merge": {
    "before_load": {
      "entry_ids": [
        "worker-polling-unsaved-entry"
      ]
    },
    "after_load": {
      "entry_ids": [
        "worker-polling-persisted-entry",
        "worker-polling-unsaved-entry"
      ]
    },
    "unsaved_entry_present": true,
    "persisted_entry_present": true,
    "token_missing_entry_loaded": true,
    "invalid_entry_absent": true,
    "invalid_bounds_entry_absent": true,
    "invalid_cadence_entry_absent": true,
    "unloaded_entry_not_remerged": true,
    "unsaved_state_preserved": true,
    "persisted_state_loaded": true,
    "token_missing_state_loaded": true,
    "unloaded_state_not_loaded": true,
    "invalid_bounds_state_not_loaded": true,
    "invalid_cadence_state_not_loaded": true,
    "invalid_state_not_loaded": true
  }
PASS worker_health_polling_stays_config_entry_scoped

CASE setup_resumes_persisted_polling_cadence
  "case_id": "setup_resumes_persisted_polling_cadence",
  "config_entry_id": "worker-polling-resume-entry",
  "persisted_result": "not_ready",
  "persisted_backoff_seconds": 60,
  "resumed_health_call_count": 0,
  "setup_timer": {
    "registered": true,
    "delay_seconds": 30
  },
  "cadence_preserved": true,
  "consecutive_failures_preserved": true,
  "backoff_seconds_preserved": true,
  "state_validation": {
    "accepted": true,
    "status": "not_ready"
  }
PASS setup_resumes_persisted_polling_cadence

CASE worker_health_polling_details_do_not_leak_to_card
  "case_id": "worker_health_polling_details_do_not_leak_to_card",
  "raw_worker_authorization_received": true,
  "token_absent_from_polling_state": true,
  "token_absent_from_setup": true,
  "token_absent_from_evidence_payload": true,
  "token_absent_from_dashboard_card_metadata": true,
  "token_absent_from_model_provider_metadata": true,
  "endpoint_absent_from_polling_state": true,
  "endpoint_message_absent_from_polling_state": true,
  "endpoint_message_url_scheme_absent": true,
  "endpoint_message_absent_from_evidence_payload": true,
  "endpoint_code_absent_from_polling_state": true,
  "endpoint_code_redacted": true,
  "endpoint_health_code_redacted": true,
  "endpoint_code_absent_from_evidence_payload": true,
  "bare_token_absent_from_polling_state": true,
  "bare_token_absent_from_evidence_payload": true,
  "bare_token_code_redacted": true,
  "bare_token_health_code_redacted": true,
  "bare_token_message_redacted": true,
  "authorization_absent_from_polling_state": true,
  "request_absent_from_polling_state": true,
  "response_checks_absent_from_polling_state": true,
  "endpoint_absent_from_dashboard_payload": true,
  "polling_absent_from_dashboard_payload": true,
  "repair_recommendation_absent_from_dashboard_payload": true
PASS worker_health_polling_details_do_not_leak_to_card

CASE worker_health_polling_remains_bounded
  "case_id": "worker_health_polling_remains_bounded",
  "allowed_aggregate": {
    "durable_health_storage_written": true,
    "post_setup_poll_enqueued": true,
    "scheduler_bookkeeping_written": true,
    "single_flight_guard_checked": true,
    "worker_health_check_called": true,
    "worker_health_request_validated": true,
    "worker_health_response_validated": true
  },
  "forbidden_aggregate": {
    "automatic_progress_task_called": false,
    "automatic_repair_called": false,
    "automatic_retry_called": false,
    "chart_artifact_written": false,
    "chart_rendering_called": false,
    "config_entry_options_written": false,
    "durable_retry_storage_written": false,
    "external_queue_called": false,
    "home_assistant_history_read": false,
    "home_assistant_service_or_state_mutation_called": false,
    "model_provider_called": false,
    "polling_metadata_leaked_to_card": false,
    "recorder_called": false,
    "semantic_memory_called": false,
    "token_generated": false,
    "token_leaked_to_card": false,
    "token_repair_called": false,
    "token_rotation_called": false,
    "worker_endpoint_leaked_to_card": false,
    "worker_render_called": false
  }
PASS worker_health_polling_remains_bounded
PASS home_assistant_durable_worker_health_polling_scaffold
```

Token and endpoint scan:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_durable_worker_health_polling_scaffold.py | Select-String -Pattern "test-worker-readiness-token","http://worker.local:8765","worker.local_8765"
```

Raw output:

```text
```

## Additional Verification

```text
.\.venv\Scripts\python.exe -m pytest tests/test_worker_health_polling_anchor.py
17 passed

.\.venv\Scripts\python.exe -m pytest tests/test_worker_health_polling_anchor.py tests/test_worker_token_provisioning_readiness_anchor.py tests/test_worker_health_readiness_endpoint_anchor.py tests/test_worker_token_rotation_repair_anchor.py tests/test_job_orchestration_worker_dispatch_rendering_anchor.py tests/test_worker_progress_streaming_anchor.py tests/test_worker_retry_backoff_policy_anchor.py tests/test_worker_transport_failure_classification_anchor.py tests/test_worker_failure_snapshot_manual_retry_anchor.py
98 passed

.\.venv\Scripts\python.exe -m pytest tests/
1 failed, 263 passed (known codegen sandbox matplotlib subprocess flake)

.\.venv\Scripts\python.exe -m pytest tests/
268 passed

.\.venv\Scripts\python.exe evals\home_assistant_durable_worker_health_polling_scaffold.py
PASS home_assistant_durable_worker_health_polling_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_worker_token_provisioning_readiness_scaffold.py
PASS home_assistant_worker_token_provisioning_readiness_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_worker_health_readiness_endpoint_scaffold.py
PASS home_assistant_worker_health_readiness_endpoint_scaffold

.\.venv\Scripts\python.exe evals\home_assistant_worker_token_rotation_repair_scaffold.py
PASS home_assistant_worker_token_rotation_repair_scaffold

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
```
