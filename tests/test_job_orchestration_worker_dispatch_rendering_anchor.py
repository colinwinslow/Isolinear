import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.job_orchestration_worker_dispatch_rendering_anchor import (  # noqa: E402
    WORKER_TEST_TOKEN,
    verify_cross_config_entry_worker_rejected_before_call,
    verify_job_orchestration_worker_dispatch_rendering_anchor,
    verify_repeated_snapshot_requests_reuse_worker_dispatch,
    verify_unknown_worker_job_rejected_before_call,
    verify_valid_worker_dispatches_stay_config_entry_scoped,
    verify_worker_authorization_redaction,
    verify_worker_dispatch_contracts_validate,
    verify_worker_dispatch_records_render_result,
    verify_worker_dispatch_side_effect_boundaries,
    verify_worker_failure_rejected_before_storage,
)


class JobOrchestrationWorkerDispatchRenderingAnchorTests(unittest.TestCase):
    def test_worker_dispatch_records_render_result(self):
        result = verify_worker_dispatch_records_render_result(REPO_ROOT)

        self.assertTrue(result["start"]["accepted"], result)
        self.assertTrue(result["snapshot_dispatch"]["accepted"], result)
        self.assertEqual(result["worker_call_count"], 1)
        self.assertEqual(result["artifact_snapshot"]["status"], "complete")
        self.assertEqual(
            result["artifact_snapshot"]["snapshot_id"],
            "worker-dispatch-entry-job-001-snapshot-004",
        )
        self.assertEqual(
            result["worker_dispatch"]["dispatch_id"],
            "worker-dispatch-entry-worker-dispatch-001",
        )
        self.assertEqual(result["worker_dispatch"]["job_id"], "worker-dispatch-entry-job-001")
        self.assertEqual(
            result["worker_dispatch"]["source_snapshot_id"],
            "worker-dispatch-entry-job-001-snapshot-003",
        )
        self.assertEqual(
            result["worker_dispatch"]["render_plan_id"],
            "worker-dispatch-entry-render-plan-001",
        )
        self.assertEqual(result["worker_dispatch"]["artifact_id"], "worker-dispatch-entry-artifact-001")
        self.assertEqual(result["worker_dispatch"]["status"], "render_succeeded")
        self.assertEqual(
            result["worker_dispatch"]["request"]["headers"]["authorization"],
            "Bearer <redacted>",
        )
        self.assertEqual(result["worker_dispatch"]["render_result"]["status"], "success")
        self.assertEqual(
            result["worker_calls"][0]["history_entity_ids"],
            ["sensor.upstairs_temperature"],
        )
        self.assertTrue(all(item["accepted"] for item in result["worker_dispatch_validation"]), result)
        self.assertTrue(all(item["accepted"] for item in result["worker_transport_validation"]), result)
        self.assertTrue(all(item["accepted"] for item in result["render_request_validation"]), result)
        self.assertTrue(all(item["accepted"] for item in result["render_result_validation"]), result)
        self.assertTrue(all(item["accepted"] for item in result["history_series_validation"]), result)
        self.assertTrue(result["snapshot_dispatch"]["orchestration"]["worker_called"])
        self.assertTrue(result["snapshot_dispatch"]["orchestration"]["chart_rendering_called"])
        self.assertTrue(result["snapshot_dispatch"]["orchestration"]["worker_dispatch_bookkeeping_written"])

    def test_repeated_snapshot_requests_reuse_worker_dispatch(self):
        result = verify_repeated_snapshot_requests_reuse_worker_dispatch(REPO_ROOT)

        self.assertTrue(result["first"]["accepted"], result)
        self.assertTrue(result["second"]["accepted"], result)
        self.assertEqual(result["worker_call_count"], 1)
        self.assertTrue(result["same_snapshot_returned"], result)
        self.assertTrue(result["same_worker_dispatch_returned"], result)
        self.assertEqual(result["worker_dispatch_count"], 1)
        self.assertEqual(result["render_plan_count"], 1)
        self.assertEqual(result["artifact_count"], 1)
        self.assertEqual(result["complete_snapshot_count"], 1)

    def test_worker_dispatch_contracts_validate(self):
        result = verify_worker_dispatch_contracts_validate(REPO_ROOT)

        self.assertTrue(result["accepted"]["worker_dispatch_valid"], result)
        self.assertTrue(result["accepted"]["worker_transport_valid"], result)
        self.assertTrue(result["accepted"]["render_request_valid"], result)
        self.assertTrue(result["accepted"]["render_result_valid"], result)
        self.assertTrue(result["accepted"]["render_plan_valid"], result)
        self.assertTrue(result["accepted"]["chart_spec_valid"], result)
        self.assertTrue(result["accepted"]["history_series_valid"], result)
        self.assertTrue(result["idempotent"]["worker_dispatch_valid"], result)
        self.assertTrue(result["isolation_entry_a"]["worker_dispatch_valid"], result)
        self.assertTrue(result["isolation_entry_b"]["worker_dispatch_valid"], result)

    def test_worker_authorization_is_redacted(self):
        result = verify_worker_authorization_redaction(REPO_ROOT)

        self.assertTrue(result["raw_worker_authorization_received"], result)
        self.assertEqual(result["stored_authorization"], "Bearer <redacted>")
        self.assertTrue(result["stored_authorization_redacted"], result)
        self.assertTrue(result["worker_token_absent_from_evidence"], result)
        self.assertNotIn(WORKER_TEST_TOKEN, str(result))

    def test_worker_failure_rejected_before_storage(self):
        result = verify_worker_failure_rejected_before_storage(REPO_ROOT)

        self.assertTrue(result["snapshot"]["accepted"], result)
        self.assertEqual(result["snapshot"]["connection"]["results"][0]["result"]["status"], "failed")
        self.assertEqual(
            result["snapshot"]["connection"]["results"][0]["result"]["failure"]["stage"],
            "worker_render",
        )
        self.assertEqual(result["worker_call_count"], 1)
        self.assertEqual(result["error_codes"], ["worker_safe_renderer_failed"])
        self.assertEqual(result["worker_dispatches"], [])
        self.assertEqual(result["render_plans"], [])
        self.assertEqual(result["artifacts"], [])
        self.assertEqual(result["complete_snapshots"], [])
        self.assertTrue(result["snapshot"]["orchestration"]["worker_called"])
        self.assertFalse(result["snapshot"]["orchestration"]["worker_dispatch_bookkeeping_written"])
        self.assertFalse(result["snapshot"]["orchestration"]["render_plan_bookkeeping_written"])
        self.assertFalse(result["snapshot"]["orchestration"]["artifact_metadata_bookkeeping_written"])

    def test_unknown_job_rejected_before_worker_call(self):
        result = verify_unknown_worker_job_rejected_before_call(REPO_ROOT)

        self.assertFalse(result["snapshot"]["accepted"], result)
        self.assertEqual(result["worker_call_count"], 0)
        self.assertEqual(result["error_codes"], ["unknown_job"])
        self.assertEqual(result["worker_dispatches"], [])
        self.assertEqual(result["render_plans"], [])
        self.assertEqual(result["artifacts"], [])

    def test_cross_config_entry_rejected_before_worker_call(self):
        result = verify_cross_config_entry_worker_rejected_before_call(REPO_ROOT)

        self.assertFalse(result["cross_snapshot"]["accepted"], result)
        self.assertEqual(result["entry_a_worker_call_count"], 0)
        self.assertEqual(result["entry_b_worker_call_count"], 0)
        self.assertEqual(result["error_codes"], ["unknown_job"])
        self.assertEqual(result["entry_b_worker_dispatches"], [])
        self.assertEqual(result["entry_b_render_plans"], [])
        self.assertEqual(result["entry_b_artifacts"], [])
        self.assertEqual(result["entry_b_complete_snapshots"], [])

    def test_valid_worker_dispatches_stay_config_entry_scoped(self):
        result = verify_valid_worker_dispatches_stay_config_entry_scoped(REPO_ROOT)

        self.assertTrue(result["entry_a"]["snapshot"]["accepted"], result)
        self.assertTrue(result["entry_b"]["snapshot"]["accepted"], result)
        self.assertEqual(result["entry_a"]["worker_call_count"], 1)
        self.assertEqual(result["entry_b"]["worker_call_count"], 1)
        self.assertEqual(result["entry_a"]["worker_dispatches"][0]["job_id"], "worker-isolation-entry-a-job-001")
        self.assertEqual(result["entry_b"]["worker_dispatches"][0]["job_id"], "worker-isolation-entry-b-job-001")
        self.assertEqual(
            result["entry_a"]["worker_calls"][0]["history_entity_ids"],
            ["sensor.upstairs_temperature"],
        )
        self.assertEqual(
            result["entry_b"]["worker_calls"][0]["history_entity_ids"],
            ["binary_sensor.office_window"],
        )
        self.assertEqual(result["entry_a"]["render_plans"][0]["chart_spec"]["chart_type"], "time_series")
        self.assertEqual(result["entry_b"]["render_plans"][0]["chart_spec"]["chart_type"], "timeline")

    def test_worker_dispatch_side_effect_boundaries(self):
        result = verify_worker_dispatch_side_effect_boundaries()

        self.assertTrue(result["allowed_aggregate"]["worker_called"])
        self.assertTrue(result["allowed_aggregate"]["chart_rendering_called"])
        self.assertTrue(result["allowed_aggregate"]["worker_dispatch_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["render_plan_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["artifact_metadata_bookkeeping_written"])
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
        self.assertFalse(result["forbidden_aggregate"]["subscription_bookkeeping_written"])
        self.assertFalse(result["forbidden_aggregate"]["subscription_progress_streaming_called"])
        self.assertFalse(result["forbidden_aggregate"]["job_orchestration_called"])

    def test_worker_dispatch_rendering_anchor_verification_passes(self):
        result = verify_job_orchestration_worker_dispatch_rendering_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
