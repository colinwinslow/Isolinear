from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from custom_components.isolinear import async_setup_entry
from custom_components.isolinear.dashboard_resource import (
    CARD_BUNDLE_FILENAME,
    CARD_RESOURCE_TYPE,
    CARD_RESOURCE_URL,
    CARD_STATIC_URL_PATH,
    NO_RESOURCE_ORCHESTRATION_CALLS,
    async_register_dashboard_resource,
    dashboard_resource_metadata,
    frontend_dist_path,
)

from .dashboard_card_anchor import repo_root


DASHBOARD_RESOURCE_FILES = [
    "custom_components/isolinear/dashboard_resource.py",
    "custom_components/isolinear/__init__.py",
    "custom_components/isolinear/frontend/dist/isolinear-card.js",
]


@dataclass
class FakeConfigEntry:
    entry_id: str = "resource-entry-001"


class FakeHttp:
    def __init__(self) -> None:
        self.static_path_calls: list[list[Any]] = []

    async def async_register_static_paths(self, paths: list[Any]) -> None:
        self.static_path_calls.append(paths)


class FakeLovelaceResources:
    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        self.loaded = True
        self._items = list(items or [])
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
    def __init__(self, resources: FakeLovelaceResources | None = None) -> None:
        self.data: dict[str, Any] = {}
        self.http = FakeHttp()
        if resources is not None:
            self.data["lovelace"] = SimpleNamespace(resources=resources)


def verify_static_path_registration(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    resources = FakeLovelaceResources()
    hass = FakeHass(resources)
    result = _run(
        async_register_dashboard_resource(
            hass,
            FakeConfigEntry(),
            bundle_dir=frontend_dist_path(root),
        )
    )
    return {
        "accepted": result["accepted"],
        "code": result["code"],
        "bundle_exists": (frontend_dist_path(root) / CARD_BUNDLE_FILENAME).is_file(),
        "static_path": result.get("static_path"),
        "resource": dashboard_resource_metadata(),
        "resource_result": result.get("resource"),
        "result": result,
        "static_path_call_count": len(hass.http.static_path_calls),
    }


def verify_setup_entry_registration(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    resources = FakeLovelaceResources()
    hass = FakeHass(resources)
    entry = FakeConfigEntry()
    setup_accepted = _run(async_setup_entry(hass, entry))
    entry_result = hass.data["isolinear"][entry.entry_id]["dashboard_resource"]
    return {
        "setup_accepted": setup_accepted,
        "entry_id": entry.entry_id,
        "entry_result": entry_result,
        "resources": resources.async_items(),
        "static_path_call_count": len(hass.http.static_path_calls),
        "bundle_exists": (frontend_dist_path(root) / CARD_BUNDLE_FILENAME).is_file(),
    }


def verify_idempotent_registration(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    resources = FakeLovelaceResources()
    hass = FakeHass(resources)
    entry = FakeConfigEntry()
    first = _run(
        async_register_dashboard_resource(
            hass,
            entry,
            bundle_dir=frontend_dist_path(root),
        )
    )
    second = _run(
        async_register_dashboard_resource(
            hass,
            entry,
            bundle_dir=frontend_dist_path(root),
        )
    )
    return {
        "first": first,
        "second": second,
        "resources": resources.async_items(),
        "resource_count": _matching_resource_count(resources.async_items()),
        "create_call_count": len(resources.create_calls),
        "static_path_call_count": len(hass.http.static_path_calls),
    }


def verify_preexisting_resource_reuse(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    resources = FakeLovelaceResources(
        [
            {
                "id": "resource-existing",
                "url": CARD_RESOURCE_URL,
                "type": CARD_RESOURCE_TYPE,
            }
        ]
    )
    hass = FakeHass(resources)
    result = _run(
        async_register_dashboard_resource(
            hass,
            FakeConfigEntry(),
            bundle_dir=frontend_dist_path(root),
        )
    )
    return {
        "accepted": result["accepted"],
        "result": result,
        "preexisting_reused": result["resource"].get("id") == "resource-existing",
        "resources": resources.async_items(),
        "resource_count": _matching_resource_count(resources.async_items()),
        "create_call_count": len(resources.create_calls),
        "static_path_call_count": len(hass.http.static_path_calls),
    }


def verify_missing_bundle_rejection(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    resources = FakeLovelaceResources()
    hass = FakeHass(resources)
    missing_bundle_dir = root / ".missing-isolinear-card-bundle"
    result = _run(
        async_register_dashboard_resource(
            hass,
            FakeConfigEntry(),
            bundle_dir=missing_bundle_dir,
        )
    )
    return {
        "accepted": result["accepted"],
        "code": result["code"],
        "resources": resources.async_items(),
        "create_call_count": len(resources.create_calls),
        "static_path_call_count": len(hass.http.static_path_calls),
        "result": result,
    }


def verify_unavailable_resource_collection_rejection(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    hass = FakeHass(None)
    result = _run(
        async_register_dashboard_resource(
            hass,
            FakeConfigEntry(),
            bundle_dir=frontend_dist_path(root),
        )
    )
    return {
        "accepted": result["accepted"],
        "code": result["code"],
        "create_call_count": 0,
        "resource_count": 0,
        "static_path_call_count": len(hass.http.static_path_calls),
        "result": result,
    }


def verify_resource_side_effects(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    observed_results = [
        {"name": "static_path_registration", **verify_static_path_registration(root)["result"]["orchestration"]},
        {"name": "setup_entry_registration", **verify_setup_entry_registration(root)["entry_result"]["orchestration"]},
        {"name": "idempotent_registration_first", **verify_idempotent_registration(root)["first"]["orchestration"]},
        {"name": "idempotent_registration_second", **verify_idempotent_registration(root)["second"]["orchestration"]},
        {"name": "missing_bundle_rejection", **verify_missing_bundle_rejection(root)["result"]["orchestration"]},
    ]
    aggregate = {
        key: any(item.get(key) for item in observed_results)
        for key in NO_RESOURCE_ORCHESTRATION_CALLS
    }
    return {
        "expected": dict(NO_RESOURCE_ORCHESTRATION_CALLS),
        "observed": observed_results,
        "aggregate": aggregate,
        "allowed_side_effects": {
            "static_path_registered": True,
            "dashboard_resource_metadata_written_or_reused": True,
        },
    }


def verify_dashboard_resource_files(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in DASHBOARD_RESOURCE_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
        "bundle_path": str(frontend_dist_path(root) / CARD_BUNDLE_FILENAME),
        "resource_url": CARD_RESOURCE_URL,
        "static_path_url": CARD_STATIC_URL_PATH,
    }


def verify_dashboard_resource_anchor(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_dashboard_resource_files(root)
    static_path = verify_static_path_registration(root)
    setup_entry = verify_setup_entry_registration(root)
    idempotence = verify_idempotent_registration(root)
    preexisting = verify_preexisting_resource_reuse(root)
    missing_bundle = verify_missing_bundle_rejection(root)
    unavailable_collection = verify_unavailable_resource_collection_rejection(root)
    side_effects = verify_resource_side_effects(root)

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more dashboard resource anchor files are missing.")
    if not static_path["accepted"]:
        failures.append("Static path registration was rejected.")
    if static_path["static_path"]["url_path"] != CARD_STATIC_URL_PATH:
        failures.append("Static path URL does not match the expected integration path.")
    if not setup_entry["setup_accepted"] or not setup_entry["entry_result"]["accepted"]:
        failures.append("Config entry setup did not store an accepted registration result.")
    if setup_entry["resources"].count(setup_entry["resources"][0]) != 1 and setup_entry["resources"]:
        failures.append("Config entry setup produced duplicate resource items.")
    if idempotence["resource_count"] != 1 or idempotence["create_call_count"] != 1:
        failures.append("Repeated registration was not idempotent.")
    if not preexisting["preexisting_reused"] or preexisting["create_call_count"] != 0:
        failures.append("Pre-existing dashboard resource metadata was not reused.")
    if missing_bundle["accepted"] or missing_bundle["create_call_count"] != 0:
        failures.append("Missing bundle did not fail closed before metadata creation.")
    if unavailable_collection["accepted"]:
        failures.append("Unavailable resource collection did not fail closed.")
    if any(side_effects["aggregate"].values()):
        failures.append("Dashboard resource registration reported orchestration side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "static_path": static_path,
        "setup_entry": setup_entry,
        "idempotence": idempotence,
        "preexisting": preexisting,
        "missing_bundle": missing_bundle,
        "unavailable_collection": unavailable_collection,
        "side_effects": side_effects,
    }


def _matching_resource_count(items: list[dict[str, Any]]) -> int:
    return sum(
        1
        for item in items
        if item.get("url") == CARD_RESOURCE_URL and item.get("type") == CARD_RESOURCE_TYPE
    )


def _run(coro):
    return asyncio.run(coro)
