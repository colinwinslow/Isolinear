# Home Assistant Integration Scaffold Evidence

Run timestamp: 2026-06-07T23:16:23+00:00

BDD file:
`bdd/integration/home-assistant-integration-scaffold-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: scaffold package is visible to Home Assistant -> `CASE scaffold_package_is_visible_to_home_assistant`
- Scenario B: local-first configuration shape is inspectable -> `CASE local_first_configuration_shape_is_inspectable`
- Scenario C: known card commands are accepted as stubs -> `CASE known_card_commands_are_accepted_as_stubs`
- Scenario D: unknown or unsupported commands fail closed -> `CASE unknown_or_unsupported_commands_fail_closed`
- Scenario E: leaky or mutating card payloads fail closed -> `CASE leaky_or_mutating_payloads_fail_closed_without_orchestration`

## Focused Unit Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_integration_scaffold_anchor.py
```

Raw output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 5 items

tests\test_integration_scaffold_anchor.py .....                          [100%]

============================== 5 passed in 0.20s ==============================
```

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_integration_scaffold.py
```

Raw output:

```text
CASE scaffold_package_is_visible_to_home_assistant
{
  "case_id": "scaffold_package_is_visible_to_home_assistant",
  "given": {
    "package": "custom_components/isolinear",
    "run_timestamp": "2026-06-07T23:16:23+00:00"
  },
  "then": {
    "command_types": {
      "answer_clarification": "isolinear/v1/clarification/answer",
      "get_snapshot": "isolinear/v1/job/snapshot",
      "retry_job": "isolinear/v1/job/retry",
      "start_job": "isolinear/v1/job/start",
      "subscribe_job": "isolinear/v1/job/subscribe"
    },
    "manifest": {
      "all_scaffold_files_present": true,
      "domain_matches": true,
      "files": {
        "custom_components/isolinear/__init__.py": true,
        "custom_components/isolinear/config_schema.py": true,
        "custom_components/isolinear/const.py": true,
        "custom_components/isolinear/manifest.json": true,
        "custom_components/isolinear/websocket_api.py": true
      },
      "manifest": {
        "codeowners": [],
        "config_flow": false,
        "dependencies": [],
        "documentation": "https://github.com/kagwerks/isolinear",
        "domain": "isolinear",
        "integration_type": "hub",
        "iot_class": "local_polling",
        "name": "Isolinear",
        "requirements": [],
        "version": "0.1.0"
      },
      "requirements_empty": true,
      "version_present": true
    }
  },
  "when": {
    "operation": "inspect_manifest_and_constants"
  }
}
PASS scaffold_package_is_visible_to_home_assistant
CASE local_first_configuration_shape_is_inspectable
{
  "case_id": "local_first_configuration_shape_is_inspectable",
  "given": {
    "config_fields": [
      "model_provider_type",
      "model_endpoint_url",
      "planner_model",
      "codegen_model",
      "visual_validator_model",
      "worker_endpoint_url"
    ],
    "options_fields": [
      "default_render_mode",
      "max_codegen_repair_attempts",
      "entity_allowlist"
    ]
  },
  "then": {
    "defaults": {
      "config_data": {
        "codegen_model": null,
        "model_endpoint_url": "http://localhost:11434",
        "model_provider_type": "ollama_compatible",
        "planner_model": "llama3.1",
        "visual_validator_model": null,
        "worker_endpoint_url": "http://localhost:8765"
      },
      "options_data": {
        "default_render_mode": "safe",
        "entity_allowlist": [],
        "max_codegen_repair_attempts": 1
      },
      "result": {
        "accepted": true,
        "code": "accepted",
        "config": {
          "codegen_model": null,
          "model_endpoint_url": "http://localhost:11434",
          "model_provider_type": "ollama_compatible",
          "planner_model": "llama3.1",
          "visual_validator_model": null,
          "worker_endpoint_url": "http://localhost:8765"
        },
        "options": {
          "default_render_mode": "safe",
          "entity_allowlist": [],
          "max_codegen_repair_attempts": 1
        }
      }
    },
    "invalid_results": {
      "credential_endpoint_url": {
        "accepted": false,
        "code": "invalid_integration_config",
        "errors": [
          {
            "path": "$.config_data.worker_endpoint_url",
            "reason": "endpoint_userinfo_forbidden"
          }
        ]
      },
      "duplicate_allowlist": {
        "accepted": false,
        "code": "invalid_integration_config",
        "errors": [
          {
            "path": "$.options_data.entity_allowlist",
            "reason": "duplicate_entity_id"
          }
        ]
      },
      "invalid_render_mode": {
        "accepted": false,
        "code": "invalid_integration_config",
        "errors": [
          {
            "path": "$.options_data.default_render_mode",
            "reason": "unsupported_render_mode"
          }
        ]
      },
      "malformed_allowlist": {
        "accepted": false,
        "code": "invalid_integration_config",
        "errors": [
          {
            "path": "$.options_data.entity_allowlist[0]",
            "reason": "invalid_entity_id"
          }
        ]
      },
      "secret_bearing": {
        "accepted": false,
        "code": "forbidden_config_material",
        "forbidden_matches": [
          {
            "path": "$.config_data.worker_token",
            "reason": "forbidden_key"
          }
        ]
      },
      "secret_like_allowed_value": {
        "accepted": false,
        "code": "forbidden_config_material",
        "forbidden_matches": [
          {
            "path": "$.config_data.planner_model",
            "reason": "secret_like_value"
          }
        ]
      }
    }
  },
  "when": {
    "operation": "validate_default_and_invalid_config_shapes"
  }
}
PASS local_first_configuration_shape_is_inspectable
CASE known_card_commands_are_accepted_as_stubs
{
  "case_id": "known_card_commands_are_accepted_as_stubs",
  "given": {
    "schema": "docs/schemas/integration-ws-command.schema.json",
    "snapshot_schema": "docs/schemas/integration-job-snapshot.schema.json"
  },
  "then": {
    "accepted_results": {
      "answer_clarification": {
        "accepted": true,
        "code": "scaffold_command_accepted",
        "orchestration": {
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "worker_called": false
        },
        "snapshot": {
          "job_id": "job-clarify-001",
          "message": "Command schema accepted by the integration scaffold; orchestration is not implemented yet.",
          "progress": {
            "message": "Waiting for a later orchestration packet.",
            "stage": "scaffold"
          },
          "prompt": "",
          "snapshot_id": "scaffold-answer",
          "state_label": "Scaffold",
          "status": "planning",
          "validation": {
            "checks": [
              {
                "name": "integration_ws_command_boundary",
                "status": "pass"
              },
              {
                "name": "orchestration",
                "status": "not_implemented"
              }
            ],
            "status": "not_run",
            "summary": "The scaffold validated only the card-facing command boundary."
          },
          "warnings": [
            "orchestration_not_implemented"
          ]
        },
        "type": "isolinear/v1/clarification/answer",
        "version": 1
      },
      "get_snapshot": {
        "accepted": true,
        "code": "scaffold_command_accepted",
        "orchestration": {
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "worker_called": false
        },
        "snapshot": {
          "job_id": "job-complete-001",
          "message": "Command schema accepted by the integration scaffold; orchestration is not implemented yet.",
          "progress": {
            "message": "Waiting for a later orchestration packet.",
            "stage": "scaffold"
          },
          "prompt": "",
          "snapshot_id": "scaffold-snapshot",
          "state_label": "Scaffold",
          "status": "planning",
          "validation": {
            "checks": [
              {
                "name": "integration_ws_command_boundary",
                "status": "pass"
              },
              {
                "name": "orchestration",
                "status": "not_implemented"
              }
            ],
            "status": "not_run",
            "summary": "The scaffold validated only the card-facing command boundary."
          },
          "warnings": [
            "orchestration_not_implemented"
          ]
        },
        "type": "isolinear/v1/job/snapshot",
        "version": 1
      },
      "retry_job": {
        "accepted": true,
        "code": "scaffold_command_accepted",
        "orchestration": {
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "worker_called": false
        },
        "snapshot": {
          "job_id": "job-failed-001",
          "message": "Command schema accepted by the integration scaffold; orchestration is not implemented yet.",
          "progress": {
            "message": "Waiting for a later orchestration packet.",
            "stage": "scaffold"
          },
          "prompt": "",
          "snapshot_id": "scaffold-retry",
          "state_label": "Scaffold",
          "status": "planning",
          "validation": {
            "checks": [
              {
                "name": "integration_ws_command_boundary",
                "status": "pass"
              },
              {
                "name": "orchestration",
                "status": "not_implemented"
              }
            ],
            "status": "not_run",
            "summary": "The scaffold validated only the card-facing command boundary."
          },
          "warnings": [
            "orchestration_not_implemented"
          ]
        },
        "type": "isolinear/v1/job/retry",
        "version": 1
      },
      "start_job": {
        "accepted": true,
        "code": "scaffold_command_accepted",
        "orchestration": {
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "worker_called": false
        },
        "snapshot": {
          "job_id": "scaffold-job-001",
          "message": "Command schema accepted by the integration scaffold; orchestration is not implemented yet.",
          "progress": {
            "message": "Waiting for a later orchestration packet.",
            "stage": "scaffold"
          },
          "prompt": "Compare upstairs and downstairs temperatures",
          "snapshot_id": "scaffold-start",
          "state_label": "Scaffold",
          "status": "planning",
          "validation": {
            "checks": [
              {
                "name": "integration_ws_command_boundary",
                "status": "pass"
              },
              {
                "name": "orchestration",
                "status": "not_implemented"
              }
            ],
            "status": "not_run",
            "summary": "The scaffold validated only the card-facing command boundary."
          },
          "warnings": [
            "orchestration_not_implemented"
          ]
        },
        "type": "isolinear/v1/job/start",
        "version": 1
      },
      "subscribe_job": {
        "accepted": true,
        "code": "scaffold_command_accepted",
        "orchestration": {
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "worker_called": false
        },
        "snapshot": {
          "job_id": "job-complete-001",
          "message": "Command schema accepted by the integration scaffold; orchestration is not implemented yet.",
          "progress": {
            "message": "Waiting for a later orchestration packet.",
            "stage": "scaffold"
          },
          "prompt": "",
          "snapshot_id": "scaffold-subscribe",
          "state_label": "Scaffold",
          "status": "planning",
          "validation": {
            "checks": [
              {
                "name": "integration_ws_command_boundary",
                "status": "pass"
              },
              {
                "name": "orchestration",
                "status": "not_implemented"
              }
            ],
            "status": "not_run",
            "summary": "The scaffold validated only the card-facing command boundary."
          },
          "warnings": [
            "orchestration_not_implemented"
          ]
        },
        "type": "isolinear/v1/job/subscribe",
        "version": 1
      }
    },
    "snapshot_validation": {
      "answer_clarification": {
        "accepted": true,
        "code": "accepted",
        "status": "planning"
      },
      "get_snapshot": {
        "accepted": true,
        "code": "accepted",
        "status": "planning"
      },
      "retry_job": {
        "accepted": true,
        "code": "accepted",
        "status": "planning"
      },
      "start_job": {
        "accepted": true,
        "code": "accepted",
        "status": "planning"
      },
      "subscribe_job": {
        "accepted": true,
        "code": "accepted",
        "status": "planning"
      }
    }
  },
  "when": {
    "operation": "handle_known_scaffold_ws_commands"
  }
}
PASS known_card_commands_are_accepted_as_stubs
CASE unknown_or_unsupported_commands_fail_closed
{
  "case_id": "unknown_or_unsupported_commands_fail_closed",
  "given": {
    "invalid_examples": [
      "unknown_command",
      "wrong_version"
    ]
  },
  "then": {
    "invalid_results": {
      "unknown_command": {
        "accepted": false,
        "code": "unknown_integration_ws_command",
        "orchestration": {
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "worker_called": false
        },
        "render_attempted": false
      },
      "wrong_version": {
        "accepted": false,
        "code": "unsupported_integration_ws_version",
        "orchestration": {
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "worker_called": false
        },
        "render_attempted": false
      }
    }
  },
  "when": {
    "operation": "handle_invalid_scaffold_ws_commands"
  }
}
PASS unknown_or_unsupported_commands_fail_closed
CASE leaky_or_mutating_payloads_fail_closed_without_orchestration
{
  "case_id": "leaky_or_mutating_payloads_fail_closed_without_orchestration",
  "given": {
    "invalid_examples": [
      "leaky_worker_url",
      "mutating_service_call"
    ]
  },
  "then": {
    "invalid_results": {
      "leaky_worker_url": {
        "accepted": false,
        "code": "forbidden_card_boundary_content",
        "forbidden_matches": [
          {
            "path": "$.worker_url",
            "reason": "forbidden_key"
          }
        ],
        "orchestration": {
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "worker_called": false
        },
        "render_attempted": false
      },
      "mutating_service_call": {
        "accepted": false,
        "code": "forbidden_card_boundary_content",
        "forbidden_matches": [
          {
            "path": "$.service",
            "reason": "forbidden_key"
          },
          {
            "path": "$.target",
            "reason": "forbidden_key"
          }
        ],
        "orchestration": {
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "worker_called": false
        },
        "render_attempted": false
      }
    },
    "no_orchestration": {
      "aggregate": {
        "home_assistant_history_called": false,
        "home_assistant_mutation_called": false,
        "model_provider_called": false,
        "semantic_memory_called": false,
        "worker_called": false
      },
      "expected": {
        "home_assistant_history_called": false,
        "home_assistant_mutation_called": false,
        "model_provider_called": false,
        "semantic_memory_called": false,
        "worker_called": false
      },
      "observed": [
        {
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "name": "start_job",
          "semantic_memory_called": false,
          "worker_called": false
        },
        {
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "name": "answer_clarification",
          "semantic_memory_called": false,
          "worker_called": false
        },
        {
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "name": "retry_job",
          "semantic_memory_called": false,
          "worker_called": false
        },
        {
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "name": "get_snapshot",
          "semantic_memory_called": false,
          "worker_called": false
        },
        {
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "name": "subscribe_job",
          "semantic_memory_called": false,
          "worker_called": false
        },
        {
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "name": "unknown_command",
          "semantic_memory_called": false,
          "worker_called": false
        },
        {
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "name": "wrong_version",
          "semantic_memory_called": false,
          "worker_called": false
        },
        {
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "name": "leaky_worker_url",
          "semantic_memory_called": false,
          "worker_called": false
        },
        {
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "name": "mutating_service_call",
          "semantic_memory_called": false,
          "worker_called": false
        }
      ]
    }
  },
  "when": {
    "operation": "handle_forbidden_boundary_material"
  }
}
PASS leaky_or_mutating_payloads_fail_closed_without_orchestration
PASS home_assistant_integration_scaffold
```
