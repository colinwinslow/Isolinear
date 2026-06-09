import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.worker_token_provisioning_readiness_anchor import (  # noqa: E402
    WORKER_READINESS_TEST_TOKEN,
    verify_explicit_token_provisioning_records_ready_state,
    verify_missing_worker_endpoint_reports_disabled,
    verify_no_token_setup_reports_not_ready,
    verify_readiness_and_tokens_stay_config_entry_scoped,
    verify_repeated_provisioning_reuses_token,
    verify_readiness_validation_failure_does_not_store_token,
    verify_unknown_config_entry_rejected_before_token_generation,
    verify_worker_readiness_side_effect_boundaries,
    verify_worker_token_does_not_leak,
    verify_worker_token_provisioning_readiness_anchor,
)


class WorkerTokenProvisioningReadinessAnchorTests(unittest.TestCase):
    def test_explicit_token_provisioning_records_ready_state(self):
        result = verify_explicit_token_provisioning_records_ready_state(REPO_ROOT)

        self.assertTrue(result["initial_setup"]["accepted"], result)
        self.assertEqual(result["initial_readiness"]["status"], "not_ready")
        self.assertTrue(result["provision"]["accepted"], result)
        self.assertEqual(result["provision"]["code"], "worker_token_provisioned")
        self.assertTrue(result["provision"]["enabled"], result)
        self.assertEqual(result["readiness"]["status"], "ready")
        self.assertTrue(result["readiness"]["token"]["present"])
        self.assertEqual(result["readiness"]["token"]["authorization"], "Bearer <redacted>")
        self.assertTrue(result["readiness_validation"]["accepted"], result)
        self.assertTrue(result["renderer_setup"]["enabled"], result)
        self.assertTrue(result["renderer_client_present"], result)
        self.assertEqual(result["raw_token_stored"], True)
        self.assertNotIn(WORKER_READINESS_TEST_TOKEN, str(result["provision"]))
        self.assertNotIn(WORKER_READINESS_TEST_TOKEN, str(result["readiness"]))

    def test_no_token_setup_reports_not_ready(self):
        result = verify_no_token_setup_reports_not_ready(REPO_ROOT)

        self.assertTrue(result["setup"]["accepted"], result)
        self.assertEqual(result["readiness"]["status"], "not_ready")
        self.assertFalse(result["readiness"]["token"]["present"])
        self.assertEqual(result["readiness"]["token"]["authorization"], "<missing>")
        self.assertTrue(result["readiness_validation"]["accepted"], result)
        self.assertFalse(result["renderer_setup"]["enabled"])
        self.assertFalse(result["renderer_client_present"])

    def test_missing_worker_endpoint_reports_disabled(self):
        result = verify_missing_worker_endpoint_reports_disabled(REPO_ROOT)

        self.assertTrue(result["setup"]["accepted"], result)
        self.assertEqual(result["readiness"]["status"], "disabled")
        self.assertFalse(result["readiness"]["worker"]["endpoint_configured"])
        self.assertFalse(result["readiness"]["token"]["present"])
        self.assertTrue(result["readiness_validation"]["accepted"], result)
        self.assertFalse(result["renderer_setup"]["enabled"])
        self.assertFalse(result["renderer_client_present"])

    def test_repeated_provisioning_reuses_token(self):
        result = verify_repeated_provisioning_reuses_token(REPO_ROOT)

        self.assertTrue(result["first"]["accepted"], result)
        self.assertTrue(result["second"]["accepted"], result)
        self.assertEqual(result["first"]["code"], "worker_token_provisioned")
        self.assertEqual(result["second"]["code"], "worker_token_already_present")
        self.assertEqual(result["token_factory_call_count"], 1)
        self.assertEqual(result["stored_token_unchanged"], True)
        self.assertEqual(result["second_readiness"]["status"], "ready")
        self.assertTrue(result["second_readiness_validation"]["accepted"], result)

    def test_unknown_config_entry_rejected_before_token_generation(self):
        result = verify_unknown_config_entry_rejected_before_token_generation()

        self.assertFalse(result["provision"]["accepted"], result)
        self.assertEqual(result["provision"]["code"], "unknown_config_entry")
        self.assertEqual(result["token_factory_call_count"], 0)
        self.assertFalse(result["entry_created"])
        self.assertFalse(result["readiness_written"])
        self.assertFalse(result["provision"]["orchestration"]["token_generated"])
        self.assertFalse(result["provision"]["orchestration"]["readiness_bookkeeping_written"])

    def test_readiness_validation_failure_does_not_store_token(self):
        result = verify_readiness_validation_failure_does_not_store_token(REPO_ROOT)

        self.assertFalse(result["provision"]["accepted"], result)
        self.assertEqual(result["provision"]["code"], "invalid_integration_worker_readiness")
        self.assertEqual(result["token_factory_call_count"], 1)
        self.assertFalse(result["token_present_after_failure"])
        self.assertFalse(result["readiness_written_after_failure"])
        self.assertEqual(result["stored_readiness"]["status"], "not_ready")
        self.assertTrue(result["provision"]["orchestration"]["token_generated"])
        self.assertFalse(result["provision"]["orchestration"]["token_stored"])
        self.assertFalse(result["provision"]["orchestration"]["readiness_bookkeeping_written"])

    def test_readiness_and_tokens_stay_config_entry_scoped(self):
        result = verify_readiness_and_tokens_stay_config_entry_scoped(REPO_ROOT)

        self.assertTrue(result["entry_a"]["provision"]["accepted"], result)
        self.assertEqual(result["entry_a"]["readiness"]["status"], "ready")
        self.assertEqual(result["entry_b"]["readiness"]["status"], "not_ready")
        self.assertTrue(result["entry_a"]["renderer_setup"]["enabled"])
        self.assertFalse(result["entry_b"]["renderer_setup"]["enabled"])
        self.assertTrue(result["entry_a"]["token_present"])
        self.assertFalse(result["entry_b"]["token_present"])
        self.assertEqual(result["entry_a"]["readiness"]["config_entry_id"], "worker-ready-entry-a")
        self.assertEqual(result["entry_b"]["readiness"]["config_entry_id"], "worker-ready-entry-b")
        self.assertTrue(result["entry_a"]["readiness_validation"]["accepted"], result)
        self.assertTrue(result["entry_b"]["readiness_validation"]["accepted"], result)

    def test_worker_token_does_not_leak(self):
        result = verify_worker_token_does_not_leak(REPO_ROOT)

        self.assertTrue(result["token_absent_from_readiness"])
        self.assertTrue(result["token_absent_from_setup"])
        self.assertTrue(result["token_absent_from_dashboard_card_metadata"])
        self.assertTrue(result["token_absent_from_model_provider_metadata"])
        self.assertTrue(result["token_absent_from_evidence_payload"])
        self.assertEqual(result["stored_authorization"], "Bearer <redacted>")

    def test_worker_readiness_side_effect_boundaries(self):
        result = verify_worker_readiness_side_effect_boundaries()

        self.assertTrue(result["allowed_aggregate"]["token_generated"])
        self.assertTrue(result["allowed_aggregate"]["token_stored"])
        self.assertTrue(result["allowed_aggregate"]["readiness_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["worker_renderer_setup_gated"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_history_read"])
        self.assertFalse(result["forbidden_aggregate"]["semantic_memory_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_service_or_state_mutation_called"])
        self.assertFalse(result["forbidden_aggregate"]["worker_called"])
        self.assertFalse(result["forbidden_aggregate"]["chart_rendering_called"])
        self.assertFalse(result["forbidden_aggregate"]["chart_artifact_written"])
        self.assertFalse(result["forbidden_aggregate"]["durable_token_storage_written"])
        self.assertFalse(result["forbidden_aggregate"]["token_rotation_called"])
        self.assertFalse(result["forbidden_aggregate"]["worker_health_check_called"])
        self.assertFalse(result["forbidden_aggregate"]["retry_behavior_called"])
        self.assertFalse(result["forbidden_aggregate"]["automatic_progress_task_called"])
        self.assertFalse(result["forbidden_aggregate"]["worker_streaming_called"])

    def test_worker_token_provisioning_readiness_anchor_verification_passes(self):
        result = verify_worker_token_provisioning_readiness_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
