import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.worker_token_rotation_repair_anchor import (  # noqa: E402
    verify_worker_token_rotation_repair_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_worker_token_rotation_repair_anchor(REPO_ROOT)

    assert_true(
        result["passed"],
        f"Worker token rotation/repair scaffold failed: {result['failures']!r}",
    )

    print_case(
        "rotation_invalidates_old_token_and_refreshes_readiness",
        given={
            "run_timestamp": run_timestamp,
            "config_entry_id": "worker-rotation-entry",
            "existing_token": "integration_owned_worker_token",
            "worker_readiness_schema": "docs/schemas/integration-worker-readiness.schema.json",
        },
        when={
            "operation": "explicitly_rotate_integration_worker_token",
        },
        then={
            "rotation": result["rotation"],
        },
    )

    print_case(
        "missing_token_repair_records_ready_state",
        given={
            "config_entry_id": "worker-repair-entry",
            "worker_endpoint_configured": True,
            "worker_token_present": False,
        },
        when={
            "operation": "explicitly_repair_integration_worker_token",
        },
        then={
            "repair": result["repair"],
        },
    )

    print_case(
        "readiness_validation_failure_rolls_back_rotation",
        given={
            "config_entry_id": "worker-rotation-rollback-entry",
            "schema_path": "docs/schemas/missing-worker-readiness.schema.json",
        },
        when={
            "operation": "rotate_worker_token_with_unavailable_readiness_schema",
        },
        then={
            "rollback": result["rollback"],
        },
    )

    print_case(
        "unknown_config_entry_rejected_before_side_effects",
        given={
            "config_entry_id": "missing-worker-rotation-entry",
        },
        when={
            "operation": "request_rotation_and_repair_for_unknown_entry",
        },
        then={
            "unknown": result["unknown"],
        },
    )

    print_case(
        "cross_entry_request_rejected_before_side_effects",
        given={
            "requesting_entry_id": "worker-cross-entry-a",
            "target_entry_id": "worker-cross-entry-b",
        },
        when={
            "operation": "request_rotation_for_another_entry",
        },
        then={
            "cross_entry": result["cross_entry"],
        },
    )

    print_case(
        "rotated_and_repaired_tokens_do_not_leak",
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
        "worker_token_rotation_repair_remains_bounded",
        given={
            "handled_surfaces": [
                "rotation",
                "repair",
                "rollback",
                "unknown_config_entry",
                "cross_entry_rejection",
            ],
        },
        when={
            "operation": "aggregate_observed_side_effects",
        },
        then={
            "side_effects": result["side_effects"],
        },
    )

    print("PASS home_assistant_worker_token_rotation_repair_scaffold")


if __name__ == "__main__":
    main()
