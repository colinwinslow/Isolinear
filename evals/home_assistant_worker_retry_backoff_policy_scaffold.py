import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.worker_retry_backoff_policy_anchor import (  # noqa: E402
    verify_worker_retry_backoff_policy_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_worker_retry_backoff_policy_anchor(REPO_ROOT)

    assert_true(
        result["passed"],
        f"Worker retry/backoff policy scaffold failed: {result['failures']!r}",
    )

    print_case(
        "worker_render_failure_records_retry_backoff_policy",
        given={
            "run_timestamp": run_timestamp,
            "config_entry_id": "worker-retry-entry",
            "worker_retry_policy_schema": "docs/schemas/integration-worker-retry-policy.schema.json",
        },
        when={
            "operation": "dispatch_registered_job_snapshot_with_failed_fake_worker_result",
        },
        then={
            "accepted": result["accepted"],
        },
    )

    print_case(
        "worker_retry_policy_contracts_validate",
        given={
            "worker_retry_policy_schema": "docs/schemas/integration-worker-retry-policy.schema.json",
            "worker_transport_schema": "docs/schemas/worker-transport-request.schema.json",
            "render_request_schema": "docs/schemas/render-request.schema.json",
            "render_result_schema": "docs/schemas/render-result.schema.json",
        },
        when={
            "operation": "validate_observed_worker_retry_policy_contracts",
        },
        then={
            "validation": result["validation"],
        },
    )

    print_case(
        "worker_retry_policy_authorization_is_redacted",
        given={
            "authorization_source": "integration_owned_fake_worker_client",
        },
        when={
            "operation": "inspect_stored_retry_policy_metadata_and_evidence",
        },
        then={
            "redaction": result["redaction"],
        },
    )

    print_case(
        "unknown_job_rejected_before_worker_retry_policy",
        given={
            "job_id": "worker-retry-unknown-entry-job-404",
        },
        when={
            "operation": "dispatch_registered_job_snapshot",
        },
        then={
            "unknown_job": result["unknown_job"],
        },
    )

    print_case(
        "cross_config_entry_rejected_before_worker_retry_policy",
        given={
            "entry_ids": ["worker-retry-cross-entry-a", "worker-retry-cross-entry-b"],
        },
        when={
            "operation": "snapshot_entry_a_job_from_entry_b",
        },
        then={
            "cross_entry": result["cross_entry"],
        },
    )

    print_case(
        "valid_worker_retry_policies_stay_config_entry_scoped",
        given={
            "entry_ids": ["worker-retry-isolation-entry-a", "worker-retry-isolation-entry-b"],
        },
        when={
            "operation": "snapshot_each_entry_own_job_with_own_failed_worker",
        },
        then={
            "isolation": result["isolation"],
        },
    )

    print_case(
        "worker_retry_policy_remains_bounded",
        given={
            "handled_surfaces": [
                "failed_worker_render",
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

    print("PASS home_assistant_worker_retry_backoff_policy_scaffold")


if __name__ == "__main__":
    main()
