import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.worker_failure_snapshot_manual_retry_anchor import (  # noqa: E402
    WORKER_TEST_TOKEN,
    verify_card_payload_excludes_worker_internals,
    verify_cross_config_entry_worker_failure_snapshot_and_retry_rejected,
    verify_manual_retry_resumes_worker_failure_snapshot,
    verify_non_retry_safe_transport_failure_rejects_manual_retry,
    verify_unknown_worker_failure_snapshot_job_rejected_before_call,
    verify_valid_worker_failure_snapshots_stay_config_entry_scoped,
    verify_worker_failure_snapshot_contracts_validate,
    verify_worker_failure_snapshot_manual_retry_anchor,
    verify_worker_failure_snapshot_manual_retry_side_effect_boundaries,
    verify_worker_render_failure_returns_failed_snapshot,
    verify_worker_transport_failure_returns_failed_snapshot,
)


class WorkerFailureSnapshotManualRetryAnchorTests(unittest.TestCase):
    def test_worker_render_failure_returns_card_facing_failed_snapshot(self):
        result = verify_worker_render_failure_returns_failed_snapshot(REPO_ROOT)

        self.assertTrue(result["snapshot"]["accepted"], result)
        self.assertEqual(result["worker_call_count"], 1)
        self.assertEqual(result["error_codes"], ["worker_safe_renderer_failed"])
        self.assertEqual(result["card_snapshot"]["status"], "failed")
        self.assertEqual(result["card_snapshot"]["failure"]["stage"], "worker_render")
        self.assertEqual(result["card_snapshot"]["failure"]["code"], "worker_safe_renderer_failed")
        self.assertTrue(result["card_snapshot"]["retry_allowed"])
        self.assertEqual(len(result["failed_snapshots"]), 1)
        self.assertEqual(len(result["worker_retry_policies"]), 1)
        self.assertEqual(result["worker_dispatches"], [])
        self.assertEqual(result["worker_progress_events"], [])
        self.assertEqual(result["transport_classifications"], [])
        self.assertEqual(result["render_plans"], [])
        self.assertEqual(result["artifacts"], [])
        self.assertEqual(result["complete_snapshots"], [])
        self.assertTrue(result["snapshot"]["orchestration"]["worker_retry_policy_bookkeeping_written"])
        self.assertTrue(result["snapshot"]["orchestration"]["job_state_scaffold_written"])
        self.assertFalse(result["snapshot"]["orchestration"]["worker_dispatch_bookkeeping_written"])

    def test_worker_transport_failure_returns_card_facing_failed_snapshot(self):
        result = verify_worker_transport_failure_returns_failed_snapshot(REPO_ROOT)

        self.assertTrue(result["snapshot"]["accepted"], result)
        self.assertEqual(result["worker_call_count"], 1)
        self.assertEqual(result["error_codes"], ["worker_connection_error"])
        self.assertEqual(result["card_snapshot"]["status"], "failed")
        self.assertEqual(result["card_snapshot"]["failure"]["stage"], "worker_transport")
        self.assertEqual(result["card_snapshot"]["failure"]["code"], "worker_connection_error")
        self.assertTrue(result["card_snapshot"]["retry_allowed"])
        self.assertEqual(len(result["failed_snapshots"]), 1)
        self.assertEqual(len(result["classifications"]), 1)
        self.assertEqual(result["worker_retry_policies"], [])
        self.assertEqual(result["worker_dispatches"], [])
        self.assertEqual(result["worker_progress_events"], [])
        self.assertEqual(result["render_plans"], [])
        self.assertEqual(result["artifacts"], [])
        self.assertEqual(result["complete_snapshots"], [])
        self.assertTrue(
            result["snapshot"]["orchestration"]["worker_transport_failure_classification_bookkeeping_written"]
        )
        self.assertTrue(result["snapshot"]["orchestration"]["job_state_scaffold_written"])
        self.assertFalse(result["snapshot"]["orchestration"]["worker_dispatch_bookkeeping_written"])

    def test_manual_retry_resumes_retryable_worker_failure_snapshot(self):
        result = verify_manual_retry_resumes_worker_failure_snapshot(REPO_ROOT)

        self.assertTrue(result["failure_snapshot_dispatch"]["accepted"], result)
        self.assertTrue(result["retry"]["accepted"], result)
        self.assertTrue(result["same_job_id"], result)
        self.assertEqual(result["failed_snapshot"]["retry_allowed"], True)
        self.assertEqual(result["retry_snapshot"]["progress_stage"], "job_orchestration_retry_continuation_ready")
        self.assertEqual(result["history_request_count_delta"], 1)
        self.assertIn("worker_failure_snapshot_ready", result["job_progress_stages"])
        self.assertIn("job_orchestration_retry_accepted", result["job_progress_stages"])
        self.assertTrue(result["retry"]["orchestration"]["retry_behavior_called"])
        self.assertTrue(result["retry"]["orchestration"]["home_assistant_history_read"])
        self.assertTrue(all(item["accepted"] for item in result["snapshot_validation"]), result)

    def test_non_retry_safe_transport_failure_rejects_manual_retry(self):
        result = verify_non_retry_safe_transport_failure_rejects_manual_retry(REPO_ROOT)

        self.assertTrue(result["failure_snapshot_dispatch"]["accepted"], result)
        self.assertEqual(result["failed_snapshot"]["failure"]["stage"], "worker_transport")
        self.assertFalse(result["failed_snapshot"]["retry_allowed"])
        self.assertFalse(result["retry"]["accepted"], result)
        self.assertEqual(result["retry_error_codes"], ["job_not_retryable"])
        self.assertEqual(result["snapshot_count_after_retry"], result["snapshot_count_before_retry"])
        self.assertEqual(result["history_request_count_delta"], 0)

    def test_worker_failure_snapshot_contracts_validate(self):
        result = verify_worker_failure_snapshot_contracts_validate(REPO_ROOT)

        self.assertTrue(result["render_failure"]["failed_snapshot_valid"], result)
        self.assertTrue(result["render_failure"]["worker_retry_policy_valid"], result)
        self.assertTrue(result["transport_failure"]["failed_snapshot_valid"], result)
        self.assertTrue(result["transport_failure"]["transport_classification_valid"], result)

    def test_card_payload_excludes_worker_internals(self):
        result = verify_card_payload_excludes_worker_internals(REPO_ROOT)

        self.assertTrue(result["card_payloads_exclude_worker_internals"], result)
        self.assertEqual(result["render_forbidden_hits"], [])
        self.assertEqual(result["transport_forbidden_hits"], [])
        self.assertTrue(result["worker_authorization_redacted_in_internal_metadata"], result)
        self.assertTrue(result["worker_token_absent_from_card_payloads"], result)
        self.assertNotIn(WORKER_TEST_TOKEN, str(result["render_card_payload"]))
        self.assertNotIn(WORKER_TEST_TOKEN, str(result["transport_card_payload"]))

    def test_unknown_job_rejected_before_worker_failure_snapshot(self):
        result = verify_unknown_worker_failure_snapshot_job_rejected_before_call(REPO_ROOT)

        self.assertFalse(result["snapshot"]["accepted"], result)
        self.assertEqual(result["worker_call_count"], 0)
        self.assertEqual(result["error_codes"], ["unknown_job"])
        self.assertEqual(result["worker_retry_policies"], [])
        self.assertEqual(result["transport_classifications"], [])
        self.assertEqual(result["worker_dispatches"], [])

    def test_cross_config_entry_rejected_before_worker_failure_snapshot_and_retry(self):
        result = verify_cross_config_entry_worker_failure_snapshot_and_retry_rejected(REPO_ROOT)

        self.assertFalse(result["cross_snapshot"]["accepted"], result)
        self.assertFalse(result["cross_retry"]["accepted"], result)
        self.assertEqual(result["entry_a_worker_call_count"], 0)
        self.assertEqual(result["entry_b_worker_call_count"], 0)
        self.assertEqual(result["error_codes"], ["unknown_job", "unknown_job"])
        self.assertEqual(result["entry_b_failed_snapshots"], [])
        self.assertEqual(result["entry_b_worker_retry_policies"], [])
        self.assertEqual(result["entry_b_transport_classifications"], [])
        self.assertEqual(result["entry_b_worker_dispatches"], [])

    def test_valid_worker_failure_snapshots_stay_config_entry_scoped(self):
        result = verify_valid_worker_failure_snapshots_stay_config_entry_scoped(REPO_ROOT)

        self.assertTrue(result["entry_a"]["snapshot"]["accepted"], result)
        self.assertTrue(result["entry_b"]["snapshot"]["accepted"], result)
        self.assertEqual(result["entry_a"]["worker_call_count"], 1)
        self.assertEqual(result["entry_b"]["worker_call_count"], 1)
        self.assertEqual(result["entry_a"]["failed_snapshots"][0]["job_id"], "worker-failure-isolation-entry-a-job-001")
        self.assertEqual(result["entry_b"]["failed_snapshots"][0]["job_id"], "worker-failure-isolation-entry-b-job-001")
        self.assertEqual(result["entry_a"]["failed_snapshots"][0]["failure"]["stage"], "worker_render")
        self.assertEqual(result["entry_b"]["failed_snapshots"][0]["failure"]["stage"], "worker_transport")
        self.assertTrue(all(item["accepted"] for item in result["entry_a"]["failed_snapshot_validation"]), result)
        self.assertTrue(all(item["accepted"] for item in result["entry_b"]["failed_snapshot_validation"]), result)

    def test_worker_failure_snapshot_manual_retry_side_effect_boundaries(self):
        result = verify_worker_failure_snapshot_manual_retry_side_effect_boundaries()

        self.assertTrue(result["allowed_aggregate"]["worker_called"])
        self.assertTrue(result["allowed_aggregate"]["chart_rendering_called"])
        self.assertTrue(result["allowed_aggregate"]["job_state_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["job_orchestration_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["worker_retry_policy_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["worker_transport_failure_classification_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["retry_behavior_called_for_manual_retry"])
        self.assertTrue(result["allowed_aggregate"]["home_assistant_history_read_for_manual_retry"])
        self.assertTrue(result["allowed_aggregate"]["websocket_command_registered"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_history_read"])
        self.assertFalse(result["forbidden_aggregate"]["semantic_memory_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_service_or_state_mutation_called"])
        self.assertFalse(result["forbidden_aggregate"]["token_generated"])
        self.assertFalse(result["forbidden_aggregate"]["token_rotation_called"])
        self.assertFalse(result["forbidden_aggregate"]["token_leaked_to_card"])
        self.assertFalse(result["forbidden_aggregate"]["token_leaked_to_model_provider"])
        self.assertFalse(result["forbidden_aggregate"]["chart_artifact_written"])
        self.assertFalse(result["forbidden_aggregate"]["durable_retry_storage_written"])
        self.assertFalse(result["forbidden_aggregate"]["worker_health_check_called"])
        self.assertFalse(result["forbidden_aggregate"]["scheduler_called"])
        self.assertFalse(result["forbidden_aggregate"]["automatic_progress_task_called"])
        self.assertFalse(result["forbidden_aggregate"]["new_worker_transport_added"])
        self.assertFalse(result["forbidden_aggregate"]["worker_metadata_exposed_to_card"])

    def test_worker_failure_snapshot_manual_retry_anchor_verification_passes(self):
        result = verify_worker_failure_snapshot_manual_retry_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
