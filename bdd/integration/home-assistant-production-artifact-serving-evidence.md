# Home Assistant Integration: Production Artifact Serving - Evidence

Paired BDD:
`bdd/integration/home-assistant-production-artifact-serving-bdd.md`

Run date: 2026-06-13

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

## Scenarios A-E - static path, served PNG URL, idempotence, failure rollback

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
collecting ... collected 7 items

tests/test_first_real_vertical_slice.py::FirstRealVerticalSliceTests::test_artifact_metadata_validation_failure_leaves_no_png_file PASSED [ 14%]
tests/test_first_real_vertical_slice.py::FirstRealVerticalSliceTests::test_complete_snapshot_validation_failure_rolls_back_png_file PASSED [ 28%]
tests/test_first_real_vertical_slice.py::FirstRealVerticalSliceTests::test_config_entry_setup_registers_artifact_static_path PASSED [ 42%]
tests/test_first_real_vertical_slice.py::FirstRealVerticalSliceTests::test_hidden_provider_entity_fails_before_render_and_artifact_storage PASSED [ 57%]
tests/test_first_real_vertical_slice.py::FirstRealVerticalSliceTests::test_ollama_structured_output_schema_embeds_chart_spec_contract PASSED [ 71%]
tests/test_first_real_vertical_slice.py::FirstRealVerticalSliceTests::test_prompt_returns_served_png_artifact_from_in_process_renderer PASSED [ 85%]
tests/test_first_real_vertical_slice.py::FirstRealVerticalSliceTests::test_repeated_snapshot_reuses_completed_png_artifact PASSED [100%]

============================== 7 passed in 3.62s ==============================
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
  "artifact_renderer": "in_process_matplotlib",
  "png_signature": [137, 80, 78, 71, 13, 10, 26, 10],
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
{'prompt': 'Show sensor.upstairs_temperature for the last 24 hours', 'elapsed_ms': 2114, 'command_types': ['isolinear/v1/job/start', 'isolinear/v1/job/snapshot'], 'start_status': 'planning', 'snapshot_status': 'complete', 'artifact_url': '/api/isolinear/artifacts/real-slice-entry-artifact-001.png', 'artifact_path': 'C:\\Users\\C12BA~1.WIN\\AppData\\Local\\Temp\\tmpdxwir9wr\\real-slice-entry-artifact-001.png', 'png_signature': [137, 80, 78, 71, 13, 10, 26, 10], 'planner_call_count': 1, 'approved_entity_ids': ['sensor.upstairs_temperature'], 'orchestration': {'worker_called': False, 'model_provider_called': True, 'home_assistant_history_called': False, 'semantic_memory_called': False, 'home_assistant_service_or_state_mutation_called': False, 'token_generated': False, 'chart_artifact_written': True, 'chart_rendering_called': True, 'durable_storage_written': False, 'retry_behavior_called': False, 'subscription_progress_streaming_called': False, 'worker_progress_streaming_called': False, 'automatic_progress_task_called': False, 'job_orchestration_called': False, 'model_provider_retry_policy_bookkeeping_written': False, 'approved_entity_catalog_read': False, 'home_assistant_history_read': False, 'history_retrieval_scaffold_written': False, 'job_state_scaffold_written': True, 'job_orchestration_scaffold_written': True, 'subscription_bookkeeping_written': False, 'artifact_metadata_bookkeeping_written': True, 'render_plan_bookkeeping_written': True, 'model_provider_plan_bookkeeping_written': True, 'worker_dispatch_bookkeeping_written': False, 'worker_progress_bookkeeping_written': False, 'worker_retry_policy_bookkeeping_written': False, 'worker_transport_failure_classification_bookkeeping_written': False, 'websocket_command_registered': False}}
.
1 passed in 2.30s
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

 ✓ src/isolinear-card.long-running-smoke.test.ts > Isolinear mounted card long-running smoke > polls job/snapshot until a delayed prompt renders a PNG chart 56ms

 Test Files  1 passed (1)
      Tests  1 passed (1)
   Start at  13:16:53
   Duration  2.37s (transform 95ms, setup 0ms, import 209ms, tests 57ms, environment 1.09s)

stderr | src/isolinear-card.long-running-smoke.test.ts
Lit is in dev mode. Not recommended for production! See https://lit.dev/msg/dev-mode for more information.
```
