import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.job_orchestration_subscription_progress_anchor import (  # noqa: E402
    verify_accepted_subscription_records_progress_event,
    verify_cross_config_entry_subscription_rejected,
    verify_job_orchestration_subscription_progress_anchor,
    verify_subscription_progress_side_effect_boundaries,
    verify_subscription_progress_snapshots_validate,
    verify_unknown_subscription_job_rejected_before_storage,
    verify_valid_subscriptions_stay_config_entry_scoped,
)


class JobOrchestrationSubscriptionProgressAnchorTests(unittest.TestCase):
    def test_accepted_subscribe_records_latest_progress_event(self):
        result = verify_accepted_subscription_records_progress_event(REPO_ROOT)

        self.assertTrue(result["start"]["accepted"], result)
        self.assertTrue(result["subscribe"]["accepted"], result)
        self.assertTrue(result["latest_snapshot_returned"], result)
        self.assertEqual(
            result["subscribe_snapshot"]["snapshot_id"],
            "subscription-entry-job-001-snapshot-003",
        )
        self.assertEqual(
            result["subscription"]["subscription_id"],
            "subscription-entry-job-001-subscription-001",
        )
        self.assertEqual(result["subscription"]["job_id"], "subscription-entry-job-001")
        self.assertEqual(result["progress_event"]["event_id"], "subscription-entry-progress-event-001")
        self.assertEqual(result["progress_event"]["type"], "isolinear_job_progress")
        self.assertEqual(result["progress_event"]["job_id"], "subscription-entry-job-001")
        self.assertEqual(
            result["progress_event"]["snapshot_id"],
            "subscription-entry-job-001-snapshot-003",
        )
        self.assertTrue(result["snapshot_validation"]["accepted"], result)
        self.assertTrue(all(item["accepted"] for item in result["progress_event_snapshot_validation"]), result)
        self.assertTrue(result["subscribe"]["orchestration"]["subscription_progress_streaming_called"])
        self.assertTrue(result["subscribe"]["orchestration"]["subscription_bookkeeping_written"])

    def test_unknown_job_fails_before_subscription_storage(self):
        result = verify_unknown_subscription_job_rejected_before_storage(REPO_ROOT)

        self.assertFalse(result["subscribe"]["accepted"], result)
        self.assertEqual(result["error_codes"], ["unknown_job"])
        self.assertEqual(result["job_store"]["job_ids"], [])
        self.assertEqual(result["subscriptions"], [])
        self.assertEqual(result["progress_events"], [])
        self.assertFalse(result["subscribe"]["orchestration"]["subscription_progress_streaming_called"])

    def test_cross_config_entry_subscribe_is_rejected_before_storage(self):
        result = verify_cross_config_entry_subscription_rejected(REPO_ROOT)

        self.assertFalse(result["cross_subscribe"]["accepted"], result)
        self.assertEqual(result["error_codes"], ["unknown_job"])
        self.assertEqual(result["entry_b_subscriptions"], [])
        self.assertEqual(result["entry_b_progress_events"], [])
        self.assertEqual(result["entry_a_subscriptions"], [])
        self.assertEqual(result["entry_a_progress_events"], [])
        self.assertFalse(result["cross_subscribe"]["orchestration"]["subscription_progress_streaming_called"])

    def test_valid_subscriptions_stay_config_entry_scoped(self):
        result = verify_valid_subscriptions_stay_config_entry_scoped(REPO_ROOT)

        self.assertTrue(result["entry_a"]["subscribe"]["accepted"], result)
        self.assertTrue(result["entry_b"]["subscribe"]["accepted"], result)
        self.assertEqual(result["entry_a"]["snapshot"]["job_id"], "valid-subscription-entry-a-job-001")
        self.assertEqual(result["entry_b"]["snapshot"]["job_id"], "valid-subscription-entry-b-job-001")
        self.assertEqual(
            result["entry_a"]["progress_events"][0]["job_id"],
            "valid-subscription-entry-a-job-001",
        )
        self.assertEqual(
            result["entry_b"]["progress_events"][0]["job_id"],
            "valid-subscription-entry-b-job-001",
        )
        self.assertEqual(len(result["entry_a"]["subscriptions"]), 1)
        self.assertEqual(len(result["entry_b"]["subscriptions"]), 1)

    def test_subscription_progress_snapshots_validate_before_storage(self):
        result = verify_subscription_progress_snapshots_validate(REPO_ROOT)

        self.assertTrue(result["accepted"]["returned_snapshot_valid"], result)
        self.assertTrue(result["accepted"]["event_snapshots_valid"], result)
        self.assertTrue(result["isolation_entry_a"]["returned_snapshot_valid"], result)
        self.assertTrue(result["isolation_entry_a"]["event_snapshots_valid"], result)
        self.assertTrue(result["isolation_entry_b"]["returned_snapshot_valid"], result)
        self.assertTrue(result["isolation_entry_b"]["event_snapshots_valid"], result)

    def test_subscription_progress_side_effect_boundaries(self):
        result = verify_subscription_progress_side_effect_boundaries()

        self.assertFalse(result["forbidden_aggregate"]["worker_called"])
        self.assertFalse(result["forbidden_aggregate"]["model_provider_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_history_called"])
        self.assertFalse(result["forbidden_aggregate"]["semantic_memory_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_service_or_state_mutation_called"])
        self.assertFalse(result["forbidden_aggregate"]["token_generated"])
        self.assertFalse(result["forbidden_aggregate"]["chart_artifact_written"])
        self.assertFalse(result["forbidden_aggregate"]["chart_rendering_called"])
        self.assertFalse(result["forbidden_aggregate"]["durable_storage_written"])
        self.assertFalse(result["forbidden_aggregate"]["retry_behavior_called"])
        self.assertFalse(result["forbidden_aggregate"]["job_orchestration_called"])
        self.assertTrue(result["allowed_aggregate"]["subscription_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["subscription_progress_streaming_called"])
        self.assertTrue(result["allowed_aggregate"]["job_orchestration_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["websocket_command_registered"])

    def test_subscription_progress_anchor_verification_passes(self):
        result = verify_job_orchestration_subscription_progress_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
