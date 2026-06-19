import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.job_orchestration_model_provider_planning_anchor import (  # noqa: E402
    verify_cross_config_entry_model_provider_rejected_before_call,
    verify_hidden_provider_entity_rejected_before_storage,
    verify_hidden_provider_output_rejected_recursively,
    verify_invalid_provider_chart_spec_rejected_before_storage,
    verify_model_provider_plan_side_effect_boundaries,
    verify_model_provider_plans_stay_config_entry_scoped,
    verify_model_provider_schema_validation,
    verify_provider_produced_chart_spec_records_provider_plan,
    verify_repeated_snapshot_requests_reuse_provider_plan,
    verify_unknown_model_provider_job_rejected_before_call,
    verify_job_orchestration_model_provider_planning_anchor,
)


class JobOrchestrationModelProviderPlanningAnchorTests(unittest.TestCase):
    def assert_card_facing_model_provider_failure(
        self,
        dispatch: dict,
        expected_code: str,
    ) -> None:
        self.assertTrue(dispatch["accepted"], dispatch)
        self.assertEqual(dispatch["connection"]["errors"], [], dispatch)
        snapshot = dispatch["handler_result"]["snapshot"]
        self.assertEqual(snapshot["status"], "failed")
        self.assertEqual(snapshot["progress"]["stage"], "model_provider_failure_snapshot_ready")
        self.assertEqual(snapshot["failure"]["stage"], "model_provider_planning")
        self.assertEqual(snapshot["failure"]["code"], expected_code)

    def test_provider_produced_chart_spec_records_provider_plan(self):
        result = verify_provider_produced_chart_spec_records_provider_plan(REPO_ROOT)

        self.assertTrue(result["start"]["accepted"], result)
        self.assertTrue(result["snapshot_dispatch"]["accepted"], result)
        self.assertEqual(result["planner_call_count"], 1)
        self.assertEqual(result["artifact_snapshot"]["status"], "complete")
        self.assertEqual(
            result["artifact_snapshot"]["snapshot_id"],
            "model-provider-entry-job-001-snapshot-004",
        )
        self.assertEqual(
            result["provider_plan"]["provider_plan_id"],
            "model-provider-entry-provider-plan-001",
        )
        self.assertEqual(result["provider_plan"]["job_id"], "model-provider-entry-job-001")
        self.assertEqual(
            result["provider_plan"]["source_snapshot_id"],
            "model-provider-entry-job-001-snapshot-003",
        )
        self.assertEqual(result["provider_plan"]["provider"]["type"], "ollama_compatible")
        self.assertEqual(result["provider_plan"]["provider"]["role"], "planner")
        self.assertEqual(result["provider_plan"]["status"], "chart_spec_ready")
        self.assertEqual(result["render_plan"]["render_plan_id"], "model-provider-entry-render-plan-001")
        self.assertEqual(result["render_plan"]["chart_spec"]["title"], "Provider Upstairs Temperature")
        self.assertEqual(
            result["render_plan"]["chart_spec"]["series"][0]["source"]["entity_id"],
            "sensor.upstairs_temperature",
        )
        self.assertNotIn("placeholder_chart_spec", result["render_plan"]["warnings"])
        self.assertTrue(result["snapshot_dispatch"]["orchestration"]["model_provider_called"])
        self.assertTrue(result["snapshot_dispatch"]["orchestration"]["model_provider_plan_bookkeeping_written"])
        self.assertTrue(result["snapshot_dispatch"]["orchestration"]["render_plan_bookkeeping_written"])
        self.assertTrue(all(item["accepted"] for item in result["provider_plan_validation"]), result)
        self.assertTrue(all(item["accepted"] for item in result["planner_result_validation"]), result)
        self.assertTrue(all(item["accepted"] for item in result["chart_spec_validation"]), result)
        self.assertTrue(all(item["accepted"] for item in result["render_plan_validation"]), result)

    def test_repeated_snapshot_requests_reuse_provider_plan(self):
        result = verify_repeated_snapshot_requests_reuse_provider_plan(REPO_ROOT)

        self.assertTrue(result["first"]["accepted"], result)
        self.assertTrue(result["second"]["accepted"], result)
        self.assertEqual(result["planner_call_count"], 1)
        self.assertTrue(result["same_snapshot_returned"], result)
        self.assertTrue(result["same_provider_plan_returned"], result)
        self.assertTrue(result["same_render_plan_returned"], result)
        self.assertEqual(result["provider_plan_count"], 1)
        self.assertEqual(result["render_plan_count"], 1)
        self.assertEqual(result["artifact_count"], 1)
        self.assertEqual(result["complete_snapshot_count"], 1)

    def test_hidden_provider_entity_rejected_before_storage(self):
        result = verify_hidden_provider_entity_rejected_before_storage(REPO_ROOT)

        self.assert_card_facing_model_provider_failure(
            result["snapshot"],
            "model_provider_referenced_unapproved_entity",
        )
        self.assertEqual(result["planner_call_count"], 1)
        self.assertEqual(result["error_codes"], ["model_provider_referenced_unapproved_entity"])
        self.assertEqual(result["provider_plans"], [])
        self.assertEqual(result["render_plans"], [])
        self.assertEqual(result["artifacts"], [])
        self.assertEqual(result["complete_snapshots"], [])
        self.assertTrue(result["snapshot"]["orchestration"]["model_provider_called"])
        self.assertFalse(result["snapshot"]["orchestration"]["model_provider_plan_bookkeeping_written"])
        self.assertFalse(result["snapshot"]["orchestration"]["render_plan_bookkeeping_written"])
        self.assertFalse(result["snapshot"]["orchestration"]["artifact_metadata_bookkeeping_written"])

    def test_hidden_provider_output_rejected_recursively(self):
        result = verify_hidden_provider_output_rejected_recursively(REPO_ROOT)

        self.assertEqual(set(result["cases"]), {"x_axis", "y_axis", "notes", "reasoning_summary", "memory_proposals"})
        for case in result["cases"].values():
            self.assert_card_facing_model_provider_failure(
                case["snapshot"],
                "model_provider_referenced_unapproved_entity",
            )
            self.assertEqual(case["planner_call_count"], 1, case)
            self.assertEqual(case["error_codes"], ["model_provider_referenced_unapproved_entity"], case)
            self.assertEqual(case["provider_plans"], [], case)
            self.assertEqual(case["render_plans"], [], case)
            self.assertEqual(case["artifacts"], [], case)
            self.assertEqual(case["complete_snapshots"], [], case)

    def test_invalid_provider_chart_spec_rejected_before_storage(self):
        result = verify_invalid_provider_chart_spec_rejected_before_storage(REPO_ROOT)

        self.assert_card_facing_model_provider_failure(
            result["snapshot"],
            "invalid_model_provider_chart_spec",
        )
        self.assertEqual(result["planner_call_count"], 1)
        self.assertEqual(result["error_codes"], ["invalid_model_provider_chart_spec"])
        self.assertEqual(result["provider_plans"], [])
        self.assertEqual(result["render_plans"], [])
        self.assertEqual(result["artifacts"], [])
        self.assertEqual(result["complete_snapshots"], [])

    def test_unknown_job_rejected_before_provider_call(self):
        result = verify_unknown_model_provider_job_rejected_before_call(REPO_ROOT)

        self.assertFalse(result["snapshot"]["accepted"], result)
        self.assertEqual(result["planner_call_count"], 0)
        self.assertEqual(result["error_codes"], ["unknown_job"])
        self.assertEqual(result["provider_plans"], [])
        self.assertEqual(result["render_plans"], [])
        self.assertEqual(result["artifacts"], [])

    def test_cross_config_entry_rejected_before_provider_call(self):
        result = verify_cross_config_entry_model_provider_rejected_before_call(REPO_ROOT)

        self.assertFalse(result["cross_snapshot"]["accepted"], result)
        self.assertEqual(result["entry_a_planner_call_count"], 0)
        self.assertEqual(result["entry_b_planner_call_count"], 0)
        self.assertEqual(result["error_codes"], ["unknown_job"])
        self.assertEqual(result["entry_b_provider_plans"], [])
        self.assertEqual(result["entry_b_render_plans"], [])
        self.assertEqual(result["entry_b_artifacts"], [])
        self.assertEqual(result["entry_b_complete_snapshots"], [])

    def test_model_provider_plans_stay_config_entry_scoped(self):
        result = verify_model_provider_plans_stay_config_entry_scoped(REPO_ROOT)

        self.assertTrue(result["entry_a"]["snapshot"]["accepted"], result)
        self.assertTrue(result["entry_b"]["snapshot"]["accepted"], result)
        self.assertEqual(result["entry_a"]["planner_call_count"], 1)
        self.assertEqual(result["entry_b"]["planner_call_count"], 1)
        self.assertEqual(result["entry_a"]["provider_plans"][0]["job_id"], "provider-isolation-entry-a-job-001")
        self.assertEqual(result["entry_b"]["provider_plans"][0]["job_id"], "provider-isolation-entry-b-job-001")
        self.assertEqual(
            result["entry_a"]["render_plans"][0]["chart_spec"]["series"][0]["source"]["entity_id"],
            "sensor.upstairs_temperature",
        )
        self.assertEqual(
            result["entry_b"]["render_plans"][0]["chart_spec"]["series"][0]["source"]["entity_id"],
            "binary_sensor.office_window",
        )

    def test_model_provider_schema_validation(self):
        result = verify_model_provider_schema_validation(REPO_ROOT)

        self.assertTrue(result["accepted"]["provider_plan_valid"], result)
        self.assertTrue(result["accepted"]["planner_result_valid"], result)
        self.assertTrue(result["accepted"]["chart_spec_valid"], result)
        self.assertTrue(result["accepted"]["render_plan_valid"], result)
        self.assertTrue(result["idempotent"]["provider_plan_valid"], result)
        self.assertTrue(result["isolation_entry_a"]["provider_plan_valid"], result)
        self.assertTrue(result["isolation_entry_b"]["provider_plan_valid"], result)

    def test_model_provider_plan_side_effect_boundaries(self):
        result = verify_model_provider_plan_side_effect_boundaries()

        self.assertTrue(result["allowed_aggregate"]["model_provider_called"])
        self.assertTrue(result["allowed_aggregate"]["model_provider_plan_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["render_plan_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["artifact_metadata_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["job_state_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["job_orchestration_scaffold_written"])
        self.assertTrue(result["allowed_aggregate"]["websocket_command_registered"])
        self.assertFalse(result["forbidden_aggregate"]["worker_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_history_read"])
        self.assertFalse(result["forbidden_aggregate"]["semantic_memory_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_service_or_state_mutation_called"])
        self.assertFalse(result["forbidden_aggregate"]["token_generated"])
        self.assertFalse(result["forbidden_aggregate"]["chart_artifact_written"])
        self.assertFalse(result["forbidden_aggregate"]["chart_rendering_called"])
        self.assertFalse(result["forbidden_aggregate"]["durable_storage_written"])
        self.assertFalse(result["forbidden_aggregate"]["retry_behavior_called"])
        self.assertFalse(result["forbidden_aggregate"]["subscription_progress_streaming_called"])
        self.assertFalse(result["forbidden_aggregate"]["job_orchestration_called"])

    def test_model_provider_planning_anchor_verification_passes(self):
        result = verify_job_orchestration_model_provider_planning_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
