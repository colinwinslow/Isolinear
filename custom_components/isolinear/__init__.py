"""Home Assistant custom integration scaffold for Isolinear."""

from __future__ import annotations

from typing import Any

from .const import DOMAIN
from .dashboard_resource import async_register_dashboard_resource
from .entity_catalog import setup_entity_catalog
from .history_retrieval import setup_history_retrieval
from .job_orchestration import setup_job_orchestration
from .job_state import ensure_job_state_store
from .model_provider import setup_model_provider_planner
from .worker_health import setup_worker_health
from .worker_readiness import setup_worker_readiness
from .worker_renderer import setup_worker_renderer
from .websocket_api import async_register_websocket_api


async def async_setup(hass: Any, config: dict[str, Any]) -> bool:
    """Set up the Isolinear scaffold package."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["setup_config_present"] = DOMAIN in config
    return True


async def async_setup_entry(hass: Any, entry: Any) -> bool:
    """Set up an Isolinear config entry scaffold."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    entry_id = getattr(entry, "entry_id", "scaffold-entry")
    entry_data = domain_data.setdefault(entry_id, {})
    entry_data["entry"] = entry
    entry_data["entity_catalog_setup"] = setup_entity_catalog(hass, entry)
    entry_data["history_retrieval_setup"] = setup_history_retrieval(hass, entry)
    entry_data["job_state"] = ensure_job_state_store(hass, entry_id)
    entry_data["model_provider_setup"] = setup_model_provider_planner(hass, entry)
    entry_data["worker_readiness_setup"] = setup_worker_readiness(hass, entry)
    entry_data["worker_renderer_setup"] = setup_worker_renderer(hass, entry)
    entry_data["worker_health_setup"] = setup_worker_health(hass, entry)
    entry_data["job_orchestration_setup"] = setup_job_orchestration(hass, entry)
    entry_data["dashboard_resource"] = await async_register_dashboard_resource(hass, entry)
    entry_data["websocket_api"] = await async_register_websocket_api(hass, entry=entry)
    return True


async def async_unload_entry(hass: Any, entry: Any) -> bool:
    """Unload an Isolinear config entry scaffold."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data.pop(getattr(entry, "entry_id", "scaffold-entry"), None)
    return True
