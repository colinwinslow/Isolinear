import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.job_orchestration_worker_dispatch_rendering_anchor import WORKER_TEST_TOKEN  # noqa: E402
from Isolinear.worker_transport_failure_classification_anchor import (  # noqa: E402
    verify_cross_config_entry_worker_transport_classification_rejected_before_call,
    verify_unknown_worker_transport_classification_job_rejected_before_call,
    verify_valid_worker_transport_classifications_stay_config_entry_scoped,
    verify_worker_connection_failure_records_retry_classification,
    verify_worker_transport_classification_side_effect_boundaries,
    verify_worker_transport_failure_classification_anchor,
    verify_worker_transport_failure_classification_contracts_validate,
    verify_worker_transport_failure_classification_redaction,
    verify_worker_transport_failure_family_mapping,
    verify_worker_transport_secret_failure_text_redaction,
)


class WorkerTransportFailureClassificationAnchorTests(unittest.TestCase):
    def test_connection_failure_records_retry_classification(self):
        result = verify_worker_connection_failure_records_retry_classification(REPO_ROOT)

        self.assertTrue(result["snapshot"]["accepted"], result)
        self.assertEqual(result["snapshot"]["connection"]["results"][0]["result"]["status"], "failed")
        self.assertEqual(result["snapshot"]["connection"]["results"][0]["result"]["retry_allowed"], True)
        self.assertEqual(result["worker_call_count"], 1)
        self.assertEqual(result["error_codes"], ["worker_connection_error"])
        self.assertEqual(len(result["classifications"]), 1)
        self.assertEqual(
            result["classification"]["classification_id"],
            "worker-transport-entry-worker-transport-failure-001",
        )
        self.assertEqual(
            result["classification"]["type"],
            "isolinear_worker_transport_failure_classification",
        )
        self.assertEqual(result["classification"]["job_id"], "worker-transport-entry-job-001")
        self.assertEqual(
            result["classification"]["source_snapshot_id"],
            "worker-transport-entry-job-001-snapshot-003",
        )
        self.assertEqual(result["classification"]["failure"]["stage"], "worker_transport")
        self.assertEqual(result["classification"]["failure"]["code"], "worker_connection_error")
        self.assertEqual(result["classification"]["classification"]["family"], "connection")
        self.assertTrue(result["classification"]["classification"]["retry_eligible"])
        self.assertTrue(result["classification"]["classification"]["manual_retry_allowed"])
        self.assertFalse(result["classification"]["classification"]["automatic_retry_scheduled"])
        self.assertEqual(result["classification"]["backoff"]["attempt_number"], 1)
        self.assertEqual(result["classification"]["backoff"]["delay_seconds"], 5)
        self.assertEqual(result["classification"]["worker"]["authorization"], "Bearer <redacted>")
        self.assertEqual(result["worker_dispatches"], [])
        self.assertEqual(result["worker_progress_events"], [])
        self.assertEqual(result["worker_retry_policies"], [])
        self.assertEqual(result["render_plans"], [])
        self.assertEqual(result["artifacts"], [])
        self.assertEqual(result["complete_snapshots"], [])
        self.assertTrue(result["snapshot"]["orchestration"]["worker_called"])
        self.assertTrue(result["snapshot"]["orchestration"]["chart_rendering_called"])
        self.assertTrue(
            result["snapshot"]["orchestration"]["worker_transport_failure_classification_bookkeeping_written"]
        )
        self.assertFalse(result["snapshot"]["orchestration"]["worker_retry_policy_bookkeeping_written"])
        self.assertFalse(result["snapshot"]["orchestration"]["worker_dispatch_bookkeeping_written"])
        self.assertFalse(result["snapshot"]["orchestration"]["render_plan_bookkeeping_written"])
        self.assertFalse(result["snapshot"]["orchestration"]["artifact_metadata_bookkeeping_written"])

    def test_transport_failure_families_map_deterministically(self):
        result = verify_worker_transport_failure_family_mapping(REPO_ROOT)

        self.assertEqual(result["connection"]["classification"]["classification"]["family"], "connection")
        self.assertTrue(result["connection"]["classification"]["classification"]["retry_eligible"])
        self.assertEqual(result["connection"]["classification"]["backoff"]["delay_seconds"], 5)
        self.assertEqual(result["http"]["classification"]["classification"]["family"], "http")
        self.assertTrue(result["http"]["classification"]["classification"]["retry_eligible"])
        self.assertEqual(result["malformed_response"]["classification"]["classification"]["family"], "malformed_response")
        self.assertFalse(result["malformed_response"]["classification"]["classification"]["retry_eligible"])
        self.assertEqual(result["malformed_response"]["classification"]["backoff"]["delay_seconds"], 0)

    def test_worker_transport_classification_contracts_validate(self):
        result = verify_worker_transport_failure_classification_contracts_validate(REPO_ROOT)

        self.assertTrue(result["accepted"]["worker_transport_classification_valid"], result)
        self.assertTrue(result["accepted"]["worker_transport_valid"], result)
        self.assertTrue(result["accepted"]["render_request_valid"], result)
        for family, case in result["families"].items():
            self.assertTrue(case["worker_transport_classification_valid"], family)
            self.assertEqual(case["observed_family"], family)
        self.assertTrue(result["isolation_entry_a"]["worker_transport_classification_valid"], result)
        self.assertTrue(result["isolation_entry_b"]["worker_transport_classification_valid"], result)

    def test_worker_transport_classification_redacts_sensitive_material(self):
        result = verify_worker_transport_failure_classification_redaction(REPO_ROOT)

        self.assertTrue(result["raw_worker_authorization_received"], result)
        self.assertEqual(result["stored_authorization"], "Bearer <redacted>")
        self.assertEqual(result["stored_request_authorization"], "Bearer <redacted>")
        self.assertTrue(result["stored_authorization_redacted"], result)
        self.assertTrue(result["worker_token_absent_from_evidence"], result)
        self.assertEqual(result["secret_failure_text"]["error_codes"], ["worker_transport_failed"])
        self.assertEqual(
            result["secret_failure_text"]["classification_failure_code"],
            "worker_transport_failed",
        )
        self.assertTrue(result["secret_failure_text"]["worker_token_absent_from_result"], result)
        self.assertNotIn(WORKER_TEST_TOKEN, str(result))

    def test_worker_transport_secret_failure_text_is_redacted(self):
        result = verify_worker_transport_secret_failure_text_redaction(REPO_ROOT)

        self.assertTrue(result["snapshot"]["accepted"], result)
        self.assertEqual(
            result["snapshot"]["connection"]["results"][0]["result"]["failure"]["code"],
            "worker_transport_failed",
        )
        self.assertEqual(result["error_codes"], ["worker_transport_failed"])
        self.assertEqual(result["classification_failure_code"], "worker_transport_failed")
        self.assertEqual(result["classification"]["failure"]["code"], "worker_transport_failed")
        self.assertNotIn("Bearer", result["classification_failure_message"])
        self.assertTrue(result["worker_token_absent_from_result"], result)
        self.assertNotIn(WORKER_TEST_TOKEN, str(result))

    def test_unknown_job_rejected_before_transport_classification(self):
        result = verify_unknown_worker_transport_classification_job_rejected_before_call(REPO_ROOT)

        self.assertFalse(result["snapshot"]["accepted"], result)
        self.assertEqual(result["worker_call_count"], 0)
        self.assertEqual(result["error_codes"], ["unknown_job"])
        self.assertEqual(result["classifications"], [])
        self.assertEqual(result["worker_dispatches"], [])

    def test_cross_config_entry_rejected_before_transport_classification(self):
        result = verify_cross_config_entry_worker_transport_classification_rejected_before_call(REPO_ROOT)

        self.assertFalse(result["cross_snapshot"]["accepted"], result)
        self.assertEqual(result["entry_a_worker_call_count"], 0)
        self.assertEqual(result["entry_b_worker_call_count"], 0)
        self.assertEqual(result["error_codes"], ["unknown_job"])
        self.assertEqual(result["entry_b_classifications"], [])
        self.assertEqual(result["entry_b_worker_dispatches"], [])
        self.assertEqual(result["entry_b_render_plans"], [])
        self.assertEqual(result["entry_b_artifacts"], [])
        self.assertEqual(result["entry_b_complete_snapshots"], [])

    def test_valid_transport_classifications_stay_config_entry_scoped(self):
        result = verify_valid_worker_transport_classifications_stay_config_entry_scoped(REPO_ROOT)

        self.assertTrue(result["entry_a"]["snapshot"]["accepted"], result)
        self.assertTrue(result["entry_b"]["snapshot"]["accepted"], result)
        self.assertEqual(result["entry_a"]["snapshot"]["connection"]["results"][0]["result"]["status"], "failed")
        self.assertEqual(result["entry_b"]["snapshot"]["connection"]["results"][0]["result"]["status"], "failed")
        self.assertEqual(result["entry_a"]["worker_call_count"], 1)
        self.assertEqual(result["entry_b"]["worker_call_count"], 1)
        self.assertEqual(
            result["entry_a"]["classifications"][0]["job_id"],
            "worker-transport-isolation-entry-a-job-001",
        )
        self.assertEqual(
            result["entry_b"]["classifications"][0]["job_id"],
            "worker-transport-isolation-entry-b-job-001",
        )
        self.assertEqual(
            result["entry_a"]["classifications"][0]["config_entry_id"],
            "worker-transport-isolation-entry-a",
        )
        self.assertEqual(
            result["entry_b"]["classifications"][0]["config_entry_id"],
            "worker-transport-isolation-entry-b",
        )

    def test_worker_transport_classification_side_effect_boundaries(self):
        result = verify_worker_transport_classification_side_effect_boundaries()

        self.assertTrue(result["allowed_aggregate"]["worker_called"])
        self.assertTrue(result["allowed_aggregate"]["chart_rendering_called"])
        self.assertTrue(result["allowed_aggregate"]["worker_transport_failure_classification_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["websocket_command_registered"])
        self.assertFalse(result["forbidden_aggregate"]["worker_dispatch_bookkeeping_written"])
        self.assertFalse(result["forbidden_aggregate"]["worker_progress_bookkeeping_written"])
        self.assertFalse(result["forbidden_aggregate"]["worker_retry_policy_bookkeeping_written"])
        self.assertFalse(result["forbidden_aggregate"]["render_plan_bookkeeping_written"])
        self.assertFalse(result["forbidden_aggregate"]["artifact_metadata_bookkeeping_written"])
        self.assertFalse(result["forbidden_aggregate"]["model_provider_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_history_read"])
        self.assertFalse(result["forbidden_aggregate"]["semantic_memory_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_service_or_state_mutation_called"])
        self.assertFalse(result["forbidden_aggregate"]["token_generated"])
        self.assertFalse(result["forbidden_aggregate"]["token_rotation_called"])
        self.assertFalse(result["forbidden_aggregate"]["token_leaked_to_card"])
        self.assertFalse(result["forbidden_aggregate"]["token_leaked_to_model_provider"])
        self.assertFalse(result["forbidden_aggregate"]["chart_artifact_written"])
        self.assertFalse(result["forbidden_aggregate"]["durable_storage_written"])
        self.assertFalse(result["forbidden_aggregate"]["durable_retry_storage_written"])
        self.assertFalse(result["forbidden_aggregate"]["worker_health_check_called"])
        self.assertFalse(result["forbidden_aggregate"]["retry_behavior_called"])
        self.assertFalse(result["forbidden_aggregate"]["scheduler_called"])
        self.assertFalse(result["forbidden_aggregate"]["automatic_progress_task_called"])
        self.assertFalse(result["forbidden_aggregate"]["new_worker_transport_added"])
        self.assertFalse(result["forbidden_aggregate"]["worker_render_result_retry_policy_changed"])
        self.assertFalse(result["forbidden_aggregate"]["job_orchestration_called"])

    def test_worker_transport_failure_classification_anchor_verification_passes(self):
        result = verify_worker_transport_failure_classification_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
