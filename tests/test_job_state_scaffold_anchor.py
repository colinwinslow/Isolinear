import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.job_state_scaffold_anchor import (  # noqa: E402
    verify_config_entry_job_isolation,
    verify_existing_job_command_updates,
    verify_job_state_scaffold_anchor,
    verify_job_state_side_effect_boundaries,
    verify_malformed_snapshot_rejected_before_storage,
    verify_start_job_creates_deterministic_state,
    verify_subscription_callback_shape,
    verify_unknown_jobs_fail_closed,
    verify_unload_removes_job_state,
)


class JobStateScaffoldAnchorTests(unittest.TestCase):
    def test_start_job_creates_deterministic_schema_valid_state(self):
        result = verify_start_job_creates_deterministic_state(REPO_ROOT)

        self.assertTrue(result["dispatch"]["accepted"], result)
        self.assertTrue(result["snapshot_validation"]["accepted"], result)
        self.assertEqual(result["snapshot"]["job_id"], "fake-config-entry-job-001")
        self.assertEqual(
            result["snapshot"]["snapshot_id"],
            "fake-config-entry-job-001-snapshot-001",
        )
        self.assertEqual(result["snapshot"]["status"], "planning")
        self.assertEqual(result["store"]["job_ids"], ["fake-config-entry-job-001"])
        self.assertEqual(result["store"]["latest_snapshot_ids"], ["fake-config-entry-job-001-snapshot-001"])

    def test_snapshot_retry_and_clarification_update_existing_job(self):
        result = verify_existing_job_command_updates(REPO_ROOT)

        self.assertTrue(result["start"]["accepted"], result)
        self.assertTrue(result["get_snapshot"]["accepted"], result)
        self.assertTrue(result["retry"]["accepted"], result)
        self.assertTrue(result["answer_clarification"]["accepted"], result)
        self.assertEqual(result["snapshot_ids"], [
            "fake-config-entry-job-001-snapshot-001",
            "fake-config-entry-job-001-snapshot-001",
            "fake-config-entry-job-001-snapshot-002",
            "fake-config-entry-job-001-snapshot-003",
        ])
        self.assertTrue(all(item["accepted"] for item in result["snapshot_validation"].values()), result)
        self.assertEqual(result["store"]["latest_snapshot_id"], "fake-config-entry-job-001-snapshot-003")

    def test_subscribe_records_callback_event_shape(self):
        result = verify_subscription_callback_shape(REPO_ROOT)

        self.assertTrue(result["subscribe"]["accepted"], result)
        self.assertTrue(result["snapshot_validation"]["accepted"], result)
        self.assertEqual(result["subscription"]["subscription_id"], "fake-config-entry-job-001-subscription-001")
        self.assertEqual(result["subscription"]["event"]["type"], "isolinear_job_snapshot")
        self.assertEqual(
            result["subscription"]["event"]["snapshot"]["snapshot_id"],
            "fake-config-entry-job-001-snapshot-001",
        )
        self.assertEqual(len(result["connection"]["results"]), 1)
        self.assertEqual(result["connection"]["errors"], [])

    def test_config_entries_cannot_read_each_others_jobs(self):
        result = verify_config_entry_job_isolation(REPO_ROOT)

        self.assertTrue(result["entry_a_start"]["accepted"], result)
        self.assertTrue(result["entry_b_start"]["accepted"], result)
        self.assertFalse(result["cross_entry_snapshot"]["accepted"], result)
        self.assertEqual(
            result["cross_entry_snapshot"]["connection"]["errors"][0]["code"],
            "unknown_job",
        )
        self.assertEqual(result["entry_a_store"]["job_ids"], ["entry-a-job-001"])
        self.assertEqual(result["entry_b_store"]["job_ids"], ["entry-b-job-001"])

    def test_unknown_jobs_fail_closed_for_job_commands(self):
        result = verify_unknown_jobs_fail_closed()

        self.assertEqual(
            {name: item["connection"]["errors"][0]["code"] for name, item in result["dispatch_results"].items()},
            {
                "get_snapshot": "unknown_job",
                "retry_job": "unknown_job",
                "answer_clarification": "unknown_job",
                "subscribe_job": "unknown_job",
            },
        )
        self.assertTrue(all(not item["accepted"] for item in result["dispatch_results"].values()))
        self.assertTrue(all(not item["connection"]["results"] for item in result["dispatch_results"].values()))
        self.assertEqual(result["store"]["job_ids"], [])

    def test_malformed_snapshots_are_rejected_before_storage(self):
        result = verify_malformed_snapshot_rejected_before_storage()

        self.assertFalse(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "invalid_integration_job_snapshot")
        self.assertIn("$.prompt is required.", result["result"]["error"])
        self.assertEqual(result["snapshots_after_attempt"], [])
        self.assertIsNone(result["latest_snapshot_after_attempt"])

    def test_unload_removes_config_entry_job_state(self):
        result = verify_unload_removes_job_state()

        self.assertTrue(result["setup_accepted"], result)
        self.assertTrue(result["unload_accepted"], result)
        self.assertTrue(result["had_job_state_before_unload"], result)
        self.assertFalse(result["entry_present_after_unload"], result)

    def test_job_state_scaffold_side_effect_boundaries(self):
        result = verify_job_state_side_effect_boundaries()

        self.assertFalse(result["forbidden_aggregate"]["worker_called"])
        self.assertFalse(result["forbidden_aggregate"]["model_provider_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_history_called"])
        self.assertFalse(result["forbidden_aggregate"]["semantic_memory_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_service_or_state_mutation_called"])
        self.assertFalse(result["forbidden_aggregate"]["token_generated"])
        self.assertFalse(result["forbidden_aggregate"]["chart_artifact_written"])
        self.assertFalse(result["forbidden_aggregate"]["job_orchestration_called"])
        self.assertTrue(result["allowed_aggregate"]["job_state_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["subscription_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["websocket_command_registered"])

    def test_job_state_scaffold_anchor_verification_passes(self):
        result = verify_job_state_scaffold_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
