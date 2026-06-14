import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.model_provider_retry_backoff_policy_anchor import (  # noqa: E402
    verify_cross_config_entry_provider_retry_policy_rejected_before_call,
    verify_malformed_provider_failure_rejected_before_policy,
    verify_model_provider_retry_backoff_policy_anchor,
    verify_model_provider_retry_policy_contracts_validate,
    verify_model_provider_retry_policy_side_effect_boundaries,
    verify_provider_failure_records_retry_policy,
    verify_provider_retry_policy_failure_details_are_sanitized,
    verify_secret_provider_failure_rejected_before_policy,
    verify_unknown_provider_retry_policy_job_rejected_before_call,
    verify_valid_provider_retry_policies_stay_config_entry_scoped,
)


class ModelProviderRetryBackoffPolicyAnchorTests(unittest.TestCase):
    def test_provider_failure_records_retry_policy(self):
        result = verify_provider_failure_records_retry_policy(REPO_ROOT)

        self.assertTrue(result["snapshot"]["accepted"], result)
        self.assertEqual(result["card_snapshot"]["status"], "failed")
        self.assertEqual(result["card_snapshot"]["retry_allowed"], True)
        self.assertEqual(result["planner_call_count"], 1)
        self.assertEqual(result["error_codes"], ["model_provider_connection_error"])
        self.assertEqual(len(result["model_provider_retry_policies"]), 1)
        self.assertEqual(
            result["model_provider_retry_policy"]["policy_id"],
            "provider-retry-entry-model-provider-retry-policy-001",
        )
        self.assertEqual(result["model_provider_retry_policy"]["type"], "isolinear_model_provider_retry_policy")
        self.assertEqual(result["model_provider_retry_policy"]["job_id"], "provider-retry-entry-job-001")
        self.assertEqual(
            result["model_provider_retry_policy"]["source_snapshot_id"],
            "provider-retry-entry-job-001-snapshot-003",
        )
        self.assertTrue(result["model_provider_retry_policy"]["decision"]["eligible"])
        self.assertTrue(result["model_provider_retry_policy"]["decision"]["manual_retry_allowed"])
        self.assertFalse(result["model_provider_retry_policy"]["decision"]["automatic_retry_scheduled"])
        self.assertEqual(result["model_provider_retry_policy"]["backoff"]["attempt_number"], 1)
        self.assertEqual(result["model_provider_retry_policy"]["backoff"]["delay_seconds"], 5)
        self.assertEqual(result["provider_plans"], [])
        self.assertEqual(result["render_plans"], [])
        self.assertEqual(result["artifacts"], [])
        self.assertEqual(result["complete_snapshots"], [])
        self.assertTrue(result["snapshot"]["orchestration"]["model_provider_called"])
        self.assertTrue(result["snapshot"]["orchestration"]["model_provider_retry_policy_bookkeeping_written"])
        self.assertFalse(result["snapshot"]["orchestration"]["model_provider_plan_bookkeeping_written"])
        self.assertFalse(result["snapshot"]["orchestration"]["render_plan_bookkeeping_written"])
        self.assertFalse(result["snapshot"]["orchestration"]["artifact_metadata_bookkeeping_written"])

    def test_model_provider_retry_policy_contracts_validate(self):
        result = verify_model_provider_retry_policy_contracts_validate(REPO_ROOT)

        self.assertTrue(result["accepted"]["model_provider_retry_policy_valid"], result)
        self.assertTrue(result["isolation_entry_a"]["model_provider_retry_policy_valid"], result)
        self.assertTrue(result["isolation_entry_b"]["model_provider_retry_policy_valid"], result)

    def test_provider_failure_details_are_sanitized(self):
        result = verify_provider_retry_policy_failure_details_are_sanitized(REPO_ROOT)

        self.assertEqual(result["stored_failure_code"], "model_provider_connection_error")
        self.assertTrue(result["card_snapshot_excludes_provider_endpoint"], result)
        self.assertTrue(result["card_snapshot_excludes_provider_model"], result)
        self.assertTrue(result["card_snapshot_excludes_policy_id"], result)
        self.assertTrue(result["card_snapshot_excludes_policy_type"], result)
        self.assertEqual(result["secret_failure"]["error_codes"], ["model_provider_failure_forbidden_material"])
        self.assertEqual(result["secret_failure"]["policy_count"], 0)
        self.assertTrue(result["secret_failure"]["secret_absent_from_result"], result)

    def test_secret_provider_failure_rejected_before_policy(self):
        result = verify_secret_provider_failure_rejected_before_policy(REPO_ROOT)

        self.assertFalse(result["snapshot"]["accepted"], result)
        self.assertEqual(result["planner_call_count"], 1)
        self.assertEqual(result["error_codes"], ["model_provider_failure_forbidden_material"])
        self.assertEqual(result["model_provider_retry_policies"], [])
        self.assertEqual(result["provider_plans"], [])
        self.assertEqual(result["render_plans"], [])
        self.assertEqual(result["artifacts"], [])
        self.assertEqual(result["complete_snapshots"], [])

    def test_malformed_provider_failure_rejected_before_policy(self):
        result = verify_malformed_provider_failure_rejected_before_policy(REPO_ROOT)

        self.assertFalse(result["snapshot"]["accepted"], result)
        self.assertEqual(result["planner_call_count"], 1)
        self.assertEqual(result["error_codes"], ["invalid_model_provider_failure"])
        self.assertEqual(result["model_provider_retry_policies"], [])
        self.assertEqual(result["provider_plans"], [])
        self.assertEqual(result["render_plans"], [])
        self.assertEqual(result["artifacts"], [])
        self.assertEqual(result["complete_snapshots"], [])

    def test_unknown_job_rejected_before_provider_retry_policy(self):
        result = verify_unknown_provider_retry_policy_job_rejected_before_call(REPO_ROOT)

        self.assertFalse(result["snapshot"]["accepted"], result)
        self.assertEqual(result["planner_call_count"], 0)
        self.assertEqual(result["error_codes"], ["unknown_job"])
        self.assertEqual(result["model_provider_retry_policies"], [])
        self.assertEqual(result["provider_plans"], [])
        self.assertEqual(result["render_plans"], [])
        self.assertEqual(result["artifacts"], [])

    def test_cross_config_entry_rejected_before_provider_retry_policy(self):
        result = verify_cross_config_entry_provider_retry_policy_rejected_before_call(REPO_ROOT)

        self.assertFalse(result["cross_snapshot"]["accepted"], result)
        self.assertEqual(result["entry_a_planner_call_count"], 0)
        self.assertEqual(result["entry_b_planner_call_count"], 0)
        self.assertEqual(result["error_codes"], ["unknown_job"])
        self.assertEqual(result["entry_b_model_provider_retry_policies"], [])
        self.assertEqual(result["entry_b_provider_plans"], [])
        self.assertEqual(result["entry_b_render_plans"], [])
        self.assertEqual(result["entry_b_artifacts"], [])
        self.assertEqual(result["entry_b_complete_snapshots"], [])

    def test_valid_provider_retry_policies_stay_config_entry_scoped(self):
        result = verify_valid_provider_retry_policies_stay_config_entry_scoped(REPO_ROOT)

        self.assertTrue(result["entry_a"]["snapshot"]["accepted"], result)
        self.assertTrue(result["entry_b"]["snapshot"]["accepted"], result)
        self.assertEqual(result["entry_a"]["planner_call_count"], 1)
        self.assertEqual(result["entry_b"]["planner_call_count"], 1)
        self.assertEqual(
            result["entry_a"]["model_provider_retry_policies"][0]["job_id"],
            "provider-retry-isolation-entry-a-job-001",
        )
        self.assertEqual(
            result["entry_b"]["model_provider_retry_policies"][0]["job_id"],
            "provider-retry-isolation-entry-b-job-001",
        )
        self.assertEqual(
            result["entry_a"]["model_provider_retry_policies"][0]["config_entry_id"],
            "provider-retry-isolation-entry-a",
        )
        self.assertEqual(
            result["entry_b"]["model_provider_retry_policies"][0]["config_entry_id"],
            "provider-retry-isolation-entry-b",
        )

    def test_model_provider_retry_policy_side_effect_boundaries(self):
        result = verify_model_provider_retry_policy_side_effect_boundaries()

        self.assertTrue(result["allowed_aggregate"]["model_provider_called"])
        self.assertTrue(result["allowed_aggregate"]["model_provider_retry_policy_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["job_state_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["job_orchestration_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["websocket_command_registered"])
        self.assertFalse(result["forbidden_aggregate"]["model_provider_plan_bookkeeping_written"])
        self.assertFalse(result["forbidden_aggregate"]["render_plan_bookkeeping_written"])
        self.assertFalse(result["forbidden_aggregate"]["artifact_metadata_bookkeeping_written"])
        self.assertFalse(result["forbidden_aggregate"]["worker_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_history_read"])
        self.assertFalse(result["forbidden_aggregate"]["semantic_memory_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_service_or_state_mutation_called"])
        self.assertFalse(result["forbidden_aggregate"]["token_generated"])
        self.assertFalse(result["forbidden_aggregate"]["chart_artifact_written"])
        self.assertFalse(result["forbidden_aggregate"]["chart_rendering_called"])
        self.assertFalse(result["forbidden_aggregate"]["durable_storage_written"])
        self.assertFalse(result["forbidden_aggregate"]["retry_behavior_called"])
        self.assertFalse(result["forbidden_aggregate"]["automatic_progress_task_called"])
        self.assertFalse(result["forbidden_aggregate"]["job_orchestration_called"])

    def test_model_provider_retry_backoff_policy_anchor_verification_passes(self):
        result = verify_model_provider_retry_backoff_policy_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
