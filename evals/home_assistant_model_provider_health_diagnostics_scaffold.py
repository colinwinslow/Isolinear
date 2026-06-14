import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.model_provider_health_diagnostics_anchor import (  # noqa: E402
    verify_model_provider_health_diagnostics_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_model_provider_health_diagnostics_anchor(REPO_ROOT)

    assert_true(
        result["passed"],
        f"Model-provider health diagnostics scaffold failed: {result['failures']!r}",
    )

    print_case(
        "ready_provider_health_probe_records_metadata",
        given={
            "run_timestamp": run_timestamp,
            "config_entry_id": "provider-health-ready-entry",
            "model_provider_health_request_schema": "docs/schemas/model-provider-health-request.schema.json",
            "integration_model_provider_health_schema": "docs/schemas/integration-model-provider-health.schema.json",
        },
        when={
            "operation": "explicitly_check_model_provider_health",
            "provider_endpoint_path": "/api/tags",
        },
        then={
            "ready": result["ready"],
        },
    )

    print_case(
        "not_ready_provider_health_response_records_internal_state",
        given={
            "config_entry_id": "provider-health-not-ready-entry",
            "provider_response_status": "not_ready",
        },
        when={
            "operation": "explicitly_check_model_provider_health",
        },
        then={
            "not_ready": result["not_ready"],
        },
    )

    print_case(
        "transport_failure_records_unavailable_provider_health",
        given={
            "config_entry_id": "provider-health-unavailable-entry",
            "provider_transport_failure": "model_provider_health_connection_error",
        },
        when={
            "operation": "explicitly_check_model_provider_health",
        },
        then={
            "unavailable": result["unavailable"],
        },
    )

    print_case(
        "malformed_accepted_provider_health_response_fails_before_storage",
        given={
            "config_entry_id": "provider-health-malformed-entry",
            "provider_response_status": "surprising",
        },
        when={
            "operation": "explicitly_check_model_provider_health",
        },
        then={
            "malformed": result["malformed"],
        },
    )

    print_case(
        "secret_bearing_provider_health_response_fails_before_storage",
        given={
            "config_entry_id": "provider-health-secret-entry",
            "provider_response_contains_secret_like_text": True,
        },
        when={
            "operation": "explicitly_check_model_provider_health",
        },
        then={
            "secret": result["secret"],
        },
    )

    print_case(
        "unconfigured_entry_rejected_before_provider_call",
        given={
            "config_entry_id": "provider-health-unconfigured-entry",
            "model_provider_planner_configured": False,
        },
        when={
            "operation": "explicitly_check_model_provider_health",
        },
        then={
            "unconfigured": result["unconfigured"],
        },
    )

    print_case(
        "unknown_config_entry_rejected_before_provider_call",
        given={
            "config_entry_id": "missing-provider-health-entry",
        },
        when={
            "operation": "explicitly_check_model_provider_health",
        },
        then={
            "unknown": result["unknown"],
        },
    )

    print_case(
        "model_provider_health_stays_config_entry_scoped",
        given={
            "entry_ids": [
                "provider-health-isolation-entry-a",
                "provider-health-isolation-entry-b",
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
        "model_provider_health_details_do_not_leak_to_card",
        given={
            "config_entry_id": "provider-health-leak-entry",
        },
        when={
            "operation": "inspect_health_setup_dashboard_worker_and_evidence_payloads",
        },
        then={
            "leakage": result["leakage"],
        },
    )

    print_case(
        "model_provider_health_diagnostics_remain_bounded",
        given={
            "handled_surfaces": [
                "ready_health",
                "not_ready_health",
                "unavailable_health",
                "malformed_response",
                "secret_response",
                "unconfigured_entry",
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

    print("PASS home_assistant_model_provider_health_diagnostics_scaffold")


if __name__ == "__main__":
    main()
