import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.job_orchestration_worker_dispatch_rendering_anchor import (  # noqa: E402
    verify_job_orchestration_worker_dispatch_rendering_anchor,
)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    run_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = verify_job_orchestration_worker_dispatch_rendering_anchor(REPO_ROOT)

    assert_true(
        result["passed"],
        f"Worker dispatch/rendering scaffold failed: {result['failures']!r}",
    )

    print_case(
        "worker_dispatch_records_render_result",
        given={
            "run_timestamp": run_timestamp,
            "config_entry_id": "worker-dispatch-entry",
            "worker_dispatch_schema": "docs/schemas/integration-worker-dispatch.schema.json",
            "worker_transport_schema": "docs/schemas/worker-transport-request.schema.json",
        },
        when={
            "operation": "dispatch_registered_job_snapshot_with_fake_worker",
        },
        then={
            "accepted": result["accepted"],
        },
    )

    print_case(
        "repeated_snapshot_requests_reuse_worker_dispatch",
        given={
            "config_entry_id": "worker-idempotent-entry",
        },
        when={
            "operation": "dispatch_registered_job_snapshot_twice",
        },
        then={
            "idempotent": result["idempotent"],
        },
    )

    print_case(
        "worker_dispatch_contracts_validate_before_storage",
        given={
            "worker_dispatch_schema": "docs/schemas/integration-worker-dispatch.schema.json",
            "worker_transport_schema": "docs/schemas/worker-transport-request.schema.json",
            "render_request_schema": "docs/schemas/render-request.schema.json",
            "render_result_schema": "docs/schemas/render-result.schema.json",
            "render_plan_schema": "docs/schemas/integration-render-plan.schema.json",
            "chart_spec_schema": "docs/schemas/chart-spec.schema.json",
            "history_series_schema": "docs/schemas/history-series.schema.json",
        },
        when={
            "operation": "validate_observed_worker_dispatch_contracts",
        },
        then={
            "validation": result["validation"],
        },
    )

    print_case(
        "worker_authorization_is_redacted",
        given={
            "authorization_source": "integration_owned_fake_worker_client",
        },
        when={
            "operation": "inspect_stored_dispatch_metadata_and_evidence",
        },
        then={
            "redaction": result["redaction"],
        },
    )

    print_case(
        "worker_failure_rejected_before_storage",
        given={
            "worker_failure_code": "worker_safe_renderer_failed",
        },
        when={
            "operation": "dispatch_registered_job_snapshot_with_failed_worker_result",
        },
        then={
            "failure": result["failure"],
        },
    )

    print_case(
        "unknown_job_rejected_before_worker_call",
        given={
            "job_id": "unknown-worker-entry-job-404",
        },
        when={
            "operation": "dispatch_registered_job_snapshot",
        },
        then={
            "unknown_job": result["unknown_job"],
        },
    )

    print_case(
        "cross_config_entry_rejected_before_worker_call",
        given={
            "entry_ids": ["worker-cross-entry-a", "worker-cross-entry-b"],
        },
        when={
            "operation": "snapshot_entry_a_job_from_entry_b",
        },
        then={
            "cross_entry": result["cross_entry"],
        },
    )

    print_case(
        "valid_worker_dispatches_stay_config_entry_scoped",
        given={
            "entry_ids": ["worker-isolation-entry-a", "worker-isolation-entry-b"],
        },
        when={
            "operation": "snapshot_each_entry_own_job_with_own_worker",
        },
        then={
            "isolation": result["isolation"],
        },
    )

    print_case(
        "worker_dispatch_remains_bounded",
        given={
            "handled_surfaces": [
                "accepted_worker_snapshot",
                "idempotent_snapshot",
                "worker_failure",
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

    print("PASS home_assistant_job_orchestration_worker_dispatch_rendering_scaffold")


if __name__ == "__main__":
    main()
