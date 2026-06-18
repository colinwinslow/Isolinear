# Home Assistant Integration: Production Artifact Serving - Evidence

Paired BDD:
`bdd/integration/home-assistant-production-artifact-serving-bdd.md`

Run date: 2026-06-16
Latest regression run: 2026-06-17 (renderer switched matplotlib → Pillow per
ADR-0019; `artifact_renderer` is now `in_process_pillow`; re-run `351 passed`)

## Scenario coverage map

- Scenario A - setup path: artifact static path is registered:
  `test_config_entry_setup_registers_artifact_static_path`
- Scenario B - happy path: allowed prompt returns a served PNG artifact URL:
  `test_prompt_returns_served_png_artifact_from_in_process_renderer` and
  registered command smoke output
- Scenario C - idempotence path: repeated snapshots reuse the served artifact:
  `test_repeated_snapshot_reuses_completed_png_artifact`
- Scenario D - failure path: hidden provider entity fails before file write:
  `test_hidden_provider_entity_fails_before_render_and_artifact_storage`
- Scenario E - failure path: complete snapshot validation rolls back artifact
  state: `test_complete_snapshot_validation_failure_rolls_back_png_file`
- Scenario F - card path: mounted card renders the served artifact URL:
  mounted card Vitest smoke output
- Scenario G - clarification path: selected entity renders a served PNG
  artifact: `test_clarification_answer_returns_served_png_artifact_from_in_process_renderer`
- Scenario H - live regression path: read-only config data keeps planner
  configured:
  `test_real_slice_home_assistant_mapping_config_data_configures_planner_and_serves_png`
- Scenario I - live regression path: overlapping snapshot polls are
  single-flight:
  `test_registered_snapshot_poll_is_single_flight_while_planner_is_running` and
  `test_registered_snapshot_poll_rechecks_completed_artifact_after_lock_acquire`
- Real-render guard - missing planner fails before placeholder artifact storage:
  `test_real_slice_missing_planner_fails_before_placeholder_artifact_storage`

## Scenarios A-E and G-H - static path, served PNG URL, clarification, idempotence, failure rollback, mapping config data

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_first_real_vertical_slice.py -vv
```

Raw output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0 -- C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collecting ... collected 10 items

tests/test_first_real_vertical_slice.py::FirstRealVerticalSliceTests::test_artifact_metadata_validation_failure_leaves_no_png_file PASSED [ 10%]
tests/test_first_real_vertical_slice.py::FirstRealVerticalSliceTests::test_clarification_answer_returns_served_png_artifact_from_in_process_renderer PASSED [ 20%]
tests/test_first_real_vertical_slice.py::FirstRealVerticalSliceTests::test_complete_snapshot_validation_failure_rolls_back_png_file PASSED [ 30%]
tests/test_first_real_vertical_slice.py::FirstRealVerticalSliceTests::test_config_entry_setup_registers_artifact_static_path PASSED [ 40%]
tests/test_first_real_vertical_slice.py::FirstRealVerticalSliceTests::test_hidden_provider_entity_fails_before_render_and_artifact_storage PASSED [ 50%]
tests/test_first_real_vertical_slice.py::FirstRealVerticalSliceTests::test_ollama_structured_output_schema_embeds_chart_spec_contract PASSED [ 60%]
tests/test_first_real_vertical_slice.py::FirstRealVerticalSliceTests::test_prompt_returns_served_png_artifact_from_in_process_renderer PASSED [ 70%]
tests/test_first_real_vertical_slice.py::FirstRealVerticalSliceTests::test_real_slice_home_assistant_mapping_config_data_configures_planner_and_serves_png PASSED [ 80%]
tests/test_first_real_vertical_slice.py::FirstRealVerticalSliceTests::test_real_slice_missing_planner_fails_before_placeholder_artifact_storage PASSED [ 90%]
tests/test_first_real_vertical_slice.py::FirstRealVerticalSliceTests::test_repeated_snapshot_reuses_completed_png_artifact PASSED [100%]

============================= 10 passed in 8.02s ==============================
```

The passing tests assert these raw values from the returned snapshot and on-disk
artifact:

```json
{
  "artifact_static_url_path": "/api/isolinear/artifacts",
  "returned_image_url_shape": "/api/isolinear/artifacts/<artifact_id>.png",
  "returned_image_url_is_data_url": false,
  "registered_response_local_path_fields_present": false,
  "artifact_status": "rendered",
  "artifact_renderer": "in_process_pillow",
  "png_signature": [137, 80, 78, 71, 13, 10, 26, 10],
  "clarification_start_status": "clarification_needed",
  "clarification_answer_status": "planning",
  "clarification_selected_entity": "sensor.downstairs_temperature",
  "clarification_planner_approved_entity_ids": ["sensor.downstairs_temperature"],
  "clarification_artifact_status": "rendered",
  "clarification_artifact_renderer": "in_process_pillow",
  "clarification_validation_summary_contains_placeholder": false,
  "missing_planner_snapshot_status": "failed",
  "missing_planner_failure_code": "model_provider_planner_not_configured",
  "missing_planner_artifact_order_count": 0,
  "missing_planner_png_file_count": 0,
  "mapping_config_data_type": "mappingproxy",
  "mapping_config_model_provider_setup_code": "model_provider_planner_configured",
  "mapping_config_snapshot_status": "complete",
  "mapping_config_artifact_url_prefix": "/api/isolinear/artifacts",
  "mapping_config_png_signature": [137, 80, 78, 71, 13, 10, 26, 10],
  "mapping_config_planner_call_count": 1,
  "hidden_entity_failure_code": "model_provider_chart_spec_hidden_entity",
  "hidden_entity_png_file_count": 0,
  "forced_artifact_metadata_failure_code": "invalid_in_process_artifact_metadata",
  "forced_artifact_metadata_failure_png_file_count": 0,
  "forced_complete_snapshot_failure_code": "invalid_integration_job_snapshot",
  "forced_complete_snapshot_failure_png_file_count_after_rollback": 0,
  "forced_complete_snapshot_failure_bookkeeping_counts_after_rollback": {
    "artifact_order": 0,
    "render_plan_order": 0,
    "model_provider_plan_order": 0,
    "artifact_by_job_id": 0,
    "render_plan_by_job_id": 0,
    "model_provider_plan_by_job_id": 0
  },
  "idempotent_png_file_count": 1,
  "idempotent_second_snapshot_chart_artifact_written": false
}
```

## Scenario B - registered command path returns served artifact details

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dashboard_card_long_running_smoke.py -q -s
```

Raw output:

```text
REGISTERED_WS_SMOKE_EVIDENCE
{'prompt': 'Show sensor.upstairs_temperature for the last 24 hours', 'elapsed_ms': 5196, 'command_types': ['isolinear/v1/job/start', 'isolinear/v1/job/snapshot'], 'start_status': 'planning', 'snapshot_status': 'complete', 'artifact_url': '/api/isolinear/artifacts/real-slice-entry-artifact-001.png', 'artifact_path': 'C:\\Users\\C12BA~1.WIN\\AppData\\Local\\Temp\\tmp1gbk9aj0\\real-slice-entry-artifact-001.png', 'png_signature': [137, 80, 78, 71, 13, 10, 26, 10], 'planner_call_count': 1, 'approved_entity_ids': ['sensor.upstairs_temperature'], 'orchestration': {'worker_called': False, 'model_provider_called': True, 'home_assistant_history_called': False, 'semantic_memory_called': False, 'home_assistant_service_or_state_mutation_called': False, 'token_generated': False, 'chart_artifact_written': True, 'chart_rendering_called': True, 'durable_storage_written': False, 'retry_behavior_called': False, 'subscription_progress_streaming_called': False, 'worker_progress_streaming_called': False, 'automatic_progress_task_called': False, 'job_orchestration_called': False, 'model_provider_retry_policy_bookkeeping_written': False, 'approved_entity_catalog_read': False, 'home_assistant_history_read': False, 'history_retrieval_scaffold_written': False, 'job_state_scaffold_written': True, 'job_orchestration_scaffold_written': True, 'subscription_bookkeeping_written': False, 'artifact_metadata_bookkeeping_written': True, 'render_plan_bookkeeping_written': True, 'model_provider_plan_bookkeeping_written': True, 'worker_dispatch_bookkeeping_written': False, 'worker_progress_bookkeeping_written': False, 'worker_retry_policy_bookkeeping_written': False, 'worker_transport_failure_classification_bookkeeping_written': False, 'websocket_command_registered': False}}
.
1 passed in 5.54s
```

## Scenario F - mounted card renders the served artifact URL

Command:

```powershell
.\scripts\frontend.ps1 test -- --reporter=verbose --silent=false src/isolinear-card.long-running-smoke.test.ts
```

Raw output:

```text
Node: v24.16.0
npm: 11.13.0

> test
> vitest run --reporter=verbose --silent=false src/isolinear-card.long-running-smoke.test.ts


 RUN  v4.1.8 C:/Users/c.winslow/OneDrive - Kagwerks/Documents/Repos/Isolinear/frontend

stdout | src/isolinear-card.long-running-smoke.test.ts > Isolinear mounted card long-running smoke > polls job/snapshot until a delayed prompt renders a PNG chart
CARD_SMOKE_EVIDENCE {
  "command_types": [
    "isolinear/v1/job/start",
    "isolinear/v1/job/snapshot"
  ],
  "final_status": "complete",
  "final_layout": "chart-first",
  "chart_image_url_prefix": "/api/isolinear/artifacts",
  "validation_status": "pass",
  "submit_disabled_during_active_job": true
}

 ✓ src/isolinear-card.long-running-smoke.test.ts > Isolinear mounted card long-running smoke > uses automatic config-entry resolution in the picker stub config 3ms
 ✓ src/isolinear-card.long-running-smoke.test.ts > Isolinear mounted card long-running smoke > normalizes the legacy fake config entry placeholder to auto 40ms
 ✓ src/isolinear-card.long-running-smoke.test.ts > Isolinear mounted card long-running smoke > shows auto in the editor when Home Assistant passes the legacy fake config entry placeholder 3ms
 ✓ src/isolinear-card.long-running-smoke.test.ts > Isolinear mounted card long-running smoke > polls job/snapshot until a delayed prompt renders a PNG chart 50ms
 ✓ src/isolinear-card.long-running-smoke.test.ts > Isolinear mounted card long-running smoke > shows a visible failure when prompt submission is rejected 23ms

 Test Files  1 passed (1)
      Tests  5 passed (5)
   Start at  12:42:36
   Duration  6.84s (transform 164ms, setup 0ms, import 501ms, tests 121ms, environment 4.91s)

stderr | src/isolinear-card.long-running-smoke.test.ts
Lit is in dev mode. Not recommended for production! See https://lit.dev/msg/dev-mode for more information.
```

## Scenario I - overlapping snapshot polls stay single-flight

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dashboard_card_long_running_smoke.py -q -s
```

Raw output:

```text
.REGISTERED_WS_SINGLE_FLIGHT_EVIDENCE
{'in_progress_code': 'job_orchestration_artifact_snapshot_in_progress', 'in_progress_status': 'planning', 'in_progress_stage': 'job_orchestration_scaffold_ready', 'first_status': 'complete', 'final_status': 'complete', 'planner_call_count': 1, 'png_signature': [137, 80, 78, 71, 13, 10, 26, 10]}
.REGISTERED_WS_STALE_LOCK_RECHECK_EVIDENCE
{'second_job_state_code': 'job_orchestration_artifact_snapshot_returned', 'first_status': 'complete', 'second_status': 'complete', 'planner_call_count': 1, 'lock_call_count': 2}
.REGISTERED_WS_SMOKE_EVIDENCE
{'prompt': 'Show sensor.upstairs_temperature for the last 24 hours', 'elapsed_ms': 400, 'command_types': ['isolinear/v1/job/start', 'isolinear/v1/job/snapshot'], 'start_status': 'planning', 'snapshot_status': 'complete', 'artifact_url': '/api/isolinear/artifacts/real-slice-entry-artifact-001.png', 'artifact_path': 'C:\\Users\\C12BA~1.WIN\\AppData\\Local\\Temp\\tmp6ei9xunt\\real-slice-entry-artifact-001.png', 'png_signature': [137, 80, 78, 71, 13, 10, 26, 10], 'planner_call_count': 1, 'approved_entity_ids': ['sensor.upstairs_temperature'], 'orchestration': {'worker_called': False, 'model_provider_called': True, 'home_assistant_history_called': False, 'semantic_memory_called': False, 'home_assistant_service_or_state_mutation_called': False, 'token_generated': False, 'chart_artifact_written': True, 'chart_rendering_called': True, 'durable_storage_written': False, 'retry_behavior_called': False, 'subscription_progress_streaming_called': False, 'worker_progress_streaming_called': False, 'automatic_progress_task_called': False, 'job_orchestration_called': False, 'model_provider_retry_policy_bookkeeping_written': False, 'approved_entity_catalog_read': False, 'home_assistant_history_read': False, 'history_retrieval_scaffold_written': False, 'job_state_scaffold_written': True, 'job_orchestration_scaffold_written': True, 'subscription_bookkeeping_written': False, 'artifact_metadata_bookkeeping_written': True, 'render_plan_bookkeeping_written': True, 'model_provider_plan_bookkeeping_written': True, 'worker_dispatch_bookkeeping_written': False, 'worker_progress_bookkeeping_written': False, 'worker_retry_policy_bookkeeping_written': False, 'worker_transport_failure_classification_bookkeeping_written': False, 'websocket_command_registered': False}}
.
4 passed in 5.68s
```
