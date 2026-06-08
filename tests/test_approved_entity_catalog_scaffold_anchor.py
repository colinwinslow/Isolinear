import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.entity_catalog_scaffold_anchor import (  # noqa: E402
    verify_allowlisted_metadata_catalog,
    verify_config_entry_catalog_isolation,
    verify_entity_catalog_scaffold_anchor,
    verify_entity_catalog_side_effect_boundaries,
    verify_malformed_allowlist_rejected_without_crash,
    verify_malformed_catalog_item_rejected_before_storage,
    verify_rejected_rebuild_clears_existing_catalog,
    verify_setup_entry_catalog_storage,
    verify_unknown_allowlisted_entity_rejection,
)


class ApprovedEntityCatalogScaffoldAnchorTests(unittest.TestCase):
    def test_allowlisted_metadata_builds_schema_valid_catalog_items(self):
        result = verify_allowlisted_metadata_catalog(REPO_ROOT)

        self.assertTrue(result["result"]["accepted"], result)
        self.assertEqual(
            result["catalog_entity_ids"],
            [
                "sensor.upstairs_temperature",
                "sensor.downstairs_temperature",
            ],
        )
        self.assertIn("light.kitchen", result["metadata_entity_ids"])
        self.assertTrue(all(item["accepted"] for item in result["item_validation"]), result)
        self.assertTrue(result["store"]["all_visible_to_agent"], result)

    def test_setup_entry_stores_config_entry_scoped_catalog(self):
        result = verify_setup_entry_catalog_storage(REPO_ROOT)

        self.assertTrue(result["setup_accepted"], result)
        self.assertTrue(result["setup_result"]["accepted"], result)
        self.assertEqual(result["entry_id"], "setup-catalog-entry")
        self.assertIn("entity_catalog", result["entry_data_keys"])
        self.assertIn("entity_catalog_setup", result["entry_data_keys"])
        self.assertEqual(
            result["store"]["entity_ids"],
            [
                "sensor.upstairs_temperature",
                "binary_sensor.office_window",
            ],
        )
        self.assertTrue(all(item["accepted"] for item in result["item_validation"]), result)

    def test_config_entries_receive_isolated_catalogs(self):
        result = verify_config_entry_catalog_isolation(REPO_ROOT)

        self.assertTrue(result["entry_a"]["accepted"], result)
        self.assertTrue(result["entry_b"]["accepted"], result)
        self.assertEqual(result["entry_a_store"]["entity_ids"], ["sensor.upstairs_temperature"])
        self.assertEqual(result["entry_b_store"]["entity_ids"], ["binary_sensor.office_window"])
        self.assertTrue(all(item["accepted"] for item in result["entry_a_validation"]), result)
        self.assertTrue(all(item["accepted"] for item in result["entry_b_validation"]), result)

    def test_unknown_allowlisted_entities_fail_closed_before_storage(self):
        result = verify_unknown_allowlisted_entity_rejection()

        self.assertFalse(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "unknown_allowlisted_entity")
        self.assertEqual(result["result"]["missing_entity_ids"], ["sensor.missing_temperature"])
        self.assertEqual(result["store"]["item_count"], 0)
        self.assertEqual(result["store"]["entity_ids"], [])

    def test_rejected_rebuild_clears_existing_catalog(self):
        result = verify_rejected_rebuild_clears_existing_catalog()

        self.assertTrue(result["accepted"]["accepted"], result)
        self.assertEqual(result["store_after_success"]["entity_ids"], ["sensor.upstairs_temperature"])
        self.assertFalse(result["rejected"]["accepted"], result)
        self.assertEqual(result["rejected"]["code"], "unknown_allowlisted_entity")
        self.assertEqual(result["store_after_rejection"]["item_count"], 0)
        self.assertEqual(result["store_after_rejection"]["entity_ids"], [])

    def test_malformed_allowlists_fail_closed_without_crashing(self):
        result = verify_malformed_allowlist_rejected_without_crash()

        self.assertFalse(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "invalid_entity_allowlist")
        self.assertEqual(
            result["result"]["errors"],
            [{"path": "$.options.entity_allowlist[0]", "reason": "invalid_entity_id"}],
        )
        self.assertEqual(result["store"]["item_count"], 0)

    def test_malformed_catalog_items_are_rejected_before_storage(self):
        result = verify_malformed_catalog_item_rejected_before_storage()

        self.assertFalse(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "invalid_entity_catalog_item")
        self.assertIn("$.domain is required.", result["result"]["error"])
        self.assertEqual(result["raw_items_after_attempt"], [])
        self.assertEqual(result["store_after_attempt"]["item_count"], 0)

    def test_entity_catalog_scaffold_side_effect_boundaries(self):
        result = verify_entity_catalog_side_effect_boundaries()

        self.assertFalse(result["forbidden_aggregate"]["worker_called"])
        self.assertFalse(result["forbidden_aggregate"]["model_provider_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_history_called"])
        self.assertFalse(result["forbidden_aggregate"]["semantic_memory_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_service_or_state_mutation_called"])
        self.assertFalse(result["forbidden_aggregate"]["token_generated"])
        self.assertFalse(result["forbidden_aggregate"]["chart_artifact_written"])
        self.assertFalse(result["forbidden_aggregate"]["job_orchestration_called"])
        self.assertFalse(result["forbidden_aggregate"]["websocket_command_registered"])
        self.assertFalse(result["forbidden_aggregate"]["dashboard_resource_metadata_written_or_reused"])
        self.assertTrue(result["allowed_aggregate"]["entity_catalog_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["home_assistant_entity_metadata_read"])

    def test_entity_catalog_scaffold_anchor_verification_passes(self):
        result = verify_entity_catalog_scaffold_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
