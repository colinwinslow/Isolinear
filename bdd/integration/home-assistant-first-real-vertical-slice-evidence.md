# Home Assistant Integration: First Real Vertical Slice - Evidence

Run timestamp: 2026-06-13T07:09:12.5831438-07:00

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
    "accepted": false,
    "code": "model_provider_chart_spec_hidden_entity",
    "orchestration": {
      "model_provider_called": true,
      "chart_rendering_called": false,
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

## Scenario C - repeated snapshot requests reuse the artifact

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

## Test Output

```text
3 passed in 3.51s
54 passed in 5.91s
57 passed in 9.37s
303 passed in 63.78s
```
