"""Storage-helper surface for durable worker health polling."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .const import DOMAIN
from .worker_health_polling_constants import (
    DATA_WORKER_HEALTH_POLLING,
    DATA_WORKER_HEALTH_POLLING_STORE,
    POLLING_STORAGE_KEY,
    POLLING_STORAGE_VERSION,
)
from .worker_health_polling_contract import _loaded_polling_entry_is_valid

try:
    from homeassistant.helpers.storage import Store as HomeAssistantStore
except ImportError:  # pragma: no cover - Home Assistant is absent in verifier tests.
    HomeAssistantStore = None


class WorkerHealthPollingStorageHelper:
    """Small JSON-safe storage-helper surface for durable polling state."""

    def __init__(self, *, ha_store: Any | None = None) -> None:
        self.storage_key = POLLING_STORAGE_KEY
        self.version = POLLING_STORAGE_VERSION
        self._ha_store = ha_store
        self.backend = (
            "home_assistant_storage_helper"
            if ha_store is not None
            else "in_memory_scaffold_storage_helper"
        )
        self.data: dict[str, Any] = {
            "version": self.version,
            "entries": {},
        }
        self._deleted_entry_ids: set[str] = set()

    async def async_load(self) -> dict[str, Any]:
        """Load persisted polling state when Home Assistant storage is available."""
        async_load = getattr(self._ha_store, "async_load", None)
        if not callable(async_load):
            return self.summary()

        loaded = await async_load()
        if (
            isinstance(loaded, dict)
            and loaded.get("version") == self.version
            and isinstance(loaded.get("entries"), dict)
        ):
            current_entries = self.data.setdefault("entries", {})
            for entry_id, state in loaded["entries"].items():
                if (
                    entry_id not in current_entries
                    and entry_id not in self._deleted_entry_ids
                    and _loaded_polling_entry_is_valid(entry_id, state)
                ):
                    current_entries[entry_id] = deepcopy(state)
        return self.summary()

    def read_state(self, entry_id: str) -> dict[str, Any] | None:
        state = self.data["entries"].get(entry_id)
        return deepcopy(state) if isinstance(state, dict) else None

    def write_state(self, entry_id: str, state: dict[str, Any]) -> None:
        self._deleted_entry_ids.discard(entry_id)
        self.data["entries"][entry_id] = deepcopy(state)
        self._schedule_save()

    def delete_state(self, entry_id: str) -> bool:
        self._deleted_entry_ids.add(entry_id)
        removed = self.data["entries"].pop(entry_id, None) is not None
        self._schedule_save()
        return removed

    def summary(self) -> dict[str, Any]:
        return {
            "storage_key": self.storage_key,
            "version": self.version,
            "backend": self.backend,
            "entry_ids": sorted(self.data["entries"]),
            "entry_count": len(self.data["entries"]),
        }

    def _schedule_save(self) -> None:
        async_delay_save = getattr(self._ha_store, "async_delay_save", None)
        if callable(async_delay_save):
            async_delay_save(lambda: deepcopy(self.data), 0)


def get_worker_health_polling_state(hass: Any, entry_id: str) -> dict[str, Any] | None:
    """Return the latest durable polling state for one config entry."""
    return get_worker_health_polling_storage(hass).read_state(entry_id)


def get_worker_health_polling_storage(hass: Any) -> WorkerHealthPollingStorageHelper:
    """Return the integration-owned worker health polling storage helper."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    store = domain_data.get(DATA_WORKER_HEALTH_POLLING_STORE)
    if isinstance(store, WorkerHealthPollingStorageHelper):
        return store
    store = WorkerHealthPollingStorageHelper(ha_store=_build_home_assistant_store(hass))
    domain_data[DATA_WORKER_HEALTH_POLLING_STORE] = store
    return store


def _write_polling_state(hass: Any, entry_id: str, state: dict[str, Any]) -> None:
    get_worker_health_polling_storage(hass).write_state(entry_id, state)
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    entry_data[DATA_WORKER_HEALTH_POLLING] = deepcopy(state)


def _build_home_assistant_store(hass: Any) -> Any | None:
    if HomeAssistantStore is None:
        return None
    return HomeAssistantStore(hass, POLLING_STORAGE_VERSION, POLLING_STORAGE_KEY)
