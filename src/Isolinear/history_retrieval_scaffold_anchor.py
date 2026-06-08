from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from custom_components.isolinear import async_setup_entry
from custom_components.isolinear.const import DOMAIN
from custom_components.isolinear.entity_catalog import (
    DATA_ENTITY_CATALOG,
    setup_entity_catalog,
)
from custom_components.isolinear.history_retrieval import (
    DATA_HISTORY_RETRIEVAL,
    DATA_HISTORY_RETRIEVAL_SETUP,
    DATA_HISTORY_SOURCE,
    NO_HISTORY_RETRIEVAL_ORCHESTRATION_CALLS,
    retrieve_approved_history,
    setup_history_retrieval,
    store_validated_history_series,
    summarize_history_retrieval_store,
)

from .contracts import ContractValidationError, validate_contract
from .dashboard_card_anchor import repo_root
from .entity_catalog_scaffold_anchor import (
    FakeConfigEntry,
    FakeHass,
    fake_entity_metadata,
    fake_states,
)


HISTORY_RETRIEVAL_SCAFFOLD_FILES = [
    "custom_components/isolinear/history_retrieval.py",
    "custom_components/isolinear/__init__.py",
    "docs/schemas/history-series.schema.json",
    "docs/specs/home-assistant-approved-history-retrieval-scaffold-spec.md",
    "bdd/integration/home-assistant-approved-history-retrieval-scaffold-bdd.md",
    "bdd/integration/home-assistant-approved-history-retrieval-scaffold-evidence.md",
    "docs/evals/home_assistant_approved_history_retrieval_scaffold.yaml",
    "tests/test_approved_history_retrieval_scaffold_anchor.py",
    "evals/home_assistant_approved_history_retrieval_scaffold.py",
]

NOW = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)


def iso_timestamp(timestamp: datetime) -> str:
    return timestamp.isoformat(timespec="seconds")


def history_time_range(now: datetime = NOW) -> dict[str, str]:
    return {
        "start": iso_timestamp(now - timedelta(hours=6)),
        "end": iso_timestamp(now),
    }


def fake_history_data(now: datetime = NOW) -> dict[str, list[dict[str, Any]]]:
    start = now - timedelta(hours=6)
    return {
        "sensor.upstairs_temperature": [
            _history_record("sensor.upstairs_temperature", "70.1", start),
            _history_record("sensor.upstairs_temperature", "unknown", start + timedelta(hours=2)),
            _history_record("sensor.upstairs_temperature", "71.4", start + timedelta(hours=4)),
            _history_record("sensor.upstairs_temperature", "72.0", now),
        ],
        "sensor.downstairs_temperature": [
            _history_record("sensor.downstairs_temperature", "68.5", start),
            _history_record("sensor.downstairs_temperature", "69.0", start + timedelta(hours=3)),
            _history_record("sensor.downstairs_temperature", "69.8", now),
        ],
        "binary_sensor.office_window": [
            _history_record("binary_sensor.office_window", "off", start),
            _history_record("binary_sensor.office_window", "on", start + timedelta(hours=1)),
            _history_record("binary_sensor.office_window", "off", start + timedelta(hours=5)),
        ],
        "light.kitchen": [
            _history_record("light.kitchen", "on", start),
            _history_record("light.kitchen", "off", now),
        ],
    }


def verify_history_retrieval_scaffold_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in HISTORY_RETRIEVAL_SCAFFOLD_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_approved_history_retrieval(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass = _fake_hass_with_history()
    entry = FakeConfigEntry(
        "history-entry",
        options={
            "entity_allowlist": [
                "sensor.upstairs_temperature",
                "binary_sensor.office_window",
            ]
        },
    )
    setup_entity_catalog(hass, entry)
    setup_history_retrieval(hass, entry)
    result = retrieve_approved_history(
        hass,
        entry,
        entity_ids=["sensor.upstairs_temperature", "binary_sensor.office_window"],
        **history_time_range(),
    )
    store = hass.data[DOMAIN][entry.entry_id][DATA_HISTORY_RETRIEVAL]
    return {
        "result": result,
        "history_source_entity_ids": sorted(fake_history_data()),
        "returned_entity_ids": [series["entity_id"] for series in result["history_series"]],
        "series_validation": _validate_history_series(result["history_series"], root),
        "store": summarize_history_retrieval_store(store),
    }


def verify_setup_entry_history_storage(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass = _fake_hass_with_history()
    entry = FakeConfigEntry(
        "setup-history-entry",
        options={
            "entity_allowlist": [
                "sensor.upstairs_temperature",
                "binary_sensor.office_window",
            ]
        },
    )
    setup_accepted = _run(async_setup_entry(hass, entry))
    entry_data = hass.data[DOMAIN][entry.entry_id]
    setup_result = entry_data[DATA_HISTORY_RETRIEVAL_SETUP]
    store = entry_data[DATA_HISTORY_RETRIEVAL]
    return {
        "setup_accepted": setup_accepted,
        "entry_id": entry.entry_id,
        "entry_data_keys": sorted(entry_data),
        "setup_result": setup_result,
        "catalog_store": {
            "entity_ids": list(entry_data[DATA_ENTITY_CATALOG]["entity_ids"]),
        },
        "store": summarize_history_retrieval_store(store),
        "files": verify_history_retrieval_scaffold_files(root),
    }


def verify_config_entry_history_isolation(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass = _fake_hass_with_history()
    entry_a = FakeConfigEntry(
        "history-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "history-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    setup_entity_catalog(hass, entry_a)
    setup_entity_catalog(hass, entry_b)
    setup_history_retrieval(hass, entry_a)
    setup_history_retrieval(hass, entry_b)

    result_a = retrieve_approved_history(
        hass,
        entry_a,
        entity_ids=["sensor.upstairs_temperature"],
        **history_time_range(),
    )
    result_b = retrieve_approved_history(
        hass,
        entry_b,
        entity_ids=["binary_sensor.office_window"],
        **history_time_range(),
    )
    store_a = hass.data[DOMAIN][entry_a.entry_id][DATA_HISTORY_RETRIEVAL]
    store_b = hass.data[DOMAIN][entry_b.entry_id][DATA_HISTORY_RETRIEVAL]
    return {
        "entry_a": result_a,
        "entry_b": result_b,
        "entry_a_store": summarize_history_retrieval_store(store_a),
        "entry_b_store": summarize_history_retrieval_store(store_b),
        "entry_a_validation": _validate_history_series(result_a["history_series"], root),
        "entry_b_validation": _validate_history_series(result_b["history_series"], root),
    }


def verify_non_catalog_entity_rejection() -> dict[str, Any]:
    hass = _fake_hass_with_history()
    entry = FakeConfigEntry(
        "non-catalog-history-entry",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    setup_entity_catalog(hass, entry)
    setup_history_retrieval(hass, entry)
    result = retrieve_approved_history(
        hass,
        entry,
        entity_ids=["light.kitchen"],
        **history_time_range(),
    )
    store = hass.data[DOMAIN][entry.entry_id][DATA_HISTORY_RETRIEVAL]
    return {
        "result": result,
        "store": summarize_history_retrieval_store(store),
    }


def verify_rejected_retrieval_clears_existing_history() -> dict[str, Any]:
    hass = _fake_hass_with_history()
    entry = FakeConfigEntry(
        "stale-history-entry",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    setup_entity_catalog(hass, entry)
    setup_history_retrieval(hass, entry)
    accepted = retrieve_approved_history(
        hass,
        entry,
        entity_ids=["sensor.upstairs_temperature"],
        **history_time_range(),
    )
    store_after_success = summarize_history_retrieval_store(
        hass.data[DOMAIN][entry.entry_id][DATA_HISTORY_RETRIEVAL]
    )
    rejected = retrieve_approved_history(
        hass,
        entry,
        entity_ids=["light.kitchen"],
        **history_time_range(),
    )
    store_after_rejection = summarize_history_retrieval_store(
        hass.data[DOMAIN][entry.entry_id][DATA_HISTORY_RETRIEVAL]
    )
    return {
        "accepted": accepted,
        "store_after_success": store_after_success,
        "rejected": rejected,
        "store_after_rejection": store_after_rejection,
    }


def verify_malformed_raw_history_rejection() -> dict[str, Any]:
    hass = _fake_hass_with_history()
    entry = FakeConfigEntry(
        "malformed-raw-history-entry",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    setup_entity_catalog(hass, entry)
    setup_history_retrieval(hass, entry)
    malformed_history = deepcopy(fake_history_data())
    malformed_history["sensor.upstairs_temperature"] = [
        {
            "entity_id": "sensor.upstairs_temperature",
            "state": "70.1",
            "last_changed": "not-a-date",
        }
    ]
    result = retrieve_approved_history(
        hass,
        entry,
        entity_ids=["sensor.upstairs_temperature"],
        history_by_entity=malformed_history,
        **history_time_range(),
    )
    store = hass.data[DOMAIN][entry.entry_id][DATA_HISTORY_RETRIEVAL]
    return {
        "result": result,
        "store": summarize_history_retrieval_store(store),
    }


def verify_malformed_history_series_rejected_before_storage() -> dict[str, Any]:
    store = {
        "entry_id": "malformed-history-entry",
        "series": [],
        "entity_ids": [],
        "request_count": 0,
        "last_time_range": None,
    }
    malformed_series = {
        "series_id": "bad_history_series",
        "kind": "numeric",
    }
    result = store_validated_history_series(store, [malformed_series])
    return {
        "malformed_series": malformed_series,
        "result": result,
        "store_after_attempt": summarize_history_retrieval_store(store),
        "raw_series_after_attempt": list(store["series"]),
    }


def verify_history_retrieval_side_effect_boundaries() -> dict[str, Any]:
    success = verify_approved_history_retrieval()
    setup = verify_setup_entry_history_storage()
    isolation = verify_config_entry_history_isolation()
    non_catalog = verify_non_catalog_entity_rejection()
    stale = verify_rejected_retrieval_clears_existing_history()
    malformed_raw = verify_malformed_raw_history_rejection()

    observed = [
        {"name": "approved_history", **success["result"]["orchestration"]},
        {"name": "setup_history", **setup["setup_result"]["orchestration"]},
        {"name": "entry_a_history", **isolation["entry_a"]["orchestration"]},
        {"name": "entry_b_history", **isolation["entry_b"]["orchestration"]},
        {"name": "non_catalog_rejection", **non_catalog["result"]["orchestration"]},
        {"name": "rejected_retrieval", **stale["rejected"]["orchestration"]},
        {"name": "malformed_raw_rejection", **malformed_raw["result"]["orchestration"]},
    ]

    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in NO_HISTORY_RETRIEVAL_ORCHESTRATION_CALLS
    }
    allowed_aggregate = {
        "approved_entity_catalog_read": any(item.get("approved_entity_catalog_read") for item in observed),
        "home_assistant_history_read": any(item.get("home_assistant_history_read") for item in observed),
        "history_retrieval_scaffold_written": any(
            item.get("history_retrieval_scaffold_written") for item in observed
        ),
    }
    return {
        "expected_forbidden": dict(NO_HISTORY_RETRIEVAL_ORCHESTRATION_CALLS),
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }


def verify_history_retrieval_scaffold_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_history_retrieval_scaffold_files(root)
    retrieval = verify_approved_history_retrieval(root)
    setup = verify_setup_entry_history_storage(root)
    isolation = verify_config_entry_history_isolation(root)
    non_catalog = verify_non_catalog_entity_rejection()
    stale = verify_rejected_retrieval_clears_existing_history()
    malformed_raw = verify_malformed_raw_history_rejection()
    malformed_series = verify_malformed_history_series_rejected_before_storage()
    side_effects = verify_history_retrieval_side_effect_boundaries()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more approved history retrieval scaffold files are missing.")
    if not retrieval["result"]["accepted"]:
        failures.append("Approved history retrieval was rejected.")
    if retrieval["returned_entity_ids"] != [
        "sensor.upstairs_temperature",
        "binary_sensor.office_window",
    ]:
        failures.append("History retrieval did not return exactly the requested approved entities.")
    if "light.kitchen" in retrieval["returned_entity_ids"]:
        failures.append("History retrieval returned non-approved entity history.")
    if not all(item["accepted"] for item in retrieval["series_validation"]):
        failures.append("One or more retrieved series failed HistorySeries validation.")
    if not setup["setup_accepted"] or not setup["setup_result"]["accepted"]:
        failures.append("async_setup_entry did not store an accepted history retrieval setup result.")
    if setup["store"]["entry_id"] != "setup-history-entry":
        failures.append("async_setup_entry history store was not config-entry scoped.")
    if isolation["entry_a_store"]["entity_ids"] != ["sensor.upstairs_temperature"]:
        failures.append("Entry A history isolation failed.")
    if isolation["entry_b_store"]["entity_ids"] != ["binary_sensor.office_window"]:
        failures.append("Entry B history isolation failed.")
    if non_catalog["result"]["accepted"] or non_catalog["store"]["series_count"] != 0:
        failures.append("Non-catalog requested entity was accepted or stored.")
    if non_catalog["result"]["orchestration"]["home_assistant_history_read"]:
        failures.append("Non-catalog requested entity read history before rejection.")
    if stale["rejected"]["accepted"] or stale["store_after_rejection"]["series_count"] != 0:
        failures.append("Rejected retrieval left stale history series in the store.")
    if malformed_raw["result"]["accepted"] or malformed_raw["store"]["series_count"] != 0:
        failures.append("Malformed raw history was accepted or stored.")
    if malformed_raw["result"]["code"] != "invalid_history_records":
        failures.append("Malformed raw history did not return invalid_history_records.")
    if malformed_series["result"]["accepted"] or malformed_series["raw_series_after_attempt"]:
        failures.append("Malformed history series was stored before schema validation.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("History retrieval scaffold reported forbidden orchestration side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("History retrieval scaffold did not report expected allowed side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "retrieval": retrieval,
        "setup": setup,
        "isolation": isolation,
        "non_catalog": non_catalog,
        "stale": stale,
        "malformed_raw": malformed_raw,
        "malformed_series": malformed_series,
        "side_effects": side_effects,
    }


def _history_record(entity_id: str, state: Any, timestamp: datetime) -> dict[str, Any]:
    return {
        "entity_id": entity_id,
        "state": state,
        "last_changed": iso_timestamp(timestamp),
        "attributes": {},
    }


def _fake_hass_with_history() -> FakeHass:
    hass = FakeHass(metadata_by_entity=fake_entity_metadata(), states=fake_states())
    hass.data[DOMAIN][DATA_HISTORY_SOURCE] = fake_history_data()
    return hass


def _validate_history_series(series: list[dict[str, Any]], root) -> list[dict[str, Any]]:
    results = []
    for item in series:
        try:
            validate_contract("history-series", item, repo_root=root)
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
                    "series_id": item["series_id"],
                    "kind": item["kind"],
                    "point_count": len(item.get("points", [])),
                }
            )
    return results


def _run(coro):
    return asyncio.run(coro)
