import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.model_provider_health_diagnostics_anchor import (  # noqa: E402
    PROVIDER_ENDPOINT_A,
    verify_malformed_model_provider_health_response_rejected_before_storage,
    verify_model_provider_health_details_do_not_leak_to_card,
    verify_model_provider_health_diagnostics_anchor,
    verify_model_provider_health_side_effect_boundaries,
    verify_model_provider_health_stays_config_entry_scoped,
    verify_model_provider_transport_failure_records_unavailable,
    verify_not_ready_model_provider_health_response_records_internal_state,
    verify_ready_model_provider_health_probe_records_metadata,
    verify_secret_model_provider_health_response_rejected_before_storage,
    verify_unconfigured_model_provider_health_rejected_before_call,
    verify_unknown_model_provider_health_config_entry_rejected_before_call,
)


class ModelProviderHealthDiagnosticsAnchorTests(unittest.TestCase):
    def test_ready_provider_health_probe_records_metadata(self):
        result = verify_ready_model_provider_health_probe_records_metadata(REPO_ROOT)

        self.assertTrue(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "model_provider_health_ready")
        self.assertEqual(result["health"]["status"], "ready")
        self.assertEqual(result["health"]["type"], "isolinear_model_provider_health")
        self.assertTrue(result["health_validation"]["accepted"], result)
        self.assertTrue(result["request_validation"]["accepted"], result)
        self.assertEqual(result["health_call_count"], 1)
        self.assertEqual(result["plan_call_count"], 0)
        self.assertEqual(result["stored_provider_endpoint"], PROVIDER_ENDPOINT_A)

    def test_not_ready_provider_health_response_records_internal_state(self):
        result = verify_not_ready_model_provider_health_response_records_internal_state(REPO_ROOT)

        self.assertTrue(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "model_provider_health_not_ready")
        self.assertEqual(result["health"]["status"], "not_ready")
        self.assertTrue(result["health_validation"]["accepted"], result)
        self.assertTrue(result["planner_client_unchanged"])
        self.assertTrue(result["planner_client_present"])
        self.assertEqual(result["health_call_count"], 1)
        self.assertEqual(result["plan_call_count"], 0)

    def test_transport_failure_records_unavailable_health(self):
        result = verify_model_provider_transport_failure_records_unavailable(REPO_ROOT)

        self.assertTrue(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "model_provider_health_connection_error")
        self.assertEqual(result["health"]["status"], "unavailable")
        self.assertFalse(result["health"]["response"]["accepted"])
        self.assertTrue(result["health_validation"]["accepted"], result)
        self.assertEqual(result["health_call_count"], 1)
        self.assertEqual(result["plan_call_count"], 0)
        self.assertFalse(any(result["retry_or_scheduler_side_effects"].values()))

    def test_malformed_accepted_response_fails_before_storage(self):
        result = verify_malformed_model_provider_health_response_rejected_before_storage(REPO_ROOT)

        self.assertFalse(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "invalid_model_provider_health_response")
        self.assertEqual(result["health_call_count"], 1)
        self.assertEqual(result["plan_call_count"], 0)
        self.assertFalse(result["health_written"])

    def test_secret_accepted_response_fails_before_storage(self):
        result = verify_secret_model_provider_health_response_rejected_before_storage(REPO_ROOT)

        self.assertFalse(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "invalid_model_provider_health_response")
        self.assertEqual(result["health_call_count"], 1)
        self.assertEqual(result["plan_call_count"], 0)
        self.assertFalse(result["health_written"])
        self.assertTrue(result["secret_absent_from_result"])

    def test_unconfigured_entry_rejected_before_provider_call(self):
        result = verify_unconfigured_model_provider_health_rejected_before_call()

        self.assertFalse(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "model_provider_health_not_configured")
        self.assertFalse(result["health_written"])
        self.assertFalse(result["planner_client_present"])
        self.assertFalse(result["result"]["orchestration"]["model_provider_health_check_called"])

    def test_unknown_config_entry_rejected_before_provider_call(self):
        result = verify_unknown_model_provider_health_config_entry_rejected_before_call()

        self.assertFalse(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "unknown_config_entry")
        self.assertFalse(result["entry_created"])
        self.assertFalse(result["health_written"])
        self.assertFalse(result["result"]["orchestration"]["model_provider_health_check_called"])

    def test_provider_health_stays_config_entry_scoped(self):
        result = verify_model_provider_health_stays_config_entry_scoped(REPO_ROOT)

        self.assertTrue(result["entry_a"]["result"]["accepted"], result)
        self.assertTrue(result["entry_b"]["result"]["accepted"], result)
        self.assertEqual(result["entry_a"]["health"]["config_entry_id"], "provider-health-isolation-entry-a")
        self.assertEqual(result["entry_b"]["health"]["config_entry_id"], "provider-health-isolation-entry-b")
        self.assertEqual(result["entry_a"]["health"]["status"], "ready")
        self.assertEqual(result["entry_b"]["health"]["status"], "not_ready")
        self.assertEqual(result["entry_a"]["health_call_count"], 1)
        self.assertEqual(result["entry_b"]["health_call_count"], 1)
        self.assertEqual(result["entry_a"]["plan_call_count"], 0)
        self.assertEqual(result["entry_b"]["plan_call_count"], 0)
        self.assertTrue(result["entry_a"]["other_endpoint_absent"])
        self.assertTrue(result["entry_b"]["other_endpoint_absent"])
        self.assertTrue(result["entry_a"]["health_validation"]["accepted"], result)
        self.assertTrue(result["entry_b"]["health_validation"]["accepted"], result)

    def test_provider_health_details_do_not_leak_to_card(self):
        result = verify_model_provider_health_details_do_not_leak_to_card(REPO_ROOT)

        self.assertTrue(result["health_validation"]["accepted"], result)
        self.assertTrue(result["endpoint_absent_from_dashboard_payload"])
        self.assertTrue(result["request_absent_from_dashboard_payload"])
        self.assertTrue(result["health_absent_from_dashboard_payload"])
        self.assertTrue(result["response_absent_from_dashboard_payload"])
        self.assertTrue(result["provider_endpoint_internal_only"])
        self.assertTrue(result["endpoint_absent_from_worker_metadata"])

    def test_provider_health_side_effect_boundaries(self):
        result = verify_model_provider_health_side_effect_boundaries()

        self.assertTrue(result["allowed_aggregate"]["model_provider_health_check_called"])
        self.assertTrue(result["allowed_aggregate"]["model_provider_health_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["model_provider_health_request_validated"])
        self.assertTrue(result["allowed_aggregate"]["model_provider_health_response_validated"])
        for key, value in result["forbidden_aggregate"].items():
            self.assertFalse(value, key)

    def test_model_provider_health_diagnostics_anchor_verification_passes(self):
        result = verify_model_provider_health_diagnostics_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
