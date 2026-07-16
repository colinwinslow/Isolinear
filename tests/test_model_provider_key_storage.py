"""Model-provider API key storage (ADR-0037, mirroring ADR-0032).

Covers: the storage helper round-trip (save/load/clear); the write-only
options-field action split (keep/save/clear); that the stored key flows into
the planner client's Authorization header; and the config_schema regression
asserting the key field name is forbidden in config data/options.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from custom_components.isolinear.config_flow import (  # noqa: E402
    MODEL_PROVIDER_KEY_OPTIONS_FIELD,
    extract_provider_key_action,
)
from custom_components.isolinear.config_schema import (  # noqa: E402
    FORBIDDEN_CONFIG_KEYS,
    default_config_data,
    default_options_data,
    validate_config_and_options,
)
from custom_components.isolinear.const import (  # noqa: E402
    DOMAIN,
    MODEL_PROVIDER_OPENAI_COMPATIBLE,
)
from custom_components.isolinear.model_provider import (  # noqa: E402
    OpenAICompatiblePlannerClient,
    _build_planner_client,
    setup_model_provider_planner,
)
from custom_components.isolinear.model_provider_key_storage import (  # noqa: E402
    DATA_PROVIDER_KEY_STORE,
    ModelProviderKeyStorageHelper,
    async_setup_model_provider_key_storage,
    get_model_provider_key_storage,
    stored_model_provider_key,
)

ENTRY_ID = "provider-key-entry"
VALID_KEY = "sk-my-litellm-bearer-key-abcdef"


class FakeHass:
    def __init__(self) -> None:
        self.data: dict[str, Any] = {DOMAIN: {}}


class FakeEntry:
    def __init__(self) -> None:
        self.entry_id = ENTRY_ID
        self.data = {
            "model_provider_type": MODEL_PROVIDER_OPENAI_COMPATIBLE,
            "model_endpoint_url": "http://10.0.1.39:4000/v1",
            "planner_model": "ollama/gemma",
            "codegen_model": None,
            "visual_validator_model": None,
            "worker_endpoint_url": "http://localhost:8765",
        }
        self.options: dict[str, Any] = {}


class FakeStore:
    def __init__(self, loaded: dict[str, Any] | None = None) -> None:
        self.loaded = loaded
        self.saved: list[dict[str, Any]] = []

    async def async_load(self) -> dict[str, Any] | None:
        return self.loaded

    def async_delay_save(self, data_fn, _delay) -> None:
        self.saved.append(data_fn())


class StorageHelperTests(unittest.TestCase):
    def test_save_load_round_trip_and_clear(self) -> None:
        store = FakeStore()
        helper = ModelProviderKeyStorageHelper(ha_store=store)
        helper.save_key(ENTRY_ID, VALID_KEY)
        self.assertEqual(helper.key_for(ENTRY_ID), VALID_KEY)
        self.assertEqual(len(store.saved), 1)
        helper.clear_key(ENTRY_ID)
        self.assertIsNone(helper.key_for(ENTRY_ID))
        self.assertEqual(len(store.saved), 2)

    def test_key_never_in_summary(self) -> None:
        helper = ModelProviderKeyStorageHelper()
        helper.save_key(ENTRY_ID, VALID_KEY)
        summary = helper.summary()
        self.assertNotIn(VALID_KEY, str(summary))
        self.assertIn(ENTRY_ID, summary["entry_ids"])

    def test_empty_key_rejected(self) -> None:
        helper = ModelProviderKeyStorageHelper()
        result = helper.save_key(ENTRY_ID, "")
        self.assertFalse(result["accepted"])
        self.assertIsNone(helper.key_for(ENTRY_ID))

    def test_whitespace_only_key_rejected(self) -> None:
        helper = ModelProviderKeyStorageHelper()
        result = helper.save_key(ENTRY_ID, "   ")
        self.assertFalse(result["accepted"])

    def test_key_stripped_on_save(self) -> None:
        helper = ModelProviderKeyStorageHelper()
        helper.save_key(ENTRY_ID, f"  {VALID_KEY}  ")
        self.assertEqual(helper.key_for(ENTRY_ID), VALID_KEY)

    def test_async_load_restores_persisted_key(self) -> None:
        store = FakeStore(loaded={"version": 1, "keys": {ENTRY_ID: VALID_KEY}})
        helper = ModelProviderKeyStorageHelper(ha_store=store)
        asyncio.run(helper.async_load())
        self.assertEqual(helper.key_for(ENTRY_ID), VALID_KEY)

    def test_async_load_skips_empty_key_from_store(self) -> None:
        store = FakeStore(loaded={"version": 1, "keys": {ENTRY_ID: ""}})
        helper = ModelProviderKeyStorageHelper(ha_store=store)
        asyncio.run(helper.async_load())
        self.assertIsNone(helper.key_for(ENTRY_ID))

    def test_async_load_skips_version_mismatch(self) -> None:
        store = FakeStore(loaded={"version": 99, "keys": {ENTRY_ID: VALID_KEY}})
        helper = ModelProviderKeyStorageHelper(ha_store=store)
        asyncio.run(helper.async_load())
        self.assertIsNone(helper.key_for(ENTRY_ID))

    def test_in_memory_backend_when_no_store(self) -> None:
        helper = ModelProviderKeyStorageHelper()
        self.assertEqual(helper.backend, "in_memory_scaffold_storage_helper")
        helper.save_key(ENTRY_ID, VALID_KEY)
        self.assertEqual(helper.key_for(ENTRY_ID), VALID_KEY)

    def test_get_model_provider_key_storage_is_cached(self) -> None:
        hass = FakeHass()
        h1 = get_model_provider_key_storage(hass)
        h2 = get_model_provider_key_storage(hass)
        self.assertIs(h1, h2)

    def test_stored_model_provider_key_returns_none_when_absent(self) -> None:
        hass = FakeHass()
        self.assertIsNone(stored_model_provider_key(hass, ENTRY_ID))

    def test_async_setup_returns_accepted(self) -> None:
        hass = FakeHass()
        entry = FakeEntry()
        result = asyncio.run(async_setup_model_provider_key_storage(hass, entry))
        self.assertTrue(result["accepted"])
        self.assertEqual(result["code"], "model_provider_key_storage_loaded")


class ExtractProviderKeyActionTests(unittest.TestCase):
    def test_absent_field_is_keep(self) -> None:
        action, remaining = extract_provider_key_action({"other": "val"})
        self.assertEqual(action["kind"], "keep")
        self.assertIn("other", remaining)

    def test_empty_string_is_keep(self) -> None:
        action, _ = extract_provider_key_action({MODEL_PROVIDER_KEY_OPTIONS_FIELD: ""})
        self.assertEqual(action["kind"], "keep")

    def test_whitespace_only_is_keep(self) -> None:
        action, _ = extract_provider_key_action({MODEL_PROVIDER_KEY_OPTIONS_FIELD: "   "})
        self.assertEqual(action["kind"], "keep")

    def test_clear_sentinel_is_clear(self) -> None:
        action, _ = extract_provider_key_action({MODEL_PROVIDER_KEY_OPTIONS_FIELD: "clear"})
        self.assertEqual(action["kind"], "clear")

    def test_clear_sentinel_case_insensitive(self) -> None:
        action, _ = extract_provider_key_action({MODEL_PROVIDER_KEY_OPTIONS_FIELD: "CLEAR"})
        self.assertEqual(action["kind"], "clear")

    def test_valid_key_is_save(self) -> None:
        action, remaining = extract_provider_key_action(
            {MODEL_PROVIDER_KEY_OPTIONS_FIELD: VALID_KEY, "other": "x"}
        )
        self.assertEqual(action["kind"], "save")
        self.assertEqual(action["key"], VALID_KEY)
        self.assertNotIn(MODEL_PROVIDER_KEY_OPTIONS_FIELD, remaining)
        self.assertIn("other", remaining)

    def test_key_stripped_in_action(self) -> None:
        action, _ = extract_provider_key_action({MODEL_PROVIDER_KEY_OPTIONS_FIELD: f"  {VALID_KEY}  "})
        self.assertEqual(action["kind"], "save")
        self.assertEqual(action["key"], VALID_KEY)

    def test_non_dict_input_is_keep(self) -> None:
        action, _ = extract_provider_key_action(None)
        self.assertEqual(action["kind"], "keep")

    def test_short_key_is_still_save(self) -> None:
        # No minimum length for provider keys (unlike the 24-char worker token).
        action, _ = extract_provider_key_action({MODEL_PROVIDER_KEY_OPTIONS_FIELD: "sk-x"})
        self.assertEqual(action["kind"], "save")
        self.assertEqual(action["key"], "sk-x")


class KeyFlowsIntoPlannerClientTests(unittest.TestCase):
    """The stored key ends up as the Authorization header."""

    def test_setup_planner_passes_stored_key_to_client(self) -> None:
        hass = FakeHass()
        entry = FakeEntry()
        get_model_provider_key_storage(hass).save_key(ENTRY_ID, VALID_KEY)
        result = setup_model_provider_planner(hass, entry)
        self.assertTrue(result["accepted"])
        client = hass.data[DOMAIN][ENTRY_ID].get("model_provider_planner")
        self.assertIsInstance(client, OpenAICompatiblePlannerClient)
        self.assertEqual(client.api_key, VALID_KEY)

    def test_setup_planner_no_key_when_storage_empty(self) -> None:
        hass = FakeHass()
        entry = FakeEntry()
        setup_model_provider_planner(hass, entry)
        client = hass.data[DOMAIN][ENTRY_ID].get("model_provider_planner")
        self.assertIsInstance(client, OpenAICompatiblePlannerClient)
        self.assertIsNone(client.api_key)

    def test_build_planner_client_passes_api_key(self) -> None:
        cfg = {
            "model_provider_type": MODEL_PROVIDER_OPENAI_COMPATIBLE,
            "model_endpoint_url": "http://x/v1",
            "planner_model": "ollama/gemma",
        }
        client = _build_planner_client(cfg, {}, api_key=VALID_KEY)
        self.assertIsInstance(client, OpenAICompatiblePlannerClient)
        self.assertEqual(client.api_key, VALID_KEY)

    def test_build_planner_client_no_key_by_default(self) -> None:
        cfg = {
            "model_provider_type": MODEL_PROVIDER_OPENAI_COMPATIBLE,
            "model_endpoint_url": "http://x/v1",
            "planner_model": "ollama/gemma",
        }
        client = _build_planner_client(cfg, {})
        self.assertIsNone(client.api_key)


class ConfigSchemaRegressionTests(unittest.TestCase):
    """The provider key field name is forbidden in config data/options (ADR-0037)."""

    def test_field_name_in_forbidden_config_keys(self) -> None:
        self.assertIn(MODEL_PROVIDER_KEY_OPTIONS_FIELD, FORBIDDEN_CONFIG_KEYS)

    def test_key_in_config_data_is_rejected(self) -> None:
        bad_config = {**default_config_data(), MODEL_PROVIDER_KEY_OPTIONS_FIELD: VALID_KEY}
        result = validate_config_and_options(bad_config, default_options_data())
        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "forbidden_config_material")

    def test_key_in_options_data_is_rejected(self) -> None:
        bad_options = {**default_options_data(), MODEL_PROVIDER_KEY_OPTIONS_FIELD: VALID_KEY}
        result = validate_config_and_options(default_config_data(), bad_options)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "forbidden_config_material")


if __name__ == "__main__":
    unittest.main()
