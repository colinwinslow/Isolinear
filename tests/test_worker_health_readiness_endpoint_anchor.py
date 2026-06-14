import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.worker_token_provisioning_readiness_anchor import WORKER_READINESS_TEST_TOKEN  # noqa: E402
from Isolinear.worker_health_readiness_endpoint_anchor import (  # noqa: E402
    verify_malformed_worker_health_response_rejected_before_storage,
    verify_no_token_worker_health_rejected_before_call,
    verify_not_ready_worker_health_response_records_internal_state,
    verify_ready_worker_health_probe_records_redacted_metadata,
    verify_unknown_worker_health_config_entry_rejected_before_call,
    verify_worker_health_details_do_not_leak_to_card,
    verify_worker_health_readiness_endpoint_anchor,
    verify_worker_health_side_effect_boundaries,
    verify_worker_health_stays_config_entry_scoped,
    verify_worker_health_transport_failure_records_unavailable,
)


class WorkerHealthReadinessEndpointAnchorTests(unittest.TestCase):
    def test_ready_worker_health_probe_records_redacted_metadata(self):
        result = verify_ready_worker_health_probe_records_redacted_metadata(REPO_ROOT)

        self.assertTrue(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "worker_health_ready")
        self.assertEqual(result["health"]["status"], "ready")
        self.assertEqual(result["health"]["type"], "isolinear_worker_health")
        self.assertTrue(result["health_validation"]["accepted"], result)
        self.assertTrue(result["request_validation"]["accepted"], result)
        self.assertEqual(result["health_call_count"], 1)
        self.assertEqual(result["render_call_count"], 0)
        self.assertEqual(result["stored_authorization"], "Bearer <redacted>")
        self.assertTrue(result["raw_request_authorization_present"])
        self.assertTrue(result["raw_request_uses_worker_token"])
        self.assertNotIn(WORKER_READINESS_TEST_TOKEN, str(result["health"]))
        self.assertNotIn(WORKER_READINESS_TEST_TOKEN, str(result["result"]))

    def test_not_ready_worker_health_response_records_internal_state(self):
        result = verify_not_ready_worker_health_response_records_internal_state(REPO_ROOT)

        self.assertTrue(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "worker_health_not_ready")
        self.assertEqual(result["health"]["status"], "not_ready")
        self.assertTrue(result["health_validation"]["accepted"], result)
        self.assertTrue(result["renderer_client_unchanged"])
        self.assertTrue(result["renderer_client_present"])
        self.assertEqual(result["health_call_count"], 1)
        self.assertEqual(result["render_call_count"], 0)

    def test_transport_failure_records_unavailable_health(self):
        result = verify_worker_health_transport_failure_records_unavailable(REPO_ROOT)

        self.assertTrue(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "worker_connection_error")
        self.assertEqual(result["health"]["status"], "unavailable")
        self.assertFalse(result["health"]["response"]["accepted"])
        self.assertTrue(result["health_validation"]["accepted"], result)
        self.assertEqual(result["health_call_count"], 1)
        self.assertEqual(result["render_call_count"], 0)
        self.assertFalse(any(result["retry_or_scheduler_side_effects"].values()))

    def test_malformed_accepted_response_fails_before_storage(self):
        result = verify_malformed_worker_health_response_rejected_before_storage(REPO_ROOT)

        self.assertFalse(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "invalid_worker_health_response")
        self.assertEqual(result["health_call_count"], 1)
        self.assertEqual(result["render_call_count"], 0)
        self.assertFalse(result["health_written"])

    def test_no_token_entry_rejected_before_worker_call(self):
        result = verify_no_token_worker_health_rejected_before_call()

        self.assertFalse(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "worker_health_not_ready")
        self.assertFalse(result["health_written"])
        self.assertFalse(result["worker_client_present"])
        self.assertFalse(result["result"]["orchestration"]["worker_health_check_called"])

    def test_unknown_config_entry_rejected_before_worker_call(self):
        result = verify_unknown_worker_health_config_entry_rejected_before_call()

        self.assertFalse(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "unknown_config_entry")
        self.assertFalse(result["entry_created"])
        self.assertFalse(result["health_written"])
        self.assertFalse(result["result"]["orchestration"]["worker_health_check_called"])

    def test_worker_health_stays_config_entry_scoped(self):
        result = verify_worker_health_stays_config_entry_scoped(REPO_ROOT)

        self.assertTrue(result["entry_a"]["result"]["accepted"], result)
        self.assertTrue(result["entry_b"]["result"]["accepted"], result)
        self.assertEqual(result["entry_a"]["health"]["config_entry_id"], "worker-health-isolation-entry-a")
        self.assertEqual(result["entry_b"]["health"]["config_entry_id"], "worker-health-isolation-entry-b")
        self.assertEqual(result["entry_a"]["health"]["status"], "ready")
        self.assertEqual(result["entry_b"]["health"]["status"], "not_ready")
        self.assertEqual(result["entry_a"]["health_call_count"], 1)
        self.assertEqual(result["entry_b"]["health_call_count"], 1)
        self.assertTrue(result["entry_a"]["raw_request_authorization_present"])
        self.assertTrue(result["entry_b"]["raw_request_authorization_present"])
        self.assertTrue(result["entry_a"]["raw_request_uses_own_token"])
        self.assertTrue(result["entry_b"]["raw_request_uses_own_token"])
        self.assertTrue(result["entry_a"]["other_token_absent_from_request"])
        self.assertTrue(result["entry_b"]["other_token_absent_from_request"])
        self.assertTrue(result["entry_a"]["health_validation"]["accepted"], result)
        self.assertTrue(result["entry_b"]["health_validation"]["accepted"], result)

    def test_worker_health_details_do_not_leak_to_card(self):
        result = verify_worker_health_details_do_not_leak_to_card(REPO_ROOT)

        self.assertTrue(result["health_validation"]["accepted"], result)
        self.assertEqual(result["stored_authorization"], "Bearer <redacted>")
        self.assertTrue(result["raw_worker_authorization_received"])
        self.assertTrue(result["token_absent_from_health"])
        self.assertTrue(result["token_absent_from_setup"])
        self.assertTrue(result["token_absent_from_evidence_payload"])
        self.assertTrue(result["token_absent_from_dashboard_card_metadata"])
        self.assertTrue(result["token_absent_from_model_provider_metadata"])
        self.assertTrue(result["endpoint_absent_from_dashboard_payload"])
        self.assertTrue(result["request_absent_from_dashboard_payload"])
        self.assertTrue(result["health_absent_from_dashboard_payload"])
        self.assertNotIn(WORKER_READINESS_TEST_TOKEN, result["health_message"])

    def test_worker_health_side_effect_boundaries(self):
        result = verify_worker_health_side_effect_boundaries()

        self.assertTrue(result["allowed_aggregate"]["worker_health_check_called"])
        self.assertTrue(result["allowed_aggregate"]["worker_health_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["worker_health_request_validated"])
        self.assertTrue(result["allowed_aggregate"]["worker_health_response_validated"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_history_read"])
        self.assertFalse(result["forbidden_aggregate"]["semantic_memory_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_service_or_state_mutation_called"])
        self.assertFalse(result["forbidden_aggregate"]["token_generated"])
        self.assertFalse(result["forbidden_aggregate"]["token_rotation_called"])
        self.assertFalse(result["forbidden_aggregate"]["worker_render_called"])
        self.assertFalse(result["forbidden_aggregate"]["chart_rendering_called"])
        self.assertFalse(result["forbidden_aggregate"]["chart_artifact_written"])
        self.assertFalse(result["forbidden_aggregate"]["durable_storage_written"])
        self.assertFalse(result["forbidden_aggregate"]["durable_retry_storage_written"])
        self.assertFalse(result["forbidden_aggregate"]["retry_behavior_called"])
        self.assertFalse(result["forbidden_aggregate"]["scheduler_called"])
        self.assertFalse(result["forbidden_aggregate"]["automatic_retry_called"])
        self.assertFalse(result["forbidden_aggregate"]["automatic_progress_task_called"])
        self.assertFalse(result["forbidden_aggregate"]["new_worker_transport_added"])
        self.assertFalse(result["forbidden_aggregate"]["token_leaked_to_card"])
        self.assertFalse(result["forbidden_aggregate"]["token_leaked_to_model_provider"])

    def test_worker_health_readiness_endpoint_anchor_verification_passes(self):
        result = verify_worker_health_readiness_endpoint_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
