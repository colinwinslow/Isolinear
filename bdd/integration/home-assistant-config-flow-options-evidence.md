# Home Assistant Config Flow and Options Evidence

Run timestamp: 2026-06-08T00:13:46+00:00

BDD file:
`bdd/integration/home-assistant-config-flow-options-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: config flow is visible to Home Assistant -> `CASE config_flow_is_visible_to_home_assistant`
- Scenario B: user config flow creates validated local-first data -> `CASE user_config_flow_creates_validated_local_first_data`
- Scenario C: options flow persists safe options -> `CASE options_flow_persists_safe_options`
- Scenario D: invalid config flow input fails closed -> `CASE invalid_config_flow_input_fails_closed`
- Scenario E: invalid options flow input fails closed -> `CASE invalid_options_flow_input_fails_closed`
- Scenario F: setup flow remains non-orchestrating -> `CASE setup_flow_remains_non_orchestrating`

## Focused Unit Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_config_flow_options_anchor.py
```

Raw output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 5 items

tests\test_config_flow_options_anchor.py .....                           [100%]

============================== 5 passed in 0.10s ==============================
```

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_config_flow_options.py
```

Raw output:

```text
CASE config_flow_is_visible_to_home_assistant
{
  "case_id": "config_flow_is_visible_to_home_assistant",
  "given": {
    "package": "custom_components/isolinear",
    "run_timestamp": "2026-06-08T00:13:46+00:00"
  },
  "then": {
    "manifest": {
      "config_flow_class_present": true,
      "config_flow_file_present": true,
      "files": {
        "custom_components/isolinear/config_flow.py": true,
        "custom_components/isolinear/config_schema.py": true,
        "custom_components/isolinear/manifest.json": true
      },
      "flow_steps": {
        "config": "user",
        "options": "init"
      },
      "manifest": {
        "codeowners": [],
        "config_flow": true,
        "dependencies": [],
        "documentation": "https://github.com/kagwerks/isolinear",
        "domain": "isolinear",
        "integration_type": "hub",
        "iot_class": "local_polling",
        "name": "Isolinear",
        "requirements": [],
        "version": "0.1.0"
      },
      "manifest_config_flow_enabled": true,
      "metadata": {
        "config_defaults": {
          "codegen_model": null,
          "model_endpoint_url": "http://localhost:11434",
          "model_provider_type": "ollama_compatible",
          "planner_model": "llama3.1",
          "visual_validator_model": null,
          "worker_endpoint_url": "http://localhost:8765"
        },
        "config_fields": [
          "model_provider_type",
          "model_endpoint_url",
          "planner_model",
          "codegen_model",
          "visual_validator_model",
          "worker_endpoint_url"
        ],
        "config_step": "user",
        "options_defaults": {
          "default_render_mode": "safe",
          "entity_allowlist": "",
          "max_codegen_repair_attempts": 1
        },
        "options_fields": [
          "default_render_mode",
          "max_codegen_repair_attempts",
          "entity_allowlist"
        ],
        "options_step": "init",
        "supported_model_provider_types": [
          "ollama_compatible"
        ],
        "supported_render_modes": [
          "safe",
          "codegen",
          "auto"
        ]
      },
      "options_flow_class_present": true
    }
  },
  "when": {
    "operation": "inspect_manifest_and_config_flow_module"
  }
}
PASS config_flow_is_visible_to_home_assistant
CASE user_config_flow_creates_validated_local_first_data
{
  "case_id": "user_config_flow_creates_validated_local_first_data",
  "given": {
    "fields": [
      "model_provider_type",
      "model_endpoint_url",
      "planner_model",
      "codegen_model",
      "visual_validator_model",
      "worker_endpoint_url"
    ],
    "step": "user"
  },
  "then": {
    "config_flow": {
      "accepted": true,
      "code": "accepted",
      "config_data": {
        "codegen_model": null,
        "model_endpoint_url": "http://localhost:11434",
        "model_provider_type": "ollama_compatible",
        "planner_model": "llama3.1",
        "visual_validator_model": null,
        "worker_endpoint_url": "http://localhost:8765"
      },
      "entry_title": "Isolinear",
      "field_errors": {},
      "options_data": {
        "default_render_mode": "safe",
        "entity_allowlist": [],
        "max_codegen_repair_attempts": 1
      },
      "orchestration": {
        "dashboard_resource_registered": false,
        "home_assistant_history_called": false,
        "home_assistant_mutation_called": false,
        "model_provider_called": false,
        "semantic_memory_called": false,
        "token_generated": false,
        "worker_called": false
      }
    }
  },
  "when": {
    "operation": "validate_config_flow_user_input"
  }
}
PASS user_config_flow_creates_validated_local_first_data
CASE options_flow_persists_safe_options
{
  "case_id": "options_flow_persists_safe_options",
  "given": {
    "fields": [
      "default_render_mode",
      "max_codegen_repair_attempts",
      "entity_allowlist"
    ],
    "step": "init"
  },
  "then": {
    "options_flow": {
      "accepted": true,
      "code": "accepted",
      "field_errors": {},
      "options_data": {
        "default_render_mode": "auto",
        "entity_allowlist": [
          "sensor.upstairs_temperature",
          "sensor.downstairs_temperature",
          "binary_sensor.office_window"
        ],
        "max_codegen_repair_attempts": 2
      },
      "orchestration": {
        "dashboard_resource_registered": false,
        "home_assistant_history_called": false,
        "home_assistant_mutation_called": false,
        "model_provider_called": false,
        "semantic_memory_called": false,
        "token_generated": false,
        "worker_called": false
      }
    }
  },
  "when": {
    "operation": "validate_options_flow_user_input"
  }
}
PASS options_flow_persists_safe_options
CASE invalid_config_flow_input_fails_closed
{
  "case_id": "invalid_config_flow_input_fails_closed",
  "given": {
    "invalid_examples": [
      "credential_endpoint_url",
      "secret_like_model",
      "secret_config_key"
    ]
  },
  "then": {
    "invalid_config_results": {
      "credential_endpoint_url": {
        "accepted": false,
        "code": "invalid_integration_config",
        "field_errors": {
          "worker_endpoint_url": "endpoint_userinfo_forbidden"
        },
        "orchestration": {
          "dashboard_resource_registered": false,
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "worker_called": false
        },
        "validation": {
          "accepted": false,
          "code": "invalid_integration_config",
          "errors": [
            {
              "path": "$.config_data.worker_endpoint_url",
              "reason": "endpoint_userinfo_forbidden"
            }
          ]
        }
      },
      "secret_config_key": {
        "accepted": false,
        "code": "forbidden_config_material",
        "field_errors": {
          "base": "forbidden_key"
        },
        "orchestration": {
          "dashboard_resource_registered": false,
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "worker_called": false
        },
        "validation": {
          "accepted": false,
          "code": "forbidden_config_material",
          "forbidden_matches": [
            {
              "path": "$.config_data.worker_token",
              "reason": "forbidden_key"
            }
          ]
        }
      },
      "secret_like_model": {
        "accepted": false,
        "code": "forbidden_config_material",
        "field_errors": {
          "planner_model": "secret_like_value"
        },
        "orchestration": {
          "dashboard_resource_registered": false,
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "worker_called": false
        },
        "validation": {
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
    }
  },
  "when": {
    "operation": "validate_invalid_config_flow_inputs"
  }
}
PASS invalid_config_flow_input_fails_closed
CASE invalid_options_flow_input_fails_closed
{
  "case_id": "invalid_options_flow_input_fails_closed",
  "given": {
    "invalid_examples": [
      "invalid_render_mode",
      "duplicate_allowlist",
      "malformed_allowlist",
      "secret_options_material"
    ]
  },
  "then": {
    "invalid_options_results": {
      "duplicate_allowlist": {
        "accepted": false,
        "code": "invalid_integration_config",
        "field_errors": {
          "entity_allowlist": "duplicate_entity_id"
        },
        "orchestration": {
          "dashboard_resource_registered": false,
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "worker_called": false
        },
        "validation": {
          "accepted": false,
          "code": "invalid_integration_config",
          "errors": [
            {
              "path": "$.options_data.entity_allowlist",
              "reason": "duplicate_entity_id"
            }
          ]
        }
      },
      "invalid_render_mode": {
        "accepted": false,
        "code": "invalid_integration_config",
        "field_errors": {
          "default_render_mode": "unsupported_render_mode"
        },
        "orchestration": {
          "dashboard_resource_registered": false,
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "worker_called": false
        },
        "validation": {
          "accepted": false,
          "code": "invalid_integration_config",
          "errors": [
            {
              "path": "$.options_data.default_render_mode",
              "reason": "unsupported_render_mode"
            }
          ]
        }
      },
      "malformed_allowlist": {
        "accepted": false,
        "code": "invalid_integration_config",
        "field_errors": {
          "entity_allowlist": "invalid_entity_id"
        },
        "orchestration": {
          "dashboard_resource_registered": false,
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "worker_called": false
        },
        "validation": {
          "accepted": false,
          "code": "invalid_integration_config",
          "errors": [
            {
              "path": "$.options_data.entity_allowlist[0]",
              "reason": "invalid_entity_id"
            }
          ]
        }
      },
      "secret_options_material": {
        "accepted": false,
        "code": "forbidden_config_material",
        "field_errors": {
          "base": "forbidden_key"
        },
        "orchestration": {
          "dashboard_resource_registered": false,
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "worker_called": false
        },
        "validation": {
          "accepted": false,
          "code": "forbidden_config_material",
          "forbidden_matches": [
            {
              "path": "$.options_data.worker_token",
              "reason": "forbidden_key"
            }
          ]
        }
      }
    }
  },
  "when": {
    "operation": "validate_invalid_options_flow_inputs"
  }
}
PASS invalid_options_flow_input_fails_closed
CASE setup_flow_remains_non_orchestrating
{
  "case_id": "setup_flow_remains_non_orchestrating",
  "given": {
    "handled_surfaces": [
      "config_flow_user",
      "options_flow_init"
    ]
  },
  "then": {
    "non_orchestration": {
      "aggregate": {
        "dashboard_resource_registered": false,
        "home_assistant_history_called": false,
        "home_assistant_mutation_called": false,
        "model_provider_called": false,
        "semantic_memory_called": false,
        "token_generated": false,
        "worker_called": false
      },
      "expected": {
        "dashboard_resource_registered": false,
        "home_assistant_history_called": false,
        "home_assistant_mutation_called": false,
        "model_provider_called": false,
        "semantic_memory_called": false,
        "token_generated": false,
        "worker_called": false
      },
      "observed": [
        {
          "dashboard_resource_registered": false,
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "name": "config_flow_user",
          "semantic_memory_called": false,
          "token_generated": false,
          "worker_called": false
        },
        {
          "dashboard_resource_registered": false,
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "name": "options_flow_init",
          "semantic_memory_called": false,
          "token_generated": false,
          "worker_called": false
        },
        {
          "dashboard_resource_registered": false,
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "name": "invalid_config_flow_input",
          "semantic_memory_called": false,
          "token_generated": false,
          "worker_called": false
        },
        {
          "dashboard_resource_registered": false,
          "home_assistant_history_called": false,
          "home_assistant_mutation_called": false,
          "model_provider_called": false,
          "name": "invalid_options_flow_input",
          "semantic_memory_called": false,
          "token_generated": false,
          "worker_called": false
        }
      ]
    }
  },
  "when": {
    "operation": "aggregate_observed_side_effects"
  }
}
PASS setup_flow_remains_non_orchestrating
PASS home_assistant_config_flow_options
```
