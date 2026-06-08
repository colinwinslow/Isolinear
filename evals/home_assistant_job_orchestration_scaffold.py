import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.job_orchestration_scaffold_anchor import (  # noqa: E402
    verify_job_orchestration_scaffold_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_job_orchestration_scaffold_anchor(REPO_ROOT)

    assert_true(result["passed"], f"Job orchestration scaffold failed: {result['failures']!r}")

    print_case(
        "start_job_composes_catalog_history_and_job_state",
        given={
            "run_timestamp": run_timestamp,
            "config_entry_id": "orchestration-entry",
            "schema": "docs/schemas/integration-job-snapshot.schema.json",
        },
        when={
            "operation": "dispatch_registered_start_job",
        },
        then={
            "success": result["success"],
        },
    )

    print_case(
        "non_catalog_prompt_entities_fail_before_history",
        given={
            "prompt_entity_id": "light.kitchen",
        },
        when={
            "operation": "dispatch_registered_start_job",
        },
        then={
            "non_catalog": result["non_catalog"],
        },
    )

    print_case(
        "missing_approved_history_returns_failed_snapshot",
        given={
            "missing_entity_id": "sensor.downstairs_temperature",
        },
        when={
            "operation": "dispatch_registered_start_job",
        },
        then={
            "missing_history": result["missing_history"],
        },
    )

    print_case(
        "config_entries_keep_orchestration_scoped",
        given={
            "entry_ids": ["orch-entry-a", "orch-entry-b"],
        },
        when={
            "operation": "dispatch_start_job_for_each_entry",
        },
        then={
            "isolation": result["isolation"],
        },
    )

    print_case(
        "ambiguous_prompt_requests_clarification",
        given={
            "approved_entity_ids": [
                "sensor.upstairs_temperature",
                "sensor.downstairs_temperature",
            ],
            "prompt": "Show thermostat history",
        },
        when={
            "operation": "dispatch_registered_start_job",
        },
        then={
            "ambiguous": result["ambiguous"],
        },
    )

    print_case(
        "setup_entry_stores_orchestration_state",
        given={
            "entry_id": "setup-orchestration-entry",
        },
        when={
            "operation": "async_setup_entry",
        },
        then={
            "setup": result["setup"],
        },
    )

    print_case(
        "job_orchestration_scaffold_remains_bounded",
        given={
            "handled_surfaces": [
                "successful_start",
                "non_catalog_failure",
                "missing_history_failure",
                "ambiguous_prompt_clarification",
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

    print_case(
        "orchestration_snapshots_validate_before_storage",
        given={
            "schema": "docs/schemas/integration-job-snapshot.schema.json",
        },
        when={
            "operation": "validate_observed_orchestration_snapshots",
        },
        then={
            "snapshot_validation": result["snapshot_validation"],
        },
    )

    print("PASS home_assistant_job_orchestration_scaffold")


if __name__ == "__main__":
    main()
