import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.job_state_scaffold_anchor import (  # noqa: E402
    verify_job_state_scaffold_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_job_state_scaffold_anchor(REPO_ROOT)

    assert_true(result["passed"], f"Job state scaffold anchor failed: {result['failures']!r}")

    print_case(
        "start_job_creates_deterministic_state",
        given={
            "run_timestamp": run_timestamp,
            "config_entry_id": "fake-config-entry",
            "schema": "docs/schemas/integration-job-snapshot.schema.json",
        },
        when={
            "operation": "dispatch_registered_start_job",
        },
        then={
            "start": result["start"],
        },
    )

    print_case(
        "existing_job_commands_update_latest_snapshot",
        given={
            "job_id": result["updates"]["snapshots"]["start"]["job_id"],
        },
        when={
            "operation": "dispatch_snapshot_retry_and_clarification",
        },
        then={
            "updates": result["updates"],
        },
    )

    print_case(
        "subscription_records_callback_event_shape",
        given={
            "job_id": result["subscription"]["snapshot"]["job_id"],
        },
        when={
            "operation": "dispatch_registered_subscribe_job",
        },
        then={
            "subscription": result["subscription"],
        },
    )

    print_case(
        "config_entries_cannot_read_each_others_jobs",
        given={
            "entry_ids": ["entry-a", "entry-b"],
        },
        when={
            "operation": "entry_b_requests_entry_a_job",
        },
        then={
            "isolation": result["isolation"],
        },
    )

    print_case(
        "unknown_jobs_fail_closed",
        given={
            "job_id": "missing-job",
            "commands": list(result["unknown"]["commands"]),
        },
        when={
            "operation": "dispatch_unknown_job_commands",
        },
        then={
            "unknown": result["unknown"],
        },
    )

    print_case(
        "unload_removes_config_entry_job_state",
        given={
            "entry_id": "fake-config-entry",
        },
        when={
            "operation": "async_unload_entry",
        },
        then={
            "unload": result["unload"],
        },
    )

    print_case(
        "malformed_snapshots_are_rejected_before_storage",
        given={
            "schema": "docs/schemas/integration-job-snapshot.schema.json",
            "malformed_snapshot": result["malformed"]["malformed_snapshot"],
        },
        when={
            "operation": "store_validated_job_snapshot",
        },
        then={
            "malformed": result["malformed"],
        },
    )

    print_case(
        "job_state_remains_non_orchestrating",
        given={
            "handled_surfaces": [
                "start",
                "snapshot",
                "retry",
                "clarification_answer",
                "subscribe",
                "unknown_job",
                "cross_config_entry_job",
            ],
        },
        when={
            "operation": "aggregate_observed_side_effects",
        },
        then={
            "side_effects": result["side_effects"],
        },
    )

    print("PASS home_assistant_job_state_scaffold")


if __name__ == "__main__":
    main()
