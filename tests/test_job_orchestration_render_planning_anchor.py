import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.job_orchestration_render_planning_anchor import (  # noqa: E402
    verify_cross_config_entry_render_plan_rejected,
    verify_job_orchestration_render_planning_anchor,
    verify_render_plan_side_effect_boundaries,
    verify_render_plans_and_chart_specs_validate,
    verify_repeated_snapshot_requests_reuse_render_plan,
    verify_scaffold_ready_snapshot_records_render_plan,
    verify_unknown_render_plan_job_rejected_before_planning,
    verify_valid_render_plans_stay_config_entry_scoped,
)


class JobOrchestrationRenderPlanningAnchorTests(unittest.TestCase):
    def test_scaffold_ready_snapshot_records_render_plan(self):
        result = verify_scaffold_ready_snapshot_records_render_plan(REPO_ROOT)

        self.assertTrue(result["start"]["accepted"], result)
        self.assertTrue(result["snapshot_dispatch"]["accepted"], result)
        self.assertEqual(result["artifact_snapshot"]["status"], "complete")
        self.assertEqual(
            result["artifact_snapshot"]["snapshot_id"],
            "render-plan-entry-job-001-snapshot-004",
        )
        self.assertEqual(result["render_plan"]["render_plan_id"], "render-plan-entry-render-plan-001")
        self.assertEqual(result["render_plan"]["job_id"], "render-plan-entry-job-001")
        self.assertEqual(
            result["render_plan"]["source_snapshot_id"],
            "render-plan-entry-job-001-snapshot-003",
        )
        self.assertEqual(result["render_plan"]["artifact_id"], "render-plan-entry-artifact-001")
        self.assertEqual(result["render_plan"]["render_mode"], "safe")
        self.assertEqual(result["render_plan"]["renderer"], "trusted_chart_spec")
        self.assertEqual(result["render_plan"]["chart_spec"]["chart_type"], "time_series")
        self.assertEqual(
            result["render_plan"]["chart_spec"]["series"][0]["source"]["entity_id"],
            "sensor.upstairs_temperature",
        )
        self.assertTrue(result["snapshot_validation"]["accepted"], result)
        self.assertTrue(all(item["accepted"] for item in result["render_plan_validation"]), result)
        self.assertTrue(all(item["accepted"] for item in result["chart_spec_validation"]), result)
        self.assertTrue(result["snapshot_dispatch"]["orchestration"]["render_plan_bookkeeping_written"])
        self.assertTrue(result["snapshot_dispatch"]["orchestration"]["artifact_metadata_bookkeeping_written"])

    def test_repeated_snapshot_requests_reuse_render_plan(self):
        result = verify_repeated_snapshot_requests_reuse_render_plan(REPO_ROOT)

        self.assertTrue(result["first"]["accepted"], result)
        self.assertTrue(result["second"]["accepted"], result)
        self.assertTrue(result["same_snapshot_returned"], result)
        self.assertTrue(result["same_render_plan_returned"], result)
        self.assertEqual(result["render_plan_count"], 1)
        self.assertEqual(result["artifact_count"], 1)
        self.assertEqual(result["complete_snapshot_count"], 1)
        self.assertEqual(
            result["first_render_plan"]["render_plan_id"],
            "render-plan-idempotent-entry-render-plan-001",
        )

    def test_unknown_job_fails_before_render_planning(self):
        result = verify_unknown_render_plan_job_rejected_before_planning(REPO_ROOT)

        self.assertFalse(result["snapshot"]["accepted"], result)
        self.assertEqual(result["error_codes"], ["unknown_job"])
        self.assertEqual(result["render_plans"], [])
        self.assertEqual(result["artifacts"], [])
        self.assertFalse(result["snapshot"]["orchestration"]["render_plan_bookkeeping_written"])
        self.assertFalse(result["snapshot"]["orchestration"]["artifact_metadata_bookkeeping_written"])

    def test_cross_config_entry_render_plan_is_rejected_before_planning(self):
        result = verify_cross_config_entry_render_plan_rejected(REPO_ROOT)

        self.assertFalse(result["cross_snapshot"]["accepted"], result)
        self.assertEqual(result["error_codes"], ["unknown_job"])
        self.assertEqual(result["entry_a_render_plans"], [])
        self.assertEqual(result["entry_b_render_plans"], [])
        self.assertEqual(result["entry_b_artifacts"], [])
        self.assertEqual(result["entry_b_complete_snapshots"], [])
        self.assertFalse(result["cross_snapshot"]["orchestration"]["render_plan_bookkeeping_written"])

    def test_valid_render_plans_stay_config_entry_scoped(self):
        result = verify_valid_render_plans_stay_config_entry_scoped(REPO_ROOT)

        self.assertTrue(result["entry_a"]["snapshot"]["accepted"], result)
        self.assertTrue(result["entry_b"]["snapshot"]["accepted"], result)
        self.assertEqual(result["entry_a"]["render_plans"][0]["job_id"], "valid-render-plan-entry-a-job-001")
        self.assertEqual(result["entry_b"]["render_plans"][0]["job_id"], "valid-render-plan-entry-b-job-001")
        self.assertEqual(
            result["entry_a"]["render_plans"][0]["chart_spec"]["series"][0]["source"]["entity_id"],
            "sensor.upstairs_temperature",
        )
        self.assertEqual(
            result["entry_b"]["render_plans"][0]["chart_spec"]["series"][0]["source"]["entity_id"],
            "binary_sensor.office_window",
        )
        self.assertEqual(result["entry_a"]["render_plans"][0]["chart_spec"]["chart_type"], "time_series")
        self.assertEqual(result["entry_b"]["render_plans"][0]["chart_spec"]["chart_type"], "timeline")

    def test_render_plans_and_chart_specs_validate_before_storage(self):
        result = verify_render_plans_and_chart_specs_validate(REPO_ROOT)

        self.assertTrue(result["accepted"]["render_plan_valid"], result)
        self.assertTrue(result["accepted"]["chart_spec_valid"], result)
        self.assertTrue(result["idempotent"]["render_plan_valid"], result)
        self.assertTrue(result["idempotent"]["chart_spec_valid"], result)
        self.assertTrue(result["isolation_entry_a"]["render_plan_valid"], result)
        self.assertTrue(result["isolation_entry_a"]["chart_spec_valid"], result)
        self.assertTrue(result["isolation_entry_b"]["render_plan_valid"], result)
        self.assertTrue(result["isolation_entry_b"]["chart_spec_valid"], result)

    def test_render_plan_side_effect_boundaries(self):
        result = verify_render_plan_side_effect_boundaries()

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
        self.assertTrue(result["allowed_aggregate"]["render_plan_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["artifact_metadata_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["job_state_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["job_orchestration_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["websocket_command_registered"])

    def test_render_planning_anchor_verification_passes(self):
        result = verify_job_orchestration_render_planning_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
