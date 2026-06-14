# Custom Card Anchor Evidence

Run timestamp: 2026-06-05T23:13:20+00:00

BDD file:
`bdd/dashboard-card/custom-card-anchor-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario: Dashboard loads the Isolinear custom card -> `CASE dashboard_loads_isolinear_custom_card`
- Scenario: User submits prompt and sees progress -> `CASE user_submits_prompt_and_sees_progress`
- Scenario: User answers clarification -> `CASE user_answers_clarification`
- Scenario: User views chart result -> `CASE user_views_chart_result`
- Scenario: User sees failure details -> `CASE user_sees_failure_details`
- Scenario: Card keeps orchestration inside the integration -> `CASE card_keeps_orchestration_inside_integration`

## Node-Backed Frontend Verification

Raw frontend build command:

```powershell
.\scripts\frontend.ps1 build
```

Raw frontend build output:

```text
Node: v24.16.0
npm: 11.13.0

> build
> tsc -p tsconfig.json --noEmit && vite build

vite v8.0.16 building client environment for production...
transforming...✓ 21 modules transformed.
rendering chunks...
computing gzip size...
dist/isolinear-card.js  32.31 kB │ gzip: 10.09 kB

✓ built in 76ms
```

Raw frontend test command:

```powershell
.\scripts\frontend.ps1 test
```

Raw frontend test output:

```text
Node: v24.16.0
npm: 11.13.0

> test
> vitest run


 RUN  v4.1.8 C:/Users/c.winslow/OneDrive - Kagwerks/Documents/Repos/Isolinear/frontend


 Test Files  1 passed (1)
      Tests  2 passed (2)
   Start at  16:13:26
   Duration  1.39s (transform 98ms, setup 0ms, import 143ms, tests 6ms, environment 0ms)
```

Raw frontend audit command:

```powershell
npm --prefix frontend audit
```

Raw frontend audit output:

```text
found 0 vulnerabilities
```

## Python Anchor Test Command

```powershell
.\scripts\test.ps1
```

Raw Python test output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 30 items

tests\test_dashboard_card_anchor.py .......                              [ 23%]
tests\test_fake_vertical_slice.py .......................                [100%]

============================= 30 passed in 0.89s ==============================
```

## BDD Eval Command

```powershell
.\.venv\Scripts\python.exe evals\dashboard_card_anchor.py
```

Raw eval output:

```text
CASE dashboard_card_anchor_files_and_fixtures
{
  "case_id": "dashboard_card_anchor_files_and_fixtures",
  "given": {
    "frontend_root": "frontend",
    "required_states": [
      "idle",
      "planning",
      "clarification_needed",
      "complete",
      "failed"
    ],
    "run_timestamp": "2026-06-05T23:13:20+00:00"
  },
  "then": {
    "fixture_job_snapshots": {
      "clarification_needed": {
        "clarification": {
          "message": "I found three upstairs temperature sensors. Should I average them and call that upstairs temperature?",
          "options": [
            {
              "can_remember": true,
              "description": "Use the approved upstairs temperature sensors as one series.",
              "label": "Average upstairs sensors",
              "option_id": "average_upstairs_temperature"
            }
          ],
          "question_id": "clarify_upstairs_temperature",
          "reason": "Multiple approved entities matched the prompt."
        },
        "job_id": "job-clarify-001",
        "prompt": "Show upstairs temperature for the last day",
        "snapshot_id": "fixture-clarification",
        "state_label": "Clarification needed",
        "status": "clarification_needed",
        "validation": {
          "status": "blocked",
          "summary": "Waiting for a clarification answer before validation."
        },
        "warnings": [
          "clarification_required"
        ]
      },
      "complete": {
        "aliases": [
          {
            "meaning": "sensor.upstairs_temperature",
            "name": "upstairs temperature"
          },
          {
            "meaning": "sensor.downstairs_temperature",
            "name": "downstairs temperature"
          }
        ],
        "chart": {
          "image_url": "../fixtures/fake-temperature-chart.svg",
          "overlays": [],
          "series": [
            {
              "entity_id": "sensor.upstairs_temperature",
              "label": "Upstairs Temperature",
              "series_id": "upstairs_temperature"
            },
            {
              "entity_id": "sensor.downstairs_temperature",
              "label": "Downstairs Temperature",
              "series_id": "downstairs_temperature"
            }
          ],
          "time_range": "Last 24 hours",
          "title": "Upstairs vs Downstairs Temperature"
        },
        "entities": [
          {
            "entity_id": "sensor.upstairs_temperature",
            "label": "Upstairs Temperature"
          },
          {
            "entity_id": "sensor.downstairs_temperature",
            "label": "Downstairs Temperature"
          }
        ],
        "job_id": "job-complete-001",
        "prompt": "Compare upstairs and downstairs temperatures",
        "snapshot_id": "fixture-complete",
        "state_label": "Complete",
        "status": "complete",
        "validation": {
          "checks": [
            {
              "name": "chart_spec_schema",
              "status": "pass"
            },
            {
              "name": "allowlisted_entities",
              "status": "pass"
            },
            {
              "name": "image_artifact",
              "status": "pass"
            }
          ],
          "status": "pass",
          "summary": "Chart spec, allowlist, image artifact, and render metadata passed."
        },
        "warnings": []
      },
      "failed": {
        "failure": {
          "code": "unsupported_chart_spec",
          "message": "The trusted renderer rejected an unsupported chart primitive.",
          "stage": "rendering"
        },
        "job_id": "job-failed-001",
        "prompt": "Render unsupported energy histogram",
        "retry_allowed": true,
        "snapshot_id": "fixture-failed",
        "state_label": "Failed",
        "status": "failed",
        "validation": {
          "status": "fail",
          "summary": "Rendering stopped before a chart image was produced."
        },
        "warnings": [
          "unsupported_chart_spec"
        ]
      },
      "idle": {
        "job_id": null,
        "message": "Ready for an approved Home Assistant history question.",
        "prompt": "",
        "snapshot_id": "fixture-idle",
        "state_label": "Idle",
        "status": "idle",
        "validation": {
          "status": "not_run",
          "summary": "Waiting for prompt."
        },
        "warnings": []
      },
      "planning": {
        "job_id": "job-planning-001",
        "progress": {
          "message": "Resolving approved entities and drafting a chart spec.",
          "stage": "planning"
        },
        "prompt": "Compare upstairs and downstairs temperatures",
        "snapshot_id": "fixture-planning",
        "state_label": "Planning",
        "status": "planning",
        "validation": {
          "status": "pending",
          "summary": "Plan validation has not completed."
        },
        "warnings": []
      }
    },
    "inventory": {
      "files": [
        {
          "bytes": 370,
          "exists": true,
          "path": "frontend/package.json"
        },
        {
          "bytes": 267,
          "exists": true,
          "path": "frontend/tsconfig.json"
        },
        {
          "bytes": 245,
          "exists": true,
          "path": "frontend/vite.config.ts"
        },
        {
          "bytes": 1765,
          "exists": true,
          "path": "frontend/src/types.ts"
        },
        {
          "bytes": 2266,
          "exists": true,
          "path": "frontend/src/isolinear-api.ts"
        },
        {
          "bytes": 12426,
          "exists": true,
          "path": "frontend/src/isolinear-card.ts"
        },
        {
          "bytes": 32313,
          "exists": true,
          "path": "frontend/dist/isolinear-card.js"
        },
        {
          "bytes": 4009,
          "exists": true,
          "path": "frontend/fixtures/job-snapshots.json"
        },
        {
          "bytes": 1667,
          "exists": true,
          "path": "frontend/fixtures/fake-temperature-chart.svg"
        },
        {
          "bytes": 1397,
          "exists": true,
          "path": "frontend/harness/fake-hass.js"
        },
        {
          "bytes": 2210,
          "exists": true,
          "path": "frontend/harness/index.html"
        }
      ]
    }
  },
  "when": {
    "operation": "verify_dashboard_card_anchor"
  }
}
PASS dashboard_card_anchor_files_and_fixtures
CASE dashboard_loads_isolinear_custom_card
{
  "case_id": "dashboard_loads_isolinear_custom_card",
  "given": {
    "config": {
      "config_entry_id": "fake-config-entry",
      "title": "Isolinear",
      "type": "custom:isolinear-card"
    },
    "module": "frontend/dist/isolinear-card.js"
  },
  "then": {
    "config_behavior": {
      "invalid_configs": [
        {
          "accepted": false,
          "config": null,
          "error": "Isolinear card config requires type custom:isolinear-card."
        },
        {
          "accepted": false,
          "config": {},
          "error": "Isolinear card config requires type custom:isolinear-card."
        },
        {
          "accepted": false,
          "config": {
            "config_entry_id": "fake-config-entry",
            "type": "custom:wrong-card"
          },
          "error": "Isolinear card config requires type custom:isolinear-card."
        },
        {
          "accepted": false,
          "config": {
            "config_entry_id": "",
            "type": "custom:isolinear-card"
          },
          "error": "Isolinear card config requires config_entry_id."
        }
      ],
      "valid_config": {
        "config_entry_id": "fake-config-entry",
        "density": "comfortable",
        "render_preference": "trusted",
        "title": "Isolinear",
        "type": "custom:isolinear-card"
      }
    },
    "idle_layout": {
      "fixture_status": "idle",
      "layout_marker": true,
      "prompt_input_marker": true,
      "submit_button_marker": true
    },
    "registration": {
      "card_picker_metadata": {
        "name": "Isolinear",
        "preview": true,
        "type": "isolinear-card",
        "window_custom_cards": true
      },
      "card_sizing_hooks": {
        "get_card_size": true,
        "get_grid_options": true
      },
      "configuration_surface": {
        "editor_defined": true,
        "get_config_element": true
      },
      "custom_element_defined": true,
      "editor_element_defined": true,
      "lit_source_custom_element": true
    }
  },
  "when": {
    "operation": "inspect_custom_element_registration_and_config_hooks"
  }
}
PASS dashboard_loads_isolinear_custom_card
CASE user_submits_prompt_and_sees_progress
{
  "case_id": "user_submits_prompt_and_sees_progress",
  "given": {
    "fake_hass": "frontend/harness/fake-hass.js",
    "snapshot": {
      "job_id": null,
      "message": "Ready for an approved Home Assistant history question.",
      "prompt": "",
      "snapshot_id": "fixture-idle",
      "state_label": "Idle",
      "status": "idle",
      "validation": {
        "status": "not_run",
        "summary": "Waiting for prompt."
      },
      "warnings": []
    }
  },
  "then": {
    "planning_layout": {
      "disabled_duplicate_submit_marker": true,
      "fixture_status": "planning",
      "job_state_marker": true
    },
    "recorded_message": {
      "config_entry_id": "fake-config-entry",
      "prompt": "Compare upstairs and downstairs temperatures",
      "type": "isolinear/v1/job/start",
      "version": 1
    },
    "submit_disabled_for_active_job": true
  },
  "when": {
    "operation": "submit_prompt",
    "prompt": "Compare upstairs and downstairs temperatures"
  }
}
PASS user_submits_prompt_and_sees_progress
CASE user_answers_clarification
{
  "case_id": "user_answers_clarification",
  "given": {
    "snapshot": {
      "clarification": {
        "message": "I found three upstairs temperature sensors. Should I average them and call that upstairs temperature?",
        "options": [
          {
            "can_remember": true,
            "description": "Use the approved upstairs temperature sensors as one series.",
            "label": "Average upstairs sensors",
            "option_id": "average_upstairs_temperature"
          }
        ],
        "question_id": "clarify_upstairs_temperature",
        "reason": "Multiple approved entities matched the prompt."
      },
      "job_id": "job-clarify-001",
      "prompt": "Show upstairs temperature for the last day",
      "snapshot_id": "fixture-clarification",
      "state_label": "Clarification needed",
      "status": "clarification_needed",
      "validation": {
        "status": "blocked",
        "summary": "Waiting for a clarification answer before validation."
      },
      "warnings": [
        "clarification_required"
      ]
    }
  },
  "then": {
    "browser_local_state_matches": [],
    "clarification_layout": {
      "fixture_status": "clarification_needed",
      "panel_marker": true,
      "use_and_remember_marker": true,
      "use_once_marker": true
    },
    "use_and_remember_message": {
      "config_entry_id": "fake-config-entry",
      "job_id": "job-clarify-001",
      "option_id": "average_upstairs_temperature",
      "question_id": "clarify_upstairs_temperature",
      "remember": true,
      "type": "isolinear/v1/clarification/answer",
      "version": 1
    },
    "use_once_message": {
      "config_entry_id": "fake-config-entry",
      "job_id": "job-clarify-001",
      "option_id": "average_upstairs_temperature",
      "question_id": "clarify_upstairs_temperature",
      "remember": false,
      "type": "isolinear/v1/clarification/answer",
      "version": 1
    }
  },
  "when": {
    "operation": "choose_use_once_and_use_and_remember"
  }
}
PASS user_answers_clarification
CASE user_views_chart_result
{
  "case_id": "user_views_chart_result",
  "given": {
    "snapshot": {
      "aliases": [
        {
          "meaning": "sensor.upstairs_temperature",
          "name": "upstairs temperature"
        },
        {
          "meaning": "sensor.downstairs_temperature",
          "name": "downstairs temperature"
        }
      ],
      "chart": {
        "image_url": "../fixtures/fake-temperature-chart.svg",
        "overlays": [],
        "series": [
          {
            "entity_id": "sensor.upstairs_temperature",
            "label": "Upstairs Temperature",
            "series_id": "upstairs_temperature"
          },
          {
            "entity_id": "sensor.downstairs_temperature",
            "label": "Downstairs Temperature",
            "series_id": "downstairs_temperature"
          }
        ],
        "time_range": "Last 24 hours",
        "title": "Upstairs vs Downstairs Temperature"
      },
      "entities": [
        {
          "entity_id": "sensor.upstairs_temperature",
          "label": "Upstairs Temperature"
        },
        {
          "entity_id": "sensor.downstairs_temperature",
          "label": "Downstairs Temperature"
        }
      ],
      "job_id": "job-complete-001",
      "prompt": "Compare upstairs and downstairs temperatures",
      "snapshot_id": "fixture-complete",
      "state_label": "Complete",
      "status": "complete",
      "validation": {
        "checks": [
          {
            "name": "chart_spec_schema",
            "status": "pass"
          },
          {
            "name": "allowlisted_entities",
            "status": "pass"
          },
          {
            "name": "image_artifact",
            "status": "pass"
          }
        ],
        "status": "pass",
        "summary": "Chart spec, allowlist, image artifact, and render metadata passed."
      },
      "warnings": []
    }
  },
  "then": {
    "aliases": [
      {
        "meaning": "sensor.upstairs_temperature",
        "name": "upstairs temperature"
      },
      {
        "meaning": "sensor.downstairs_temperature",
        "name": "downstairs temperature"
      }
    ],
    "chart_title": "Upstairs vs Downstairs Temperature",
    "complete_layout": {
      "bottom_composer_marker": true,
      "chart_dominant_rows": true,
      "chart_image_marker": true,
      "compact_complete_composer_rows": true,
      "fixture_status": "complete",
      "layout_marker": true
    },
    "entities": [
      {
        "entity_id": "sensor.upstairs_temperature",
        "label": "Upstairs Temperature"
      },
      {
        "entity_id": "sensor.downstairs_temperature",
        "label": "Downstairs Temperature"
      }
    ],
    "validation": {
      "checks": [
        {
          "name": "chart_spec_schema",
          "status": "pass"
        },
        {
          "name": "allowlisted_entities",
          "status": "pass"
        },
        {
          "name": "image_artifact",
          "status": "pass"
        }
      ],
      "status": "pass",
      "summary": "Chart spec, allowlist, image artifact, and render metadata passed."
    }
  },
  "when": {
    "operation": "render_complete_snapshot"
  }
}
PASS user_views_chart_result
CASE user_sees_failure_details
{
  "case_id": "user_sees_failure_details",
  "given": {
    "snapshot": {
      "failure": {
        "code": "unsupported_chart_spec",
        "message": "The trusted renderer rejected an unsupported chart primitive.",
        "stage": "rendering"
      },
      "job_id": "job-failed-001",
      "prompt": "Render unsupported energy histogram",
      "retry_allowed": true,
      "snapshot_id": "fixture-failed",
      "state_label": "Failed",
      "status": "failed",
      "validation": {
        "status": "fail",
        "summary": "Rendering stopped before a chart image was produced."
      },
      "warnings": [
        "unsupported_chart_spec"
      ]
    }
  },
  "then": {
    "failed_layout": {
      "failure_marker": true,
      "fixture_status": "failed",
      "retry_marker": true,
      "revise_marker": true
    },
    "failure": {
      "code": "unsupported_chart_spec",
      "message": "The trusted renderer rejected an unsupported chart primitive.",
      "stage": "rendering"
    },
    "retry_message": {
      "config_entry_id": "fake-config-entry",
      "job_id": "job-failed-001",
      "type": "isolinear/v1/job/retry",
      "version": 1
    }
  },
  "when": {
    "operation": "render_failed_snapshot"
  }
}
PASS user_sees_failure_details
CASE card_keeps_orchestration_inside_integration
{
  "case_id": "card_keeps_orchestration_inside_integration",
  "given": {
    "scanned_files": [
      "frontend/src/types.ts",
      "frontend/src/isolinear-api.ts",
      "frontend/src/isolinear-card.ts",
      "frontend/dist/isolinear-card.js"
    ]
  },
  "then": {
    "adapter": {
      "all_commands_versioned": true,
      "card_uses_send_message_promise": true,
      "command_markers_present": {
        "isolinear/v1/clarification/answer": true,
        "isolinear/v1/job/retry": true,
        "isolinear/v1/job/start": true
      },
      "fake_hass_records_calls": true,
      "recorded_messages": [
        {
          "config_entry_id": "fake-config-entry",
          "prompt": "Compare upstairs and downstairs temperatures",
          "type": "isolinear/v1/job/start",
          "version": 1
        },
        {
          "config_entry_id": "fake-config-entry",
          "job_id": "job-clarify-001",
          "option_id": "average_upstairs_temperature",
          "question_id": "clarify_upstairs_temperature",
          "remember": false,
          "type": "isolinear/v1/clarification/answer",
          "version": 1
        },
        {
          "config_entry_id": "fake-config-entry",
          "job_id": "job-clarify-001",
          "option_id": "average_upstairs_temperature",
          "question_id": "clarify_upstairs_temperature",
          "remember": true,
          "type": "isolinear/v1/clarification/answer",
          "version": 1
        },
        {
          "config_entry_id": "fake-config-entry",
          "job_id": "job-failed-001",
          "type": "isolinear/v1/job/retry",
          "version": 1
        }
      ]
    },
    "boundary": {
      "matches": [],
      "passed": true,
      "scanned_files": [
        "frontend/src/types.ts",
        "frontend/src/isolinear-api.ts",
        "frontend/src/isolinear-card.ts",
        "frontend/dist/isolinear-card.js"
      ]
    }
  },
  "when": {
    "operation": "static_boundary_scan"
  }
}
PASS card_keeps_orchestration_inside_integration
PASS dashboard_card_anchor
```
