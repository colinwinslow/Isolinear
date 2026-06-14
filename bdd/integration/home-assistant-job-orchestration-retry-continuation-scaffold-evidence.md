CASE accepted_retry_resumes_same_failed_job
{
  "case_id": "accepted_retry_resumes_same_failed_job",
  "given": {
    "config_entry_id": "retry-entry",
    "run_timestamp": "2026-06-08T20:46:42+00:00",
    "schema": "docs/schemas/integration-job-snapshot.schema.json"
  },
  "then": {
    "accepted": {
      "failed_snapshot": {
        "failure": {
          "code": "missing_approved_history",
          "message": "Approved history is missing for: sensor.downstairs_temperature.",
          "stage": "approved_history_retrieval"
        },
        "job_id": "retry-entry-job-001",
        "message": "Approved history is missing for: sensor.downstairs_temperature.",
        "progress": {
          "message": "Approved history is missing for: sensor.downstairs_temperature.",
          "stage": "job_orchestration_scaffold_failed"
        },
        "prompt": "Show sensor.downstairs_temperature",
        "retry_allowed": true,
        "snapshot_id": "retry-entry-job-001-snapshot-003",
        "state_label": "Failed",
        "status": "failed",
        "validation": {
          "checks": [
            {
              "name": "integration_job_state_scaffold",
              "status": "pass"
            },
            {
              "name": "approved_entity_catalog",
              "status": "pass"
            },
            {
              "name": "approved_history_retrieval",
              "status": "fail"
            },
            {
              "name": "model_provider",
              "status": "not_called"
            },
            {
              "name": "worker",
              "status": "not_called"
            }
          ],
          "status": "fail",
          "summary": "The orchestration scaffold stopped at a deterministic gate."
        },
        "warnings": [
          "job_orchestration_scaffold",
          "missing_approved_history",
          "orchestration_stopped_before_model_worker"
        ]
      },
      "history_store": {
        "entity_ids": [
          "sensor.downstairs_temperature"
        ],
        "entry_id": "retry-entry",
        "last_time_range": {
          "end": "2026-06-08T12:00:00+00:00",
          "start": "2026-06-08T06:00:00+00:00"
        },
        "request_count": 1,
        "series_count": 1
      },
      "job_progress_stages": [
        "job_state_scaffold",
        "approved_history_retrieval",
        "job_orchestration_scaffold_failed",
        "job_orchestration_retry_accepted",
        "approved_history_retrieval",
        "job_orchestration_retry_continuation_ready"
      ],
      "job_snapshot_ids": [
        "retry-entry-job-001-snapshot-001",
        "retry-entry-job-001-snapshot-002",
        "retry-entry-job-001-snapshot-003",
        "retry-entry-job-001-snapshot-004",
        "retry-entry-job-001-snapshot-005",
        "retry-entry-job-001-snapshot-006"
      ],
      "job_snapshot_statuses": [
        "planning",
        "fetching_history",
        "failed",
        "planning",
        "fetching_history",
        "planning"
      ],
      "job_store": {
        "entry_id": "retry-entry",
        "job_ids": [
          "retry-entry-job-001"
        ],
        "latest_snapshot_ids": [
          "retry-entry-job-001-snapshot-006"
        ],
        "next_job_number": 2,
        "subscription_count": 0,
        "subscription_ids": []
      },
      "orchestration_store": {
        "entry_id": "retry-entry",
        "latest_history_entity_ids": [
          "sensor.downstairs_temperature"
        ],
        "latest_job_id": "retry-entry-job-001",
        "latest_requested_entity_ids": [
          "sensor.downstairs_temperature"
        ],
        "latest_result_code": "retry_approved_history_ready",
        "run_count": 2,
        "run_ids": [
          "retry-entry-orchestration-run-001",
          "retry-entry-orchestration-run-002"
        ]
      },
      "retry": {
        "accepted": true,
        "connection": {
          "errors": [],
          "results": [
            {
              "id": 2,
              "result": {
                "entities": [
                  {
                    "entity_id": "sensor.downstairs_temperature",
                    "label": "Downstairs Temperature"
                  }
                ],
                "job_id": "retry-entry-job-001",
                "message": "Retry composed approved catalog and history for a later planning packet; model and worker calls are not implemented yet.",
                "progress": {
                  "message": "Approved retry history is staged for future planning.",
                  "stage": "job_orchestration_retry_continuation_ready"
                },
                "prompt": "Show sensor.downstairs_temperature",
                "snapshot_id": "retry-entry-job-001-snapshot-006",
                "state_label": "Ready",
                "status": "planning",
                "validation": {
                  "checks": [
                    {
                      "name": "integration_job_state_scaffold",
                      "status": "pass"
                    },
                    {
                      "name": "retry_command",
                      "status": "pass"
                    },
                    {
                      "name": "approved_entity_catalog",
                      "status": "pass"
                    },
                    {
                      "name": "approved_history_retrieval",
                      "status": "pass"
                    },
                    {
                      "name": "model_provider",
                      "status": "not_called"
                    },
                    {
                      "name": "worker",
                      "status": "not_called"
                    },
                    {
                      "name": "chart_rendering",
                      "status": "not_called"
                    }
                  ],
                  "status": "pass",
                  "summary": "The retry continuation scaffold composed approved catalog, history, and existing job state."
                },
                "warnings": [
                  "job_orchestration_retry_continuation_scaffold",
                  "model_provider_not_called",
                  "worker_not_called",
                  "chart_rendering_not_started"
                ]
              }
            }
          ]
        },
        "handler_called": true,
        "handler_result": {
          "accepted": true,
          "code": "registered_job_state_command_accepted",
          "config_entry_id": "retry-entry",
          "job_orchestration": {
            "run": {
              "entry_id": "retry-entry",
              "history_entity_ids": [
                "sensor.downstairs_temperature"
              ],
              "job_id": "retry-entry-job-001",
              "missing_entity_ids": [],
              "prompt": "Show sensor.downstairs_temperature",
              "rejected_entity_ids": [],
              "requested_entity_ids": [
                "sensor.downstairs_temperature"
              ],
              "result_code": "retry_approved_history_ready",
              "run_id": "retry-entry-orchestration-run-002",
              "snapshot_ids": [
                "retry-entry-job-001-snapshot-001",
                "retry-entry-job-001-snapshot-002",
                "retry-entry-job-001-snapshot-003",
                "retry-entry-job-001-snapshot-004",
                "retry-entry-job-001-snapshot-005",
                "retry-entry-job-001-snapshot-006"
              ]
            }
          },
          "job_state": {
            "code": "job_orchestration_retry_continuation_ready",
            "job_id": "retry-entry-job-001",
            "subscription": null
          },
          "orchestration": {
            "approved_entity_catalog_read": true,
            "chart_artifact_written": false,
            "chart_rendering_called": false,
            "durable_storage_written": false,
            "history_retrieval_scaffold_written": true,
            "home_assistant_history_called": false,
            "home_assistant_history_read": true,
            "home_assistant_service_or_state_mutation_called": false,
            "job_orchestration_called": false,
            "job_orchestration_scaffold_written": true,
            "job_state_scaffold_written": true,
            "model_provider_called": false,
            "retry_behavior_called": true,
            "semantic_memory_called": false,
            "subscription_progress_streaming_called": false,
            "token_generated": false,
            "websocket_command_registered": false,
            "worker_called": false
          },
          "snapshot": {
            "entities": [
              {
                "entity_id": "sensor.downstairs_temperature",
                "label": "Downstairs Temperature"
              }
            ],
            "job_id": "retry-entry-job-001",
            "message": "Retry composed approved catalog and history for a later planning packet; model and worker calls are not implemented yet.",
            "progress": {
              "message": "Approved retry history is staged for future planning.",
              "stage": "job_orchestration_retry_continuation_ready"
            },
            "prompt": "Show sensor.downstairs_temperature",
            "snapshot_id": "retry-entry-job-001-snapshot-006",
            "state_label": "Ready",
            "status": "planning",
            "validation": {
              "checks": [
                {
                  "name": "integration_job_state_scaffold",
                  "status": "pass"
                },
                {
                  "name": "retry_command",
                  "status": "pass"
                },
                {
                  "name": "approved_entity_catalog",
                  "status": "pass"
                },
                {
                  "name": "approved_history_retrieval",
                  "status": "pass"
                },
                {
                  "name": "model_provider",
                  "status": "not_called"
                },
                {
                  "name": "worker",
                  "status": "not_called"
                },
                {
                  "name": "chart_rendering",
                  "status": "not_called"
                }
              ],
              "status": "pass",
              "summary": "The retry continuation scaffold composed approved catalog, history, and existing job state."
            },
            "warnings": [
              "job_orchestration_retry_continuation_scaffold",
              "model_provider_not_called",
              "worker_not_called",
              "chart_rendering_not_started"
            ]
          },
          "type": "isolinear/v1/job/retry",
          "version": 1
        },
        "orchestration": {
          "approved_entity_catalog_read": true,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_storage_written": false,
          "history_retrieval_scaffold_written": true,
          "home_assistant_history_called": false,
          "home_assistant_history_read": true,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "job_orchestration_scaffold_written": true,
          "job_state_scaffold_written": true,
          "model_provider_called": false,
          "retry_behavior_called": true,
          "semantic_memory_called": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        }
      },
      "retry_snapshot": {
        "entities": [
          {
            "entity_id": "sensor.downstairs_temperature",
            "label": "Downstairs Temperature"
          }
        ],
        "job_id": "retry-entry-job-001",
        "message": "Retry composed approved catalog and history for a later planning packet; model and worker calls are not implemented yet.",
        "progress": {
          "message": "Approved retry history is staged for future planning.",
          "stage": "job_orchestration_retry_continuation_ready"
        },
        "prompt": "Show sensor.downstairs_temperature",
        "snapshot_id": "retry-entry-job-001-snapshot-006",
        "state_label": "Ready",
        "status": "planning",
        "validation": {
          "checks": [
            {
              "name": "integration_job_state_scaffold",
              "status": "pass"
            },
            {
              "name": "retry_command",
              "status": "pass"
            },
            {
              "name": "approved_entity_catalog",
              "status": "pass"
            },
            {
              "name": "approved_history_retrieval",
              "status": "pass"
            },
            {
              "name": "model_provider",
              "status": "not_called"
            },
            {
              "name": "worker",
              "status": "not_called"
            },
            {
              "name": "chart_rendering",
              "status": "not_called"
            }
          ],
          "status": "pass",
          "summary": "The retry continuation scaffold composed approved catalog, history, and existing job state."
        },
        "warnings": [
          "job_orchestration_retry_continuation_scaffold",
          "model_provider_not_called",
          "worker_not_called",
          "chart_rendering_not_started"
        ]
      },
      "run": {
        "entry_id": "retry-entry",
        "history_entity_ids": [
          "sensor.downstairs_temperature"
        ],
        "job_id": "retry-entry-job-001",
        "missing_entity_ids": [],
        "prompt": "Show sensor.downstairs_temperature",
        "rejected_entity_ids": [],
        "requested_entity_ids": [
          "sensor.downstairs_temperature"
        ],
        "result_code": "retry_approved_history_ready",
        "run_id": "retry-entry-orchestration-run-002",
        "snapshot_ids": [
          "retry-entry-job-001-snapshot-001",
          "retry-entry-job-001-snapshot-002",
          "retry-entry-job-001-snapshot-003",
          "retry-entry-job-001-snapshot-004",
          "retry-entry-job-001-snapshot-005",
          "retry-entry-job-001-snapshot-006"
        ]
      },
      "same_job_id": true,
      "snapshot_count_after": 6,
      "snapshot_count_before": 3,
      "snapshot_validation": [
        {
          "accepted": true,
          "code": "accepted",
          "failure_code": null,
          "job_id": "retry-entry-job-001",
          "progress_stage": "job_state_scaffold",
          "retry_allowed": null,
          "snapshot_id": "retry-entry-job-001-snapshot-001",
          "status": "planning"
        },
        {
          "accepted": true,
          "code": "accepted",
          "failure_code": null,
          "job_id": "retry-entry-job-001",
          "progress_stage": "approved_history_retrieval",
          "retry_allowed": null,
          "snapshot_id": "retry-entry-job-001-snapshot-002",
          "status": "fetching_history"
        },
        {
          "accepted": true,
          "code": "accepted",
          "failure_code": "missing_approved_history",
          "job_id": "retry-entry-job-001",
          "progress_stage": "job_orchestration_scaffold_failed",
          "retry_allowed": true,
          "snapshot_id": "retry-entry-job-001-snapshot-003",
          "status": "failed"
        },
        {
          "accepted": true,
          "code": "accepted",
          "failure_code": null,
          "job_id": "retry-entry-job-001",
          "progress_stage": "job_orchestration_retry_accepted",
          "retry_allowed": null,
          "snapshot_id": "retry-entry-job-001-snapshot-004",
          "status": "planning"
        },
        {
          "accepted": true,
          "code": "accepted",
          "failure_code": null,
          "job_id": "retry-entry-job-001",
          "progress_stage": "approved_history_retrieval",
          "retry_allowed": null,
          "snapshot_id": "retry-entry-job-001-snapshot-005",
          "status": "fetching_history"
        },
        {
          "accepted": true,
          "code": "accepted",
          "failure_code": null,
          "job_id": "retry-entry-job-001",
          "progress_stage": "job_orchestration_retry_continuation_ready",
          "retry_allowed": null,
          "snapshot_id": "retry-entry-job-001-snapshot-006",
          "status": "planning"
        }
      ],
      "start": {
        "accepted": true,
        "connection": {
          "errors": [],
          "results": [
            {
              "id": 1,
              "result": {
                "failure": {
                  "code": "missing_approved_history",
                  "message": "Approved history is missing for: sensor.downstairs_temperature.",
                  "stage": "approved_history_retrieval"
                },
                "job_id": "retry-entry-job-001",
                "message": "Approved history is missing for: sensor.downstairs_temperature.",
                "progress": {
                  "message": "Approved history is missing for: sensor.downstairs_temperature.",
                  "stage": "job_orchestration_scaffold_failed"
                },
                "prompt": "Show sensor.downstairs_temperature",
                "retry_allowed": true,
                "snapshot_id": "retry-entry-job-001-snapshot-003",
                "state_label": "Failed",
                "status": "failed",
                "validation": {
                  "checks": [
                    {
                      "name": "integration_job_state_scaffold",
                      "status": "pass"
                    },
                    {
                      "name": "approved_entity_catalog",
                      "status": "pass"
                    },
                    {
                      "name": "approved_history_retrieval",
                      "status": "fail"
                    },
                    {
                      "name": "model_provider",
                      "status": "not_called"
                    },
                    {
                      "name": "worker",
                      "status": "not_called"
                    }
                  ],
                  "status": "fail",
                  "summary": "The orchestration scaffold stopped at a deterministic gate."
                },
                "warnings": [
                  "job_orchestration_scaffold",
                  "missing_approved_history",
                  "orchestration_stopped_before_model_worker"
                ]
              }
            }
          ]
        },
        "handler_called": true,
        "handler_result": {
          "accepted": true,
          "code": "registered_job_state_command_accepted",
          "config_entry_id": "retry-entry",
          "job_orchestration": {
            "run": {
              "entry_id": "retry-entry",
              "history_entity_ids": [],
              "job_id": "retry-entry-job-001",
              "missing_entity_ids": [
                "sensor.downstairs_temperature"
              ],
              "prompt": "Show sensor.downstairs_temperature",
              "rejected_entity_ids": [],
              "requested_entity_ids": [
                "sensor.downstairs_temperature"
              ],
              "result_code": "missing_approved_history",
              "run_id": "retry-entry-orchestration-run-001",
              "snapshot_ids": [
                "retry-entry-job-001-snapshot-001",
                "retry-entry-job-001-snapshot-002",
                "retry-entry-job-001-snapshot-003"
              ]
            }
          },
          "job_state": {
            "code": "job_orchestration_scaffold_failed",
            "job_id": "retry-entry-job-001",
            "subscription": null
          },
          "orchestration": {
            "approved_entity_catalog_read": true,
            "chart_artifact_written": false,
            "chart_rendering_called": false,
            "durable_storage_written": false,
            "history_retrieval_scaffold_written": false,
            "home_assistant_history_called": false,
            "home_assistant_history_read": true,
            "home_assistant_service_or_state_mutation_called": false,
            "job_orchestration_called": false,
            "job_orchestration_scaffold_written": true,
            "job_state_scaffold_written": true,
            "model_provider_called": false,
            "retry_behavior_called": false,
            "semantic_memory_called": false,
            "subscription_progress_streaming_called": false,
            "token_generated": false,
            "websocket_command_registered": false,
            "worker_called": false
          },
          "snapshot": {
            "failure": {
              "code": "missing_approved_history",
              "message": "Approved history is missing for: sensor.downstairs_temperature.",
              "stage": "approved_history_retrieval"
            },
            "job_id": "retry-entry-job-001",
            "message": "Approved history is missing for: sensor.downstairs_temperature.",
            "progress": {
              "message": "Approved history is missing for: sensor.downstairs_temperature.",
              "stage": "job_orchestration_scaffold_failed"
            },
            "prompt": "Show sensor.downstairs_temperature",
            "retry_allowed": true,
            "snapshot_id": "retry-entry-job-001-snapshot-003",
            "state_label": "Failed",
            "status": "failed",
            "validation": {
              "checks": [
                {
                  "name": "integration_job_state_scaffold",
                  "status": "pass"
                },
                {
                  "name": "approved_entity_catalog",
                  "status": "pass"
                },
                {
                  "name": "approved_history_retrieval",
                  "status": "fail"
                },
                {
                  "name": "model_provider",
                  "status": "not_called"
                },
                {
                  "name": "worker",
                  "status": "not_called"
                }
              ],
              "status": "fail",
              "summary": "The orchestration scaffold stopped at a deterministic gate."
            },
            "warnings": [
              "job_orchestration_scaffold",
              "missing_approved_history",
              "orchestration_stopped_before_model_worker"
            ]
          },
          "type": "isolinear/v1/job/start",
          "version": 1
        },
        "orchestration": {
          "approved_entity_catalog_read": true,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_storage_written": false,
          "history_retrieval_scaffold_written": false,
          "home_assistant_history_called": false,
          "home_assistant_history_read": true,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "job_orchestration_scaffold_written": true,
          "job_state_scaffold_written": true,
          "model_provider_called": false,
          "retry_behavior_called": false,
          "semantic_memory_called": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        }
      }
    }
  },
  "when": {
    "history_repaired_for_entity": "sensor.downstairs_temperature",
    "operation": "dispatch_registered_job_retry"
  }
}
PASS accepted_retry_resumes_same_failed_job
CASE unknown_job_fails_before_history
{
  "case_id": "unknown_job_fails_before_history",
  "given": {
    "job_id": "unknown-retry-entry-job-404"
  },
  "then": {
    "unknown_job": {
      "error_codes": [
        "unknown_job"
      ],
      "history_after": {
        "entity_ids": [],
        "entry_id": "unknown-retry-entry",
        "last_time_range": null,
        "request_count": 0,
        "series_count": 0
      },
      "history_before": {
        "entity_ids": [],
        "entry_id": "unknown-retry-entry",
        "last_time_range": null,
        "request_count": 0,
        "series_count": 0
      },
      "job_store": {
        "entry_id": "unknown-retry-entry",
        "job_ids": [],
        "latest_snapshot_ids": [],
        "next_job_number": 1,
        "subscription_count": 0,
        "subscription_ids": []
      },
      "retry": {
        "accepted": false,
        "connection": {
          "errors": [
            {
              "code": "unknown_job",
              "id": 10,
              "message": "The requested Isolinear job was not found for this config entry."
            }
          ],
          "results": []
        },
        "handler_called": true,
        "handler_result": {
          "accepted": false,
          "code": "unknown_job",
          "config_entry_id": "unknown-retry-entry",
          "job_id": "unknown-retry-entry-job-404",
          "orchestration": {
            "approved_entity_catalog_read": false,
            "chart_artifact_written": false,
            "chart_rendering_called": false,
            "durable_storage_written": false,
            "history_retrieval_scaffold_written": false,
            "home_assistant_history_called": false,
            "home_assistant_history_read": false,
            "home_assistant_service_or_state_mutation_called": false,
            "job_orchestration_called": false,
            "job_orchestration_scaffold_written": false,
            "job_state_scaffold_written": false,
            "model_provider_called": false,
            "retry_behavior_called": false,
            "semantic_memory_called": false,
            "subscription_progress_streaming_called": false,
            "token_generated": false,
            "websocket_command_registered": false,
            "worker_called": false
          },
          "render_attempted": false
        },
        "orchestration": {
          "approved_entity_catalog_read": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_storage_written": false,
          "history_retrieval_scaffold_written": false,
          "home_assistant_history_called": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "job_orchestration_scaffold_written": false,
          "job_state_scaffold_written": false,
          "model_provider_called": false,
          "retry_behavior_called": false,
          "semantic_memory_called": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        }
      },
      "snapshot_validation": []
    }
  },
  "when": {
    "operation": "dispatch_registered_job_retry"
  }
}
PASS unknown_job_fails_before_history
CASE non_retryable_job_fails_before_history
{
  "case_id": "non_retryable_job_fails_before_history",
  "given": {
    "latest_snapshot_status": "planning"
  },
  "then": {
    "non_retryable": {
      "error_codes": [
        "job_not_retryable"
      ],
      "history_after": {
        "entity_ids": [
          "sensor.upstairs_temperature"
        ],
        "entry_id": "non-retryable-entry",
        "last_time_range": {
          "end": "2026-06-08T12:00:00+00:00",
          "start": "2026-06-08T06:00:00+00:00"
        },
        "request_count": 1,
        "series_count": 1
      },
      "history_before": {
        "entity_ids": [
          "sensor.upstairs_temperature"
        ],
        "entry_id": "non-retryable-entry",
        "last_time_range": {
          "end": "2026-06-08T12:00:00+00:00",
          "start": "2026-06-08T06:00:00+00:00"
        },
        "request_count": 1,
        "series_count": 1
      },
      "orchestration_store": {
        "entry_id": "non-retryable-entry",
        "latest_history_entity_ids": [],
        "latest_job_id": "non-retryable-entry-job-001",
        "latest_requested_entity_ids": [],
        "latest_result_code": "job_not_retryable",
        "run_count": 2,
        "run_ids": [
          "non-retryable-entry-orchestration-run-001",
          "non-retryable-entry-orchestration-run-002"
        ]
      },
      "retry": {
        "accepted": false,
        "connection": {
          "errors": [
            {
              "code": "job_not_retryable",
              "id": 21,
              "message": "Isolinear WebSocket command rejected."
            }
          ],
          "results": []
        },
        "handler_called": true,
        "handler_result": {
          "accepted": false,
          "code": "job_not_retryable",
          "config_entry_id": "non-retryable-entry",
          "job_id": "non-retryable-entry-job-001",
          "orchestration": {
            "approved_entity_catalog_read": false,
            "chart_artifact_written": false,
            "chart_rendering_called": false,
            "durable_storage_written": false,
            "history_retrieval_scaffold_written": false,
            "home_assistant_history_called": false,
            "home_assistant_history_read": false,
            "home_assistant_service_or_state_mutation_called": false,
            "job_orchestration_called": false,
            "job_orchestration_scaffold_written": true,
            "job_state_scaffold_written": false,
            "model_provider_called": false,
            "retry_behavior_called": false,
            "semantic_memory_called": false,
            "subscription_progress_streaming_called": false,
            "token_generated": false,
            "websocket_command_registered": false,
            "worker_called": false
          },
          "render_attempted": false
        },
        "orchestration": {
          "approved_entity_catalog_read": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_storage_written": false,
          "history_retrieval_scaffold_written": false,
          "home_assistant_history_called": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "job_orchestration_scaffold_written": true,
          "job_state_scaffold_written": false,
          "model_provider_called": false,
          "retry_behavior_called": false,
          "semantic_memory_called": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        }
      },
      "snapshot_count_after": 3,
      "snapshot_count_before": 3,
      "start": {
        "accepted": true,
        "connection": {
          "errors": [],
          "results": [
            {
              "id": 20,
              "result": {
                "entities": [
                  {
                    "entity_id": "sensor.upstairs_temperature",
                    "label": "Upstairs Temperature"
                  }
                ],
                "job_id": "non-retryable-entry-job-001",
                "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
                "progress": {
                  "message": "Approved history is staged for future planning.",
                  "stage": "job_orchestration_scaffold_ready"
                },
                "prompt": "Show sensor.upstairs_temperature",
                "snapshot_id": "non-retryable-entry-job-001-snapshot-003",
                "state_label": "Ready",
                "status": "planning",
                "validation": {
                  "checks": [
                    {
                      "name": "integration_job_state_scaffold",
                      "status": "pass"
                    },
                    {
                      "name": "approved_entity_catalog",
                      "status": "pass"
                    },
                    {
                      "name": "approved_history_retrieval",
                      "status": "pass"
                    },
                    {
                      "name": "model_provider",
                      "status": "not_called"
                    },
                    {
                      "name": "worker",
                      "status": "not_called"
                    },
                    {
                      "name": "chart_rendering",
                      "status": "not_called"
                    }
                  ],
                  "status": "pass",
                  "summary": "The orchestration scaffold composed approved catalog, history, and job state."
                },
                "warnings": [
                  "job_orchestration_scaffold",
                  "model_provider_not_called",
                  "worker_not_called",
                  "chart_rendering_not_started"
                ]
              }
            }
          ]
        },
        "handler_called": true,
        "handler_result": {
          "accepted": true,
          "code": "registered_job_state_command_accepted",
          "config_entry_id": "non-retryable-entry",
          "job_orchestration": {
            "run": {
              "entry_id": "non-retryable-entry",
              "history_entity_ids": [
                "sensor.upstairs_temperature"
              ],
              "job_id": "non-retryable-entry-job-001",
              "missing_entity_ids": [],
              "prompt": "Show sensor.upstairs_temperature",
              "rejected_entity_ids": [],
              "requested_entity_ids": [
                "sensor.upstairs_temperature"
              ],
              "result_code": "approved_history_ready",
              "run_id": "non-retryable-entry-orchestration-run-001",
              "snapshot_ids": [
                "non-retryable-entry-job-001-snapshot-001",
                "non-retryable-entry-job-001-snapshot-002",
                "non-retryable-entry-job-001-snapshot-003"
              ]
            }
          },
          "job_state": {
            "code": "job_orchestration_scaffold_ready",
            "job_id": "non-retryable-entry-job-001",
            "subscription": null
          },
          "orchestration": {
            "approved_entity_catalog_read": true,
            "chart_artifact_written": false,
            "chart_rendering_called": false,
            "durable_storage_written": false,
            "history_retrieval_scaffold_written": true,
            "home_assistant_history_called": false,
            "home_assistant_history_read": true,
            "home_assistant_service_or_state_mutation_called": false,
            "job_orchestration_called": false,
            "job_orchestration_scaffold_written": true,
            "job_state_scaffold_written": true,
            "model_provider_called": false,
            "retry_behavior_called": false,
            "semantic_memory_called": false,
            "subscription_progress_streaming_called": false,
            "token_generated": false,
            "websocket_command_registered": false,
            "worker_called": false
          },
          "snapshot": {
            "entities": [
              {
                "entity_id": "sensor.upstairs_temperature",
                "label": "Upstairs Temperature"
              }
            ],
            "job_id": "non-retryable-entry-job-001",
            "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
            "progress": {
              "message": "Approved history is staged for future planning.",
              "stage": "job_orchestration_scaffold_ready"
            },
            "prompt": "Show sensor.upstairs_temperature",
            "snapshot_id": "non-retryable-entry-job-001-snapshot-003",
            "state_label": "Ready",
            "status": "planning",
            "validation": {
              "checks": [
                {
                  "name": "integration_job_state_scaffold",
                  "status": "pass"
                },
                {
                  "name": "approved_entity_catalog",
                  "status": "pass"
                },
                {
                  "name": "approved_history_retrieval",
                  "status": "pass"
                },
                {
                  "name": "model_provider",
                  "status": "not_called"
                },
                {
                  "name": "worker",
                  "status": "not_called"
                },
                {
                  "name": "chart_rendering",
                  "status": "not_called"
                }
              ],
              "status": "pass",
              "summary": "The orchestration scaffold composed approved catalog, history, and job state."
            },
            "warnings": [
              "job_orchestration_scaffold",
              "model_provider_not_called",
              "worker_not_called",
              "chart_rendering_not_started"
            ]
          },
          "type": "isolinear/v1/job/start",
          "version": 1
        },
        "orchestration": {
          "approved_entity_catalog_read": true,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_storage_written": false,
          "history_retrieval_scaffold_written": true,
          "home_assistant_history_called": false,
          "home_assistant_history_read": true,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "job_orchestration_scaffold_written": true,
          "job_state_scaffold_written": true,
          "model_provider_called": false,
          "retry_behavior_called": false,
          "semantic_memory_called": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        }
      },
      "start_snapshot_validation": {
        "accepted": true,
        "code": "accepted",
        "failure_code": null,
        "job_id": "non-retryable-entry-job-001",
        "progress_stage": "job_orchestration_scaffold_ready",
        "retry_allowed": null,
        "snapshot_id": "non-retryable-entry-job-001-snapshot-003",
        "status": "planning"
      }
    }
  },
  "when": {
    "operation": "dispatch_registered_job_retry"
  }
}
PASS non_retryable_job_fails_before_history
CASE cross_config_entry_retry_rejected
{
  "case_id": "cross_config_entry_retry_rejected",
  "given": {
    "entry_ids": [
      "retry-entry-a",
      "retry-entry-b"
    ]
  },
  "then": {
    "cross_entry": {
      "cross_retry": {
        "accepted": false,
        "connection": {
          "errors": [
            {
              "code": "unknown_job",
              "id": 32,
              "message": "The requested Isolinear job was not found for this config entry."
            }
          ],
          "results": []
        },
        "handler_called": true,
        "handler_result": {
          "accepted": false,
          "code": "unknown_job",
          "config_entry_id": "retry-entry-b",
          "job_id": "retry-entry-a-job-001",
          "orchestration": {
            "approved_entity_catalog_read": false,
            "chart_artifact_written": false,
            "chart_rendering_called": false,
            "durable_storage_written": false,
            "history_retrieval_scaffold_written": false,
            "home_assistant_history_called": false,
            "home_assistant_history_read": false,
            "home_assistant_service_or_state_mutation_called": false,
            "job_orchestration_called": false,
            "job_orchestration_scaffold_written": false,
            "job_state_scaffold_written": false,
            "model_provider_called": false,
            "retry_behavior_called": false,
            "semantic_memory_called": false,
            "subscription_progress_streaming_called": false,
            "token_generated": false,
            "websocket_command_registered": false,
            "worker_called": false
          },
          "render_attempted": false
        },
        "orchestration": {
          "approved_entity_catalog_read": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_storage_written": false,
          "history_retrieval_scaffold_written": false,
          "home_assistant_history_called": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "job_orchestration_scaffold_written": false,
          "job_state_scaffold_written": false,
          "model_provider_called": false,
          "retry_behavior_called": false,
          "semantic_memory_called": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        }
      },
      "entry_a_history_store": {
        "entity_ids": [],
        "entry_id": "retry-entry-a",
        "last_time_range": null,
        "request_count": 0,
        "series_count": 0
      },
      "entry_a_orchestration_store": {
        "entry_id": "retry-entry-a",
        "latest_history_entity_ids": [],
        "latest_job_id": "retry-entry-a-job-001",
        "latest_requested_entity_ids": [
          "sensor.downstairs_temperature"
        ],
        "latest_result_code": "missing_approved_history",
        "run_count": 1,
        "run_ids": [
          "retry-entry-a-orchestration-run-001"
        ]
      },
      "entry_a_snapshot_validation": {
        "accepted": true,
        "code": "accepted",
        "failure_code": "missing_approved_history",
        "job_id": "retry-entry-a-job-001",
        "progress_stage": "job_orchestration_scaffold_failed",
        "retry_allowed": true,
        "snapshot_id": "retry-entry-a-job-001-snapshot-003",
        "status": "failed"
      },
      "entry_a_start": {
        "accepted": true,
        "connection": {
          "errors": [],
          "results": [
            {
              "id": 30,
              "result": {
                "failure": {
                  "code": "missing_approved_history",
                  "message": "Approved history is missing for: sensor.downstairs_temperature.",
                  "stage": "approved_history_retrieval"
                },
                "job_id": "retry-entry-a-job-001",
                "message": "Approved history is missing for: sensor.downstairs_temperature.",
                "progress": {
                  "message": "Approved history is missing for: sensor.downstairs_temperature.",
                  "stage": "job_orchestration_scaffold_failed"
                },
                "prompt": "Show sensor.downstairs_temperature",
                "retry_allowed": true,
                "snapshot_id": "retry-entry-a-job-001-snapshot-003",
                "state_label": "Failed",
                "status": "failed",
                "validation": {
                  "checks": [
                    {
                      "name": "integration_job_state_scaffold",
                      "status": "pass"
                    },
                    {
                      "name": "approved_entity_catalog",
                      "status": "pass"
                    },
                    {
                      "name": "approved_history_retrieval",
                      "status": "fail"
                    },
                    {
                      "name": "model_provider",
                      "status": "not_called"
                    },
                    {
                      "name": "worker",
                      "status": "not_called"
                    }
                  ],
                  "status": "fail",
                  "summary": "The orchestration scaffold stopped at a deterministic gate."
                },
                "warnings": [
                  "job_orchestration_scaffold",
                  "missing_approved_history",
                  "orchestration_stopped_before_model_worker"
                ]
              }
            }
          ]
        },
        "handler_called": true,
        "handler_result": {
          "accepted": true,
          "code": "registered_job_state_command_accepted",
          "config_entry_id": "retry-entry-a",
          "job_orchestration": {
            "run": {
              "entry_id": "retry-entry-a",
              "history_entity_ids": [],
              "job_id": "retry-entry-a-job-001",
              "missing_entity_ids": [
                "sensor.downstairs_temperature"
              ],
              "prompt": "Show sensor.downstairs_temperature",
              "rejected_entity_ids": [],
              "requested_entity_ids": [
                "sensor.downstairs_temperature"
              ],
              "result_code": "missing_approved_history",
              "run_id": "retry-entry-a-orchestration-run-001",
              "snapshot_ids": [
                "retry-entry-a-job-001-snapshot-001",
                "retry-entry-a-job-001-snapshot-002",
                "retry-entry-a-job-001-snapshot-003"
              ]
            }
          },
          "job_state": {
            "code": "job_orchestration_scaffold_failed",
            "job_id": "retry-entry-a-job-001",
            "subscription": null
          },
          "orchestration": {
            "approved_entity_catalog_read": true,
            "chart_artifact_written": false,
            "chart_rendering_called": false,
            "durable_storage_written": false,
            "history_retrieval_scaffold_written": false,
            "home_assistant_history_called": false,
            "home_assistant_history_read": true,
            "home_assistant_service_or_state_mutation_called": false,
            "job_orchestration_called": false,
            "job_orchestration_scaffold_written": true,
            "job_state_scaffold_written": true,
            "model_provider_called": false,
            "retry_behavior_called": false,
            "semantic_memory_called": false,
            "subscription_progress_streaming_called": false,
            "token_generated": false,
            "websocket_command_registered": false,
            "worker_called": false
          },
          "snapshot": {
            "failure": {
              "code": "missing_approved_history",
              "message": "Approved history is missing for: sensor.downstairs_temperature.",
              "stage": "approved_history_retrieval"
            },
            "job_id": "retry-entry-a-job-001",
            "message": "Approved history is missing for: sensor.downstairs_temperature.",
            "progress": {
              "message": "Approved history is missing for: sensor.downstairs_temperature.",
              "stage": "job_orchestration_scaffold_failed"
            },
            "prompt": "Show sensor.downstairs_temperature",
            "retry_allowed": true,
            "snapshot_id": "retry-entry-a-job-001-snapshot-003",
            "state_label": "Failed",
            "status": "failed",
            "validation": {
              "checks": [
                {
                  "name": "integration_job_state_scaffold",
                  "status": "pass"
                },
                {
                  "name": "approved_entity_catalog",
                  "status": "pass"
                },
                {
                  "name": "approved_history_retrieval",
                  "status": "fail"
                },
                {
                  "name": "model_provider",
                  "status": "not_called"
                },
                {
                  "name": "worker",
                  "status": "not_called"
                }
              ],
              "status": "fail",
              "summary": "The orchestration scaffold stopped at a deterministic gate."
            },
            "warnings": [
              "job_orchestration_scaffold",
              "missing_approved_history",
              "orchestration_stopped_before_model_worker"
            ]
          },
          "type": "isolinear/v1/job/start",
          "version": 1
        },
        "orchestration": {
          "approved_entity_catalog_read": true,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_storage_written": false,
          "history_retrieval_scaffold_written": false,
          "home_assistant_history_called": false,
          "home_assistant_history_read": true,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "job_orchestration_scaffold_written": true,
          "job_state_scaffold_written": true,
          "model_provider_called": false,
          "retry_behavior_called": false,
          "semantic_memory_called": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        }
      },
      "entry_b_history_after": {
        "entity_ids": [
          "sensor.upstairs_temperature"
        ],
        "entry_id": "retry-entry-b",
        "last_time_range": {
          "end": "2026-06-08T12:00:00+00:00",
          "start": "2026-06-08T06:00:00+00:00"
        },
        "request_count": 1,
        "series_count": 1
      },
      "entry_b_history_before": {
        "entity_ids": [
          "sensor.upstairs_temperature"
        ],
        "entry_id": "retry-entry-b",
        "last_time_range": {
          "end": "2026-06-08T12:00:00+00:00",
          "start": "2026-06-08T06:00:00+00:00"
        },
        "request_count": 1,
        "series_count": 1
      },
      "entry_b_orchestration_store": {
        "entry_id": "retry-entry-b",
        "latest_history_entity_ids": [
          "sensor.upstairs_temperature"
        ],
        "latest_job_id": "retry-entry-b-job-001",
        "latest_requested_entity_ids": [
          "sensor.upstairs_temperature"
        ],
        "latest_result_code": "approved_history_ready",
        "run_count": 1,
        "run_ids": [
          "retry-entry-b-orchestration-run-001"
        ]
      },
      "entry_b_snapshot_validation": {
        "accepted": true,
        "code": "accepted",
        "failure_code": null,
        "job_id": "retry-entry-b-job-001",
        "progress_stage": "job_orchestration_scaffold_ready",
        "retry_allowed": null,
        "snapshot_id": "retry-entry-b-job-001-snapshot-003",
        "status": "planning"
      },
      "entry_b_start": {
        "accepted": true,
        "connection": {
          "errors": [],
          "results": [
            {
              "id": 31,
              "result": {
                "entities": [
                  {
                    "entity_id": "sensor.upstairs_temperature",
                    "label": "Upstairs Temperature"
                  }
                ],
                "job_id": "retry-entry-b-job-001",
                "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
                "progress": {
                  "message": "Approved history is staged for future planning.",
                  "stage": "job_orchestration_scaffold_ready"
                },
                "prompt": "Show sensor.upstairs_temperature",
                "snapshot_id": "retry-entry-b-job-001-snapshot-003",
                "state_label": "Ready",
                "status": "planning",
                "validation": {
                  "checks": [
                    {
                      "name": "integration_job_state_scaffold",
                      "status": "pass"
                    },
                    {
                      "name": "approved_entity_catalog",
                      "status": "pass"
                    },
                    {
                      "name": "approved_history_retrieval",
                      "status": "pass"
                    },
                    {
                      "name": "model_provider",
                      "status": "not_called"
                    },
                    {
                      "name": "worker",
                      "status": "not_called"
                    },
                    {
                      "name": "chart_rendering",
                      "status": "not_called"
                    }
                  ],
                  "status": "pass",
                  "summary": "The orchestration scaffold composed approved catalog, history, and job state."
                },
                "warnings": [
                  "job_orchestration_scaffold",
                  "model_provider_not_called",
                  "worker_not_called",
                  "chart_rendering_not_started"
                ]
              }
            }
          ]
        },
        "handler_called": true,
        "handler_result": {
          "accepted": true,
          "code": "registered_job_state_command_accepted",
          "config_entry_id": "retry-entry-b",
          "job_orchestration": {
            "run": {
              "entry_id": "retry-entry-b",
              "history_entity_ids": [
                "sensor.upstairs_temperature"
              ],
              "job_id": "retry-entry-b-job-001",
              "missing_entity_ids": [],
              "prompt": "Show sensor.upstairs_temperature",
              "rejected_entity_ids": [],
              "requested_entity_ids": [
                "sensor.upstairs_temperature"
              ],
              "result_code": "approved_history_ready",
              "run_id": "retry-entry-b-orchestration-run-001",
              "snapshot_ids": [
                "retry-entry-b-job-001-snapshot-001",
                "retry-entry-b-job-001-snapshot-002",
                "retry-entry-b-job-001-snapshot-003"
              ]
            }
          },
          "job_state": {
            "code": "job_orchestration_scaffold_ready",
            "job_id": "retry-entry-b-job-001",
            "subscription": null
          },
          "orchestration": {
            "approved_entity_catalog_read": true,
            "chart_artifact_written": false,
            "chart_rendering_called": false,
            "durable_storage_written": false,
            "history_retrieval_scaffold_written": true,
            "home_assistant_history_called": false,
            "home_assistant_history_read": true,
            "home_assistant_service_or_state_mutation_called": false,
            "job_orchestration_called": false,
            "job_orchestration_scaffold_written": true,
            "job_state_scaffold_written": true,
            "model_provider_called": false,
            "retry_behavior_called": false,
            "semantic_memory_called": false,
            "subscription_progress_streaming_called": false,
            "token_generated": false,
            "websocket_command_registered": false,
            "worker_called": false
          },
          "snapshot": {
            "entities": [
              {
                "entity_id": "sensor.upstairs_temperature",
                "label": "Upstairs Temperature"
              }
            ],
            "job_id": "retry-entry-b-job-001",
            "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
            "progress": {
              "message": "Approved history is staged for future planning.",
              "stage": "job_orchestration_scaffold_ready"
            },
            "prompt": "Show sensor.upstairs_temperature",
            "snapshot_id": "retry-entry-b-job-001-snapshot-003",
            "state_label": "Ready",
            "status": "planning",
            "validation": {
              "checks": [
                {
                  "name": "integration_job_state_scaffold",
                  "status": "pass"
                },
                {
                  "name": "approved_entity_catalog",
                  "status": "pass"
                },
                {
                  "name": "approved_history_retrieval",
                  "status": "pass"
                },
                {
                  "name": "model_provider",
                  "status": "not_called"
                },
                {
                  "name": "worker",
                  "status": "not_called"
                },
                {
                  "name": "chart_rendering",
                  "status": "not_called"
                }
              ],
              "status": "pass",
              "summary": "The orchestration scaffold composed approved catalog, history, and job state."
            },
            "warnings": [
              "job_orchestration_scaffold",
              "model_provider_not_called",
              "worker_not_called",
              "chart_rendering_not_started"
            ]
          },
          "type": "isolinear/v1/job/start",
          "version": 1
        },
        "orchestration": {
          "approved_entity_catalog_read": true,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_storage_written": false,
          "history_retrieval_scaffold_written": true,
          "home_assistant_history_called": false,
          "home_assistant_history_read": true,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "job_orchestration_scaffold_written": true,
          "job_state_scaffold_written": true,
          "model_provider_called": false,
          "retry_behavior_called": false,
          "semantic_memory_called": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        }
      },
      "error_codes": [
        "unknown_job"
      ]
    }
  },
  "when": {
    "operation": "retry_entry_a_job_from_entry_b"
  }
}
PASS cross_config_entry_retry_rejected
CASE valid_retries_stay_config_entry_scoped
{
  "case_id": "valid_retries_stay_config_entry_scoped",
  "given": {
    "entry_ids": [
      "valid-retry-entry-a",
      "valid-retry-entry-b"
    ]
  },
  "then": {
    "isolation": {
      "entry_a": {
        "history_store": {
          "entity_ids": [
            "sensor.upstairs_temperature"
          ],
          "entry_id": "valid-retry-entry-a",
          "last_time_range": {
            "end": "2026-06-08T12:00:00+00:00",
            "start": "2026-06-08T06:00:00+00:00"
          },
          "request_count": 1,
          "series_count": 1
        },
        "orchestration_store": {
          "entry_id": "valid-retry-entry-a",
          "latest_history_entity_ids": [
            "sensor.upstairs_temperature"
          ],
          "latest_job_id": "valid-retry-entry-a-job-001",
          "latest_requested_entity_ids": [
            "sensor.upstairs_temperature"
          ],
          "latest_result_code": "retry_approved_history_ready",
          "run_count": 2,
          "run_ids": [
            "valid-retry-entry-a-orchestration-run-001",
            "valid-retry-entry-a-orchestration-run-002"
          ]
        },
        "retry": {
          "accepted": true,
          "connection": {
            "errors": [],
            "results": [
              {
                "id": 42,
                "result": {
                  "entities": [
                    {
                      "entity_id": "sensor.upstairs_temperature",
                      "label": "Upstairs Temperature"
                    }
                  ],
                  "job_id": "valid-retry-entry-a-job-001",
                  "message": "Retry composed approved catalog and history for a later planning packet; model and worker calls are not implemented yet.",
                  "progress": {
                    "message": "Approved retry history is staged for future planning.",
                    "stage": "job_orchestration_retry_continuation_ready"
                  },
                  "prompt": "Show sensor.upstairs_temperature",
                  "snapshot_id": "valid-retry-entry-a-job-001-snapshot-006",
                  "state_label": "Ready",
                  "status": "planning",
                  "validation": {
                    "checks": [
                      {
                        "name": "integration_job_state_scaffold",
                        "status": "pass"
                      },
                      {
                        "name": "retry_command",
                        "status": "pass"
                      },
                      {
                        "name": "approved_entity_catalog",
                        "status": "pass"
                      },
                      {
                        "name": "approved_history_retrieval",
                        "status": "pass"
                      },
                      {
                        "name": "model_provider",
                        "status": "not_called"
                      },
                      {
                        "name": "worker",
                        "status": "not_called"
                      },
                      {
                        "name": "chart_rendering",
                        "status": "not_called"
                      }
                    ],
                    "status": "pass",
                    "summary": "The retry continuation scaffold composed approved catalog, history, and existing job state."
                  },
                  "warnings": [
                    "job_orchestration_retry_continuation_scaffold",
                    "model_provider_not_called",
                    "worker_not_called",
                    "chart_rendering_not_started"
                  ]
                }
              }
            ]
          },
          "handler_called": true,
          "handler_result": {
            "accepted": true,
            "code": "registered_job_state_command_accepted",
            "config_entry_id": "valid-retry-entry-a",
            "job_orchestration": {
              "run": {
                "entry_id": "valid-retry-entry-a",
                "history_entity_ids": [
                  "sensor.upstairs_temperature"
                ],
                "job_id": "valid-retry-entry-a-job-001",
                "missing_entity_ids": [],
                "prompt": "Show sensor.upstairs_temperature",
                "rejected_entity_ids": [],
                "requested_entity_ids": [
                  "sensor.upstairs_temperature"
                ],
                "result_code": "retry_approved_history_ready",
                "run_id": "valid-retry-entry-a-orchestration-run-002",
                "snapshot_ids": [
                  "valid-retry-entry-a-job-001-snapshot-001",
                  "valid-retry-entry-a-job-001-snapshot-002",
                  "valid-retry-entry-a-job-001-snapshot-003",
                  "valid-retry-entry-a-job-001-snapshot-004",
                  "valid-retry-entry-a-job-001-snapshot-005",
                  "valid-retry-entry-a-job-001-snapshot-006"
                ]
              }
            },
            "job_state": {
              "code": "job_orchestration_retry_continuation_ready",
              "job_id": "valid-retry-entry-a-job-001",
              "subscription": null
            },
            "orchestration": {
              "approved_entity_catalog_read": true,
              "chart_artifact_written": false,
              "chart_rendering_called": false,
              "durable_storage_written": false,
              "history_retrieval_scaffold_written": true,
              "home_assistant_history_called": false,
              "home_assistant_history_read": true,
              "home_assistant_service_or_state_mutation_called": false,
              "job_orchestration_called": false,
              "job_orchestration_scaffold_written": true,
              "job_state_scaffold_written": true,
              "model_provider_called": false,
              "retry_behavior_called": true,
              "semantic_memory_called": false,
              "subscription_progress_streaming_called": false,
              "token_generated": false,
              "websocket_command_registered": false,
              "worker_called": false
            },
            "snapshot": {
              "entities": [
                {
                  "entity_id": "sensor.upstairs_temperature",
                  "label": "Upstairs Temperature"
                }
              ],
              "job_id": "valid-retry-entry-a-job-001",
              "message": "Retry composed approved catalog and history for a later planning packet; model and worker calls are not implemented yet.",
              "progress": {
                "message": "Approved retry history is staged for future planning.",
                "stage": "job_orchestration_retry_continuation_ready"
              },
              "prompt": "Show sensor.upstairs_temperature",
              "snapshot_id": "valid-retry-entry-a-job-001-snapshot-006",
              "state_label": "Ready",
              "status": "planning",
              "validation": {
                "checks": [
                  {
                    "name": "integration_job_state_scaffold",
                    "status": "pass"
                  },
                  {
                    "name": "retry_command",
                    "status": "pass"
                  },
                  {
                    "name": "approved_entity_catalog",
                    "status": "pass"
                  },
                  {
                    "name": "approved_history_retrieval",
                    "status": "pass"
                  },
                  {
                    "name": "model_provider",
                    "status": "not_called"
                  },
                  {
                    "name": "worker",
                    "status": "not_called"
                  },
                  {
                    "name": "chart_rendering",
                    "status": "not_called"
                  }
                ],
                "status": "pass",
                "summary": "The retry continuation scaffold composed approved catalog, history, and existing job state."
              },
              "warnings": [
                "job_orchestration_retry_continuation_scaffold",
                "model_provider_not_called",
                "worker_not_called",
                "chart_rendering_not_started"
              ]
            },
            "type": "isolinear/v1/job/retry",
            "version": 1
          },
          "orchestration": {
            "approved_entity_catalog_read": true,
            "chart_artifact_written": false,
            "chart_rendering_called": false,
            "durable_storage_written": false,
            "history_retrieval_scaffold_written": true,
            "home_assistant_history_called": false,
            "home_assistant_history_read": true,
            "home_assistant_service_or_state_mutation_called": false,
            "job_orchestration_called": false,
            "job_orchestration_scaffold_written": true,
            "job_state_scaffold_written": true,
            "model_provider_called": false,
            "retry_behavior_called": true,
            "semantic_memory_called": false,
            "subscription_progress_streaming_called": false,
            "token_generated": false,
            "websocket_command_registered": false,
            "worker_called": false
          }
        },
        "run": {
          "entry_id": "valid-retry-entry-a",
          "history_entity_ids": [
            "sensor.upstairs_temperature"
          ],
          "job_id": "valid-retry-entry-a-job-001",
          "missing_entity_ids": [],
          "prompt": "Show sensor.upstairs_temperature",
          "rejected_entity_ids": [],
          "requested_entity_ids": [
            "sensor.upstairs_temperature"
          ],
          "result_code": "retry_approved_history_ready",
          "run_id": "valid-retry-entry-a-orchestration-run-002",
          "snapshot_ids": [
            "valid-retry-entry-a-job-001-snapshot-001",
            "valid-retry-entry-a-job-001-snapshot-002",
            "valid-retry-entry-a-job-001-snapshot-003",
            "valid-retry-entry-a-job-001-snapshot-004",
            "valid-retry-entry-a-job-001-snapshot-005",
            "valid-retry-entry-a-job-001-snapshot-006"
          ]
        },
        "snapshot": {
          "entities": [
            {
              "entity_id": "sensor.upstairs_temperature",
              "label": "Upstairs Temperature"
            }
          ],
          "job_id": "valid-retry-entry-a-job-001",
          "message": "Retry composed approved catalog and history for a later planning packet; model and worker calls are not implemented yet.",
          "progress": {
            "message": "Approved retry history is staged for future planning.",
            "stage": "job_orchestration_retry_continuation_ready"
          },
          "prompt": "Show sensor.upstairs_temperature",
          "snapshot_id": "valid-retry-entry-a-job-001-snapshot-006",
          "state_label": "Ready",
          "status": "planning",
          "validation": {
            "checks": [
              {
                "name": "integration_job_state_scaffold",
                "status": "pass"
              },
              {
                "name": "retry_command",
                "status": "pass"
              },
              {
                "name": "approved_entity_catalog",
                "status": "pass"
              },
              {
                "name": "approved_history_retrieval",
                "status": "pass"
              },
              {
                "name": "model_provider",
                "status": "not_called"
              },
              {
                "name": "worker",
                "status": "not_called"
              },
              {
                "name": "chart_rendering",
                "status": "not_called"
              }
            ],
            "status": "pass",
            "summary": "The retry continuation scaffold composed approved catalog, history, and existing job state."
          },
          "warnings": [
            "job_orchestration_retry_continuation_scaffold",
            "model_provider_not_called",
            "worker_not_called",
            "chart_rendering_not_started"
          ]
        },
        "snapshot_validation": [
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "valid-retry-entry-a-job-001",
            "progress_stage": "job_state_scaffold",
            "retry_allowed": null,
            "snapshot_id": "valid-retry-entry-a-job-001-snapshot-001",
            "status": "planning"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "valid-retry-entry-a-job-001",
            "progress_stage": "approved_history_retrieval",
            "retry_allowed": null,
            "snapshot_id": "valid-retry-entry-a-job-001-snapshot-002",
            "status": "fetching_history"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": "missing_approved_history",
            "job_id": "valid-retry-entry-a-job-001",
            "progress_stage": "job_orchestration_scaffold_failed",
            "retry_allowed": true,
            "snapshot_id": "valid-retry-entry-a-job-001-snapshot-003",
            "status": "failed"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "valid-retry-entry-a-job-001",
            "progress_stage": "job_orchestration_retry_accepted",
            "retry_allowed": null,
            "snapshot_id": "valid-retry-entry-a-job-001-snapshot-004",
            "status": "planning"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "valid-retry-entry-a-job-001",
            "progress_stage": "approved_history_retrieval",
            "retry_allowed": null,
            "snapshot_id": "valid-retry-entry-a-job-001-snapshot-005",
            "status": "fetching_history"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "valid-retry-entry-a-job-001",
            "progress_stage": "job_orchestration_retry_continuation_ready",
            "retry_allowed": null,
            "snapshot_id": "valid-retry-entry-a-job-001-snapshot-006",
            "status": "planning"
          }
        ],
        "start": {
          "accepted": true,
          "connection": {
            "errors": [],
            "results": [
              {
                "id": 40,
                "result": {
                  "failure": {
                    "code": "missing_approved_history",
                    "message": "Approved history is missing for: sensor.upstairs_temperature.",
                    "stage": "approved_history_retrieval"
                  },
                  "job_id": "valid-retry-entry-a-job-001",
                  "message": "Approved history is missing for: sensor.upstairs_temperature.",
                  "progress": {
                    "message": "Approved history is missing for: sensor.upstairs_temperature.",
                    "stage": "job_orchestration_scaffold_failed"
                  },
                  "prompt": "Show sensor.upstairs_temperature",
                  "retry_allowed": true,
                  "snapshot_id": "valid-retry-entry-a-job-001-snapshot-003",
                  "state_label": "Failed",
                  "status": "failed",
                  "validation": {
                    "checks": [
                      {
                        "name": "integration_job_state_scaffold",
                        "status": "pass"
                      },
                      {
                        "name": "approved_entity_catalog",
                        "status": "pass"
                      },
                      {
                        "name": "approved_history_retrieval",
                        "status": "fail"
                      },
                      {
                        "name": "model_provider",
                        "status": "not_called"
                      },
                      {
                        "name": "worker",
                        "status": "not_called"
                      }
                    ],
                    "status": "fail",
                    "summary": "The orchestration scaffold stopped at a deterministic gate."
                  },
                  "warnings": [
                    "job_orchestration_scaffold",
                    "missing_approved_history",
                    "orchestration_stopped_before_model_worker"
                  ]
                }
              }
            ]
          },
          "handler_called": true,
          "handler_result": {
            "accepted": true,
            "code": "registered_job_state_command_accepted",
            "config_entry_id": "valid-retry-entry-a",
            "job_orchestration": {
              "run": {
                "entry_id": "valid-retry-entry-a",
                "history_entity_ids": [],
                "job_id": "valid-retry-entry-a-job-001",
                "missing_entity_ids": [
                  "sensor.upstairs_temperature"
                ],
                "prompt": "Show sensor.upstairs_temperature",
                "rejected_entity_ids": [],
                "requested_entity_ids": [
                  "sensor.upstairs_temperature"
                ],
                "result_code": "missing_approved_history",
                "run_id": "valid-retry-entry-a-orchestration-run-001",
                "snapshot_ids": [
                  "valid-retry-entry-a-job-001-snapshot-001",
                  "valid-retry-entry-a-job-001-snapshot-002",
                  "valid-retry-entry-a-job-001-snapshot-003"
                ]
              }
            },
            "job_state": {
              "code": "job_orchestration_scaffold_failed",
              "job_id": "valid-retry-entry-a-job-001",
              "subscription": null
            },
            "orchestration": {
              "approved_entity_catalog_read": true,
              "chart_artifact_written": false,
              "chart_rendering_called": false,
              "durable_storage_written": false,
              "history_retrieval_scaffold_written": false,
              "home_assistant_history_called": false,
              "home_assistant_history_read": true,
              "home_assistant_service_or_state_mutation_called": false,
              "job_orchestration_called": false,
              "job_orchestration_scaffold_written": true,
              "job_state_scaffold_written": true,
              "model_provider_called": false,
              "retry_behavior_called": false,
              "semantic_memory_called": false,
              "subscription_progress_streaming_called": false,
              "token_generated": false,
              "websocket_command_registered": false,
              "worker_called": false
            },
            "snapshot": {
              "failure": {
                "code": "missing_approved_history",
                "message": "Approved history is missing for: sensor.upstairs_temperature.",
                "stage": "approved_history_retrieval"
              },
              "job_id": "valid-retry-entry-a-job-001",
              "message": "Approved history is missing for: sensor.upstairs_temperature.",
              "progress": {
                "message": "Approved history is missing for: sensor.upstairs_temperature.",
                "stage": "job_orchestration_scaffold_failed"
              },
              "prompt": "Show sensor.upstairs_temperature",
              "retry_allowed": true,
              "snapshot_id": "valid-retry-entry-a-job-001-snapshot-003",
              "state_label": "Failed",
              "status": "failed",
              "validation": {
                "checks": [
                  {
                    "name": "integration_job_state_scaffold",
                    "status": "pass"
                  },
                  {
                    "name": "approved_entity_catalog",
                    "status": "pass"
                  },
                  {
                    "name": "approved_history_retrieval",
                    "status": "fail"
                  },
                  {
                    "name": "model_provider",
                    "status": "not_called"
                  },
                  {
                    "name": "worker",
                    "status": "not_called"
                  }
                ],
                "status": "fail",
                "summary": "The orchestration scaffold stopped at a deterministic gate."
              },
              "warnings": [
                "job_orchestration_scaffold",
                "missing_approved_history",
                "orchestration_stopped_before_model_worker"
              ]
            },
            "type": "isolinear/v1/job/start",
            "version": 1
          },
          "orchestration": {
            "approved_entity_catalog_read": true,
            "chart_artifact_written": false,
            "chart_rendering_called": false,
            "durable_storage_written": false,
            "history_retrieval_scaffold_written": false,
            "home_assistant_history_called": false,
            "home_assistant_history_read": true,
            "home_assistant_service_or_state_mutation_called": false,
            "job_orchestration_called": false,
            "job_orchestration_scaffold_written": true,
            "job_state_scaffold_written": true,
            "model_provider_called": false,
            "retry_behavior_called": false,
            "semantic_memory_called": false,
            "subscription_progress_streaming_called": false,
            "token_generated": false,
            "websocket_command_registered": false,
            "worker_called": false
          }
        }
      },
      "entry_b": {
        "history_store": {
          "entity_ids": [
            "binary_sensor.office_window"
          ],
          "entry_id": "valid-retry-entry-b",
          "last_time_range": {
            "end": "2026-06-08T12:00:00+00:00",
            "start": "2026-06-08T06:00:00+00:00"
          },
          "request_count": 1,
          "series_count": 1
        },
        "orchestration_store": {
          "entry_id": "valid-retry-entry-b",
          "latest_history_entity_ids": [
            "binary_sensor.office_window"
          ],
          "latest_job_id": "valid-retry-entry-b-job-001",
          "latest_requested_entity_ids": [
            "binary_sensor.office_window"
          ],
          "latest_result_code": "retry_approved_history_ready",
          "run_count": 2,
          "run_ids": [
            "valid-retry-entry-b-orchestration-run-001",
            "valid-retry-entry-b-orchestration-run-002"
          ]
        },
        "retry": {
          "accepted": true,
          "connection": {
            "errors": [],
            "results": [
              {
                "id": 43,
                "result": {
                  "entities": [
                    {
                      "entity_id": "binary_sensor.office_window",
                      "label": "Office Window"
                    }
                  ],
                  "job_id": "valid-retry-entry-b-job-001",
                  "message": "Retry composed approved catalog and history for a later planning packet; model and worker calls are not implemented yet.",
                  "progress": {
                    "message": "Approved retry history is staged for future planning.",
                    "stage": "job_orchestration_retry_continuation_ready"
                  },
                  "prompt": "Show binary_sensor.office_window",
                  "snapshot_id": "valid-retry-entry-b-job-001-snapshot-006",
                  "state_label": "Ready",
                  "status": "planning",
                  "validation": {
                    "checks": [
                      {
                        "name": "integration_job_state_scaffold",
                        "status": "pass"
                      },
                      {
                        "name": "retry_command",
                        "status": "pass"
                      },
                      {
                        "name": "approved_entity_catalog",
                        "status": "pass"
                      },
                      {
                        "name": "approved_history_retrieval",
                        "status": "pass"
                      },
                      {
                        "name": "model_provider",
                        "status": "not_called"
                      },
                      {
                        "name": "worker",
                        "status": "not_called"
                      },
                      {
                        "name": "chart_rendering",
                        "status": "not_called"
                      }
                    ],
                    "status": "pass",
                    "summary": "The retry continuation scaffold composed approved catalog, history, and existing job state."
                  },
                  "warnings": [
                    "job_orchestration_retry_continuation_scaffold",
                    "model_provider_not_called",
                    "worker_not_called",
                    "chart_rendering_not_started"
                  ]
                }
              }
            ]
          },
          "handler_called": true,
          "handler_result": {
            "accepted": true,
            "code": "registered_job_state_command_accepted",
            "config_entry_id": "valid-retry-entry-b",
            "job_orchestration": {
              "run": {
                "entry_id": "valid-retry-entry-b",
                "history_entity_ids": [
                  "binary_sensor.office_window"
                ],
                "job_id": "valid-retry-entry-b-job-001",
                "missing_entity_ids": [],
                "prompt": "Show binary_sensor.office_window",
                "rejected_entity_ids": [],
                "requested_entity_ids": [
                  "binary_sensor.office_window"
                ],
                "result_code": "retry_approved_history_ready",
                "run_id": "valid-retry-entry-b-orchestration-run-002",
                "snapshot_ids": [
                  "valid-retry-entry-b-job-001-snapshot-001",
                  "valid-retry-entry-b-job-001-snapshot-002",
                  "valid-retry-entry-b-job-001-snapshot-003",
                  "valid-retry-entry-b-job-001-snapshot-004",
                  "valid-retry-entry-b-job-001-snapshot-005",
                  "valid-retry-entry-b-job-001-snapshot-006"
                ]
              }
            },
            "job_state": {
              "code": "job_orchestration_retry_continuation_ready",
              "job_id": "valid-retry-entry-b-job-001",
              "subscription": null
            },
            "orchestration": {
              "approved_entity_catalog_read": true,
              "chart_artifact_written": false,
              "chart_rendering_called": false,
              "durable_storage_written": false,
              "history_retrieval_scaffold_written": true,
              "home_assistant_history_called": false,
              "home_assistant_history_read": true,
              "home_assistant_service_or_state_mutation_called": false,
              "job_orchestration_called": false,
              "job_orchestration_scaffold_written": true,
              "job_state_scaffold_written": true,
              "model_provider_called": false,
              "retry_behavior_called": true,
              "semantic_memory_called": false,
              "subscription_progress_streaming_called": false,
              "token_generated": false,
              "websocket_command_registered": false,
              "worker_called": false
            },
            "snapshot": {
              "entities": [
                {
                  "entity_id": "binary_sensor.office_window",
                  "label": "Office Window"
                }
              ],
              "job_id": "valid-retry-entry-b-job-001",
              "message": "Retry composed approved catalog and history for a later planning packet; model and worker calls are not implemented yet.",
              "progress": {
                "message": "Approved retry history is staged for future planning.",
                "stage": "job_orchestration_retry_continuation_ready"
              },
              "prompt": "Show binary_sensor.office_window",
              "snapshot_id": "valid-retry-entry-b-job-001-snapshot-006",
              "state_label": "Ready",
              "status": "planning",
              "validation": {
                "checks": [
                  {
                    "name": "integration_job_state_scaffold",
                    "status": "pass"
                  },
                  {
                    "name": "retry_command",
                    "status": "pass"
                  },
                  {
                    "name": "approved_entity_catalog",
                    "status": "pass"
                  },
                  {
                    "name": "approved_history_retrieval",
                    "status": "pass"
                  },
                  {
                    "name": "model_provider",
                    "status": "not_called"
                  },
                  {
                    "name": "worker",
                    "status": "not_called"
                  },
                  {
                    "name": "chart_rendering",
                    "status": "not_called"
                  }
                ],
                "status": "pass",
                "summary": "The retry continuation scaffold composed approved catalog, history, and existing job state."
              },
              "warnings": [
                "job_orchestration_retry_continuation_scaffold",
                "model_provider_not_called",
                "worker_not_called",
                "chart_rendering_not_started"
              ]
            },
            "type": "isolinear/v1/job/retry",
            "version": 1
          },
          "orchestration": {
            "approved_entity_catalog_read": true,
            "chart_artifact_written": false,
            "chart_rendering_called": false,
            "durable_storage_written": false,
            "history_retrieval_scaffold_written": true,
            "home_assistant_history_called": false,
            "home_assistant_history_read": true,
            "home_assistant_service_or_state_mutation_called": false,
            "job_orchestration_called": false,
            "job_orchestration_scaffold_written": true,
            "job_state_scaffold_written": true,
            "model_provider_called": false,
            "retry_behavior_called": true,
            "semantic_memory_called": false,
            "subscription_progress_streaming_called": false,
            "token_generated": false,
            "websocket_command_registered": false,
            "worker_called": false
          }
        },
        "run": {
          "entry_id": "valid-retry-entry-b",
          "history_entity_ids": [
            "binary_sensor.office_window"
          ],
          "job_id": "valid-retry-entry-b-job-001",
          "missing_entity_ids": [],
          "prompt": "Show binary_sensor.office_window",
          "rejected_entity_ids": [],
          "requested_entity_ids": [
            "binary_sensor.office_window"
          ],
          "result_code": "retry_approved_history_ready",
          "run_id": "valid-retry-entry-b-orchestration-run-002",
          "snapshot_ids": [
            "valid-retry-entry-b-job-001-snapshot-001",
            "valid-retry-entry-b-job-001-snapshot-002",
            "valid-retry-entry-b-job-001-snapshot-003",
            "valid-retry-entry-b-job-001-snapshot-004",
            "valid-retry-entry-b-job-001-snapshot-005",
            "valid-retry-entry-b-job-001-snapshot-006"
          ]
        },
        "snapshot": {
          "entities": [
            {
              "entity_id": "binary_sensor.office_window",
              "label": "Office Window"
            }
          ],
          "job_id": "valid-retry-entry-b-job-001",
          "message": "Retry composed approved catalog and history for a later planning packet; model and worker calls are not implemented yet.",
          "progress": {
            "message": "Approved retry history is staged for future planning.",
            "stage": "job_orchestration_retry_continuation_ready"
          },
          "prompt": "Show binary_sensor.office_window",
          "snapshot_id": "valid-retry-entry-b-job-001-snapshot-006",
          "state_label": "Ready",
          "status": "planning",
          "validation": {
            "checks": [
              {
                "name": "integration_job_state_scaffold",
                "status": "pass"
              },
              {
                "name": "retry_command",
                "status": "pass"
              },
              {
                "name": "approved_entity_catalog",
                "status": "pass"
              },
              {
                "name": "approved_history_retrieval",
                "status": "pass"
              },
              {
                "name": "model_provider",
                "status": "not_called"
              },
              {
                "name": "worker",
                "status": "not_called"
              },
              {
                "name": "chart_rendering",
                "status": "not_called"
              }
            ],
            "status": "pass",
            "summary": "The retry continuation scaffold composed approved catalog, history, and existing job state."
          },
          "warnings": [
            "job_orchestration_retry_continuation_scaffold",
            "model_provider_not_called",
            "worker_not_called",
            "chart_rendering_not_started"
          ]
        },
        "snapshot_validation": [
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "valid-retry-entry-b-job-001",
            "progress_stage": "job_state_scaffold",
            "retry_allowed": null,
            "snapshot_id": "valid-retry-entry-b-job-001-snapshot-001",
            "status": "planning"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "valid-retry-entry-b-job-001",
            "progress_stage": "approved_history_retrieval",
            "retry_allowed": null,
            "snapshot_id": "valid-retry-entry-b-job-001-snapshot-002",
            "status": "fetching_history"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": "missing_approved_history",
            "job_id": "valid-retry-entry-b-job-001",
            "progress_stage": "job_orchestration_scaffold_failed",
            "retry_allowed": true,
            "snapshot_id": "valid-retry-entry-b-job-001-snapshot-003",
            "status": "failed"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "valid-retry-entry-b-job-001",
            "progress_stage": "job_orchestration_retry_accepted",
            "retry_allowed": null,
            "snapshot_id": "valid-retry-entry-b-job-001-snapshot-004",
            "status": "planning"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "valid-retry-entry-b-job-001",
            "progress_stage": "approved_history_retrieval",
            "retry_allowed": null,
            "snapshot_id": "valid-retry-entry-b-job-001-snapshot-005",
            "status": "fetching_history"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "valid-retry-entry-b-job-001",
            "progress_stage": "job_orchestration_retry_continuation_ready",
            "retry_allowed": null,
            "snapshot_id": "valid-retry-entry-b-job-001-snapshot-006",
            "status": "planning"
          }
        ],
        "start": {
          "accepted": true,
          "connection": {
            "errors": [],
            "results": [
              {
                "id": 41,
                "result": {
                  "failure": {
                    "code": "missing_approved_history",
                    "message": "Approved history is missing for: binary_sensor.office_window.",
                    "stage": "approved_history_retrieval"
                  },
                  "job_id": "valid-retry-entry-b-job-001",
                  "message": "Approved history is missing for: binary_sensor.office_window.",
                  "progress": {
                    "message": "Approved history is missing for: binary_sensor.office_window.",
                    "stage": "job_orchestration_scaffold_failed"
                  },
                  "prompt": "Show binary_sensor.office_window",
                  "retry_allowed": true,
                  "snapshot_id": "valid-retry-entry-b-job-001-snapshot-003",
                  "state_label": "Failed",
                  "status": "failed",
                  "validation": {
                    "checks": [
                      {
                        "name": "integration_job_state_scaffold",
                        "status": "pass"
                      },
                      {
                        "name": "approved_entity_catalog",
                        "status": "pass"
                      },
                      {
                        "name": "approved_history_retrieval",
                        "status": "fail"
                      },
                      {
                        "name": "model_provider",
                        "status": "not_called"
                      },
                      {
                        "name": "worker",
                        "status": "not_called"
                      }
                    ],
                    "status": "fail",
                    "summary": "The orchestration scaffold stopped at a deterministic gate."
                  },
                  "warnings": [
                    "job_orchestration_scaffold",
                    "missing_approved_history",
                    "orchestration_stopped_before_model_worker"
                  ]
                }
              }
            ]
          },
          "handler_called": true,
          "handler_result": {
            "accepted": true,
            "code": "registered_job_state_command_accepted",
            "config_entry_id": "valid-retry-entry-b",
            "job_orchestration": {
              "run": {
                "entry_id": "valid-retry-entry-b",
                "history_entity_ids": [],
                "job_id": "valid-retry-entry-b-job-001",
                "missing_entity_ids": [
                  "binary_sensor.office_window"
                ],
                "prompt": "Show binary_sensor.office_window",
                "rejected_entity_ids": [],
                "requested_entity_ids": [
                  "binary_sensor.office_window"
                ],
                "result_code": "missing_approved_history",
                "run_id": "valid-retry-entry-b-orchestration-run-001",
                "snapshot_ids": [
                  "valid-retry-entry-b-job-001-snapshot-001",
                  "valid-retry-entry-b-job-001-snapshot-002",
                  "valid-retry-entry-b-job-001-snapshot-003"
                ]
              }
            },
            "job_state": {
              "code": "job_orchestration_scaffold_failed",
              "job_id": "valid-retry-entry-b-job-001",
              "subscription": null
            },
            "orchestration": {
              "approved_entity_catalog_read": true,
              "chart_artifact_written": false,
              "chart_rendering_called": false,
              "durable_storage_written": false,
              "history_retrieval_scaffold_written": false,
              "home_assistant_history_called": false,
              "home_assistant_history_read": true,
              "home_assistant_service_or_state_mutation_called": false,
              "job_orchestration_called": false,
              "job_orchestration_scaffold_written": true,
              "job_state_scaffold_written": true,
              "model_provider_called": false,
              "retry_behavior_called": false,
              "semantic_memory_called": false,
              "subscription_progress_streaming_called": false,
              "token_generated": false,
              "websocket_command_registered": false,
              "worker_called": false
            },
            "snapshot": {
              "failure": {
                "code": "missing_approved_history",
                "message": "Approved history is missing for: binary_sensor.office_window.",
                "stage": "approved_history_retrieval"
              },
              "job_id": "valid-retry-entry-b-job-001",
              "message": "Approved history is missing for: binary_sensor.office_window.",
              "progress": {
                "message": "Approved history is missing for: binary_sensor.office_window.",
                "stage": "job_orchestration_scaffold_failed"
              },
              "prompt": "Show binary_sensor.office_window",
              "retry_allowed": true,
              "snapshot_id": "valid-retry-entry-b-job-001-snapshot-003",
              "state_label": "Failed",
              "status": "failed",
              "validation": {
                "checks": [
                  {
                    "name": "integration_job_state_scaffold",
                    "status": "pass"
                  },
                  {
                    "name": "approved_entity_catalog",
                    "status": "pass"
                  },
                  {
                    "name": "approved_history_retrieval",
                    "status": "fail"
                  },
                  {
                    "name": "model_provider",
                    "status": "not_called"
                  },
                  {
                    "name": "worker",
                    "status": "not_called"
                  }
                ],
                "status": "fail",
                "summary": "The orchestration scaffold stopped at a deterministic gate."
              },
              "warnings": [
                "job_orchestration_scaffold",
                "missing_approved_history",
                "orchestration_stopped_before_model_worker"
              ]
            },
            "type": "isolinear/v1/job/start",
            "version": 1
          },
          "orchestration": {
            "approved_entity_catalog_read": true,
            "chart_artifact_written": false,
            "chart_rendering_called": false,
            "durable_storage_written": false,
            "history_retrieval_scaffold_written": false,
            "home_assistant_history_called": false,
            "home_assistant_history_read": true,
            "home_assistant_service_or_state_mutation_called": false,
            "job_orchestration_called": false,
            "job_orchestration_scaffold_written": true,
            "job_state_scaffold_written": true,
            "model_provider_called": false,
            "retry_behavior_called": false,
            "semantic_memory_called": false,
            "subscription_progress_streaming_called": false,
            "token_generated": false,
            "websocket_command_registered": false,
            "worker_called": false
          }
        }
      }
    }
  },
  "when": {
    "operation": "retry_each_entry_own_failed_job"
  }
}
PASS valid_retries_stay_config_entry_scoped
CASE retry_snapshots_validate_before_storage
{
  "case_id": "retry_snapshots_validate_before_storage",
  "given": {
    "schema": "docs/schemas/integration-job-snapshot.schema.json"
  },
  "then": {
    "snapshot_validation": {
      "isolation_entry_a": {
        "all_snapshots_valid": true,
        "snapshot_validation": [
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "valid-retry-entry-a-job-001",
            "progress_stage": "job_state_scaffold",
            "retry_allowed": null,
            "snapshot_id": "valid-retry-entry-a-job-001-snapshot-001",
            "status": "planning"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "valid-retry-entry-a-job-001",
            "progress_stage": "approved_history_retrieval",
            "retry_allowed": null,
            "snapshot_id": "valid-retry-entry-a-job-001-snapshot-002",
            "status": "fetching_history"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": "missing_approved_history",
            "job_id": "valid-retry-entry-a-job-001",
            "progress_stage": "job_orchestration_scaffold_failed",
            "retry_allowed": true,
            "snapshot_id": "valid-retry-entry-a-job-001-snapshot-003",
            "status": "failed"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "valid-retry-entry-a-job-001",
            "progress_stage": "job_orchestration_retry_accepted",
            "retry_allowed": null,
            "snapshot_id": "valid-retry-entry-a-job-001-snapshot-004",
            "status": "planning"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "valid-retry-entry-a-job-001",
            "progress_stage": "approved_history_retrieval",
            "retry_allowed": null,
            "snapshot_id": "valid-retry-entry-a-job-001-snapshot-005",
            "status": "fetching_history"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "valid-retry-entry-a-job-001",
            "progress_stage": "job_orchestration_retry_continuation_ready",
            "retry_allowed": null,
            "snapshot_id": "valid-retry-entry-a-job-001-snapshot-006",
            "status": "planning"
          }
        ]
      },
      "isolation_entry_b": {
        "all_snapshots_valid": true,
        "snapshot_validation": [
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "valid-retry-entry-b-job-001",
            "progress_stage": "job_state_scaffold",
            "retry_allowed": null,
            "snapshot_id": "valid-retry-entry-b-job-001-snapshot-001",
            "status": "planning"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "valid-retry-entry-b-job-001",
            "progress_stage": "approved_history_retrieval",
            "retry_allowed": null,
            "snapshot_id": "valid-retry-entry-b-job-001-snapshot-002",
            "status": "fetching_history"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": "missing_approved_history",
            "job_id": "valid-retry-entry-b-job-001",
            "progress_stage": "job_orchestration_scaffold_failed",
            "retry_allowed": true,
            "snapshot_id": "valid-retry-entry-b-job-001-snapshot-003",
            "status": "failed"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "valid-retry-entry-b-job-001",
            "progress_stage": "job_orchestration_retry_accepted",
            "retry_allowed": null,
            "snapshot_id": "valid-retry-entry-b-job-001-snapshot-004",
            "status": "planning"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "valid-retry-entry-b-job-001",
            "progress_stage": "approved_history_retrieval",
            "retry_allowed": null,
            "snapshot_id": "valid-retry-entry-b-job-001-snapshot-005",
            "status": "fetching_history"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "valid-retry-entry-b-job-001",
            "progress_stage": "job_orchestration_retry_continuation_ready",
            "retry_allowed": null,
            "snapshot_id": "valid-retry-entry-b-job-001-snapshot-006",
            "status": "planning"
          }
        ]
      },
      "success": {
        "all_snapshots_valid": true,
        "snapshot_validation": [
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "retry-entry-job-001",
            "progress_stage": "job_state_scaffold",
            "retry_allowed": null,
            "snapshot_id": "retry-entry-job-001-snapshot-001",
            "status": "planning"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "retry-entry-job-001",
            "progress_stage": "approved_history_retrieval",
            "retry_allowed": null,
            "snapshot_id": "retry-entry-job-001-snapshot-002",
            "status": "fetching_history"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": "missing_approved_history",
            "job_id": "retry-entry-job-001",
            "progress_stage": "job_orchestration_scaffold_failed",
            "retry_allowed": true,
            "snapshot_id": "retry-entry-job-001-snapshot-003",
            "status": "failed"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "retry-entry-job-001",
            "progress_stage": "job_orchestration_retry_accepted",
            "retry_allowed": null,
            "snapshot_id": "retry-entry-job-001-snapshot-004",
            "status": "planning"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "retry-entry-job-001",
            "progress_stage": "approved_history_retrieval",
            "retry_allowed": null,
            "snapshot_id": "retry-entry-job-001-snapshot-005",
            "status": "fetching_history"
          },
          {
            "accepted": true,
            "code": "accepted",
            "failure_code": null,
            "job_id": "retry-entry-job-001",
            "progress_stage": "job_orchestration_retry_continuation_ready",
            "retry_allowed": null,
            "snapshot_id": "retry-entry-job-001-snapshot-006",
            "status": "planning"
          }
        ]
      }
    }
  },
  "when": {
    "operation": "validate_observed_retry_snapshots"
  }
}
PASS retry_snapshots_validate_before_storage
CASE retry_continuation_remains_bounded
{
  "case_id": "retry_continuation_remains_bounded",
  "given": {
    "handled_surfaces": [
      "accepted_retry",
      "unknown_job_failure",
      "non_retryable_failure",
      "cross_config_entry_failure",
      "config_entry_isolation"
    ]
  },
  "then": {
    "side_effects": {
      "allowed_aggregate": {
        "approved_entity_catalog_read": true,
        "history_retrieval_scaffold_written": true,
        "home_assistant_history_read": true,
        "job_orchestration_scaffold_written": true,
        "job_state_scaffold_written": true,
        "retry_behavior_called": true,
        "websocket_command_registered": true
      },
      "expected_forbidden": {
        "chart_artifact_written": false,
        "chart_rendering_called": false,
        "durable_storage_written": false,
        "home_assistant_history_called": false,
        "home_assistant_service_or_state_mutation_called": false,
        "job_orchestration_called": false,
        "model_provider_called": false,
        "semantic_memory_called": false,
        "subscription_progress_streaming_called": false,
        "token_generated": false,
        "worker_called": false
      },
      "forbidden_aggregate": {
        "chart_artifact_written": false,
        "chart_rendering_called": false,
        "durable_storage_written": false,
        "home_assistant_history_called": false,
        "home_assistant_service_or_state_mutation_called": false,
        "job_orchestration_called": false,
        "model_provider_called": false,
        "semantic_memory_called": false,
        "subscription_progress_streaming_called": false,
        "token_generated": false,
        "worker_called": false
      },
      "observed": [
        {
          "approved_entity_catalog_read": true,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_storage_written": false,
          "history_retrieval_scaffold_written": true,
          "home_assistant_history_called": false,
          "home_assistant_history_read": true,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "job_orchestration_scaffold_written": true,
          "job_state_scaffold_written": true,
          "model_provider_called": false,
          "name": "accepted_retry",
          "retry_behavior_called": true,
          "semantic_memory_called": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        },
        {
          "approved_entity_catalog_read": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_storage_written": false,
          "history_retrieval_scaffold_written": false,
          "home_assistant_history_called": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "job_orchestration_scaffold_written": false,
          "job_state_scaffold_written": false,
          "model_provider_called": false,
          "name": "unknown_retry_job",
          "retry_behavior_called": false,
          "semantic_memory_called": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        },
        {
          "approved_entity_catalog_read": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_storage_written": false,
          "history_retrieval_scaffold_written": false,
          "home_assistant_history_called": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "job_orchestration_scaffold_written": true,
          "job_state_scaffold_written": false,
          "model_provider_called": false,
          "name": "non_retryable_job",
          "retry_behavior_called": false,
          "semantic_memory_called": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        },
        {
          "approved_entity_catalog_read": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_storage_written": false,
          "history_retrieval_scaffold_written": false,
          "home_assistant_history_called": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "job_orchestration_scaffold_written": false,
          "job_state_scaffold_written": false,
          "model_provider_called": false,
          "name": "cross_config_entry",
          "retry_behavior_called": false,
          "semantic_memory_called": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        },
        {
          "approved_entity_catalog_read": true,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_storage_written": false,
          "history_retrieval_scaffold_written": true,
          "home_assistant_history_called": false,
          "home_assistant_history_read": true,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "job_orchestration_scaffold_written": true,
          "job_state_scaffold_written": true,
          "model_provider_called": false,
          "name": "entry_a_retry",
          "retry_behavior_called": true,
          "semantic_memory_called": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        },
        {
          "approved_entity_catalog_read": true,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_storage_written": false,
          "history_retrieval_scaffold_written": true,
          "home_assistant_history_called": false,
          "home_assistant_history_read": true,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "job_orchestration_scaffold_written": true,
          "job_state_scaffold_written": true,
          "model_provider_called": false,
          "name": "entry_b_retry",
          "retry_behavior_called": true,
          "semantic_memory_called": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        },
        {
          "approved_entity_catalog_read": true,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_storage_written": false,
          "history_retrieval_scaffold_written": false,
          "home_assistant_history_called": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "job_orchestration_scaffold_written": false,
          "job_state_scaffold_written": false,
          "model_provider_called": false,
          "name": "setup_orchestration",
          "retry_behavior_called": false,
          "semantic_memory_called": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        },
        {
          "dashboard_resource_metadata_written_or_reused": false,
          "home_assistant_history_called": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "model_provider_called": false,
          "name": "websocket_registration",
          "semantic_memory_called": false,
          "token_generated": false,
          "websocket_command_registered": true,
          "worker_called": false
        }
      ]
    }
  },
  "when": {
    "operation": "aggregate_observed_side_effects"
  }
}
PASS retry_continuation_remains_bounded
PASS home_assistant_job_orchestration_retry_continuation_scaffold
