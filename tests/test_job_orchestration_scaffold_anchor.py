import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.job_orchestration_scaffold_anchor import (  # noqa: E402
    verify_ambiguous_prompt_requires_clarification,
    verify_config_entry_orchestration_isolation,
    verify_job_orchestration_scaffold_anchor,
    verify_job_orchestration_side_effect_boundaries,
    verify_missing_approved_history_failure,
    verify_non_catalog_prompt_entity_failure,
    verify_orchestration_snapshots_validate,
    verify_setup_entry_orchestration_storage,
    verify_start_job_orchestration_success,
    verify_unresolved_allowlist_catalog_failure,
)


class JobOrchestrationScaffoldAnchorTests(unittest.TestCase):
    def test_start_job_composes_catalog_history_and_job_state(self):
        result = verify_start_job_orchestration_success(REPO_ROOT)

        self.assertTrue(result["dispatch"]["accepted"], result)
        self.assertEqual(result["snapshot"]["status"], "planning")
        self.assertEqual(result["snapshot"]["progress"]["stage"], "job_orchestration_scaffold_ready")
        self.assertEqual(result["snapshot"]["job_id"], "orchestration-entry-job-001")
        self.assertEqual(result["snapshot"]["snapshot_id"], "orchestration-entry-job-001-snapshot-003")
        self.assertEqual(
            result["job_store"]["latest_snapshot_ids"],
            ["orchestration-entry-job-001-snapshot-003"],
        )
        self.assertEqual(
            result["job_snapshot_statuses"],
            ["planning", "fetching_history", "planning"],
        )
        self.assertEqual(
            result["history_store"]["entity_ids"],
            ["sensor.upstairs_temperature", "binary_sensor.office_window"],
        )
        self.assertTrue(all(item["accepted"] for item in result["snapshot_validation"]), result)

    def test_non_catalog_prompt_entities_fail_before_history_read(self):
        result = verify_non_catalog_prompt_entity_failure(REPO_ROOT)

        self.assertTrue(result["dispatch"]["accepted"], result)
        self.assertEqual(result["snapshot"]["status"], "failed")
        self.assertEqual(result["snapshot"]["failure"]["code"], "entity_not_in_approved_catalog")
        self.assertFalse(result["orchestration"]["home_assistant_history_read"])
        self.assertEqual(result["history_store"]["series_count"], 0)
        self.assertTrue(result["snapshot_validation"]["accepted"], result)

    def test_missing_approved_history_returns_failed_snapshot(self):
        result = verify_missing_approved_history_failure(REPO_ROOT)

        self.assertTrue(result["dispatch"]["accepted"], result)
        self.assertEqual(result["snapshot"]["status"], "failed")
        self.assertEqual(result["snapshot"]["failure"]["code"], "missing_approved_history")
        self.assertEqual(result["run"]["missing_entity_ids"], ["sensor.downstairs_temperature"])
        self.assertTrue(result["orchestration"]["home_assistant_history_read"])
        self.assertTrue(result["snapshot_validation"]["accepted"], result)

    def test_unresolved_allowlist_entity_surfaces_catalog_setup_failure(self):
        result = verify_unresolved_allowlist_catalog_failure(REPO_ROOT)

        self.assertTrue(result["dispatch"]["accepted"], result)
        self.assertEqual(result["catalog_setup"]["code"], "unknown_allowlisted_entity")
        self.assertEqual(
            result["catalog_setup"]["missing_entity_ids"],
            ["sensor.bathrrom_sensor_temperature"],
        )
        self.assertEqual(result["snapshot"]["status"], "failed")
        self.assertEqual(result["snapshot"]["failure"]["code"], "unknown_allowlisted_entity")
        self.assertIn("sensor.bathrrom_sensor_temperature", result["snapshot"]["failure"]["message"])
        self.assertEqual(result["run"]["missing_entity_ids"], ["sensor.bathrrom_sensor_temperature"])
        self.assertTrue(result["retry"]["dispatch"]["accepted"], result)
        self.assertEqual(result["retry"]["snapshot"]["status"], "failed")
        self.assertEqual(result["retry"]["snapshot"]["failure"]["code"], "unknown_allowlisted_entity")
        self.assertIn(
            "sensor.bathrrom_sensor_temperature",
            result["retry"]["snapshot"]["failure"]["message"],
        )
        self.assertEqual(
            result["retry"]["run"]["missing_entity_ids"],
            ["sensor.bathrrom_sensor_temperature"],
        )
        self.assertTrue(result["retry"]["snapshot_validation"]["accepted"], result)
        self.assertFalse(result["orchestration"]["home_assistant_history_read"])
        self.assertEqual(result["history_store"]["series_count"], 0)
        self.assertTrue(result["snapshot_validation"]["accepted"], result)

    def test_config_entries_keep_orchestration_scoped(self):
        result = verify_config_entry_orchestration_isolation(REPO_ROOT)

        self.assertTrue(result["entry_a"]["dispatch"]["accepted"], result)
        self.assertTrue(result["entry_b"]["dispatch"]["accepted"], result)
        self.assertEqual(result["entry_a"]["snapshot"]["job_id"], "orch-entry-a-job-001")
        self.assertEqual(result["entry_b"]["snapshot"]["job_id"], "orch-entry-b-job-001")
        self.assertEqual(result["entry_a"]["history_store"]["entity_ids"], ["sensor.upstairs_temperature"])
        self.assertEqual(result["entry_b"]["history_store"]["entity_ids"], ["binary_sensor.office_window"])
        self.assertEqual(result["entry_a"]["orchestration_store"]["latest_requested_entity_ids"], ["sensor.upstairs_temperature"])
        self.assertEqual(result["entry_b"]["orchestration_store"]["latest_requested_entity_ids"], ["binary_sensor.office_window"])

    def test_ambiguous_prompts_require_clarification_without_history_read(self):
        result = verify_ambiguous_prompt_requires_clarification(REPO_ROOT)

        self.assertTrue(result["dispatch"]["accepted"], result)
        self.assertEqual(result["snapshot"]["status"], "clarification_needed")
        self.assertEqual(result["snapshot"]["clarification"]["question_id"], "select_approved_entity")
        self.assertEqual(
            [option["option_id"] for option in result["snapshot"]["clarification"]["options"]],
            ["sensor_upstairs_temperature", "sensor_downstairs_temperature"],
        )
        self.assertFalse(result["orchestration"]["home_assistant_history_read"])
        self.assertEqual(result["history_store"]["series_count"], 0)
        self.assertTrue(result["snapshot_validation"]["accepted"], result)

    def test_setup_entry_stores_orchestration_state(self):
        result = verify_setup_entry_orchestration_storage()

        self.assertTrue(result["setup_accepted"], result)
        self.assertTrue(result["setup_result"]["accepted"], result)
        self.assertTrue(result["setup_result"]["enabled"], result)
        self.assertIn("job_orchestration", result["entry_data_keys"])
        self.assertIn("job_orchestration_setup", result["entry_data_keys"])
        self.assertEqual(result["store"]["entry_id"], "setup-orchestration-entry")

    def test_orchestration_snapshots_validate_before_storage(self):
        result = verify_orchestration_snapshots_validate(REPO_ROOT)

        self.assertTrue(result["success"]["all_snapshots_valid"], result)
        self.assertTrue(result["non_catalog"]["snapshot_validation"]["accepted"], result)
        self.assertTrue(result["missing_history"]["snapshot_validation"]["accepted"], result)

    def test_job_orchestration_scaffold_side_effect_boundaries(self):
        result = verify_job_orchestration_side_effect_boundaries()

        self.assertFalse(result["forbidden_aggregate"]["worker_called"])
        self.assertFalse(result["forbidden_aggregate"]["model_provider_called"])
        self.assertFalse(result["forbidden_aggregate"]["semantic_memory_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_service_or_state_mutation_called"])
        self.assertFalse(result["forbidden_aggregate"]["token_generated"])
        self.assertFalse(result["forbidden_aggregate"]["chart_artifact_written"])
        self.assertFalse(result["forbidden_aggregate"]["chart_rendering_called"])
        self.assertFalse(result["forbidden_aggregate"]["durable_storage_written"])
        self.assertFalse(result["forbidden_aggregate"]["job_orchestration_called"])
        self.assertTrue(result["allowed_aggregate"]["approved_entity_catalog_read"])
        self.assertTrue(result["allowed_aggregate"]["home_assistant_history_read"])
        self.assertTrue(result["allowed_aggregate"]["history_retrieval_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["job_state_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["job_orchestration_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["websocket_command_registered"])

    def test_job_orchestration_scaffold_anchor_verification_passes(self):
        result = verify_job_orchestration_scaffold_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
