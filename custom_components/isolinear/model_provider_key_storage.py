"""Model-provider API key storage (ADR-0037).

The bearer key for the OpenAI-compatible (LiteLLM) provider is deployment
configuration: the user pastes it into a write-only options-flow field, and
it persists here — an integration-owned HA Store, never config-entry data or
options (the secret-vocabulary fail-closed check in ``config_schema.py`` stays
intact). Mirrors the ADR-0032 worker-token pattern exactly.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .const import DOMAIN

try:  # pragma: no cover - import guard mirrors worker_token_storage
    from homeassistant.helpers.storage import Store as HomeAssistantStore
except ImportError:  # pragma: no cover - unit tests run without HA installed
    HomeAssistantStore = None  # type: ignore[assignment]

PROVIDER_KEY_STORAGE_KEY = "isolinear_model_provider_key"
PROVIDER_KEY_STORAGE_VERSION = 1
DATA_PROVIDER_KEY_STORE = "model_provider_key_storage_helper"


class ModelProviderKeyStorageHelper:
    """Per-config-entry model-provider API key store.

    One Home Assistant ``Store`` document holds every config entry's key,
    keyed by ``config_entry_id``. When no ``ha_store`` is supplied an in-memory
    backend is used (tests / scaffold) — mirroring the worker-token helper.
    """

    def __init__(self, *, ha_store: Any | None = None) -> None:
        self.storage_key = PROVIDER_KEY_STORAGE_KEY
        self.version = PROVIDER_KEY_STORAGE_VERSION
        self._ha_store = ha_store
        self.backend = (
            "home_assistant_storage_helper"
            if ha_store is not None
            else "in_memory_scaffold_storage_helper"
        )
        self.data: dict[str, Any] = {"version": self.version, "keys": {}}

    async def async_load(self) -> dict[str, Any]:
        """Load persisted keys when HA storage is available."""
        async_load = getattr(self._ha_store, "async_load", None)
        if not callable(async_load):
            return self.summary()

        loaded = await async_load()
        if (
            isinstance(loaded, dict)
            and loaded.get("version") == self.version
            and isinstance(loaded.get("keys"), dict)
        ):
            keys = self.data.setdefault("keys", {})
            for entry_id, key in loaded["keys"].items():
                if entry_id not in keys and isinstance(key, str) and key.strip():
                    keys[entry_id] = key.strip()
        return self.summary()

    def key_for(self, entry_id: str) -> str | None:
        """Return the stored API key for one config entry, if any."""
        key = self.data["keys"].get(entry_id)
        return key if isinstance(key, str) and key.strip() else None

    def save_key(self, entry_id: str, key: str) -> dict[str, Any]:
        """Persist one entry's API key (synchronous; mirrors save_token)."""
        stripped = key.strip() if isinstance(key, str) else ""
        if not stripped:
            return {"accepted": False, "error": "provider_key_empty"}
        self.data["keys"][entry_id] = stripped
        self._schedule_save()
        return {"accepted": True}

    def clear_key(self, entry_id: str) -> dict[str, Any]:
        """Remove one entry's API key."""
        self.data["keys"].pop(entry_id, None)
        self._schedule_save()
        return {"accepted": True}

    def _schedule_save(self) -> None:
        async_delay_save = getattr(self._ha_store, "async_delay_save", None)
        if callable(async_delay_save):
            async_delay_save(lambda: deepcopy(self.data), 0)

    def summary(self) -> dict[str, Any]:
        # Key VALUES never appear in the summary — presence only.
        return {
            "storage_key": self.storage_key,
            "version": self.version,
            "backend": self.backend,
            "entry_ids": sorted(self.data["keys"]),
            "entry_count": len(self.data["keys"]),
        }


def get_model_provider_key_storage(hass: Any) -> ModelProviderKeyStorageHelper:
    """Return the integration-owned provider-key storage helper (cached)."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    helper = domain_data.get(DATA_PROVIDER_KEY_STORE)
    if isinstance(helper, ModelProviderKeyStorageHelper):
        return helper
    helper = ModelProviderKeyStorageHelper(ha_store=_build_home_assistant_store(hass))
    domain_data[DATA_PROVIDER_KEY_STORE] = helper
    return helper


def stored_model_provider_key(hass: Any, entry_id: str) -> str | None:
    """The single read surface planner setup uses (ADR-0037)."""
    return get_model_provider_key_storage(hass).key_for(entry_id)


async def async_setup_model_provider_key_storage(hass: Any, entry: Any) -> dict[str, Any]:
    """Load persisted provider keys so planner setup can read them."""
    helper = get_model_provider_key_storage(hass)
    await helper.async_load()
    return {
        "accepted": True,
        "code": "model_provider_key_storage_loaded",
        "summary": helper.summary(),
    }


def _build_home_assistant_store(hass: Any) -> Any | None:
    if HomeAssistantStore is None:
        return None
    return HomeAssistantStore(
        hass, PROVIDER_KEY_STORAGE_VERSION, PROVIDER_KEY_STORAGE_KEY
    )
