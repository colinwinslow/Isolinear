# Home Assistant Job Orchestration Artifact Storage Scaffold Evidence

Run timestamp: 2026-06-08T22:39:28+00:00

BDD file:
`bdd/integration/home-assistant-job-orchestration-artifact-storage-scaffold-bdd.md`

Overall result: PASS

## Scenario Mapping

- Scenario A: scaffold-ready snapshot records placeholder artifact -> `CASE scaffold_ready_snapshot_records_placeholder_artifact`
- Scenario B: repeated snapshot requests reuse the artifact -> `CASE repeated_snapshot_requests_reuse_artifact`
- Scenario C: unknown job fails before artifact side effects -> `CASE unknown_job_fails_before_artifact_storage`
- Scenario D: config entries cannot retrieve each other's artifacts -> `CASE cross_config_entry_artifact_rejected`
- Scenario E: valid artifacts stay config-entry scoped -> `CASE valid_artifacts_stay_config_entry_scoped`
- Scenario F: artifact metadata and snapshots validate before storage -> `CASE artifact_metadata_and_snapshots_validate_before_storage`
- Scenario G: artifact storage scaffold remains bounded -> `CASE artifact_storage_remains_bounded`

## Eval Verification

Raw command:

```powershell
.\.venv\Scripts\python.exe evals\home_assistant_job_orchestration_artifact_storage_scaffold.py
```

Raw output:

```text
CASE scaffold_ready_snapshot_records_placeholder_artifact
{
  "case_id": "scaffold_ready_snapshot_records_placeholder_artifact",
  "given": {
    "artifact_schema": "docs/schemas/integration-artifact-metadata.schema.json",
    "config_entry_id": "artifact-entry",
    "run_timestamp": "2026-06-08T22:39:28+00:00",
    "snapshot_schema": "docs/schemas/integration-job-snapshot.schema.json"
  },
  "when": {
    "operation": "dispatch_registered_job_snapshot_after_scaffold_ready"
  },
  "then": {
    "accepted": {
      "artifact_snapshot": {
        "job_id": "artifact-entry-job-001",
        "snapshot_id": "artifact-entry-job-001-snapshot-004",
        "status": "complete",
        "progress": {
          "stage": "job_orchestration_artifact_storage_ready"
        },
        "chart": {
          "image_url": "/api/isolinear/artifacts/artifact-entry-artifact-001.png",
          "series": [
            {
              "entity_id": "sensor.upstairs_temperature",
              "label": "Upstairs Temperature",
              "series_id": "series-001"
            }
          ],
          "title": "Upstairs Temperature Chart"
        }
      },
      "artifact": {
        "artifact_id": "artifact-entry-artifact-001",
        "config_entry_id": "artifact-entry",
        "job_id": "artifact-entry-job-001",
        "source_snapshot_id": "artifact-entry-job-001-snapshot-003",
        "status": "placeholder",
        "render_metadata": {
          "renderer": "artifact_storage_scaffold",
          "render_attempted": false,
          "worker_called": false,
          "chart_rendering_called": false
        }
      },
      "orchestration_store": {
        "artifact_count": 1,
        "artifact_ids": [
          "artifact-entry-artifact-001"
        ],
        "latest_artifact_source_snapshot_id": "artifact-entry-job-001-snapshot-003"
      },
      "snapshot_validation": {
        "accepted": true,
        "snapshot_id": "artifact-entry-job-001-snapshot-004",
        "status": "complete"
      },
      "artifact_validation": [
        {
          "accepted": true,
          "artifact_id": "artifact-entry-artifact-001",
          "status": "placeholder"
        }
      ],
      "snapshot_dispatch": {
        "accepted": true,
        "orchestration": {
          "artifact_metadata_bookkeeping_written": true,
          "job_state_scaffold_written": true,
          "job_orchestration_scaffold_written": true,
          "worker_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false
        }
      }
    }
  }
}
PASS scaffold_ready_snapshot_records_placeholder_artifact

CASE repeated_snapshot_requests_reuse_artifact
{
  "case_id": "repeated_snapshot_requests_reuse_artifact",
  "given": {
    "config_entry_id": "artifact-idempotent-entry"
  },
  "when": {
    "operation": "dispatch_registered_job_snapshot_twice"
  },
  "then": {
    "idempotent": {
      "artifact_count": 1,
      "complete_snapshot_count": 1,
      "same_snapshot_returned": true,
      "first_snapshot": {
        "snapshot_id": "artifact-idempotent-entry-job-001-snapshot-004",
        "status": "complete"
      },
      "second_snapshot": {
        "snapshot_id": "artifact-idempotent-entry-job-001-snapshot-004",
        "status": "complete"
      },
      "artifacts": [
        {
          "artifact_id": "artifact-idempotent-entry-artifact-001",
          "job_id": "artifact-idempotent-entry-job-001",
          "source_snapshot_id": "artifact-idempotent-entry-job-001-snapshot-003"
        }
      ]
    }
  }
}
PASS repeated_snapshot_requests_reuse_artifact

CASE unknown_job_fails_before_artifact_storage
{
  "case_id": "unknown_job_fails_before_artifact_storage",
  "given": {
    "job_id": "unknown-artifact-entry-job-404"
  },
  "when": {
    "operation": "dispatch_registered_job_snapshot"
  },
  "then": {
    "unknown_job": {
      "error_codes": [
        "unknown_job"
      ],
      "artifacts": [],
      "job_store": {
        "job_ids": []
      },
      "snapshot": {
        "accepted": false,
        "orchestration": {
          "artifact_metadata_bookkeeping_written": false,
          "job_state_scaffold_written": false,
          "worker_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false
        }
      }
    }
  }
}
PASS unknown_job_fails_before_artifact_storage

CASE cross_config_entry_artifact_rejected
{
  "case_id": "cross_config_entry_artifact_rejected",
  "given": {
    "entry_ids": [
      "artifact-entry-a",
      "artifact-entry-b"
    ]
  },
  "when": {
    "operation": "snapshot_entry_a_job_from_entry_b"
  },
  "then": {
    "cross_entry": {
      "error_codes": [
        "unknown_job"
      ],
      "entry_a_artifacts": [],
      "entry_b_artifacts": [],
      "entry_b_complete_snapshots": [],
      "cross_snapshot": {
        "accepted": false,
        "orchestration": {
          "artifact_metadata_bookkeeping_written": false,
          "job_state_scaffold_written": false,
          "worker_called": false,
          "chart_artifact_written": false,
          "chart_rendering_called": false
        }
      }
    }
  }
}
PASS cross_config_entry_artifact_rejected

CASE valid_artifacts_stay_config_entry_scoped
{
  "case_id": "valid_artifacts_stay_config_entry_scoped",
  "given": {
    "entry_ids": [
      "valid-artifact-entry-a",
      "valid-artifact-entry-b"
    ]
  },
  "when": {
    "operation": "snapshot_each_entry_own_job"
  },
  "then": {
    "isolation": {
      "entry_a": {
        "artifact_snapshot": {
          "job_id": "valid-artifact-entry-a-job-001",
          "snapshot_id": "valid-artifact-entry-a-job-001-snapshot-004",
          "status": "complete"
        },
        "artifacts": [
          {
            "artifact_id": "valid-artifact-entry-a-artifact-001",
            "job_id": "valid-artifact-entry-a-job-001",
            "series": [
              {
                "entity_id": "sensor.upstairs_temperature"
              }
            ]
          }
        ]
      },
      "entry_b": {
        "artifact_snapshot": {
          "job_id": "valid-artifact-entry-b-job-001",
          "snapshot_id": "valid-artifact-entry-b-job-001-snapshot-004",
          "status": "complete"
        },
        "artifacts": [
          {
            "artifact_id": "valid-artifact-entry-b-artifact-001",
            "job_id": "valid-artifact-entry-b-job-001",
            "series": [
              {
                "entity_id": "binary_sensor.office_window"
              }
            ]
          }
        ]
      }
    }
  }
}
PASS valid_artifacts_stay_config_entry_scoped

CASE artifact_metadata_and_snapshots_validate_before_storage
{
  "case_id": "artifact_metadata_and_snapshots_validate_before_storage",
  "given": {
    "artifact_schema": "docs/schemas/integration-artifact-metadata.schema.json",
    "snapshot_schema": "docs/schemas/integration-job-snapshot.schema.json"
  },
  "when": {
    "operation": "validate_observed_artifact_metadata_and_snapshots"
  },
  "then": {
    "validation": {
      "accepted": {
        "returned_snapshot_valid": true,
        "stored_snapshots_valid": true,
        "artifact_metadata_valid": true
      },
      "idempotent": {
        "returned_snapshot_valid": true,
        "artifact_metadata_valid": true
      },
      "isolation_entry_a": {
        "returned_snapshot_valid": true,
        "artifact_metadata_valid": true
      },
      "isolation_entry_b": {
        "returned_snapshot_valid": true,
        "artifact_metadata_valid": true
      }
    }
  }
}
PASS artifact_metadata_and_snapshots_validate_before_storage

CASE artifact_storage_remains_bounded
{
  "case_id": "artifact_storage_remains_bounded",
  "given": {
    "handled_surfaces": [
      "accepted_artifact_snapshot",
      "idempotent_snapshot",
      "unknown_job_failure",
      "cross_config_entry_failure",
      "config_entry_isolation"
    ]
  },
  "when": {
    "operation": "aggregate_observed_side_effects"
  },
  "then": {
    "side_effects": {
      "allowed_aggregate": {
        "artifact_metadata_bookkeeping_written": true,
        "job_orchestration_scaffold_written": true,
        "job_state_scaffold_written": true,
        "websocket_command_registered": true
      },
      "forbidden_aggregate": {
          "chart_artifact_written": false,
          "chart_rendering_called": false,
          "durable_storage_written": false,
          "home_assistant_history_called": false,
          "home_assistant_history_read": false,
          "history_retrieval_scaffold_written": false,
          "home_assistant_service_or_state_mutation_called": false,
          "job_orchestration_called": false,
          "model_provider_called": false,
          "retry_behavior_called": false,
          "semantic_memory_called": false,
          "subscription_bookkeeping_written": false,
          "subscription_progress_streaming_called": false,
          "token_generated": false,
          "worker_called": false
      }
    }
  }
}
PASS artifact_storage_remains_bounded
PASS home_assistant_job_orchestration_artifact_storage_scaffold
```
