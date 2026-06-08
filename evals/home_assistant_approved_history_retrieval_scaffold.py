import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.history_retrieval_scaffold_anchor import (  # noqa: E402
    verify_history_retrieval_scaffold_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_history_retrieval_scaffold_anchor(REPO_ROOT)

    assert_true(result["passed"], f"Approved history retrieval scaffold failed: {result['failures']!r}")

    print_case(
        "approved_entities_retrieve_schema_valid_history",
        given={
            "run_timestamp": run_timestamp,
            "schema": "docs/schemas/history-series.schema.json",
            "history_source_entity_ids": result["retrieval"]["history_source_entity_ids"],
        },
        when={
            "operation": "retrieve_approved_history",
        },
        then={
            "retrieval": result["retrieval"],
        },
    )

    print_case(
        "setup_entry_stores_config_entry_scoped_history_store",
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
        "config_entries_receive_isolated_history",
        given={
            "entry_ids": ["history-entry-a", "history-entry-b"],
        },
        when={
            "operation": "retrieve_approved_history_for_each_entry",
        },
        then={
            "isolation": result["isolation"],
        },
    )

    print_case(
        "non_catalog_entities_fail_closed_before_history_read",
        given={
            "requested_entity_id": "light.kitchen",
        },
        when={
            "operation": "retrieve_approved_history",
        },
        then={
            "non_catalog": result["non_catalog"],
        },
    )

    print_case(
        "rejected_retrieval_clears_existing_history",
        given={
            "initial_entity_ids": ["sensor.upstairs_temperature"],
            "rejected_entity_ids": ["light.kitchen"],
        },
        when={
            "operation": "retrieve_approved_history_after_rejected_request",
        },
        then={
            "stale": result["stale"],
        },
    )

    print_case(
        "malformed_raw_history_fails_closed",
        given={
            "malformed_field": "last_changed",
        },
        when={
            "operation": "retrieve_approved_history",
        },
        then={
            "malformed_raw": result["malformed_raw"],
        },
    )

    print_case(
        "malformed_history_series_rejected_before_storage",
        given={
            "schema": "docs/schemas/history-series.schema.json",
            "malformed_series": result["malformed_series"]["malformed_series"],
        },
        when={
            "operation": "store_validated_history_series",
        },
        then={
            "malformed_series": result["malformed_series"],
        },
    )

    print_case(
        "history_retrieval_remains_non_orchestrating",
        given={
            "handled_surfaces": [
                "approved_history",
                "setup_history",
                "config_entry_isolation",
                "non_catalog_rejection",
                "malformed_raw_rejection",
                "malformed_series_rejection",
            ],
        },
        when={
            "operation": "aggregate_observed_side_effects",
        },
        then={
            "side_effects": result["side_effects"],
        },
    )

    print("PASS home_assistant_approved_history_retrieval_scaffold")


if __name__ == "__main__":
    main()
