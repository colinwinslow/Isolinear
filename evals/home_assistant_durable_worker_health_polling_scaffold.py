import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.worker_health_polling_anchor import (  # noqa: E402
    verify_worker_health_polling_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_worker_health_polling_anchor(REPO_ROOT)

    assert_true(
        result["passed"],
        f"Durable worker health polling scaffold failed: {result['failures']!r}",
    )

    print_case(
        "setup_enqueues_post_setup_poll_without_worker_call",
        given={
            "run_timestamp": run_timestamp,
            "config_entry_id": "worker-polling-setup-entry",
            "polling_state_schema": "docs/schemas/integration-worker-health-polling-state.schema.json",
        },
        when={
            "operation": "setup_worker_health_polling",
            "setup_worker_call_expected": False,
        },
        then={
            "setup": result["setup"],
        },
    )

    print_case(
        "scheduled_ready_poll_records_cadence",
        given={
            "config_entry_id": "worker-polling-ready-entry",
            "worker_response_status": "ready",
        },
        when={
            "operation": "run_worker_health_poll",
        },
        then={
            "ready": result["ready"],
            "timing": {
                "ready": result["timing"]["ready"],
            },
        },
    )

    print_case(
        "home_assistant_timer_schedules_post_setup_and_next_poll",
        given={
            "config_entry_id": "worker-polling-scheduler-entry",
            "home_assistant_timer_surface": True,
        },
        when={
            "operation": "fire_registered_worker_health_polling_timer",
        },
        then={
            "scheduler": result["scheduler"],
        },
    )

    print_case(
        "failure_poll_results_use_bounded_backoff",
        given={
            "entry_ids": [
                "worker-polling-not-ready-entry",
                "worker-polling-unavailable-entry",
            ],
            "backoff_seconds": [30, 60, 120, 300, 900],
        },
        when={
            "operation": "run_failure_worker_health_polls",
        },
        then={
            "failures": result["failures_case"],
            "timing": {
                "not_ready": result["timing"]["not_ready"],
            },
        },
    )

    print_case(
        "missing_preconditions_block_before_worker_call",
        given={
            "config_entry_id": "worker-polling-blocked-entry",
            "worker_endpoint_configured": True,
            "worker_readiness_ready": False,
        },
        when={
            "operation": "run_worker_health_poll",
        },
        then={
            "blocked": result["blocked"],
        },
    )

    print_case(
        "single_flight_guard_prevents_overlapping_poll",
        given={
            "config_entry_id": "worker-polling-single-flight-entry",
            "poll_in_flight": True,
        },
        when={
            "operation": "run_worker_health_poll",
        },
        then={
            "single_flight": result["single_flight"],
        },
    )

    print_case(
        "unload_removes_durable_polling_state",
        given={
            "entry_ids": [
                "worker-polling-unload-entry-a",
                "worker-polling-unload-entry-b",
            ],
        },
        when={
            "operation": "async_unload_entry",
            "target_entry_id": "worker-polling-unload-entry-a",
        },
        then={
            "unload": result["unload"],
            "unload_race": result["unload_race"],
            "reload_race": result["reload_race"],
            "context_change": result["context_change"],
        },
    )

    print_case(
        "worker_health_polling_stays_config_entry_scoped",
        given={
            "entry_ids": [
                "worker-polling-isolation-entry-a",
                "worker-polling-isolation-entry-b",
            ],
        },
        when={
            "operation": "run_worker_health_poll_for_both_entries",
        },
        then={
            "isolation": result["isolation"],
            "storage_merge": result["storage_merge"],
        },
    )

    print_case(
        "setup_resumes_persisted_polling_cadence",
        given={
            "config_entry_id": "worker-polling-resume-entry",
            "persisted_result": "not_ready",
            "persisted_backoff_seconds": 60,
        },
        when={
            "operation": "async_setup_worker_health_polling_after_storage_load",
        },
        then={
            "resume": result["resume"],
        },
    )

    print_case(
        "worker_health_polling_details_do_not_leak_to_card",
        given={
            "config_entry_id": "worker-polling-leak-entry",
            "authorization_source": "integration_owned_worker_token",
        },
        when={
            "operation": "inspect_polling_setup_dashboard_model_and_evidence_payloads",
        },
        then={
            "leakage": result["leakage"],
        },
    )

    print_case(
        "worker_health_polling_remains_bounded",
        given={
            "handled_surfaces": [
                "setup",
                "ha_timer_poll",
                "ready_poll",
                "failure_polls",
                "blocked_poll",
                "single_flight",
                "unload",
                "config_entry_isolation",
                "setup_resume",
                "reload_race",
                "context_change",
            ],
        },
        when={
            "operation": "aggregate_observed_side_effects",
        },
        then={
            "side_effects": result["side_effects"],
        },
    )

    print("PASS home_assistant_durable_worker_health_polling_scaffold")


if __name__ == "__main__":
    main()
