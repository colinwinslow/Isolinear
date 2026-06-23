"""Live semantic-alias memory: per-config-entry store load, use-time validity,
prompt matching, and entity injection for planning (ADR-0009/0010, Tranche 1).

Tranche 1 is read-only: it loads a persisted ``SemanticMemoryStore`` envelope for
one config entry, computes alias validity against the current entity catalog,
matches valid aliases to the prompt by token overlap, and reports the entity IDs
to inject into entity selection. It does not write the store (propose/confirm/save
is Tranche 2). See ``docs/specs/semantic-alias-live-wiring.md``.

The validity/extraction logic mirrors the reference implementation in
``src/Isolinear/fake_slice.py``; the storage helper mirrors
``worker_token_lifecycle.WorkerTokenLifecycleStorageHelper``.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from ._paths import load_schema_document, schema_path
from .const import DOMAIN
from .entity_catalog import EntityCatalogValidationError, _validate_json_schema

try:  # pragma: no cover - exercised only inside a real Home Assistant runtime
    from homeassistant.helpers.storage import Store as HomeAssistantStore
except Exception:  # noqa: BLE001 - HA not importable in unit/scaffold context
    HomeAssistantStore = None  # type: ignore[assignment]

SEMANTIC_MEMORY_STORAGE_KEY = "isolinear_semantic_memory"
SEMANTIC_MEMORY_STORAGE_VERSION = 1

DATA_SEMANTIC_MEMORY_STORE = "semantic_memory_storage_helper"
DATA_SEMANTIC_MEMORY_SETUP = "semantic_memory_setup"

# The single tuning knob for prompt matching: an alias natural name matches when
# at least this fraction of its (non-trivial) tokens appear in the prompt. At
# 0.6, single- and two-token names require ALL their tokens present (0.5 < 0.6),
# so a 2-token alias can't fire on one weak shared word like "running"; longer
# names tolerate one missing token (3/3, 2/3, 3/4, ...).
SEMANTIC_ALIAS_MATCH_RATIO = 0.6

# Stripped from natural-name tokens so a stop word can't satisfy the ratio on its
# own (e.g. "the AC" -> {ac}, not {the, ac}). Deliberately small; meaning-bearing
# short words like "ac" are NOT trivial and carry the match.
_SEMANTIC_ALIAS_TRIVIAL_TOKENS = {
    "the", "a", "an", "is", "was", "are", "of", "and", "to", "on",
}

# Same token rule as the entity selector (``_prompt_tokens``) so the two systems
# agree on what a token is. Unlike the selector, the alias matcher applies NO
# minimum-length floor: alias natural names are short user-authored phrases where
# a two-character token like "ac" is the entire signal.
_TOKEN_RE = re.compile(r"[a-z0-9_]+")

_STORE_SCHEMA_PATH = schema_path("semantic-memory-store.schema.json")


class SemanticMemoryStoreError(ValueError):
    """Raised when a semantic memory store envelope is internally inconsistent."""


class SemanticMemoryStorageHelper:
    """Dual-backend, per-config-entry semantic-alias store loader (read-only).

    One Home Assistant ``Store`` document holds every config entry's envelope,
    keyed internally by ``config_entry_id`` (ADR-0010 scoping). When no
    ``ha_store`` is supplied an in-memory backend is used (tests / scaffold).
    """

    def __init__(self, *, ha_store: Any | None = None) -> None:
        self.storage_key = SEMANTIC_MEMORY_STORAGE_KEY
        self.version = SEMANTIC_MEMORY_STORAGE_VERSION
        self._ha_store = ha_store
        self.backend = (
            "home_assistant_storage_helper"
            if ha_store is not None
            else "in_memory_scaffold_storage_helper"
        )
        self.data: dict[str, Any] = {"version": self.version, "stores": {}}

    async def async_load(self) -> dict[str, Any]:
        """Load persisted per-entry store envelopes when HA storage is available."""
        async_load = getattr(self._ha_store, "async_load", None)
        if not callable(async_load):
            return self.summary()

        loaded = await async_load()
        if (
            isinstance(loaded, dict)
            and loaded.get("version") == self.version
            and isinstance(loaded.get("stores"), dict)
        ):
            stores = self.data.setdefault("stores", {})
            for entry_id, store in loaded["stores"].items():
                if entry_id not in stores and isinstance(store, dict):
                    stores[entry_id] = deepcopy(store)
        return self.summary()

    def store_for(self, entry_id: str) -> dict[str, Any] | None:
        """Return a deep copy of the persisted envelope for one config entry."""
        store = self.data["stores"].get(entry_id)
        return deepcopy(store) if isinstance(store, dict) else None

    def seed_store(self, entry_id: str, store: dict[str, Any]) -> None:
        """Seed one entry's envelope in memory.

        Tranche 1 has no propose/confirm/save flow; aliases are seeded directly
        for live testing (the documented manual workaround). This is the only
        write surface and it does not persist on its own.
        """
        self.data["stores"][entry_id] = deepcopy(store)

    def summary(self) -> dict[str, Any]:
        return {
            "storage_key": self.storage_key,
            "version": self.version,
            "backend": self.backend,
            "entry_ids": sorted(self.data["stores"]),
            "entry_count": len(self.data["stores"]),
        }


def validate_semantic_memory_store_contract(store: Any) -> dict[str, Any]:
    """Validate a SemanticMemoryStore envelope against the bundled JSON Schema."""
    try:
        schema = load_schema_document(_STORE_SCHEMA_PATH)
        _validate_json_schema(store, schema, root_schema=schema, path="$")
        _validate_store_alias_ids(store)
    except (
        EntityCatalogValidationError,
        SemanticMemoryStoreError,
        KeyError,
        TypeError,
        OSError,
        ValueError,
    ) as exc:
        return {
            "accepted": False,
            "code": "semantic_memory_store_invalid",
            "error": str(exc),
        }
    return {"accepted": True, "code": "accepted"}


def prepare_semantic_memory_for_planning(
    *,
    semantic_memory_store: dict[str, Any],
    entity_catalog: list[dict[str, Any]],
) -> dict[str, Any]:
    """Split enabled aliases into valid/invalid against the current catalog.

    Fail closed on a schema-invalid or duplicate-id store: no aliases, a
    ``store_error``. Validity is computed at use time and never mutates the store
    (semantic-memory-spec "Invalidity policy").
    """
    validation = validate_semantic_memory_store_contract(semantic_memory_store)
    if not validation["accepted"]:
        return {
            "valid_semantic_aliases": [],
            "invalid_semantic_aliases": [],
            "store_error": {
                "code": validation["code"],
                "message": validation["error"],
            },
        }

    valid_aliases: list[dict[str, Any]] = []
    invalid_aliases: list[dict[str, str]] = []
    for alias in semantic_memory_store["aliases"]:
        if not alias.get("enabled", True):
            continue

        invalid_entities = _invalid_semantic_alias_entities(
            alias=alias,
            entity_catalog=entity_catalog,
        )
        if invalid_entities:
            invalid_aliases.extend(invalid_entities)
            continue

        valid_aliases.append(alias)

    return {
        "valid_semantic_aliases": valid_aliases,
        "invalid_semantic_aliases": invalid_aliases,
        "store_error": None,
    }


def alias_matches_prompt(alias: dict[str, Any], prompt: str) -> bool:
    """Return whether any of an alias's natural names clears the overlap ratio."""
    prompt_tokens = set(_tokens(prompt))
    for name in alias.get("natural_names", []):
        name_tokens = _natural_name_tokens(name)
        if not name_tokens:
            continue
        overlap = len(name_tokens & prompt_tokens)
        if overlap >= 1 and overlap / len(name_tokens) >= SEMANTIC_ALIAS_MATCH_RATIO:
            return True
    return False


def match_aliases_to_prompt(
    valid_aliases: list[dict[str, Any]], prompt: str
) -> list[dict[str, Any]]:
    """Return the subset of valid aliases whose natural names match the prompt."""
    return [alias for alias in valid_aliases if alias_matches_prompt(alias, prompt)]


def semantic_alias_entity_ids(alias: dict[str, Any]) -> list[str]:
    """Return the entity IDs named by an alias's meaning (order-stable)."""
    meaning = alias.get("meaning", {})
    if meaning.get("type") == "aggregate":
        return [
            entity_id
            for entity_id in meaning.get("entity_ids", [])
            if isinstance(entity_id, str)
        ]

    entity_id = meaning.get("entity_id")
    if isinstance(entity_id, str):
        return [entity_id]
    return []


def resolve_alias_injection(
    *,
    semantic_memory_store: dict[str, Any] | None,
    entity_catalog: list[dict[str, Any]],
    prompt: str,
) -> dict[str, Any]:
    """Load -> match -> inject in one call for the orchestration selection site.

    Returns the matched alias IDs, the de-duplicated entity IDs to inject into
    selection, and any ``store_error``. A missing store or no match yields empty
    injection (zero behavior change on the no-alias path).
    """
    if semantic_memory_store is None:
        return {
            "matched_alias_ids": [],
            "injected_entity_ids": [],
            "store_error": None,
        }

    prepared = prepare_semantic_memory_for_planning(
        semantic_memory_store=semantic_memory_store,
        entity_catalog=entity_catalog,
    )
    matched = match_aliases_to_prompt(prepared["valid_semantic_aliases"], prompt)

    injected_entity_ids: list[str] = []
    for alias in matched:
        for entity_id in semantic_alias_entity_ids(alias):
            if entity_id not in injected_entity_ids:
                injected_entity_ids.append(entity_id)

    return {
        "matched_alias_ids": [alias["alias_id"] for alias in matched],
        "injected_entity_ids": injected_entity_ids,
        "store_error": prepared["store_error"],
    }


def _validate_store_alias_ids(store: dict[str, Any]) -> None:
    seen_alias_ids: set[str] = set()
    duplicate_alias_ids: set[str] = set()
    for alias in store["aliases"]:
        alias_id = alias["alias_id"]
        if alias_id in seen_alias_ids:
            duplicate_alias_ids.add(alias_id)
        seen_alias_ids.add(alias_id)
    if duplicate_alias_ids:
        duplicate_list = ", ".join(sorted(duplicate_alias_ids))
        raise SemanticMemoryStoreError(f"Duplicate semantic alias IDs: {duplicate_list}.")


def _invalid_semantic_alias_entities(
    *,
    alias: dict[str, Any],
    entity_catalog: list[dict[str, Any]],
) -> list[dict[str, str]]:
    by_entity_id = {item["entity_id"]: item for item in entity_catalog}
    invalid_entities: list[dict[str, str]] = []

    for entity_id in semantic_alias_entity_ids(alias):
        entity = by_entity_id.get(entity_id)
        if entity is None:
            reason = "entity_unavailable"
        elif not entity.get("visible_to_agent"):
            reason = "entity_not_allowlisted"
        else:
            continue

        invalid_entities.append(
            {
                "alias_id": alias.get("alias_id", ""),
                "entity_id": entity_id,
                "reason": reason,
            }
        )

    return invalid_entities


def _tokens(value: str) -> list[str]:
    return _TOKEN_RE.findall(value.lower())


def _natural_name_tokens(name: str) -> set[str]:
    return {
        token
        for token in _tokens(name)
        if token not in _SEMANTIC_ALIAS_TRIVIAL_TOKENS
    }


def get_semantic_memory_storage(hass: Any) -> SemanticMemoryStorageHelper:
    """Return the integration-owned semantic-memory storage helper (cached)."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    helper = domain_data.get(DATA_SEMANTIC_MEMORY_STORE)
    if isinstance(helper, SemanticMemoryStorageHelper):
        return helper
    helper = SemanticMemoryStorageHelper(ha_store=_build_home_assistant_store(hass))
    domain_data[DATA_SEMANTIC_MEMORY_STORE] = helper
    return helper


def semantic_memory_store_for(hass: Any, entry_id: str) -> dict[str, Any] | None:
    """Return the persisted SemanticMemoryStore envelope for one config entry."""
    return get_semantic_memory_storage(hass).store_for(entry_id)


async def async_setup_semantic_memory(hass: Any, entry: Any) -> dict[str, Any]:
    """Load persisted semantic aliases so planning can inject them (read-only)."""
    helper = get_semantic_memory_storage(hass)
    await helper.async_load()
    return {
        "accepted": True,
        "code": "semantic_memory_loaded",
        "summary": helper.summary(),
    }


def _build_home_assistant_store(hass: Any) -> Any | None:
    if HomeAssistantStore is None:
        return None
    return HomeAssistantStore(
        hass, SEMANTIC_MEMORY_STORAGE_VERSION, SEMANTIC_MEMORY_STORAGE_KEY
    )
