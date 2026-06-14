import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.history_retrieval_scaffold_anchor import (  # noqa: E402
    verify_approved_history_retrieval,
    verify_config_entry_history_isolation,
    verify_history_retrieval_scaffold_anchor,
    verify_history_retrieval_side_effect_boundaries,
    verify_malformed_history_series_rejected_before_storage,
    verify_malformed_raw_history_rejection,
    verify_non_catalog_entity_rejection,
    verify_rejected_retrieval_clears_existing_history,
    verify_setup_entry_history_storage,
)


class ApprovedHistoryRetrievalScaffoldAnchorTests(unittest.TestCase):
    def test_approved_catalog_entities_retrieve_schema_valid_history(self):
        result = verify_approved_history_retrieval(REPO_ROOT)

        self.assertTrue(result["result"]["accepted"], result)
        self.assertEqual(
            result["returned_entity_ids"],
            [
                "sensor.upstairs_temperature",
                "binary_sensor.office_window",
            ],
        )
        self.assertIn("light.kitchen", result["history_source_entity_ids"])
        self.assertTrue(all(item["accepted"] for item in result["series_validation"]), result)
        self.assertEqual(result["store"]["entity_ids"], result["returned_entity_ids"])
        self.assertEqual(result["store"]["kinds"], ["numeric", "binary_state"])

    def test_setup_entry_stores_config_entry_scoped_history_store(self):
        result = verify_setup_entry_history_storage(REPO_ROOT)

        self.assertTrue(result["setup_accepted"], result)
        self.assertTrue(result["setup_result"]["accepted"], result)
        self.assertEqual(result["entry_id"], "setup-history-entry")
        self.assertIn("history_retrieval", result["entry_data_keys"])
        self.assertIn("history_retrieval_setup", result["entry_data_keys"])
        self.assertEqual(result["store"]["entry_id"], "setup-history-entry")
        self.assertEqual(result["store"]["series_count"], 0)
        self.assertEqual(
            result["catalog_store"]["entity_ids"],
            [
                "sensor.upstairs_temperature",
                "binary_sensor.office_window",
            ],
        )

    def test_config_entries_receive_isolated_history_stores(self):
        result = verify_config_entry_history_isolation(REPO_ROOT)

        self.assertTrue(result["entry_a"]["accepted"], result)
        self.assertTrue(result["entry_b"]["accepted"], result)
        self.assertEqual(result["entry_a_store"]["entity_ids"], ["sensor.upstairs_temperature"])
        self.assertEqual(result["entry_b_store"]["entity_ids"], ["binary_sensor.office_window"])
        self.assertTrue(all(item["accepted"] for item in result["entry_a_validation"]), result)
        self.assertTrue(all(item["accepted"] for item in result["entry_b_validation"]), result)

    def test_non_catalog_entities_fail_closed_before_history_read(self):
        result = verify_non_catalog_entity_rejection()

        self.assertFalse(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "entity_not_in_approved_catalog")
        self.assertEqual(result["result"]["rejected_entity_ids"], ["light.kitchen"])
        self.assertFalse(result["result"]["orchestration"]["home_assistant_history_read"])
        self.assertEqual(result["store"]["series_count"], 0)

    def test_rejected_retrieval_clears_existing_history(self):
        result = verify_rejected_retrieval_clears_existing_history()

        self.assertTrue(result["accepted"]["accepted"], result)
        self.assertEqual(result["store_after_success"]["entity_ids"], ["sensor.upstairs_temperature"])
        self.assertFalse(result["rejected"]["accepted"], result)
        self.assertEqual(result["rejected"]["code"], "entity_not_in_approved_catalog")
        self.assertEqual(result["store_after_rejection"]["series_count"], 0)
        self.assertEqual(result["store_after_rejection"]["entity_ids"], [])

    def test_malformed_raw_history_fails_closed_without_storage(self):
        result = verify_malformed_raw_history_rejection()

        self.assertFalse(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "invalid_history_records")
        self.assertEqual(
            result["result"]["errors"],
            [
                {
                    "path": "$.history_by_entity.sensor.upstairs_temperature[0].last_changed",
                    "reason": "must_be_datetime",
                }
            ],
        )
        self.assertEqual(result["store"]["series_count"], 0)

    def test_malformed_history_series_are_rejected_before_storage(self):
        result = verify_malformed_history_series_rejected_before_storage()

        self.assertFalse(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "invalid_history_series")
        self.assertIn("$.label is required.", result["result"]["error"])
        self.assertEqual(result["raw_series_after_attempt"], [])
        self.assertEqual(result["store_after_attempt"]["series_count"], 0)

    def test_history_retrieval_side_effect_boundaries(self):
        result = verify_history_retrieval_side_effect_boundaries()

        self.assertFalse(result["forbidden_aggregate"]["worker_called"])
        self.assertFalse(result["forbidden_aggregate"]["model_provider_called"])
        self.assertFalse(result["forbidden_aggregate"]["semantic_memory_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_service_or_state_mutation_called"])
        self.assertFalse(result["forbidden_aggregate"]["token_generated"])
        self.assertFalse(result["forbidden_aggregate"]["chart_artifact_written"])
        self.assertFalse(result["forbidden_aggregate"]["chart_rendering_called"])
        self.assertFalse(result["forbidden_aggregate"]["job_orchestration_called"])
        self.assertFalse(result["forbidden_aggregate"]["websocket_command_registered"])
        self.assertFalse(result["forbidden_aggregate"]["dashboard_resource_metadata_written_or_reused"])
        self.assertTrue(result["allowed_aggregate"]["approved_entity_catalog_read"])
        self.assertTrue(result["allowed_aggregate"]["home_assistant_history_read"])
        self.assertTrue(result["allowed_aggregate"]["history_retrieval_scaffold_written"])

    def test_history_retrieval_scaffold_anchor_verification_passes(self):
        result = verify_history_retrieval_scaffold_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
