"""Home Assistant custom integration scaffold for Isolinear."""

from __future__ import annotations

from typing import Any

from ._paths import preload_schema_documents
from .artifact_serving import async_setup_artifact_serving
from .const import DOMAIN
from .dashboard_resource import async_register_dashboard_resource
from .entity_catalog import setup_entity_catalog
from .history_retrieval import setup_history_retrieval
from .job_orchestration import setup_job_orchestration
from .job_state import ensure_job_state_store
from .model_provider import setup_model_provider_codegen, setup_model_provider_planner
from .model_provider_health import setup_model_provider_health
from .worker_health import setup_worker_health
from .worker_health_polling import async_setup_worker_health_polling, unload_worker_health_polling
from .semantic_memory import async_setup_semantic_memory
from .worker_token_lifecycle import async_setup_worker_token_lifecycle
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
    # Warm the bundled-schema cache off the event loop before any synchronous
    # setup step validates against JSON Schema. Without this the first read of
    # each schema file runs on the loop and Home Assistant logs blocking-call
    # warnings for entity-catalog/worker setup validation.
    await _preload_schema_documents(hass)
    entry_data["entity_catalog_setup"] = setup_entity_catalog(hass, entry)
    entry_data["history_retrieval_setup"] = setup_history_retrieval(hass, entry)
    entry_data["job_state"] = ensure_job_state_store(hass, entry_id)
    entry_data["model_provider_setup"] = setup_model_provider_planner(hass, entry)
    entry_data["model_provider_codegen_setup"] = setup_model_provider_codegen(hass, entry)
    entry_data["model_provider_health_setup"] = setup_model_provider_health(hass, entry)
    entry_data["semantic_memory_setup"] = await async_setup_semantic_memory(hass, entry)
    entry_data["worker_token_lifecycle_setup"] = await async_setup_worker_token_lifecycle(hass, entry)
    if not entry_data["worker_token_lifecycle_setup"].get("accepted"):
        return False
    entry_data["worker_readiness_setup"] = setup_worker_readiness(hass, entry)
    entry_data["worker_renderer_setup"] = setup_worker_renderer(hass, entry)
    entry_data["worker_health_setup"] = setup_worker_health(hass, entry)
    entry_data["job_orchestration_setup"] = setup_job_orchestration(hass, entry)
    entry_data["artifact_serving"] = await async_setup_artifact_serving(hass, entry)
    entry_data["dashboard_resource"] = await async_register_dashboard_resource(hass, entry)
    entry_data["websocket_api"] = await async_register_websocket_api(hass, entry=entry)
    entry_data["worker_health_polling_setup"] = await async_setup_worker_health_polling(hass, entry)
    entry_data["options_update_listener_registered"] = _register_options_update_listener(entry)
    return True


async def async_unload_entry(hass: Any, entry: Any) -> bool:
    """Unload an Isolinear config entry scaffold."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    entry_id = getattr(entry, "entry_id", "scaffold-entry")
    unload_worker_health_polling(hass, entry_id)
    domain_data.pop(entry_id, None)
    return True


async def _preload_schema_documents(hass: Any) -> None:
    """Warm the bundled-schema cache from an executor, off the event loop."""
    executor_job = getattr(hass, "async_add_executor_job", None)
    if callable(executor_job):
        await executor_job(preload_schema_documents)
    else:
        preload_schema_documents()


async def _async_options_updated(hass: Any, entry: Any) -> None:
    """Refresh runtime allowlist-derived stores after options edits."""
    entry_id = getattr(entry, "entry_id", "scaffold-entry")
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    entry_data["entry"] = entry
    entry_data["entity_catalog_setup"] = setup_entity_catalog(hass, entry)
    entry_data["history_retrieval_setup"] = setup_history_retrieval(hass, entry)
    entry_data["job_orchestration_setup"] = setup_job_orchestration(hass, entry)


def _register_options_update_listener(entry: Any) -> bool:
    add_update_listener = getattr(entry, "add_update_listener", None)
    if not callable(add_update_listener):
        return False

    remove_listener = add_update_listener(_async_options_updated)
    async_on_unload = getattr(entry, "async_on_unload", None)
    if callable(async_on_unload) and callable(remove_listener):
        async_on_unload(remove_listener)
    return True
