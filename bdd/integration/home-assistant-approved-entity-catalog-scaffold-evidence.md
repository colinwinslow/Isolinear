# Home Assistant Approved Entity Catalog Scaffold Evidence

Run timestamps:

- Baseline eval transcript: 2026-06-08T13:56:06+00:00
- Options-update runtime catalog regression refresh: 2026-06-16T16:36:43+00:00
- Home Assistant read-only mapping options regression refresh: 2026-06-16T18:25:29+00:00

BDD file:
`bdd/integration/home-assistant-approved-entity-catalog-scaffold-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: allowlisted metadata becomes schema-valid catalog items -> `CASE allowlisted_metadata_builds_schema_valid_catalog`
- Scenario B: setup stores a config-entry-scoped catalog -> `CASE setup_entry_stores_config_entry_scoped_catalog`
- Scenario C2: options update rebuilds runtime catalog -> `CASE options_update_rebuilds_runtime_catalog`
- Scenario C3: read-only options mappings build runtime catalog -> `CASE read_only_options_mapping_builds_runtime_catalog`
- Scenario C: config entries receive separate catalogs -> `CASE config_entries_receive_isolated_catalogs`
- Scenario D: unknown allowlisted entities fail closed -> `CASE unknown_allowlisted_entities_fail_closed`
- Scenario E: rejected rebuild clears existing catalog -> `CASE rejected_rebuild_clears_existing_catalog`
- Scenario F: malformed allowlists fail closed -> `CASE malformed_allowlists_fail_closed_without_crashing`
- Scenario G: malformed catalog items are rejected before storage -> `CASE malformed_catalog_items_are_rejected_before_storage`
- Scenario H: catalog construction remains non-orchestrating -> `CASE entity_catalog_remains_non_orchestrating`

## Focused Unit Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_approved_entity_catalog_scaffold_anchor.py
```

Raw output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 11 items

tests\test_approved_entity_catalog_scaffold_anchor.py ...........        [100%]

============================= 11 passed in 0.52s ==============================
```

## Full Unit Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\
```

Raw output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 339 items

tests\test_approved_entity_catalog_scaffold_anchor.py ...........        [  3%]
...
tests\test_worker_transport_failure_classification_anchor.py ..........  [100%]

======================= 339 passed in 92.10s (0:01:32) ========================
```

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_approved_entity_catalog_scaffold.py
```

Raw output summary:

```text
CASE allowlisted_metadata_builds_schema_valid_catalog
PASS allowlisted_metadata_builds_schema_valid_catalog
CASE setup_entry_stores_config_entry_scoped_catalog
PASS setup_entry_stores_config_entry_scoped_catalog
CASE options_update_rebuilds_runtime_catalog
PASS options_update_rebuilds_runtime_catalog
CASE read_only_options_mapping_builds_runtime_catalog
PASS read_only_options_mapping_builds_runtime_catalog
CASE config_entries_receive_isolated_catalogs
PASS config_entries_receive_isolated_catalogs
CASE unknown_allowlisted_entities_fail_closed
PASS unknown_allowlisted_entities_fail_closed
CASE rejected_rebuild_clears_existing_catalog
PASS rejected_rebuild_clears_existing_catalog
CASE malformed_allowlists_fail_closed_without_crashing
PASS malformed_allowlists_fail_closed_without_crashing
CASE malformed_catalog_items_are_rejected_before_storage
PASS malformed_catalog_items_are_rejected_before_storage
CASE entity_catalog_remains_non_orchestrating
PASS entity_catalog_remains_non_orchestrating
PASS home_assistant_approved_entity_catalog_scaffold
```

## Scenario Evidence Excerpts

These excerpts are copied from the `CASE` payloads emitted by the eval run.

### Scenario A

```text
case_id: allowlisted_metadata_builds_schema_valid_catalog
given.schema: docs/schemas/entity-catalog-item.schema.json
given.metadata_entity_ids:
- binary_sensor.office_window
- light.kitchen
- sensor.downstairs_temperature
- sensor.upstairs_temperature
when.operation: setup_entity_catalog
then.catalog.catalog_entity_ids:
- sensor.upstairs_temperature
- sensor.downstairs_temperature
then.catalog.item_validation[0].accepted: true
then.catalog.item_validation[0].entity_id: sensor.upstairs_temperature
then.catalog.item_validation[0].visible_to_agent: true
then.catalog.item_validation[1].accepted: true
then.catalog.item_validation[1].entity_id: sensor.downstairs_temperature
then.catalog.item_validation[1].visible_to_agent: true
then.catalog.result.validation.accepted: true
then.catalog.store.entity_ids:
- sensor.upstairs_temperature
- sensor.downstairs_temperature
then.catalog.store.all_visible_to_agent: true
```

### Scenario B

```text
case_id: setup_entry_stores_config_entry_scoped_catalog
given.entry_id: setup-catalog-entry
when.operation: async_setup_entry
then.setup.setup_accepted: true
then.setup.entry_data_keys:
- dashboard_resource
- entity_catalog
- entity_catalog_setup
- entry
- history_retrieval
- history_retrieval_setup
- job_orchestration
- job_orchestration_setup
- job_state
- options_update_listener_registered
- websocket_api
then.setup.setup_result.accepted: true
then.setup.setup_result.entry_id: setup-catalog-entry
then.setup.store.entry_id: setup-catalog-entry
then.setup.store.entity_ids:
- sensor.upstairs_temperature
- binary_sensor.office_window
then.setup.item_validation[0].accepted: true
then.setup.item_validation[1].accepted: true
```

### Scenario C2

```text
case_id: options_update_rebuilds_runtime_catalog
given.entry_id: options-update-catalog-entry
given.initial_allowlist: []
given.updated_allowlist:
- sensor.upstairs_temperature
- sensor.downstairs_temperature
when.operation: invoke_registered_options_update_listener
then.options_update.listener_registered: true
then.options_update.updated_options_type: mappingproxy
then.options_update.store_before_update.entity_ids: []
then.options_update.store_after_update.entity_ids:
- sensor.upstairs_temperature
- sensor.downstairs_temperature
then.options_update.catalog_setup.accepted: true
then.options_update.history_setup.approved_entity_ids:
- sensor.upstairs_temperature
- sensor.downstairs_temperature
then.options_update.job_orchestration_setup.approved_entity_ids:
- sensor.upstairs_temperature
- sensor.downstairs_temperature
then.options_update.job_orchestration_setup.enabled: true
then.options_update.item_validation[0].accepted: true
then.options_update.item_validation[1].accepted: true
```

### Scenario C3

```text
case_id: read_only_options_mapping_builds_runtime_catalog
given.entry_id: mapping-options-catalog-entry
given.options_type: mappingproxy
given.configured_entity_ids:
- sensor.upstairs_temperature
- sensor.downstairs_temperature
when.operation: setup_entity_catalog
then.mapping_options.result.accepted: true
then.mapping_options.result.entity_allowlist:
- sensor.upstairs_temperature
- sensor.downstairs_temperature
then.mapping_options.store.entity_ids:
- sensor.upstairs_temperature
- sensor.downstairs_temperature
then.mapping_options.item_validation[0].accepted: true
then.mapping_options.item_validation[1].accepted: true
```

### Scenario C

```text
case_id: config_entries_receive_isolated_catalogs
given.entry_ids:
- entry-a
- entry-b
when.operation: setup_entity_catalog_for_each_entry
then.isolation.entry_a.accepted: true
then.isolation.entry_a_store.entity_ids:
- sensor.upstairs_temperature
then.isolation.entry_b.accepted: true
then.isolation.entry_b_store.entity_ids:
- binary_sensor.office_window
then.isolation.entry_a_validation[0].accepted: true
then.isolation.entry_b_validation[0].accepted: true
```

### Scenario D

```text
case_id: unknown_allowlisted_entities_fail_closed
given.entity_id: sensor.missing_temperature
when.operation: setup_entity_catalog
then.unknown.result.accepted: false
then.unknown.result.code: unknown_allowlisted_entity
then.unknown.result.missing_entity_ids:
- sensor.missing_temperature
then.unknown.store.entry_id: missing-entity-entry
then.unknown.store.item_count: 0
then.unknown.store.entity_ids: []
```

### Scenario E

```text
case_id: rejected_rebuild_clears_existing_catalog
given.initial_allowlist:
- sensor.upstairs_temperature
given.replacement_allowlist:
- sensor.missing_temperature
when.operation: setup_entity_catalog_after_allowlist_change
then.stale.accepted.accepted: true
then.stale.store_after_success.entity_ids:
- sensor.upstairs_temperature
then.stale.rejected.accepted: false
then.stale.rejected.code: unknown_allowlisted_entity
then.stale.rejected.missing_entity_ids:
- sensor.missing_temperature
then.stale.store_after_rejection.item_count: 0
then.stale.store_after_rejection.entity_ids: []
```

### Scenario F

```text
case_id: malformed_allowlists_fail_closed_without_crashing
given.entity_allowlist:
- entity_id: sensor.upstairs_temperature
when.operation: setup_entity_catalog
then.malformed_allowlist.result.accepted: false
then.malformed_allowlist.result.code: invalid_entity_allowlist
then.malformed_allowlist.result.errors:
- path: $.options.entity_allowlist[0]
  reason: invalid_entity_id
then.malformed_allowlist.store.item_count: 0
then.malformed_allowlist.store.entity_ids: []
```

### Scenario G

```text
case_id: malformed_catalog_items_are_rejected_before_storage
given.schema: docs/schemas/entity-catalog-item.schema.json
given.malformed_item.entity_id: sensor.bad_catalog_item
given.malformed_item.visible_to_agent: true
when.operation: store_validated_entity_catalog
then.malformed.result.accepted: false
then.malformed.result.code: invalid_entity_catalog_item
then.malformed.result.error: $.domain is required.
then.malformed.result.item_index: 0
then.malformed.raw_items_after_attempt: []
then.malformed.store_after_attempt.item_count: 0
```

### Scenario H

```text
case_id: entity_catalog_remains_non_orchestrating
when.operation: aggregate_observed_side_effects
then.side_effects.forbidden_aggregate.worker_called: false
then.side_effects.forbidden_aggregate.model_provider_called: false
then.side_effects.forbidden_aggregate.home_assistant_history_called: false
then.side_effects.forbidden_aggregate.semantic_memory_called: false
then.side_effects.forbidden_aggregate.home_assistant_service_or_state_mutation_called: false
then.side_effects.forbidden_aggregate.token_generated: false
then.side_effects.forbidden_aggregate.chart_artifact_written: false
then.side_effects.forbidden_aggregate.job_orchestration_called: false
then.side_effects.forbidden_aggregate.websocket_command_registered: false
then.side_effects.forbidden_aggregate.dashboard_resource_metadata_written_or_reused: false
then.side_effects.allowed_aggregate.entity_catalog_scaffold_written: true
then.side_effects.allowed_aggregate.home_assistant_entity_metadata_read: true
```

## Adjacent Home Assistant Eval Verification

Raw commands:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_integration_scaffold.py
.\.venv\Scripts\python.exe evals\home_assistant_config_flow_options.py
.\.venv\Scripts\python.exe evals\home_assistant_hacs_install_packaging.py
.\.venv\Scripts\python.exe evals\home_assistant_dashboard_resource_registration.py
.\.venv\Scripts\python.exe evals\home_assistant_websocket_command_registration.py
.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_scaffold.py
```

Raw output endings:

```text
PASS home_assistant_integration_scaffold
PASS home_assistant_config_flow_options
PASS home_assistant_hacs_install_packaging
PASS home_assistant_dashboard_resource_registration
PASS home_assistant_websocket_command_registration
PASS home_assistant_job_orchestration_scaffold
```
