import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.worker_token_provisioning_readiness_anchor import WORKER_READINESS_TEST_TOKEN  # noqa: E402
from Isolinear.worker_health_polling_anchor import (  # noqa: E402
    READY_POLL_CADENCE_SECONDS,
    verify_failure_poll_results_use_bounded_backoff,
    verify_home_assistant_timer_schedules_post_setup_and_next_poll,
    verify_in_flight_poll_clears_after_worker_context_change,
    verify_in_flight_poll_does_not_write_after_same_entry_reload,
    verify_missing_preconditions_block_before_worker_call,
    verify_next_poll_timing_blocks_early_duplicate_polls,
    verify_scheduled_ready_poll_records_cadence,
    verify_setup_enqueues_post_setup_poll_without_worker_call,
    verify_setup_resumes_persisted_polling_cadence,
    verify_single_flight_guard_prevents_overlapping_poll,
    verify_storage_load_merges_persisted_entries_without_dropping_unsaved,
    verify_unload_races_do_not_resurrect_polling_state,
    verify_unload_removes_durable_polling_state,
    verify_worker_health_polling_anchor,
    verify_worker_health_polling_details_do_not_leak_to_card,
    verify_worker_health_polling_side_effect_boundaries,
    verify_worker_health_polling_stays_config_entry_scoped,
)


class WorkerHealthPollingAnchorTests(unittest.TestCase):
    def test_setup_enqueues_post_setup_poll_without_worker_call(self):
        result = verify_setup_enqueues_post_setup_poll_without_worker_call(REPO_ROOT)

        self.assertTrue(result["setup"]["accepted"], result)
        self.assertEqual(result["state"]["status"], "scheduled")
        self.assertTrue(result["state_validation"]["accepted"], result)
        self.assertTrue(result["state"]["scheduler"]["post_setup_poll_enqueued"])
        self.assertEqual(result["health_call_count"], 0)
        self.assertEqual(result["render_call_count"], 0)

    def test_home_assistant_timer_schedules_post_setup_and_next_poll(self):
        result = verify_home_assistant_timer_schedules_post_setup_and_next_poll(REPO_ROOT)

        self.assertEqual(result["health_calls_after_setup"], 0)
        self.assertTrue(result["setup_timer"]["registered"], result)
        self.assertEqual(result["setup_timer"]["delay_seconds"], 0)
        self.assertEqual(result["fired_timer_delay_seconds"], 0)
        self.assertEqual(result["state_after_fire"]["status"], "ready")
        self.assertTrue(result["state_validation"]["accepted"], result)
        self.assertEqual(result["health_call_count"], 1)
        self.assertEqual(result["created_task_count"], 1)
        self.assertEqual(result["executor_job_count"], 1)
        self.assertTrue(result["next_timer"]["registered"], result)
        self.assertEqual(result["next_timer"]["delay_seconds"], READY_POLL_CADENCE_SECONDS)
        self.assertTrue(result["unload"]["cancelled_scheduled_poll"], result)
        self.assertTrue(result["timer_absent_after_unload"], result)

    def test_scheduled_ready_poll_records_cadence(self):
        result = verify_scheduled_ready_poll_records_cadence(REPO_ROOT)

        self.assertTrue(result["result"]["accepted"], result)
        self.assertEqual(result["state"]["status"], "ready")
        self.assertTrue(result["state_validation"]["accepted"], result)
        self.assertEqual(result["state"]["scheduler"]["consecutive_failures"], 0)
        self.assertEqual(result["next_poll_delay_seconds"], READY_POLL_CADENCE_SECONDS)
        self.assertEqual(result["health_call_count"], 1)
        self.assertEqual(result["render_call_count"], 0)
        self.assertFalse(result["explicit_health_state_written"], result)
        self.assertEqual(result["worker_health_setup_code"], "worker_health_probe_available")

    def test_next_poll_timing_blocks_early_duplicate_polls(self):
        result = verify_next_poll_timing_blocks_early_duplicate_polls(REPO_ROOT)

        self.assertEqual(result["ready"]["early_result"]["code"], "worker_health_poll_not_due")
        self.assertEqual(result["ready"]["health_call_count"], 1)
        self.assertEqual(result["ready"]["next_poll_delay_seconds"], READY_POLL_CADENCE_SECONDS)
        self.assertTrue(result["ready"]["state_validation"]["accepted"], result)
        self.assertEqual(result["ready"]["lost_precondition_result"]["code"], "worker_health_polling_blocked")
        self.assertEqual(result["ready"]["lost_precondition_state"]["status"], "blocked")
        self.assertFalse(
            result["ready"]["lost_precondition_state"]["orchestration"]["worker_health_check_called"]
        )
        self.assertTrue(result["ready"]["lost_precondition_validation"]["accepted"], result)
        self.assertEqual(result["not_ready"]["early_result"]["code"], "worker_health_poll_not_due")
        self.assertEqual(result["not_ready"]["health_call_count"], 1)
        self.assertEqual(result["not_ready"]["consecutive_failures"], 1)
        self.assertEqual(result["not_ready"]["backoff_seconds"], 30)
        self.assertTrue(result["not_ready"]["state_validation"]["accepted"], result)

    def test_failure_poll_results_use_bounded_backoff(self):
        result = verify_failure_poll_results_use_bounded_backoff(REPO_ROOT)

        self.assertEqual(result["not_ready"]["state"]["status"], "not_ready")
        self.assertEqual(result["not_ready"]["state"]["scheduler"]["consecutive_failures"], 2)
        self.assertEqual(result["not_ready"]["state"]["scheduler"]["backoff_seconds"], 60)
        self.assertTrue(result["not_ready"]["state_validation"]["accepted"], result)
        self.assertEqual(result["unavailable"]["state"]["status"], "unavailable")
        self.assertEqual(result["unavailable"]["state"]["health"]["failure_family"], "connection")
        self.assertEqual(result["unavailable"]["state"]["scheduler"]["backoff_seconds"], 30)
        self.assertTrue(result["unavailable"]["state_validation"]["accepted"], result)

    def test_missing_preconditions_block_before_worker_call(self):
        result = verify_missing_preconditions_block_before_worker_call(REPO_ROOT)

        self.assertFalse(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "worker_health_polling_blocked")
        self.assertEqual(result["state"]["status"], "blocked")
        self.assertFalse(result["worker_client_present"])
        self.assertTrue(result["state_validation"]["accepted"], result)
        self.assertFalse(result["state"]["orchestration"]["worker_health_check_called"])

    def test_single_flight_guard_prevents_overlapping_poll(self):
        result = verify_single_flight_guard_prevents_overlapping_poll(REPO_ROOT)

        self.assertTrue(result["mark"]["accepted"], result)
        self.assertFalse(result["result"]["accepted"], result)
        self.assertEqual(result["result"]["code"], "worker_health_poll_already_in_flight")
        self.assertEqual(result["health_call_count"], 0)
        self.assertTrue(result["state"]["scheduler"]["poll_in_flight"])
        self.assertTrue(result["normal_poll"]["poll_in_flight_during_health_call"])
        self.assertFalse(result["normal_poll"]["poll_in_flight_after_poll"])
        self.assertEqual(result["normal_poll"]["health_call_count"], 1)

    def test_unload_removes_durable_polling_state(self):
        result = verify_unload_removes_durable_polling_state(REPO_ROOT)

        self.assertTrue(result["unload_result"], result)
        self.assertIsNone(result["entry_a_state"])
        self.assertNotIn("worker-polling-unload-entry-a", result["after_unload"]["entry_ids"])
        self.assertIn("worker-polling-unload-entry-b", result["after_unload"]["entry_ids"])
        self.assertTrue(result["entry_b_validation"]["accepted"], result)

    def test_worker_health_polling_stays_config_entry_scoped(self):
        result = verify_worker_health_polling_stays_config_entry_scoped(REPO_ROOT)

        self.assertEqual(result["entry_a"]["state"]["config_entry_id"], "worker-polling-isolation-entry-a")
        self.assertEqual(result["entry_b"]["state"]["config_entry_id"], "worker-polling-isolation-entry-b")
        self.assertEqual(result["entry_a"]["state"]["status"], "ready")
        self.assertEqual(result["entry_b"]["state"]["status"], "not_ready")
        self.assertEqual(result["entry_a"]["health_call_count"], 1)
        self.assertEqual(result["entry_b"]["health_call_count"], 1)
        self.assertTrue(result["entry_a"]["raw_request_uses_own_token"])
        self.assertTrue(result["entry_b"]["raw_request_uses_own_token"])
        self.assertTrue(result["entry_a"]["other_token_absent_from_request"])
        self.assertTrue(result["entry_b"]["other_token_absent_from_request"])

    def test_storage_load_merges_persisted_entries_without_dropping_unsaved(self):
        result = verify_storage_load_merges_persisted_entries_without_dropping_unsaved(REPO_ROOT)

        self.assertTrue(result["unsaved_entry_present"], result)
        self.assertTrue(result["persisted_entry_present"], result)
        self.assertTrue(result["token_missing_entry_loaded"], result)
        self.assertTrue(result["invalid_entry_absent"], result)
        self.assertTrue(result["invalid_bounds_entry_absent"], result)
        self.assertTrue(result["invalid_cadence_entry_absent"], result)
        self.assertTrue(result["cancelled_entry_absent"], result)
        self.assertTrue(result["unloaded_entry_not_remerged"], result)
        self.assertTrue(result["persisted_entry_still_present_after_unloaded_load"], result)
        self.assertTrue(result["unsaved_state_preserved"], result)
        self.assertTrue(result["persisted_state_loaded"], result)
        self.assertTrue(result["token_missing_state_loaded"], result)
        self.assertTrue(result["unloaded_state_not_loaded"], result)
        self.assertTrue(result["invalid_state_not_loaded"], result)
        self.assertTrue(result["invalid_bounds_state_not_loaded"], result)
        self.assertTrue(result["invalid_cadence_state_not_loaded"], result)
        self.assertTrue(result["cancelled_state_not_loaded"], result)
        self.assertTrue(result["state_a_validation"]["accepted"], result)
        self.assertTrue(result["state_b_validation"]["accepted"], result)
        self.assertTrue(result["token_missing_validation"]["accepted"], result)

    def test_setup_resumes_persisted_polling_cadence(self):
        result = verify_setup_resumes_persisted_polling_cadence(REPO_ROOT)

        self.assertTrue(result["state_validation"]["accepted"], result)
        self.assertTrue(result["cadence_preserved"], result)
        self.assertTrue(result["consecutive_failures_preserved"], result)
        self.assertTrue(result["backoff_seconds_preserved"], result)
        self.assertEqual(result["resumed_health_call_count"], 0)
        self.assertEqual(result["setup_timer"]["delay_seconds"], 30)

    def test_unload_races_do_not_resurrect_polling_state(self):
        result = verify_unload_races_do_not_resurrect_polling_state(REPO_ROOT)

        self.assertEqual(result["result"]["code"], "worker_health_polling_entry_unloaded")
        self.assertTrue(result["state_absent_after_poll"], result)
        self.assertTrue(result["entry_data_absent_after_poll"], result)
        self.assertEqual(result["health_call_count"], 1)

    def test_in_flight_poll_does_not_write_after_same_entry_reload(self):
        result = verify_in_flight_poll_does_not_write_after_same_entry_reload(REPO_ROOT)

        self.assertEqual(result["result"]["code"], "worker_health_polling_entry_reloaded")
        self.assertTrue(result["state_validation"]["accepted"], result)
        self.assertEqual(result["old_health_call_count"], 1)
        self.assertEqual(result["reloaded_health_call_count"], 0)
        self.assertTrue(result["new_entry_is_current"], result)
        self.assertTrue(result["old_worker_health_absent_from_reloaded_entry"], result)
        self.assertTrue(result["stale_ready_state_absent"], result)
        self.assertTrue(result["stale_old_token_absent"], result)

    def test_in_flight_poll_clears_after_worker_context_change(self):
        result = verify_in_flight_poll_clears_after_worker_context_change(REPO_ROOT)

        self.assertEqual(result["result"]["code"], "worker_health_polling_context_changed")
        self.assertTrue(result["context_state_validation"]["accepted"], result)
        self.assertTrue(result["rotation_accepted"], result)
        self.assertTrue(result["in_flight_cleared"], result)
        self.assertEqual(result["follow_up_result"]["code"], "worker_health_ready")
        self.assertTrue(result["follow_up_poll_accepted"], result)
        self.assertTrue(result["follow_up_used_replacement_client"], result)
        self.assertTrue(result["follow_up_state_validation"]["accepted"], result)

    def test_worker_health_polling_details_do_not_leak_to_card(self):
        result = verify_worker_health_polling_details_do_not_leak_to_card(REPO_ROOT)

        self.assertTrue(result["state_validation"]["accepted"], result)
        self.assertTrue(result["raw_worker_authorization_received"])
        self.assertTrue(result["token_absent_from_polling_state"])
        self.assertTrue(result["token_absent_from_setup"])
        self.assertTrue(result["token_absent_from_evidence_payload"])
        self.assertTrue(result["token_absent_from_dashboard_card_metadata"])
        self.assertTrue(result["endpoint_absent_from_polling_state"])
        self.assertTrue(result["endpoint_message_absent_from_polling_state"])
        self.assertTrue(result["endpoint_message_url_scheme_absent"])
        self.assertTrue(result["endpoint_message_absent_from_evidence_payload"])
        self.assertTrue(result["endpoint_code_absent_from_polling_state"])
        self.assertTrue(result["endpoint_code_redacted"])
        self.assertTrue(result["endpoint_health_code_redacted"])
        self.assertTrue(result["endpoint_code_absent_from_evidence_payload"])
        self.assertTrue(result["bare_token_absent_from_polling_state"])
        self.assertTrue(result["bare_token_absent_from_evidence_payload"])
        self.assertTrue(result["bare_token_code_redacted"])
        self.assertTrue(result["bare_token_health_code_redacted"])
        self.assertTrue(result["bare_token_message_redacted"])
        self.assertTrue(result["authorization_absent_from_polling_state"])
        self.assertTrue(result["endpoint_absent_from_dashboard_payload"])
        self.assertTrue(result["polling_absent_from_dashboard_payload"])
        self.assertNotIn(WORKER_READINESS_TEST_TOKEN, str(result))

    def test_worker_health_polling_side_effect_boundaries(self):
        result = verify_worker_health_polling_side_effect_boundaries()

        self.assertTrue(result["allowed_aggregate"]["durable_health_storage_written"])
        self.assertTrue(result["allowed_aggregate"]["scheduler_bookkeeping_written"])
        self.assertTrue(result["allowed_aggregate"]["post_setup_poll_enqueued"])
        self.assertTrue(result["allowed_aggregate"]["worker_health_check_called"])
        self.assertTrue(result["allowed_aggregate"]["worker_health_request_validated"])
        self.assertTrue(result["allowed_aggregate"]["worker_health_response_validated"])
        self.assertTrue(result["allowed_aggregate"]["single_flight_guard_checked"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_history_read"])
        self.assertFalse(result["forbidden_aggregate"]["semantic_memory_called"])
        self.assertFalse(result["forbidden_aggregate"]["home_assistant_service_or_state_mutation_called"])
        self.assertFalse(result["forbidden_aggregate"]["token_generated"])
        self.assertFalse(result["forbidden_aggregate"]["token_rotation_called"])
        self.assertFalse(result["forbidden_aggregate"]["token_repair_called"])
        self.assertFalse(result["forbidden_aggregate"]["worker_render_called"])
        self.assertFalse(result["forbidden_aggregate"]["model_provider_called"])
        self.assertFalse(result["forbidden_aggregate"]["chart_rendering_called"])
        self.assertFalse(result["forbidden_aggregate"]["chart_artifact_written"])
        self.assertFalse(result["forbidden_aggregate"]["durable_retry_storage_written"])
        self.assertFalse(result["forbidden_aggregate"]["recorder_called"])
        self.assertFalse(result["forbidden_aggregate"]["config_entry_options_written"])
        self.assertFalse(result["forbidden_aggregate"]["external_queue_called"])
        self.assertFalse(result["forbidden_aggregate"]["automatic_retry_called"])
        self.assertFalse(result["forbidden_aggregate"]["automatic_progress_task_called"])
        self.assertFalse(result["forbidden_aggregate"]["automatic_repair_called"])

    def test_worker_health_polling_anchor_verification_passes(self):
        result = verify_worker_health_polling_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
