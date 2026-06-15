# Home Assistant WebSocket Command Registration Evidence

Run timestamp: 2026-06-15T17:55:28+00:00

BDD file:
`bdd/integration/home-assistant-websocket-command-registration-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: command names are registered with Home Assistant -> `CASE command_names_registered_with_home_assistant`
- Scenario B: config entry setup stores registration metadata -> `CASE config_entry_setup_stores_registration_metadata`
- Scenario C: registered callbacks return scaffold snapshots -> `CASE registered_callbacks_return_scaffold_snapshots`
- Scenario D: malformed or unsafe commands fail closed -> `CASE malformed_or_unsafe_commands_fail_closed`
- Scenario E: missing config-entry scope fails closed -> `CASE missing_config_entry_scope_fails_closed`
- Scenario F: auto config-entry resolution is deterministic -> `CASE auto_config_entry_resolves_only_when_unambiguous`
- Scenario G: registered command decisions are visible -> `CASE registered_websocket_decisions_are_observable`
- Scenario H: repeated setup does not duplicate commands -> `CASE repeated_setup_does_not_duplicate_commands`
- Scenario I: registration remains non-orchestrating -> `CASE websocket_registration_remains_non_orchestrating`

## Focused Unit Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_websocket_command_registration_anchor.py
```

Raw output:

```text
collected 13 items
tests\test_websocket_command_registration_anchor.py .............        [100%]
13 passed in 0.54s
```

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_websocket_command_registration.py
```

Raw observed output excerpts:

```text
CASE command_names_registered_with_home_assistant
"registered_count": 5
"registered_types": [
  "isolinear/v1/job/start",
  "isolinear/v1/clarification/answer",
  "isolinear/v1/job/retry",
  "isolinear/v1/job/snapshot",
  "isolinear/v1/job/subscribe"
]
"handlers_have_command_schema": true
PASS command_names_registered_with_home_assistant

CASE config_entry_setup_stores_registration_metadata
"entry_id": "fake-config-entry"
"config_entry_scoped_result": true
"registered_count": 5
PASS config_entry_setup_stores_registration_metadata

CASE registered_callbacks_return_scaffold_snapshots
"accepted": true
"snapshot": {"status": "planning", "warnings": ["job_state_scaffold", "orchestration_not_implemented"]}
"websocket_observability": {
  "accepted": true,
  "code": "registered_job_state_command_accepted",
  "command_type": "isolinear/v1/job/start",
  "requested_config_entry_id": "auto",
  "resolved_config_entry_id": "fake-config-entry"
}
PASS registered_callbacks_return_scaffold_snapshots

CASE malformed_or_unsafe_commands_fail_closed
"unknown_command": {"accepted": false, "code": "unknown_integration_ws_command"}
"wrong_version": {"accepted": false, "code": "unsupported_integration_ws_version"}
"leaky_worker_url": {"accepted": false, "code": "forbidden_card_boundary_content"}
"mutating_service_call": {"accepted": false, "code": "forbidden_card_boundary_content"}
PASS malformed_or_unsafe_commands_fail_closed

CASE missing_config_entry_scope_fails_closed
"known_config_entries": []
"dispatch_result": {"accepted": false, "code": "unknown_config_entry"}
PASS missing_config_entry_scope_fails_closed

CASE auto_config_entry_resolves_only_when_unambiguous
"single_entry": {"known_config_entries": ["fake-config-entry"], "result": {"accepted": true, "config_entry_id": "fake-config-entry"}}
"multiple_entries": {"known_config_entries": ["fake-config-entry", "second-config-entry"], "result": {"accepted": false, "code": "ambiguous_config_entry"}}
"registry_single_entry": {"known_config_entries": ["registry-entry-001"], "result": {"accepted": true, "config_entry_id": "registry-entry-001"}}
"registry_multiple_entries": {"known_config_entries": ["registry-entry-001", "registry-entry-002"], "result": {"accepted": false, "code": "ambiguous_config_entry"}}
PASS auto_config_entry_resolves_only_when_unambiguous

CASE registered_websocket_decisions_are_observable
"event_count": 2
"events": [
  {
    "accepted": true,
    "code": "registered_job_state_command_accepted",
    "command_type": "isolinear/v1/job/start",
    "requested_config_entry_id": "auto",
    "resolved_config_entry_id": "fake-config-entry"
  },
  {
    "accepted": false,
    "code": "unknown_config_entry",
    "command_type": "isolinear/v1/job/snapshot",
    "requested_config_entry_id": "missing-config-entry",
    "resolved_config_entry_id": null
  }
]
PASS registered_websocket_decisions_are_observable

CASE repeated_setup_does_not_duplicate_commands
"first_count": 5
"second_count": 5
"duplicate_count": 0
PASS repeated_setup_does_not_duplicate_commands

CASE websocket_registration_remains_non_orchestrating
"forbidden_aggregate": {
  "worker_called": false,
  "model_provider_called": false,
  "home_assistant_history_called": false,
  "semantic_memory_called": false,
  "home_assistant_service_or_state_mutation_called": false,
  "token_generated": false,
  "job_orchestration_called": false,
  "dashboard_resource_metadata_written_or_reused": false
}
"allowed_aggregate": {"websocket_command_registered": true}
"allowed_side_effects": {"websocket_command_registered": true, "websocket_decision_observability_recorded": true}
PASS websocket_registration_remains_non_orchestrating

PASS home_assistant_websocket_command_registration
```
