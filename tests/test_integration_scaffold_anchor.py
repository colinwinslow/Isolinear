import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.contracts import validate_contract  # noqa: E402
from Isolinear.integration_scaffold_anchor import (  # noqa: E402
    verify_command_stubs,
    verify_config_shape,
    verify_integration_scaffold_anchor,
    verify_manifest,
)


class IntegrationScaffoldAnchorTests(unittest.TestCase):
    def test_manifest_and_constants_define_home_assistant_scaffold(self):
        result = verify_manifest(REPO_ROOT)

        self.assertTrue(result["domain_matches"], result)
        self.assertTrue(result["version_present"], result)
        self.assertTrue(result["requirements_empty"], result)
        self.assertTrue(result["all_scaffold_files_present"], result["files"])
        self.assertEqual(result["manifest"]["domain"], "isolinear")
        self.assertEqual(result["manifest"]["integration_type"], "hub")

    def test_config_shape_accepts_defaults_and_rejects_bad_inputs(self):
        result = verify_config_shape()

        self.assertTrue(result["defaults"]["result"]["accepted"], result)
        self.assertEqual(
            result["defaults"]["result"]["options"]["default_render_mode"],
            "safe",
        )
        self.assertEqual(
            result["defaults"]["result"]["options"]["entity_allowlist"],
            [],
        )
        self.assertEqual(
            result["invalid_results"]["invalid_render_mode"]["code"],
            "invalid_integration_config",
        )
        self.assertEqual(
            result["invalid_results"]["secret_bearing"]["code"],
            "forbidden_config_material",
        )
        self.assertEqual(
            result["invalid_results"]["credential_endpoint_url"]["errors"],
            [{"path": "$.config_data.worker_endpoint_url", "reason": "endpoint_userinfo_forbidden"}],
        )
        self.assertEqual(
            result["invalid_results"]["secret_like_allowed_value"]["forbidden_matches"],
            [{"path": "$.config_data.planner_model", "reason": "secret_like_value"}],
        )
        self.assertTrue(all(not item["accepted"] for item in result["invalid_results"].values()))

    def test_known_websocket_commands_return_schema_valid_scaffold_snapshots(self):
        result = verify_command_stubs(REPO_ROOT)

        self.assertEqual(result["namespace"], "isolinear/v1")
        self.assertEqual(result["version"], 1)
        self.assertEqual(
            [command["type"] for command in result["commands"].values()],
            list(result["command_types"].values()),
        )
        for name, command in result["commands"].items():
            validate_contract("integration-ws-command", command, repo_root=REPO_ROOT)
            self.assertTrue(result["accepted_results"][name]["accepted"])
            snapshot = result["accepted_results"][name]["snapshot"]
            validate_contract("integration-job-snapshot", snapshot, repo_root=REPO_ROOT)
            self.assertEqual(snapshot["status"], "planning")
            self.assertIn("orchestration_not_implemented", snapshot["warnings"])
            self.assertFalse(result["accepted_results"][name]["orchestration"]["worker_called"])

    def test_unknown_leaky_and_mutating_websocket_commands_fail_closed(self):
        result = verify_command_stubs(REPO_ROOT)

        self.assertEqual(
            result["invalid_results"]["unknown_command"]["code"],
            "unknown_integration_ws_command",
        )
        self.assertEqual(
            result["invalid_results"]["wrong_version"]["code"],
            "unsupported_integration_ws_version",
        )
        self.assertEqual(
            result["invalid_results"]["leaky_worker_url"]["code"],
            "forbidden_card_boundary_content",
        )
        self.assertEqual(
            result["invalid_results"]["mutating_service_call"]["code"],
            "forbidden_card_boundary_content",
        )
        self.assertTrue(all(not item["accepted"] for item in result["invalid_results"].values()))
        self.assertTrue(
            all(not item["orchestration"]["home_assistant_mutation_called"] for item in result["invalid_results"].values())
        )

    def test_integration_scaffold_anchor_verification_passes(self):
        result = verify_integration_scaffold_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])
        self.assertFalse(result["no_orchestration"]["aggregate"]["worker_called"])
        self.assertFalse(result["no_orchestration"]["aggregate"]["model_provider_called"])
        self.assertFalse(result["no_orchestration"]["aggregate"]["home_assistant_history_called"])
        self.assertFalse(result["no_orchestration"]["aggregate"]["semantic_memory_called"])
        self.assertFalse(result["no_orchestration"]["aggregate"]["home_assistant_mutation_called"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
