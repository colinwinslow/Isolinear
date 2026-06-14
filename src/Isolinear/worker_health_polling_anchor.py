from __future__ import annotations

from custom_components.isolinear.worker_health_polling import (
    FAILURE_BACKOFF_SECONDS,
    READY_POLL_CADENCE_SECONDS,
    WorkerHealthPollingStorageHelper,
)

from .worker_health_polling_anchor_cases import (
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
    verify_worker_health_polling_details_do_not_leak_to_card,
    verify_worker_health_polling_files,
    verify_worker_health_polling_side_effect_boundaries,
    verify_worker_health_polling_stays_config_entry_scoped,
)
from .worker_health_polling_anchor_verifier import verify_worker_health_polling_anchor

__all__ = [
    "FAILURE_BACKOFF_SECONDS",
    "READY_POLL_CADENCE_SECONDS",
    "WorkerHealthPollingStorageHelper",
    "verify_failure_poll_results_use_bounded_backoff",
    "verify_home_assistant_timer_schedules_post_setup_and_next_poll",
    "verify_in_flight_poll_clears_after_worker_context_change",
    "verify_in_flight_poll_does_not_write_after_same_entry_reload",
    "verify_missing_preconditions_block_before_worker_call",
    "verify_next_poll_timing_blocks_early_duplicate_polls",
    "verify_scheduled_ready_poll_records_cadence",
    "verify_setup_enqueues_post_setup_poll_without_worker_call",
    "verify_setup_resumes_persisted_polling_cadence",
    "verify_single_flight_guard_prevents_overlapping_poll",
    "verify_storage_load_merges_persisted_entries_without_dropping_unsaved",
    "verify_unload_races_do_not_resurrect_polling_state",
    "verify_unload_removes_durable_polling_state",
    "verify_worker_health_polling_anchor",
    "verify_worker_health_polling_details_do_not_leak_to_card",
    "verify_worker_health_polling_files",
    "verify_worker_health_polling_side_effect_boundaries",
    "verify_worker_health_polling_stays_config_entry_scoped",
]
