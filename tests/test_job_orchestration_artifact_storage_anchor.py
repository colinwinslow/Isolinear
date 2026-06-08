import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.job_orchestration_artifact_storage_anchor import (  # noqa: E402
    verify_artifact_metadata_and_snapshots_validate,
    verify_artifact_storage_side_effect_boundaries,
    verify_cross_config_entry_artifact_rejected,
    verify_job_orchestration_artifact_storage_anchor,
    verify_repeated_snapshot_requests_reuse_artifact,
    verify_scaffold_ready_snapshot_records_placeholder_artifact,
    verify_unknown_artifact_job_rejected_before_storage,
    verify_valid_artifacts_stay_config_entry_scoped,
)


class JobOrchestrationArtifactStorageAnchorTests(unittest.TestCase):
    def test_scaffold_ready_snapshot_records_placeholder_artifact(self):
        result = verify_scaffold_ready_snapshot_records_placeholder_artifact(REPO_ROOT)

        self.assertTrue(result["start"]["accepted"], result)
        self.assertTrue(result["snapshot_dispatch"]["accepted"], result)
        self.assertEqual(result["artifact_snapshot"]["status"], "complete")
        self.assertEqual(
            result["artifact_snapshot"]["snapshot_id"],
            "artifact-entry-job-001-snapshot-004",
        )
        self.assertEqual(result["artifact"]["artifact_id"], "artifact-entry-artifact-001")
        self.assertEqual(result["artifact"]["job_id"], "artifact-entry-job-001")
        self.assertEqual(
            result["artifact"]["source_snapshot_id"],
            "artifact-entry-job-001-snapshot-003",
        )
        self.assertEqual(
            result["artifact_snapshot"]["chart"]["image_url"],
            result["artifact"]["image_url"],
        )
        self.assertTrue(result["snapshot_validation"]["accepted"], result)
        self.assertTrue(all(item["accepted"] for item in result["stored_snapshot_validation"]), result)
        self.assertTrue(all(item["accepted"] for item in result["artifact_validation"]), result)
        self.assertTrue(result["snapshot_dispatch"]["orchestration"]["artifact_metadata_bookkeeping_written"])
        self.assertTrue(result["snapshot_dispatch"]["orchestration"]["job_state_scaffold_written"])

    def test_repeated_snapshot_requests_reuse_artifact(self):
        result = verify_repeated_snapshot_requests_reuse_artifact(REPO_ROOT)

        self.assertTrue(result["first"]["accepted"], result)
        self.assertTrue(result["second"]["accepted"], result)
        self.assertTrue(result["same_snapshot_returned"], result)
        self.assertEqual(result["artifact_count"], 1)
        self.assertEqual(result["complete_snapshot_count"], 1)
        self.assertEqual(
            result["first_snapshot"]["snapshot_id"],
            "artifact-idempotent-entry-job-001-snapshot-004",
        )
        self.assertEqual(result["job_snapshot_ids"].count("artifact-idempotent-entry-job-001-snapshot-004"), 1)

    def test_unknown_job_fails_before_artifact_storage(self):
        result = verify_unknown_artifact_job_rejected_before_storage(REPO_ROOT)

        self.assertFalse(result["snapshot"]["accepted"], result)
        self.assertEqual(result["error_codes"], ["unknown_job"])
        self.assertEqual(result["job_store"]["job_ids"], [])
        self.assertEqual(result["artifacts"], [])
        self.assertFalse(result["snapshot"]["orchestration"]["artifact_metadata_bookkeeping_written"])

    def test_cross_config_entry_artifact_is_rejected_before_storage(self):
        result = verify_cross_config_entry_artifact_rejected(REPO_ROOT)

        self.assertFalse(result["cross_snapshot"]["accepted"], result)
        self.assertEqual(result["error_codes"], ["unknown_job"])
        self.assertEqual(result["entry_a_artifacts"], [])
        self.assertEqual(result["entry_b_artifacts"], [])
        self.assertEqual(result["entry_b_complete_snapshots"], [])
        self.assertFalse(result["cross_snapshot"]["orchestration"]["artifact_metadata_bookkeeping_written"])

    def test_valid_artifacts_stay_config_entry_scoped(self):
        result = verify_valid_artifacts_stay_config_entry_scoped(REPO_ROOT)

        self.assertTrue(result["entry_a"]["snapshot"]["accepted"], result)
        self.assertTrue(result["entry_b"]["snapshot"]["accepted"], result)
        self.assertEqual(result["entry_a"]["artifact_snapshot"]["job_id"], "valid-artifact-entry-a-job-001")
        self.assertEqual(result["entry_b"]["artifact_snapshot"]["job_id"], "valid-artifact-entry-b-job-001")
        self.assertEqual(result["entry_a"]["artifacts"][0]["artifact_id"], "valid-artifact-entry-a-artifact-001")
        self.assertEqual(result["entry_b"]["artifacts"][0]["artifact_id"], "valid-artifact-entry-b-artifact-001")
        self.assertEqual(result["entry_a"]["artifacts"][0]["series"][0]["entity_id"], "sensor.upstairs_temperature")
        self.assertEqual(result["entry_b"]["artifacts"][0]["series"][0]["entity_id"], "binary_sensor.office_window")

    def test_artifact_metadata_and_snapshots_validate_before_storage(self):
        result = verify_artifact_metadata_and_snapshots_validate(REPO_ROOT)

        self.assertTrue(result["accepted"]["returned_snapshot_valid"], result)
        self.assertTrue(result["accepted"]["stored_snapshots_valid"], result)
        self.assertTrue(result["accepted"]["artifact_metadata_valid"], result)
        self.assertTrue(result["idempotent"]["returned_snapshot_valid"], result)
        self.assertTrue(result["idempotent"]["artifact_metadata_valid"], result)
        self.assertTrue(result["isolation_entry_a"]["returned_snapshot_valid"], result)
        self.assertTrue(result["isolation_entry_a"]["artifact_metadata_valid"], result)
        self.assertTrue(result["isolation_entry_b"]["returned_snapshot_valid"], result)
        self.assertTrue(result["isolation_entry_b"]["artifact_metadata_valid"], result)

    def test_artifact_storage_side_effect_boundaries(self):
        result = verify_artifact_storage_side_effect_boundaries()

        self.assertFalse(result["forbidden_aggregate"]["worker_called"])
        self.assertFalse(result["forbidden_aggregate"]["model_provider_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_history_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_history_read"])
        self.assertFalse(result["forbidden_aggregate"]["history_retrieval_scaffold_written"])
        self.assertFalse(result["forbidden_aggregate"]["semantic_memory_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_service_or_state_mutation_called"])
        self.assertFalse(result["forbidden_aggregate"]["token_generated"])
        self.assertFalse(result["forbidden_aggregate"]["chart_artifact_written"])
        self.assertFalse(result["forbidden_aggregate"]["chart_rendering_called"])
        self.assertFalse(result["forbidden_aggregate"]["durable_storage_written"])
        self.assertFalse(result["forbidden_aggregate"]["retry_behavior_called"])
        self.assertFalse(result["forbidden_aggregate"]["subscription_bookkeeping_written"])
        self.assertFalse(result["forbidden_aggregate"]["subscription_progress_streaming_called"])
        self.assertFalse(result["forbidden_aggregate"]["job_orchestration_called"])
        self.assertTrue(result["allowed_aggregate"]["artifact_metadata_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["job_state_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["job_orchestration_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["websocket_command_registered"])

    def test_artifact_storage_anchor_verification_passes(self):
        result = verify_job_orchestration_artifact_storage_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
