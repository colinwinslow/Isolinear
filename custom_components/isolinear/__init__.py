"""Home Assistant custom integration scaffold for Isolinear."""

from __future__ import annotations

from typing import Any

from .const import DOMAIN
from .websocket_api import async_register_websocket_api


async def async_setup(hass: Any, config: dict[str, Any]) -> bool:
    """Set up the Isolinear scaffold package."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["setup_config_present"] = DOMAIN in config
    return True


async def async_setup_entry(hass: Any, entry: Any) -> bool:
    """Set up an Isolinear config entry scaffold."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data[getattr(entry, "entry_id", "scaffold-entry")] = {
        "entry": entry,
        "websocket_api": await async_register_websocket_api(hass),
    }
    return True


async def async_unload_entry(hass: Any, entry: Any) -> bool:
    """Unload an Isolinear config entry scaffold."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data.pop(getattr(entry, "entry_id", "scaffold-entry"), None)
    return True
