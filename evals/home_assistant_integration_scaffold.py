import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.integration_scaffold_anchor import verify_integration_scaffold_anchor  # noqa: E402


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_integration_scaffold_anchor(REPO_ROOT)

    assert_true(result["passed"], f"Integration scaffold anchor verification failed: {result['failures']!r}")

    print_case(
        "scaffold_package_is_visible_to_home_assistant",
        given={
            "run_timestamp": run_timestamp,
            "package": "custom_components/isolinear",
        },
        when={
            "operation": "inspect_manifest_and_constants",
        },
        then={
            "manifest": result["manifest"],
            "command_types": result["commands"]["command_types"],
        },
    )

    print_case(
        "local_first_configuration_shape_is_inspectable",
        given={
            "config_fields": list(result["config"]["defaults"]["config_data"]),
            "options_fields": list(result["config"]["defaults"]["options_data"]),
        },
        when={
            "operation": "validate_default_and_invalid_config_shapes",
        },
        then={
            "defaults": result["config"]["defaults"],
            "invalid_results": result["config"]["invalid_results"],
        },
    )

    print_case(
        "known_card_commands_are_accepted_as_stubs",
        given={
            "schema": "docs/schemas/integration-ws-command.schema.json",
            "snapshot_schema": "docs/schemas/integration-job-snapshot.schema.json",
        },
        when={
            "operation": "handle_known_scaffold_ws_commands",
        },
        then={
            "accepted_results": result["commands"]["accepted_results"],
            "snapshot_validation": result["commands"]["snapshot_validation"],
        },
    )

    print_case(
        "unknown_or_unsupported_commands_fail_closed",
        given={
            "invalid_examples": ["unknown_command", "wrong_version"],
        },
        when={
            "operation": "handle_invalid_scaffold_ws_commands",
        },
        then={
            "invalid_results": {
                key: result["commands"]["invalid_results"][key]
                for key in ["unknown_command", "wrong_version"]
            },
        },
    )

    print_case(
        "leaky_or_mutating_payloads_fail_closed_without_orchestration",
        given={
            "invalid_examples": ["leaky_worker_url", "mutating_service_call"],
        },
        when={
            "operation": "handle_forbidden_boundary_material",
        },
        then={
            "invalid_results": {
                key: result["commands"]["invalid_results"][key]
                for key in ["leaky_worker_url", "mutating_service_call"]
            },
            "no_orchestration": result["no_orchestration"],
        },
    )

    print("PASS home_assistant_integration_scaffold")


if __name__ == "__main__":
    main()
