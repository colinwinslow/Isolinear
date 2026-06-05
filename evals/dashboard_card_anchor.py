import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.dashboard_card_anchor import (  # noqa: E402
    PROMPT_TEXT,
    VALID_CARD_CONFIG,
    verify_dashboard_card_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_dashboard_card_anchor(REPO_ROOT)

    assert_true(result["passed"], f"Dashboard card anchor verification failed: {result['failures']!r}")

    print_case(
        "dashboard_card_anchor_files_and_fixtures",
        given={
            "run_timestamp": run_timestamp,
            "frontend_root": "frontend",
            "required_states": ["idle", "planning", "clarification_needed", "complete", "failed"],
        },
        when={
            "operation": "verify_dashboard_card_anchor",
        },
        then={
            "inventory": result["inventory"],
            "fixture_job_snapshots": result["snapshots"],
        },
    )

    print_case(
        "dashboard_loads_isolinear_custom_card",
        given={
            "module": "frontend/dist/isolinear-card.js",
            "config": VALID_CARD_CONFIG,
        },
        when={
            "operation": "inspect_custom_element_registration_and_config_hooks",
        },
        then={
            "registration": result["registration"],
            "config_behavior": result["config_behavior"],
            "idle_layout": result["layout"]["idle_prompt_first"],
        },
    )

    print_case(
        "user_submits_prompt_and_sees_progress",
        given={
            "snapshot": result["snapshots"]["idle"],
            "fake_hass": "frontend/harness/fake-hass.js",
        },
        when={
            "prompt": PROMPT_TEXT,
            "operation": "submit_prompt",
        },
        then={
            "planning_layout": result["layout"]["active_planning"],
            "recorded_message": result["adapter"]["recorded_messages"][0],
            "submit_disabled_for_active_job": result["layout"]["active_planning"][
                "disabled_duplicate_submit_marker"
            ],
        },
    )

    print_case(
        "user_answers_clarification",
        given={
            "snapshot": result["snapshots"]["clarification_needed"],
        },
        when={
            "operation": "choose_use_once_and_use_and_remember",
        },
        then={
            "clarification_layout": result["layout"]["clarification"],
            "use_once_message": result["adapter"]["recorded_messages"][1],
            "use_and_remember_message": result["adapter"]["recorded_messages"][2],
            "browser_local_state_matches": result["boundary"]["matches"],
        },
    )

    print_case(
        "user_views_chart_result",
        given={
            "snapshot": result["snapshots"]["complete"],
        },
        when={
            "operation": "render_complete_snapshot",
        },
        then={
            "complete_layout": result["layout"]["complete_chart_first"],
            "chart_title": result["snapshots"]["complete"]["chart"]["title"],
            "entities": result["snapshots"]["complete"]["entities"],
            "aliases": result["snapshots"]["complete"]["aliases"],
            "validation": result["snapshots"]["complete"]["validation"],
        },
    )

    print_case(
        "user_sees_failure_details",
        given={
            "snapshot": result["snapshots"]["failed"],
        },
        when={
            "operation": "render_failed_snapshot",
        },
        then={
            "failed_layout": result["layout"]["failed"],
            "failure": result["snapshots"]["failed"]["failure"],
            "retry_message": result["adapter"]["recorded_messages"][3],
        },
    )

    print_case(
        "card_keeps_orchestration_inside_integration",
        given={
            "scanned_files": result["boundary"]["scanned_files"],
        },
        when={
            "operation": "static_boundary_scan",
        },
        then={
            "adapter": result["adapter"],
            "boundary": result["boundary"],
        },
    )

    print("PASS dashboard_card_anchor")


if __name__ == "__main__":
    main()
