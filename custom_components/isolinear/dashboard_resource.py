"""Dashboard resource registration for the Isolinear Home Assistant card."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .const import DOMAIN


try:  # pragma: no cover - exercised by Home Assistant, not repo tests.
    from homeassistant.components.http import StaticPathConfig
except ImportError:  # pragma: no cover - deterministic fallback for repo tests.

    @dataclass(frozen=True)
    class StaticPathConfig:
        """Fallback shape matching Home Assistant's static path config."""

        url_path: str
        path: str
        cache_headers: bool


CARD_BUNDLE_FILENAME = "isolinear-card.js"
CARD_STATIC_URL_PATH = f"/api/{DOMAIN}/static"
CARD_RESOURCE_URL = f"{CARD_STATIC_URL_PATH}/{CARD_BUNDLE_FILENAME}"
CARD_RESOURCE_TYPE = "module"

DATA_DASHBOARD_RESOURCE = "dashboard_resource"
DATA_STATIC_PATHS = "static_paths"

NO_RESOURCE_ORCHESTRATION_CALLS = {
    "worker_called": False,
    "model_provider_called": False,
    "home_assistant_history_called": False,
    "semantic_memory_called": False,
    "home_assistant_service_or_state_mutation_called": False,
    "token_generated": False,
    "job_orchestration_called": False,
    "websocket_command_registered": False,
}


def frontend_dist_path(root: Path | None = None) -> Path:
    """Return the checked-in dashboard card bundle directory."""
    if root is not None:
        return root / "frontend" / "dist"
    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


def dashboard_resource_metadata() -> dict[str, str]:
    """Return the Lovelace resource metadata for the Isolinear card."""
    return {
        "url": CARD_RESOURCE_URL,
        "type": CARD_RESOURCE_TYPE,
    }


async def async_register_dashboard_resource(
    hass: Any,
    entry: Any | None = None,
    *,
    bundle_dir: Path | None = None,
    resource_collection: Any | None = None,
) -> dict[str, Any]:
    """Serve and register the Isolinear dashboard card resource."""
    entry_id = getattr(entry, "entry_id", None)
    bundle_directory = bundle_dir or frontend_dist_path()
    bundle_path = bundle_directory / CARD_BUNDLE_FILENAME

    if not bundle_path.is_file():
        return _resource_rejection(
            "dashboard_card_bundle_missing",
            entry_id=entry_id,
            bundle_path=bundle_path,
        )

    collection = resource_collection or _resolve_lovelace_resource_collection(hass)
    if collection is None or not hasattr(collection, "async_items"):
        return _resource_rejection(
            "lovelace_resource_collection_unavailable",
            entry_id=entry_id,
            bundle_path=bundle_path,
        )

    await _ensure_collection_loaded(collection)
    static_path = await async_register_card_static_path(hass, bundle_directory)
    if static_path["code"] == "static_path_registration_unavailable":
        return _resource_rejection(
            "static_path_registration_unavailable",
            entry_id=entry_id,
            bundle_path=bundle_path,
            static_path=static_path,
        )

    existing = await _find_existing_resource(collection)
    if existing is not None:
        return _resource_success(
            "dashboard_resource_already_registered",
            entry_id=entry_id,
            bundle_path=bundle_path,
            static_path=static_path,
            resource=existing,
            created=False,
            reused=True,
        )

    if not hasattr(collection, "async_create_item"):
        return _resource_rejection(
            "lovelace_resource_collection_unavailable",
            entry_id=entry_id,
            bundle_path=bundle_path,
        )

    created = await collection.async_create_item(
        {
            "url": CARD_RESOURCE_URL,
            "res_type": CARD_RESOURCE_TYPE,
        }
    )
    return _resource_success(
        "dashboard_resource_registered",
        entry_id=entry_id,
        bundle_path=bundle_path,
        static_path=static_path,
        resource=_normalize_resource_item(created),
        created=True,
        reused=False,
    )


async def async_register_card_static_path(hass: Any, bundle_dir: Path) -> dict[str, Any]:
    """Register the static path for the bundled card assets once."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    static_paths = domain_data.setdefault(DATA_STATIC_PATHS, {})
    cached = static_paths.get(CARD_STATIC_URL_PATH)
    if cached is not None:
        return {
            **cached,
            "code": "static_path_already_registered",
            "call_made": False,
        }

    config = StaticPathConfig(CARD_STATIC_URL_PATH, str(bundle_dir), True)
    http = getattr(hass, "http", None)
    if http is None or not hasattr(http, "async_register_static_paths"):
        return {
            "code": "static_path_registration_unavailable",
            "url_path": CARD_STATIC_URL_PATH,
            "path": str(bundle_dir),
            "cache_headers": True,
            "call_made": False,
        }

    await http.async_register_static_paths([config])
    result = {
        "code": "static_path_registered",
        "url_path": CARD_STATIC_URL_PATH,
        "path": str(bundle_dir),
        "cache_headers": True,
        "call_made": True,
    }
    static_paths[CARD_STATIC_URL_PATH] = result
    return result


def _resolve_lovelace_resource_collection(hass: Any) -> Any | None:
    lovelace_data = getattr(hass, "data", {}).get("lovelace")
    if lovelace_data is None:
        return None
    if isinstance(lovelace_data, dict):
        return lovelace_data.get("resources")
    return getattr(lovelace_data, "resources", None)


async def _ensure_collection_loaded(collection: Any) -> None:
    if getattr(collection, "loaded", True):
        return
    loader = getattr(collection, "async_load", None)
    if loader is not None:
        result = loader()
        if inspect.isawaitable(result):
            await result
    if hasattr(collection, "loaded"):
        collection.loaded = True


async def _find_existing_resource(collection: Any) -> dict[str, Any] | None:
    for item in await _collection_items(collection):
        resource = _normalize_resource_item(item)
        if (
            resource.get("url") == CARD_RESOURCE_URL
            and resource.get("type") == CARD_RESOURCE_TYPE
        ):
            return resource
    return None


async def _collection_items(collection: Any) -> list[dict[str, Any]]:
    items = collection.async_items()
    if inspect.isawaitable(items):
        items = await items
    return list(items or [])


def _normalize_resource_item(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return dashboard_resource_metadata()
    normalized = dict(item)
    if "type" not in normalized and "res_type" in normalized:
        normalized["type"] = normalized["res_type"]
    return {
        key: value
        for key, value in normalized.items()
        if key in {"id", "url", "type"}
    }


def _resource_success(
    code: str,
    *,
    entry_id: str | None,
    bundle_path: Path,
    static_path: dict[str, Any],
    resource: dict[str, Any],
    created: bool,
    reused: bool,
) -> dict[str, Any]:
    return {
        "accepted": True,
        "code": code,
        "entry_id": entry_id,
        "config_entry_scoped": entry_id is not None,
        "bundle_path": str(bundle_path),
        "resource": resource,
        "static_path": static_path,
        "resource_created": created,
        "resource_reused": reused,
        "orchestration": dict(NO_RESOURCE_ORCHESTRATION_CALLS),
    }


def _resource_rejection(
    code: str,
    *,
    entry_id: str | None,
    bundle_path: Path,
    static_path: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "accepted": False,
        "code": code,
        "entry_id": entry_id,
        "config_entry_scoped": entry_id is not None,
        "bundle_path": str(bundle_path),
        "resource": dashboard_resource_metadata(),
        "resource_created": False,
        "resource_reused": False,
        "orchestration": dict(NO_RESOURCE_ORCHESTRATION_CALLS),
    }
    if static_path is not None:
        result["static_path"] = static_path
    return result
