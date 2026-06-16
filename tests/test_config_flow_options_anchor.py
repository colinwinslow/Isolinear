import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.config_flow_anchor import (  # noqa: E402
    verify_allowlist_form_default_round_trip,
    verify_config_flow_anchor,
    verify_config_flow_manifest,
    verify_config_flow_user_path,
    verify_invalid_flow_inputs,
    verify_live_allowlist_input_variants,
    verify_non_orchestration,
    verify_options_flow_tolerates_missing_config_entry_data,
    verify_options_flow_uses_passed_config_entry,
    verify_options_flow_path,
)


class ConfigFlowOptionsAnchorTests(unittest.TestCase):
    def test_manifest_enables_config_flow_and_files_exist(self):
        result = verify_config_flow_manifest(REPO_ROOT)

        self.assertTrue(result["manifest_config_flow_enabled"], result)
        self.assertTrue(result["config_flow_file_present"], result)
        self.assertTrue(result["config_flow_class_present"], result)
        self.assertTrue(result["options_flow_class_present"], result)
        self.assertEqual(result["flow_steps"]["config"], "user")
        self.assertEqual(result["flow_steps"]["options"], "init")

    def test_config_flow_accepts_and_normalizes_local_first_data(self):
        result = verify_config_flow_user_path()

        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["code"], "accepted")
        self.assertEqual(result["entry_title"], "Isolinear")
        self.assertEqual(result["config_data"]["model_provider_type"], "ollama_compatible")
        self.assertEqual(result["config_data"]["model_endpoint_url"], "http://localhost:11434")
        self.assertEqual(result["config_data"]["worker_endpoint_url"], "http://localhost:8765")
        self.assertIsNone(result["config_data"]["codegen_model"])
        self.assertIsNone(result["config_data"]["visual_validator_model"])
        self.assertEqual(result["options_data"]["default_render_mode"], "safe")

    def test_options_flow_accepts_and_normalizes_allowlist_text(self):
        result = verify_options_flow_path()

        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["code"], "accepted")
        self.assertEqual(result["options_data"]["default_render_mode"], "auto")
        self.assertEqual(result["options_data"]["max_codegen_repair_attempts"], 2)
        self.assertEqual(
            result["options_data"]["entity_allowlist"],
            [
                "sensor.upstairs_temperature",
                "sensor.downstairs_temperature",
                "binary_sensor.office_window",
            ],
        )

    def test_options_flow_accepts_raw_single_allowlist_string(self):
        result = verify_live_allowlist_input_variants()["variants"]["plain_entity_text"]

        self.assertTrue(result["accepted"], result)
        self.assertEqual(
            result["options_data"]["entity_allowlist"],
            ["sensor.family_room_sensor_temperature"],
        )

    def test_options_flow_accepts_json_style_allowlist_text(self):
        result = verify_live_allowlist_input_variants()["variants"]["json_array_text"]

        self.assertTrue(result["accepted"], result)
        self.assertEqual(
            result["options_data"]["entity_allowlist"],
            ["sensor.family_room_sensor_temperature"],
        )

    def test_options_flow_accepts_two_entity_json_allowlist_text(self):
        result = verify_live_allowlist_input_variants()["variants"]["json_array_two_entities"]

        self.assertTrue(result["accepted"], result)
        self.assertEqual(
            result["options_data"]["entity_allowlist"],
            [
                "sensor.family_room_sensor_temperature",
                "sensor.bathroom_sensor_temperature",
            ],
        )

    def test_options_flow_redisplays_allowlist_with_separators(self):
        result = verify_allowlist_form_default_round_trip()

        self.assertEqual(
            result["form_default"],
            [
                "sensor.family_room_sensor_temperature",
                "sensor.bathroom_sensor_temperature",
            ],
        )
        self.assertEqual(result["selector"]["type"], "entity")
        self.assertTrue(result["selector"]["multiple"], result)
        self.assertFalse(result["fused_default"], result)
        self.assertTrue(result["submitted"]["accepted"], result)
        self.assertEqual(
            result["submitted"]["options_data"]["entity_allowlist"],
            result["stored_entity_allowlist"],
        )
        self.assertEqual(
            result["legacy_text_default"],
            "sensor.family_room_sensor_temperature, sensor.bathroom_sensor_temperature",
        )
        self.assertEqual(
            result["legacy_stored_text_form_default"],
            result["stored_entity_allowlist"],
        )
        self.assertFalse(result["legacy_fused_default"], result)
        self.assertTrue(result["legacy_submitted"]["accepted"], result)
        self.assertEqual(
            result["legacy_submitted"]["options_data"]["entity_allowlist"],
            result["stored_entity_allowlist"],
        )

    def test_options_flow_uses_passed_config_entry(self):
        result = verify_options_flow_uses_passed_config_entry()

        self.assertTrue(result["retains_passed_config_entry"], result)
        self.assertEqual(result["result"]["type"], "create_entry")
        self.assertEqual(
            result["result"]["data"]["entity_allowlist"],
            ["sensor.family_room_sensor_temperature"],
        )

    def test_options_flow_tolerates_missing_config_entry_data(self):
        result = verify_options_flow_tolerates_missing_config_entry_data()

        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["result"]["type"], "create_entry")
        self.assertEqual(
            result["result"]["data"]["entity_allowlist"],
            ["sensor.family_room_sensor_temperature"],
        )

    def test_invalid_config_and_options_inputs_fail_closed(self):
        result = verify_invalid_flow_inputs()

        self.assertTrue(all(not item["accepted"] for item in result["config"].values()))
        self.assertTrue(all(not item["accepted"] for item in result["options"].values()))
        self.assertEqual(result["config"]["credential_endpoint_url"]["code"], "invalid_integration_config")
        self.assertEqual(result["config"]["secret_like_model"]["code"], "forbidden_config_material")
        self.assertEqual(result["options"]["invalid_render_mode"]["code"], "invalid_integration_config")
        self.assertEqual(result["options"]["duplicate_allowlist"]["code"], "invalid_integration_config")
        self.assertEqual(result["options"]["malformed_allowlist"]["field_errors"]["entity_allowlist"], "invalid_entity_id")
        self.assertEqual(result["options"]["secret_options_material"]["code"], "forbidden_config_material")

    def test_config_flow_anchor_verification_passes_without_orchestration(self):
        result = verify_config_flow_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])
        self.assertEqual(verify_non_orchestration()["aggregate"], result["non_orchestration"]["expected"])
        self.assertFalse(result["non_orchestration"]["aggregate"]["worker_called"])
        self.assertFalse(result["non_orchestration"]["aggregate"]["model_provider_called"])
        self.assertFalse(result["non_orchestration"]["aggregate"]["home_assistant_history_called"])
        self.assertFalse(result["non_orchestration"]["aggregate"]["semantic_memory_called"])
        self.assertFalse(result["non_orchestration"]["aggregate"]["home_assistant_mutation_called"])
        self.assertFalse(result["non_orchestration"]["aggregate"]["token_generated"])
        self.assertFalse(result["non_orchestration"]["aggregate"]["dashboard_resource_registered"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
