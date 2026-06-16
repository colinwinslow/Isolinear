import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.entity_catalog_scaffold_anchor import (  # noqa: E402
    verify_entity_catalog_scaffold_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_entity_catalog_scaffold_anchor(REPO_ROOT)

    assert_true(result["passed"], f"Approved entity catalog scaffold failed: {result['failures']!r}")

    print_case(
        "allowlisted_metadata_builds_schema_valid_catalog",
        given={
            "run_timestamp": run_timestamp,
            "schema": "docs/schemas/entity-catalog-item.schema.json",
            "metadata_entity_ids": result["catalog"]["metadata_entity_ids"],
        },
        when={
            "operation": "setup_entity_catalog",
        },
        then={
            "catalog": result["catalog"],
        },
    )

    print_case(
        "setup_entry_stores_config_entry_scoped_catalog",
        given={
            "entry_id": result["setup"]["entry_id"],
        },
        when={
            "operation": "async_setup_entry",
        },
        then={
            "setup": result["setup"],
        },
    )

    print_case(
        "options_update_rebuilds_runtime_catalog",
        given={
            "entry_id": "options-update-catalog-entry",
            "initial_allowlist": [],
            "updated_allowlist": [
                "sensor.upstairs_temperature",
                "sensor.downstairs_temperature",
            ],
        },
        when={
            "operation": "invoke_registered_options_update_listener",
        },
        then={
            "options_update": result["options_update"],
        },
    )

    print_case(
        "config_entries_receive_isolated_catalogs",
        given={
            "entry_ids": ["entry-a", "entry-b"],
        },
        when={
            "operation": "setup_entity_catalog_for_each_entry",
        },
        then={
            "isolation": result["isolation"],
        },
    )

    print_case(
        "unknown_allowlisted_entities_fail_closed",
        given={
            "entity_id": "sensor.missing_temperature",
        },
        when={
            "operation": "setup_entity_catalog",
        },
        then={
            "unknown": result["unknown"],
        },
    )

    print_case(
        "rejected_rebuild_clears_existing_catalog",
        given={
            "initial_allowlist": ["sensor.upstairs_temperature"],
            "replacement_allowlist": ["sensor.missing_temperature"],
        },
        when={
            "operation": "setup_entity_catalog_after_allowlist_change",
        },
        then={
            "stale": result["stale"],
        },
    )

    print_case(
        "malformed_allowlists_fail_closed_without_crashing",
        given={
            "entity_allowlist": [{"entity_id": "sensor.upstairs_temperature"}],
        },
        when={
            "operation": "setup_entity_catalog",
        },
        then={
            "malformed_allowlist": result["malformed_allowlist"],
        },
    )

    print_case(
        "malformed_catalog_items_are_rejected_before_storage",
        given={
            "schema": "docs/schemas/entity-catalog-item.schema.json",
            "malformed_item": result["malformed"]["malformed_item"],
        },
        when={
            "operation": "store_validated_entity_catalog",
        },
        then={
            "malformed": result["malformed"],
        },
    )

    print_case(
        "entity_catalog_remains_non_orchestrating",
        given={
            "handled_surfaces": [
                "allowlisted_catalog",
                "setup_entry_catalog",
                "config_entry_isolation",
                "unknown_entity_rejection",
                "malformed_item_rejection",
            ],
        },
        when={
            "operation": "aggregate_observed_side_effects",
        },
        then={
            "side_effects": result["side_effects"],
        },
    )

    print("PASS home_assistant_approved_entity_catalog_scaffold")


if __name__ == "__main__":
    main()
