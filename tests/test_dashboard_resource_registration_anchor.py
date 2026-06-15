import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.dashboard_resource_anchor import (  # noqa: E402
    verify_dashboard_resource_anchor,
    verify_idempotent_registration,
    verify_missing_bundle_rejection,
    verify_preexisting_resource_reuse,
    verify_setup_entry_registration,
    verify_static_path_registration,
    verify_stale_resource_update,
    verify_unavailable_resource_collection_rejection,
)
from custom_components.isolinear.const import INTEGRATION_VERSION  # noqa: E402


class DashboardResourceRegistrationAnchorTests(unittest.TestCase):
    def test_card_bundle_is_served_from_integration_static_path(self):
        result = verify_static_path_registration(REPO_ROOT)

        self.assertTrue(result["bundle_exists"], result)
        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["static_path"]["url_path"], "/api/isolinear/static")
        self.assertEqual(result["static_path"]["cache_headers"], True)
        self.assertEqual(
            result["resource"]["url"],
            f"/api/isolinear/static/isolinear-card.js?v={INTEGRATION_VERSION}",
        )
        self.assertEqual(result["resource"]["type"], "module")

    def test_config_entry_setup_registers_resource_metadata(self):
        result = verify_setup_entry_registration(REPO_ROOT)

        self.assertTrue(result["setup_accepted"], result)
        self.assertTrue(result["entry_result"]["accepted"], result)
        self.assertEqual(result["entry_id"], "resource-entry-001")
        self.assertEqual(len(result["resources"]), 1)
        self.assertEqual(
            result["resources"][0]["url"],
            f"/api/isolinear/static/isolinear-card.js?v={INTEGRATION_VERSION}",
        )
        self.assertEqual(result["resources"][0]["type"], "module")
        self.assertTrue(result["entry_result"]["config_entry_scoped"])

    def test_repeated_registration_does_not_duplicate_metadata(self):
        result = verify_idempotent_registration(REPO_ROOT)

        self.assertTrue(result["first"]["accepted"], result)
        self.assertTrue(result["second"]["accepted"], result)
        self.assertEqual(result["resource_count"], 1)
        self.assertEqual(result["create_call_count"], 1)
        self.assertEqual(result["second"]["code"], "dashboard_resource_already_registered")

    def test_preexisting_matching_metadata_is_reused(self):
        result = verify_preexisting_resource_reuse(REPO_ROOT)

        self.assertTrue(result["accepted"], result)
        self.assertTrue(result["preexisting_reused"], result)
        self.assertEqual(result["resource_count"], 1)
        self.assertEqual(result["create_call_count"], 0)
        self.assertEqual(result["result"]["code"], "dashboard_resource_already_registered")

    def test_stale_unversioned_resource_is_updated_not_duplicated(self):
        result = verify_stale_resource_update(REPO_ROOT)

        self.assertTrue(result["accepted"], result)
        self.assertTrue(result["resource_updated"], result)
        self.assertFalse(result["resource_created"], result)
        self.assertEqual(result["create_call_count"], 0)
        self.assertEqual(result["update_call_count"], 1)
        self.assertEqual(result["resource_count"], 1)
        self.assertEqual(
            result["resources"][0]["url"],
            f"/api/isolinear/static/isolinear-card.js?v={INTEGRATION_VERSION}",
        )
        self.assertEqual(result["resources"][0]["type"], "module")

    def test_missing_bundle_fails_closed_before_metadata_write(self):
        result = verify_missing_bundle_rejection(REPO_ROOT)

        self.assertFalse(result["accepted"], result)
        self.assertEqual(result["code"], "dashboard_card_bundle_missing")
        self.assertEqual(result["resources"], [])
        self.assertEqual(result["create_call_count"], 0)
        self.assertEqual(result["static_path_call_count"], 0)

    def test_unavailable_resource_collection_fails_closed(self):
        result = verify_unavailable_resource_collection_rejection(REPO_ROOT)

        self.assertFalse(result["accepted"], result)
        self.assertEqual(result["code"], "lovelace_resource_collection_unavailable")
        self.assertEqual(result["create_call_count"], 0)
        self.assertEqual(result["resource_count"], 0)

    def test_dashboard_resource_anchor_verification_passes_without_orchestration(self):
        result = verify_dashboard_resource_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])
        aggregate = result["side_effects"]["aggregate"]
        self.assertFalse(aggregate["worker_called"])
        self.assertFalse(aggregate["model_provider_called"])
        self.assertFalse(aggregate["home_assistant_history_called"])
        self.assertFalse(aggregate["semantic_memory_called"])
        self.assertFalse(aggregate["home_assistant_service_or_state_mutation_called"])
        self.assertFalse(aggregate["token_generated"])
        self.assertFalse(aggregate["job_orchestration_called"])
        self.assertFalse(aggregate["websocket_command_registered"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
