import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.worker_progress_streaming_anchor import (  # noqa: E402
    WORKER_TEST_TOKEN,
    verify_cross_config_entry_worker_progress_rejected_before_call,
    verify_http_worker_non_list_progress_rejected_before_storage,
    verify_invalid_worker_progress_rejected_before_storage,
    verify_repeated_snapshot_requests_reuse_worker_progress,
    verify_subscribed_worker_progress_records_rendering_snapshots,
    verify_unknown_worker_progress_job_rejected_before_call,
    verify_valid_worker_progress_stays_config_entry_scoped,
    verify_worker_progress_authorization_redaction,
    verify_worker_progress_contracts_validate,
    verify_worker_progress_links_existing_subscriptions,
    verify_worker_progress_secret_text_rejected_before_storage,
    verify_worker_progress_side_effect_boundaries,
    verify_worker_progress_streaming_anchor,
)


class WorkerProgressStreamingAnchorTests(unittest.TestCase):
    def test_subscribed_worker_progress_records_rendering_snapshots(self):
        result = verify_subscribed_worker_progress_records_rendering_snapshots(REPO_ROOT)

        self.assertTrue(result["start"]["accepted"], result)
        self.assertTrue(result["subscribe"]["accepted"], result)
        self.assertTrue(result["snapshot_dispatch"]["accepted"], result)
        self.assertEqual(result["worker_call_count"], 1)
        self.assertEqual(len(result["rendering_snapshots"]), 2)
        self.assertEqual(
            [item["progress"]["stage"] for item in result["rendering_snapshots"]],
            ["worker_render_started", "worker_render_finished"],
        )
        self.assertEqual(result["complete_snapshot"]["status"], "complete")
        self.assertEqual(result["complete_snapshot"]["snapshot_id"], "worker-progress-entry-job-001-snapshot-006")
        self.assertEqual(len(result["worker_progress_events"]), 2)
        self.assertEqual(result["worker_progress_event"]["event_id"], "worker-progress-entry-worker-progress-001")
        self.assertEqual(result["worker_progress_event"]["type"], "isolinear_worker_progress")
        self.assertEqual(result["worker_progress_event"]["snapshot_id"], "worker-progress-entry-job-001-snapshot-004")
        self.assertTrue(all(item["accepted"] for item in result["worker_progress_validation"]), result)
        self.assertTrue(all(item["accepted"] for item in result["worker_progress_snapshot_validation"]), result)
        self.assertTrue(result["snapshot_dispatch"]["orchestration"]["worker_progress_streaming_called"])
        self.assertTrue(result["snapshot_dispatch"]["orchestration"]["worker_progress_bookkeeping_written"])

    def test_worker_progress_links_existing_subscriptions(self):
        result = verify_worker_progress_links_existing_subscriptions(REPO_ROOT)

        self.assertEqual(result["subscription_ids"], ["worker-progress-entry-job-001-subscription-001"])
        self.assertTrue(result["all_progress_events_link_subscription"], result)
        self.assertEqual(
            result["worker_progress_subscription_ids"],
            [
                ["worker-progress-entry-job-001-subscription-001"],
                ["worker-progress-entry-job-001-subscription-001"],
            ],
        )

    def test_worker_progress_contracts_validate(self):
        result = verify_worker_progress_contracts_validate(REPO_ROOT)

        self.assertTrue(result["accepted"]["worker_progress_valid"], result)
        self.assertTrue(result["accepted"]["worker_progress_snapshot_valid"], result)
        self.assertTrue(result["accepted"]["worker_dispatch_valid"], result)
        self.assertTrue(result["accepted"]["worker_transport_valid"], result)
        self.assertTrue(result["accepted"]["render_request_valid"], result)
        self.assertTrue(result["accepted"]["render_result_valid"], result)
        self.assertTrue(result["accepted"]["render_plan_valid"], result)
        self.assertTrue(result["accepted"]["chart_spec_valid"], result)
        self.assertTrue(result["accepted"]["history_series_valid"], result)
        self.assertTrue(result["idempotent"]["worker_progress_valid"], result)
        self.assertTrue(result["isolation_entry_a"]["worker_progress_valid"], result)
        self.assertTrue(result["isolation_entry_b"]["worker_progress_valid"], result)

    def test_worker_progress_authorization_is_redacted(self):
        result = verify_worker_progress_authorization_redaction(REPO_ROOT)

        self.assertTrue(result["raw_worker_authorization_received"], result)
        self.assertEqual(result["stored_authorizations"], ["Bearer <redacted>", "Bearer <redacted>"])
        self.assertTrue(result["stored_authorization_redacted"], result)
        self.assertTrue(result["worker_token_absent_from_evidence"], result)
        self.assertEqual(result["secret_text"]["error_codes"], ["invalid_integration_worker_progress"])
        self.assertTrue(result["secret_text"]["token_absent_from_result"], result)
        self.assertNotIn(WORKER_TEST_TOKEN, str(result))

    def test_worker_progress_secret_text_rejected_before_storage(self):
        result = verify_worker_progress_secret_text_rejected_before_storage(REPO_ROOT)

        self.assertFalse(result["snapshot"]["accepted"], result)
        self.assertEqual(result["worker_call_count"], 1)
        self.assertEqual(result["error_codes"], ["invalid_integration_worker_progress"])
        self.assertEqual(result["worker_progress_events"], [])
        self.assertEqual(result["worker_dispatches"], [])
        self.assertEqual(result["render_plans"], [])
        self.assertEqual(result["artifacts"], [])
        self.assertEqual(result["complete_snapshots"], [])
        self.assertTrue(result["token_absent_from_result"], result)

    def test_repeated_snapshot_requests_reuse_worker_progress(self):
        result = verify_repeated_snapshot_requests_reuse_worker_progress(REPO_ROOT)

        self.assertTrue(result["first"]["accepted"], result)
        self.assertTrue(result["second"]["accepted"], result)
        self.assertEqual(result["worker_call_count"], 1)
        self.assertTrue(result["same_snapshot_returned"], result)
        self.assertEqual(result["worker_progress_count"], 2)
        self.assertEqual(result["worker_dispatch_count"], 1)
        self.assertEqual(result["render_plan_count"], 1)
        self.assertEqual(result["artifact_count"], 1)
        self.assertEqual(result["complete_snapshot_count"], 1)

    def test_invalid_worker_progress_rejected_before_storage(self):
        result = verify_invalid_worker_progress_rejected_before_storage(REPO_ROOT)

        self.assertFalse(result["snapshot"]["accepted"], result)
        self.assertEqual(result["worker_call_count"], 1)
        self.assertEqual(result["error_codes"], ["invalid_integration_worker_progress"])
        self.assertEqual(result["worker_progress_events"], [])
        self.assertEqual(result["worker_dispatches"], [])
        self.assertEqual(result["render_plans"], [])
        self.assertEqual(result["artifacts"], [])
        self.assertEqual(result["complete_snapshots"], [])
        self.assertTrue(result["snapshot"]["orchestration"]["worker_called"])
        self.assertFalse(result["snapshot"]["orchestration"]["worker_progress_bookkeeping_written"])

    def test_http_worker_non_list_progress_rejected_before_storage(self):
        result = verify_http_worker_non_list_progress_rejected_before_storage(REPO_ROOT)

        self.assertFalse(result["snapshot"]["accepted"], result)
        self.assertEqual(result["worker_http_call_count"], 1)
        self.assertEqual(result["forwarded_progress_type"], "dict")
        self.assertEqual(result["error_codes"], ["invalid_integration_worker_progress"])
        self.assertEqual(result["worker_progress_events"], [])
        self.assertEqual(result["worker_dispatches"], [])
        self.assertEqual(result["render_plans"], [])
        self.assertEqual(result["artifacts"], [])
        self.assertEqual(result["complete_snapshots"], [])
        self.assertTrue(result["token_absent_from_result"], result)
        self.assertTrue(result["snapshot"]["orchestration"]["worker_called"])
        self.assertFalse(result["snapshot"]["orchestration"]["worker_progress_bookkeeping_written"])

    def test_unknown_job_rejected_before_worker_progress(self):
        result = verify_unknown_worker_progress_job_rejected_before_call(REPO_ROOT)

        self.assertFalse(result["snapshot"]["accepted"], result)
        self.assertEqual(result["worker_call_count"], 0)
        self.assertEqual(result["error_codes"], ["unknown_job"])
        self.assertEqual(result["worker_progress_events"], [])
        self.assertEqual(result["worker_dispatches"], [])

    def test_cross_config_entry_rejected_before_worker_progress(self):
        result = verify_cross_config_entry_worker_progress_rejected_before_call(REPO_ROOT)

        self.assertFalse(result["cross_snapshot"]["accepted"], result)
        self.assertEqual(result["entry_a_worker_call_count"], 0)
        self.assertEqual(result["entry_b_worker_call_count"], 0)
        self.assertEqual(result["error_codes"], ["unknown_job"])
        self.assertEqual(result["entry_b_worker_progress_events"], [])
        self.assertEqual(result["entry_b_worker_dispatches"], [])
        self.assertEqual(result["entry_b_render_plans"], [])
        self.assertEqual(result["entry_b_artifacts"], [])
        self.assertEqual(result["entry_b_complete_snapshots"], [])

    def test_valid_worker_progress_stays_config_entry_scoped(self):
        result = verify_valid_worker_progress_stays_config_entry_scoped(REPO_ROOT)

        self.assertTrue(result["entry_a"]["snapshot"]["accepted"], result)
        self.assertTrue(result["entry_b"]["snapshot"]["accepted"], result)
        self.assertEqual(result["entry_a"]["worker_call_count"], 1)
        self.assertEqual(result["entry_b"]["worker_call_count"], 1)
        self.assertEqual(len(result["entry_a"]["worker_progress_events"]), 2)
        self.assertEqual(len(result["entry_b"]["worker_progress_events"]), 2)
        self.assertTrue(
            all(
                event["job_id"] == "worker-progress-isolation-entry-a-job-001"
                for event in result["entry_a"]["worker_progress_events"]
            ),
            result,
        )
        self.assertTrue(
            all(
                event["job_id"] == "worker-progress-isolation-entry-b-job-001"
                for event in result["entry_b"]["worker_progress_events"]
            ),
            result,
        )

    def test_worker_progress_side_effect_boundaries(self):
        result = verify_worker_progress_side_effect_boundaries()

        self.assertTrue(result["allowed_aggregate"]["worker_called"])
        self.assertTrue(result["allowed_aggregate"]["chart_rendering_called"])
        self.assertTrue(result["allowed_aggregate"]["worker_progress_streaming_called"])
        self.assertTrue(result["allowed_aggregate"]["worker_progress_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["worker_dispatch_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["render_plan_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["artifact_metadata_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["subscription_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["subscription_progress_streaming_called"])
        self.assertTrue(result["allowed_aggregate"]["job_state_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["job_orchestration_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["websocket_command_registered"])
        self.assertFalse(result["forbidden_aggregate"]["model_provider_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_history_read"])
        self.assertFalse(result["forbidden_aggregate"]["semantic_memory_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_service_or_state_mutation_called"])
        self.assertFalse(result["forbidden_aggregate"]["token_generated"])
        self.assertFalse(result["forbidden_aggregate"]["chart_artifact_written"])
        self.assertFalse(result["forbidden_aggregate"]["durable_storage_written"])
        self.assertFalse(result["forbidden_aggregate"]["retry_behavior_called"])
        self.assertFalse(result["forbidden_aggregate"]["automatic_progress_task_called"])
        self.assertFalse(result["forbidden_aggregate"]["job_orchestration_called"])

    def test_worker_progress_streaming_anchor_verification_passes(self):
        result = verify_worker_progress_streaming_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
