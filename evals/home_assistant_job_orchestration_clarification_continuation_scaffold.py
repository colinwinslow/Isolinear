import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.job_orchestration_clarification_continuation_anchor import (  # noqa: E402
    verify_job_orchestration_clarification_continuation_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_job_orchestration_clarification_continuation_anchor(REPO_ROOT)

    assert_true(
        result["passed"],
        f"Clarification continuation scaffold failed: {result['failures']!r}",
    )

    print_case(
        "accepted_clarification_resumes_same_job",
        given={
            "run_timestamp": run_timestamp,
            "config_entry_id": "clarification-entry",
            "schema": "docs/schemas/integration-job-snapshot.schema.json",
        },
        when={
            "operation": "dispatch_registered_clarification_answer",
            "option_id": "sensor_upstairs_temperature",
        },
        then={
            "accepted": result["accepted"],
        },
    )

    print_case(
        "unknown_option_fails_before_history",
        given={
            "option_id": "sensor_basement_temperature",
        },
        when={
            "operation": "dispatch_registered_clarification_answer",
        },
        then={
            "unknown_option": result["unknown_option"],
        },
    )

    print_case(
        "wrong_question_fails_before_history",
        given={
            "question_id": "select_different_question",
        },
        when={
            "operation": "dispatch_registered_clarification_answer",
        },
        then={
            "wrong_question": result["wrong_question"],
        },
    )

    print_case(
        "colliding_option_fails_before_history",
        given={
            "option_id": "sensor_foo_bar",
            "approved_entity_ids": ["sensor.foo_bar", "sensor_foo.bar"],
        },
        when={
            "operation": "dispatch_registered_clarification_answer",
        },
        then={
            "collision": result["collision"],
        },
    )

    print_case(
        "cross_config_entry_answer_rejected",
        given={
            "entry_ids": ["answer-entry-a", "answer-entry-b"],
        },
        when={
            "operation": "answer_entry_a_job_from_entry_b",
        },
        then={
            "cross_entry": result["cross_entry"],
        },
    )

    print_case(
        "valid_continuations_stay_config_entry_scoped",
        given={
            "entry_ids": ["continuation-entry-a", "continuation-entry-b"],
        },
        when={
            "operation": "answer_each_entry_own_clarification",
        },
        then={
            "isolation": result["isolation"],
        },
    )

    print_case(
        "continuation_snapshots_validate_before_storage",
        given={
            "schema": "docs/schemas/integration-job-snapshot.schema.json",
        },
        when={
            "operation": "validate_observed_continuation_snapshots",
        },
        then={
            "snapshot_validation": result["snapshot_validation"],
        },
    )

    print_case(
        "clarification_continuation_remains_bounded",
        given={
            "handled_surfaces": [
                "accepted_clarification",
                "unknown_option_failure",
                "wrong_question_failure",
                "cross_config_entry_failure",
                "config_entry_isolation",
            ],
        },
        when={
            "operation": "aggregate_observed_side_effects",
        },
        then={
            "side_effects": result["side_effects"],
        },
    )

    print("PASS home_assistant_job_orchestration_clarification_continuation_scaffold")


if __name__ == "__main__":
    main()
