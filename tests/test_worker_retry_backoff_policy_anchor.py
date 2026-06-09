import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.worker_retry_backoff_policy_anchor import (  # noqa: E402
    WORKER_TEST_TOKEN,
    verify_cross_config_entry_worker_retry_policy_rejected_before_call,
    verify_unknown_worker_retry_policy_job_rejected_before_call,
    verify_valid_worker_retry_policies_stay_config_entry_scoped,
    verify_worker_failure_records_retry_policy,
    verify_worker_retry_backoff_policy_anchor,
    verify_worker_retry_policy_authorization_redaction,
    verify_worker_retry_policy_contracts_validate,
    verify_worker_retry_policy_secret_failure_code_redaction,
    verify_worker_retry_policy_side_effect_boundaries,
)


class WorkerRetryBackoffPolicyAnchorTests(unittest.TestCase):
    def test_worker_failure_records_retry_policy(self):
        result = verify_worker_failure_records_retry_policy(REPO_ROOT)

        self.assertFalse(result["snapshot"]["accepted"], result)
        self.assertEqual(result["worker_call_count"], 1)
        self.assertEqual(result["error_codes"], ["worker_safe_renderer_failed"])
        self.assertEqual(len(result["worker_retry_policies"]), 1)
        self.assertEqual(result["worker_retry_policy"]["policy_id"], "worker-retry-entry-worker-retry-policy-001")
        self.assertEqual(result["worker_retry_policy"]["type"], "isolinear_worker_retry_policy")
        self.assertEqual(result["worker_retry_policy"]["job_id"], "worker-retry-entry-job-001")
        self.assertEqual(result["worker_retry_policy"]["source_snapshot_id"], "worker-retry-entry-job-001-snapshot-003")
        self.assertTrue(result["worker_retry_policy"]["decision"]["eligible"])
        self.assertTrue(result["worker_retry_policy"]["decision"]["manual_retry_allowed"])
        self.assertFalse(result["worker_retry_policy"]["decision"]["automatic_retry_scheduled"])
        self.assertEqual(result["worker_retry_policy"]["backoff"]["attempt_number"], 1)
        self.assertEqual(result["worker_retry_policy"]["backoff"]["delay_seconds"], 5)
        self.assertEqual(result["worker_retry_policy"]["worker"]["authorization"], "Bearer <redacted>")
        self.assertEqual(result["worker_dispatches"], [])
        self.assertEqual(result["worker_progress_events"], [])
        self.assertEqual(result["render_plans"], [])
        self.assertEqual(result["artifacts"], [])
        self.assertEqual(result["complete_snapshots"], [])
        self.assertTrue(result["snapshot"]["orchestration"]["worker_called"])
        self.assertTrue(result["snapshot"]["orchestration"]["chart_rendering_called"])
        self.assertTrue(result["snapshot"]["orchestration"]["worker_retry_policy_bookkeeping_written"])
        self.assertFalse(result["snapshot"]["orchestration"]["worker_dispatch_bookkeeping_written"])
        self.assertFalse(result["snapshot"]["orchestration"]["render_plan_bookkeeping_written"])
        self.assertFalse(result["snapshot"]["orchestration"]["artifact_metadata_bookkeeping_written"])

    def test_worker_retry_policy_contracts_validate(self):
        result = verify_worker_retry_policy_contracts_validate(REPO_ROOT)

        self.assertTrue(result["accepted"]["worker_retry_policy_valid"], result)
        self.assertTrue(result["accepted"]["worker_transport_valid"], result)
        self.assertTrue(result["accepted"]["render_request_valid"], result)
        self.assertTrue(result["accepted"]["render_result_valid"], result)
        self.assertTrue(result["isolation_entry_a"]["worker_retry_policy_valid"], result)
        self.assertTrue(result["isolation_entry_b"]["worker_retry_policy_valid"], result)

    def test_worker_retry_policy_authorization_is_redacted(self):
        result = verify_worker_retry_policy_authorization_redaction(REPO_ROOT)

        self.assertTrue(result["raw_worker_authorization_received"], result)
        self.assertEqual(result["stored_authorization"], "Bearer <redacted>")
        self.assertEqual(result["stored_request_authorization"], "Bearer <redacted>")
        self.assertTrue(result["stored_authorization_redacted"], result)
        self.assertTrue(result["worker_token_absent_from_evidence"], result)
        self.assertEqual(result["secret_failure_code"]["error_codes"], ["worker_render_failed"])
        self.assertEqual(result["secret_failure_code"]["policy_failure_code"], "worker_render_failed")
        self.assertTrue(result["secret_failure_code"]["worker_token_absent_from_result"], result)
        self.assertNotIn(WORKER_TEST_TOKEN, str(result))

    def test_worker_retry_policy_secret_failure_code_is_redacted(self):
        result = verify_worker_retry_policy_secret_failure_code_redaction(REPO_ROOT)

        self.assertFalse(result["snapshot"]["accepted"], result)
        self.assertEqual(result["error_codes"], ["worker_render_failed"])
        self.assertEqual(result["policy_failure_code"], "worker_render_failed")
        self.assertEqual(result["worker_retry_policy"]["failure"]["code"], "worker_render_failed")
        self.assertTrue(result["worker_token_absent_from_result"], result)
        self.assertNotIn(WORKER_TEST_TOKEN, str(result))

    def test_unknown_job_rejected_before_retry_policy(self):
        result = verify_unknown_worker_retry_policy_job_rejected_before_call(REPO_ROOT)

        self.assertFalse(result["snapshot"]["accepted"], result)
        self.assertEqual(result["worker_call_count"], 0)
        self.assertEqual(result["error_codes"], ["unknown_job"])
        self.assertEqual(result["worker_retry_policies"], [])
        self.assertEqual(result["worker_dispatches"], [])

    def test_cross_config_entry_rejected_before_retry_policy(self):
        result = verify_cross_config_entry_worker_retry_policy_rejected_before_call(REPO_ROOT)

        self.assertFalse(result["cross_snapshot"]["accepted"], result)
        self.assertEqual(result["entry_a_worker_call_count"], 0)
        self.assertEqual(result["entry_b_worker_call_count"], 0)
        self.assertEqual(result["error_codes"], ["unknown_job"])
        self.assertEqual(result["entry_b_worker_retry_policies"], [])
        self.assertEqual(result["entry_b_worker_dispatches"], [])
        self.assertEqual(result["entry_b_render_plans"], [])
        self.assertEqual(result["entry_b_artifacts"], [])
        self.assertEqual(result["entry_b_complete_snapshots"], [])

    def test_valid_worker_retry_policies_stay_config_entry_scoped(self):
        result = verify_valid_worker_retry_policies_stay_config_entry_scoped(REPO_ROOT)

        self.assertFalse(result["entry_a"]["snapshot"]["accepted"], result)
        self.assertFalse(result["entry_b"]["snapshot"]["accepted"], result)
        self.assertEqual(result["entry_a"]["worker_call_count"], 1)
        self.assertEqual(result["entry_b"]["worker_call_count"], 1)
        self.assertEqual(result["entry_a"]["worker_retry_policies"][0]["job_id"], "worker-retry-isolation-entry-a-job-001")
        self.assertEqual(result["entry_b"]["worker_retry_policies"][0]["job_id"], "worker-retry-isolation-entry-b-job-001")
        self.assertEqual(result["entry_a"]["worker_retry_policies"][0]["config_entry_id"], "worker-retry-isolation-entry-a")
        self.assertEqual(result["entry_b"]["worker_retry_policies"][0]["config_entry_id"], "worker-retry-isolation-entry-b")

    def test_worker_retry_policy_side_effect_boundaries(self):
        result = verify_worker_retry_policy_side_effect_boundaries()

        self.assertTrue(result["allowed_aggregate"]["worker_called"])
        self.assertTrue(result["allowed_aggregate"]["chart_rendering_called"])
        self.assertTrue(result["allowed_aggregate"]["worker_retry_policy_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["websocket_command_registered"])
        self.assertFalse(result["forbidden_aggregate"]["worker_dispatch_bookkeeping_written"])
        self.assertFalse(result["forbidden_aggregate"]["worker_progress_bookkeeping_written"])
        self.assertFalse(result["forbidden_aggregate"]["render_plan_bookkeeping_written"])
        self.assertFalse(result["forbidden_aggregate"]["artifact_metadata_bookkeeping_written"])
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

    def test_worker_retry_backoff_policy_anchor_verification_passes(self):
        result = verify_worker_retry_backoff_policy_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
