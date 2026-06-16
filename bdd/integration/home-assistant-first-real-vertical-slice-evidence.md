# Home Assistant Integration: First Real Vertical Slice - Evidence

Run timestamp: 2026-06-13T10:05:08.5235113-07:00

## Scenario A - happy path: allowed prompt returns a PNG chart

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_first_real_vertical_slice.py -q
```

Raw result snippet:

```json
{
  "start_result": {
    "accepted": true,
    "code": "registered_job_state_command_accepted",
    "snapshot_id": "real-slice-entry-job-001-snapshot-003",
    "job_id": "real-slice-entry-job-001",
    "status": "planning"
  },
  "snapshot_result": {
    "accepted": true,
    "code": "registered_job_state_command_accepted",
    "snapshot_id": "real-slice-entry-job-001-snapshot-004",
    "status": "complete",
    "message": "In-process trusted matplotlib render is ready for the dashboard card.",
    "image_url_prefix": "data:image/png;base64,",
    "png_signature": [137, 80, 78, 71, 13, 10, 26, 10],
    "validation": {
      "status": "pass",
      "summary": "The first real vertical slice rendered a schema-valid PNG chart in process.",
      "checks": [
        {"name": "integration_job_state_scaffold", "status": "pass"},
        {"name": "integration_artifact_metadata", "status": "pass"},
        {"name": "worker", "status": "not_called"},
        {"name": "chart_rendering", "status": "pass"}
      ]
    },
    "warnings": [
      "first_real_vertical_slice",
      "in_process_matplotlib_renderer",
      "chart_artifact_data_url",
      "worker_not_called"
    ],
    "in_process_render": {
      "renderer": "in_process_matplotlib",
      "render_result": {
        "request_id": "real-slice-entry-render-request-001",
        "status": "success",
        "image_id": "real-slice-entry-render-request-001-image",
        "image_mime_type": "image/png",
        "image_path": null,
        "error": null,
        "render_metadata": {
          "title": "Real Slice Upstairs Temperature",
          "series_plotted": ["sensor_upstairs_temperature"],
          "overlays_plotted": [],
          "x_min": "2026-06-13T03:36:38+00:00",
          "x_max": "2026-06-13T06:36:38+00:00",
          "warnings": [],
          "codegen_attempts": 0
        }
      },
      "png_byte_count": 44355,
      "image_url_prefix": "data:image/png;base64"
    }
  },
  "store": {
    "provider_plan_order": ["real-slice-entry-provider-plan-001"],
    "render_plan_order": ["real-slice-entry-render-plan-001"],
    "artifact_order": ["real-slice-entry-artifact-001"],
    "worker_dispatch_order": [],
    "latest_artifact": {
      "artifact_id": "real-slice-entry-artifact-001",
      "status": "rendered",
      "render_metadata": {
        "renderer": "in_process_matplotlib",
        "render_attempted": true,
        "worker_called": false,
        "chart_rendering_called": true
      }
    }
  }
}
```

## Scenario B - hidden provider entity fails closed

Raw result snippet:

```json
{
  "snapshot_result": {
    "accepted": true,
    "code": "registered_job_state_command_accepted",
    "status": "failed",
    "failure": {
      "stage": "model_provider_planning",
      "code": "model_provider_chart_spec_hidden_entity",
      "message": "The model provider returned a chart spec that referenced an entity outside the approved allowlist."
    },
    "orchestration": {
      "model_provider_called": true,
      "chart_rendering_called": false,
      "chart_artifact_written": false,
      "artifact_metadata_bookkeeping_written": false,
      "render_plan_bookkeeping_written": false,
      "model_provider_plan_bookkeeping_written": false,
      "worker_dispatch_bookkeeping_written": false
    }
  },
  "planner_call_count": 1,
  "store": {
    "provider_plan_order": [],
    "render_plan_order": [],
    "artifact_order": [],
    "worker_dispatch_order": []
  }
}
```

## Scenario C - invalid provider chart output returns a failed snapshot

Raw result snippet:

```json
{
  "snapshot_result": {
    "accepted": true,
    "code": "registered_job_state_command_accepted",
    "status": "failed",
    "failure": {
      "stage": "model_provider_planning",
      "code": "invalid_model_provider_chart_spec",
      "message": "The model provider returned a chart spec that failed schema validation."
    },
    "orchestration": {
      "model_provider_called": true,
      "chart_rendering_called": false,
      "chart_artifact_written": false,
      "artifact_metadata_bookkeeping_written": false,
      "render_plan_bookkeeping_written": false,
      "model_provider_plan_bookkeeping_written": false
    }
  },
  "planner_call_count": 1,
  "png_files_written": 0
}
```

## Scenario D - repeated snapshot requests reuse the artifact

Raw result snippet:

```json
{
  "first_snapshot_id": "real-slice-entry-job-001-snapshot-004",
  "second_snapshot_id": "real-slice-entry-job-001-snapshot-004",
  "same_snapshot_returned": true,
  "planner_call_count": 1,
  "store": {
    "provider_plan_count": 1,
    "render_plan_count": 1,
    "artifact_count": 1,
    "worker_dispatch_count": 0
  }
}
```

## Manual real Home Assistant + Ollama verification

Manual verification timestamp: 2026-06-13.

Runtime shape:

- Home Assistant core: `2025.1.4`, running in WSL Ubuntu 24.04 with a temporary
  config directory and a real SQLite recorder database.
- Ollama endpoint: `http://10.0.1.39:11434`.
- Planner model: `gemma4:e4b` as reported by Ollama `/api/tags`.
- Entity allowlist: `["sensor.isolinear_probe_temperature"]`.
- Invocation path: current custom integration loaded into a real Home
  Assistant `HomeAssistant` object, then `isolinear/v1/job/start` and
  `isolinear/v1/job/snapshot` dispatched through the registered Home Assistant
  WebSocket handlers with a test connection object.

Command shape:

```powershell
wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/c.winslow/OneDrive\ -\ Kagwerks/Documents/Repos/Isolinear && /home/cwinslow/.cache/isolinear-ha-site-20260613/bin/python <manual-real-ha-ollama-script>"
```

Raw result snippet:

```json
{
  "hass_ready": true,
  "real_recorder_history_count": 4,
  "setup": {
    "isolinear_setup_ok": true,
    "catalog_setup": {
      "code": "entity_catalog_ready",
      "item_count": 1,
      "entity_ids": ["sensor.isolinear_probe_temperature"],
      "all_visible_to_agent": true
    },
    "history_setup": {
      "code": "history_retrieval_ready",
      "entities": ["sensor.isolinear_probe_temperature"]
    },
    "model_setup": {
      "code": "model_provider_planner_configured",
      "provider": {
        "type": "ollama_compatible",
        "role": "planner",
        "endpoint_url": "http://10.0.1.39:11434",
        "model": "gemma4:e4b"
      }
    },
    "dashboard_resource_code": "dashboard_resource_registered",
    "websocket_code": "websocket_commands_registered"
  },
  "start_result": {
    "accepted": true,
    "code": "registered_job_state_command_accepted",
    "connection_errors": [],
    "connection_result_status": "planning",
    "job_id": "real-ha-entry-pass-job-001",
    "status": "planning"
  },
  "snapshot_result": {
    "accepted": true,
    "code": "registered_job_state_command_accepted",
    "connection_errors": [],
    "status": "complete",
    "message": "In-process trusted matplotlib render is ready for the dashboard card.",
    "image_url_prefix": "data:image/png;base64,",
    "image_url_length": 56110,
    "png_signature": [137, 80, 78, 71, 13, 10, 26, 10],
    "orchestration": {
      "model_provider_called": true,
      "chart_rendering_called": true,
      "worker_called": false,
      "model_provider_plan_bookkeeping_written": true,
      "render_plan_bookkeeping_written": true,
      "artifact_metadata_bookkeeping_written": true,
      "home_assistant_mutation": false,
      "semantic_memory_written": false,
      "worker_token_written": false
    }
  },
  "store_counts": {
    "provider_plans": 1,
    "render_plans": 1,
    "artifacts": 1,
    "worker_dispatches": 0,
    "artifact_renderer": "in_process_matplotlib",
    "artifact_status": "rendered",
    "chart_entity": "sensor.isolinear_probe_temperature",
    "history_series": ["sensor.isolinear_probe_temperature"]
  }
}
```

Runtime drift found and closed:

- Real Home Assistant recorder access cannot run inside the event loop, and
  Home Assistant's WebSocket dispatcher does not directly await bare coroutine
  handlers. The registered WebSocket handler now uses Home Assistant's
  `async_response` scheduler and awaits an async bridge that runs the existing
  blocking orchestration helper through `hass.async_add_executor_job`.
- The first live `gemma4:e4b` structured response used a graph-shaped object
  instead of the expected `ChartSpec` fields. The Ollama structured-output
  schema now narrows `chart_spec` to the first-slice `time_series` contract and
  the prompt includes a minimal valid example.

## Test Output

```text
4 passed in 3.47s
8 passed in 0.45s
40 passed in 6.72s
305 passed in 57.56s
```

## Regression Addendum - 2026-06-16 Provider Output Failure Snapshot

Live dashboard retesting showed that some model-provider failures could reach
the card as generic registered WebSocket command rejections instead of
card-facing failed job snapshots. Focused regression coverage now proves invalid
provider chart output returns a failed snapshot with model-provider failure
details while still avoiding render and artifact writes.

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_first_real_vertical_slice.py -q
```

Raw output:

```text
...........                                                              [100%]
11 passed in 4.90s
```

Verified behavior:

```text
invalid provider chart output:
  registered command accepted: true
  snapshot status: failed
  failure stage: model_provider_planning
  failure code: invalid_model_provider_chart_spec
  model provider called: true
  chart rendering called: false
  chart artifact written: false
  PNG files written: 0
```
