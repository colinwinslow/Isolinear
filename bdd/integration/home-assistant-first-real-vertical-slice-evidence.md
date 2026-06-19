# Home Assistant Integration: First Real Vertical Slice - Evidence

Initial run timestamp: 2026-06-13T10:05:08.5235113-07:00
Latest regression run timestamp: 2026-06-18 (venv Python 3.14.5 / Pillow 12.2.0; `370 passed`; ADR-0020/0021 model-resolved window + tiered data source, 0.1.22)

> Renderer note (ADR-0019): the trusted in-process renderer now draws with
> Pillow instead of matplotlib. The renderer identifier is `in_process_pillow`
> and the PNG signature below is unchanged (`[137, 80, 78, 71, 13, 10, 26, 10]`,
> verified against a fresh Pillow render).

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
    "message": "In-process trusted Pillow render is ready for the dashboard card.",
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
      "in_process_pillow_renderer",
      "chart_artifact_data_url",
      "worker_not_called"
    ],
    "in_process_render": {
      "renderer": "in_process_pillow",
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
        "renderer": "in_process_pillow",
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
    "message": "In-process trusted Pillow render is ready for the dashboard card.",
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
    "artifact_renderer": "in_process_pillow",
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

## Regression Addendum - 2026-06-17 Trusted Renderer Failure Snapshot

Live dashboard retesting of `0.1.14` showed `job/snapshot` rejections with
`code=in_process_renderer_failed` after the backend reached real recorder
history and the trusted renderer path. Focused regression coverage now proves
trusted renderer failures return card-facing failed job snapshots instead of
snapshot-poll command rejections.

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_first_real_vertical_slice.py -q
```

Raw output:

```text
............                                                             [100%]
12 passed in 5.06s
```

Focused evidence command:

```powershell
@'
<inline Python script patching render_in_process_chart to return in_process_renderer_failed>
'@ | .\.venv\Scripts\python.exe -
```

Raw result:

```json
{
  "orchestration": {
    "artifact_metadata_bookkeeping_written": false,
    "chart_artifact_written": false,
    "chart_rendering_called": true,
    "model_provider_called": true
  },
  "png_files_written": 0,
  "snapshot": {
    "accepted": true,
    "code": "registered_job_state_command_accepted",
    "failure": {
      "code": "in_process_renderer_failed",
      "message": "The trusted chart renderer failed before a chart artifact was accepted.",
      "stage": "chart_rendering"
    },
    "job_state_code": "job_orchestration_in_process_renderer_failure_snapshot_recorded",
    "progress_stage": "in_process_renderer_failure_snapshot_ready",
    "retry_allowed": true,
    "status": "failed"
  },
  "start": {
    "accepted": true,
    "code": "registered_job_state_command_accepted",
    "job_id": "real-slice-entry-job-001",
    "status": "planning"
  },
  "store": {
    "artifact_order": [],
    "provider_plan_order": [],
    "render_plan_order": []
  }
}
```

## Scenarios F-H - model-resolved window and tiered data source (0.1.22)

Captured from `tests/test_first_real_vertical_slice.py`
(`ResolveHistoryWindowTests`, `HistoryTierSelectionTests`,
`TieredHistoryRetrievalTests`, `ModelResolvedWindowEndToEndTests`) with a fixed
`now = 2026-06-18T12:00:00+00:00` and `recorder_keep_days = 10`.

### Scenario F - window clamp/validate (ADR-0020)

```json
{
  "honored": {
    "model_resolved": true,
    "start": "2026-06-16T12:00:00+00:00",
    "end": "2026-06-18T12:00:00+00:00",
    "warnings": []
  },
  "future_end_clamped": {
    "model_resolved": true,
    "end": "2026-06-18T12:00:00+00:00",
    "warnings": ["history_window_end_clamped_to_now"]
  },
  "inverted_fallback": {
    "model_resolved": false,
    "start": "2026-06-17T12:00:00+00:00",
    "end": "2026-06-18T12:00:00+00:00",
    "warnings": ["history_window_not_increasing"]
  }
}
```

### Tier selection (ADR-0021)

```json
{
  "raw_12h": ["recorder_states", "raw", null, false],
  "hourly_5d": ["long_term_statistics", "hourly", "hour", false],
  "daily_90d": ["long_term_statistics", "daily", "day", true]
}
```

### Scenario G - seasonal window renders statistics with a band

```json
{
  "status": "complete",
  "image_url_suffix": "e-entry-artifact-001.png",
  "series_source": "long_term_statistics",
  "series_resolution": "daily",
  "first_point": {
    "ts": "2026-03-20T12:00:00+00:00",
    "value": 60.0,
    "value_min": 58.0,
    "value_max": 63.0,
    "raw_state": null,
    "quality": "ok"
  },
  "png_files_written": 1
}
```

### Scenario H - beyond retention without statistics fails closed

```json
{
  "status": "failed",
  "failure": {
    "stage": "approved_history_retrieval",
    "code": "no_long_term_statistics",
    "message": "No long-term statistics are available to chart this time range (sensor.upstairs_temperature). Statistics require an entity with a measurement state class."
  },
  "png_files_written": 0
}
```

## Scenarios I-L - categorical timeline render family (0.1.25, ADR-0022)

Proof: `tests/test_first_real_vertical_slice.py` classes
`InProcessTimelineRendererTests` and `RenderFamilyRoutingTests`, plus the
disambiguation tests in `FirstRealVerticalSliceTests`, and the eval
`evals/timeline_render_family_routing.py`. Focused run:

```
$ python -m pytest tests/test_first_real_vertical_slice.py \
    -k "Timeline or RenderFamily or substituted or hidden_provider"
10 passed, 32 deselected
```

### Scenario J - deterministic render-family routing (raw eval CASE)

```json
{
  "case_id": "deterministic_render_family_routing",
  "then": {
    "numeric": "time_series",
    "binary": "timeline",
    "categorical": "timeline",
    "mixed": "mixed",
    "time_series_chart_type": ["time_series"],
    "timeline_chart_type": ["timeline"],
    "timeline_render_as": ["step"]
  },
  "when": {"operation": "_resolve_render_family + load_planner_result_schema"}
}
```

A mixed numeric + binary prompt fails closed **before the planner is called**
(`planner.calls == 0`) with a card-facing snapshot:

```json
{
  "status": "failed",
  "failure": {"stage": "model_provider_planning", "code": "mixed_chart_composition_unsupported"},
  "png_files_written": 0
}
```

### Scenario I - binary entity renders an on/off timeline (raw eval CASE)

```json
{
  "case_id": "binary_timeline_render",
  "given": {"entity": "binary_sensor.kitchen_door", "kind": "binary_state"},
  "then": {
    "on_region_hours": [[6, 9], [14, 20]],
    "status": "success",
    "renderer": "in_process_pillow",
    "png_signature_ok": true,
    "series_plotted": ["kitchen_door"]
  },
  "when": {"operation": "render_in_process_chart(chart_type=timeline)"}
}
```

End-to-end (`test_binary_prompt_renders_timeline_png`): a `job/start` ->
`job/snapshot` for `binary_sensor.kitchen_door` returns a `complete` snapshot
whose `chart.image_url` is `/api/isolinear/artifacts/<id>.png`, exactly one PNG
is written, and its signature bytes are `89 50 4E 47 0D 0A 1A 0A`. The approved,
disclosed door sensor never produces a hidden/substituted-entity failure. The
rendered anchor PNG (two-lane binary + categorical) was eyes-on verified legible
at a 380px phone-card downscale.

### Scenario L - honest failure-code disambiguation

```json
{
  "unapproved_reference": {
    "failure": {"stage": "model_provider_planning", "code": "model_provider_referenced_unapproved_entity"},
    "note": "sensor.hidden_temperature is absent from the approved catalog"
  },
  "substituted_reference": {
    "failure": {"stage": "model_provider_planning", "code": "model_provider_substituted_entity"},
    "note": "sensor.basement_temperature is approved but was not disclosed for this job"
  }
}
```

Both fail before rendering or artifact storage
(`chart_rendering_called == false`, no PNG written). The model-provider planning
anchor verifier (`src/Isolinear/job_orchestration_model_provider_planning_anchor.py`)
and its recursive hidden-output cases now assert
`model_provider_referenced_unapproved_entity`.

### Scenario K - beyond-retention timeline

Proof: `test_beyond_retention_binary_timeline_fails_closed`. A `timeline` window
beyond recorder retention has no raw states and no long-term statistics for a
non-`state_class` binary entity, so it fails closed through the same
`no_long_term_statistics` history-retrieval gate as Scenario H (the gate stays
*after* planning per ADR-0020; routing does not move it):

```json
{
  "status": "failed",
  "failure": {"code": "no_long_term_statistics"},
  "png_files_written": 0
}
```

A dedicated `timeline_history_unavailable` code is a documented 0.1.26
refinement.

## Scenarios M-O - numeric + binary overlay composition (0.1.26, ADR-0022 D4/D5)

Proof: `tests/test_first_real_vertical_slice.py::InProcessOverlayRendererTests`
and the overlay tests in `RenderFamilyRoutingTests`
(`test_compose_binary_overlays_injects_shaded_intervals`,
`test_fuzzy_mixed_prompt_resolves_numeric_primary_plus_overlay`,
`test_explicit_mixed_prompt_renders_overlay_png`,
`test_two_numeric_plus_binary_fails_closed_with_mixed_code`), plus
`evals/timeline_render_family_routing.py`. Focused run:

```
$ python -m pytest tests/test_first_real_vertical_slice.py \
    -k "Overlay or overlay or fuzzy or two_numeric"
6 passed, 42 deselected
```

### Scenario M - numeric line + binary shaded overlay (raw eval CASE)

```json
{
  "case_id": "numeric_line_with_binary_overlay",
  "given": {"primary": "sensor.living_room_temperature", "overlay": "binary_sensor.ac"},
  "then": {
    "overlay_render_as": "shaded_intervals",
    "overlays_plotted": ["overlay-001"],
    "series_plotted": ["temp"],
    "png_signature_ok": true
  },
  "when": {"operation": "_compose_binary_overlays + render_in_process_chart(time_series)"}
}
```

End-to-end (`test_explicit_mixed_prompt_renders_overlay_png`): a prompt resolving
`sensor.upstairs_temperature` + `binary_sensor.kitchen_door` returns a `complete`
snapshot; the planner is disclosed **only** the numeric primary
(`approved_entity_ids == ["sensor.upstairs_temperature"]`); the stored render
plan's `chart_spec.overlays[0]` is a `shaded_intervals` overlay sourced from
`binary_sensor.kitchen_door`; exactly one PNG is written with a valid signature.
The rendered anchor PNG (temperature line with two amber AC-on bands shaded
behind it, the line dipping while the AC runs) was eyes-on verified legible at a
380px phone-card downscale.

### Scenario N - fuzzy mixed prompt resolves to the overlay composition

`select_prompt_entity_ids("show me the living room temperature and when the ac
was running", ...)` returns `accepted` with
`source: "numeric_with_overlay"` and entity IDs
`["sensor.living_room_temperature", "binary_sensor.living_room_ac"]` (numeric
primary first), instead of single-entity clarification.

### Scenario O - two numeric + a binary still fails closed

```json
{
  "status": "failed",
  "failure": {"stage": "model_provider_planning", "code": "mixed_chart_composition_unsupported"},
  "planner_calls": 0,
  "png_files_written": 0
}
```
