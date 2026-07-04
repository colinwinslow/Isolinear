"""Deployment-supplied worker token storage (ADR-0032).

The worker bearer token is deployment configuration: the user pastes the token
the worker was deployed with (12-factor ``ISOLINEAR_WORKER_TOKEN``) into a
write-only options-flow field, and it persists here — an integration-owned HA
Store, never config-entry data or options (the secret-vocabulary fail-closed
check in ``config_schema.py`` stays intact). The integration never generates,
rotates, or repairs a token; rotation is a deployment action plus a re-paste.

Replaces the retired ADR-0015/0016 self-provisioned token lifecycle.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .const import DOMAIN

try:  # pragma: no cover - import guard mirrors semantic_memory
    from homeassistant.helpers.storage import Store as HomeAssistantStore
except ImportError:  # pragma: no cover - unit tests run without HA installed
    HomeAssistantStore = None  # type: ignore[assignment]

WORKER_TOKEN_STORAGE_KEY = "isolinear_worker_deployment_token"
WORKER_TOKEN_STORAGE_VERSION = 1
DATA_WORKER_TOKEN_STORE = "worker_token_storage_helper"

# Same floor the worker's own startup enforces on ISOLINEAR_WORKER_TOKEN.
MIN_WORKER_TOKEN_LENGTH = 24


def is_valid_deployment_worker_token(token: Any) -> bool:
    """True when ``token`` meets the worker's own minimum-length contract."""
    return isinstance(token, str) and len(token.strip()) >= MIN_WORKER_TOKEN_LENGTH


class WorkerTokenStorageHelper:
    """Per-config-entry deployment worker token store.

    One Home Assistant ``Store`` document holds every config entry's token,
    keyed by ``config_entry_id``. When no ``ha_store`` is supplied an in-memory
    backend is used (tests / scaffold) — mirroring the semantic-memory helper.
    """

    def __init__(self, *, ha_store: Any | None = None) -> None:
        self.storage_key = WORKER_TOKEN_STORAGE_KEY
        self.version = WORKER_TOKEN_STORAGE_VERSION
        self._ha_store = ha_store
        self.backend = (
            "home_assistant_storage_helper"
            if ha_store is not None
            else "in_memory_scaffold_storage_helper"
        )
        self.data: dict[str, Any] = {"version": self.version, "tokens": {}}

    async def async_load(self) -> dict[str, Any]:
        """Load persisted tokens when HA storage is available."""
        async_load = getattr(self._ha_store, "async_load", None)
        if not callable(async_load):
            return self.summary()

        loaded = await async_load()
        if (
            isinstance(loaded, dict)
            and loaded.get("version") == self.version
            and isinstance(loaded.get("tokens"), dict)
        ):
            tokens = self.data.setdefault("tokens", {})
            for entry_id, token in loaded["tokens"].items():
                if entry_id not in tokens and is_valid_deployment_worker_token(token):
                    tokens[entry_id] = token
        return self.summary()

    def token_for(self, entry_id: str) -> str | None:
        """Return the stored deployment token for one config entry, if any."""
        token = self.data["tokens"].get(entry_id)
        return token if is_valid_deployment_worker_token(token) else None

    def save_token(self, entry_id: str, token: str) -> dict[str, Any]:
        """Persist one entry's deployment token (synchronous; options handlers
        may run in an executor thread — mirrors ``save_alias``)."""
        if not is_valid_deployment_worker_token(token):
            return {"accepted": False, "error": "worker_token_too_short"}
        self.data["tokens"][entry_id] = token.strip()
        self._schedule_save()
        return {"accepted": True}

    def clear_token(self, entry_id: str) -> dict[str, Any]:
        """Remove one entry's deployment token."""
        self.data["tokens"].pop(entry_id, None)
        self._schedule_save()
        return {"accepted": True}

    def _schedule_save(self) -> None:
        # delay=0: a token the user just pasted must survive a restart right
        # away, and writes are rare. async_delay_save hands the write to the
        # event loop, required when called from an executor thread.
        async_delay_save = getattr(self._ha_store, "async_delay_save", None)
        if callable(async_delay_save):
            async_delay_save(lambda: deepcopy(self.data), 0)

    def summary(self) -> dict[str, Any]:
        # Token VALUES never appear in the summary — presence only.
        return {
            "storage_key": self.storage_key,
            "version": self.version,
            "backend": self.backend,
            "entry_ids": sorted(self.data["tokens"]),
            "entry_count": len(self.data["tokens"]),
        }


def get_worker_token_storage(hass: Any) -> WorkerTokenStorageHelper:
    """Return the integration-owned worker-token storage helper (cached)."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    helper = domain_data.get(DATA_WORKER_TOKEN_STORE)
    if isinstance(helper, WorkerTokenStorageHelper):
        return helper
    helper = WorkerTokenStorageHelper(ha_store=_build_home_assistant_store(hass))
    domain_data[DATA_WORKER_TOKEN_STORE] = helper
    return helper


def stored_worker_token(hass: Any, entry_id: str) -> str | None:
    """The single read surface renderer setup uses (ADR-0032)."""
    return get_worker_token_storage(hass).token_for(entry_id)


async def async_setup_worker_token_storage(hass: Any, entry: Any) -> dict[str, Any]:
    """Load persisted deployment tokens so renderer setup can read them."""
    helper = get_worker_token_storage(hass)
    await helper.async_load()
    return {
        "accepted": True,
        "code": "worker_token_storage_loaded",
        "summary": helper.summary(),
    }


def _build_home_assistant_store(hass: Any) -> Any | None:
    if HomeAssistantStore is None:
        return None
    return HomeAssistantStore(
        hass, WORKER_TOKEN_STORAGE_VERSION, WORKER_TOKEN_STORAGE_KEY
    )
