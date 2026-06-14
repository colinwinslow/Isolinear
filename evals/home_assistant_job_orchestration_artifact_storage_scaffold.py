import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.job_orchestration_artifact_storage_anchor import (  # noqa: E402
    verify_job_orchestration_artifact_storage_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_job_orchestration_artifact_storage_anchor(REPO_ROOT)

    assert_true(
        result["passed"],
        f"Artifact storage scaffold failed: {result['failures']!r}",
    )

    print_case(
        "scaffold_ready_snapshot_records_placeholder_artifact",
        given={
            "run_timestamp": run_timestamp,
            "config_entry_id": "artifact-entry",
            "snapshot_schema": "docs/schemas/integration-job-snapshot.schema.json",
            "artifact_schema": "docs/schemas/integration-artifact-metadata.schema.json",
        },
        when={
            "operation": "dispatch_registered_job_snapshot_after_scaffold_ready",
        },
        then={
            "accepted": result["accepted"],
        },
    )

    print_case(
        "repeated_snapshot_requests_reuse_artifact",
        given={
            "config_entry_id": "artifact-idempotent-entry",
        },
        when={
            "operation": "dispatch_registered_job_snapshot_twice",
        },
        then={
            "idempotent": result["idempotent"],
        },
    )

    print_case(
        "unknown_job_fails_before_artifact_storage",
        given={
            "job_id": "unknown-artifact-entry-job-404",
        },
        when={
            "operation": "dispatch_registered_job_snapshot",
        },
        then={
            "unknown_job": result["unknown_job"],
        },
    )

    print_case(
        "cross_config_entry_artifact_rejected",
        given={
            "entry_ids": ["artifact-entry-a", "artifact-entry-b"],
        },
        when={
            "operation": "snapshot_entry_a_job_from_entry_b",
        },
        then={
            "cross_entry": result["cross_entry"],
        },
    )

    print_case(
        "valid_artifacts_stay_config_entry_scoped",
        given={
            "entry_ids": ["valid-artifact-entry-a", "valid-artifact-entry-b"],
        },
        when={
            "operation": "snapshot_each_entry_own_job",
        },
        then={
            "isolation": result["isolation"],
        },
    )

    print_case(
        "artifact_metadata_and_snapshots_validate_before_storage",
        given={
            "snapshot_schema": "docs/schemas/integration-job-snapshot.schema.json",
            "artifact_schema": "docs/schemas/integration-artifact-metadata.schema.json",
        },
        when={
            "operation": "validate_observed_artifact_metadata_and_snapshots",
        },
        then={
            "validation": result["validation"],
        },
    )

    print_case(
        "artifact_storage_remains_bounded",
        given={
            "handled_surfaces": [
                "accepted_artifact_snapshot",
                "idempotent_snapshot",
                "unknown_job_failure",
                "cross_config_entry_failure",
                "config_entry_isolation",
            ],
        },
        when={
            "operation": "aggregate_observed_side_effects",
        },
        then={
            "side_effects": result["side_effects"],
        },
    )

    print("PASS home_assistant_job_orchestration_artifact_storage_scaffold")


if __name__ == "__main__":
    main()
