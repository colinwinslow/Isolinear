import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.worker_token_provisioning_readiness_anchor import (  # noqa: E402
    verify_worker_token_provisioning_readiness_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_worker_token_provisioning_readiness_anchor(REPO_ROOT)

    assert_true(
        result["passed"],
        f"Worker token/readiness scaffold failed: {result['failures']!r}",
    )

    print_case(
        "explicit_token_provisioning_records_ready_state",
        given={
            "run_timestamp": run_timestamp,
            "config_entry_id": "worker-ready-entry",
            "worker_readiness_schema": "docs/schemas/integration-worker-readiness.schema.json",
        },
        when={
            "operation": "explicitly_provision_integration_worker_token",
        },
        then={
            "accepted": result["accepted"],
        },
    )

    print_case(
        "no_token_setup_reports_not_ready",
        given={
            "config_entry_id": "worker-no-token-entry",
            "worker_endpoint_configured": True,
        },
        when={
            "operation": "run_config_entry_setup_without_worker_token",
        },
        then={
            "no_token": result["no_token"],
        },
    )

    print_case(
        "missing_worker_endpoint_reports_disabled",
        given={
            "config_entry_id": "worker-disabled-entry",
            "worker_endpoint_configured": False,
        },
        when={
            "operation": "run_config_entry_setup_without_worker_endpoint",
        },
        then={
            "disabled": result["disabled"],
        },
    )

    print_case(
        "repeated_provisioning_reuses_token",
        given={
            "config_entry_id": "worker-idempotent-ready-entry",
        },
        when={
            "operation": "request_worker_token_provisioning_twice",
        },
        then={
            "repeated": result["repeated"],
        },
    )

    print_case(
        "unknown_config_entry_rejected_before_token_generation",
        given={
            "config_entry_id": "missing-worker-entry",
        },
        when={
            "operation": "request_worker_token_provisioning",
        },
        then={
            "unknown": result["unknown"],
        },
    )

    print_case(
        "readiness_validation_failure_rolls_back_token",
        given={
            "config_entry_id": "worker-validation-failure-entry",
            "schema_path": "docs/schemas/missing-worker-readiness.schema.json",
        },
        when={
            "operation": "request_worker_token_provisioning_with_unavailable_readiness_schema",
        },
        then={
            "validation_failure": result["validation_failure"],
        },
    )

    print_case(
        "readiness_and_tokens_stay_config_entry_scoped",
        given={
            "entry_ids": ["worker-ready-entry-a", "worker-ready-entry-b"],
        },
        when={
            "operation": "provision_only_entry_a",
        },
        then={
            "isolation": result["isolation"],
        },
    )

    print_case(
        "worker_token_does_not_leak",
        given={
            "authorization_source": "integration_owned_worker_token",
        },
        when={
            "operation": "inspect_readiness_setup_dashboard_model_and_evidence_payloads",
        },
        then={
            "leakage": result["leakage"],
        },
    )

    print_case(
        "worker_readiness_remains_bounded",
        given={
            "handled_surfaces": [
                "explicit_provisioning",
                "no_token_setup",
                "missing_endpoint_setup",
                "repeated_provisioning",
                "unknown_config_entry",
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

    print("PASS home_assistant_worker_token_provisioning_readiness_scaffold")


if __name__ == "__main__":
    main()
