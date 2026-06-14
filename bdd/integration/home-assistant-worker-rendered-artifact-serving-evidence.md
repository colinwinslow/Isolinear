# Home Assistant Integration: Worker-Rendered Artifact Serving - Evidence

Status: accepted proof captured on 2026-06-14.

## Focused pytest

Command:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_worker_rendered_artifact_serving.py -q -s
```

Output:

```text
.....WORKER_RENDERED_ARTIFACT_EVIDENCE
{'snapshot_status': 'complete', 'artifact_url': '/api/isolinear/artifacts/worker-real-slice-entry-artifact-001.png', 'png_signature': [137, 80, 78, 71, 13, 10, 26, 10], 'worker_call_count': 1, 'worker_authorization_redacted': True, 'local_paths_exposed': False, 'worker_paths_exposed': False, 'orchestration': {'worker_called': True, 'model_provider_called': True, 'home_assistant_history_called': False, 'semantic_memory_called': False, 'home_assistant_service_or_state_mutation_called': False, 'token_generated': False, 'chart_artifact_written': True, 'chart_rendering_called': True, 'durable_storage_written': False, 'retry_behavior_called': False, 'subscription_progress_streaming_called': False, 'worker_progress_streaming_called': False, 'automatic_progress_task_called': False, 'job_orchestration_called': False, 'model_provider_retry_policy_bookkeeping_written': False, 'approved_entity_catalog_read': False, 'home_assistant_history_read': False, 'history_retrieval_scaffold_written': False, 'job_state_scaffold_written': True, 'job_orchestration_scaffold_written': True, 'subscription_bookkeeping_written': False, 'artifact_metadata_bookkeeping_written': True, 'render_plan_bookkeeping_written': True, 'model_provider_plan_bookkeeping_written': True, 'worker_dispatch_bookkeeping_written': True, 'worker_progress_bookkeeping_written': False, 'worker_retry_policy_bookkeeping_written': False, 'worker_transport_failure_classification_bookkeeping_written': False, 'websocket_command_registered': False}}
.
6 passed in 0.61s
```

## Adjacent verification

Commands:

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_first_real_vertical_slice.py tests/test_job_orchestration_worker_dispatch_rendering_anchor.py tests/test_dashboard_card_long_running_smoke.py -q
```

Output:

```text
18 passed in 7.82s
```

## Full unit sweep

Command:

```bash
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

Output:

```text
315 passed in 70.17s (0:01:10)
```

## Architecture Review

Command:

```bash
codex exec "You are performing the Isolinear architecture review pass for the current uncommitted diff after the worker-rendered artifact serving fixes..."
```

Result:

```text
Findings: No blocking findings.
Residual risks: artifact_rollback diagnostics are not surfaced by the outer rejection wrapper; non-serving legacy worker scaffold stores the raw worker render_result internally, though registered responses strip paths/base64.
Focused verification inside review: 6 passed in 0.58s.
```

## Legacy Worker-Dispatch Eval

Command:

```bash
.\.venv\Scripts\python.exe evals/home_assistant_job_orchestration_worker_dispatch_rendering_scaffold.py
```

Result:

```text
PASS home_assistant_job_orchestration_worker_dispatch_rendering_scaffold
```

The eval evidence retained `chart_artifact_written: false` for the older
worker-dispatch scaffold path, confirming the new worker artifact write remains
scoped to the real-slice provider-plan route.
