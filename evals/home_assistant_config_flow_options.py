import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.config_flow_anchor import verify_config_flow_anchor  # noqa: E402


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_config_flow_anchor(REPO_ROOT)

    assert_true(result["passed"], f"Config-flow/options anchor failed: {result['failures']!r}")

    print_case(
        "config_flow_is_visible_to_home_assistant",
        given={
            "run_timestamp": run_timestamp,
            "package": "custom_components/isolinear",
        },
        when={
            "operation": "inspect_manifest_and_config_flow_module",
        },
        then={
            "manifest": result["manifest"],
        },
    )

    print_case(
        "user_config_flow_creates_validated_local_first_data",
        given={
            "step": result["manifest"]["metadata"]["config_step"],
            "fields": result["manifest"]["metadata"]["config_fields"],
        },
        when={
            "operation": "validate_config_flow_user_input",
        },
        then={
            "config_flow": result["config_flow"],
        },
    )

    print_case(
        "options_flow_persists_safe_options",
        given={
            "step": result["manifest"]["metadata"]["options_step"],
            "fields": result["manifest"]["metadata"]["options_fields"],
        },
        when={
            "operation": "validate_options_flow_user_input",
        },
        then={
            "options_flow": result["options_flow"],
        },
    )

    print_case(
        "options_flow_accepts_live_allowlist_input_variants",
        given={
            "reported_entity_id": "sensor.family_room_sensor_temperature",
            "input_variants": list(result["live_allowlist_variants"]["variants"]),
        },
        when={
            "operation": "validate_live_allowlist_input_variants",
        },
        then={
            "allowlist_variants": result["live_allowlist_variants"],
            "options_flow_config_entry": result["options_flow_config_entry"],
        },
    )

    print_case(
        "invalid_config_flow_input_fails_closed",
        given={
            "invalid_examples": list(result["invalid_inputs"]["config"]),
        },
        when={
            "operation": "validate_invalid_config_flow_inputs",
        },
        then={
            "invalid_config_results": result["invalid_inputs"]["config"],
        },
    )

    print_case(
        "invalid_options_flow_input_fails_closed",
        given={
            "invalid_examples": list(result["invalid_inputs"]["options"]),
        },
        when={
            "operation": "validate_invalid_options_flow_inputs",
        },
        then={
            "invalid_options_results": result["invalid_inputs"]["options"],
        },
    )

    print_case(
        "setup_flow_remains_non_orchestrating",
        given={
            "handled_surfaces": ["config_flow_user", "options_flow_init"],
        },
        when={
            "operation": "aggregate_observed_side_effects",
        },
        then={
            "non_orchestration": result["non_orchestration"],
        },
    )

    print("PASS home_assistant_config_flow_options")


if __name__ == "__main__":
    main()
