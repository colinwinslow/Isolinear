"""Unit tests for live semantic-alias wiring (ADR-0009/0010, Tranche 1).

Covers store load (dual-backend), use-time validity split, the token-overlap
matcher (including the two-character-token case and the no-floor rule), entity-id
extraction per meaning type, and the orchestration injection/composition helper.
"""

import asyncio
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from custom_components.isolinear.semantic_memory import (  # noqa: E402
    SemanticMemoryStorageHelper,
    alias_matches_prompt,
    match_aliases_to_prompt,
    prepare_semantic_memory_for_planning,
    resolve_alias_injection,
    semantic_alias_entity_ids,
    validate_semantic_memory_store_contract,
)

_NOW = datetime(2026, 6, 23, 12, 0, 0, tzinfo=timezone.utc).isoformat()


def _alias(**overrides):
    alias = {
        "alias_id": "whole_house_ac",
        "natural_names": ["AC", "AC running"],
        "meaning": {
            "type": "state_interval",
            "entity_id": "climate.kitchen_ecobee",
            "active_values": ["cool", "heat"],
        },
        "source": "user_confirmed",
        "created_at": _NOW,
    }
    alias.update(overrides)
    return alias


def _store(aliases, *, config_entry_id="fake-config-entry", store_version=1):
    return {
        "store_version": store_version,
        "config_entry_id": config_entry_id,
        "created_at": _NOW,
        "updated_at": _NOW,
        "aliases": aliases,
    }


def _catalog(*entity_ids, hidden=()):
    return [
        {
            "entity_id": entity_id,
            "friendly_name": entity_id.split(".")[-1].replace("_", " ").title(),
            "domain": entity_id.split(".")[0],
            "visible_to_agent": entity_id not in hidden,
        }
        for entity_id in entity_ids
    ]


class _FakeHaStore:
    def __init__(self, loaded):
        self._loaded = loaded

    async def async_load(self):
        return self._loaded


class StorageHelperTests(unittest.TestCase):
    def test_in_memory_backend_when_no_ha_store(self):
        helper = SemanticMemoryStorageHelper()
        self.assertEqual(helper.backend, "in_memory_scaffold_storage_helper")
        self.assertIsNone(helper.store_for("fake-config-entry"))

    def test_seed_and_read_back_is_entry_scoped(self):
        helper = SemanticMemoryStorageHelper()
        helper.seed_store("entry-a", _store([_alias()]))
        self.assertIsNotNone(helper.store_for("entry-a"))
        self.assertIsNone(helper.store_for("entry-b"))

    def test_async_load_restores_persisted_stores(self):
        persisted = {"version": 1, "stores": {"entry-a": _store([_alias()])}}
        helper = SemanticMemoryStorageHelper(ha_store=_FakeHaStore(persisted))
        asyncio.run(helper.async_load())
        self.assertEqual(helper.backend, "home_assistant_storage_helper")
        self.assertIsNotNone(helper.store_for("entry-a"))

    def test_async_load_ignores_wrong_version_envelope(self):
        persisted = {"version": 99, "stores": {"entry-a": _store([_alias()])}}
        helper = SemanticMemoryStorageHelper(ha_store=_FakeHaStore(persisted))
        asyncio.run(helper.async_load())
        self.assertIsNone(helper.store_for("entry-a"))


class StoreContractTests(unittest.TestCase):
    def test_valid_store_accepted(self):
        result = validate_semantic_memory_store_contract(_store([_alias()]))
        self.assertTrue(result["accepted"])

    def test_unsupported_version_fails_closed(self):
        result = validate_semantic_memory_store_contract(
            _store([_alias()], store_version=99)
        )
        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "semantic_memory_store_invalid")

    def test_missing_required_field_fails_closed(self):
        store = _store([_alias()])
        del store["aliases"]
        result = validate_semantic_memory_store_contract(store)
        self.assertFalse(result["accepted"])

    def test_duplicate_alias_ids_fail_closed(self):
        store = _store([_alias(), _alias(natural_names=["other"])])
        result = validate_semantic_memory_store_contract(store)
        self.assertFalse(result["accepted"])
        self.assertIn("whole_house_ac", result["error"])


class ValiditySplitTests(unittest.TestCase):
    def test_valid_alias_returned(self):
        prepared = prepare_semantic_memory_for_planning(
            semantic_memory_store=_store([_alias()]),
            entity_catalog=_catalog("climate.kitchen_ecobee"),
        )
        self.assertEqual(len(prepared["valid_semantic_aliases"]), 1)
        self.assertEqual(prepared["invalid_semantic_aliases"], [])
        self.assertIsNone(prepared["store_error"])

    def test_disabled_alias_skipped_not_invalid(self):
        prepared = prepare_semantic_memory_for_planning(
            semantic_memory_store=_store([_alias(enabled=False)]),
            entity_catalog=_catalog("climate.kitchen_ecobee"),
        )
        self.assertEqual(prepared["valid_semantic_aliases"], [])
        self.assertEqual(prepared["invalid_semantic_aliases"], [])

    def test_missing_entity_is_unavailable(self):
        prepared = prepare_semantic_memory_for_planning(
            semantic_memory_store=_store([_alias()]),
            entity_catalog=_catalog("sensor.kitchen_temperature"),
        )
        self.assertEqual(prepared["valid_semantic_aliases"], [])
        self.assertEqual(
            prepared["invalid_semantic_aliases"][0]["reason"], "entity_unavailable"
        )

    def test_hidden_entity_is_not_allowlisted(self):
        prepared = prepare_semantic_memory_for_planning(
            semantic_memory_store=_store([_alias()]),
            entity_catalog=_catalog(
                "climate.kitchen_ecobee", hidden=("climate.kitchen_ecobee",)
            ),
        )
        self.assertEqual(prepared["valid_semantic_aliases"], [])
        self.assertEqual(
            prepared["invalid_semantic_aliases"][0]["reason"], "entity_not_allowlisted"
        )

    def test_malformed_store_returns_store_error(self):
        prepared = prepare_semantic_memory_for_planning(
            semantic_memory_store=_store([_alias()], store_version=99),
            entity_catalog=_catalog("climate.kitchen_ecobee"),
        )
        self.assertEqual(prepared["valid_semantic_aliases"], [])
        self.assertEqual(
            prepared["store_error"]["code"], "semantic_memory_store_invalid"
        )


class MatcherTests(unittest.TestCase):
    def test_two_token_name_full_overlap_matches(self):
        self.assertTrue(
            alias_matches_prompt(_alias(), "show kitchen temp and when the AC was running")
        )

    def test_two_character_token_matches_without_length_floor(self):
        self.assertTrue(
            alias_matches_prompt(_alias(natural_names=["AC"]), "is the AC on right now?")
        )

    def test_no_token_overlap_does_not_match(self):
        self.assertFalse(
            alias_matches_prompt(
                _alias(natural_names=["dishwasher running"]),
                "show kitchen temperature today",
            )
        )

    def test_trivial_words_only_do_not_match(self):
        # "the on" tokenizes to {} after trivial-word stripping -> never matches.
        self.assertFalse(alias_matches_prompt(_alias(natural_names=["the on"]), "the on"))

    def test_sub_threshold_overlap_does_not_match(self):
        # name has 3 meaningful tokens, only 1 present -> ratio 0.33 < 0.5.
        alias = _alias(natural_names=["upstairs bedroom thermostat"])
        self.assertFalse(alias_matches_prompt(alias, "show upstairs values"))

    def test_match_aliases_filters_to_matching(self):
        aliases = [
            _alias(),
            _alias(alias_id="dishwasher", natural_names=["dishwasher running"]),
        ]
        matched = match_aliases_to_prompt(aliases, "when was the AC running")
        self.assertEqual([a["alias_id"] for a in matched], ["whole_house_ac"])


class EntityIdExtractionTests(unittest.TestCase):
    def test_state_interval_single_entity(self):
        self.assertEqual(
            semantic_alias_entity_ids(_alias()), ["climate.kitchen_ecobee"]
        )

    def test_aggregate_returns_all_entities(self):
        alias = _alias(
            meaning={
                "type": "aggregate",
                "operation": "mean",
                "entity_ids": ["sensor.a", "sensor.b", "sensor.c"],
            }
        )
        self.assertEqual(
            semantic_alias_entity_ids(alias), ["sensor.a", "sensor.b", "sensor.c"]
        )

    def test_entity_meaning_single_entity(self):
        alias = _alias(meaning={"type": "entity", "entity_id": "sensor.x"})
        self.assertEqual(semantic_alias_entity_ids(alias), ["sensor.x"])


class ResolveInjectionTests(unittest.TestCase):
    def test_matched_alias_injects_entity(self):
        result = resolve_alias_injection(
            semantic_memory_store=_store([_alias()]),
            entity_catalog=_catalog(
                "sensor.kitchen_temperature", "climate.kitchen_ecobee"
            ),
            prompt="show kitchen temp and when the AC was running",
        )
        self.assertEqual(result["matched_alias_ids"], ["whole_house_ac"])
        self.assertEqual(result["injected_entity_ids"], ["climate.kitchen_ecobee"])
        self.assertIsNone(result["store_error"])

    def test_disabled_alias_injects_nothing(self):
        result = resolve_alias_injection(
            semantic_memory_store=_store([_alias(enabled=False)]),
            entity_catalog=_catalog("climate.kitchen_ecobee"),
            prompt="show me when the AC was running",
        )
        self.assertEqual(result["injected_entity_ids"], [])

    def test_invalid_alias_injects_nothing(self):
        result = resolve_alias_injection(
            semantic_memory_store=_store([_alias()]),
            entity_catalog=_catalog("sensor.kitchen_temperature"),
            prompt="show me when the AC was running",
        )
        self.assertEqual(result["injected_entity_ids"], [])

    def test_no_match_injects_nothing(self):
        result = resolve_alias_injection(
            semantic_memory_store=_store([_alias()]),
            entity_catalog=_catalog("climate.kitchen_ecobee"),
            prompt="show kitchen temperature today",
        )
        self.assertEqual(result["matched_alias_ids"], [])
        self.assertEqual(result["injected_entity_ids"], [])

    def test_none_store_injects_nothing(self):
        result = resolve_alias_injection(
            semantic_memory_store=None,
            entity_catalog=_catalog("climate.kitchen_ecobee"),
            prompt="show me when the AC was running",
        )
        self.assertEqual(result["injected_entity_ids"], [])
        self.assertIsNone(result["store_error"])

    def test_malformed_store_fails_closed_with_error(self):
        result = resolve_alias_injection(
            semantic_memory_store=_store([_alias()], store_version=99),
            entity_catalog=_catalog("climate.kitchen_ecobee"),
            prompt="show me when the AC was running",
        )
        self.assertEqual(result["injected_entity_ids"], [])
        self.assertEqual(result["store_error"]["code"], "semantic_memory_store_invalid")

    def test_aggregate_alias_injects_all_present_entities(self):
        alias = _alias(
            alias_id="upstairs_temperature",
            natural_names=["upstairs temperature"],
            meaning={
                "type": "aggregate",
                "operation": "mean",
                "entity_ids": [
                    "sensor.bed1_temp",
                    "sensor.bed2_temp",
                    "sensor.bed3_temp",
                ],
            },
        )
        result = resolve_alias_injection(
            semantic_memory_store=_store([alias]),
            entity_catalog=_catalog(
                "sensor.bed1_temp", "sensor.bed2_temp", "sensor.bed3_temp"
            ),
            prompt="show upstairs temperature overnight",
        )
        self.assertEqual(
            result["injected_entity_ids"],
            ["sensor.bed1_temp", "sensor.bed2_temp", "sensor.bed3_temp"],
        )


class _FakeHass:
    def __init__(self):
        self.data = {}


class OrchestrationInjectionTests(unittest.TestCase):
    """Covers _inject_semantic_aliases composition at the orchestration site."""

    def setUp(self):
        from custom_components.isolinear.semantic_memory import (
            DATA_SEMANTIC_MEMORY_STORE,
            SemanticMemoryStorageHelper,
        )
        from custom_components.isolinear.const import DOMAIN

        self.hass = _FakeHass()
        self.helper = SemanticMemoryStorageHelper()
        self.hass.data[DOMAIN] = {DATA_SEMANTIC_MEMORY_STORE: self.helper}

    def _inject(self, prompt, catalog_items):
        from custom_components.isolinear.job_orchestration import (
            _inject_semantic_aliases,
            select_prompt_entity_ids,
        )

        selection = select_prompt_entity_ids(prompt, catalog_items)
        return _inject_semantic_aliases(
            self.hass, "fake-config-entry", prompt, catalog_items, selection
        )

    def test_anchor_direct_and_alias_compose(self):
        # Direct match resolves the temperature sensor (full-word "temperature"
        # outscores "kitchen"-only); the alias injects the climate entity the
        # prompt never names.
        self.helper.seed_store("fake-config-entry", _store([_alias()]))
        catalog = [
            {
                "entity_id": "sensor.kitchen_temperature",
                "friendly_name": "Kitchen Temperature",
                "domain": "sensor",
                "visible_to_agent": True,
            },
            {
                "entity_id": "climate.kitchen_ecobee",
                "friendly_name": "Kitchen Ecobee",
                "domain": "climate",
                "visible_to_agent": True,
            },
        ]
        result = self._inject(
            "show kitchen temperature and when the AC was running", catalog
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["source"], "semantic_alias")
        self.assertEqual(
            result["entity_ids"],
            ["sensor.kitchen_temperature", "climate.kitchen_ecobee"],
        )
        self.assertEqual(result["matched_alias_ids"], ["whole_house_ac"])

    def test_no_store_returns_selection_unchanged(self):
        catalog = _catalog("sensor.kitchen_temperature")
        result = self._inject("show kitchen temperature today", catalog)
        # No seeded store -> store_for None -> selection passes through untouched.
        self.assertEqual(result["source"], "catalog_label")

    def test_alias_only_when_prompt_has_no_direct_match(self):
        self.helper.seed_store("fake-config-entry", _store([_alias()]))
        catalog = _catalog("climate.kitchen_ecobee")
        result = self._inject("is the AC on right now?", catalog)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["entity_ids"], ["climate.kitchen_ecobee"])
        self.assertEqual(result["source"], "semantic_alias")

    def test_no_dup_when_alias_entity_already_directly_resolved(self):
        self.helper.seed_store(
            "fake-config-entry",
            _store(
                [
                    _alias(
                        alias_id="ecobee_alias",
                        natural_names=["kitchen ecobee"],
                        meaning={"type": "entity", "entity_id": "climate.kitchen_ecobee"},
                    )
                ]
            ),
        )
        catalog = _catalog("climate.kitchen_ecobee")
        result = self._inject("show kitchen ecobee", catalog)
        self.assertEqual(result["entity_ids"], ["climate.kitchen_ecobee"])


if __name__ == "__main__":
    unittest.main()
