import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.job_orchestration_model_provider_planning_anchor import (  # noqa: E402
    verify_job_orchestration_model_provider_planning_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_job_orchestration_model_provider_planning_anchor(REPO_ROOT)

    assert_true(
        result["passed"],
        f"Model-provider planning scaffold failed: {result['failures']!r}",
    )

    print_case(
        "provider_produced_chart_spec_records_provider_plan",
        given={
            "run_timestamp": run_timestamp,
            "config_entry_id": "model-provider-entry",
            "model_provider_plan_schema": "docs/schemas/integration-model-provider-plan.schema.json",
            "planner_result_schema": "docs/schemas/planner-result.schema.json",
            "chart_spec_schema": "docs/schemas/chart-spec.schema.json",
        },
        when={
            "operation": "dispatch_registered_job_snapshot_with_fake_ollama_planner",
        },
        then={
            "accepted": result["accepted"],
        },
    )

    print_case(
        "repeated_snapshot_requests_reuse_provider_plan",
        given={
            "config_entry_id": "model-provider-idempotent-entry",
        },
        when={
            "operation": "dispatch_registered_job_snapshot_twice",
        },
        then={
            "idempotent": result["idempotent"],
        },
    )

    print_case(
        "hidden_provider_entity_rejected_before_storage",
        given={
            "returned_entity_id": "sensor.secret_temperature",
        },
        when={
            "operation": "dispatch_registered_job_snapshot_with_hidden_entity_chart_spec",
        },
        then={
            "hidden": result["hidden"],
            "hidden_memory": result["hidden_memory"],
            "entity_named_chart_id": result["entity_named_chart_id"],
        },
    )

    print_case(
        "invalid_provider_chart_spec_rejected_before_storage",
        given={
            "malformation": "missing_required_series",
        },
        when={
            "operation": "dispatch_registered_job_snapshot_with_invalid_chart_spec",
        },
        then={
            "invalid": result["invalid"],
        },
    )

    print_case(
        "unknown_job_rejected_before_provider_call",
        given={
            "job_id": "unknown-provider-entry-job-404",
        },
        when={
            "operation": "dispatch_registered_job_snapshot",
        },
        then={
            "unknown_job": result["unknown_job"],
        },
    )

    print_case(
        "cross_config_entry_rejected_before_provider_call",
        given={
            "entry_ids": ["provider-cross-entry-a", "provider-cross-entry-b"],
        },
        when={
            "operation": "snapshot_entry_a_job_from_entry_b",
        },
        then={
            "cross_entry": result["cross_entry"],
        },
    )

    print_case(
        "valid_provider_plans_stay_config_entry_scoped",
        given={
            "entry_ids": ["provider-isolation-entry-a", "provider-isolation-entry-b"],
        },
        when={
            "operation": "snapshot_each_entry_own_job_with_own_planner",
        },
        then={
            "isolation": result["isolation"],
        },
    )

    print_case(
        "provider_plans_and_chart_specs_validate_before_storage",
        given={
            "model_provider_plan_schema": "docs/schemas/integration-model-provider-plan.schema.json",
            "planner_result_schema": "docs/schemas/planner-result.schema.json",
            "render_plan_schema": "docs/schemas/integration-render-plan.schema.json",
            "chart_spec_schema": "docs/schemas/chart-spec.schema.json",
        },
        when={
            "operation": "validate_observed_provider_plans_and_render_plans",
        },
        then={
            "validation": result["validation"],
        },
    )

    print_case(
        "model_provider_planning_remains_bounded",
        given={
            "handled_surfaces": [
                "accepted_provider_snapshot",
                "idempotent_snapshot",
                "hidden_entity_failure",
                "invalid_chart_spec_failure",
                "unknown_job_failure",
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

    print("PASS home_assistant_job_orchestration_model_provider_planning_scaffold")


if __name__ == "__main__":
    main()
