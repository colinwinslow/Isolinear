import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.worker_token_provisioning_readiness_anchor import (  # noqa: E402
    WORKER_READINESS_SECOND_TOKEN,
    WORKER_READINESS_TEST_TOKEN,
)
from Isolinear.worker_token_rotation_repair_anchor import (  # noqa: E402
    WORKER_REPAIRED_TOKEN,
    WORKER_ROTATED_TOKEN,
    verify_cross_entry_worker_token_request_rejected_before_side_effects,
    verify_missing_token_repair_records_ready_state,
    verify_readiness_validation_failure_rolls_back_rotation,
    verify_rotation_invalidates_old_token_and_refreshes_readiness,
    verify_rotated_and_repaired_tokens_do_not_leak,
    verify_unknown_worker_token_rotation_repair_rejected_before_side_effects,
    verify_worker_token_rotation_repair_anchor,
    verify_worker_token_rotation_repair_side_effect_boundaries,
)


class WorkerTokenRotationRepairAnchorTests(unittest.TestCase):
    def test_rotation_invalidates_old_token_and_refreshes_readiness(self):
        result = verify_rotation_invalidates_old_token_and_refreshes_readiness(REPO_ROOT)

        self.assertTrue(result["initial_provision"]["accepted"], result)
        self.assertTrue(result["initial_renderer_setup"]["enabled"], result)
        self.assertTrue(result["rotation"]["accepted"], result)
        self.assertEqual(result["rotation"]["code"], "worker_token_rotated")
        self.assertEqual(result["readiness"]["status"], "ready")
        self.assertEqual(result["readiness"]["code"], "worker_token_rotated")
        self.assertEqual(result["readiness"]["token"]["authorization"], "Bearer <redacted>")
        self.assertTrue(result["readiness_validation"]["accepted"], result)
        self.assertTrue(result["rotation"]["old_token_invalidated"])
        self.assertTrue(result["renderer_client_refreshed"])
        self.assertTrue(result["renderer_setup"]["enabled"], result)
        self.assertEqual(result["stored_token_is_new"], True)
        self.assertEqual(result["renderer_client_uses_new_token"], True)
        self.assertNotIn(WORKER_READINESS_TEST_TOKEN, str(result["rotation"]))
        self.assertNotIn(WORKER_ROTATED_TOKEN, str(result["rotation"]))
        self.assertNotIn(WORKER_ROTATED_TOKEN, str(result["readiness"]))

    def test_missing_token_repair_records_ready_state(self):
        result = verify_missing_token_repair_records_ready_state(REPO_ROOT)

        self.assertEqual(result["initial_readiness"]["status"], "not_ready")
        self.assertTrue(result["repair"]["accepted"], result)
        self.assertEqual(result["repair"]["code"], "worker_token_repaired")
        self.assertEqual(result["readiness"]["status"], "ready")
        self.assertTrue(result["readiness_validation"]["accepted"], result)
        self.assertTrue(result["renderer_setup"]["enabled"], result)
        self.assertEqual(result["stored_token_is_repaired"], True)
        self.assertEqual(result["renderer_client_uses_repaired_token"], True)
        self.assertNotIn(WORKER_REPAIRED_TOKEN, str(result["repair"]))

    def test_readiness_validation_failure_rolls_back_rotation(self):
        result = verify_readiness_validation_failure_rolls_back_rotation(REPO_ROOT)

        self.assertFalse(result["rotation"]["accepted"], result)
        self.assertEqual(result["rotation"]["code"], "invalid_integration_worker_readiness")
        self.assertEqual(result["token_factory_call_count"], 1)
        self.assertTrue(result["stored_token_restored"])
        self.assertTrue(result["rotated_token_absent_after_failure"])
        self.assertTrue(result["old_renderer_client_restored"])
        self.assertEqual(result["stored_readiness_after_failure"], result["stored_readiness_before_failure"])
        self.assertEqual(result["stored_renderer_setup_after_failure"], result["stored_renderer_setup_before_failure"])
        self.assertNotIn(WORKER_ROTATED_TOKEN, str(result["rotation"]))

    def test_unknown_config_entry_rejected_before_side_effects(self):
        result = verify_unknown_worker_token_rotation_repair_rejected_before_side_effects()

        self.assertFalse(result["rotation"]["accepted"], result)
        self.assertFalse(result["repair"]["accepted"], result)
        self.assertEqual(result["rotation"]["code"], "unknown_config_entry")
        self.assertEqual(result["repair"]["code"], "unknown_config_entry")
        self.assertEqual(result["rotation_token_factory_call_count"], 0)
        self.assertEqual(result["repair_token_factory_call_count"], 0)
        self.assertFalse(result["entry_created"])
        self.assertFalse(result["readiness_written"])

    def test_cross_entry_request_rejected_before_side_effects(self):
        result = verify_cross_entry_worker_token_request_rejected_before_side_effects()

        self.assertFalse(result["rotation"]["accepted"], result)
        self.assertEqual(result["rotation"]["code"], "cross_config_entry_worker_token_request")
        self.assertEqual(result["token_factory_call_count"], 0)
        self.assertTrue(result["entry_a_token_unchanged"])
        self.assertTrue(result["entry_b_token_unchanged"])
        self.assertEqual(result["entry_a_readiness"], result["entry_a_readiness_before"])
        self.assertEqual(result["entry_b_readiness"], result["entry_b_readiness_before"])

    def test_rotated_and_repaired_tokens_do_not_leak(self):
        result = verify_rotated_and_repaired_tokens_do_not_leak(REPO_ROOT)

        self.assertTrue(result["rotation_readiness_validation"]["accepted"], result)
        self.assertTrue(result["repair_readiness_validation"]["accepted"], result)
        self.assertEqual(result["rotation_authorization"], "Bearer <redacted>")
        self.assertEqual(result["repair_authorization"], "Bearer <redacted>")
        self.assertTrue(result["tokens_absent_from_readiness"])
        self.assertTrue(result["tokens_absent_from_setup"])
        self.assertTrue(result["tokens_absent_from_dashboard_card_metadata"])
        self.assertTrue(result["tokens_absent_from_model_provider_metadata"])
        self.assertTrue(result["tokens_absent_from_evidence_payload"])
        self.assertTrue(result["rotation_internals_absent_from_dashboard_payload"])
        self.assertTrue(result["repair_internals_absent_from_dashboard_payload"])

    def test_worker_token_rotation_repair_side_effect_boundaries(self):
        result = verify_worker_token_rotation_repair_side_effect_boundaries()

        self.assertTrue(result["allowed_aggregate"]["token_generated"])
        self.assertTrue(result["allowed_aggregate"]["token_stored"])
        self.assertTrue(result["allowed_aggregate"]["token_rotation_called"])
        self.assertTrue(result["allowed_aggregate"]["readiness_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["worker_renderer_setup_gated"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_history_read"])
        self.assertFalse(result["forbidden_aggregate"]["semantic_memory_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_service_or_state_mutation_called"])
        self.assertFalse(result["forbidden_aggregate"]["worker_called"])
        self.assertFalse(result["forbidden_aggregate"]["worker_health_check_called"])
        self.assertFalse(result["forbidden_aggregate"]["chart_rendering_called"])
        self.assertFalse(result["forbidden_aggregate"]["chart_artifact_written"])
        self.assertFalse(result["forbidden_aggregate"]["durable_token_storage_written"])
        self.assertFalse(result["forbidden_aggregate"]["retry_behavior_called"])
        self.assertFalse(result["forbidden_aggregate"]["automatic_progress_task_called"])
        self.assertFalse(result["forbidden_aggregate"]["worker_streaming_called"])

    def test_worker_token_rotation_repair_anchor_verification_passes(self):
        result = verify_worker_token_rotation_repair_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
