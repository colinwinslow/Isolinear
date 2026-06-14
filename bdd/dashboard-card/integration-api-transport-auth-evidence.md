# Integration API Transport/Auth Evidence

Run timestamp: 2026-06-06T00:01:50+00:00

BDD file:
`bdd/dashboard-card/integration-api-transport-auth-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: card commands are versioned integration commands -> `CASE integration_ws_commands_are_versioned`
- Scenario B: worker render request uses integration-owned auth -> `CASE worker_render_request_uses_integration_owned_auth`
- Scenario C: bad worker credentials fail closed -> `CASE worker_rejects_bad_auth_or_version_before_rendering`
- Scenario D: unsupported worker version fails closed -> `CASE worker_rejects_bad_auth_or_version_before_rendering`
- Scenario E: secrets are not exposed across boundaries -> `CASE card_does_not_receive_worker_boundary_material`

## Focused Unit Verification

Raw command:

```powershell
.\scripts\test.ps1 tests/test_transport_auth_anchor.py
```

Raw output:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.5, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\c.winslow\OneDrive - Kagwerks\Documents\Repos\Isolinear
collected 5 items

tests\test_transport_auth_anchor.py .....                                [100%]

============================== 5 passed in 0.14s ==============================
```

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\integration_api_transport_auth.py
```

Raw output:

```text
CASE integration_ws_commands_are_versioned
{
  "case_id": "integration_ws_commands_are_versioned",
  "given": {
    "config_entry_id": "fake-config-entry",
    "run_timestamp": "2026-06-06T00:01:50+00:00",
    "schema": "docs/schemas/integration-ws-command.schema.json"
  },
  "then": {
    "command_results": {
      "answer_clarification": {
        "accepted": true,
        "code": "accepted",
        "render_attempted": false,
        "type": "isolinear/v1/clarification/answer",
        "version": 1
      },
      "get_snapshot": {
        "accepted": true,
        "code": "accepted",
        "render_attempted": false,
        "type": "isolinear/v1/job/snapshot",
        "version": 1
      },
      "retry_job": {
        "accepted": true,
        "code": "accepted",
        "render_attempted": false,
        "type": "isolinear/v1/job/retry",
        "version": 1
      },
      "start_job": {
        "accepted": true,
        "code": "accepted",
        "render_attempted": false,
        "type": "isolinear/v1/job/start",
        "version": 1
      },
      "subscribe_job": {
        "accepted": true,
        "code": "accepted",
        "render_attempted": false,
        "type": "isolinear/v1/job/subscribe",
        "version": 1
      }
    },
    "commands": {
      "answer_clarification": {
        "config_entry_id": "fake-config-entry",
        "job_id": "job-clarify-001",
        "option_id": "average_upstairs_temperature",
        "question_id": "clarify_upstairs_temperature",
        "remember": false,
        "type": "isolinear/v1/clarification/answer",
        "version": 1
      },
      "get_snapshot": {
        "config_entry_id": "fake-config-entry",
        "job_id": "job-complete-001",
        "type": "isolinear/v1/job/snapshot",
        "version": 1
      },
      "retry_job": {
        "config_entry_id": "fake-config-entry",
        "job_id": "job-failed-001",
        "type": "isolinear/v1/job/retry",
        "version": 1
      },
      "start_job": {
        "config_entry_id": "fake-config-entry",
        "prompt": "Compare upstairs and downstairs temperatures",
        "type": "isolinear/v1/job/start",
        "version": 1
      },
      "subscribe_job": {
        "config_entry_id": "fake-config-entry",
        "job_id": "job-complete-001",
        "type": "isolinear/v1/job/subscribe",
        "version": 1
      }
    },
    "snapshot_results": {
      "clarification_needed": {
        "accepted": true,
        "code": "accepted",
        "status": "clarification_needed"
      },
      "complete": {
        "accepted": true,
        "code": "accepted",
        "status": "complete"
      },
      "failed": {
        "accepted": true,
        "code": "accepted",
        "status": "failed"
      },
      "idle": {
        "accepted": true,
        "code": "accepted",
        "status": "idle"
      },
      "planning": {
        "accepted": true,
        "code": "accepted",
        "status": "planning"
      }
    }
  },
  "when": {
    "operation": "validate_start_answer_retry_snapshot_and_subscribe_commands"
  }
}
PASS integration_ws_commands_are_versioned
CASE worker_render_request_uses_integration_owned_auth
{
  "case_id": "worker_render_request_uses_integration_owned_auth",
  "given": {
    "nested_schema": "docs/schemas/render-request.schema.json",
    "schema": "docs/schemas/worker-transport-request.schema.json",
    "worker_path": "/v1/render"
  },
  "then": {
    "evidence_redaction": {
      "home_assistant_token_redacted": true,
      "worker_token_redacted": true
    },
    "redacted_worker_request": {
      "body": {
        "operation": "render_chart",
        "render_request": {
          "chart_spec": {
            "chart_id": "upstairs_downstairs_temperature",
            "chart_type": "time_series",
            "notes": [],
            "overlays": [],
            "series": [
              {
                "label": "Upstairs Temperature",
                "render_as": "line",
                "role": "primary",
                "series_id": "upstairs_temperature",
                "source": {
                  "entity_id": "sensor.upstairs_temperature",
                  "type": "entity"
                },
                "unit": "degF"
              }
            ],
            "time_range": {
              "duration": "24h",
              "type": "relative"
            },
            "title": "Upstairs vs Downstairs Temperature"
          },
          "codegen": null,
          "derived_intervals": [],
          "history_series": [
            {
              "entity_id": "sensor.upstairs_temperature",
              "kind": "numeric",
              "label": "Upstairs Temperature",
              "points": [
                {
                  "quality": "ok",
                  "raw_state": "71.2",
                  "ts": "2026-06-05T08:00:00Z",
                  "value": 71.2
                },
                {
                  "quality": "ok",
                  "raw_state": "71.8",
                  "ts": "2026-06-05T09:00:00Z",
                  "value": 71.8
                }
              ],
              "series_id": "upstairs_temperature",
              "source_entity_ids": [
                "sensor.upstairs_temperature"
              ],
              "unit": "degF",
              "warnings": []
            }
          ],
          "output": {
            "format": "png",
            "height": 800,
            "width": 1400
          },
          "render_mode": "safe",
          "request_id": "render-transport-001",
          "theme": {
            "mode": "light"
          }
        },
        "request_id": "transport-envelope-001",
        "version": 1
      },
      "headers": {
        "authorization": "Bearer <redacted>",
        "content_type": "application/json",
        "x_isolinear_worker_api_version": "1"
      },
      "method": "POST",
      "path": "/v1/render",
      "protocol_version": 1
    },
    "valid_worker_result": {
      "accepted": true,
      "authorization": "Bearer <redacted>",
      "code": "accepted",
      "operation": "render_chart",
      "path": "/v1/render",
      "render_attempted": true,
      "render_request_id": "render-transport-001"
    }
  },
  "when": {
    "operation": "validate_worker_transport_request"
  }
}
PASS worker_render_request_uses_integration_owned_auth
CASE worker_rejects_bad_auth_or_version_before_rendering
{
  "case_id": "worker_rejects_bad_auth_or_version_before_rendering",
  "given": {
    "invalid_examples": [
      "missing_auth",
      "bad_token",
      "wrong_version",
      "leaked_home_assistant_token"
    ]
  },
  "then": {
    "rejection_results": {
      "bad_token": {
        "accepted": false,
        "code": "unauthorized_worker_request",
        "render_attempted": false
      },
      "leaked_home_assistant_token": {
        "accepted": false,
        "authorization": "Bearer <redacted>",
        "code": "forbidden_worker_boundary_content",
        "forbidden_matches": [
          {
            "path": "$.body.render_request.theme.home_assistant_token",
            "reason": "forbidden_key"
          }
        ],
        "render_attempted": false
      },
      "missing_auth": {
        "accepted": false,
        "code": "missing_worker_authorization",
        "render_attempted": false
      },
      "wrong_version": {
        "accepted": false,
        "code": "unsupported_worker_api_version",
        "render_attempted": false
      }
    }
  },
  "when": {
    "operation": "validate_invalid_worker_transport_requests"
  }
}
PASS worker_rejects_bad_auth_or_version_before_rendering
CASE card_does_not_receive_worker_boundary_material
{
  "case_id": "card_does_not_receive_worker_boundary_material",
  "given": {
    "forbidden_boundary_material": [
      "worker_url",
      "worker_token",
      "model_endpoint",
      "entity_allowlist",
      "raw_history",
      "semantic_memory",
      "generated_code"
    ]
  },
  "then": {
    "evidence_redaction": {
      "home_assistant_token_redacted": true,
      "worker_token_redacted": true
    },
    "invalid_card_command_result": {
      "accepted": false,
      "code": "forbidden_card_boundary_content",
      "forbidden_matches": [
        {
          "path": "$.worker_url",
          "reason": "forbidden_key"
        }
      ],
      "render_attempted": false
    }
  },
  "when": {
    "operation": "validate_leaky_card_command"
  }
}
PASS card_does_not_receive_worker_boundary_material
PASS integration_api_transport_auth
```
