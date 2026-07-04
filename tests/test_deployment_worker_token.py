"""Deployment-supplied worker token (ADR-0032, spec deployment-worker-token).

Covers: the storage helper round-trip; the write-only options-field action
split (keep/save/clear/too-short); the renderer enable matrix from
endpoint+stored-token; on-demand `check_health()` against the real packet-2
in-process server; and the machinery-deletion guard (no integration module
imports the retired ADR-0015/0016 names).
"""

from __future__ import annotations

import asyncio
import json
import sys
import threading
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "worker"))

from custom_components.isolinear.config_flow import (  # noqa: E402
    WORKER_TOKEN_OPTIONS_FIELD,
    extract_worker_token_action,
)
from custom_components.isolinear.const import DOMAIN  # noqa: E402
from custom_components.isolinear.worker_renderer import (  # noqa: E402
    HttpJsonWorkerRenderClient,
    build_worker_health_request,
    setup_worker_renderer,
)
from custom_components.isolinear.worker_token_storage import (  # noqa: E402
    DATA_WORKER_TOKEN_STORE,
    WorkerTokenStorageHelper,
    get_worker_token_storage,
    is_valid_deployment_worker_token,
    stored_worker_token,
)
from isolinear_worker.http_server import (  # noqa: E402
    WorkerConfig,
    WorkerHTTPServer,
)

VALID_TOKEN = "deployment-worker-token-abcdef123456"
ENTRY_ID = "deployment-token-entry"


class FakeHass:
    def __init__(self) -> None:
        self.data: dict[str, Any] = {DOMAIN: {}}


class FakeEntry:
    def __init__(self, *, endpoint: str | None) -> None:
        self.entry_id = ENTRY_ID
        self.data = {"worker_endpoint_url": endpoint} if endpoint else {}
        self.options: dict[str, Any] = {}


class FakeStore:
    """Duck-typed HA Store capturing async_delay_save payloads."""

    def __init__(self, loaded: dict[str, Any] | None = None) -> None:
        self.loaded = loaded
        self.saved: list[dict[str, Any]] = []

    async def async_load(self) -> dict[str, Any] | None:
        return self.loaded

    def async_delay_save(self, data_fn, _delay) -> None:
        self.saved.append(data_fn())


class WorkerTokenStorageTests(unittest.TestCase):
    def test_save_load_round_trip_and_clear(self) -> None:
        store = FakeStore()
        helper = WorkerTokenStorageHelper(ha_store=store)

        self.assertEqual(helper.save_token(ENTRY_ID, VALID_TOKEN), {"accepted": True})
        self.assertEqual(helper.token_for(ENTRY_ID), VALID_TOKEN)
        self.assertTrue(store.saved, "save was not scheduled")

        reloaded = WorkerTokenStorageHelper(ha_store=FakeStore(loaded=store.saved[-1]))
        asyncio.run(reloaded.async_load())
        self.assertEqual(reloaded.token_for(ENTRY_ID), VALID_TOKEN)

        helper.clear_token(ENTRY_ID)
        self.assertIsNone(helper.token_for(ENTRY_ID))

    def test_short_token_is_rejected_never_stored(self) -> None:
        helper = WorkerTokenStorageHelper()
        result = helper.save_token(ENTRY_ID, "too-short")
        self.assertEqual(result, {"accepted": False, "error": "worker_token_too_short"})
        self.assertIsNone(helper.token_for(ENTRY_ID))
        self.assertFalse(is_valid_deployment_worker_token("x" * 23))
        self.assertTrue(is_valid_deployment_worker_token("x" * 24))

    def test_summary_never_carries_token_values(self) -> None:
        helper = WorkerTokenStorageHelper()
        helper.save_token(ENTRY_ID, VALID_TOKEN)
        self.assertNotIn(VALID_TOKEN, json.dumps(helper.summary()))
        self.assertEqual(helper.summary()["entry_ids"], [ENTRY_ID])


class OptionsTokenActionTests(unittest.TestCase):
    def test_absent_or_empty_keeps(self) -> None:
        for user_input in ({}, {WORKER_TOKEN_OPTIONS_FIELD: ""}, {WORKER_TOKEN_OPTIONS_FIELD: "   "}):
            action, remaining = extract_worker_token_action({**user_input, "render_path": "auto"})
            self.assertEqual(action, {"kind": "keep"})
            self.assertNotIn(WORKER_TOKEN_OPTIONS_FIELD, remaining)
            self.assertEqual(remaining.get("render_path"), "auto")

    def test_valid_token_saves_and_is_stripped_from_options(self) -> None:
        action, remaining = extract_worker_token_action(
            {WORKER_TOKEN_OPTIONS_FIELD: f"  {VALID_TOKEN}  ", "render_path": "auto"}
        )
        self.assertEqual(action, {"kind": "save", "token": VALID_TOKEN})
        # The options payload never carries the token (config_schema fail-closed intact).
        self.assertNotIn(VALID_TOKEN, json.dumps(remaining))

    def test_clear_sentinel_clears(self) -> None:
        action, _ = extract_worker_token_action({WORKER_TOKEN_OPTIONS_FIELD: "Clear"})
        self.assertEqual(action, {"kind": "clear"})

    def test_short_value_errors(self) -> None:
        action, _ = extract_worker_token_action({WORKER_TOKEN_OPTIONS_FIELD: "abc123"})
        self.assertEqual(action, {"kind": "too_short"})


class RendererWiringTests(unittest.TestCase):
    def _hass_with_stored_token(self, token: str | None) -> FakeHass:
        hass = FakeHass()
        if token is not None:
            get_worker_token_storage(hass).save_token(ENTRY_ID, token)
        return hass

    def test_endpoint_plus_stored_token_enables_client(self) -> None:
        hass = self._hass_with_stored_token(VALID_TOKEN)
        entry = FakeEntry(endpoint="http://10.0.1.39:8080")

        setup = setup_worker_renderer(hass, entry)

        self.assertTrue(setup["enabled"])
        self.assertEqual(setup["code"], "worker_renderer_configured")
        client = hass.data[DOMAIN][ENTRY_ID]["worker_render_client"]
        self.assertIsInstance(client, HttpJsonWorkerRenderClient)
        self.assertEqual(client.worker_token, VALID_TOKEN)
        self.assertEqual(stored_worker_token(hass, ENTRY_ID), VALID_TOKEN)

    def test_missing_token_disables(self) -> None:
        hass = self._hass_with_stored_token(None)
        setup = setup_worker_renderer(hass, FakeEntry(endpoint="http://10.0.1.39:8080"))
        self.assertFalse(setup["enabled"])
        self.assertEqual(setup["code"], "worker_renderer_token_missing")

    def test_missing_endpoint_disables_even_with_token(self) -> None:
        hass = self._hass_with_stored_token(VALID_TOKEN)
        setup = setup_worker_renderer(hass, FakeEntry(endpoint=None))
        self.assertFalse(setup["enabled"])

    def test_storage_helper_is_cached_on_hass(self) -> None:
        hass = FakeHass()
        first = get_worker_token_storage(hass)
        self.assertIs(get_worker_token_storage(hass), first)
        self.assertIs(hass.data[DOMAIN][DATA_WORKER_TOKEN_STORE], first)

    def test_token_only_repaste_rebuilds_client_via_options_flow(self) -> None:
        # Architecture-review finding: HA fires update listeners only when the
        # options payload changed, so a token-only paste must rebuild the
        # client from the options flow itself.
        from custom_components.isolinear.config_flow import IsolinearOptionsFlow

        hass = self._hass_with_stored_token(None)
        entry = FakeEntry(endpoint="http://10.0.1.39:8080")
        setup = setup_worker_renderer(hass, entry)
        self.assertFalse(setup["enabled"])

        flow = IsolinearOptionsFlow(entry)
        flow.hass = hass
        flow._apply_worker_token_action(entry, {"kind": "save", "token": VALID_TOKEN})

        rebuilt = hass.data[DOMAIN][ENTRY_ID]["worker_renderer_setup"]
        self.assertTrue(rebuilt["enabled"])
        client = hass.data[DOMAIN][ENTRY_ID]["worker_render_client"]
        self.assertEqual(client.worker_token, VALID_TOKEN)

        flow._apply_worker_token_action(entry, {"kind": "clear"})
        cleared = hass.data[DOMAIN][ENTRY_ID]["worker_renderer_setup"]
        self.assertFalse(cleared["enabled"])
        self.assertNotIn("worker_render_client", hass.data[DOMAIN][ENTRY_ID])


class CheckHealthAgainstRealServerTests(unittest.TestCase):
    """Scenario D — on-demand health over the real packet-2 HTTP server."""

    @classmethod
    def setUpClass(cls) -> None:
        (REPO_ROOT / ".test-output").mkdir(exist_ok=True)
        cls.work_root = REPO_ROOT / ".test-output" / "deployment-token-health"
        cls.work_root.mkdir(exist_ok=True)
        config = WorkerConfig(token=VALID_TOKEN, work_root=cls.work_root)
        cls.server = WorkerHTTPServer(config)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def _client(self, token: str) -> HttpJsonWorkerRenderClient:
        return HttpJsonWorkerRenderClient(
            endpoint_url=f"http://127.0.0.1:{self.port}",
            worker_token=token,
            timeout_seconds=5,
        )

    def test_health_envelope_with_correct_token(self) -> None:
        client = self._client(VALID_TOKEN)
        request = build_worker_health_request(
            request_id="deployment-token-health", worker_token=VALID_TOKEN
        )
        result = client.check_health(request)

        self.assertTrue(result["accepted"])
        self.assertEqual(result["code"], "worker_health_result_received")
        # Dev box: matplotlib is not importable under -I, so status is
        # environment-dependent — assert the envelope shape, not readiness.
        self.assertIn(result["health_result"]["status"], ("ready", "not_ready"))
        self.assertNotIn(VALID_TOKEN, json.dumps(result))

    def test_wrong_token_surfaces_fault_without_token_material(self) -> None:
        wrong = "wrong-token-000000000000000000"
        client = self._client(wrong)
        request = build_worker_health_request(
            request_id="deployment-token-health-401", worker_token=wrong
        )
        result = client.check_health(request)

        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "worker_health_http_error")
        self.assertNotIn(wrong, json.dumps(result))
        self.assertNotIn(VALID_TOKEN, json.dumps(result))

    def test_connection_fault_is_a_dict_not_an_exception(self) -> None:
        client = HttpJsonWorkerRenderClient(
            endpoint_url="http://127.0.0.1:9",  # discard port — refused
            worker_token=VALID_TOKEN,
            timeout_seconds=2,
        )
        request = build_worker_health_request(
            request_id="deployment-token-health-refused", worker_token=VALID_TOKEN
        )
        result = client.check_health(request)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "worker_health_connection_error")


class MachineryDeletionGuardTests(unittest.TestCase):
    """Scenario E — the retired ADR-0015/0016 modules stay gone."""

    RETIRED_MODULES = (
        "worker_token_lifecycle",
        "worker_readiness",
        "worker_health",
        "worker_health_polling",
        "worker_health_polling_constants",
        "worker_health_polling_contract",
        "worker_health_polling_state",
        "worker_health_polling_storage",
    )
    RETIRED_SCHEMAS = (
        "integration-worker-token-lifecycle-state.schema.json",
        "integration-worker-health-polling-state.schema.json",
        "integration-worker-health.schema.json",
        "integration-worker-readiness.schema.json",
        "worker-health-request.schema.json",
    )

    def test_no_integration_module_imports_retired_names(self) -> None:
        package_dir = REPO_ROOT / "custom_components" / "isolinear"
        for path in package_dir.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for module in self.RETIRED_MODULES:
                self.assertNotIn(
                    f"from .{module} import",
                    source,
                    f"{path.name} still imports retired module {module}",
                )
            self.assertNotIn("import worker_token_lifecycle", source, path.name)

    def test_no_eval_imports_retired_names(self) -> None:
        # Architecture-review finding: pytest never runs evals, so a stale
        # import there survives a green suite. Pin evals/ too.
        for path in (REPO_ROOT / "evals").glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for module in self.RETIRED_MODULES:
                self.assertNotIn(
                    f"custom_components.isolinear import {module}",
                    source,
                    f"evals/{path.name} still imports retired module {module}",
                )

    def test_retired_module_files_and_schemas_are_gone(self) -> None:
        package_dir = REPO_ROOT / "custom_components" / "isolinear"
        for module in self.RETIRED_MODULES:
            self.assertFalse((package_dir / f"{module}.py").exists(), module)
        for schema in self.RETIRED_SCHEMAS:
            self.assertFalse((package_dir / "schemas" / schema).exists(), schema)
            self.assertFalse((REPO_ROOT / "docs" / "schemas" / schema).exists(), schema)


if __name__ == "__main__":
    unittest.main()
