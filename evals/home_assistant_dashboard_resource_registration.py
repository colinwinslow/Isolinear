import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.dashboard_resource_anchor import (  # noqa: E402
    verify_dashboard_resource_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_dashboard_resource_anchor(REPO_ROOT)

    assert_true(result["passed"], f"Dashboard resource anchor failed: {result['failures']!r}")

    print_case(
        "card_bundle_served_from_integration_static_path",
        given={
            "run_timestamp": run_timestamp,
            "card_bundle": result["files"]["bundle_path"],
        },
        when={
            "operation": "async_register_card_static_path",
        },
        then={
            "files": result["files"],
            "static_path": result["static_path"],
        },
    )

    print_case(
        "config_entry_setup_registers_resource_metadata",
        given={
            "entry_id": result["setup_entry"]["entry_id"],
            "resource_url": result["files"]["resource_url"],
        },
        when={
            "operation": "async_setup_entry",
        },
        then={
            "setup_entry": result["setup_entry"],
        },
    )

    print_case(
        "repeated_setup_does_not_duplicate_metadata",
        given={
            "resource_url": result["files"]["resource_url"],
        },
        when={
            "operation": "async_register_dashboard_resource_twice",
        },
        then={
            "idempotence": result["idempotence"],
        },
    )

    print_case(
        "preexisting_matching_metadata_is_reused",
        given={
            "resource_url": result["files"]["resource_url"],
            "resource_type": "module",
        },
        when={
            "operation": "async_register_dashboard_resource_with_existing_item",
        },
        then={
            "preexisting": result["preexisting"],
        },
    )

    print_case(
        "stale_isolinear_resource_is_updated",
        given={
            "legacy_resource_url": "/api/isolinear/static/isolinear-card.js",
            "resource_url": result["files"]["resource_url"],
        },
        when={
            "operation": "async_register_dashboard_resource_with_stale_item",
        },
        then={
            "stale_update": result["stale_update"],
        },
    )

    print_case(
        "missing_bundle_fails_closed",
        given={
            "bundle_path": result["missing_bundle"]["result"]["bundle_path"],
        },
        when={
            "operation": "async_register_dashboard_resource",
        },
        then={
            "missing_bundle": result["missing_bundle"],
        },
    )

    print_case(
        "unavailable_resource_collection_fails_closed",
        given={
            "lovelace_resource_collection": None,
        },
        when={
            "operation": "async_register_dashboard_resource",
        },
        then={
            "unavailable_collection": result["unavailable_collection"],
        },
    )

    print_case(
        "dashboard_resource_registration_remains_non_orchestrating",
        given={
            "handled_surfaces": [
                "static_path_registration",
                "setup_entry_registration",
                "idempotent_registration",
                "preexisting_resource_reuse",
                "stale_resource_update",
                "missing_bundle_rejection",
            ],
        },
        when={
            "operation": "aggregate_observed_side_effects",
        },
        then={
            "side_effects": result["side_effects"],
        },
    )

    print("PASS home_assistant_dashboard_resource_registration")


if __name__ == "__main__":
    main()
