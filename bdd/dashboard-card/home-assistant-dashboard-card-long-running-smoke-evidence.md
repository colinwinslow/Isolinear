# Home Assistant Dashboard Card: Long-Running Prompt Smoke - Evidence

Paired BDD:
`bdd/dashboard-card/home-assistant-dashboard-card-long-running-smoke-bdd.md`

Run date: 2026-06-13

## Scenario A - delayed card prompt reaches chart result

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
  "chart_image_url_prefix": "data:image/png;base64,iVBORw0K",
  "validation_status": "pass",
  "submit_disabled_during_active_job": true
}

 ✓ src/isolinear-card.long-running-smoke.test.ts > Isolinear mounted card long-running smoke > polls job/snapshot until a delayed prompt renders a PNG chart 58ms

 Test Files  1 passed (1)
      Tests  1 passed (1)
   Start at  11:06:32
   Duration  2.38s (transform 101ms, setup 0ms, import 224ms, tests 59ms, environment 1.08s)

stderr | src/isolinear-card.long-running-smoke.test.ts
Lit is in dev mode. Not recommended for production! See https://lit.dev/msg/dev-mode for more information.
```

## Scenario B - registered commands return a PNG snapshot

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dashboard_card_long_running_smoke.py -s
```

Raw output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 1 item

tests\test_dashboard_card_long_running_smoke.py REGISTERED_WS_SMOKE_EVIDENCE
{'prompt': 'Show sensor.upstairs_temperature for the last 24 hours', 'elapsed_ms': 2890, 'command_types': ['isolinear/v1/job/start', 'isolinear/v1/job/snapshot'], 'start_status': 'planning', 'snapshot_status': 'complete', 'png_signature': [137, 80, 78, 71, 13, 10, 26, 10], 'planner_call_count': 1, 'approved_entity_ids': ['sensor.upstairs_temperature'], 'orchestration': {'worker_called': False, 'model_provider_called': True, 'home_assistant_history_called': False, 'semantic_memory_called': False, 'home_assistant_service_or_state_mutation_called': False, 'token_generated': False, 'chart_artifact_written': False, 'chart_rendering_called': True, 'durable_storage_written': False, 'retry_behavior_called': False, 'subscription_progress_streaming_called': False, 'worker_progress_streaming_called': False, 'automatic_progress_task_called': False, 'job_orchestration_called': False, 'model_provider_retry_policy_bookkeeping_written': False, 'approved_entity_catalog_read': False, 'home_assistant_history_read': False, 'history_retrieval_scaffold_written': False, 'job_state_scaffold_written': True, 'job_orchestration_scaffold_written': True, 'subscription_bookkeeping_written': False, 'artifact_metadata_bookkeeping_written': True, 'render_plan_bookkeeping_written': True, 'model_provider_plan_bookkeeping_written': True, 'worker_dispatch_bookkeeping_written': False, 'worker_progress_bookkeeping_written': False, 'worker_retry_policy_bookkeeping_written': False, 'worker_transport_failure_classification_bookkeeping_written': False, 'websocket_command_registered': False}}
.

============================== 1 passed in 3.08s ==============================
```

## Scenario C - browser remains a thin client

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dashboard_card_anchor.py
```

Raw output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 7 items

tests\test_dashboard_card_anchor.py .......                              [100%]

============================== 7 passed in 0.14s ==============================
```

## Build and broader frontend verification

Command:

```powershell
.\scripts\frontend.ps1 build
```

Raw output:

```text
Node: v24.16.0
npm: 11.13.0

> build
> tsc -p tsconfig.json --noEmit && vite build

vite v8.0.16 building client environment for production...
transforming...✓ 21 modules transformed.
rendering chunks...
computing gzip size...
dist/isolinear-card.js  34.96 kB │ gzip: 10.64 kB

✓ built in 75ms
```

Command:

```powershell
.\scripts\frontend.ps1 test
```

Raw output:

```text
Node: v24.16.0
npm: 11.13.0

> test
> vitest run


 RUN  v4.1.8 C:/Users/c.winslow/OneDrive - Kagwerks/Documents/Repos/Isolinear/frontend


 Test Files  2 passed (2)
      Tests  5 passed (5)
   Start at  11:04:58
   Duration  2.52s (transform 129ms, setup 0ms, import 280ms, tests 58ms, environment 1.20s)
```
