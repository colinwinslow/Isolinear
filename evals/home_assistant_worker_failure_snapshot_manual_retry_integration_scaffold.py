import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.worker_failure_snapshot_manual_retry_anchor import (  # noqa: E402
    verify_worker_failure_snapshot_manual_retry_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_worker_failure_snapshot_manual_retry_anchor(REPO_ROOT)

    assert_true(
        result["passed"],
        f"Worker failure snapshot/manual retry integration failed: {result['failures']!r}",
    )

    print_case(
        "worker_render_failure_returns_failed_snapshot",
        given={
            "run_timestamp": run_timestamp,
            "config_entry_id": "worker-failure-render-entry",
            "worker_retry_policy_schema": "docs/schemas/integration-worker-retry-policy.schema.json",
            "job_snapshot_schema": "docs/schemas/integration-job-snapshot.schema.json",
        },
        when={
            "operation": "dispatch_registered_job_snapshot_with_failed_worker_render_result",
        },
        then={
            "snapshot_accepted": result["render"]["snapshot"]["accepted"],
            "error_codes": result["render"]["error_codes"],
            "card_snapshot": result["render"]["card_snapshot"],
            "worker_call_count": result["render"]["worker_call_count"],
            "worker_retry_policy_count": len(result["render"]["worker_retry_policies"]),
            "worker_dispatch_count": len(result["render"]["worker_dispatches"]),
            "render_plan_count": len(result["render"]["render_plans"]),
            "artifact_count": len(result["render"]["artifacts"]),
            "complete_snapshot_count": len(result["render"]["complete_snapshots"]),
            "failed_snapshot_validation": result["render"]["failed_snapshot_validation"],
        },
    )

    print_case(
        "worker_transport_failure_returns_failed_snapshot",
        given={
            "config_entry_id": "worker-failure-transport-entry",
            "transport_failure_code": "worker_connection_error",
            "worker_transport_failure_classification_schema": (
                "docs/schemas/integration-worker-transport-failure-classification.schema.json"
            ),
            "job_snapshot_schema": "docs/schemas/integration-job-snapshot.schema.json",
        },
        when={
            "operation": "dispatch_registered_job_snapshot_with_accepted_false_worker_response",
        },
        then={
            "snapshot_accepted": result["transport"]["snapshot"]["accepted"],
            "error_codes": result["transport"]["error_codes"],
            "card_snapshot": result["transport"]["card_snapshot"],
            "worker_call_count": result["transport"]["worker_call_count"],
            "transport_classification_count": len(result["transport"]["classifications"]),
            "worker_retry_policy_count": len(result["transport"]["worker_retry_policies"]),
            "worker_dispatch_count": len(result["transport"]["worker_dispatches"]),
            "render_plan_count": len(result["transport"]["render_plans"]),
            "artifact_count": len(result["transport"]["artifacts"]),
            "complete_snapshot_count": len(result["transport"]["complete_snapshots"]),
            "failed_snapshot_validation": result["transport"]["failed_snapshot_validation"],
        },
    )

    print_case(
        "manual_retry_resumes_worker_failure_snapshot",
        given={
            "failed_snapshot_stage": "worker_render",
            "retry_allowed": True,
        },
        when={
            "operation": "dispatch_registered_job_retry_for_failed_worker_snapshot",
        },
        then={
            "failure_snapshot": result["retry"]["failed_snapshot"],
            "retry_accepted": result["retry"]["retry"]["accepted"],
            "retry_snapshot": result["retry"]["retry_snapshot"],
            "same_job_id": result["retry"]["same_job_id"],
            "job_progress_stages": result["retry"]["job_progress_stages"],
            "history_request_count_delta": result["retry"]["history_request_count_delta"],
            "run_result_code": result["retry"]["run"]["result_code"],
        },
    )

    print_case(
        "non_retry_safe_transport_failure_rejects_manual_retry",
        given={
            "transport_failure_code": "worker_response_error",
            "retry_safe": False,
        },
        when={
            "operation": "dispatch_registered_job_retry_for_non_retryable_worker_failure_snapshot",
        },
        then={
            "failed_snapshot": result["non_retry_safe"]["failed_snapshot"],
            "retry_accepted": result["non_retry_safe"]["retry"]["accepted"],
            "retry_error_codes": result["non_retry_safe"]["retry_error_codes"],
            "snapshot_count_before_retry": result["non_retry_safe"]["snapshot_count_before_retry"],
            "snapshot_count_after_retry": result["non_retry_safe"]["snapshot_count_after_retry"],
            "history_request_count_delta": result["non_retry_safe"]["history_request_count_delta"],
            "classification_validation": result["non_retry_safe"]["classification_validation"],
        },
    )

    print_case(
        "worker_failure_snapshot_contracts_validate",
        given={
            "job_snapshot_schema": "docs/schemas/integration-job-snapshot.schema.json",
            "worker_retry_policy_schema": "docs/schemas/integration-worker-retry-policy.schema.json",
            "worker_transport_failure_classification_schema": (
                "docs/schemas/integration-worker-transport-failure-classification.schema.json"
            ),
        },
        when={
            "operation": "validate_failed_worker_snapshots_and_internal_worker_failure_envelopes",
        },
        then={
            "validation": result["validation"],
        },
    )

    print_case(
        "card_payload_excludes_worker_internals",
        given={
            "authorization_source": "integration_owned_fake_worker_client",
        },
        when={
            "operation": "inspect_card_facing_failed_snapshot_payloads",
        },
        then={
            "card_redaction": result["card_redaction"],
        },
    )

    print_case(
        "unknown_job_rejected_before_worker_failure_snapshot",
        given={
            "job_id": "worker-failure-unknown-entry-job-404",
        },
        when={
            "operation": "dispatch_registered_job_snapshot",
        },
        then={
            "snapshot_accepted": result["unknown_job"]["snapshot"]["accepted"],
            "error_codes": result["unknown_job"]["error_codes"],
            "worker_call_count": result["unknown_job"]["worker_call_count"],
            "worker_retry_policy_count": len(result["unknown_job"]["worker_retry_policies"]),
            "transport_classification_count": len(result["unknown_job"]["transport_classifications"]),
            "worker_dispatch_count": len(result["unknown_job"]["worker_dispatches"]),
        },
    )

    print_case(
        "cross_config_entry_rejected_before_worker_failure_snapshot",
        given={
            "entry_ids": ["worker-failure-cross-entry-a", "worker-failure-cross-entry-b"],
        },
        when={
            "operation": "snapshot_and_retry_entry_a_job_from_entry_b",
        },
        then={
            "cross_snapshot_accepted": result["cross_entry"]["cross_snapshot"]["accepted"],
            "cross_retry_accepted": result["cross_entry"]["cross_retry"]["accepted"],
            "error_codes": result["cross_entry"]["error_codes"],
            "entry_a_worker_call_count": result["cross_entry"]["entry_a_worker_call_count"],
            "entry_b_worker_call_count": result["cross_entry"]["entry_b_worker_call_count"],
            "entry_b_failed_snapshot_count": len(result["cross_entry"]["entry_b_failed_snapshots"]),
            "entry_b_worker_retry_policy_count": len(result["cross_entry"]["entry_b_worker_retry_policies"]),
            "entry_b_transport_classification_count": len(
                result["cross_entry"]["entry_b_transport_classifications"]
            ),
        },
    )

    print_case(
        "valid_worker_failure_snapshots_stay_config_entry_scoped",
        given={
            "entry_ids": ["worker-failure-isolation-entry-a", "worker-failure-isolation-entry-b"],
        },
        when={
            "operation": "snapshot_each_entry_own_job_with_own_worker_failure",
        },
        then={
            "entry_a": {
                "snapshot_accepted": result["isolation"]["entry_a"]["snapshot"]["accepted"],
                "worker_call_count": result["isolation"]["entry_a"]["worker_call_count"],
                "failed_snapshots": result["isolation"]["entry_a"]["failed_snapshots"],
                "worker_retry_policy_count": len(result["isolation"]["entry_a"]["worker_retry_policies"]),
                "transport_classification_count": len(
                    result["isolation"]["entry_a"]["transport_classifications"]
                ),
            },
            "entry_b": {
                "snapshot_accepted": result["isolation"]["entry_b"]["snapshot"]["accepted"],
                "worker_call_count": result["isolation"]["entry_b"]["worker_call_count"],
                "failed_snapshots": result["isolation"]["entry_b"]["failed_snapshots"],
                "worker_retry_policy_count": len(result["isolation"]["entry_b"]["worker_retry_policies"]),
                "transport_classification_count": len(
                    result["isolation"]["entry_b"]["transport_classifications"]
                ),
            },
        },
    )

    print_case(
        "worker_failure_snapshot_manual_retry_remains_bounded",
        given={
            "handled_surfaces": [
                "worker_render_failure_snapshot",
                "worker_transport_failure_snapshot",
                "manual_retry",
                "non_retry_safe_manual_retry_rejection",
                "unknown_job_failure",
                "cross_config_entry_failure",
                "config_entry_isolation",
            ],
        },
        when={
            "operation": "aggregate_observed_side_effects",
        },
        then={
            "forbidden_aggregate": result["side_effects"]["forbidden_aggregate"],
            "allowed_aggregate": result["side_effects"]["allowed_aggregate"],
            "card_payloads_exclude_worker_internals": (
                result["side_effects"]["card_redaction"]["card_payloads_exclude_worker_internals"]
            ),
            "worker_token_absent_from_card_payloads": (
                result["side_effects"]["card_redaction"]["worker_token_absent_from_card_payloads"]
            ),
        },
    )

    print("PASS home_assistant_worker_failure_snapshot_manual_retry_integration_scaffold")


if __name__ == "__main__":
    main()
