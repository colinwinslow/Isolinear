import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.contracts import validate_contract  # noqa: E402
from Isolinear.fake_slice import (  # noqa: E402
    create_semantic_memory_store,
    get_fake_approved_entity_catalog,
    iso_timestamp,
    prepare_semantic_memory_for_planning,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Expected {expected!r} but got {actual!r}.")


def make_alias(alias_id, natural_name, entity_id, now, *, enabled=True):
    return {
        "alias_id": alias_id,
        "natural_names": [natural_name],
        "meaning": {
            "type": "threshold_interval",
            "entity_id": entity_id,
            "operator": ">",
            "value": 5,
            "unit": "W",
        },
        "source": "user_confirmed",
        "created_from_prompt": "Mark when the dishwasher was running over the last day",
        "created_at": iso_timestamp(now),
        "last_used_at": iso_timestamp(now),
        "enabled": enabled,
    }


def has_persisted_invalidity(store):
    invalidity_keys = {"invalid", "invalid_reason", "invalid_reasons", "invalid_semantic_aliases"}
    stack = [store]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if invalidity_keys.intersection(current):
                return True
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return False


def main():
    now = datetime(2026, 5, 29, 15, 0, 0, tzinfo=timezone.utc)
    valid_alias = make_alias(
        "dishwasher_running",
        "dishwasher running",
        "sensor.dishwasher_power",
        now,
    )
    unavailable_alias = make_alias(
        "retired_dishwasher_running",
        "retired dishwasher running",
        "sensor.retired_dishwasher_power",
        now,
    )
    disabled_alias = make_alias(
        "disabled_dishwasher_running",
        "disabled dishwasher running",
        "sensor.retired_dishwasher_power",
        now,
        enabled=False,
    )
    store = create_semantic_memory_store(
        aliases=[valid_alias, unavailable_alias, disabled_alias],
        now=now,
        repo_root=REPO_ROOT,
    )
    original_store = deepcopy(store)
    entity_catalog = get_fake_approved_entity_catalog()

    planning_context = prepare_semantic_memory_for_planning(
        semantic_memory_store=store,
        entity_catalog=entity_catalog,
        repo_root=REPO_ROOT,
    )

    assert_equal(store["store_version"], 1, "Store version should match eval expectation.")
    assert_equal(store["config_entry_id"], "fake-config-entry", "Store should be scoped to the config entry.")
    assert_equal(planning_context["valid_semantic_aliases"], [valid_alias], "Only valid enabled aliases should be injected.")
    assert_equal(
        planning_context["invalid_semantic_aliases"],
        [
            {
                "alias_id": "retired_dishwasher_running",
                "entity_id": "sensor.retired_dishwasher_power",
                "reason": "entity_unavailable",
            }
        ],
        "Invalidity should be computed from the current entity catalog.",
    )
    assert_equal(planning_context["store_error"], None, "Valid store should not produce a store error.")
    assert_equal(store, original_store, "Computing invalidity should not mutate the store.")
    assert_equal(has_persisted_invalidity(store), False, "Invalidity should not be persisted in the store.")

    validate_contract("semantic-memory-store", store, repo_root=REPO_ROOT)
    for alias in store["aliases"]:
        validate_contract("semantic-alias", alias, repo_root=REPO_ROOT)

    print_case(
        "semantic_memory_store_envelope",
        given={
            "semantic_memory_store": store,
            "entity_catalog": entity_catalog,
        },
        when={
            "operation": "prepare_semantic_memory_for_planning",
        },
        then={
            "valid_alias_ids": [
                alias["alias_id"]
                for alias in planning_context["valid_semantic_aliases"]
            ],
            "invalid_semantic_aliases": planning_context["invalid_semantic_aliases"],
            "store_unchanged_after_filter": store == original_store,
            "invalidity_persisted": has_persisted_invalidity(store),
        },
    )
    unsupported_version_store = {
        "store_version": 99,
        "config_entry_id": "fake-config-entry",
        "created_at": iso_timestamp(now),
        "updated_at": iso_timestamp(now),
        "aliases": [valid_alias],
    }
    unsupported_version_context = prepare_semantic_memory_for_planning(
        semantic_memory_store=unsupported_version_store,
        entity_catalog=entity_catalog,
        repo_root=REPO_ROOT,
    )

    assert_equal(
        unsupported_version_context["valid_semantic_aliases"],
        [],
        "Unsupported store version should not inject aliases.",
    )
    assert_equal(
        unsupported_version_context["invalid_semantic_aliases"],
        [],
        "Unsupported store version should fail before alias invalidity checks.",
    )
    assert_equal(
        unsupported_version_context["store_error"]["code"],
        "semantic_memory_store_invalid",
        "Unsupported store version should return a repairable store error.",
    )

    print_case(
        "unsupported_store_version_fails_closed",
        given={
            "semantic_memory_store": unsupported_version_store,
            "entity_catalog": entity_catalog,
        },
        when={
            "operation": "prepare_semantic_memory_for_planning",
        },
        then={
            "valid_alias_ids": [
                alias["alias_id"]
                for alias in unsupported_version_context["valid_semantic_aliases"]
            ],
            "invalid_semantic_aliases": unsupported_version_context["invalid_semantic_aliases"],
            "store_error": unsupported_version_context["store_error"],
        },
    )

    conflicting_alias = deepcopy(valid_alias)
    conflicting_alias["natural_names"] = ["alternate dishwasher running"]
    conflicting_alias["meaning"] = {
        "type": "threshold_interval",
        "entity_id": "sensor.retired_dishwasher_power",
        "operator": ">",
        "value": 5,
        "unit": "W",
    }
    duplicate_alias_store = {
        "store_version": 1,
        "config_entry_id": "fake-config-entry",
        "created_at": iso_timestamp(now),
        "updated_at": iso_timestamp(now),
        "aliases": [valid_alias, conflicting_alias],
    }
    duplicate_alias_context = prepare_semantic_memory_for_planning(
        semantic_memory_store=duplicate_alias_store,
        entity_catalog=entity_catalog,
        repo_root=REPO_ROOT,
    )

    assert_equal(
        duplicate_alias_context["valid_semantic_aliases"],
        [],
        "Duplicate alias IDs should not inject aliases.",
    )
    assert_equal(
        duplicate_alias_context["invalid_semantic_aliases"],
        [],
        "Duplicate alias IDs should fail before alias invalidity checks.",
    )
    assert_equal(
        duplicate_alias_context["store_error"]["code"],
        "semantic_memory_store_invalid",
        "Duplicate alias IDs should return a repairable store error.",
    )
    duplicate_error = duplicate_alias_context["store_error"]["message"]
    if "Duplicate semantic alias IDs: dishwasher_running." not in duplicate_error:
        raise AssertionError("Duplicate alias ID error should name the conflicting alias_id.")

    print_case(
        "duplicate_alias_ids_fail_closed",
        given={
            "semantic_memory_store": duplicate_alias_store,
            "entity_catalog": entity_catalog,
        },
        when={
            "operation": "prepare_semantic_memory_for_planning",
        },
        then={
            "valid_alias_ids": [
                alias["alias_id"]
                for alias in duplicate_alias_context["valid_semantic_aliases"]
            ],
            "invalid_semantic_aliases": duplicate_alias_context["invalid_semantic_aliases"],
            "store_error": duplicate_alias_context["store_error"],
        },
    )
    print("PASS semantic_memory_store_envelope")


if __name__ == "__main__":
    main()
