# Home Assistant Dashboard Resource Registration Evidence

Run timestamp: 2026-06-16T16:40:12+00:00

BDD file:
`bdd/integration/home-assistant-dashboard-resource-registration-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: card bundle is served from an integration static path -> `CASE card_bundle_served_from_integration_static_path`
- Scenario B: config entry setup registers resource metadata -> `CASE config_entry_setup_registers_resource_metadata`
- Scenario C: repeated setup does not duplicate metadata -> `CASE repeated_setup_does_not_duplicate_metadata`
- Scenario D: pre-existing matching metadata is reused -> `CASE preexisting_matching_metadata_is_reused`
- Scenario E: stale Isolinear metadata is updated in place -> `CASE stale_isolinear_resource_is_updated`
- Scenario F: missing bundle fails closed -> `CASE missing_bundle_fails_closed`
- Scenario G: registration remains non-orchestrating -> `CASE dashboard_resource_registration_remains_non_orchestrating`

Additional failure-path coverage:

- Lovelace resource collection unavailable -> `CASE unavailable_resource_collection_fails_closed`

## Focused Unit Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dashboard_resource_registration_anchor.py tests/test_hacs_install_packaging.py
```

Raw output:

```text
collected 14 items
tests\test_dashboard_resource_registration_anchor.py ........            [ 57%]
tests\test_hacs_install_packaging.py ......                              [100%]
14 passed in 0.41s
```

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_dashboard_resource_registration.py
```

Raw observed output excerpts:

```text
CASE card_bundle_served_from_integration_static_path
"bundle_path": "...\\custom_components\\isolinear\\frontend\\dist\\isolinear-card.js"
"static_path_url": "/api/isolinear/static"
"resource_url": "/api/isolinear/static/isolinear-card.js?v=0.1.7"
PASS card_bundle_served_from_integration_static_path

CASE config_entry_setup_registers_resource_metadata
"setup_accepted": true
"resources": [{"id": "resource-001", "type": "module", "url": "/api/isolinear/static/isolinear-card.js?v=0.1.7"}]
PASS config_entry_setup_registers_resource_metadata

CASE repeated_setup_does_not_duplicate_metadata
"resource_count": 1
"create_call_count": 1
"second": {"code": "dashboard_resource_already_registered", "resource_reused": true}
PASS repeated_setup_does_not_duplicate_metadata

CASE preexisting_matching_metadata_is_reused
"preexisting_reused": true
"create_call_count": 0
"update_call_count": 0
PASS preexisting_matching_metadata_is_reused

CASE stale_isolinear_resource_is_updated
"legacy_resource_url": "/api/isolinear/static/isolinear-card.js"
"resource_url": "/api/isolinear/static/isolinear-card.js?v=0.1.7"
"code": "dashboard_resource_updated"
"resource_updated": true
"resource_created": false
"create_call_count": 0
"update_call_count": 1
"resources": [{"id": "resource-stale", "type": "module", "url": "/api/isolinear/static/isolinear-card.js?v=0.1.7"}]
PASS stale_isolinear_resource_is_updated

CASE missing_bundle_fails_closed
"accepted": false
"code": "dashboard_card_bundle_missing"
"create_call_count": 0
"static_path_call_count": 0
PASS missing_bundle_fails_closed

CASE unavailable_resource_collection_fails_closed
"accepted": false
"code": "lovelace_resource_collection_unavailable"
"create_call_count": 0
"resource_count": 0
PASS unavailable_resource_collection_fails_closed

CASE dashboard_resource_registration_remains_non_orchestrating
"aggregate": {
  "worker_called": false,
  "model_provider_called": false,
  "home_assistant_history_called": false,
  "semantic_memory_called": false,
  "home_assistant_service_or_state_mutation_called": false,
  "token_generated": false,
  "job_orchestration_called": false,
  "websocket_command_registered": false
}
"allowed_side_effects": {"static_path_registered": true, "dashboard_resource_metadata_created_reused_or_updated": true}
PASS dashboard_resource_registration_remains_non_orchestrating

PASS home_assistant_dashboard_resource_registration
```
