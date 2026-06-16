import asyncio
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.websocket_command_registration_anchor import (  # noqa: E402
    FakeConfigEntry,
    FakeConnection,
    verify_idempotent_command_registration,
    verify_invalid_registered_commands_fail_closed,
    verify_home_assistant_routing_schema_accepts_card_payload,
    verify_missing_config_entry_rejection,
    verify_registered_callback_snapshots,
    verify_registered_command_names,
    verify_setup_entry_websocket_registration,
    verify_websocket_command_registration_anchor,
)
from custom_components.isolinear.const import (  # noqa: E402
    CONFIG_ENTRY_AUTO,
    DOMAIN,
    INTEGRATION_COMMAND_TYPES,
    INTEGRATION_WS_VERSION,
)
from custom_components.isolinear.job_orchestration import DATA_JOB_ORCHESTRATION_SETUP  # noqa: E402
from custom_components.isolinear.websocket_api import (  # noqa: E402
    DATA_WEBSOCKET_OBSERVABILITY,
    handle_registered_ws_command,
    registered_websocket_handlers,
)


class FakeConfigEntries:
    def __init__(self, entry_ids):
        self._entries = [FakeConfigEntry(entry_id) for entry_id in entry_ids]

    def async_entries(self, domain=None):
        return list(self._entries)


class SchedulingHass:
    def __init__(self, *, include_entry: bool = True, registry_entry_ids=None) -> None:
        self.data = {DOMAIN: {}}
        if include_entry:
            self.data[DOMAIN]["fake-config-entry"] = {"entry": FakeConfigEntry()}
        if registry_entry_ids is not None:
            self.config_entries = FakeConfigEntries(registry_entry_ids)
        self.background_tasks = []
        self.executor_calls = []

    def async_create_background_task(self, coro, name, **kwargs):
        self.background_tasks.append({"name": name, "kwargs": kwargs})
        return asyncio.run(coro)

    def async_add_executor_job(self, func, *args):
        self.executor_calls.append({"func": func.__name__, "args": args})
        return func(*args)


class WebSocketCommandRegistrationAnchorTests(unittest.TestCase):
    def test_command_names_are_registered_with_home_assistant_boundary(self):
        result = verify_registered_command_names(REPO_ROOT)

        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["namespace"], "isolinear/v1")
        self.assertEqual(result["version"], 1)
        self.assertEqual(result["registered_count"], 5)
        self.assertEqual(result["registered_types"], result["expected_commands"])
        self.assertTrue(result["registered_via_async_register_command"], result)
        self.assertTrue(result["handlers_have_command_schema"], result)
        self.assertEqual(result["hass_data_commands"], result["expected_commands"])

    def test_setup_entry_stores_config_entry_scoped_registration_result(self):
        result = verify_setup_entry_websocket_registration(REPO_ROOT)

        self.assertTrue(result["setup_accepted"], result)
        self.assertTrue(result["registration"]["accepted"], result)
        self.assertEqual(result["entry_id"], "fake-config-entry")
        self.assertTrue(result["config_entry_scoped_result"], result)
        self.assertIn("websocket_api", result["entry_data_keys"])
        self.assertEqual(result["registered_count"], 5)

    def test_registered_callbacks_return_schema_valid_scaffold_snapshots(self):
        result = verify_registered_callback_snapshots(REPO_ROOT)

        self.assertTrue(result["registration"]["accepted"], result)
        for name, dispatch in result["dispatch_results"].items():
            self.assertTrue(dispatch["accepted"], name)
            self.assertEqual(dispatch["connection"]["errors"], [])
            self.assertEqual(len(dispatch["connection"]["results"]), 1)
            snapshot = dispatch["connection"]["results"][0]["result"]
            self.assertEqual(snapshot["status"], "planning")
            self.assertIn("orchestration_not_implemented", snapshot["warnings"])
            self.assertTrue(result["snapshot_validation"][name]["accepted"], name)

    def test_invalid_registered_commands_fail_closed_without_snapshots(self):
        result = verify_invalid_registered_commands_fail_closed()

        self.assertEqual(
            result["dispatch_results"]["unknown_command"]["connection"]["errors"][0]["code"],
            "unknown_integration_ws_command",
        )
        self.assertEqual(
            result["dispatch_results"]["wrong_version"]["connection"]["errors"][0]["code"],
            "unsupported_integration_ws_version",
        )
        self.assertEqual(
            result["dispatch_results"]["leaky_worker_url"]["connection"]["errors"][0]["code"],
            "forbidden_card_boundary_content",
        )
        self.assertEqual(
            result["dispatch_results"]["mutating_service_call"]["connection"]["errors"][0]["code"],
            "forbidden_card_boundary_content",
        )
        self.assertTrue(all(not item["accepted"] for item in result["dispatch_results"].values()))
        self.assertTrue(all(not item["connection"]["results"] for item in result["dispatch_results"].values()))

    def test_home_assistant_routing_schema_accepts_card_transport_envelope(self):
        result = verify_home_assistant_routing_schema_accepts_card_payload()

        self.assertTrue(result["home_assistant_routing_result"]["accepted"], result)
        self.assertTrue(result["home_assistant_routing_result"]["handler_called"], result)
        self.assertEqual(
            result["home_assistant_routing_result"]["routing"]["code"],
            "routing_schema_accepts_transport_envelope",
        )
        self.assertTrue(result["handler_schema"]["allows_extra"], result)
        self.assertFalse(result["internal_strict_extra_result"]["accepted"], result)
        self.assertTrue(result["internal_strict_extra_result"]["handler_called"], result)
        self.assertEqual(
            result["internal_strict_extra_result"]["connection"]["errors"][0]["code"],
            "invalid_integration_ws_command",
        )

    def test_missing_config_entry_scope_fails_closed(self):
        result = verify_missing_config_entry_rejection()

        self.assertFalse(result["dispatch_result"]["accepted"], result)
        self.assertEqual(
            result["dispatch_result"]["connection"]["errors"][0]["code"],
            "unknown_config_entry",
        )
        self.assertEqual(result["dispatch_result"]["connection"]["results"], [])

    def test_auto_config_entry_resolves_when_exactly_one_entry_exists(self):
        hass = SchedulingHass()
        message = {
            "id": 61,
            "type": INTEGRATION_COMMAND_TYPES["start_job"],
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": CONFIG_ENTRY_AUTO,
            "prompt": "Show the family room temperature",
        }

        result = handle_registered_ws_command(hass, message)

        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["config_entry_id"], "fake-config-entry")
        self.assertEqual(result["snapshot"]["status"], "planning")

    def test_configured_orchestration_does_not_fall_back_to_job_state_scaffold(self):
        hass = SchedulingHass()
        hass.data[DOMAIN]["fake-config-entry"][DATA_JOB_ORCHESTRATION_SETUP] = {
            "accepted": True,
            "code": "job_orchestration_ready",
            "enabled": False,
            "approved_entity_ids": [],
        }
        message = {
            "id": 67,
            "type": INTEGRATION_COMMAND_TYPES["start_job"],
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": CONFIG_ENTRY_AUTO,
            "prompt": "Show the family room temperature",
        }

        result = handle_registered_ws_command(hass, message)

        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["config_entry_id"], "fake-config-entry")
        self.assertEqual(result["snapshot"]["status"], "failed")
        self.assertEqual(result["snapshot"]["failure"]["code"], "no_approved_entities_available")
        self.assertNotIn("orchestration_not_implemented", result["snapshot"]["warnings"])
        self.assertEqual(
            result["snapshot"]["progress"]["stage"],
            "job_orchestration_scaffold_failed",
        )

    def test_configured_orchestration_routes_followup_commands_to_orchestration_boundary(self):
        hass = SchedulingHass()
        hass.data[DOMAIN]["fake-config-entry"][DATA_JOB_ORCHESTRATION_SETUP] = {
            "accepted": True,
            "code": "job_orchestration_ready",
            "enabled": False,
            "approved_entity_ids": [],
        }
        commands = [
            {
                "id": 68,
                "type": INTEGRATION_COMMAND_TYPES["answer_clarification"],
                "version": INTEGRATION_WS_VERSION,
                "config_entry_id": CONFIG_ENTRY_AUTO,
                "job_id": "missing-job",
                "question_id": "select_approved_entity",
                "option_id": "sensor.family_room_sensor_temperature",
                "remember": False,
            },
            {
                "id": 69,
                "type": INTEGRATION_COMMAND_TYPES["retry_job"],
                "version": INTEGRATION_WS_VERSION,
                "config_entry_id": CONFIG_ENTRY_AUTO,
                "job_id": "missing-job",
            },
            {
                "id": 70,
                "type": INTEGRATION_COMMAND_TYPES["get_snapshot"],
                "version": INTEGRATION_WS_VERSION,
                "config_entry_id": CONFIG_ENTRY_AUTO,
                "job_id": "missing-job",
            },
            {
                "id": 71,
                "type": INTEGRATION_COMMAND_TYPES["subscribe_job"],
                "version": INTEGRATION_WS_VERSION,
                "config_entry_id": CONFIG_ENTRY_AUTO,
                "job_id": "missing-job",
            },
        ]

        results = [handle_registered_ws_command(hass, command) for command in commands]

        self.assertTrue(all(not result["accepted"] for result in results), results)
        self.assertTrue(all(result["code"] == "unknown_job" for result in results), results)
        self.assertTrue(all("snapshot" not in result for result in results), results)

    def test_auto_config_entry_falls_back_to_config_entry_registry(self):
        hass = SchedulingHass(include_entry=False, registry_entry_ids=["registry-entry-001"])
        message = {
            "id": 63,
            "type": INTEGRATION_COMMAND_TYPES["start_job"],
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": CONFIG_ENTRY_AUTO,
            "prompt": "Show the family room temperature",
        }

        result = handle_registered_ws_command(hass, message)

        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["config_entry_id"], "registry-entry-001")
        self.assertEqual(result["snapshot"]["status"], "planning")

    def test_auto_config_entry_fails_closed_when_multiple_entries_exist(self):
        hass = SchedulingHass()
        hass.data[DOMAIN]["second-config-entry"] = {"entry": FakeConfigEntry("second-config-entry")}
        message = {
            "id": 62,
            "type": INTEGRATION_COMMAND_TYPES["start_job"],
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": CONFIG_ENTRY_AUTO,
            "prompt": "Show the family room temperature",
        }

        result = handle_registered_ws_command(hass, message)

        self.assertFalse(result["accepted"], result)
        self.assertEqual(result["code"], "ambiguous_config_entry")
        self.assertEqual(result["config_entry_id"], CONFIG_ENTRY_AUTO)

    def test_auto_config_entry_registry_fallback_fails_closed_when_ambiguous(self):
        hass = SchedulingHass(
            include_entry=False,
            registry_entry_ids=["registry-entry-001", "registry-entry-002"],
        )
        message = {
            "id": 64,
            "type": INTEGRATION_COMMAND_TYPES["start_job"],
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": CONFIG_ENTRY_AUTO,
            "prompt": "Show the family room temperature",
        }

        result = handle_registered_ws_command(hass, message)

        self.assertFalse(result["accepted"], result)
        self.assertEqual(result["code"], "ambiguous_config_entry")
        self.assertEqual(result["config_entry_id"], CONFIG_ENTRY_AUTO)

    def test_registered_websocket_decisions_are_observable(self):
        hass = SchedulingHass()
        accepted_message = {
            "id": 65,
            "type": INTEGRATION_COMMAND_TYPES["start_job"],
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": CONFIG_ENTRY_AUTO,
            "prompt": "Show the family room temperature",
        }
        rejected_message = {
            "id": 66,
            "type": INTEGRATION_COMMAND_TYPES["get_snapshot"],
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": "missing-config-entry",
            "job_id": "job-001",
        }

        accepted = handle_registered_ws_command(hass, accepted_message)
        rejected = handle_registered_ws_command(hass, rejected_message)
        events = hass.data[DOMAIN][DATA_WEBSOCKET_OBSERVABILITY]

        self.assertTrue(accepted["accepted"], accepted)
        self.assertFalse(rejected["accepted"], rejected)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["command_type"], INTEGRATION_COMMAND_TYPES["start_job"])
        self.assertEqual(events[0]["requested_config_entry_id"], CONFIG_ENTRY_AUTO)
        self.assertEqual(events[0]["resolved_config_entry_id"], "fake-config-entry")
        self.assertTrue(events[0]["accepted"])
        self.assertEqual(events[0]["code"], "registered_job_state_command_accepted")
        self.assertEqual(events[1]["command_type"], INTEGRATION_COMMAND_TYPES["get_snapshot"])
        self.assertEqual(events[1]["requested_config_entry_id"], "missing-config-entry")
        self.assertIsNone(events[1]["resolved_config_entry_id"])
        self.assertFalse(events[1]["accepted"])
        self.assertEqual(events[1]["code"], "unknown_config_entry")

    def test_repeated_setup_does_not_duplicate_command_registration(self):
        result = verify_idempotent_command_registration()

        self.assertTrue(result["first_setup"], result)
        self.assertTrue(result["second_setup"], result)
        self.assertEqual(result["first_count"], 5)
        self.assertEqual(result["second_count"], 5)
        self.assertEqual(result["duplicate_count"], 0)
        self.assertEqual(result["second_registration"]["code"], "websocket_commands_already_registered")

    def test_registered_handler_uses_home_assistant_async_response_scheduler(self):
        hass = SchedulingHass()
        connection = FakeConnection()
        handler = next(
            item
            for item in registered_websocket_handlers()
            if getattr(item, "_isolinear_command_type", None) == INTEGRATION_COMMAND_TYPES["start_job"]
        )
        message = {
            "id": 1,
            "type": INTEGRATION_COMMAND_TYPES["start_job"],
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": "fake-config-entry",
            "prompt": "Show the temperature",
        }

        result = handler(hass, connection, message)

        self.assertIsNone(result)
        self.assertEqual(len(hass.background_tasks), 1)
        self.assertEqual(hass.background_tasks[0]["name"], "websocket_api.async:ws_handle_isolinear_command")
        self.assertEqual(hass.executor_calls[0]["func"], "handle_registered_ws_command")
        self.assertEqual(connection.errors, [])
        self.assertEqual(connection.results[0]["result"]["status"], "planning")

    def test_websocket_command_registration_anchor_verification_passes(self):
        result = verify_websocket_command_registration_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])
        self.assertFalse(result["side_effects"]["forbidden_aggregate"]["worker_called"])
        self.assertFalse(result["side_effects"]["forbidden_aggregate"]["model_provider_called"])
        self.assertFalse(result["side_effects"]["forbidden_aggregate"]["home_assistant_history_called"])
        self.assertFalse(result["side_effects"]["forbidden_aggregate"]["semantic_memory_called"])
        self.assertFalse(
            result["side_effects"]["forbidden_aggregate"]["home_assistant_service_or_state_mutation_called"]
        )
        self.assertFalse(result["side_effects"]["forbidden_aggregate"]["token_generated"])
        self.assertFalse(result["side_effects"]["forbidden_aggregate"]["job_orchestration_called"])
        self.assertFalse(
            result["side_effects"]["forbidden_aggregate"]["dashboard_resource_metadata_written_or_reused"]
        )
        self.assertTrue(result["side_effects"]["allowed_aggregate"]["websocket_command_registered"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
