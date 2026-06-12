CASE ready_provider_health_probe_records_metadata
{
  "case_id": "ready_provider_health_probe_records_metadata",
  "given": {
    "config_entry_id": "provider-health-ready-entry",
    "integration_model_provider_health_schema": "docs/schemas/integration-model-provider-health.schema.json",
    "model_provider_health_request_schema": "docs/schemas/model-provider-health-request.schema.json",
    "run_timestamp": "2026-06-12T21:51:02+00:00"
  },
  "then": {
    "ready": {
      "health": {
        "code": "model_provider_health_ready",
        "config_entry_id": "provider-health-ready-entry",
        "health_id": "provider-health-ready-entry-model-provider-health-001",
        "orchestration": {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": true,
          "model_provider_health_check_called": true,
          "model_provider_health_request_validated": true,
          "model_provider_health_response_validated": true,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        },
        "provider": {
          "endpoint_url": "http://ollama-a.local:11434",
          "health_path": "/api/tags",
          "model": "llama3.1",
          "role": "planner",
          "type": "ollama_compatible"
        },
        "request": {
          "headers": {
            "accept": "application/json"
          },
          "method": "GET",
          "path": "/api/tags",
          "protocol_version": 1
        },
        "response": {
          "accepted": true,
          "capabilities": {
            "planning": true,
            "structured_output": true
          },
          "checks": [
            {
              "name": "ollama_tags_endpoint",
              "status": "pass"
            },
            {
              "name": "planner_model",
              "status": "pass"
            }
          ],
          "code": "model_provider_health_ready",
          "message": "Model-provider health endpoint reports ready.",
          "status": "ready"
        },
        "status": "ready",
        "type": "isolinear_model_provider_health",
        "validation": {
          "checks": [
            {
              "name": "model_provider_health_request",
              "status": "pass"
            },
            {
              "name": "model_provider_health_response",
              "status": "pass"
            },
            {
              "name": "provider_health_metadata_card_safe",
              "status": "pass"
            }
          ],
          "status": "pass",
          "summary": "Model-provider health metadata validates before storage."
        },
        "warnings": [
          "model_provider_health_ready",
          "provider_details_internal_only"
        ]
      },
      "health_call_count": 1,
      "health_setup": {
        "accepted": true,
        "code": "model_provider_health_probe_available",
        "config_entry_scoped": true,
        "enabled": true,
        "entry_id": "provider-health-ready-entry",
        "orchestration": {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": false,
          "model_provider_health_check_called": false,
          "model_provider_health_request_validated": false,
          "model_provider_health_response_validated": false,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        },
        "provider": {
          "endpoint_url": "http://ollama-a.local:11434",
          "health_path": "/api/tags",
          "model": "llama3.1",
          "role": "planner",
          "type": "ollama_compatible"
        }
      },
      "health_validation": {
        "accepted": true,
        "code": "accepted",
        "config_entry_id": "provider-health-ready-entry",
        "health_id": "provider-health-ready-entry-model-provider-health-001",
        "health_path": "/api/tags",
        "status": "ready"
      },
      "plan_call_count": 0,
      "request_validation": {
        "accepted": true,
        "code": "accepted",
        "method": "GET",
        "path": "/api/tags",
        "uses_health_path": true
      },
      "result": {
        "accepted": true,
        "code": "model_provider_health_ready",
        "config_entry_scoped": true,
        "enabled": true,
        "entry_id": "provider-health-ready-entry",
        "health": {
          "code": "model_provider_health_ready",
          "config_entry_id": "provider-health-ready-entry",
          "health_id": "provider-health-ready-entry-model-provider-health-001",
          "orchestration": {
            "automatic_progress_task_called": false,
            "automatic_retry_called": false,
            "chart_artifact_written": false,
            "chart_rendering_called": false,
            "durable_retry_storage_written": false,
            "durable_storage_written": false,
            "home_assistant_history_read": false,
            "home_assistant_service_or_state_mutation_called": false,
            "model_provider_health_bookkeeping_written": true,
            "model_provider_health_check_called": true,
            "model_provider_health_request_validated": true,
            "model_provider_health_response_validated": true,
            "model_provider_planning_called": false,
            "model_provider_retry_policy_written": false,
            "new_provider_transport_added": false,
            "provider_details_leaked_to_card": false,
            "retry_behavior_called": false,
            "scheduler_called": false,
            "semantic_memory_called": false,
            "token_generated": false,
            "token_rotation_called": false,
            "worker_called": false,
            "worker_health_check_called": false
          },
          "provider": {
            "endpoint_url": "http://ollama-a.local:11434",
            "health_path": "/api/tags",
            "model": "llama3.1",
            "role": "planner",
            "type": "ollama_compatible"
          },
          "request": {
            "headers": {
              "accept": "application/json"
            },
            "method": "GET",
            "path": "/api/tags",
            "protocol_version": 1
          },
          "response": {
            "accepted": true,
            "capabilities": {
              "planning": true,
              "structured_output": true
            },
            "checks": [
              {
                "name": "ollama_tags_endpoint",
                "status": "pass"
              },
              {
                "name": "planner_model",
                "status": "pass"
              }
            ],
            "code": "model_provider_health_ready",
            "message": "Model-provider health endpoint reports ready.",
            "status": "ready"
          },
          "status": "ready",
          "type": "isolinear_model_provider_health",
          "validation": {
            "checks": [
              {
                "name": "model_provider_health_request",
                "status": "pass"
              },
              {
                "name": "model_provider_health_response",
                "status": "pass"
              },
              {
                "name": "provider_health_metadata_card_safe",
                "status": "pass"
              }
            ],
            "status": "pass",
            "summary": "Model-provider health metadata validates before storage."
          },
          "warnings": [
            "model_provider_health_ready",
            "provider_details_internal_only"
          ]
        },
        "orchestration": {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": true,
          "model_provider_health_check_called": true,
          "model_provider_health_request_validated": true,
          "model_provider_health_response_validated": true,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        },
        "status": "ready",
        "validation": {
          "accepted": true,
          "code": "accepted",
          "schema": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\docs\\schemas\\integration-model-provider-health.schema.json"
        }
      },
      "stored_provider_endpoint": "http://ollama-a.local:11434",
      "stored_provider_model": "llama3.1"
    }
  },
  "when": {
    "operation": "explicitly_check_model_provider_health",
    "provider_endpoint_path": "/api/tags"
  }
}
PASS ready_provider_health_probe_records_metadata
CASE not_ready_provider_health_response_records_internal_state
{
  "case_id": "not_ready_provider_health_response_records_internal_state",
  "given": {
    "config_entry_id": "provider-health-not-ready-entry",
    "provider_response_status": "not_ready"
  },
  "then": {
    "not_ready": {
      "health": {
        "code": "model_provider_health_not_ready",
        "config_entry_id": "provider-health-not-ready-entry",
        "health_id": "provider-health-not-ready-entry-model-provider-health-001",
        "orchestration": {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": true,
          "model_provider_health_check_called": true,
          "model_provider_health_request_validated": true,
          "model_provider_health_response_validated": true,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        },
        "provider": {
          "endpoint_url": "http://ollama-a.local:11434",
          "health_path": "/api/tags",
          "model": "llama3.1",
          "role": "planner",
          "type": "ollama_compatible"
        },
        "request": {
          "headers": {
            "accept": "application/json"
          },
          "method": "GET",
          "path": "/api/tags",
          "protocol_version": 1
        },
        "response": {
          "accepted": true,
          "capabilities": {
            "planning": false,
            "structured_output": false
          },
          "checks": [
            {
              "name": "ollama_tags_endpoint",
              "status": "pass"
            },
            {
              "name": "planner_model",
              "status": "not_ready"
            }
          ],
          "code": "model_provider_health_not_ready",
          "message": "Model-provider health endpoint reports not_ready.",
          "status": "not_ready"
        },
        "status": "not_ready",
        "type": "isolinear_model_provider_health",
        "validation": {
          "checks": [
            {
              "name": "model_provider_health_request",
              "status": "pass"
            },
            {
              "name": "model_provider_health_response",
              "status": "pass"
            },
            {
              "name": "provider_health_metadata_card_safe",
              "status": "pass"
            }
          ],
          "status": "pass",
          "summary": "Model-provider health metadata validates before storage."
        },
        "warnings": [
          "model_provider_health_not_ready",
          "provider_details_internal_only"
        ]
      },
      "health_call_count": 1,
      "health_setup": {
        "accepted": true,
        "code": "model_provider_health_probe_available",
        "config_entry_scoped": true,
        "enabled": true,
        "entry_id": "provider-health-not-ready-entry",
        "orchestration": {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": false,
          "model_provider_health_check_called": false,
          "model_provider_health_request_validated": false,
          "model_provider_health_response_validated": false,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        },
        "provider": {
          "endpoint_url": "http://ollama-a.local:11434",
          "health_path": "/api/tags",
          "model": "llama3.1",
          "role": "planner",
          "type": "ollama_compatible"
        }
      },
      "health_validation": {
        "accepted": true,
        "code": "accepted",
        "config_entry_id": "provider-health-not-ready-entry",
        "health_id": "provider-health-not-ready-entry-model-provider-health-001",
        "health_path": "/api/tags",
        "status": "not_ready"
      },
      "plan_call_count": 0,
      "planner_client_present": true,
      "planner_client_unchanged": true,
      "result": {
        "accepted": true,
        "code": "model_provider_health_not_ready",
        "config_entry_scoped": true,
        "enabled": false,
        "entry_id": "provider-health-not-ready-entry",
        "health": {
          "code": "model_provider_health_not_ready",
          "config_entry_id": "provider-health-not-ready-entry",
          "health_id": "provider-health-not-ready-entry-model-provider-health-001",
          "orchestration": {
            "automatic_progress_task_called": false,
            "automatic_retry_called": false,
            "chart_artifact_written": false,
            "chart_rendering_called": false,
            "durable_retry_storage_written": false,
            "durable_storage_written": false,
            "home_assistant_history_read": false,
            "home_assistant_service_or_state_mutation_called": false,
            "model_provider_health_bookkeeping_written": true,
            "model_provider_health_check_called": true,
            "model_provider_health_request_validated": true,
            "model_provider_health_response_validated": true,
            "model_provider_planning_called": false,
            "model_provider_retry_policy_written": false,
            "new_provider_transport_added": false,
            "provider_details_leaked_to_card": false,
            "retry_behavior_called": false,
            "scheduler_called": false,
            "semantic_memory_called": false,
            "token_generated": false,
            "token_rotation_called": false,
            "worker_called": false,
            "worker_health_check_called": false
          },
          "provider": {
            "endpoint_url": "http://ollama-a.local:11434",
            "health_path": "/api/tags",
            "model": "llama3.1",
            "role": "planner",
            "type": "ollama_compatible"
          },
          "request": {
            "headers": {
              "accept": "application/json"
            },
            "method": "GET",
            "path": "/api/tags",
            "protocol_version": 1
          },
          "response": {
            "accepted": true,
            "capabilities": {
              "planning": false,
              "structured_output": false
            },
            "checks": [
              {
                "name": "ollama_tags_endpoint",
                "status": "pass"
              },
              {
                "name": "planner_model",
                "status": "not_ready"
              }
            ],
            "code": "model_provider_health_not_ready",
            "message": "Model-provider health endpoint reports not_ready.",
            "status": "not_ready"
          },
          "status": "not_ready",
          "type": "isolinear_model_provider_health",
          "validation": {
            "checks": [
              {
                "name": "model_provider_health_request",
                "status": "pass"
              },
              {
                "name": "model_provider_health_response",
                "status": "pass"
              },
              {
                "name": "provider_health_metadata_card_safe",
                "status": "pass"
              }
            ],
            "status": "pass",
            "summary": "Model-provider health metadata validates before storage."
          },
          "warnings": [
            "model_provider_health_not_ready",
            "provider_details_internal_only"
          ]
        },
        "orchestration": {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": true,
          "model_provider_health_check_called": true,
          "model_provider_health_request_validated": true,
          "model_provider_health_response_validated": true,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        },
        "status": "not_ready",
        "validation": {
          "accepted": true,
          "code": "accepted",
          "schema": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\docs\\schemas\\integration-model-provider-health.schema.json"
        }
      }
    }
  },
  "when": {
    "operation": "explicitly_check_model_provider_health"
  }
}
PASS not_ready_provider_health_response_records_internal_state
CASE transport_failure_records_unavailable_provider_health
{
  "case_id": "transport_failure_records_unavailable_provider_health",
  "given": {
    "config_entry_id": "provider-health-unavailable-entry",
    "provider_transport_failure": "model_provider_health_connection_error"
  },
  "then": {
    "unavailable": {
      "health": {
        "code": "model_provider_health_connection_error",
        "config_entry_id": "provider-health-unavailable-entry",
        "health_id": "provider-health-unavailable-entry-model-provider-health-001",
        "orchestration": {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": true,
          "model_provider_health_check_called": true,
          "model_provider_health_request_validated": true,
          "model_provider_health_response_validated": true,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        },
        "provider": {
          "endpoint_url": "http://ollama-a.local:11434",
          "health_path": "/api/tags",
          "model": "llama3.1",
          "role": "planner",
          "type": "ollama_compatible"
        },
        "request": {
          "headers": {
            "accept": "application/json"
          },
          "method": "GET",
          "path": "/api/tags",
          "protocol_version": 1
        },
        "response": {
          "accepted": false,
          "capabilities": {
            "planning": false,
            "structured_output": false
          },
          "checks": [],
          "code": "model_provider_health_connection_error",
          "message": "Connection refused by provider health endpoint.",
          "status": "unavailable"
        },
        "status": "unavailable",
        "type": "isolinear_model_provider_health",
        "validation": {
          "checks": [
            {
              "name": "model_provider_health_request",
              "status": "pass"
            },
            {
              "name": "model_provider_health_response",
              "status": "pass"
            },
            {
              "name": "provider_health_metadata_card_safe",
              "status": "pass"
            }
          ],
          "status": "pass",
          "summary": "Model-provider health metadata validates before storage."
        },
        "warnings": [
          "model_provider_health_unavailable",
          "provider_details_internal_only",
          "automatic_retry_not_scheduled"
        ]
      },
      "health_call_count": 1,
      "health_validation": {
        "accepted": true,
        "code": "accepted",
        "config_entry_id": "provider-health-unavailable-entry",
        "health_id": "provider-health-unavailable-entry-model-provider-health-001",
        "health_path": "/api/tags",
        "status": "unavailable"
      },
      "plan_call_count": 0,
      "result": {
        "accepted": true,
        "code": "model_provider_health_connection_error",
        "config_entry_scoped": true,
        "enabled": false,
        "entry_id": "provider-health-unavailable-entry",
        "health": {
          "code": "model_provider_health_connection_error",
          "config_entry_id": "provider-health-unavailable-entry",
          "health_id": "provider-health-unavailable-entry-model-provider-health-001",
          "orchestration": {
            "automatic_progress_task_called": false,
            "automatic_retry_called": false,
            "chart_artifact_written": false,
            "chart_rendering_called": false,
            "durable_retry_storage_written": false,
            "durable_storage_written": false,
            "home_assistant_history_read": false,
            "home_assistant_service_or_state_mutation_called": false,
            "model_provider_health_bookkeeping_written": true,
            "model_provider_health_check_called": true,
            "model_provider_health_request_validated": true,
            "model_provider_health_response_validated": true,
            "model_provider_planning_called": false,
            "model_provider_retry_policy_written": false,
            "new_provider_transport_added": false,
            "provider_details_leaked_to_card": false,
            "retry_behavior_called": false,
            "scheduler_called": false,
            "semantic_memory_called": false,
            "token_generated": false,
            "token_rotation_called": false,
            "worker_called": false,
            "worker_health_check_called": false
          },
          "provider": {
            "endpoint_url": "http://ollama-a.local:11434",
            "health_path": "/api/tags",
            "model": "llama3.1",
            "role": "planner",
            "type": "ollama_compatible"
          },
          "request": {
            "headers": {
              "accept": "application/json"
            },
            "method": "GET",
            "path": "/api/tags",
            "protocol_version": 1
          },
          "response": {
            "accepted": false,
            "capabilities": {
              "planning": false,
              "structured_output": false
            },
            "checks": [],
            "code": "model_provider_health_connection_error",
            "message": "Connection refused by provider health endpoint.",
            "status": "unavailable"
          },
          "status": "unavailable",
          "type": "isolinear_model_provider_health",
          "validation": {
            "checks": [
              {
                "name": "model_provider_health_request",
                "status": "pass"
              },
              {
                "name": "model_provider_health_response",
                "status": "pass"
              },
              {
                "name": "provider_health_metadata_card_safe",
                "status": "pass"
              }
            ],
            "status": "pass",
            "summary": "Model-provider health metadata validates before storage."
          },
          "warnings": [
            "model_provider_health_unavailable",
            "provider_details_internal_only",
            "automatic_retry_not_scheduled"
          ]
        },
        "orchestration": {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": true,
          "model_provider_health_check_called": true,
          "model_provider_health_request_validated": true,
          "model_provider_health_response_validated": true,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        },
        "status": "unavailable",
        "validation": {
          "accepted": true,
          "code": "accepted",
          "schema": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\docs\\schemas\\integration-model-provider-health.schema.json"
        }
      },
      "retry_or_scheduler_side_effects": {
        "automatic_retry_called": false,
        "durable_retry_storage_written": false,
        "model_provider_retry_policy_written": false,
        "retry_behavior_called": false,
        "scheduler_called": false
      }
    }
  },
  "when": {
    "operation": "explicitly_check_model_provider_health"
  }
}
PASS transport_failure_records_unavailable_provider_health
CASE malformed_accepted_provider_health_response_fails_before_storage
{
  "case_id": "malformed_accepted_provider_health_response_fails_before_storage",
  "given": {
    "config_entry_id": "provider-health-malformed-entry",
    "provider_response_status": "surprising"
  },
  "then": {
    "malformed": {
      "health_call_count": 1,
      "health_validation": {
        "accepted": false,
        "code": "not_written"
      },
      "health_written": false,
      "plan_call_count": 0,
      "result": {
        "accepted": false,
        "code": "invalid_model_provider_health_response",
        "enabled": false,
        "orchestration": {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": false,
          "model_provider_health_check_called": true,
          "model_provider_health_request_validated": true,
          "model_provider_health_response_validated": false,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        }
      }
    }
  },
  "when": {
    "operation": "explicitly_check_model_provider_health"
  }
}
PASS malformed_accepted_provider_health_response_fails_before_storage
CASE secret_bearing_provider_health_response_fails_before_storage
{
  "case_id": "secret_bearing_provider_health_response_fails_before_storage",
  "given": {
    "config_entry_id": "provider-health-secret-entry",
    "provider_response_contains_secret_like_text": true
  },
  "then": {
    "secret": {
      "health_call_count": 1,
      "health_written": false,
      "plan_call_count": 0,
      "result": {
        "accepted": false,
        "code": "invalid_model_provider_health_response",
        "enabled": false,
        "orchestration": {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": false,
          "model_provider_health_check_called": true,
          "model_provider_health_request_validated": true,
          "model_provider_health_response_validated": false,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        }
      },
      "secret_absent_from_result": true
    }
  },
  "when": {
    "operation": "explicitly_check_model_provider_health"
  }
}
PASS secret_bearing_provider_health_response_fails_before_storage
CASE unconfigured_entry_rejected_before_provider_call
{
  "case_id": "unconfigured_entry_rejected_before_provider_call",
  "given": {
    "config_entry_id": "provider-health-unconfigured-entry",
    "model_provider_planner_configured": false
  },
  "then": {
    "unconfigured": {
      "health_setup": {
        "accepted": true,
        "code": "model_provider_health_probe_disabled",
        "config_entry_scoped": true,
        "enabled": false,
        "entry_id": "provider-health-unconfigured-entry",
        "orchestration": {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": false,
          "model_provider_health_check_called": false,
          "model_provider_health_request_validated": false,
          "model_provider_health_response_validated": false,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        },
        "provider": null
      },
      "health_written": false,
      "planner_client_present": false,
      "result": {
        "accepted": false,
        "code": "model_provider_health_not_configured",
        "enabled": false,
        "orchestration": {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": false,
          "model_provider_health_check_called": false,
          "model_provider_health_request_validated": false,
          "model_provider_health_response_validated": false,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        }
      }
    }
  },
  "when": {
    "operation": "explicitly_check_model_provider_health"
  }
}
PASS unconfigured_entry_rejected_before_provider_call
CASE unknown_config_entry_rejected_before_provider_call
{
  "case_id": "unknown_config_entry_rejected_before_provider_call",
  "given": {
    "config_entry_id": "missing-provider-health-entry"
  },
  "then": {
    "unknown": {
      "entry_created": false,
      "health_written": false,
      "result": {
        "accepted": false,
        "code": "unknown_config_entry",
        "enabled": false,
        "orchestration": {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": false,
          "model_provider_health_check_called": false,
          "model_provider_health_request_validated": false,
          "model_provider_health_response_validated": false,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        }
      }
    }
  },
  "when": {
    "operation": "explicitly_check_model_provider_health"
  }
}
PASS unknown_config_entry_rejected_before_provider_call
CASE model_provider_health_stays_config_entry_scoped
{
  "case_id": "model_provider_health_stays_config_entry_scoped",
  "given": {
    "entry_ids": [
      "provider-health-isolation-entry-a",
      "provider-health-isolation-entry-b"
    ]
  },
  "then": {
    "isolation": {
      "entry_a": {
        "health": {
          "code": "model_provider_health_ready",
          "config_entry_id": "provider-health-isolation-entry-a",
          "health_id": "provider-health-isolation-entry-a-model-provider-health-001",
          "orchestration": {
            "automatic_progress_task_called": false,
            "automatic_retry_called": false,
            "chart_artifact_written": false,
            "chart_rendering_called": false,
            "durable_retry_storage_written": false,
            "durable_storage_written": false,
            "home_assistant_history_read": false,
            "home_assistant_service_or_state_mutation_called": false,
            "model_provider_health_bookkeeping_written": true,
            "model_provider_health_check_called": true,
            "model_provider_health_request_validated": true,
            "model_provider_health_response_validated": true,
            "model_provider_planning_called": false,
            "model_provider_retry_policy_written": false,
            "new_provider_transport_added": false,
            "provider_details_leaked_to_card": false,
            "retry_behavior_called": false,
            "scheduler_called": false,
            "semantic_memory_called": false,
            "token_generated": false,
            "token_rotation_called": false,
            "worker_called": false,
            "worker_health_check_called": false
          },
          "provider": {
            "endpoint_url": "http://ollama-a.local:11434",
            "health_path": "/api/tags",
            "model": "llama3.1",
            "role": "planner",
            "type": "ollama_compatible"
          },
          "request": {
            "headers": {
              "accept": "application/json"
            },
            "method": "GET",
            "path": "/api/tags",
            "protocol_version": 1
          },
          "response": {
            "accepted": true,
            "capabilities": {
              "planning": true,
              "structured_output": true
            },
            "checks": [
              {
                "name": "ollama_tags_endpoint",
                "status": "pass"
              },
              {
                "name": "planner_model",
                "status": "pass"
              }
            ],
            "code": "model_provider_health_ready",
            "message": "Model-provider health endpoint reports ready.",
            "status": "ready"
          },
          "status": "ready",
          "type": "isolinear_model_provider_health",
          "validation": {
            "checks": [
              {
                "name": "model_provider_health_request",
                "status": "pass"
              },
              {
                "name": "model_provider_health_response",
                "status": "pass"
              },
              {
                "name": "provider_health_metadata_card_safe",
                "status": "pass"
              }
            ],
            "status": "pass",
            "summary": "Model-provider health metadata validates before storage."
          },
          "warnings": [
            "model_provider_health_ready",
            "provider_details_internal_only"
          ]
        },
        "health_call_count": 1,
        "health_validation": {
          "accepted": true,
          "code": "accepted",
          "config_entry_id": "provider-health-isolation-entry-a",
          "health_id": "provider-health-isolation-entry-a-model-provider-health-001",
          "health_path": "/api/tags",
          "status": "ready"
        },
        "other_endpoint_absent": true,
        "plan_call_count": 0,
        "request": {
          "headers": {
            "accept": "application/json"
          },
          "method": "GET",
          "path": "/api/tags",
          "protocol_version": 1
        },
        "result": {
          "accepted": true,
          "code": "model_provider_health_ready",
          "config_entry_scoped": true,
          "enabled": true,
          "entry_id": "provider-health-isolation-entry-a",
          "health": {
            "code": "model_provider_health_ready",
            "config_entry_id": "provider-health-isolation-entry-a",
            "health_id": "provider-health-isolation-entry-a-model-provider-health-001",
            "orchestration": {
              "automatic_progress_task_called": false,
              "automatic_retry_called": false,
              "chart_artifact_written": false,
              "chart_rendering_called": false,
              "durable_retry_storage_written": false,
              "durable_storage_written": false,
              "home_assistant_history_read": false,
              "home_assistant_service_or_state_mutation_called": false,
              "model_provider_health_bookkeeping_written": true,
              "model_provider_health_check_called": true,
              "model_provider_health_request_validated": true,
              "model_provider_health_response_validated": true,
              "model_provider_planning_called": false,
              "model_provider_retry_policy_written": false,
              "new_provider_transport_added": false,
              "provider_details_leaked_to_card": false,
              "retry_behavior_called": false,
              "scheduler_called": false,
              "semantic_memory_called": false,
              "token_generated": false,
              "token_rotation_called": false,
              "worker_called": false,
              "worker_health_check_called": false
            },
            "provider": {
              "endpoint_url": "http://ollama-a.local:11434",
              "health_path": "/api/tags",
              "model": "llama3.1",
              "role": "planner",
              "type": "ollama_compatible"
            },
            "request": {
              "headers": {
                "accept": "application/json"
              },
              "method": "GET",
              "path": "/api/tags",
              "protocol_version": 1
            },
            "response": {
              "accepted": true,
              "capabilities": {
                "planning": true,
                "structured_output": true
              },
              "checks": [
                {
                  "name": "ollama_tags_endpoint",
                  "status": "pass"
                },
                {
                  "name": "planner_model",
                  "status": "pass"
                }
              ],
              "code": "model_provider_health_ready",
              "message": "Model-provider health endpoint reports ready.",
              "status": "ready"
            },
            "status": "ready",
            "type": "isolinear_model_provider_health",
            "validation": {
              "checks": [
                {
                  "name": "model_provider_health_request",
                  "status": "pass"
                },
                {
                  "name": "model_provider_health_response",
                  "status": "pass"
                },
                {
                  "name": "provider_health_metadata_card_safe",
                  "status": "pass"
                }
              ],
              "status": "pass",
              "summary": "Model-provider health metadata validates before storage."
            },
            "warnings": [
              "model_provider_health_ready",
              "provider_details_internal_only"
            ]
          },
          "orchestration": {
            "automatic_progress_task_called": false,
            "automatic_retry_called": false,
            "chart_artifact_written": false,
            "chart_rendering_called": false,
            "durable_retry_storage_written": false,
            "durable_storage_written": false,
            "home_assistant_history_read": false,
            "home_assistant_service_or_state_mutation_called": false,
            "model_provider_health_bookkeeping_written": true,
            "model_provider_health_check_called": true,
            "model_provider_health_request_validated": true,
            "model_provider_health_response_validated": true,
            "model_provider_planning_called": false,
            "model_provider_retry_policy_written": false,
            "new_provider_transport_added": false,
            "provider_details_leaked_to_card": false,
            "retry_behavior_called": false,
            "scheduler_called": false,
            "semantic_memory_called": false,
            "token_generated": false,
            "token_rotation_called": false,
            "worker_called": false,
            "worker_health_check_called": false
          },
          "status": "ready",
          "validation": {
            "accepted": true,
            "code": "accepted",
            "schema": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\docs\\schemas\\integration-model-provider-health.schema.json"
          }
        },
        "stored_endpoint": "http://ollama-a.local:11434"
      },
      "entry_b": {
        "health": {
          "code": "model_provider_health_not_ready",
          "config_entry_id": "provider-health-isolation-entry-b",
          "health_id": "provider-health-isolation-entry-b-model-provider-health-001",
          "orchestration": {
            "automatic_progress_task_called": false,
            "automatic_retry_called": false,
            "chart_artifact_written": false,
            "chart_rendering_called": false,
            "durable_retry_storage_written": false,
            "durable_storage_written": false,
            "home_assistant_history_read": false,
            "home_assistant_service_or_state_mutation_called": false,
            "model_provider_health_bookkeeping_written": true,
            "model_provider_health_check_called": true,
            "model_provider_health_request_validated": true,
            "model_provider_health_response_validated": true,
            "model_provider_planning_called": false,
            "model_provider_retry_policy_written": false,
            "new_provider_transport_added": false,
            "provider_details_leaked_to_card": false,
            "retry_behavior_called": false,
            "scheduler_called": false,
            "semantic_memory_called": false,
            "token_generated": false,
            "token_rotation_called": false,
            "worker_called": false,
            "worker_health_check_called": false
          },
          "provider": {
            "endpoint_url": "http://ollama-b.local:11434",
            "health_path": "/api/tags",
            "model": "mistral",
            "role": "planner",
            "type": "ollama_compatible"
          },
          "request": {
            "headers": {
              "accept": "application/json"
            },
            "method": "GET",
            "path": "/api/tags",
            "protocol_version": 1
          },
          "response": {
            "accepted": true,
            "capabilities": {
              "planning": false,
              "structured_output": false
            },
            "checks": [
              {
                "name": "ollama_tags_endpoint",
                "status": "pass"
              },
              {
                "name": "planner_model",
                "status": "not_ready"
              }
            ],
            "code": "model_provider_health_not_ready",
            "message": "Model-provider health endpoint reports not_ready.",
            "status": "not_ready"
          },
          "status": "not_ready",
          "type": "isolinear_model_provider_health",
          "validation": {
            "checks": [
              {
                "name": "model_provider_health_request",
                "status": "pass"
              },
              {
                "name": "model_provider_health_response",
                "status": "pass"
              },
              {
                "name": "provider_health_metadata_card_safe",
                "status": "pass"
              }
            ],
            "status": "pass",
            "summary": "Model-provider health metadata validates before storage."
          },
          "warnings": [
            "model_provider_health_not_ready",
            "provider_details_internal_only"
          ]
        },
        "health_call_count": 1,
        "health_validation": {
          "accepted": true,
          "code": "accepted",
          "config_entry_id": "provider-health-isolation-entry-b",
          "health_id": "provider-health-isolation-entry-b-model-provider-health-001",
          "health_path": "/api/tags",
          "status": "not_ready"
        },
        "other_endpoint_absent": true,
        "plan_call_count": 0,
        "request": {
          "headers": {
            "accept": "application/json"
          },
          "method": "GET",
          "path": "/api/tags",
          "protocol_version": 1
        },
        "result": {
          "accepted": true,
          "code": "model_provider_health_not_ready",
          "config_entry_scoped": true,
          "enabled": false,
          "entry_id": "provider-health-isolation-entry-b",
          "health": {
            "code": "model_provider_health_not_ready",
            "config_entry_id": "provider-health-isolation-entry-b",
            "health_id": "provider-health-isolation-entry-b-model-provider-health-001",
            "orchestration": {
              "automatic_progress_task_called": false,
              "automatic_retry_called": false,
              "chart_artifact_written": false,
              "chart_rendering_called": false,
              "durable_retry_storage_written": false,
              "durable_storage_written": false,
              "home_assistant_history_read": false,
              "home_assistant_service_or_state_mutation_called": false,
              "model_provider_health_bookkeeping_written": true,
              "model_provider_health_check_called": true,
              "model_provider_health_request_validated": true,
              "model_provider_health_response_validated": true,
              "model_provider_planning_called": false,
              "model_provider_retry_policy_written": false,
              "new_provider_transport_added": false,
              "provider_details_leaked_to_card": false,
              "retry_behavior_called": false,
              "scheduler_called": false,
              "semantic_memory_called": false,
              "token_generated": false,
              "token_rotation_called": false,
              "worker_called": false,
              "worker_health_check_called": false
            },
            "provider": {
              "endpoint_url": "http://ollama-b.local:11434",
              "health_path": "/api/tags",
              "model": "mistral",
              "role": "planner",
              "type": "ollama_compatible"
            },
            "request": {
              "headers": {
                "accept": "application/json"
              },
              "method": "GET",
              "path": "/api/tags",
              "protocol_version": 1
            },
            "response": {
              "accepted": true,
              "capabilities": {
                "planning": false,
                "structured_output": false
              },
              "checks": [
                {
                  "name": "ollama_tags_endpoint",
                  "status": "pass"
                },
                {
                  "name": "planner_model",
                  "status": "not_ready"
                }
              ],
              "code": "model_provider_health_not_ready",
              "message": "Model-provider health endpoint reports not_ready.",
              "status": "not_ready"
            },
            "status": "not_ready",
            "type": "isolinear_model_provider_health",
            "validation": {
              "checks": [
                {
                  "name": "model_provider_health_request",
                  "status": "pass"
                },
                {
                  "name": "model_provider_health_response",
                  "status": "pass"
                },
                {
                  "name": "provider_health_metadata_card_safe",
                  "status": "pass"
                }
              ],
              "status": "pass",
              "summary": "Model-provider health metadata validates before storage."
            },
            "warnings": [
              "model_provider_health_not_ready",
              "provider_details_internal_only"
            ]
          },
          "orchestration": {
            "automatic_progress_task_called": false,
            "automatic_retry_called": false,
            "chart_artifact_written": false,
            "chart_rendering_called": false,
            "durable_retry_storage_written": false,
            "durable_storage_written": false,
            "home_assistant_history_read": false,
            "home_assistant_service_or_state_mutation_called": false,
            "model_provider_health_bookkeeping_written": true,
            "model_provider_health_check_called": true,
            "model_provider_health_request_validated": true,
            "model_provider_health_response_validated": true,
            "model_provider_planning_called": false,
            "model_provider_retry_policy_written": false,
            "new_provider_transport_added": false,
            "provider_details_leaked_to_card": false,
            "retry_behavior_called": false,
            "scheduler_called": false,
            "semantic_memory_called": false,
            "token_generated": false,
            "token_rotation_called": false,
            "worker_called": false,
            "worker_health_check_called": false
          },
          "status": "not_ready",
          "validation": {
            "accepted": true,
            "code": "accepted",
            "schema": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\docs\\schemas\\integration-model-provider-health.schema.json"
          }
        },
        "setup": {
          "accepted": true,
          "code": "model_provider_health_probe_available",
          "config_entry_scoped": true,
          "enabled": true,
          "entry_id": "provider-health-isolation-entry-b",
          "orchestration": {
            "automatic_progress_task_called": false,
            "automatic_retry_called": false,
            "chart_artifact_written": false,
            "chart_rendering_called": false,
            "durable_retry_storage_written": false,
            "durable_storage_written": false,
            "home_assistant_history_read": false,
            "home_assistant_service_or_state_mutation_called": false,
            "model_provider_health_bookkeeping_written": false,
            "model_provider_health_check_called": false,
            "model_provider_health_request_validated": false,
            "model_provider_health_response_validated": false,
            "model_provider_planning_called": false,
            "model_provider_retry_policy_written": false,
            "new_provider_transport_added": false,
            "provider_details_leaked_to_card": false,
            "retry_behavior_called": false,
            "scheduler_called": false,
            "semantic_memory_called": false,
            "token_generated": false,
            "token_rotation_called": false,
            "worker_called": false,
            "worker_health_check_called": false
          },
          "provider": {
            "endpoint_url": "http://ollama-b.local:11434",
            "health_path": "/api/tags",
            "model": "mistral",
            "role": "planner",
            "type": "ollama_compatible"
          }
        },
        "stored_endpoint": "http://ollama-b.local:11434"
      }
    }
  },
  "when": {
    "operation": "check_health_for_both_entries"
  }
}
PASS model_provider_health_stays_config_entry_scoped
CASE model_provider_health_details_do_not_leak_to_card
{
  "case_id": "model_provider_health_details_do_not_leak_to_card",
  "given": {
    "config_entry_id": "provider-health-leak-entry"
  },
  "then": {
    "leakage": {
      "endpoint_absent_from_dashboard_payload": true,
      "endpoint_absent_from_worker_metadata": true,
      "evidence_contains_internal_health": true,
      "health_absent_from_dashboard_payload": true,
      "health_validation": {
        "accepted": true,
        "code": "accepted",
        "config_entry_id": "provider-health-leak-entry",
        "health_id": "provider-health-leak-entry-model-provider-health-001",
        "health_path": "/api/tags",
        "status": "ready"
      },
      "provider_endpoint_internal_only": true,
      "request_absent_from_dashboard_payload": true,
      "response_absent_from_dashboard_payload": true
    }
  },
  "when": {
    "operation": "inspect_health_setup_dashboard_worker_and_evidence_payloads"
  }
}
PASS model_provider_health_details_do_not_leak_to_card
CASE model_provider_health_diagnostics_remain_bounded
{
  "case_id": "model_provider_health_diagnostics_remain_bounded",
  "given": {
    "handled_surfaces": [
      "ready_health",
      "not_ready_health",
      "unavailable_health",
      "malformed_response",
      "secret_response",
      "unconfigured_entry",
      "unknown_config_entry",
      "config_entry_isolation"
    ]
  },
  "then": {
    "side_effects": {
      "allowed_aggregate": {
        "model_provider_health_bookkeeping_written": true,
        "model_provider_health_check_called": true,
        "model_provider_health_request_validated": true,
        "model_provider_health_response_validated": true
      },
      "expected_forbidden": {
        "automatic_progress_task_called": false,
        "automatic_retry_called": false,
        "chart_artifact_written": false,
        "chart_rendering_called": false,
        "durable_retry_storage_written": false,
        "durable_storage_written": false,
        "home_assistant_history_read": false,
        "home_assistant_service_or_state_mutation_called": false,
        "model_provider_planning_called": false,
        "model_provider_retry_policy_written": false,
        "new_provider_transport_added": false,
        "provider_details_leaked_to_card": false,
        "retry_behavior_called": false,
        "scheduler_called": false,
        "semantic_memory_called": false,
        "token_generated": false,
        "token_rotation_called": false,
        "worker_called": false,
        "worker_health_check_called": false
      },
      "forbidden_aggregate": {
        "automatic_progress_task_called": false,
        "automatic_retry_called": false,
        "chart_artifact_written": false,
        "chart_rendering_called": false,
        "durable_retry_storage_written": false,
        "durable_storage_written": false,
        "home_assistant_history_read": false,
        "home_assistant_service_or_state_mutation_called": false,
        "model_provider_planning_called": false,
        "model_provider_retry_policy_written": false,
        "new_provider_transport_added": false,
        "provider_details_leaked_to_card": false,
        "retry_behavior_called": false,
        "scheduler_called": false,
        "semantic_memory_called": false,
        "token_generated": false,
        "token_rotation_called": false,
        "worker_called": false,
        "worker_health_check_called": false
      },
      "observed": [
        {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": true,
          "model_provider_health_check_called": true,
          "model_provider_health_request_validated": true,
          "model_provider_health_response_validated": true,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "name": "ready_health",
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        },
        {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": true,
          "model_provider_health_check_called": true,
          "model_provider_health_request_validated": true,
          "model_provider_health_response_validated": true,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "name": "not_ready_health",
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        },
        {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": true,
          "model_provider_health_check_called": true,
          "model_provider_health_request_validated": true,
          "model_provider_health_response_validated": true,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "name": "unavailable_health",
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        },
        {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": false,
          "model_provider_health_check_called": true,
          "model_provider_health_request_validated": true,
          "model_provider_health_response_validated": false,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "name": "malformed_rejection",
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        },
        {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": false,
          "model_provider_health_check_called": true,
          "model_provider_health_request_validated": true,
          "model_provider_health_response_validated": false,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "name": "secret_rejection",
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        },
        {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": false,
          "model_provider_health_check_called": false,
          "model_provider_health_request_validated": false,
          "model_provider_health_response_validated": false,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "name": "unconfigured_rejection",
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        },
        {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": false,
          "model_provider_health_check_called": false,
          "model_provider_health_request_validated": false,
          "model_provider_health_response_validated": false,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "name": "unknown_rejection",
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        },
        {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": true,
          "model_provider_health_check_called": true,
          "model_provider_health_request_validated": true,
          "model_provider_health_response_validated": true,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "name": "isolation_entry_a",
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        },
        {
          "automatic_progress_task_called": false,
          "automatic_retry_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_retry_storage_written": false,
          "durable_storage_written": false,
          "home_assistant_history_read": false,
          "home_assistant_service_or_state_mutation_called": false,
          "model_provider_health_bookkeeping_written": true,
          "model_provider_health_check_called": true,
          "model_provider_health_request_validated": true,
          "model_provider_health_response_validated": true,
          "model_provider_planning_called": false,
          "model_provider_retry_policy_written": false,
          "name": "isolation_entry_b",
          "new_provider_transport_added": false,
          "provider_details_leaked_to_card": false,
          "retry_behavior_called": false,
          "scheduler_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "token_rotation_called": false,
          "worker_called": false,
          "worker_health_check_called": false
        }
      ]
    }
  },
  "when": {
    "operation": "aggregate_observed_side_effects"
  }
}
PASS model_provider_health_diagnostics_remain_bounded
PASS home_assistant_model_provider_health_diagnostics_scaffold
