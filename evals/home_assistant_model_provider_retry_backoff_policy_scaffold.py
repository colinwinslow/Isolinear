import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.model_provider_retry_backoff_policy_anchor import (  # noqa: E402
    verify_model_provider_retry_backoff_policy_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_model_provider_retry_backoff_policy_anchor(REPO_ROOT)

    assert_true(
        result["passed"],
        f"Model-provider retry/backoff policy scaffold failed: {result['failures']!r}",
    )

    print_case(
        "provider_failure_records_retry_policy",
        given={
            "run_timestamp": run_timestamp,
            "config_entry_id": "provider-retry-entry",
            "model_provider_retry_policy_schema": (
                "docs/schemas/integration-model-provider-retry-policy.schema.json"
            ),
        },
        when={
            "operation": "dispatch_registered_job_snapshot_with_retry_safe_failing_planner",
        },
        then={
            "accepted": result["accepted"],
        },
    )

    print_case(
        "provider_retry_policy_contracts_validate",
        given={
            "model_provider_retry_policy_schema": (
                "docs/schemas/integration-model-provider-retry-policy.schema.json"
            ),
        },
        when={
            "operation": "validate_observed_model_provider_retry_policies",
        },
        then={
            "validation": result["validation"],
        },
    )

    print_case(
        "provider_retry_policy_failure_details_are_sanitized",
        given={
            "card_boundary": "registered_websocket_result_snapshot",
        },
        when={
            "operation": "inspect_card_snapshot_and_secret_failure_case",
        },
        then={
            "sanitization": result["sanitization"],
            "secret": result["secret"],
        },
    )

    print_case(
        "malformed_provider_failure_rejected_before_policy",
        given={
            "malformation": "retry_safe_is_not_boolean",
        },
        when={
            "operation": "dispatch_registered_job_snapshot_with_malformed_provider_failure",
        },
        then={
            "malformed": result["malformed"],
        },
    )

    print_case(
        "unknown_job_rejected_before_provider_retry_policy",
        given={
            "job_id": "provider-retry-unknown-entry-job-404",
        },
        when={
            "operation": "dispatch_registered_job_snapshot",
        },
        then={
            "unknown_job": result["unknown_job"],
        },
    )

    print_case(
        "cross_config_entry_rejected_before_provider_retry_policy",
        given={
            "entry_ids": ["provider-retry-cross-entry-a", "provider-retry-cross-entry-b"],
        },
        when={
            "operation": "snapshot_entry_a_job_from_entry_b",
        },
        then={
            "cross_entry": result["cross_entry"],
        },
    )

    print_case(
        "valid_provider_retry_policies_stay_config_entry_scoped",
        given={
            "entry_ids": ["provider-retry-isolation-entry-a", "provider-retry-isolation-entry-b"],
        },
        when={
            "operation": "snapshot_each_entry_own_job_with_failing_planner",
        },
        then={
            "isolation": result["isolation"],
        },
    )

    print_case(
        "model_provider_retry_policy_remains_bounded",
        given={
            "handled_surfaces": [
                "retry_safe_provider_failure",
                "secret_provider_failure",
                "malformed_provider_failure",
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

    print("PASS home_assistant_model_provider_retry_backoff_policy_scaffold")


if __name__ == "__main__":
    main()
