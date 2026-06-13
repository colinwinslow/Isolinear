import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.worker_token_lifecycle_anchor import (  # noqa: E402
    WORKER_LIFECYCLE_PERSISTED_TOKEN,
    WORKER_LIFECYCLE_REPAIRED_TOKEN,
    WORKER_LIFECYCLE_ROTATED_TOKEN,
    verify_durable_explicit_operations_persist_private_tokens,
    verify_invalid_persisted_entries_skipped_before_restore,
    verify_lifecycle_validation_failure_rolls_back,
    verify_missing_persisted_token_records_repair_issue,
    verify_missing_worker_endpoint_records_disabled_lifecycle,
    verify_setup_restores_persisted_token_before_readiness,
    verify_setup_lifecycle_storage_failure_blocks_restore,
    verify_worker_token_lifecycle_anchor,
    verify_worker_token_lifecycle_details_do_not_leak,
    verify_worker_token_lifecycle_side_effect_boundaries,
    verify_worker_token_lifecycle_stays_config_entry_scoped,
)


class WorkerTokenLifecycleAnchorTests(unittest.TestCase):
    def test_setup_restores_persisted_token_before_readiness(self):
        result = verify_setup_restores_persisted_token_before_readiness(REPO_ROOT)

        self.assertEqual(result["lifecycle"]["status"], "ready")
        self.assertEqual(result["lifecycle"]["code"], "worker_token_restored_from_storage")
        self.assertTrue(result["lifecycle_validation"]["accepted"], result)
        self.assertTrue(result["stored_token_restored_to_memory"], result)
        self.assertEqual(result["readiness_status"], "ready")
        self.assertTrue(result["renderer_setup"]["enabled"], result)
        self.assertTrue(result["renderer_client_uses_restored_token"], result)
        self.assertTrue(result["private_store_has_token"], result)
        self.assertFalse(result["lifecycle"]["orchestration"]["setup_time_token_generation_called"])
        self.assertFalse(result["lifecycle"]["orchestration"]["worker_render_called"])
        self.assertFalse(result["lifecycle"]["orchestration"]["worker_health_call"])
        self.assertNotIn(WORKER_LIFECYCLE_PERSISTED_TOKEN, str(result["lifecycle"]))

    def test_missing_persisted_token_records_repair_issue(self):
        result = verify_missing_persisted_token_records_repair_issue(REPO_ROOT)

        self.assertEqual(result["lifecycle"]["status"], "not_ready")
        self.assertEqual(result["lifecycle"]["code"], "worker_token_repair_issue_created")
        self.assertTrue(result["lifecycle_validation"]["accepted"], result)
        self.assertTrue(result["repair_issue"]["present"])
        self.assertEqual(result["repair_issue"]["surface"], "home_assistant_repairs_scaffold")
        self.assertEqual(result["repair_issue"]["suggested_action"], "manual_token_repair")
        self.assertFalse(result["token_present"])
        self.assertFalse(result["lifecycle"]["orchestration"]["token_generated"])

    def test_missing_worker_endpoint_records_disabled_lifecycle(self):
        result = verify_missing_worker_endpoint_records_disabled_lifecycle(REPO_ROOT)

        self.assertEqual(result["lifecycle"]["status"], "disabled")
        self.assertEqual(result["lifecycle"]["code"], "worker_endpoint_missing")
        self.assertTrue(result["lifecycle_validation"]["accepted"], result)
        self.assertFalse(result["repair_issue"]["present"])
        self.assertFalse(result["token_present"])

    def test_durable_explicit_operations_persist_private_tokens(self):
        result = verify_durable_explicit_operations_persist_private_tokens(REPO_ROOT)

        self.assertTrue(result["provision"]["accepted"], result)
        self.assertTrue(result["rotation"]["accepted"], result)
        self.assertTrue(result["repair"]["accepted"], result)
        self.assertTrue(result["private_provision_token_persisted"], result)
        self.assertTrue(result["private_repair_token_persisted"], result)
        self.assertTrue(result["rotation_replaced_private_token"], result)
        self.assertTrue(result["repair_issue_cleared_after_success"], result)
        self.assertTrue(result["provision_lifecycle_validation"]["accepted"], result)
        self.assertTrue(result["repair_lifecycle_validation"]["accepted"], result)
        self.assertNotIn(WORKER_LIFECYCLE_ROTATED_TOKEN, str(result["provision_lifecycle"]))
        self.assertNotIn(WORKER_LIFECYCLE_REPAIRED_TOKEN, str(result["repair_lifecycle"]))

    def test_invalid_persisted_entries_skipped_before_restore(self):
        result = verify_invalid_persisted_entries_skipped_before_restore(REPO_ROOT)

        self.assertFalse(result["token_restored"], result)
        self.assertEqual(result["readiness"]["status"], "not_ready")
        self.assertTrue(result["repair_issue"]["present"])
        self.assertTrue(result["lifecycle_validation"]["accepted"], result)

    def test_setup_lifecycle_storage_failure_blocks_restore(self):
        result = verify_setup_lifecycle_storage_failure_blocks_restore()

        self.assertFalse(result["setup_accepted"], result)
        self.assertFalse(result["lifecycle_setup"]["accepted"], result)
        self.assertEqual(result["lifecycle_setup"]["code"], "invalid_integration_worker_token_lifecycle")
        self.assertFalse(result["token_restored"])
        self.assertFalse(result["readiness_written"])
        self.assertFalse(result["renderer_setup_written"])
        self.assertTrue(result["private_token_retained"])

    def test_lifecycle_validation_failure_rolls_back(self):
        result = verify_lifecycle_validation_failure_rolls_back(REPO_ROOT)

        self.assertFalse(result["rotation"]["accepted"], result)
        self.assertEqual(result["rotation"]["code"], "invalid_integration_worker_token_lifecycle")
        self.assertEqual(result["token_factory_call_count"], 1)
        self.assertTrue(result["private_token_restored"])
        self.assertTrue(result["rotated_token_absent_from_private_store"])
        self.assertTrue(result["in_memory_token_restored"])
        self.assertTrue(result["old_renderer_client_restored"])
        self.assertEqual(result["lifecycle_after_failure"], result["lifecycle_before_failure"])
        self.assertEqual(result["readiness_after_failure"], result["readiness_before_failure"])
        self.assertEqual(result["renderer_setup_after_failure"], result["renderer_setup_before_failure"])

    def test_worker_token_lifecycle_stays_config_entry_scoped(self):
        result = verify_worker_token_lifecycle_stays_config_entry_scoped(REPO_ROOT)

        self.assertTrue(result["entry_a"]["private_token"], result)
        self.assertTrue(result["entry_a"]["renderer_client_uses_own_token"], result)
        self.assertEqual(result["entry_b"]["lifecycle"], result["entry_b_before"]["lifecycle"])
        self.assertEqual(result["entry_b"]["readiness"], result["entry_b_before"]["readiness"])
        self.assertFalse(result["entry_b"]["token_present"])
        self.assertIsNone(result["entry_b"]["private_token"])

    def test_worker_token_lifecycle_details_do_not_leak(self):
        result = verify_worker_token_lifecycle_details_do_not_leak(REPO_ROOT)

        self.assertTrue(result["tokens_absent_from_lifecycle_state"])
        self.assertTrue(result["tokens_absent_from_setup_results"])
        self.assertTrue(result["tokens_absent_from_repair_issue_metadata"])
        self.assertTrue(result["tokens_absent_from_dashboard_card_metadata"])
        self.assertTrue(result["tokens_absent_from_model_provider_metadata"])
        self.assertTrue(result["tokens_absent_from_evidence_payload"])
        self.assertTrue(result["lifecycle_absent_from_dashboard_payload"])
        self.assertTrue(result["repair_issue_absent_from_dashboard_payload"])
        self.assertTrue(result["endpoint_absent_from_dashboard_payload"])

    def test_worker_token_lifecycle_side_effect_boundaries(self):
        result = verify_worker_token_lifecycle_side_effect_boundaries()

        self.assertTrue(result["allowed_aggregate"]["durable_token_storage_loaded"])
        self.assertTrue(result["allowed_aggregate"]["durable_token_storage_written"])
        self.assertTrue(result["allowed_aggregate"]["in_memory_token_restored"])
        self.assertTrue(result["allowed_aggregate"]["automatic_token_restore_called"])
        self.assertTrue(result["allowed_aggregate"]["repair_issue_created"])
        self.assertTrue(result["allowed_aggregate"]["repair_issue_deleted"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_history_read"])
        self.assertFalse(result["forbidden_aggregate"]["semantic_memory_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_service_or_state_mutation_called"])
        self.assertFalse(result["forbidden_aggregate"]["config_entry_options_written"])
        self.assertFalse(result["forbidden_aggregate"]["recorder_called"])
        self.assertFalse(result["forbidden_aggregate"]["worker_render_called"])
        self.assertFalse(result["forbidden_aggregate"]["worker_health_call"])
        self.assertFalse(result["forbidden_aggregate"]["model_provider_called"])
        self.assertFalse(result["forbidden_aggregate"]["chart_rendering_called"])
        self.assertFalse(result["forbidden_aggregate"]["chart_artifact_written"])
        self.assertFalse(result["forbidden_aggregate"]["durable_retry_storage_written"])
        self.assertFalse(result["forbidden_aggregate"]["external_queue_or_database_called"])
        self.assertFalse(result["forbidden_aggregate"]["scheduler_called"])
        self.assertFalse(result["forbidden_aggregate"]["automatic_rotation_called"])
        self.assertFalse(result["forbidden_aggregate"]["automatic_token_repair_execution_called"])
        self.assertFalse(result["forbidden_aggregate"]["setup_time_token_generation_called"])
        self.assertFalse(result["forbidden_aggregate"]["dashboard_command_registered"])

    def test_worker_token_lifecycle_anchor_verification_passes(self):
        result = verify_worker_token_lifecycle_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
