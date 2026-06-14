import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.job_orchestration_subscription_progress_anchor import (  # noqa: E402
    verify_job_orchestration_subscription_progress_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_job_orchestration_subscription_progress_anchor(REPO_ROOT)

    assert_true(
        result["passed"],
        f"Subscription/progress scaffold failed: {result['failures']!r}",
    )

    print_case(
        "accepted_subscribe_records_latest_progress_event",
        given={
            "run_timestamp": run_timestamp,
            "config_entry_id": "subscription-entry",
            "schema": "docs/schemas/integration-job-snapshot.schema.json",
        },
        when={
            "operation": "dispatch_registered_job_subscribe",
        },
        then={
            "accepted": result["accepted"],
        },
    )

    print_case(
        "unknown_job_fails_before_subscription_storage",
        given={
            "job_id": "unknown-subscription-entry-job-404",
        },
        when={
            "operation": "dispatch_registered_job_subscribe",
        },
        then={
            "unknown_job": result["unknown_job"],
        },
    )

    print_case(
        "cross_config_entry_subscription_rejected",
        given={
            "entry_ids": ["subscription-entry-a", "subscription-entry-b"],
        },
        when={
            "operation": "subscribe_entry_a_job_from_entry_b",
        },
        then={
            "cross_entry": result["cross_entry"],
        },
    )

    print_case(
        "valid_subscriptions_stay_config_entry_scoped",
        given={
            "entry_ids": ["valid-subscription-entry-a", "valid-subscription-entry-b"],
        },
        when={
            "operation": "subscribe_each_entry_own_job",
        },
        then={
            "isolation": result["isolation"],
        },
    )

    print_case(
        "subscription_progress_snapshots_validate_before_storage",
        given={
            "schema": "docs/schemas/integration-job-snapshot.schema.json",
        },
        when={
            "operation": "validate_observed_subscription_progress_snapshots",
        },
        then={
            "snapshot_validation": result["snapshot_validation"],
        },
    )

    print_case(
        "subscription_progress_remains_bounded",
        given={
            "handled_surfaces": [
                "accepted_subscribe",
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

    print("PASS home_assistant_job_orchestration_subscription_progress_scaffold")


if __name__ == "__main__":
    main()
