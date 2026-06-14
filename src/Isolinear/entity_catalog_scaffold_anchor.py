from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from custom_components.isolinear import async_setup_entry
from custom_components.isolinear.const import DOMAIN
from custom_components.isolinear.entity_catalog import (
    DATA_ENTITY_CATALOG,
    DATA_ENTITY_CATALOG_SETUP,
    DATA_ENTITY_METADATA,
    NO_ENTITY_CATALOG_ORCHESTRATION_CALLS,
    setup_entity_catalog,
    store_validated_entity_catalog,
    summarize_entity_catalog_store,
)

from .contracts import ContractValidationError, validate_contract
from .dashboard_card_anchor import repo_root


ENTITY_CATALOG_SCAFFOLD_FILES = [
    "custom_components/isolinear/entity_catalog.py",
    "custom_components/isolinear/__init__.py",
    "docs/schemas/entity-catalog-item.schema.json",
    "docs/specs/home-assistant-approved-entity-catalog-scaffold-spec.md",
    "bdd/integration/home-assistant-approved-entity-catalog-scaffold-bdd.md",
    "docs/evals/home_assistant_approved_entity_catalog_scaffold.yaml",
    "tests/test_approved_entity_catalog_scaffold_anchor.py",
    "evals/home_assistant_approved_entity_catalog_scaffold.py",
]


@dataclass
class FakeConfigEntry:
    entry_id: str = "catalog-entry-001"
    options: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class FakeState:
    state: Any
    attributes: dict[str, Any] = field(default_factory=dict)


class FakeStates:
    def __init__(self, states: dict[str, FakeState] | None = None) -> None:
        self._states = dict(states or {})

    def get(self, entity_id: str) -> FakeState | None:
        return self._states.get(entity_id)


class FakeHttp:
    def __init__(self) -> None:
        self.static_path_calls: list[list[Any]] = []

    async def async_register_static_paths(self, paths: list[Any]) -> None:
        self.static_path_calls.append(paths)


class FakeLovelaceResources:
    def __init__(self) -> None:
        self.loaded = True
        self._items: list[dict[str, Any]] = []
        self.create_calls: list[dict[str, Any]] = []

    def async_items(self) -> list[dict[str, Any]]:
        return list(self._items)

    async def async_create_item(self, data: dict[str, Any]) -> dict[str, Any]:
        self.create_calls.append(dict(data))
        item = {
            "id": f"resource-{len(self._items) + 1:03d}",
            "url": data["url"],
            "type": data.get("type") or data.get("res_type"),
        }
        self._items.append(item)
        return item


class FakeHass:
    def __init__(
        self,
        *,
        metadata_by_entity: dict[str, Any] | None = None,
        states: dict[str, FakeState] | None = None,
    ) -> None:
        self.data: dict[str, Any] = {
            DOMAIN: {
                DATA_ENTITY_METADATA: dict(metadata_by_entity or {}),
            },
            "lovelace": SimpleNamespace(resources=FakeLovelaceResources()),
        }
        self.states = FakeStates(states)
        self.http = FakeHttp()


def fake_entity_metadata() -> dict[str, dict[str, Any]]:
    return {
        "sensor.upstairs_temperature": {
            "friendly_name": "Upstairs Temperature",
            "device_class": "temperature",
            "state_class": "measurement",
            "unit_of_measurement": "degF",
            "area": "Upstairs",
            "labels": ["climate", "approved"],
            "device_name": "Upstairs Thermostat",
            "integration": "demo",
            "attributes": {
                "friendly_name": "Upstairs Temperature",
                "device_class": "temperature",
                "state_class": "measurement",
                "unit_of_measurement": "degF",
            },
        },
        "sensor.downstairs_temperature": {
            "friendly_name": "Downstairs Temperature",
            "device_class": "temperature",
            "state_class": "measurement",
            "unit_of_measurement": "degF",
            "area": "Downstairs",
            "labels": ["climate"],
            "device_name": "Downstairs Thermostat",
            "integration": "demo",
            "attributes": {
                "friendly_name": "Downstairs Temperature",
                "device_class": "temperature",
                "state_class": "measurement",
                "unit_of_measurement": "degF",
            },
        },
        "binary_sensor.office_window": {
            "friendly_name": "Office Window",
            "device_class": "window",
            "state_class": None,
            "unit_of_measurement": None,
            "area": "Office",
            "labels": ["security"],
            "device_name": "Office Window Sensor",
            "integration": "demo",
            "attributes": {
                "friendly_name": "Office Window",
                "device_class": "window",
            },
        },
        "light.kitchen": {
            "friendly_name": "Kitchen Lights",
            "device_class": None,
            "state_class": None,
            "unit_of_measurement": None,
            "area": "Kitchen",
            "labels": ["not-allowlisted"],
            "device_name": "Kitchen Light Group",
            "integration": "demo",
            "attributes": {
                "friendly_name": "Kitchen Lights",
            },
        },
    }


def fake_states() -> dict[str, FakeState]:
    return {
        "sensor.upstairs_temperature": FakeState("72.1"),
        "sensor.downstairs_temperature": FakeState("69.4"),
        "binary_sensor.office_window": FakeState("off"),
        "light.kitchen": FakeState("on"),
    }


def verify_entity_catalog_scaffold_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in ENTITY_CATALOG_SCAFFOLD_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_allowlisted_metadata_catalog(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass = FakeHass(metadata_by_entity=fake_entity_metadata(), states=fake_states())
    entry = FakeConfigEntry(
        options={
            "entity_allowlist": [
                "sensor.upstairs_temperature",
                "sensor.downstairs_temperature",
            ]
        }
    )
    result = setup_entity_catalog(hass, entry)
    item_validation = _validate_catalog_items(result["catalog"], root)
    store = hass.data[DOMAIN][entry.entry_id][DATA_ENTITY_CATALOG]
    return {
        "result": result,
        "catalog_entity_ids": [item["entity_id"] for item in result["catalog"]],
        "metadata_entity_ids": sorted(fake_entity_metadata()),
        "item_validation": item_validation,
        "store": summarize_entity_catalog_store(store),
    }


def verify_setup_entry_catalog_storage(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass = FakeHass(metadata_by_entity=fake_entity_metadata(), states=fake_states())
    entry = FakeConfigEntry(
        "setup-catalog-entry",
        options={
            "entity_allowlist": [
                "sensor.upstairs_temperature",
                "binary_sensor.office_window",
            ]
        },
    )
    setup_accepted = _run(async_setup_entry(hass, entry))
    entry_data = hass.data[DOMAIN][entry.entry_id]
    setup_result = entry_data[DATA_ENTITY_CATALOG_SETUP]
    store = entry_data[DATA_ENTITY_CATALOG]
    return {
        "setup_accepted": setup_accepted,
        "entry_id": entry.entry_id,
        "entry_data_keys": sorted(entry_data),
        "setup_result": setup_result,
        "store": summarize_entity_catalog_store(store),
        "item_validation": _validate_catalog_items(store["items"], root),
    }


def verify_config_entry_catalog_isolation(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass = FakeHass(metadata_by_entity=fake_entity_metadata(), states=fake_states())
    entry_a = FakeConfigEntry(
        "entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    result_a = setup_entity_catalog(hass, entry_a)
    result_b = setup_entity_catalog(hass, entry_b)
    store_a = hass.data[DOMAIN][entry_a.entry_id][DATA_ENTITY_CATALOG]
    store_b = hass.data[DOMAIN][entry_b.entry_id][DATA_ENTITY_CATALOG]
    return {
        "entry_a": result_a,
        "entry_b": result_b,
        "entry_a_store": summarize_entity_catalog_store(store_a),
        "entry_b_store": summarize_entity_catalog_store(store_b),
        "entry_a_validation": _validate_catalog_items(store_a["items"], root),
        "entry_b_validation": _validate_catalog_items(store_b["items"], root),
    }


def verify_unknown_allowlisted_entity_rejection() -> dict[str, Any]:
    hass = FakeHass(metadata_by_entity=fake_entity_metadata(), states=fake_states())
    entry = FakeConfigEntry(
        "missing-entity-entry",
        options={"entity_allowlist": ["sensor.missing_temperature"]},
    )
    result = setup_entity_catalog(hass, entry)
    store = hass.data[DOMAIN][entry.entry_id][DATA_ENTITY_CATALOG]
    return {
        "result": result,
        "store": summarize_entity_catalog_store(store),
    }


def verify_rejected_rebuild_clears_existing_catalog() -> dict[str, Any]:
    hass = FakeHass(metadata_by_entity=fake_entity_metadata(), states=fake_states())
    entry = FakeConfigEntry(
        "stale-rebuild-entry",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    accepted = setup_entity_catalog(hass, entry)
    store_after_success = summarize_entity_catalog_store(
        hass.data[DOMAIN][entry.entry_id][DATA_ENTITY_CATALOG]
    )

    entry.options = {"entity_allowlist": ["sensor.missing_temperature"]}
    rejected = setup_entity_catalog(hass, entry)
    store_after_rejection = summarize_entity_catalog_store(
        hass.data[DOMAIN][entry.entry_id][DATA_ENTITY_CATALOG]
    )
    return {
        "accepted": accepted,
        "store_after_success": store_after_success,
        "rejected": rejected,
        "store_after_rejection": store_after_rejection,
    }


def verify_malformed_allowlist_rejected_without_crash() -> dict[str, Any]:
    hass = FakeHass(metadata_by_entity=fake_entity_metadata(), states=fake_states())
    entry = FakeConfigEntry(
        "malformed-allowlist-entry",
        options={"entity_allowlist": [{"entity_id": "sensor.upstairs_temperature"}]},
    )
    result = setup_entity_catalog(hass, entry)
    store = hass.data[DOMAIN][entry.entry_id][DATA_ENTITY_CATALOG]
    return {
        "result": result,
        "store": summarize_entity_catalog_store(store),
    }


def verify_malformed_catalog_item_rejected_before_storage() -> dict[str, Any]:
    store = {
        "entry_id": "malformed-catalog-entry",
        "items": [],
        "entity_ids": [],
    }
    malformed_item = {
        "entity_id": "sensor.bad_catalog_item",
        "visible_to_agent": True,
    }
    result = store_validated_entity_catalog(store, [malformed_item])
    return {
        "malformed_item": malformed_item,
        "result": result,
        "store_after_attempt": summarize_entity_catalog_store(store),
        "raw_items_after_attempt": list(store["items"]),
    }


def verify_entity_catalog_side_effect_boundaries() -> dict[str, Any]:
    success = verify_allowlisted_metadata_catalog()
    setup = verify_setup_entry_catalog_storage()
    isolation = verify_config_entry_catalog_isolation()
    unknown = verify_unknown_allowlisted_entity_rejection()
    stale = verify_rejected_rebuild_clears_existing_catalog()
    malformed_allowlist = verify_malformed_allowlist_rejected_without_crash()
    malformed = verify_malformed_catalog_item_rejected_before_storage()

    observed = [
        {"name": "allowlisted_catalog", **success["result"]["orchestration"]},
        {"name": "setup_entry_catalog", **setup["setup_result"]["orchestration"]},
        {"name": "entry_a_catalog", **isolation["entry_a"]["orchestration"]},
        {"name": "entry_b_catalog", **isolation["entry_b"]["orchestration"]},
        {"name": "unknown_entity_rejection", **unknown["result"]["orchestration"]},
        {"name": "rejected_rebuild", **stale["rejected"]["orchestration"]},
        {"name": "malformed_allowlist", **malformed_allowlist["result"]["orchestration"]},
    ]
    if "orchestration" in malformed["result"]:
        observed.append({"name": "malformed_item_rejection", **malformed["result"]["orchestration"]})

    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in NO_ENTITY_CATALOG_ORCHESTRATION_CALLS
    }
    allowed_aggregate = {
        "entity_catalog_scaffold_written": any(item.get("entity_catalog_scaffold_written") for item in observed),
        "home_assistant_entity_metadata_read": any(item.get("home_assistant_entity_metadata_read") for item in observed),
    }
    return {
        "expected_forbidden": dict(NO_ENTITY_CATALOG_ORCHESTRATION_CALLS),
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }


def verify_entity_catalog_scaffold_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_entity_catalog_scaffold_files(root)
    catalog = verify_allowlisted_metadata_catalog(root)
    setup = verify_setup_entry_catalog_storage(root)
    isolation = verify_config_entry_catalog_isolation(root)
    unknown = verify_unknown_allowlisted_entity_rejection()
    stale = verify_rejected_rebuild_clears_existing_catalog()
    malformed_allowlist = verify_malformed_allowlist_rejected_without_crash()
    malformed = verify_malformed_catalog_item_rejected_before_storage()
    side_effects = verify_entity_catalog_side_effect_boundaries()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more approved entity catalog scaffold files are missing.")
    if not catalog["result"]["accepted"]:
        failures.append("Allowlisted catalog build was rejected.")
    if catalog["catalog_entity_ids"] != [
        "sensor.upstairs_temperature",
        "sensor.downstairs_temperature",
    ]:
        failures.append("Catalog did not contain exactly the configured allowlist.")
    if not all(item["accepted"] for item in catalog["item_validation"]):
        failures.append("One or more catalog items failed EntityCatalogItem validation.")
    if not setup["setup_accepted"] or not setup["setup_result"]["accepted"]:
        failures.append("async_setup_entry did not store an accepted catalog setup result.")
    if setup["store"]["entity_ids"] != [
        "sensor.upstairs_temperature",
        "binary_sensor.office_window",
    ]:
        failures.append("async_setup_entry catalog store does not match the entry allowlist.")
    if isolation["entry_a_store"]["entity_ids"] != ["sensor.upstairs_temperature"]:
        failures.append("Entry A catalog isolation failed.")
    if isolation["entry_b_store"]["entity_ids"] != ["binary_sensor.office_window"]:
        failures.append("Entry B catalog isolation failed.")
    if unknown["result"]["accepted"] or unknown["store"]["item_count"] != 0:
        failures.append("Unknown allowlisted entity was accepted or stored.")
    if stale["rejected"]["accepted"] or stale["store_after_rejection"]["item_count"] != 0:
        failures.append("Rejected rebuild left stale catalog items in the store.")
    if malformed_allowlist["result"]["accepted"] or malformed_allowlist["store"]["item_count"] != 0:
        failures.append("Malformed allowlist was accepted or stored.")
    if malformed_allowlist["result"]["code"] != "invalid_entity_allowlist":
        failures.append("Malformed allowlist did not return a structured invalid_entity_allowlist result.")
    if malformed["result"]["accepted"] or malformed["raw_items_after_attempt"]:
        failures.append("Malformed catalog item was stored before schema validation.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("Entity catalog scaffold reported forbidden orchestration side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("Entity catalog scaffold did not report expected allowed side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "catalog": catalog,
        "setup": setup,
        "isolation": isolation,
        "unknown": unknown,
        "stale": stale,
        "malformed_allowlist": malformed_allowlist,
        "malformed": malformed,
        "side_effects": side_effects,
    }


def _validate_catalog_items(items: list[dict[str, Any]], root) -> list[dict[str, Any]]:
    results = []
    for item in items:
        try:
            validate_contract("entity-catalog-item", item, repo_root=root)
        except ContractValidationError as exc:
            results.append(
                {
                    "accepted": False,
                    "code": "contract_validation_failed",
                    "entity_id": item.get("entity_id") if isinstance(item, dict) else None,
                    "error": str(exc),
                }
            )
        else:
            results.append(
                {
                    "accepted": True,
                    "code": "accepted",
                    "entity_id": item["entity_id"],
                    "visible_to_agent": item["visible_to_agent"],
                    "domain": item["domain"],
                }
            )
    return results


def _run(coro):
    return asyncio.run(coro)
