# Home Assistant Job Orchestration Subscription Progress Streaming Scaffold Evidence

Run timestamp: 2026-06-08T21:39:45+00:00

BDD file:
`bdd/integration/home-assistant-job-orchestration-subscription-progress-streaming-scaffold-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: accepted subscribe records latest progress event -> `CASE accepted_subscribe_records_latest_progress_event`
- Scenario B: unknown job fails before subscription side effects -> `CASE unknown_job_fails_before_subscription_storage`
- Scenario C: config entries cannot subscribe to each other's jobs -> `CASE cross_config_entry_subscription_rejected`
- Scenario D: valid subscriptions stay config-entry scoped -> `CASE valid_subscriptions_stay_config_entry_scoped`
- Scenario E: progress event snapshots validate before storage -> `CASE subscription_progress_snapshots_validate_before_storage`
- Scenario F: subscription/progress scaffold remains bounded -> `CASE subscription_progress_remains_bounded`

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_subscription_progress_scaffold.py
```

Raw output:

```text
CASE accepted_subscribe_records_latest_progress_event
{
  "case_id": "accepted_subscribe_records_latest_progress_event",
  "given": {
    "config_entry_id": "subscription-entry",
    "run_timestamp": "2026-06-08T21:39:46+00:00",
    "schema": "docs/schemas/integration-job-snapshot.schema.json"
  },
  "then": {
    "accepted": {
      "job_store": {
        "entry_id": "subscription-entry",
        "job_ids": [
          "subscription-entry-job-001"
        ],
        "latest_snapshot_ids": [
          "subscription-entry-job-001-snapshot-003"
        ],
        "next_job_number": 2,
        "subscription_count": 1,
        "subscription_ids": [
          "subscription-entry-job-001-subscription-001"
        ]
      },
      "latest_snapshot_returned": true,
      "orchestration_store": {
        "entry_id": "subscription-entry",
        "latest_history_entity_ids": [
          "sensor.upstairs_temperature"
        ],
        "latest_job_id": "subscription-entry-job-001",
        "latest_progress_event_id": "subscription-entry-progress-event-001",
        "latest_progress_snapshot_id": "subscription-entry-job-001-snapshot-003",
        "latest_requested_entity_ids": [
          "sensor.upstairs_temperature"
        ],
        "latest_result_code": "approved_history_ready",
        "progress_event_count": 1,
        "progress_event_ids": [
          "subscription-entry-progress-event-001"
        ],
        "run_count": 1,
        "run_ids": [
          "subscription-entry-orchestration-run-001"
        ]
      },
      "progress_event": {
        "config_entry_id": "subscription-entry",
        "event_id": "subscription-entry-progress-event-001",
        "job_id": "subscription-entry-job-001",
        "message_id": 2,
        "progress": {
          "message": "Approved history is staged for future planning.",
          "stage": "job_orchestration_scaffold_ready"
        },
        "snapshot": {
          "entities": [
            {
              "entity_id": "sensor.upstairs_temperature",
              "label": "Upstairs Temperature"
            }
          ],
          "job_id": "subscription-entry-job-001",
          "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
          "progress": {
            "message": "Approved history is staged for future planning.",
            "stage": "job_orchestration_scaffold_ready"
          },
          "prompt": "Show sensor.upstairs_temperature",
          "snapshot_id": "subscription-entry-job-001-snapshot-003",
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
        "snapshot_id": "subscription-entry-job-001-snapshot-003",
        "subscription_id": "subscription-entry-job-001-subscription-001",
        "type": "isolinear_job_progress"
      },
      "progress_event_snapshot_validation": [
        {
          "accepted": true,
          "code": "accepted",
          "job_id": "subscription-entry-job-001",
          "progress_stage": "job_orchestration_scaffold_ready",
          "snapshot_id": "subscription-entry-job-001-snapshot-003",
          "status": "planning"
        }
      ],
      "progress_events": [
        {
          "config_entry_id": "subscription-entry",
          "event_id": "subscription-entry-progress-event-001",
          "job_id": "subscription-entry-job-001",
          "message_id": 2,
          "progress": {
            "message": "Approved history is staged for future planning.",
            "stage": "job_orchestration_scaffold_ready"
          },
          "snapshot": {
            "entities": [
              {
                "entity_id": "sensor.upstairs_temperature",
                "label": "Upstairs Temperature"
              }
            ],
            "job_id": "subscription-entry-job-001",
            "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
            "progress": {
              "message": "Approved history is staged for future planning.",
              "stage": "job_orchestration_scaffold_ready"
            },
            "prompt": "Show sensor.upstairs_temperature",
            "snapshot_id": "subscription-entry-job-001-snapshot-003",
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
          "snapshot_id": "subscription-entry-job-001-snapshot-003",
          "subscription_id": "subscription-entry-job-001-subscription-001",
          "type": "isolinear_job_progress"
        }
      ],
      "snapshot_validation": {
        "accepted": true,
        "code": "accepted",
        "job_id": "subscription-entry-job-001",
        "progress_stage": "job_orchestration_scaffold_ready",
        "snapshot_id": "subscription-entry-job-001-snapshot-003",
        "status": "planning"
      },
      "start": {
        "accepted": true,
        "connection": {
          "errors": [],
          "results": [
            {
              "id": 1,
              "result": {
                "entities": [
                  {
                    "entity_id": "sensor.upstairs_temperature",
                    "label": "Upstairs Temperature"
                  }
                ],
                "job_id": "subscription-entry-job-001",
                "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
                "progress": {
                  "message": "Approved history is staged for future planning.",
                  "stage": "job_orchestration_scaffold_ready"
                },
                "prompt": "Show sensor.upstairs_temperature",
                "snapshot_id": "subscription-entry-job-001-snapshot-003",
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
          "config_entry_id": "subscription-entry",
          "job_orchestration": {
            "progress_event": null,
            "run": {
              "entry_id": "subscription-entry",
              "history_entity_ids": [
                "sensor.upstairs_temperature"
              ],
              "job_id": "subscription-entry-job-001",
              "missing_entity_ids": [],
              "prompt": "Show sensor.upstairs_temperature",
              "rejected_entity_ids": [],
              "requested_entity_ids": [
                "sensor.upstairs_temperature"
              ],
              "result_code": "approved_history_ready",
              "run_id": "subscription-entry-orchestration-run-001",
              "snapshot_ids": [
                "subscription-entry-job-001-snapshot-001",
                "subscription-entry-job-001-snapshot-002",
                "subscription-entry-job-001-snapshot-003"
              ]
            }
          },
          "job_state": {
            "code": "job_orchestration_scaffold_ready",
            "job_id": "subscription-entry-job-001",
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
            "subscription_bookkeeping_written": false,
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
            "job_id": "subscription-entry-job-001",
            "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
            "progress": {
              "message": "Approved history is staged for future planning.",
              "stage": "job_orchestration_scaffold_ready"
            },
            "prompt": "Show sensor.upstairs_temperature",
            "snapshot_id": "subscription-entry-job-001-snapshot-003",
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
          "subscription_bookkeeping_written": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        }
      },
      "start_snapshot": {
        "entities": [
          {
            "entity_id": "sensor.upstairs_temperature",
            "label": "Upstairs Temperature"
          }
        ],
        "job_id": "subscription-entry-job-001",
        "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
        "progress": {
          "message": "Approved history is staged for future planning.",
          "stage": "job_orchestration_scaffold_ready"
        },
        "prompt": "Show sensor.upstairs_temperature",
        "snapshot_id": "subscription-entry-job-001-snapshot-003",
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
      "subscribe": {
        "accepted": true,
        "connection": {
          "errors": [],
          "results": [
            {
              "id": 2,
              "result": {
                "entities": [
                  {
                    "entity_id": "sensor.upstairs_temperature",
                    "label": "Upstairs Temperature"
                  }
                ],
                "job_id": "subscription-entry-job-001",
                "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
                "progress": {
                  "message": "Approved history is staged for future planning.",
                  "stage": "job_orchestration_scaffold_ready"
                },
                "prompt": "Show sensor.upstairs_temperature",
                "snapshot_id": "subscription-entry-job-001-snapshot-003",
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
          "config_entry_id": "subscription-entry",
          "job_orchestration": {
            "progress_event": {
              "config_entry_id": "subscription-entry",
              "event_id": "subscription-entry-progress-event-001",
              "job_id": "subscription-entry-job-001",
              "message_id": 2,
              "progress": {
                "message": "Approved history is staged for future planning.",
                "stage": "job_orchestration_scaffold_ready"
              },
              "snapshot": {
                "entities": [
                  {
                    "entity_id": "sensor.upstairs_temperature",
                    "label": "Upstairs Temperature"
                  }
                ],
                "job_id": "subscription-entry-job-001",
                "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
                "progress": {
                  "message": "Approved history is staged for future planning.",
                  "stage": "job_orchestration_scaffold_ready"
                },
                "prompt": "Show sensor.upstairs_temperature",
                "snapshot_id": "subscription-entry-job-001-snapshot-003",
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
              "snapshot_id": "subscription-entry-job-001-snapshot-003",
              "subscription_id": "subscription-entry-job-001-subscription-001",
              "type": "isolinear_job_progress"
            },
            "run": null
          },
          "job_state": {
            "code": "job_orchestration_subscription_progress_recorded",
            "job_id": "subscription-entry-job-001",
            "subscription": {
              "config_entry_id": "subscription-entry",
              "event": {
                "job_id": "subscription-entry-job-001",
                "snapshot": {
                  "entities": [
                    {
                      "entity_id": "sensor.upstairs_temperature",
                      "label": "Upstairs Temperature"
                    }
                  ],
                  "job_id": "subscription-entry-job-001",
                  "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
                  "progress": {
                    "message": "Approved history is staged for future planning.",
                    "stage": "job_orchestration_scaffold_ready"
                  },
                  "prompt": "Show sensor.upstairs_temperature",
                  "snapshot_id": "subscription-entry-job-001-snapshot-003",
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
                "type": "isolinear_job_snapshot"
              },
              "job_id": "subscription-entry-job-001",
              "message_id": 2,
              "subscription_id": "subscription-entry-job-001-subscription-001"
            }
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
            "subscription_bookkeeping_written": true,
            "subscription_progress_streaming_called": true,
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
            "job_id": "subscription-entry-job-001",
            "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
            "progress": {
              "message": "Approved history is staged for future planning.",
              "stage": "job_orchestration_scaffold_ready"
            },
            "prompt": "Show sensor.upstairs_temperature",
            "snapshot_id": "subscription-entry-job-001-snapshot-003",
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
          "type": "isolinear/v1/job/subscribe",
          "version": 1
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
          "subscription_bookkeeping_written": true,
          "subscription_progress_streaming_called": true,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        }
      },
      "subscribe_snapshot": {
        "entities": [
          {
            "entity_id": "sensor.upstairs_temperature",
            "label": "Upstairs Temperature"
          }
        ],
        "job_id": "subscription-entry-job-001",
        "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
        "progress": {
          "message": "Approved history is staged for future planning.",
          "stage": "job_orchestration_scaffold_ready"
        },
        "prompt": "Show sensor.upstairs_temperature",
        "snapshot_id": "subscription-entry-job-001-snapshot-003",
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
      "subscription": {
        "config_entry_id": "subscription-entry",
        "event": {
          "job_id": "subscription-entry-job-001",
          "snapshot": {
            "entities": [
              {
                "entity_id": "sensor.upstairs_temperature",
                "label": "Upstairs Temperature"
              }
            ],
            "job_id": "subscription-entry-job-001",
            "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
            "progress": {
              "message": "Approved history is staged for future planning.",
              "stage": "job_orchestration_scaffold_ready"
            },
            "prompt": "Show sensor.upstairs_temperature",
            "snapshot_id": "subscription-entry-job-001-snapshot-003",
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
          "type": "isolinear_job_snapshot"
        },
        "job_id": "subscription-entry-job-001",
        "message_id": 2,
        "subscription_id": "subscription-entry-job-001-subscription-001"
      }
    }
  },
  "when": {
    "operation": "dispatch_registered_job_subscribe"
  }
}
PASS accepted_subscribe_records_latest_progress_event
CASE unknown_job_fails_before_subscription_storage
{
  "case_id": "unknown_job_fails_before_subscription_storage",
  "given": {
    "job_id": "unknown-subscription-entry-job-404"
  },
  "then": {
    "unknown_job": {
      "error_codes": [
        "unknown_job"
      ],
      "job_store": {
        "entry_id": "unknown-subscription-entry",
        "job_ids": [],
        "latest_snapshot_ids": [],
        "next_job_number": 1,
        "subscription_count": 0,
        "subscription_ids": []
      },
      "progress_events": [],
      "snapshot_validation": [],
      "subscribe": {
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
          "config_entry_id": "unknown-subscription-entry",
          "job_id": "unknown-subscription-entry-job-404",
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
            "subscription_bookkeeping_written": false,
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
          "subscription_bookkeeping_written": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        }
      },
      "subscriptions": []
    }
  },
  "when": {
    "operation": "dispatch_registered_job_subscribe"
  }
}
PASS unknown_job_fails_before_subscription_storage
CASE cross_config_entry_subscription_rejected
{
  "case_id": "cross_config_entry_subscription_rejected",
  "given": {
    "entry_ids": [
      "subscription-entry-a",
      "subscription-entry-b"
    ]
  },
  "then": {
    "cross_entry": {
      "cross_subscribe": {
        "accepted": false,
        "connection": {
          "errors": [
            {
              "code": "unknown_job",
              "id": 22,
              "message": "The requested Isolinear job was not found for this config entry."
            }
          ],
          "results": []
        },
        "handler_called": true,
        "handler_result": {
          "accepted": false,
          "code": "unknown_job",
          "config_entry_id": "subscription-entry-b",
          "job_id": "subscription-entry-a-job-001",
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
            "subscription_bookkeeping_written": false,
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
          "subscription_bookkeeping_written": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        }
      },
      "entry_a_progress_events": [],
      "entry_a_snapshot_validation": {
        "accepted": true,
        "code": "accepted",
        "job_id": "subscription-entry-a-job-001",
        "progress_stage": "job_orchestration_scaffold_ready",
        "snapshot_id": "subscription-entry-a-job-001-snapshot-003",
        "status": "planning"
      },
      "entry_a_start": {
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
                "job_id": "subscription-entry-a-job-001",
                "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
                "progress": {
                  "message": "Approved history is staged for future planning.",
                  "stage": "job_orchestration_scaffold_ready"
                },
                "prompt": "Show sensor.upstairs_temperature",
                "snapshot_id": "subscription-entry-a-job-001-snapshot-003",
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
          "config_entry_id": "subscription-entry-a",
          "job_orchestration": {
            "progress_event": null,
            "run": {
              "entry_id": "subscription-entry-a",
              "history_entity_ids": [
                "sensor.upstairs_temperature"
              ],
              "job_id": "subscription-entry-a-job-001",
              "missing_entity_ids": [],
              "prompt": "Show sensor.upstairs_temperature",
              "rejected_entity_ids": [],
              "requested_entity_ids": [
                "sensor.upstairs_temperature"
              ],
              "result_code": "approved_history_ready",
              "run_id": "subscription-entry-a-orchestration-run-001",
              "snapshot_ids": [
                "subscription-entry-a-job-001-snapshot-001",
                "subscription-entry-a-job-001-snapshot-002",
                "subscription-entry-a-job-001-snapshot-003"
              ]
            }
          },
          "job_state": {
            "code": "job_orchestration_scaffold_ready",
            "job_id": "subscription-entry-a-job-001",
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
            "subscription_bookkeeping_written": false,
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
            "job_id": "subscription-entry-a-job-001",
            "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
            "progress": {
              "message": "Approved history is staged for future planning.",
              "stage": "job_orchestration_scaffold_ready"
            },
            "prompt": "Show sensor.upstairs_temperature",
            "snapshot_id": "subscription-entry-a-job-001-snapshot-003",
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
          "subscription_bookkeeping_written": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        }
      },
      "entry_a_subscriptions": [],
      "entry_b_progress_events": [],
      "entry_b_snapshot_validation": {
        "accepted": true,
        "code": "accepted",
        "job_id": "subscription-entry-b-job-001",
        "progress_stage": "job_orchestration_scaffold_ready",
        "snapshot_id": "subscription-entry-b-job-001-snapshot-003",
        "status": "planning"
      },
      "entry_b_start": {
        "accepted": true,
        "connection": {
          "errors": [],
          "results": [
            {
              "id": 21,
              "result": {
                "entities": [
                  {
                    "entity_id": "binary_sensor.office_window",
                    "label": "Office Window"
                  }
                ],
                "job_id": "subscription-entry-b-job-001",
                "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
                "progress": {
                  "message": "Approved history is staged for future planning.",
                  "stage": "job_orchestration_scaffold_ready"
                },
                "prompt": "Show binary_sensor.office_window",
                "snapshot_id": "subscription-entry-b-job-001-snapshot-003",
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
          "config_entry_id": "subscription-entry-b",
          "job_orchestration": {
            "progress_event": null,
            "run": {
              "entry_id": "subscription-entry-b",
              "history_entity_ids": [
                "binary_sensor.office_window"
              ],
              "job_id": "subscription-entry-b-job-001",
              "missing_entity_ids": [],
              "prompt": "Show binary_sensor.office_window",
              "rejected_entity_ids": [],
              "requested_entity_ids": [
                "binary_sensor.office_window"
              ],
              "result_code": "approved_history_ready",
              "run_id": "subscription-entry-b-orchestration-run-001",
              "snapshot_ids": [
                "subscription-entry-b-job-001-snapshot-001",
                "subscription-entry-b-job-001-snapshot-002",
                "subscription-entry-b-job-001-snapshot-003"
              ]
            }
          },
          "job_state": {
            "code": "job_orchestration_scaffold_ready",
            "job_id": "subscription-entry-b-job-001",
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
            "subscription_bookkeeping_written": false,
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
            "job_id": "subscription-entry-b-job-001",
            "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
            "progress": {
              "message": "Approved history is staged for future planning.",
              "stage": "job_orchestration_scaffold_ready"
            },
            "prompt": "Show binary_sensor.office_window",
            "snapshot_id": "subscription-entry-b-job-001-snapshot-003",
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
          "subscription_bookkeeping_written": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        }
      },
      "entry_b_subscriptions": [],
      "error_codes": [
        "unknown_job"
      ]
    }
  },
  "when": {
    "operation": "subscribe_entry_a_job_from_entry_b"
  }
}
PASS cross_config_entry_subscription_rejected
CASE valid_subscriptions_stay_config_entry_scoped
{
  "case_id": "valid_subscriptions_stay_config_entry_scoped",
  "given": {
    "entry_ids": [
      "valid-subscription-entry-a",
      "valid-subscription-entry-b"
    ]
  },
  "then": {
    "isolation": {
      "entry_a": {
        "orchestration_store": {
          "entry_id": "valid-subscription-entry-a",
          "latest_history_entity_ids": [
            "sensor.upstairs_temperature"
          ],
          "latest_job_id": "valid-subscription-entry-a-job-001",
          "latest_progress_event_id": "valid-subscription-entry-a-progress-event-001",
          "latest_progress_snapshot_id": "valid-subscription-entry-a-job-001-snapshot-003",
          "latest_requested_entity_ids": [
            "sensor.upstairs_temperature"
          ],
          "latest_result_code": "approved_history_ready",
          "progress_event_count": 1,
          "progress_event_ids": [
            "valid-subscription-entry-a-progress-event-001"
          ],
          "run_count": 1,
          "run_ids": [
            "valid-subscription-entry-a-orchestration-run-001"
          ]
        },
        "progress_event_snapshot_validation": [
          {
            "accepted": true,
            "code": "accepted",
            "job_id": "valid-subscription-entry-a-job-001",
            "progress_stage": "job_orchestration_scaffold_ready",
            "snapshot_id": "valid-subscription-entry-a-job-001-snapshot-003",
            "status": "planning"
          }
        ],
        "progress_events": [
          {
            "config_entry_id": "valid-subscription-entry-a",
            "event_id": "valid-subscription-entry-a-progress-event-001",
            "job_id": "valid-subscription-entry-a-job-001",
            "message_id": 32,
            "progress": {
              "message": "Approved history is staged for future planning.",
              "stage": "job_orchestration_scaffold_ready"
            },
            "snapshot": {
              "entities": [
                {
                  "entity_id": "sensor.upstairs_temperature",
                  "label": "Upstairs Temperature"
                }
              ],
              "job_id": "valid-subscription-entry-a-job-001",
              "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
              "progress": {
                "message": "Approved history is staged for future planning.",
                "stage": "job_orchestration_scaffold_ready"
              },
              "prompt": "Show sensor.upstairs_temperature",
              "snapshot_id": "valid-subscription-entry-a-job-001-snapshot-003",
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
            "snapshot_id": "valid-subscription-entry-a-job-001-snapshot-003",
            "subscription_id": "valid-subscription-entry-a-job-001-subscription-001",
            "type": "isolinear_job_progress"
          }
        ],
        "snapshot": {
          "entities": [
            {
              "entity_id": "sensor.upstairs_temperature",
              "label": "Upstairs Temperature"
            }
          ],
          "job_id": "valid-subscription-entry-a-job-001",
          "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
          "progress": {
            "message": "Approved history is staged for future planning.",
            "stage": "job_orchestration_scaffold_ready"
          },
          "prompt": "Show sensor.upstairs_temperature",
          "snapshot_id": "valid-subscription-entry-a-job-001-snapshot-003",
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
        "snapshot_validation": {
          "accepted": true,
          "code": "accepted",
          "job_id": "valid-subscription-entry-a-job-001",
          "progress_stage": "job_orchestration_scaffold_ready",
          "snapshot_id": "valid-subscription-entry-a-job-001-snapshot-003",
          "status": "planning"
        },
        "start": {
          "accepted": true,
          "connection": {
            "errors": [],
            "results": [
              {
                "id": 30,
                "result": {
                  "entities": [
                    {
                      "entity_id": "sensor.upstairs_temperature",
                      "label": "Upstairs Temperature"
                    }
                  ],
                  "job_id": "valid-subscription-entry-a-job-001",
                  "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
                  "progress": {
                    "message": "Approved history is staged for future planning.",
                    "stage": "job_orchestration_scaffold_ready"
                  },
                  "prompt": "Show sensor.upstairs_temperature",
                  "snapshot_id": "valid-subscription-entry-a-job-001-snapshot-003",
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
            "config_entry_id": "valid-subscription-entry-a",
            "job_orchestration": {
              "progress_event": null,
              "run": {
                "entry_id": "valid-subscription-entry-a",
                "history_entity_ids": [
                  "sensor.upstairs_temperature"
                ],
                "job_id": "valid-subscription-entry-a-job-001",
                "missing_entity_ids": [],
                "prompt": "Show sensor.upstairs_temperature",
                "rejected_entity_ids": [],
                "requested_entity_ids": [
                  "sensor.upstairs_temperature"
                ],
                "result_code": "approved_history_ready",
                "run_id": "valid-subscription-entry-a-orchestration-run-001",
                "snapshot_ids": [
                  "valid-subscription-entry-a-job-001-snapshot-001",
                  "valid-subscription-entry-a-job-001-snapshot-002",
                  "valid-subscription-entry-a-job-001-snapshot-003"
                ]
              }
            },
            "job_state": {
              "code": "job_orchestration_scaffold_ready",
              "job_id": "valid-subscription-entry-a-job-001",
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
              "subscription_bookkeeping_written": false,
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
              "job_id": "valid-subscription-entry-a-job-001",
              "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
              "progress": {
                "message": "Approved history is staged for future planning.",
                "stage": "job_orchestration_scaffold_ready"
              },
              "prompt": "Show sensor.upstairs_temperature",
              "snapshot_id": "valid-subscription-entry-a-job-001-snapshot-003",
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
            "subscription_bookkeeping_written": false,
            "subscription_progress_streaming_called": false,
            "token_generated": false,
            "websocket_command_registered": false,
            "worker_called": false
          }
        },
        "subscribe": {
          "accepted": true,
          "connection": {
            "errors": [],
            "results": [
              {
                "id": 32,
                "result": {
                  "entities": [
                    {
                      "entity_id": "sensor.upstairs_temperature",
                      "label": "Upstairs Temperature"
                    }
                  ],
                  "job_id": "valid-subscription-entry-a-job-001",
                  "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
                  "progress": {
                    "message": "Approved history is staged for future planning.",
                    "stage": "job_orchestration_scaffold_ready"
                  },
                  "prompt": "Show sensor.upstairs_temperature",
                  "snapshot_id": "valid-subscription-entry-a-job-001-snapshot-003",
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
            "config_entry_id": "valid-subscription-entry-a",
            "job_orchestration": {
              "progress_event": {
                "config_entry_id": "valid-subscription-entry-a",
                "event_id": "valid-subscription-entry-a-progress-event-001",
                "job_id": "valid-subscription-entry-a-job-001",
                "message_id": 32,
                "progress": {
                  "message": "Approved history is staged for future planning.",
                  "stage": "job_orchestration_scaffold_ready"
                },
                "snapshot": {
                  "entities": [
                    {
                      "entity_id": "sensor.upstairs_temperature",
                      "label": "Upstairs Temperature"
                    }
                  ],
                  "job_id": "valid-subscription-entry-a-job-001",
                  "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
                  "progress": {
                    "message": "Approved history is staged for future planning.",
                    "stage": "job_orchestration_scaffold_ready"
                  },
                  "prompt": "Show sensor.upstairs_temperature",
                  "snapshot_id": "valid-subscription-entry-a-job-001-snapshot-003",
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
                "snapshot_id": "valid-subscription-entry-a-job-001-snapshot-003",
                "subscription_id": "valid-subscription-entry-a-job-001-subscription-001",
                "type": "isolinear_job_progress"
              },
              "run": null
            },
            "job_state": {
              "code": "job_orchestration_subscription_progress_recorded",
              "job_id": "valid-subscription-entry-a-job-001",
              "subscription": {
                "config_entry_id": "valid-subscription-entry-a",
                "event": {
                  "job_id": "valid-subscription-entry-a-job-001",
                  "snapshot": {
                    "entities": [
                      {
                        "entity_id": "sensor.upstairs_temperature",
                        "label": "Upstairs Temperature"
                      }
                    ],
                    "job_id": "valid-subscription-entry-a-job-001",
                    "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
                    "progress": {
                      "message": "Approved history is staged for future planning.",
                      "stage": "job_orchestration_scaffold_ready"
                    },
                    "prompt": "Show sensor.upstairs_temperature",
                    "snapshot_id": "valid-subscription-entry-a-job-001-snapshot-003",
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
                  "type": "isolinear_job_snapshot"
                },
                "job_id": "valid-subscription-entry-a-job-001",
                "message_id": 32,
                "subscription_id": "valid-subscription-entry-a-job-001-subscription-001"
              }
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
              "subscription_bookkeeping_written": true,
              "subscription_progress_streaming_called": true,
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
              "job_id": "valid-subscription-entry-a-job-001",
              "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
              "progress": {
                "message": "Approved history is staged for future planning.",
                "stage": "job_orchestration_scaffold_ready"
              },
              "prompt": "Show sensor.upstairs_temperature",
              "snapshot_id": "valid-subscription-entry-a-job-001-snapshot-003",
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
            "type": "isolinear/v1/job/subscribe",
            "version": 1
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
            "subscription_bookkeeping_written": true,
            "subscription_progress_streaming_called": true,
            "token_generated": false,
            "websocket_command_registered": false,
            "worker_called": false
          }
        },
        "subscriptions": [
          {
            "config_entry_id": "valid-subscription-entry-a",
            "event": {
              "job_id": "valid-subscription-entry-a-job-001",
              "snapshot": {
                "entities": [
                  {
                    "entity_id": "sensor.upstairs_temperature",
                    "label": "Upstairs Temperature"
                  }
                ],
                "job_id": "valid-subscription-entry-a-job-001",
                "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
                "progress": {
                  "message": "Approved history is staged for future planning.",
                  "stage": "job_orchestration_scaffold_ready"
                },
                "prompt": "Show sensor.upstairs_temperature",
                "snapshot_id": "valid-subscription-entry-a-job-001-snapshot-003",
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
              "type": "isolinear_job_snapshot"
            },
            "job_id": "valid-subscription-entry-a-job-001",
            "message_id": 32,
            "subscription_id": "valid-subscription-entry-a-job-001-subscription-001"
          }
        ]
      },
      "entry_b": {
        "orchestration_store": {
          "entry_id": "valid-subscription-entry-b",
          "latest_history_entity_ids": [
            "binary_sensor.office_window"
          ],
          "latest_job_id": "valid-subscription-entry-b-job-001",
          "latest_progress_event_id": "valid-subscription-entry-b-progress-event-001",
          "latest_progress_snapshot_id": "valid-subscription-entry-b-job-001-snapshot-003",
          "latest_requested_entity_ids": [
            "binary_sensor.office_window"
          ],
          "latest_result_code": "approved_history_ready",
          "progress_event_count": 1,
          "progress_event_ids": [
            "valid-subscription-entry-b-progress-event-001"
          ],
          "run_count": 1,
          "run_ids": [
            "valid-subscription-entry-b-orchestration-run-001"
          ]
        },
        "progress_event_snapshot_validation": [
          {
            "accepted": true,
            "code": "accepted",
            "job_id": "valid-subscription-entry-b-job-001",
            "progress_stage": "job_orchestration_scaffold_ready",
            "snapshot_id": "valid-subscription-entry-b-job-001-snapshot-003",
            "status": "planning"
          }
        ],
        "progress_events": [
          {
            "config_entry_id": "valid-subscription-entry-b",
            "event_id": "valid-subscription-entry-b-progress-event-001",
            "job_id": "valid-subscription-entry-b-job-001",
            "message_id": 33,
            "progress": {
              "message": "Approved history is staged for future planning.",
              "stage": "job_orchestration_scaffold_ready"
            },
            "snapshot": {
              "entities": [
                {
                  "entity_id": "binary_sensor.office_window",
                  "label": "Office Window"
                }
              ],
              "job_id": "valid-subscription-entry-b-job-001",
              "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
              "progress": {
                "message": "Approved history is staged for future planning.",
                "stage": "job_orchestration_scaffold_ready"
              },
              "prompt": "Show binary_sensor.office_window",
              "snapshot_id": "valid-subscription-entry-b-job-001-snapshot-003",
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
            "snapshot_id": "valid-subscription-entry-b-job-001-snapshot-003",
            "subscription_id": "valid-subscription-entry-b-job-001-subscription-001",
            "type": "isolinear_job_progress"
          }
        ],
        "snapshot": {
          "entities": [
            {
              "entity_id": "binary_sensor.office_window",
              "label": "Office Window"
            }
          ],
          "job_id": "valid-subscription-entry-b-job-001",
          "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
          "progress": {
            "message": "Approved history is staged for future planning.",
            "stage": "job_orchestration_scaffold_ready"
          },
          "prompt": "Show binary_sensor.office_window",
          "snapshot_id": "valid-subscription-entry-b-job-001-snapshot-003",
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
        "snapshot_validation": {
          "accepted": true,
          "code": "accepted",
          "job_id": "valid-subscription-entry-b-job-001",
          "progress_stage": "job_orchestration_scaffold_ready",
          "snapshot_id": "valid-subscription-entry-b-job-001-snapshot-003",
          "status": "planning"
        },
        "start": {
          "accepted": true,
          "connection": {
            "errors": [],
            "results": [
              {
                "id": 31,
                "result": {
                  "entities": [
                    {
                      "entity_id": "binary_sensor.office_window",
                      "label": "Office Window"
                    }
                  ],
                  "job_id": "valid-subscription-entry-b-job-001",
                  "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
                  "progress": {
                    "message": "Approved history is staged for future planning.",
                    "stage": "job_orchestration_scaffold_ready"
                  },
                  "prompt": "Show binary_sensor.office_window",
                  "snapshot_id": "valid-subscription-entry-b-job-001-snapshot-003",
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
            "config_entry_id": "valid-subscription-entry-b",
            "job_orchestration": {
              "progress_event": null,
              "run": {
                "entry_id": "valid-subscription-entry-b",
                "history_entity_ids": [
                  "binary_sensor.office_window"
                ],
                "job_id": "valid-subscription-entry-b-job-001",
                "missing_entity_ids": [],
                "prompt": "Show binary_sensor.office_window",
                "rejected_entity_ids": [],
                "requested_entity_ids": [
                  "binary_sensor.office_window"
                ],
                "result_code": "approved_history_ready",
                "run_id": "valid-subscription-entry-b-orchestration-run-001",
                "snapshot_ids": [
                  "valid-subscription-entry-b-job-001-snapshot-001",
                  "valid-subscription-entry-b-job-001-snapshot-002",
                  "valid-subscription-entry-b-job-001-snapshot-003"
                ]
              }
            },
            "job_state": {
              "code": "job_orchestration_scaffold_ready",
              "job_id": "valid-subscription-entry-b-job-001",
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
              "subscription_bookkeeping_written": false,
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
              "job_id": "valid-subscription-entry-b-job-001",
              "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
              "progress": {
                "message": "Approved history is staged for future planning.",
                "stage": "job_orchestration_scaffold_ready"
              },
              "prompt": "Show binary_sensor.office_window",
              "snapshot_id": "valid-subscription-entry-b-job-001-snapshot-003",
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
            "subscription_bookkeeping_written": false,
            "subscription_progress_streaming_called": false,
            "token_generated": false,
            "websocket_command_registered": false,
            "worker_called": false
          }
        },
        "subscribe": {
          "accepted": true,
          "connection": {
            "errors": [],
            "results": [
              {
                "id": 33,
                "result": {
                  "entities": [
                    {
                      "entity_id": "binary_sensor.office_window",
                      "label": "Office Window"
                    }
                  ],
                  "job_id": "valid-subscription-entry-b-job-001",
                  "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
                  "progress": {
                    "message": "Approved history is staged for future planning.",
                    "stage": "job_orchestration_scaffold_ready"
                  },
                  "prompt": "Show binary_sensor.office_window",
                  "snapshot_id": "valid-subscription-entry-b-job-001-snapshot-003",
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
            "config_entry_id": "valid-subscription-entry-b",
            "job_orchestration": {
              "progress_event": {
                "config_entry_id": "valid-subscription-entry-b",
                "event_id": "valid-subscription-entry-b-progress-event-001",
                "job_id": "valid-subscription-entry-b-job-001",
                "message_id": 33,
                "progress": {
                  "message": "Approved history is staged for future planning.",
                  "stage": "job_orchestration_scaffold_ready"
                },
                "snapshot": {
                  "entities": [
                    {
                      "entity_id": "binary_sensor.office_window",
                      "label": "Office Window"
                    }
                  ],
                  "job_id": "valid-subscription-entry-b-job-001",
                  "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
                  "progress": {
                    "message": "Approved history is staged for future planning.",
                    "stage": "job_orchestration_scaffold_ready"
                  },
                  "prompt": "Show binary_sensor.office_window",
                  "snapshot_id": "valid-subscription-entry-b-job-001-snapshot-003",
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
                "snapshot_id": "valid-subscription-entry-b-job-001-snapshot-003",
                "subscription_id": "valid-subscription-entry-b-job-001-subscription-001",
                "type": "isolinear_job_progress"
              },
              "run": null
            },
            "job_state": {
              "code": "job_orchestration_subscription_progress_recorded",
              "job_id": "valid-subscription-entry-b-job-001",
              "subscription": {
                "config_entry_id": "valid-subscription-entry-b",
                "event": {
                  "job_id": "valid-subscription-entry-b-job-001",
                  "snapshot": {
                    "entities": [
                      {
                        "entity_id": "binary_sensor.office_window",
                        "label": "Office Window"
                      }
                    ],
                    "job_id": "valid-subscription-entry-b-job-001",
                    "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
                    "progress": {
                      "message": "Approved history is staged for future planning.",
                      "stage": "job_orchestration_scaffold_ready"
                    },
                    "prompt": "Show binary_sensor.office_window",
                    "snapshot_id": "valid-subscription-entry-b-job-001-snapshot-003",
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
                  "type": "isolinear_job_snapshot"
                },
                "job_id": "valid-subscription-entry-b-job-001",
                "message_id": 33,
                "subscription_id": "valid-subscription-entry-b-job-001-subscription-001"
              }
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
              "subscription_bookkeeping_written": true,
              "subscription_progress_streaming_called": true,
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
              "job_id": "valid-subscription-entry-b-job-001",
              "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
              "progress": {
                "message": "Approved history is staged for future planning.",
                "stage": "job_orchestration_scaffold_ready"
              },
              "prompt": "Show binary_sensor.office_window",
              "snapshot_id": "valid-subscription-entry-b-job-001-snapshot-003",
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
            "type": "isolinear/v1/job/subscribe",
            "version": 1
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
            "subscription_bookkeeping_written": true,
            "subscription_progress_streaming_called": true,
            "token_generated": false,
            "websocket_command_registered": false,
            "worker_called": false
          }
        },
        "subscriptions": [
          {
            "config_entry_id": "valid-subscription-entry-b",
            "event": {
              "job_id": "valid-subscription-entry-b-job-001",
              "snapshot": {
                "entities": [
                  {
                    "entity_id": "binary_sensor.office_window",
                    "label": "Office Window"
                  }
                ],
                "job_id": "valid-subscription-entry-b-job-001",
                "message": "Approved catalog and history are ready for a later planning packet; model and worker calls are not implemented yet.",
                "progress": {
                  "message": "Approved history is staged for future planning.",
                  "stage": "job_orchestration_scaffold_ready"
                },
                "prompt": "Show binary_sensor.office_window",
                "snapshot_id": "valid-subscription-entry-b-job-001-snapshot-003",
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
              "type": "isolinear_job_snapshot"
            },
            "job_id": "valid-subscription-entry-b-job-001",
            "message_id": 33,
            "subscription_id": "valid-subscription-entry-b-job-001-subscription-001"
          }
        ]
      }
    }
  },
  "when": {
    "operation": "subscribe_each_entry_own_job"
  }
}
PASS valid_subscriptions_stay_config_entry_scoped
CASE subscription_progress_snapshots_validate_before_storage
{
  "case_id": "subscription_progress_snapshots_validate_before_storage",
  "given": {
    "schema": "docs/schemas/integration-job-snapshot.schema.json"
  },
  "then": {
    "snapshot_validation": {
      "accepted": {
        "event_snapshots_valid": true,
        "progress_event_snapshot_validation": [
          {
            "accepted": true,
            "code": "accepted",
            "job_id": "subscription-entry-job-001",
            "progress_stage": "job_orchestration_scaffold_ready",
            "snapshot_id": "subscription-entry-job-001-snapshot-003",
            "status": "planning"
          }
        ],
        "returned_snapshot_valid": true,
        "snapshot_validation": {
          "accepted": true,
          "code": "accepted",
          "job_id": "subscription-entry-job-001",
          "progress_stage": "job_orchestration_scaffold_ready",
          "snapshot_id": "subscription-entry-job-001-snapshot-003",
          "status": "planning"
        }
      },
      "isolation_entry_a": {
        "event_snapshots_valid": true,
        "progress_event_snapshot_validation": [
          {
            "accepted": true,
            "code": "accepted",
            "job_id": "valid-subscription-entry-a-job-001",
            "progress_stage": "job_orchestration_scaffold_ready",
            "snapshot_id": "valid-subscription-entry-a-job-001-snapshot-003",
            "status": "planning"
          }
        ],
        "returned_snapshot_valid": true,
        "snapshot_validation": {
          "accepted": true,
          "code": "accepted",
          "job_id": "valid-subscription-entry-a-job-001",
          "progress_stage": "job_orchestration_scaffold_ready",
          "snapshot_id": "valid-subscription-entry-a-job-001-snapshot-003",
          "status": "planning"
        }
      },
      "isolation_entry_b": {
        "event_snapshots_valid": true,
        "progress_event_snapshot_validation": [
          {
            "accepted": true,
            "code": "accepted",
            "job_id": "valid-subscription-entry-b-job-001",
            "progress_stage": "job_orchestration_scaffold_ready",
            "snapshot_id": "valid-subscription-entry-b-job-001-snapshot-003",
            "status": "planning"
          }
        ],
        "returned_snapshot_valid": true,
        "snapshot_validation": {
          "accepted": true,
          "code": "accepted",
          "job_id": "valid-subscription-entry-b-job-001",
          "progress_stage": "job_orchestration_scaffold_ready",
          "snapshot_id": "valid-subscription-entry-b-job-001-snapshot-003",
          "status": "planning"
        }
      }
    }
  },
  "when": {
    "operation": "validate_observed_subscription_progress_snapshots"
  }
}
PASS subscription_progress_snapshots_validate_before_storage
CASE subscription_progress_remains_bounded
{
  "case_id": "subscription_progress_remains_bounded",
  "given": {
    "handled_surfaces": [
      "accepted_subscribe",
      "unknown_job_failure",
      "cross_config_entry_failure",
      "config_entry_isolation"
    ]
  },
  "then": {
    "side_effects": {
      "allowed_aggregate": {
        "job_orchestration_scaffold_written": true,
        "subscription_bookkeeping_written": true,
        "subscription_progress_streaming_called": true,
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
        "retry_behavior_called": false,
        "semantic_memory_called": false,
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
        "retry_behavior_called": false,
        "semantic_memory_called": false,
        "token_generated": false,
        "worker_called": false
      },
      "observed": [
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
          "name": "accepted_subscribe",
          "retry_behavior_called": false,
          "semantic_memory_called": false,
          "subscription_bookkeeping_written": true,
          "subscription_progress_streaming_called": true,
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
          "name": "unknown_subscribe_job",
          "retry_behavior_called": false,
          "semantic_memory_called": false,
          "subscription_bookkeeping_written": false,
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
          "subscription_bookkeeping_written": false,
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
          "name": "entry_a_subscribe",
          "retry_behavior_called": false,
          "semantic_memory_called": false,
          "subscription_bookkeeping_written": true,
          "subscription_progress_streaming_called": true,
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
          "name": "entry_b_subscribe",
          "retry_behavior_called": false,
          "semantic_memory_called": false,
          "subscription_bookkeeping_written": true,
          "subscription_progress_streaming_called": true,
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
          "subscription_bookkeeping_written": false,
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
PASS subscription_progress_remains_bounded
PASS home_assistant_job_orchestration_subscription_progress_scaffold
```
