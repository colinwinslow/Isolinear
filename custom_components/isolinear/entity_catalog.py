"""Approved entity catalog scaffold for the Isolinear integration."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ._paths import load_schema_document, schema_path
from .config_schema import ENTITY_ID_PATTERN
from .const import DOMAIN


DATA_ENTITY_CATALOG = "entity_catalog"
DATA_ENTITY_CATALOG_SETUP = "entity_catalog_setup"
DATA_ENTITY_METADATA = "entity_metadata"
ENTITY_CATALOG_SCHEMA_PATH = (
    schema_path("entity-catalog-item.schema.json")
)

NO_ENTITY_CATALOG_ORCHESTRATION_CALLS = {
    "worker_called": False,
    "model_provider_called": False,
    "home_assistant_history_called": False,
    "semantic_memory_called": False,
    "home_assistant_service_or_state_mutation_called": False,
    "token_generated": False,
    "chart_artifact_written": False,
    "job_orchestration_called": False,
    "websocket_command_registered": False,
    "dashboard_resource_metadata_written_or_reused": False,
}


class EntityCatalogValidationError(ValueError):
    """Raised when an EntityCatalogItem does not satisfy its schema."""

    def __init__(self, result: dict[str, Any]) -> None:
        super().__init__(result.get("error", "Entity catalog validation failed."))
        self.result = result


def setup_entity_catalog(
    hass: Any,
    entry: Any,
    *,
    metadata_by_entity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and store one config-entry-scoped approved entity catalog."""
    entry_id = getattr(entry, "entry_id", "scaffold-entry")
    store = ensure_entity_catalog_store(hass, entry_id)
    result = build_approved_entity_catalog(
        hass,
        entry,
        store=store,
        metadata_by_entity=metadata_by_entity,
    )
    hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})[DATA_ENTITY_CATALOG_SETUP] = result
    return result


def ensure_entity_catalog_store(hass: Any, entry_id: str) -> dict[str, Any]:
    """Return the in-memory approved entity catalog store for one entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    entry_data = domain_data.setdefault(entry_id, {})
    store = entry_data.get(DATA_ENTITY_CATALOG)
    if isinstance(store, dict):
        return store

    store = {
        "entry_id": entry_id,
        "items": [],
        "entity_ids": [],
    }
    entry_data[DATA_ENTITY_CATALOG] = store
    return store


def build_approved_entity_catalog(
    hass: Any,
    entry: Any,
    *,
    store: dict[str, Any] | None = None,
    metadata_by_entity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema-valid catalog containing only allowlisted entities."""
    entry_id = getattr(entry, "entry_id", "scaffold-entry")
    catalog_store = store or ensure_entity_catalog_store(hass, entry_id)
    allowlist_result = normalize_entry_entity_allowlist(entry)
    if not allowlist_result["accepted"]:
        return _catalog_rejection(
            allowlist_result["code"],
            entry_id=entry_id,
            store=catalog_store,
            errors=allowlist_result.get("errors"),
        )

    allowlist = allowlist_result["entity_allowlist"]
    source_result = _catalog_items_for_allowlist(
        hass,
        allowlist,
        metadata_by_entity=metadata_by_entity,
    )
    if not source_result["accepted"]:
        return _catalog_rejection(
            source_result["code"],
            entry_id=entry_id,
            store=catalog_store,
            errors=source_result.get("errors"),
            missing_entity_ids=source_result.get("missing_entity_ids"),
            metadata_read=bool(allowlist),
        )

    storage_result = store_validated_entity_catalog(catalog_store, source_result["items"])
    if not storage_result["accepted"]:
        return _catalog_rejection(
            storage_result["code"],
            entry_id=entry_id,
            store=catalog_store,
            validation=storage_result,
            metadata_read=bool(allowlist),
        )

    return {
        "accepted": True,
        "code": "entity_catalog_ready",
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "entity_allowlist": list(allowlist),
        "catalog": storage_result["items"],
        "validation": storage_result["validation"],
        "store": summarize_entity_catalog_store(catalog_store),
        "orchestration": entity_catalog_side_effects(
            entity_catalog_written=True,
            entity_metadata_read=bool(allowlist),
        ),
    }


def normalize_entry_entity_allowlist(entry: Any) -> dict[str, Any]:
    """Return the entity allowlist configured for a Home Assistant entry."""
    options = getattr(entry, "options", None)
    data = getattr(entry, "data", None)
    allowlist = []
    if isinstance(options, Mapping) and "entity_allowlist" in options:
        allowlist = options["entity_allowlist"]
    elif isinstance(data, Mapping) and "entity_allowlist" in data:
        allowlist = data["entity_allowlist"]

    if isinstance(allowlist, tuple):
        allowlist = list(allowlist)
    if not isinstance(allowlist, list):
        return {
            "accepted": False,
            "code": "invalid_entity_allowlist",
            "errors": [{"path": "$.options.entity_allowlist", "reason": "must_be_list"}],
        }

    errors = []
    seen_entity_ids: set[str] = set()
    for index, entity_id in enumerate(allowlist):
        if not isinstance(entity_id, str) or ENTITY_ID_PATTERN.search(entity_id) is None:
            errors.append(
                {
                    "path": f"$.options.entity_allowlist[{index}]",
                    "reason": "invalid_entity_id",
                }
            )
            continue
        if entity_id in seen_entity_ids:
            errors.append(
                {
                    "path": f"$.options.entity_allowlist[{index}]",
                    "reason": "duplicate_entity_id",
                }
            )
            continue
        seen_entity_ids.add(entity_id)

    if errors:
        return {
            "accepted": False,
            "code": "invalid_entity_allowlist",
            "errors": errors,
        }
    return {
        "accepted": True,
        "code": "accepted",
        "entity_allowlist": list(allowlist),
    }


def store_validated_entity_catalog(store: dict[str, Any], items: Any) -> dict[str, Any]:
    """Validate all catalog items before mutating the in-memory store."""
    validation = validate_entity_catalog_contract(items)
    if not validation["accepted"]:
        return validation

    stored_items = deepcopy(items)
    store["items"] = stored_items
    store["entity_ids"] = [item["entity_id"] for item in stored_items]
    return {
        "accepted": True,
        "code": "accepted",
        "items": deepcopy(stored_items),
        "validation": validation,
    }


def validate_entity_catalog_contract(items: Any) -> dict[str, Any]:
    """Validate a list of EntityCatalogItem records against JSON Schema."""
    if not isinstance(items, list):
        return {
            "accepted": False,
            "code": "invalid_entity_catalog_item",
            "error": "$ must be a list of EntityCatalogItem records.",
        }

    item_results = []
    for index, item in enumerate(items):
        result = validate_entity_catalog_item_contract(item)
        item_results.append(result)
        if not result["accepted"]:
            return {
                **result,
                "item_index": index,
            }

    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(ENTITY_CATALOG_SCHEMA_PATH),
        "item_count": len(items),
        "items": item_results,
    }


def validate_entity_catalog_item_contract(item: Any) -> dict[str, Any]:
    """Validate one EntityCatalogItem against the repo JSON Schema."""
    try:
        schema = load_schema_document(ENTITY_CATALOG_SCHEMA_PATH)
        _validate_json_schema(item, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, EntityCatalogValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_entity_catalog_item",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(ENTITY_CATALOG_SCHEMA_PATH),
        "entity_id": item["entity_id"],
    }


def summarize_entity_catalog_store(store: dict[str, Any]) -> dict[str, Any]:
    """Return an evidence-friendly summary of an entity catalog store."""
    items = list(store.get("items", []))
    return {
        "entry_id": store.get("entry_id"),
        "item_count": len(items),
        "entity_ids": [item.get("entity_id") for item in items],
        "domains": sorted({item.get("domain") for item in items if item.get("domain")}),
        "all_visible_to_agent": all(item.get("visible_to_agent") is True for item in items),
    }


def entity_catalog_side_effects(
    *,
    entity_catalog_written: bool = False,
    entity_metadata_read: bool = False,
) -> dict[str, bool]:
    """Return side-effect accounting for the approved entity catalog packet."""
    return {
        **NO_ENTITY_CATALOG_ORCHESTRATION_CALLS,
        "entity_catalog_scaffold_written": entity_catalog_written,
        "home_assistant_entity_metadata_read": entity_metadata_read,
    }


def _catalog_items_for_allowlist(
    hass: Any,
    allowlist: list[str],
    *,
    metadata_by_entity: dict[str, Any] | None,
) -> dict[str, Any]:
    errors = []
    items = []
    missing_entity_ids = []
    metadata_source = _metadata_source_from_hass(hass) if metadata_by_entity is None else metadata_by_entity
    if metadata_source is not None and not isinstance(metadata_source, dict):
        return {
            "accepted": False,
            "code": "invalid_entity_catalog_metadata",
            "errors": [{"path": "$.metadata_by_entity", "reason": "must_be_object"}],
        }

    for entity_id in allowlist:
        metadata_result = _metadata_for_entity(hass, entity_id, metadata_source or {})
        if not metadata_result["accepted"]:
            if metadata_result["code"] == "unknown_allowlisted_entity":
                missing_entity_ids.append(entity_id)
            else:
                errors.extend(metadata_result.get("errors", []))
            continue

        item_result = _normalize_entity_catalog_item(entity_id, metadata_result["metadata"])
        if not item_result["accepted"]:
            errors.extend(item_result.get("errors", []))
            continue
        items.append(item_result["item"])

    if missing_entity_ids:
        return {
            "accepted": False,
            "code": "unknown_allowlisted_entity",
            "missing_entity_ids": missing_entity_ids,
        }
    if errors:
        return {
            "accepted": False,
            "code": "invalid_entity_catalog_metadata",
            "errors": errors,
        }
    return {
        "accepted": True,
        "code": "accepted",
        "items": items,
    }


def _metadata_source_from_hass(hass: Any) -> dict[str, Any]:
    domain_data = getattr(hass, "data", {}).get(DOMAIN, {})
    metadata = domain_data.get(DATA_ENTITY_METADATA, {})
    if metadata is None:
        return {}
    return metadata


def _metadata_for_entity(
    hass: Any,
    entity_id: str,
    metadata_by_entity: dict[str, Any],
) -> dict[str, Any]:
    raw_metadata = metadata_by_entity.get(entity_id)
    state_metadata = _state_metadata_for_entity(hass, entity_id)
    registry_metadata = _registry_metadata_for_entity(hass, entity_id)
    if raw_metadata is None and state_metadata is None and registry_metadata is None:
        return {
            "accepted": False,
            "code": "unknown_allowlisted_entity",
        }
    if raw_metadata is not None and not isinstance(raw_metadata, dict):
        return {
            "accepted": False,
            "code": "invalid_entity_catalog_metadata",
            "errors": [{"path": f"$.metadata_by_entity.{entity_id}", "reason": "must_be_object"}],
        }

    metadata = {}
    if registry_metadata is not None:
        metadata.update(registry_metadata)
    if state_metadata is not None:
        metadata.update(state_metadata)
    if raw_metadata is not None:
        existing_attributes = metadata.get("attributes")
        raw_attributes = raw_metadata.get("attributes")
        metadata.update(raw_metadata)
        if isinstance(existing_attributes, dict) and isinstance(raw_attributes, dict):
            metadata["attributes"] = {
                **existing_attributes,
                **raw_attributes,
            }
    return {
        "accepted": True,
        "code": "accepted",
        "metadata": metadata,
    }


def _registry_metadata_for_entity(hass: Any, entity_id: str) -> dict[str, Any] | None:
    """Return best-effort real Home Assistant registry metadata for one entity."""
    try:  # pragma: no cover - exercised only in Home Assistant.
        from homeassistant.helpers import area_registry, device_registry, entity_registry
    except ImportError:  # pragma: no cover - repo tests run without Home Assistant.
        return None

    try:
        entity_reg = entity_registry.async_get(hass)
        entity_entry = entity_reg.async_get(entity_id)
    except (AttributeError, TypeError, ValueError):
        return None
    if entity_entry is None:
        return None

    metadata: dict[str, Any] = {
        "friendly_name": getattr(entity_entry, "name", None)
        or getattr(entity_entry, "original_name", None),
        "device_class": getattr(entity_entry, "device_class", None)
        or getattr(entity_entry, "original_device_class", None),
        "integration": getattr(entity_entry, "platform", None),
    }

    area_id = getattr(entity_entry, "area_id", None)
    device_id = getattr(entity_entry, "device_id", None)
    labels = getattr(entity_entry, "labels", None)
    if isinstance(labels, (set, list, tuple)):
        metadata["labels"] = sorted(str(label) for label in labels)

    try:
        area_reg = area_registry.async_get(hass)
        device_reg = device_registry.async_get(hass)
    except (AttributeError, TypeError, ValueError):
        area_reg = None
        device_reg = None

    if device_id is not None and device_reg is not None:
        try:
            device_entry = device_reg.async_get(device_id)
        except (AttributeError, TypeError, ValueError):
            device_entry = None
        if device_entry is not None:
            metadata["device_name"] = (
                getattr(device_entry, "name_by_user", None)
                or getattr(device_entry, "name", None)
                or getattr(device_entry, "default_name", None)
            )
            area_id = area_id or getattr(device_entry, "area_id", None)

    if area_id is not None and area_reg is not None:
        try:
            area_entry = area_reg.async_get_area(area_id)
        except (AttributeError, TypeError, ValueError):
            area_entry = None
        if area_entry is not None:
            metadata["area"] = getattr(area_entry, "name", None)

    return {key: value for key, value in metadata.items() if value is not None}


def _state_metadata_for_entity(hass: Any, entity_id: str) -> dict[str, Any] | None:
    states = getattr(hass, "states", None)
    if states is None:
        return None
    state = states.get(entity_id) if isinstance(states, dict) else getattr(states, "get", lambda _entity_id: None)(entity_id)
    if state is None:
        return None

    if isinstance(state, dict):
        current_state = state.get("state")
        attributes = state.get("attributes") or {}
    else:
        current_state = getattr(state, "state", None)
        attributes = getattr(state, "attributes", {}) or {}
    if not isinstance(attributes, dict):
        attributes = {}

    return {
        "friendly_name": attributes.get("friendly_name"),
        "device_class": attributes.get("device_class"),
        "state_class": attributes.get("state_class"),
        "unit_of_measurement": attributes.get("unit_of_measurement"),
        "current_state": current_state,
        "attributes": dict(attributes),
    }


def _normalize_entity_catalog_item(entity_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
    attributes = metadata.get("attributes", {})
    if attributes is None:
        attributes = {}
    if not isinstance(attributes, dict):
        return _metadata_rejection(entity_id, "attributes", "must_be_object")

    labels = metadata.get("labels", [])
    if labels is None:
        labels = []
    if not isinstance(labels, list) or any(not isinstance(label, str) for label in labels):
        return _metadata_rejection(entity_id, "labels", "must_be_list_of_strings")

    optional_fields = {
        "friendly_name": metadata.get("friendly_name", attributes.get("friendly_name")),
        "device_class": metadata.get("device_class", attributes.get("device_class")),
        "state_class": metadata.get("state_class", attributes.get("state_class")),
        "unit_of_measurement": metadata.get("unit_of_measurement", attributes.get("unit_of_measurement")),
        "area": metadata.get("area"),
        "device_name": metadata.get("device_name"),
        "integration": metadata.get("integration"),
    }
    for field_name, value in optional_fields.items():
        if value is not None and not isinstance(value, str):
            return _metadata_rejection(entity_id, field_name, "must_be_string_or_null")

    current_state = metadata.get("current_state", metadata.get("state"))
    item = {
        "entity_id": entity_id,
        "friendly_name": optional_fields["friendly_name"],
        "domain": entity_id.split(".", 1)[0],
        "device_class": optional_fields["device_class"],
        "state_class": optional_fields["state_class"],
        "unit_of_measurement": optional_fields["unit_of_measurement"],
        "area": optional_fields["area"],
        "labels": list(labels),
        "device_name": optional_fields["device_name"],
        "integration": optional_fields["integration"],
        "current_state": current_state,
        "attributes": deepcopy(attributes),
        "visible_to_agent": True,
    }
    return {
        "accepted": True,
        "code": "accepted",
        "item": item,
    }


def _metadata_rejection(entity_id: str, field_name: str, reason: str) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": "invalid_entity_catalog_metadata",
        "errors": [
            {
                "path": f"$.metadata_by_entity.{entity_id}.{field_name}",
                "reason": reason,
            }
        ],
    }


def _catalog_rejection(
    code: str,
    *,
    entry_id: str,
    store: dict[str, Any],
    errors: list[dict[str, str]] | None = None,
    missing_entity_ids: list[str] | None = None,
    validation: dict[str, Any] | None = None,
    metadata_read: bool = False,
) -> dict[str, Any]:
    _clear_entity_catalog_store(store)
    result = {
        "accepted": False,
        "code": code,
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "catalog": [],
        "store": summarize_entity_catalog_store(store),
        "orchestration": entity_catalog_side_effects(entity_metadata_read=metadata_read),
    }
    if errors is not None:
        result["errors"] = errors
    if missing_entity_ids is not None:
        result["missing_entity_ids"] = missing_entity_ids
    if validation is not None:
        result["validation"] = validation
    return result


def _clear_entity_catalog_store(store: dict[str, Any]) -> None:
    store["items"] = []
    store["entity_ids"] = []


def _validate_json_schema(
    payload: Any,
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any],
    path: str,
) -> None:
    if "$ref" in schema:
        schema = _resolve_ref(schema["$ref"], root_schema)

    if "const" in schema and payload != schema["const"]:
        raise EntityCatalogValidationError(_schema_error(f"{path} must equal {schema['const']!r}."))

    if "enum" in schema and payload not in schema["enum"]:
        raise EntityCatalogValidationError(_schema_error(f"{path} must be one of {schema['enum']!r}."))

    if "type" in schema:
        _validate_type(payload, schema["type"], path)

    if isinstance(payload, dict):
        _validate_object(payload, schema, root_schema=root_schema, path=path)
    elif isinstance(payload, list):
        _validate_array(payload, schema, root_schema=root_schema, path=path)
    elif isinstance(payload, str):
        _validate_string(payload, schema, path)


def _validate_object(
    payload: dict[str, Any],
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any],
    path: str,
) -> None:
    for property_name in schema.get("required", []):
        if property_name not in payload:
            raise EntityCatalogValidationError(_schema_error(f"{path}.{property_name} is required."))

    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        extra_properties = sorted(set(payload) - set(properties))
        if extra_properties:
            raise EntityCatalogValidationError(
                _schema_error(f"{path} has unexpected properties: {extra_properties!r}.")
            )

    for property_name, property_schema in properties.items():
        if property_name in payload:
            _validate_json_schema(
                payload[property_name],
                property_schema,
                root_schema=root_schema,
                path=f"{path}.{property_name}",
            )


def _validate_array(
    payload: list[Any],
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any],
    path: str,
) -> None:
    item_schema = schema.get("items")
    if item_schema is None:
        return

    for index, item in enumerate(payload):
        _validate_json_schema(item, item_schema, root_schema=root_schema, path=f"{path}[{index}]")


def _validate_string(payload: str, schema: dict[str, Any], path: str) -> None:
    pattern = schema.get("pattern")
    if pattern is not None and re.search(pattern, payload) is None:
        raise EntityCatalogValidationError(_schema_error(f"{path} must match pattern {pattern!r}."))


def _validate_type(payload: Any, schema_type: str | list[str], path: str) -> None:
    expected_types = [schema_type] if isinstance(schema_type, str) else schema_type
    if any(_matches_type(payload, expected_type) for expected_type in expected_types):
        return
    raise EntityCatalogValidationError(_schema_error(f"{path} must be of type {expected_types!r}."))


def _matches_type(payload: Any, schema_type: str) -> bool:
    if schema_type == "object":
        return isinstance(payload, dict)
    if schema_type == "array":
        return isinstance(payload, list)
    if schema_type == "string":
        return isinstance(payload, str)
    if schema_type == "number":
        return isinstance(payload, (int, float)) and not isinstance(payload, bool)
    if schema_type == "integer":
        return isinstance(payload, int) and not isinstance(payload, bool)
    if schema_type == "boolean":
        return isinstance(payload, bool)
    if schema_type == "null":
        return payload is None
    return False


def _resolve_ref(ref: str, root_schema: dict[str, Any]) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise EntityCatalogValidationError(_schema_error(f"Unsupported schema ref '{ref}'."))

    current: Any = root_schema
    for part in ref[2:].split("/"):
        current = current[part]
    return current


def _schema_error(error: str) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": "invalid_entity_catalog_item",
        "error": error,
    }
