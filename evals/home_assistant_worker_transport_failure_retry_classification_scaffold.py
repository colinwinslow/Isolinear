import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.worker_transport_failure_classification_anchor import (  # noqa: E402
    verify_worker_transport_failure_classification_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_worker_transport_failure_classification_anchor(REPO_ROOT)

    assert_true(
        result["passed"],
        f"Worker transport failure classification scaffold failed: {result['failures']!r}",
    )

    print_case(
        "worker_connection_failure_records_retry_classification",
        given={
            "run_timestamp": run_timestamp,
            "config_entry_id": "worker-transport-entry",
            "worker_transport_failure_classification_schema": (
                "docs/schemas/integration-worker-transport-failure-classification.schema.json"
            ),
        },
        when={
            "operation": "dispatch_registered_job_snapshot_with_connection_failure_worker_response",
        },
        then={
            "accepted": result["accepted"],
        },
    )

    print_case(
        "worker_transport_failure_families_map_deterministically",
        given={
            "transport_failure_codes": [
                "worker_connection_error",
                "worker_http_error",
                "worker_response_error",
            ],
        },
        when={
            "operation": "classify_accepted_false_worker_transport_responses",
        },
        then={
            "families": result["families"],
        },
    )

    print_case(
        "worker_transport_failure_classification_contracts_validate",
        given={
            "worker_transport_failure_classification_schema": (
                "docs/schemas/integration-worker-transport-failure-classification.schema.json"
            ),
            "worker_transport_schema": "docs/schemas/worker-transport-request.schema.json",
            "render_request_schema": "docs/schemas/render-request.schema.json",
        },
        when={
            "operation": "validate_observed_worker_transport_classification_contracts",
        },
        then={
            "validation": result["validation"],
        },
    )

    print_case(
        "worker_transport_failure_classification_redacts_sensitive_material",
        given={
            "authorization_source": "integration_owned_fake_worker_client",
        },
        when={
            "operation": "inspect_stored_transport_classification_metadata_and_evidence",
        },
        then={
            "redaction": result["redaction"],
        },
    )

    print_case(
        "unknown_job_rejected_before_worker_transport_classification",
        given={
            "job_id": "worker-transport-unknown-entry-job-404",
        },
        when={
            "operation": "dispatch_registered_job_snapshot",
        },
        then={
            "unknown_job": result["unknown_job"],
        },
    )

    print_case(
        "cross_config_entry_rejected_before_worker_transport_classification",
        given={
            "entry_ids": ["worker-transport-cross-entry-a", "worker-transport-cross-entry-b"],
        },
        when={
            "operation": "snapshot_entry_a_job_from_entry_b",
        },
        then={
            "cross_entry": result["cross_entry"],
        },
    )

    print_case(
        "valid_worker_transport_classifications_stay_config_entry_scoped",
        given={
            "entry_ids": ["worker-transport-isolation-entry-a", "worker-transport-isolation-entry-b"],
        },
        when={
            "operation": "snapshot_each_entry_own_job_with_own_transport_failure_worker",
        },
        then={
            "isolation": result["isolation"],
        },
    )

    print_case(
        "worker_transport_classification_remains_bounded",
        given={
            "handled_surfaces": [
                "accepted_false_worker_transport_failure",
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

    print("PASS home_assistant_worker_transport_failure_retry_classification_scaffold")


if __name__ == "__main__":
    main()
