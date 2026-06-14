import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.worker_token_lifecycle_anchor import (  # noqa: E402
    verify_worker_token_lifecycle_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_worker_token_lifecycle_anchor(REPO_ROOT)

    assert_true(
        result["passed"],
        f"Durable worker token lifecycle scaffold failed: {result['failures']!r}",
    )

    print_case(
        "setup_restores_persisted_token_before_readiness",
        given={
            "run_timestamp": run_timestamp,
            "config_entry_id": "worker-lifecycle-restore-entry",
            "persisted_token": "integration_owned_worker_token",
            "worker_readiness_schema": "docs/schemas/integration-worker-readiness.schema.json",
            "worker_token_lifecycle_schema": (
                "docs/schemas/integration-worker-token-lifecycle-state.schema.json"
            ),
        },
        when={
            "operation": "config_entry_setup_loads_durable_worker_token_lifecycle",
        },
        then={
            "restore": result["restore"],
        },
    )

    print_case(
        "missing_persisted_token_records_repair_issue",
        given={
            "config_entry_id": "worker-lifecycle-repair-issue-entry",
            "worker_endpoint_configured": True,
            "in_memory_token_present": False,
            "persisted_token_present": False,
        },
        when={
            "operation": "setup_worker_token_lifecycle_without_restorable_token",
        },
        then={
            "repair_issue": result["repair_issue"],
        },
    )

    print_case(
        "missing_worker_endpoint_records_disabled_lifecycle",
        given={
            "config_entry_id": "worker-lifecycle-disabled-entry",
            "worker_endpoint_configured": False,
        },
        when={
            "operation": "setup_worker_token_lifecycle_without_worker_endpoint",
        },
        then={
            "disabled": result["disabled"],
        },
    )

    print_case(
        "durable_explicit_operations_persist_private_tokens",
        given={
            "operations": [
                "durable_provision",
                "durable_rotation",
                "durable_repair",
            ],
        },
        when={
            "operation": "call_durable_worker_token_lifecycle_wrappers",
        },
        then={
            "explicit": result["explicit"],
        },
    )

    print_case(
        "invalid_persisted_entries_skipped_before_restore",
        given={
            "invalid_entries": [
                "mismatched_config_entry_id",
                "malformed_token",
            ],
        },
        when={
            "operation": "setup_worker_token_lifecycle_with_invalid_persisted_entries",
        },
        then={
            "invalid": result["invalid"],
        },
    )

    print_case(
        "setup_lifecycle_storage_failure_blocks_restore",
        given={
            "config_entry_id": "worker-lifecycle-setup-failure-entry",
            "persisted_token": "integration_owned_worker_token",
            "storage_write_result": "forced_lifecycle_storage_failure",
        },
        when={
            "operation": "setup_worker_token_lifecycle_with_storage_write_failure",
        },
        then={
            "setup_failure": result["setup_failure"],
        },
    )

    print_case(
        "lifecycle_validation_failure_rolls_back",
        given={
            "config_entry_id": "worker-lifecycle-rollback-entry",
            "schema_path": "docs/schemas/missing-token-lifecycle.schema.json",
        },
        when={
            "operation": "durable_rotation_with_unavailable_lifecycle_schema",
        },
        then={
            "rollback": result["rollback"],
        },
    )

    print_case(
        "worker_token_lifecycle_stays_config_entry_scoped",
        given={
            "entry_a": "worker-lifecycle-isolation-a",
            "entry_b": "worker-lifecycle-isolation-b",
        },
        when={
            "operation": "restore_and_rotate_entry_a_only",
        },
        then={
            "isolation": result["isolation"],
        },
    )

    print_case(
        "worker_token_lifecycle_details_do_not_leak",
        given={
            "handled_surfaces": [
                "restore",
                "repair_issue",
                "explicit_operations",
                "invalid_persisted_entries",
            ],
        },
        when={
            "operation": "inspect_lifecycle_setup_dashboard_model_and_evidence_payloads",
        },
        then={
            "leakage": result["leakage"],
        },
    )

    print_case(
        "worker_token_lifecycle_remains_bounded",
        given={
            "handled_surfaces": [
                "restore",
                "repair_issue",
                "disabled",
                "explicit_operations",
                "rollback",
                "isolation",
            ],
        },
        when={
            "operation": "aggregate_observed_side_effects",
        },
        then={
            "side_effects": result["side_effects"],
        },
    )

    print("PASS home_assistant_durable_worker_token_lifecycle_scaffold")


if __name__ == "__main__":
    main()
