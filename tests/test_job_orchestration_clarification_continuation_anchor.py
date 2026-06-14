import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.job_orchestration_clarification_continuation_anchor import (  # noqa: E402
    verify_accepted_clarification_resumes_same_job,
    verify_clarification_continuation_side_effect_boundaries,
    verify_colliding_option_fails_before_history,
    verify_continuation_snapshots_validate,
    verify_cross_config_entry_answer_rejected,
    verify_job_orchestration_clarification_continuation_anchor,
    verify_unknown_option_fails_before_history,
    verify_valid_continuations_stay_config_entry_scoped,
    verify_wrong_question_fails_before_history,
)


class JobOrchestrationClarificationContinuationAnchorTests(unittest.TestCase):
    def test_accepted_clarification_resumes_same_job_through_history(self):
        result = verify_accepted_clarification_resumes_same_job(REPO_ROOT)

        self.assertTrue(result["start"]["accepted"], result)
        self.assertTrue(result["answer"]["accepted"], result)
        self.assertTrue(result["same_job_id"], result)
        self.assertEqual(result["answer_snapshot"]["snapshot_id"], "clarification-entry-job-001-snapshot-005")
        self.assertEqual(
            result["job_progress_stages"],
            [
                "job_state_scaffold",
                "entity_selection_clarification",
                "clarification_answer_accepted",
                "approved_history_retrieval",
                "job_orchestration_clarification_continuation_ready",
            ],
        )
        self.assertEqual(result["history_store"]["entity_ids"], ["sensor.upstairs_temperature"])
        self.assertEqual(result["run"]["result_code"], "clarification_approved_history_ready")
        self.assertEqual(result["run"]["requested_entity_ids"], ["sensor.upstairs_temperature"])
        self.assertTrue(all(item["accepted"] for item in result["snapshot_validation"]), result)

    def test_unknown_option_fails_before_history_without_snapshot_append(self):
        result = verify_unknown_option_fails_before_history(REPO_ROOT)

        self.assertFalse(result["answer"]["accepted"], result)
        self.assertEqual(result["error_codes"], ["unknown_clarification_option"])
        self.assertEqual(result["snapshot_count_after"], result["snapshot_count_before"])
        self.assertEqual(result["history_store"]["series_count"], 0)
        self.assertFalse(result["answer"]["orchestration"]["home_assistant_history_read"])
        self.assertTrue(result["start_snapshot_validation"]["accepted"], result)

    def test_wrong_question_fails_before_history_without_snapshot_append(self):
        result = verify_wrong_question_fails_before_history(REPO_ROOT)

        self.assertFalse(result["answer"]["accepted"], result)
        self.assertEqual(result["error_codes"], ["clarification_question_mismatch"])
        self.assertEqual(result["snapshot_count_after"], result["snapshot_count_before"])
        self.assertEqual(result["history_store"]["series_count"], 0)
        self.assertFalse(result["answer"]["orchestration"]["home_assistant_history_read"])
        self.assertTrue(result["start_snapshot_validation"]["accepted"], result)

    def test_colliding_option_ids_fail_before_history_without_snapshot_append(self):
        result = verify_colliding_option_fails_before_history(REPO_ROOT)

        self.assertFalse(result["answer"]["accepted"], result)
        self.assertEqual(result["error_codes"], ["ambiguous_clarification_option"])
        self.assertEqual(
            [option["option_id"] for option in result["start_options"]],
            ["sensor_foo_bar", "sensor_foo_bar"],
        )
        self.assertEqual(result["snapshot_count_after"], result["snapshot_count_before"])
        self.assertEqual(result["history_store"]["series_count"], 0)
        self.assertFalse(result["answer"]["orchestration"]["home_assistant_history_read"])
        self.assertTrue(result["start_snapshot_validation"]["accepted"], result)

    def test_cross_config_entry_answer_is_rejected_before_history(self):
        result = verify_cross_config_entry_answer_rejected(REPO_ROOT)

        self.assertFalse(result["cross_answer"]["accepted"], result)
        self.assertEqual(result["error_codes"], ["unknown_job"])
        self.assertEqual(result["entry_a_history_store"]["series_count"], 0)
        self.assertEqual(result["entry_b_history_store"]["series_count"], 0)
        self.assertFalse(result["cross_answer"]["orchestration"]["home_assistant_history_read"])

    def test_valid_continuations_stay_config_entry_scoped(self):
        result = verify_valid_continuations_stay_config_entry_scoped(REPO_ROOT)

        self.assertTrue(result["entry_a"]["answer"]["accepted"], result)
        self.assertTrue(result["entry_b"]["answer"]["accepted"], result)
        self.assertEqual(result["entry_a"]["snapshot"]["job_id"], "continuation-entry-a-job-001")
        self.assertEqual(result["entry_b"]["snapshot"]["job_id"], "continuation-entry-b-job-001")
        self.assertEqual(result["entry_a"]["history_store"]["entity_ids"], ["sensor.upstairs_temperature"])
        self.assertEqual(result["entry_b"]["history_store"]["entity_ids"], ["binary_sensor.office_window"])
        self.assertEqual(result["entry_a"]["run"]["requested_entity_ids"], ["sensor.upstairs_temperature"])
        self.assertEqual(result["entry_b"]["run"]["requested_entity_ids"], ["binary_sensor.office_window"])

    def test_continuation_snapshots_validate_before_storage(self):
        result = verify_continuation_snapshots_validate(REPO_ROOT)

        self.assertTrue(result["success"]["all_snapshots_valid"], result)
        self.assertTrue(result["isolation_entry_a"]["all_snapshots_valid"], result)
        self.assertTrue(result["isolation_entry_b"]["all_snapshots_valid"], result)

    def test_clarification_continuation_side_effect_boundaries(self):
        result = verify_clarification_continuation_side_effect_boundaries()

        self.assertFalse(result["forbidden_aggregate"]["worker_called"])
        self.assertFalse(result["forbidden_aggregate"]["model_provider_called"])
        self.assertFalse(result["forbidden_aggregate"]["semantic_memory_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_service_or_state_mutation_called"])
        self.assertFalse(result["forbidden_aggregate"]["token_generated"])
        self.assertFalse(result["forbidden_aggregate"]["chart_artifact_written"])
        self.assertFalse(result["forbidden_aggregate"]["chart_rendering_called"])
        self.assertFalse(result["forbidden_aggregate"]["durable_storage_written"])
        self.assertFalse(result["forbidden_aggregate"]["retry_behavior_called"])
        self.assertFalse(result["forbidden_aggregate"]["subscription_progress_streaming_called"])
        self.assertFalse(result["forbidden_aggregate"]["job_orchestration_called"])
        self.assertTrue(result["allowed_aggregate"]["approved_entity_catalog_read"])
        self.assertTrue(result["allowed_aggregate"]["home_assistant_history_read"])
        self.assertTrue(result["allowed_aggregate"]["history_retrieval_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["job_state_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["job_orchestration_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["websocket_command_registered"])

    def test_clarification_continuation_anchor_verification_passes(self):
        result = verify_job_orchestration_clarification_continuation_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
