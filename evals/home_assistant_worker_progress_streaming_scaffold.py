import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.worker_progress_streaming_anchor import (  # noqa: E402
    verify_worker_progress_streaming_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_worker_progress_streaming_anchor(REPO_ROOT)

    assert_true(
        result["passed"],
        f"Worker progress streaming scaffold failed: {result['failures']!r}",
    )

    print_case(
        "subscribed_worker_job_records_progress_snapshots",
        given={
            "run_timestamp": run_timestamp,
            "config_entry_id": "worker-progress-entry",
            "worker_progress_schema": "docs/schemas/integration-worker-progress.schema.json",
            "job_snapshot_schema": "docs/schemas/integration-job-snapshot.schema.json",
        },
        when={
            "operation": "subscribe_then_dispatch_registered_job_snapshot_with_streaming_fake_worker",
        },
        then={
            "accepted": result["accepted"],
        },
    )

    print_case(
        "worker_progress_links_to_card_subscriptions",
        given={
            "subscription_source": "isolinear/v1/job/subscribe",
        },
        when={
            "operation": "inspect_worker_progress_subscription_ids",
        },
        then={
            "subscription_linkage": result["subscription_linkage"],
        },
    )

    print_case(
        "worker_progress_contracts_validate_before_storage",
        given={
            "worker_progress_schema": "docs/schemas/integration-worker-progress.schema.json",
            "job_snapshot_schema": "docs/schemas/integration-job-snapshot.schema.json",
            "worker_transport_schema": "docs/schemas/worker-transport-request.schema.json",
            "render_request_schema": "docs/schemas/render-request.schema.json",
            "render_result_schema": "docs/schemas/render-result.schema.json",
            "worker_dispatch_schema": "docs/schemas/integration-worker-dispatch.schema.json",
        },
        when={
            "operation": "validate_observed_worker_progress_contracts",
        },
        then={
            "validation": result["validation"],
        },
    )

    print_case(
        "worker_progress_authorization_is_redacted",
        given={
            "authorization_source": "integration_owned_fake_worker_client",
        },
        when={
            "operation": "inspect_stored_worker_progress_metadata_and_evidence",
        },
        then={
            "redaction": result["redaction"],
        },
    )

    print_case(
        "repeated_snapshot_requests_reuse_worker_progress",
        given={
            "config_entry_id": "worker-progress-idempotent-entry",
        },
        when={
            "operation": "dispatch_registered_job_snapshot_twice_after_worker_progress",
        },
        then={
            "idempotent": result["idempotent"],
        },
    )

    print_case(
        "invalid_worker_progress_rejected_before_storage",
        given={
            "invalid_progress": {
                "stage": "",
                "percent_complete": 125,
            },
            "http_progress_events_type": "dict",
        },
        when={
            "operation": "dispatch_registered_job_snapshot_with_invalid_or_non_list_worker_progress",
        },
        then={
            "invalid": result["invalid"],
            "http_non_list": result["http_non_list"],
        },
    )

    print_case(
        "unknown_job_rejected_before_worker_progress",
        given={
            "job_id": "worker-progress-unknown-entry-job-404",
        },
        when={
            "operation": "dispatch_registered_job_snapshot",
        },
        then={
            "unknown_job": result["unknown_job"],
        },
    )

    print_case(
        "cross_config_entry_rejected_before_worker_progress",
        given={
            "entry_ids": ["worker-progress-cross-entry-a", "worker-progress-cross-entry-b"],
        },
        when={
            "operation": "snapshot_entry_a_job_from_entry_b",
        },
        then={
            "cross_entry": result["cross_entry"],
        },
    )

    print_case(
        "valid_worker_progress_stays_config_entry_scoped",
        given={
            "entry_ids": ["worker-progress-isolation-entry-a", "worker-progress-isolation-entry-b"],
        },
        when={
            "operation": "snapshot_each_entry_own_job_with_own_streaming_worker",
        },
        then={
            "isolation": result["isolation"],
        },
    )

    print_case(
        "worker_progress_remains_bounded",
        given={
            "handled_surfaces": [
                "accepted_worker_progress_snapshot",
                "accepted_subscription",
                "idempotent_snapshot",
                "invalid_progress_failure",
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

    print("PASS home_assistant_worker_progress_streaming_scaffold")


if __name__ == "__main__":
    main()
