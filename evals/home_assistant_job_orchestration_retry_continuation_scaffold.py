import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.job_orchestration_retry_continuation_anchor import (  # noqa: E402
    verify_job_orchestration_retry_continuation_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_job_orchestration_retry_continuation_anchor(REPO_ROOT)

    assert_true(
        result["passed"],
        f"Retry continuation scaffold failed: {result['failures']!r}",
    )

    print_case(
        "accepted_retry_resumes_same_failed_job",
        given={
            "run_timestamp": run_timestamp,
            "config_entry_id": "retry-entry",
            "schema": "docs/schemas/integration-job-snapshot.schema.json",
        },
        when={
            "operation": "dispatch_registered_job_retry",
            "history_repaired_for_entity": "sensor.downstairs_temperature",
        },
        then={
            "accepted": result["accepted"],
        },
    )

    print_case(
        "unknown_job_fails_before_history",
        given={
            "job_id": "unknown-retry-entry-job-404",
        },
        when={
            "operation": "dispatch_registered_job_retry",
        },
        then={
            "unknown_job": result["unknown_job"],
        },
    )

    print_case(
        "non_retryable_job_fails_before_history",
        given={
            "latest_snapshot_status": "planning",
        },
        when={
            "operation": "dispatch_registered_job_retry",
        },
        then={
            "non_retryable": result["non_retryable"],
        },
    )

    print_case(
        "cross_config_entry_retry_rejected",
        given={
            "entry_ids": ["retry-entry-a", "retry-entry-b"],
        },
        when={
            "operation": "retry_entry_a_job_from_entry_b",
        },
        then={
            "cross_entry": result["cross_entry"],
        },
    )

    print_case(
        "valid_retries_stay_config_entry_scoped",
        given={
            "entry_ids": ["valid-retry-entry-a", "valid-retry-entry-b"],
        },
        when={
            "operation": "retry_each_entry_own_failed_job",
        },
        then={
            "isolation": result["isolation"],
        },
    )

    print_case(
        "retry_snapshots_validate_before_storage",
        given={
            "schema": "docs/schemas/integration-job-snapshot.schema.json",
        },
        when={
            "operation": "validate_observed_retry_snapshots",
        },
        then={
            "snapshot_validation": result["snapshot_validation"],
        },
    )

    print_case(
        "retry_continuation_remains_bounded",
        given={
            "handled_surfaces": [
                "accepted_retry",
                "unknown_job_failure",
                "non_retryable_failure",
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

    print("PASS home_assistant_job_orchestration_retry_continuation_scaffold")


if __name__ == "__main__":
    main()
