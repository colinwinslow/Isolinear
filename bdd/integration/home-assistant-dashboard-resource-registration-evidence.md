# Home Assistant Dashboard Resource Registration Evidence

Run timestamp: 2026-06-08T00:49:51+00:00

BDD file:
`bdd/integration/home-assistant-dashboard-resource-registration-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: card bundle is served from an integration static path -> `CASE card_bundle_served_from_integration_static_path`
- Scenario B: config entry setup registers resource metadata -> `CASE config_entry_setup_registers_resource_metadata`
- Scenario C: repeated setup does not duplicate metadata -> `CASE repeated_setup_does_not_duplicate_metadata`
- Scenario D: pre-existing matching metadata is reused -> `CASE preexisting_matching_metadata_is_reused`
- Scenario E: missing bundle fails closed -> `CASE missing_bundle_fails_closed`
- Scenario F: registration remains non-orchestrating -> `CASE dashboard_resource_registration_remains_non_orchestrating`

Additional failure-path coverage:

- Lovelace resource collection unavailable -> `CASE unavailable_resource_collection_fails_closed`

## Focused Unit Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dashboard_resource_registration_anchor.py
```

Raw output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 7 items

tests\test_dashboard_resource_registration_anchor.py .......             [100%]

============================== 7 passed in 0.13s ==============================
```

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_dashboard_resource_registration.py
```

Raw output:

```text
CASE card_bundle_served_from_integration_static_path
{
  "case_id": "card_bundle_served_from_integration_static_path",
  "given": {
    "card_bundle": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\frontend\\dist\\isolinear-card.js",
    "run_timestamp": "2026-06-08T00:49:51+00:00"
  },
  "then": {
    "files": {
      "all_files_present": true,
      "bundle_path": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\frontend\\dist\\isolinear-card.js",
      "files": {
        "custom_components/isolinear/__init__.py": true,
        "custom_components/isolinear/dashboard_resource.py": true,
        "frontend/dist/isolinear-card.js": true
      },
      "resource_url": "/api/isolinear/static/isolinear-card.js",
      "static_path_url": "/api/isolinear/static"
    },
    "static_path": {
      "accepted": true,
      "bundle_exists": true,
      "code": "dashboard_resource_registered",
      "resource": {
        "type": "module",
        "url": "/api/isolinear/static/isolinear-card.js"
      },
      "resource_result": {
        "id": "resource-001",
        "type": "module",
        "url": "/api/isolinear/static/isolinear-card.js"
      },
      "result": {
        "accepted": true,
        "bundle_path": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\frontend\\dist\\isolinear-card.js",
        "code": "dashboard_resource_registered",
        "config_entry_scoped": true,
        "entry_id": "resource-entry-001",
        "orchestration": {
          "home_assistant_history_called": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        },
        "resource": {
          "id": "resource-001",
          "type": "module",
          "url": "/api/isolinear/static/isolinear-card.js"
        },
        "resource_created": true,
        "resource_reused": false,
        "static_path": {
          "cache_headers": true,
          "call_made": true,
          "code": "static_path_registered",
          "path": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\frontend\\dist",
          "url_path": "/api/isolinear/static"
        }
      },
      "static_path": {
        "cache_headers": true,
        "call_made": true,
        "code": "static_path_registered",
        "path": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\frontend\\dist",
        "url_path": "/api/isolinear/static"
      },
      "static_path_call_count": 1
    }
  },
  "when": {
    "operation": "async_register_card_static_path"
  }
}
PASS card_bundle_served_from_integration_static_path
CASE config_entry_setup_registers_resource_metadata
{
  "case_id": "config_entry_setup_registers_resource_metadata",
  "given": {
    "entry_id": "resource-entry-001",
    "resource_url": "/api/isolinear/static/isolinear-card.js"
  },
  "then": {
    "setup_entry": {
      "bundle_exists": true,
      "entry_id": "resource-entry-001",
      "entry_result": {
        "accepted": true,
        "bundle_path": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\frontend\\dist\\isolinear-card.js",
        "code": "dashboard_resource_registered",
        "config_entry_scoped": true,
        "entry_id": "resource-entry-001",
        "orchestration": {
          "home_assistant_history_called": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        },
        "resource": {
          "id": "resource-001",
          "type": "module",
          "url": "/api/isolinear/static/isolinear-card.js"
        },
        "resource_created": true,
        "resource_reused": false,
        "static_path": {
          "cache_headers": true,
          "call_made": true,
          "code": "static_path_registered",
          "path": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\frontend\\dist",
          "url_path": "/api/isolinear/static"
        }
      },
      "resources": [
        {
          "id": "resource-001",
          "type": "module",
          "url": "/api/isolinear/static/isolinear-card.js"
        }
      ],
      "setup_accepted": true,
      "static_path_call_count": 1
    }
  },
  "when": {
    "operation": "async_setup_entry"
  }
}
PASS config_entry_setup_registers_resource_metadata
CASE repeated_setup_does_not_duplicate_metadata
{
  "case_id": "repeated_setup_does_not_duplicate_metadata",
  "given": {
    "resource_url": "/api/isolinear/static/isolinear-card.js"
  },
  "then": {
    "idempotence": {
      "create_call_count": 1,
      "first": {
        "accepted": true,
        "bundle_path": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\frontend\\dist\\isolinear-card.js",
        "code": "dashboard_resource_registered",
        "config_entry_scoped": true,
        "entry_id": "resource-entry-001",
        "orchestration": {
          "home_assistant_history_called": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        },
        "resource": {
          "id": "resource-001",
          "type": "module",
          "url": "/api/isolinear/static/isolinear-card.js"
        },
        "resource_created": true,
        "resource_reused": false,
        "static_path": {
          "cache_headers": true,
          "call_made": true,
          "code": "static_path_registered",
          "path": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\frontend\\dist",
          "url_path": "/api/isolinear/static"
        }
      },
      "resource_count": 1,
      "resources": [
        {
          "id": "resource-001",
          "type": "module",
          "url": "/api/isolinear/static/isolinear-card.js"
        }
      ],
      "second": {
        "accepted": true,
        "bundle_path": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\frontend\\dist\\isolinear-card.js",
        "code": "dashboard_resource_already_registered",
        "config_entry_scoped": true,
        "entry_id": "resource-entry-001",
        "orchestration": {
          "home_assistant_history_called": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        },
        "resource": {
          "id": "resource-001",
          "type": "module",
          "url": "/api/isolinear/static/isolinear-card.js"
        },
        "resource_created": false,
        "resource_reused": true,
        "static_path": {
          "cache_headers": true,
          "call_made": false,
          "code": "static_path_already_registered",
          "path": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\frontend\\dist",
          "url_path": "/api/isolinear/static"
        }
      },
      "static_path_call_count": 1
    }
  },
  "when": {
    "operation": "async_register_dashboard_resource_twice"
  }
}
PASS repeated_setup_does_not_duplicate_metadata
CASE preexisting_matching_metadata_is_reused
{
  "case_id": "preexisting_matching_metadata_is_reused",
  "given": {
    "resource_type": "module",
    "resource_url": "/api/isolinear/static/isolinear-card.js"
  },
  "then": {
    "preexisting": {
      "accepted": true,
      "create_call_count": 0,
      "preexisting_reused": true,
      "resource_count": 1,
      "resources": [
        {
          "id": "resource-existing",
          "type": "module",
          "url": "/api/isolinear/static/isolinear-card.js"
        }
      ],
      "result": {
        "accepted": true,
        "bundle_path": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\frontend\\dist\\isolinear-card.js",
        "code": "dashboard_resource_already_registered",
        "config_entry_scoped": true,
        "entry_id": "resource-entry-001",
        "orchestration": {
          "home_assistant_history_called": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        },
        "resource": {
          "id": "resource-existing",
          "type": "module",
          "url": "/api/isolinear/static/isolinear-card.js"
        },
        "resource_created": false,
        "resource_reused": true,
        "static_path": {
          "cache_headers": true,
          "call_made": true,
          "code": "static_path_registered",
          "path": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\frontend\\dist",
          "url_path": "/api/isolinear/static"
        }
      },
      "static_path_call_count": 1
    }
  },
  "when": {
    "operation": "async_register_dashboard_resource_with_existing_item"
  }
}
PASS preexisting_matching_metadata_is_reused
CASE missing_bundle_fails_closed
{
  "case_id": "missing_bundle_fails_closed",
  "given": {
    "bundle_path": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\.missing-isolinear-card-bundle\\isolinear-card.js"
  },
  "then": {
    "missing_bundle": {
      "accepted": false,
      "code": "dashboard_card_bundle_missing",
      "create_call_count": 0,
      "resources": [],
      "result": {
        "accepted": false,
        "bundle_path": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\.missing-isolinear-card-bundle\\isolinear-card.js",
        "code": "dashboard_card_bundle_missing",
        "config_entry_scoped": true,
        "entry_id": "resource-entry-001",
        "orchestration": {
          "home_assistant_history_called": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        },
        "resource": {
          "type": "module",
          "url": "/api/isolinear/static/isolinear-card.js"
        },
        "resource_created": false,
        "resource_reused": false
      },
      "static_path_call_count": 0
    }
  },
  "when": {
    "operation": "async_register_dashboard_resource"
  }
}
PASS missing_bundle_fails_closed
CASE unavailable_resource_collection_fails_closed
{
  "case_id": "unavailable_resource_collection_fails_closed",
  "given": {
    "lovelace_resource_collection": null
  },
  "then": {
    "unavailable_collection": {
      "accepted": false,
      "code": "lovelace_resource_collection_unavailable",
      "create_call_count": 0,
      "resource_count": 0,
      "result": {
        "accepted": false,
        "bundle_path": "C:\\Users\\c.winslow\\OneDrive - Kagwerks\\Documents\\Repos\\Isolinear\\frontend\\dist\\isolinear-card.js",
        "code": "lovelace_resource_collection_unavailable",
        "config_entry_scoped": true,
        "entry_id": "resource-entry-001",
        "orchestration": {
          "home_assistant_history_called": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "model_provider_called": false,
          "semantic_memory_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        },
        "resource": {
          "type": "module",
          "url": "/api/isolinear/static/isolinear-card.js"
        },
        "resource_created": false,
        "resource_reused": false
      },
      "static_path_call_count": 0
    }
  },
  "when": {
    "operation": "async_register_dashboard_resource"
  }
}
PASS unavailable_resource_collection_fails_closed
CASE dashboard_resource_registration_remains_non_orchestrating
{
  "case_id": "dashboard_resource_registration_remains_non_orchestrating",
  "given": {
    "handled_surfaces": [
      "static_path_registration",
      "setup_entry_registration",
      "idempotent_registration",
      "preexisting_resource_reuse",
      "missing_bundle_rejection"
    ]
  },
  "then": {
    "side_effects": {
      "aggregate": {
        "home_assistant_history_called": false,
        "home_assistant_service_or_state_mutation_called": false,
        "job_orchestration_called": false,
        "model_provider_called": false,
        "semantic_memory_called": false,
        "token_generated": false,
        "websocket_command_registered": false,
        "worker_called": false
      },
      "allowed_side_effects": {
        "dashboard_resource_metadata_written_or_reused": true,
        "static_path_registered": true
      },
      "expected": {
        "home_assistant_history_called": false,
        "home_assistant_service_or_state_mutation_called": false,
        "job_orchestration_called": false,
        "model_provider_called": false,
        "semantic_memory_called": false,
        "token_generated": false,
        "websocket_command_registered": false,
        "worker_called": false
      },
      "observed": [
        {
          "home_assistant_history_called": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "model_provider_called": false,
          "name": "static_path_registration",
          "semantic_memory_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        },
        {
          "home_assistant_history_called": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "model_provider_called": false,
          "name": "setup_entry_registration",
          "semantic_memory_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        },
        {
          "home_assistant_history_called": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "model_provider_called": false,
          "name": "idempotent_registration_first",
          "semantic_memory_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        },
        {
          "home_assistant_history_called": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "model_provider_called": false,
          "name": "idempotent_registration_second",
          "semantic_memory_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        },
        {
          "home_assistant_history_called": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "model_provider_called": false,
          "name": "missing_bundle_rejection",
          "semantic_memory_called": false,
          "token_generated": false,
          "websocket_command_registered": false,
          "worker_called": false
        }
      ]
    }
  },
  "when": {
    "operation": "aggregate_observed_side_effects"
  }
}
PASS dashboard_resource_registration_remains_non_orchestrating
PASS home_assistant_dashboard_resource_registration
```
