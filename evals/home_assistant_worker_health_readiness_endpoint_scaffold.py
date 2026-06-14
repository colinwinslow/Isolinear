import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.worker_health_readiness_endpoint_anchor import (  # noqa: E402
    verify_worker_health_readiness_endpoint_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_worker_health_readiness_endpoint_anchor(REPO_ROOT)

    assert_true(
        result["passed"],
        f"Worker health/readiness endpoint scaffold failed: {result['failures']!r}",
    )

    print_case(
        "ready_worker_health_probe_records_redacted_metadata",
        given={
            "run_timestamp": run_timestamp,
            "config_entry_id": "worker-health-ready-entry",
            "worker_health_request_schema": "docs/schemas/worker-health-request.schema.json",
            "integration_worker_health_schema": "docs/schemas/integration-worker-health.schema.json",
        },
        when={
            "operation": "explicitly_check_worker_health",
            "worker_endpoint_path": "/v1/health",
        },
        then={
            "ready": result["ready"],
        },
    )

    print_case(
        "not_ready_health_response_records_internal_state",
        given={
            "config_entry_id": "worker-health-not-ready-entry",
            "worker_response_status": "not_ready",
        },
        when={
            "operation": "explicitly_check_worker_health",
        },
        then={
            "not_ready": result["not_ready"],
        },
    )

    print_case(
        "transport_failure_records_unavailable_health",
        given={
            "config_entry_id": "worker-health-unavailable-entry",
            "worker_transport_failure": "worker_connection_error",
        },
        when={
            "operation": "explicitly_check_worker_health",
        },
        then={
            "unavailable": result["unavailable"],
        },
    )

    print_case(
        "malformed_accepted_health_response_fails_before_storage",
        given={
            "config_entry_id": "worker-health-malformed-entry",
            "worker_response_status": "surprising",
        },
        when={
            "operation": "explicitly_check_worker_health",
        },
        then={
            "malformed": result["malformed"],
        },
    )

    print_case(
        "no_token_entry_rejected_before_worker_call",
        given={
            "config_entry_id": "worker-health-no-token-entry",
            "worker_endpoint_configured": True,
            "worker_token_present": False,
        },
        when={
            "operation": "explicitly_check_worker_health",
        },
        then={
            "no_token": result["no_token"],
        },
    )

    print_case(
        "unknown_config_entry_rejected_before_worker_call",
        given={
            "config_entry_id": "missing-worker-health-entry",
        },
        when={
            "operation": "explicitly_check_worker_health",
        },
        then={
            "unknown": result["unknown"],
        },
    )

    print_case(
        "worker_health_stays_config_entry_scoped",
        given={
            "entry_ids": [
                "worker-health-isolation-entry-a",
                "worker-health-isolation-entry-b",
            ],
        },
        when={
            "operation": "check_health_for_both_entries",
        },
        then={
            "isolation": result["isolation"],
        },
    )

    print_case(
        "worker_health_details_do_not_leak_to_card",
        given={
            "config_entry_id": "worker-health-leak-entry",
            "authorization_source": "integration_owned_worker_token",
        },
        when={
            "operation": "inspect_health_setup_dashboard_model_and_evidence_payloads",
        },
        then={
            "leakage": result["leakage"],
        },
    )

    print_case(
        "worker_health_checks_remain_bounded",
        given={
            "handled_surfaces": [
                "ready_health",
                "not_ready_health",
                "unavailable_health",
                "malformed_response",
                "no_token_entry",
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

    print("PASS home_assistant_worker_health_readiness_endpoint_scaffold")


if __name__ == "__main__":
    main()
