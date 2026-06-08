# Home Assistant WebSocket Command Registration Evidence

Run timestamp: 2026-06-08T04:28:54+00:00

BDD file:
`bdd/integration/home-assistant-websocket-command-registration-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: command names are registered with Home Assistant -> `CASE command_names_registered_with_home_assistant`
- Scenario B: config entry setup stores registration metadata -> `CASE config_entry_setup_stores_registration_metadata`
- Scenario C: registered callbacks return scaffold snapshots -> `CASE registered_callbacks_return_scaffold_snapshots`
- Scenario D: malformed or unsafe commands fail closed -> `CASE malformed_or_unsafe_commands_fail_closed`
- Scenario E: missing config-entry scope fails closed -> `CASE missing_config_entry_scope_fails_closed`
- Scenario F: repeated setup does not duplicate commands -> `CASE repeated_setup_does_not_duplicate_commands`
- Scenario G: registration remains non-orchestrating -> `CASE websocket_registration_remains_non_orchestrating`

Additional failure-path coverage:

- Unknown command not registered with Home Assistant -> `unknown_command`
  dispatch result has no handler call and sends `unknown_integration_ws_command`.
- Wrong-version command reaches the registered type boundary and sends
  `unsupported_integration_ws_version`.
- Leaky worker URL and mutating service payloads send
  `forbidden_card_boundary_content`.

## Focused Unit Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_websocket_command_registration_anchor.py
```

Raw output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 7 items

tests\test_websocket_command_registration_anchor.py .......              [100%]

============================== 7 passed in 0.20s ==============================
```

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_websocket_command_registration.py
```

Raw output summary:

```text
CASE command_names_registered_with_home_assistant
PASS command_names_registered_with_home_assistant
CASE config_entry_setup_stores_registration_metadata
PASS config_entry_setup_stores_registration_metadata
CASE registered_callbacks_return_scaffold_snapshots
PASS registered_callbacks_return_scaffold_snapshots
CASE malformed_or_unsafe_commands_fail_closed
PASS malformed_or_unsafe_commands_fail_closed
CASE missing_config_entry_scope_fails_closed
PASS missing_config_entry_scope_fails_closed
CASE repeated_setup_does_not_duplicate_commands
PASS repeated_setup_does_not_duplicate_commands
CASE websocket_registration_remains_non_orchestrating
PASS websocket_registration_remains_non_orchestrating
PASS home_assistant_websocket_command_registration
```

Key observed facts from the raw CASE payload:

- Registered command names exactly matched:
  `isolinear/v1/job/start`,
  `isolinear/v1/clarification/answer`,
  `isolinear/v1/job/retry`,
  `isolinear/v1/job/snapshot`,
  `isolinear/v1/job/subscribe`.
- Handler count was `5`, and every handler carried a command schema.
- `async_setup_entry` stored `websocket_api` under config entry
  `fake-config-entry`.
- Accepted registered callbacks sent one schema-valid
  `IntegrationJobSnapshot` with status `planning` and warning
  `orchestration_not_implemented`.
- Missing config-entry scope sent `unknown_config_entry` and returned no
  snapshot.
- Repeated setup kept the registered handler count at `5`; duplicate count was
  `0`.
- Forbidden side-effect aggregate remained false for worker, model-provider,
  Home Assistant history, semantic-memory, service/state mutation,
  token-generation, job-orchestration, and dashboard-resource metadata writes.
- Allowed side-effect aggregate reported `websocket_command_registered: true`.

## Scenario Evidence Excerpts

These excerpts are copied from the `CASE` payloads emitted by the eval run.

### Scenario A

```text
case_id: command_names_registered_with_home_assistant
then.registration.registered_via_async_register_command: true
then.registration.handlers_have_command_schema: true
then.registration.registered_count: 5
then.registration.registered_types:
- isolinear/v1/job/start
- isolinear/v1/clarification/answer
- isolinear/v1/job/retry
- isolinear/v1/job/snapshot
- isolinear/v1/job/subscribe
then.registration.handler_schemas:
- type: isolinear/v1/job/start
- type: isolinear/v1/clarification/answer
- type: isolinear/v1/job/retry
- type: isolinear/v1/job/snapshot
- type: isolinear/v1/job/subscribe
```

### Scenario B

```text
case_id: config_entry_setup_stores_registration_metadata
then.setup_entry.setup_accepted: true
then.setup_entry.entry_id: fake-config-entry
then.setup_entry.entry_data_keys:
- dashboard_resource
- entry
- websocket_api
then.setup_entry.registration.config_entry_scoped: true
then.setup_entry.registered_count: 5
```

### Scenario C

```text
case_id: registered_callbacks_return_scaffold_snapshots
then.callbacks.snapshot_validation.start_job:
  accepted: true
  status: planning
then.callbacks.snapshot_validation.answer_clarification:
  accepted: true
  status: planning
then.callbacks.snapshot_validation.retry_job:
  accepted: true
  status: planning
then.callbacks.snapshot_validation.get_snapshot:
  accepted: true
  status: planning
then.callbacks.snapshot_validation.subscribe_job:
  accepted: true
  status: planning
then.callbacks.dispatch_results.*.connection.errors: []
then.callbacks.dispatch_results.*.connection.results[0].result.warnings:
- orchestration_not_implemented
```

### Scenario D

```text
case_id: malformed_or_unsafe_commands_fail_closed
then.invalid.dispatch_results.unknown_command.connection.errors[0].code:
  unknown_integration_ws_command
then.invalid.dispatch_results.wrong_version.connection.errors[0].code:
  unsupported_integration_ws_version
then.invalid.dispatch_results.leaky_worker_url.connection.errors[0].code:
  forbidden_card_boundary_content
then.invalid.dispatch_results.mutating_service_call.connection.errors[0].code:
  forbidden_card_boundary_content
then.invalid.dispatch_results.*.connection.results: []
```

### Scenario E

```text
case_id: missing_config_entry_scope_fails_closed
given.known_config_entries: []
then.missing_scope.dispatch_result.accepted: false
then.missing_scope.dispatch_result.connection.errors[0].code:
  unknown_config_entry
then.missing_scope.dispatch_result.connection.results: []
```

### Scenario F

```text
case_id: repeated_setup_does_not_duplicate_commands
then.idempotence.first_setup: true
then.idempotence.second_setup: true
then.idempotence.first_count: 5
then.idempotence.second_count: 5
then.idempotence.duplicate_count: 0
then.idempotence.second_registration.code:
  websocket_commands_already_registered
```

### Scenario G

```text
case_id: websocket_registration_remains_non_orchestrating
then.side_effects.forbidden_aggregate.worker_called: false
then.side_effects.forbidden_aggregate.model_provider_called: false
then.side_effects.forbidden_aggregate.home_assistant_history_called: false
then.side_effects.forbidden_aggregate.semantic_memory_called: false
then.side_effects.forbidden_aggregate.home_assistant_service_or_state_mutation_called: false
then.side_effects.forbidden_aggregate.token_generated: false
then.side_effects.forbidden_aggregate.job_orchestration_called: false
then.side_effects.forbidden_aggregate.dashboard_resource_metadata_written_or_reused: false
then.side_effects.allowed_aggregate.websocket_command_registered: true
```
