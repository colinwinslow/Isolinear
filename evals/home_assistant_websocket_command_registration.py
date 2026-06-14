import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.websocket_command_registration_anchor import (  # noqa: E402
    verify_websocket_command_registration_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_websocket_command_registration_anchor(REPO_ROOT)

    assert_true(result["passed"], f"WebSocket command registration anchor failed: {result['failures']!r}")

    print_case(
        "command_names_registered_with_home_assistant",
        given={
            "run_timestamp": run_timestamp,
            "namespace": result["registration"]["namespace"],
            "expected_commands": result["registration"]["expected_commands"],
        },
        when={
            "operation": "async_register_websocket_api",
        },
        then={
            "registration": result["registration"],
        },
    )

    print_case(
        "config_entry_setup_stores_registration_metadata",
        given={
            "entry_id": result["setup_entry"]["entry_id"],
        },
        when={
            "operation": "async_setup_entry",
        },
        then={
            "setup_entry": result["setup_entry"],
        },
    )

    print_case(
        "registered_callbacks_return_scaffold_snapshots",
        given={
            "schema": "docs/schemas/integration-ws-command.schema.json",
            "snapshot_schema": "docs/schemas/integration-job-snapshot.schema.json",
        },
        when={
            "operation": "dispatch_registered_known_commands",
        },
        then={
            "callbacks": result["callbacks"],
        },
    )

    print_case(
        "malformed_or_unsafe_commands_fail_closed",
        given={
            "invalid_examples": [
                "unknown_command",
                "wrong_version",
                "leaky_worker_url",
                "mutating_service_call",
            ],
        },
        when={
            "operation": "dispatch_invalid_registered_commands",
        },
        then={
            "invalid": result["invalid"],
        },
    )

    print_case(
        "missing_config_entry_scope_fails_closed",
        given={
            "config_entry_id": result["missing_scope"]["command"]["config_entry_id"],
            "known_config_entries": [],
        },
        when={
            "operation": "dispatch_registered_command",
        },
        then={
            "missing_scope": result["missing_scope"],
        },
    )

    print_case(
        "repeated_setup_does_not_duplicate_commands",
        given={
            "entry_id": result["setup_entry"]["entry_id"],
        },
        when={
            "operation": "async_setup_entry_twice",
        },
        then={
            "idempotence": result["idempotence"],
        },
    )

    print_case(
        "websocket_registration_remains_non_orchestrating",
        given={
            "handled_surfaces": [
                "command_registration",
                "accepted_callbacks",
                "invalid_callbacks",
                "missing_config_entry_rejection",
            ],
        },
        when={
            "operation": "aggregate_observed_side_effects",
        },
        then={
            "side_effects": result["side_effects"],
        },
    )

    print("PASS home_assistant_websocket_command_registration")


if __name__ == "__main__":
    main()
