from __future__ import annotations

from .worker_health_polling_anchor_cases import *  # noqa: F403
from .worker_health_polling_anchor_fixtures import *  # noqa: F403


def verify_worker_health_polling_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_worker_health_polling_files(root)
    setup = verify_setup_enqueues_post_setup_poll_without_worker_call(root)
    scheduler = verify_home_assistant_timer_schedules_post_setup_and_next_poll(root)
    ready = verify_scheduled_ready_poll_records_cadence(root)
    timing = verify_next_poll_timing_blocks_early_duplicate_polls(root)
    failures = verify_failure_poll_results_use_bounded_backoff(root)
    blocked = verify_missing_preconditions_block_before_worker_call(root)
    single_flight = verify_single_flight_guard_prevents_overlapping_poll(root)
    unload = verify_unload_removes_durable_polling_state(root)
    isolation = verify_worker_health_polling_stays_config_entry_scoped(root)
    storage_merge = verify_storage_load_merges_persisted_entries_without_dropping_unsaved(root)
    resume = verify_setup_resumes_persisted_polling_cadence(root)
    unload_race = verify_unload_races_do_not_resurrect_polling_state(root)
    reload_race = verify_in_flight_poll_does_not_write_after_same_entry_reload(root)
    context_change = verify_in_flight_poll_clears_after_worker_context_change(root)
    leakage = verify_worker_health_polling_details_do_not_leak_to_card(root)
    side_effects = verify_worker_health_polling_side_effect_boundaries()

    failure_messages = []
    if not files["all_files_present"]:
        failure_messages.append("One or more worker health polling scaffold files are missing.")
    if setup["state"]["status"] != "scheduled" or setup["health_call_count"] != 0:
        failure_messages.append("Setup did not enqueue polling without a worker call.")
    if not setup["state_validation"]["accepted"]:
        failure_messages.append("Setup polling state did not validate.")
    if (
        scheduler["health_calls_after_setup"] != 0
        or scheduler["setup_timer"]["registered"] is not True
        or scheduler["setup_timer"]["delay_seconds"] != 0
        or scheduler["state_after_fire"]["status"] != "ready"
        or scheduler["health_call_count"] != 1
        or scheduler["created_task_count"] != 1
        or scheduler["executor_job_count"] != 1
        or scheduler["next_timer"]["registered"] is not True
        or scheduler["next_timer"]["delay_seconds"] != READY_POLL_CADENCE_SECONDS
        or scheduler["unload"]["cancelled_scheduled_poll"] is not True
        or not scheduler["timer_absent_after_unload"]
    ):
        failure_messages.append("Home Assistant timer did not run the post-setup poll and schedule the next poll.")
    if ready["state"]["status"] != "ready" or ready["next_poll_delay_seconds"] != READY_POLL_CADENCE_SECONDS:
        failure_messages.append("Ready poll did not store ready state with 300 second cadence.")
    if ready["state"]["scheduler"]["consecutive_failures"] != 0:
        failure_messages.append("Ready poll did not reset consecutive failures.")
    if ready["explicit_health_state_written"] or ready["worker_health_setup_code"] != "worker_health_probe_available":
        failure_messages.append("Scheduled poll wrote explicit worker health state.")
    if timing["ready"]["early_result"]["code"] != "worker_health_poll_not_due":
        failure_messages.append("Ready poll did not block an early duplicate poll.")
    if timing["ready"]["health_call_count"] != 1:
        failure_messages.append("Ready early duplicate poll called the worker.")
    if (
        timing["ready"]["lost_precondition_result"]["code"] != "worker_health_polling_blocked"
        or timing["ready"]["lost_precondition_state"]["status"] != "blocked"
        or timing["ready"]["lost_precondition_state"]["orchestration"]["worker_health_check_called"]
    ):
        failure_messages.append("Ready poll did not revalidate preconditions before the not-due shortcut.")
    if timing["not_ready"]["early_result"]["code"] != "worker_health_poll_not_due":
        failure_messages.append("Not-ready poll did not block an early duplicate poll.")
    if timing["not_ready"]["health_call_count"] != 1 or timing["not_ready"]["consecutive_failures"] != 1:
        failure_messages.append("Not-ready early duplicate poll advanced failure state.")
    if not failures["not_ready"]["state_validation"]["accepted"] or not failures["unavailable"]["state_validation"]["accepted"]:
        failure_messages.append("Failure polling states did not validate.")
    if failures["not_ready"]["state"]["scheduler"]["backoff_seconds"] != 60:
        failure_messages.append("Repeated not-ready poll did not advance to 60 second backoff.")
    if failures["unavailable"]["state"]["scheduler"]["backoff_seconds"] != 30:
        failure_messages.append("Unavailable poll did not start at 30 second backoff.")
    if blocked["state"]["status"] != "blocked" or blocked["worker_client_present"]:
        failure_messages.append("Blocked preconditions did not stop before worker client setup.")
    if single_flight["result"]["code"] != "worker_health_poll_already_in_flight":
        failure_messages.append("Single-flight guard did not reject overlapping poll.")
    if single_flight["health_call_count"] != 0:
        failure_messages.append("Single-flight guard allowed a worker health call.")
    if single_flight["normal_poll"]["poll_in_flight_during_health_call"] is not True:
        failure_messages.append("Normal poll did not mark in-flight before the worker health call.")
    if single_flight["normal_poll"]["poll_in_flight_after_poll"] is not False:
        failure_messages.append("Normal poll did not clear in-flight state after the worker health call.")
    if unload["entry_a_state"] is not None or "worker-polling-unload-entry-a" in unload["after_unload"]["entry_ids"]:
        failure_messages.append("Unload did not remove entry A durable polling state.")
    if "worker-polling-unload-entry-b" not in unload["after_unload"]["entry_ids"]:
        failure_messages.append("Unload removed unrelated polling state.")
    if isolation["entry_a"]["state"]["config_entry_id"] == isolation["entry_b"]["state"]["config_entry_id"]:
        failure_messages.append("Polling states did not stay config-entry scoped.")
    if not isolation["entry_a"]["other_token_absent_from_request"] or not isolation["entry_b"]["other_token_absent_from_request"]:
        failure_messages.append("A polling health request included another entry's token.")
    if (
        not storage_merge["unsaved_entry_present"]
        or not storage_merge["persisted_entry_present"]
        or not storage_merge["token_missing_entry_loaded"]
        or not storage_merge["invalid_entry_absent"]
        or not storage_merge["invalid_bounds_entry_absent"]
        or not storage_merge["invalid_cadence_entry_absent"]
        or not storage_merge["cancelled_entry_absent"]
        or not storage_merge["unloaded_entry_not_remerged"]
    ):
        failure_messages.append("Storage load did not merge persisted and unsaved polling entries.")
    if (
        not storage_merge["unsaved_state_preserved"]
        or not storage_merge["persisted_state_loaded"]
        or not storage_merge["token_missing_state_loaded"]
        or not storage_merge["invalid_state_not_loaded"]
        or not storage_merge["invalid_bounds_state_not_loaded"]
        or not storage_merge["invalid_cadence_state_not_loaded"]
        or not storage_merge["cancelled_state_not_loaded"]
        or not storage_merge["unloaded_state_not_loaded"]
    ):
        failure_messages.append("Storage load replaced or corrupted polling entries.")
    if (
        not resume["state_validation"]["accepted"]
        or not resume["cadence_preserved"]
        or not resume["consecutive_failures_preserved"]
        or not resume["backoff_seconds_preserved"]
        or resume["resumed_health_call_count"] != 0
        or resume["setup_timer"]["delay_seconds"] != 30
    ):
        failure_messages.append("Setup did not resume persisted polling cadence.")
    if (
        unload_race["result"]["code"] != "worker_health_polling_entry_unloaded"
        or not unload_race["state_absent_after_poll"]
        or not unload_race["entry_data_absent_after_poll"]
    ):
        failure_messages.append("In-flight poll completion resurrected unloaded polling state.")
    if (
        reload_race["result"]["code"] != "worker_health_polling_entry_reloaded"
        or reload_race["old_health_call_count"] != 1
        or reload_race["reloaded_health_call_count"] != 0
        or not reload_race["new_entry_is_current"]
        or not reload_race["old_worker_health_absent_from_reloaded_entry"]
        or not reload_race["stale_ready_state_absent"]
        or not reload_race["stale_old_token_absent"]
        or not reload_race["new_token_present_only_in_worker_client"]
    ):
        failure_messages.append("In-flight poll completion wrote stale state after same-entry reload.")
    if (
        context_change["result"]["code"] != "worker_health_polling_context_changed"
        or not context_change["rotation_accepted"]
        or not context_change["in_flight_cleared"]
        or context_change["follow_up_result"]["code"] != "worker_health_ready"
        or not context_change["follow_up_poll_accepted"]
        or not context_change["follow_up_used_replacement_client"]
    ):
        failure_messages.append("In-flight poll completion wedged polling after worker context changed.")
    if not all(
        leakage[key]
        for key in (
            "token_absent_from_polling_state",
            "token_absent_from_setup",
            "token_absent_from_evidence_payload",
            "token_absent_from_dashboard_card_metadata",
            "token_absent_from_model_provider_metadata",
            "endpoint_absent_from_polling_state",
            "endpoint_message_absent_from_polling_state",
            "endpoint_message_url_scheme_absent",
            "endpoint_message_absent_from_evidence_payload",
            "endpoint_code_absent_from_polling_state",
            "endpoint_code_redacted",
            "endpoint_health_code_redacted",
            "endpoint_code_absent_from_evidence_payload",
            "bare_token_absent_from_polling_state",
            "bare_token_absent_from_evidence_payload",
            "bare_token_code_redacted",
            "bare_token_health_code_redacted",
            "bare_token_message_redacted",
            "authorization_absent_from_polling_state",
            "request_absent_from_polling_state",
            "response_checks_absent_from_polling_state",
            "endpoint_absent_from_dashboard_payload",
            "polling_absent_from_dashboard_payload",
            "repair_recommendation_absent_from_dashboard_payload",
        )
    ):
        failure_messages.append("Worker health polling details leaked to durable state or dashboard payloads.")
    if any(side_effects["forbidden_aggregate"].values()):
        failure_messages.append("Worker health polling scaffold reported forbidden side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failure_messages.append("Worker health polling scaffold did not report expected allowed side effects.")

    return {
        "passed": not failure_messages,
        "failures": failure_messages,
        "files": files,
        "setup": setup,
        "scheduler": scheduler,
        "ready": ready,
        "timing": timing,
        "failures_case": failures,
        "blocked": blocked,
        "single_flight": single_flight,
        "unload": unload,
        "isolation": isolation,
        "storage_merge": storage_merge,
        "resume": resume,
        "unload_race": unload_race,
        "reload_race": reload_race,
        "context_change": context_change,
        "leakage": leakage,
        "side_effects": side_effects,
    }
