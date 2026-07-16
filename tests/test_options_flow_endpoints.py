"""Editable connection endpoints in the options flow.

Colin's request (2026-07-04): make the model (Ollama) and worker endpoints
editable in the post-install Configure form, above the entity picker. The
endpoints live in config-entry DATA (single source of truth for consumers), so
the options form extracts them before options validation and routes the edits
into config data + rebuilds the endpoint-dependent setups live.
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
    ENDPOINT_OPTIONS_FIELDS,
    IsolinearOptionsFlow,
    build_options_flow_schema,
    extract_endpoint_edits,
)
from custom_components.isolinear.config_schema import (  # noqa: E402
    default_config_data,
    default_options_data,
)
from custom_components.isolinear.const import DOMAIN  # noqa: E402
from custom_components.isolinear.worker_token_storage import (  # noqa: E402
    get_worker_token_storage,
)

VALID_TOKEN = "deployment-worker-token-abcdef123456"
WORKER_URL = "http://10.0.1.39:8080"
MODEL_URL = "http://10.0.1.39:11434"


class FakeConfigEntries:
    def __init__(self) -> None:
        self.updates: list[tuple[str, Any]] = []

    def async_update_entry(self, entry, *, data=None, options=None):
        if data is not None:
            entry.data = dict(data)
        if options is not None:
            entry.options = dict(options)
        self.updates.append((entry.entry_id, data))
        return True


class FakeHass:
    def __init__(self) -> None:
        self.data: dict[str, Any] = {DOMAIN: {}}
        self.config_entries = FakeConfigEntries()


class FakeEntry:
    def __init__(self, entry_id: str, data: dict[str, Any], options: dict[str, Any] | None = None) -> None:
        self.entry_id = entry_id
        self.data = dict(data)
        self.options = dict(options or {})


def _flow(entry: FakeEntry, hass: FakeHass) -> IsolinearOptionsFlow:
    flow = IsolinearOptionsFlow(entry)
    flow.hass = hass
    return flow


def _options_input(**overrides: Any) -> dict[str, Any]:
    base = {
        "model_endpoint_url": MODEL_URL,
        "worker_endpoint_url": WORKER_URL,
        "default_render_mode": "safe",
        "max_codegen_repair_attempts": 1,
        "render_path": "auto",
        "entity_allowlist": ["sensor.upstairs_temperature"],
        "worker_api_token": "",  # keep existing
    }
    base.update(overrides)
    return base


class ExtractEndpointEditsTests(unittest.TestCase):
    def test_pulls_both_endpoints_stripped_leaves_rest(self) -> None:
        edits, remaining = extract_endpoint_edits(
            {
                "model_endpoint_url": f"  {MODEL_URL}  ",
                "worker_endpoint_url": WORKER_URL,
                "render_path": "auto",
            }
        )
        self.assertEqual(edits, {"model_endpoint_url": MODEL_URL, "worker_endpoint_url": WORKER_URL})
        self.assertEqual(remaining, {"render_path": "auto"})

    def test_absent_endpoints_yield_no_edits(self) -> None:
        edits, remaining = extract_endpoint_edits({"render_path": "auto"})
        self.assertEqual(edits, {})
        self.assertEqual(remaining, {"render_path": "auto"})

    def test_non_dict_input_is_safe(self) -> None:
        self.assertEqual(extract_endpoint_edits("nope"), ({}, {}))


class OptionsSchemaOrderTests(unittest.TestCase):
    def test_endpoints_render_above_the_entity_picker_with_config_defaults(self) -> None:
        schema = build_options_flow_schema(
            {"entity_allowlist": ["sensor.a"]},
            {**default_config_data(), "model_endpoint_url": MODEL_URL, "worker_endpoint_url": WORKER_URL},
        )
        fields = schema["fields"]
        self.assertEqual(fields[:2], list(ENDPOINT_OPTIONS_FIELDS))
        self.assertLess(fields.index("model_endpoint_url"), fields.index("entity_allowlist"))
        self.assertLess(fields.index("worker_endpoint_url"), fields.index("entity_allowlist"))
        self.assertEqual(schema["defaults"]["model_endpoint_url"], MODEL_URL)
        self.assertEqual(schema["defaults"]["worker_endpoint_url"], WORKER_URL)


class ApplyEndpointEditsTests(unittest.TestCase):
    def test_persists_to_data_and_rebuilds_worker_client(self) -> None:
        hass = FakeHass()
        get_worker_token_storage(hass).save_token("e1", VALID_TOKEN)
        entry = FakeEntry(
            "e1",
            data={**default_config_data(), "worker_endpoint_url": "http://localhost:8765"},
        )
        flow = _flow(entry, hass)

        updated = {**default_config_data(), "worker_endpoint_url": WORKER_URL, "model_endpoint_url": MODEL_URL}
        flow._apply_endpoint_edits(entry, updated)

        # config-entry data is the source of truth and now carries the new endpoints
        self.assertEqual(entry.data["worker_endpoint_url"], WORKER_URL)
        self.assertEqual(entry.data["model_endpoint_url"], MODEL_URL)
        # the worker renderer was rebuilt against the new endpoint (token present)
        setup = hass.data[DOMAIN]["e1"]["worker_renderer_setup"]
        self.assertTrue(setup["enabled"])
        client = hass.data[DOMAIN]["e1"]["worker_render_client"]
        self.assertEqual(client.endpoint_url, WORKER_URL)


class OptionsFlowEndToEndTests(unittest.TestCase):
    def _entry_hass(self) -> tuple[FakeEntry, FakeHass]:
        hass = FakeHass()
        get_worker_token_storage(hass).save_token("e1", VALID_TOKEN)
        entry = FakeEntry("e1", data=default_config_data(), options=default_options_data())
        return entry, hass

    def test_valid_submit_persists_endpoints_and_keeps_them_out_of_options(self) -> None:
        entry, hass = self._entry_hass()
        result = asyncio.run(_flow(entry, hass).async_step_init(_options_input()))

        self.assertEqual(result["type"], "create_entry")
        # endpoints landed in config-entry data
        self.assertEqual(entry.data["worker_endpoint_url"], WORKER_URL)
        self.assertEqual(entry.data["model_endpoint_url"], MODEL_URL)
        # ...and NOT in the persisted options payload (exact-keys contract intact)
        self.assertNotIn("worker_endpoint_url", result["data"])
        self.assertNotIn("model_endpoint_url", result["data"])
        self.assertEqual(result["data"]["entity_allowlist"], ["sensor.upstairs_temperature"])

    def test_bad_worker_url_is_a_field_error_and_is_not_persisted(self) -> None:
        entry, hass = self._entry_hass()
        result = asyncio.run(
            _flow(entry, hass).async_step_init(_options_input(worker_endpoint_url="not-a-url"))
        )
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"].get("worker_endpoint_url"), "must_be_http_url")
        self.assertEqual(entry.data["worker_endpoint_url"], default_config_data()["worker_endpoint_url"])

    def test_userinfo_in_endpoint_is_rejected(self) -> None:
        entry, hass = self._entry_hass()
        result = asyncio.run(
            _flow(entry, hass).async_step_init(
                _options_input(worker_endpoint_url="http://user:pass@10.0.1.39:8080")
            )
        )
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"].get("worker_endpoint_url"), "endpoint_userinfo_forbidden")


class ProviderSwitchInPlaceTests(unittest.TestCase):
    """ADR-0037: an existing Ollama install can switch to the LiteLLM proxy via
    the options form (keeping its entity allowlist) — the provider fields route
    into config-entry data and the model-provider client is rebuilt live."""

    def _ollama_entry_hass(self):
        from custom_components.isolinear.const import MODEL_PROVIDER_OLLAMA_COMPATIBLE

        hass = FakeHass()
        get_worker_token_storage(hass).save_token("e1", VALID_TOKEN)
        ollama_config = {
            **default_config_data(),
            "model_provider_type": MODEL_PROVIDER_OLLAMA_COMPATIBLE,
            "model_endpoint_url": "http://10.0.1.39:11434",
            "planner_model": "llama3.1",
        }
        # A non-empty allowlist we must NOT lose across the switch.
        options = {**default_options_data(), "entity_allowlist": ["sensor.upstairs_temperature"]}
        entry = FakeEntry("e1", data=ollama_config, options=options)
        return entry, hass

    def test_switch_to_litellm_persists_to_data_and_rebuilds_openai_client(self) -> None:
        from custom_components.isolinear.const import (
            DOMAIN,
            MODEL_PROVIDER_OPENAI_COMPATIBLE,
        )
        from custom_components.isolinear.model_provider import (
            OpenAICompatiblePlannerClient,
            get_model_provider_planner,
        )

        entry, hass = self._ollama_entry_hass()
        result = asyncio.run(
            _flow(entry, hass).async_step_init(
                _options_input(
                    model_provider_type=MODEL_PROVIDER_OPENAI_COMPATIBLE,
                    model_endpoint_url="http://10.0.1.39:4000/v1",
                    planner_model="ollama/gemma",
                )
            )
        )
        self.assertEqual(result["type"], "create_entry")
        # provider + endpoint landed in config-entry data
        self.assertEqual(entry.data["model_provider_type"], MODEL_PROVIDER_OPENAI_COMPATIBLE)
        self.assertEqual(entry.data["model_endpoint_url"], "http://10.0.1.39:4000/v1")
        self.assertEqual(entry.data["planner_model"], "ollama/gemma")
        # the allowlist is preserved (the whole reason for switching in place)
        self.assertEqual(result["data"]["entity_allowlist"], ["sensor.upstairs_temperature"])
        # the live planner client was rebuilt as the OpenAI-compatible client
        planner = get_model_provider_planner(hass, "e1")
        self.assertIsInstance(planner, OpenAICompatiblePlannerClient)
        self.assertEqual(planner.endpoint_url, "http://10.0.1.39:4000/v1")
        self.assertEqual(planner.planner_model, "ollama/gemma")


if __name__ == "__main__":
    unittest.main()
