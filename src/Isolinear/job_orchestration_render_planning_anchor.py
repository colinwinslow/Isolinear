from __future__ import annotations

from copy import deepcopy
from typing import Any

from custom_components.isolinear import async_setup_entry
from custom_components.isolinear.const import DOMAIN
from custom_components.isolinear.job_orchestration import (
    DATA_JOB_ORCHESTRATION,
    DATA_JOB_ORCHESTRATION_SETUP,
    NO_JOB_ORCHESTRATION_CALLS,
    summarize_job_orchestration_store,
)

from .contracts import ContractValidationError, validate_contract
from .dashboard_card_anchor import repo_root
from .entity_catalog_scaffold_anchor import FakeConfigEntry
from .job_orchestration_artifact_storage_anchor import (
    _artifacts,
    _complete_snapshots,
    _dispatch_snapshot,
    _dispatch_start,
    _error_codes,
    _job,
    _job_store,
    _setup_artifact_hass,
    _validate_artifacts,
    _validate_snapshot,
)
from .job_orchestration_scaffold_anchor import _fake_hass, _first_result_payload, _run
from custom_components.isolinear.job_state import summarize_job_state_store
from .websocket_command_registration_anchor import FakeWebSocketApiModule


RENDER_PLANNING_FILES = [
    "custom_components/isolinear/job_orchestration.py",
    "custom_components/isolinear/websocket_api.py",
    "docs/specs/home-assistant-job-orchestration-render-planning-scaffold-spec.md",
    "bdd/integration/home-assistant-job-orchestration-render-planning-scaffold-bdd.md",
    "bdd/integration/home-assistant-job-orchestration-render-planning-scaffold-evidence.md",
    "docs/evals/home_assistant_job_orchestration_render_planning_scaffold.yaml",
    "docs/schemas/integration-render-plan.schema.json",
    "docs/schemas/chart-spec.schema.json",
    "tests/test_job_orchestration_render_planning_anchor.py",
    "evals/home_assistant_job_orchestration_render_planning_scaffold.py",
    "src/Isolinear/job_orchestration_render_planning_anchor.py",
]

RENDER_PLANNING_FORBIDDEN_SIDE_EFFECT_KEYS = [
    *NO_JOB_ORCHESTRATION_CALLS,
    "home_assistant_history_read",
    "history_retrieval_scaffold_written",
    "subscription_bookkeeping_written",
]


def verify_render_planning_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in RENDER_PLANNING_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_scaffold_ready_snapshot_records_render_plan(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_artifact_hass(
        FakeConfigEntry(
            "render-plan-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        )
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "render-plan-entry",
        "Show sensor.upstairs_temperature",
        1,
    )
    start_snapshot = _first_result_payload(start)
    snapshot_dispatch = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "render-plan-entry",
        start_snapshot["job_id"],
        2,
    )
    artifact_snapshot = _first_result_payload(snapshot_dispatch)
    render_plans = _render_plans(hass, "render-plan-entry")
    artifacts = _artifacts(hass, "render-plan-entry")
    job = _job(hass, "render-plan-entry", start_snapshot["job_id"])
    stored_complete_snapshots = [
        snapshot for snapshot in job["snapshots"] if snapshot.get("status") == "complete"
    ]
    return {
        "start": start,
        "snapshot_dispatch": snapshot_dispatch,
        "start_snapshot": _snapshot_summary(start_snapshot),
        "artifact_snapshot": _snapshot_summary(artifact_snapshot),
        "render_plan": _render_plan_summary(render_plans[0]) if render_plans else None,
        "render_plans": [_render_plan_summary(plan) for plan in render_plans],
        "artifact": _artifact_summary(artifacts[0]) if artifacts else None,
        "artifacts": [_artifact_summary(artifact) for artifact in artifacts],
        "stored_complete_snapshots": [_snapshot_summary(snapshot) for snapshot in stored_complete_snapshots],
        "job_store": summarize_job_state_store(_job_store(hass, "render-plan-entry")),
        "orchestration_store": _orchestration_store_summary(hass, "render-plan-entry"),
        "snapshot_validation": _validate_snapshot(artifact_snapshot, root),
        "render_plan_validation": _validate_render_plans(render_plans, root),
        "chart_spec_validation": _validate_chart_specs(render_plans, root),
        "artifact_validation": _validate_artifacts(artifacts, root),
    }


def verify_repeated_snapshot_requests_reuse_render_plan(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_artifact_hass(
        FakeConfigEntry(
            "render-plan-idempotent-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        )
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "render-plan-idempotent-entry",
        "Show sensor.upstairs_temperature",
        10,
    )
    job_id = _first_result_payload(start)["job_id"]
    first = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "render-plan-idempotent-entry",
        job_id,
        11,
    )
    first_render_plan = _latest_render_plan_from_dispatch(first)
    second = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "render-plan-idempotent-entry",
        job_id,
        12,
    )
    first_snapshot = _first_result_payload(first)
    second_snapshot = _first_result_payload(second)
    second_render_plan = _latest_render_plan_from_dispatch(second)
    render_plans = _render_plans(hass, "render-plan-idempotent-entry")
    artifacts = _artifacts(hass, "render-plan-idempotent-entry")
    job = _job(hass, "render-plan-idempotent-entry", job_id)
    return {
        "first": first,
        "second": second,
        "first_snapshot": _snapshot_summary(first_snapshot),
        "second_snapshot": _snapshot_summary(second_snapshot),
        "first_render_plan": _render_plan_summary(first_render_plan),
        "second_render_plan": _render_plan_summary(second_render_plan),
        "same_snapshot_returned": first_snapshot == second_snapshot,
        "same_render_plan_returned": first_render_plan == second_render_plan,
        "render_plans": [_render_plan_summary(plan) for plan in render_plans],
        "render_plan_count": len(render_plans),
        "artifacts": [_artifact_summary(artifact) for artifact in artifacts],
        "artifact_count": len(artifacts),
        "complete_snapshot_count": len(
            [snapshot for snapshot in job["snapshots"] if snapshot.get("status") == "complete"]
        ),
        "render_plan_validation": _validate_render_plans(render_plans, root),
        "chart_spec_validation": _validate_chart_specs(render_plans, root),
        "snapshot_validation": _validate_snapshot(second_snapshot, root),
    }


def verify_unknown_render_plan_job_rejected_before_planning(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_artifact_hass(
        FakeConfigEntry(
            "unknown-render-plan-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        )
    )
    snapshot = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "unknown-render-plan-entry",
        "unknown-render-plan-entry-job-404",
        20,
    )
    return {
        "snapshot": snapshot,
        "error_codes": _error_codes(snapshot),
        "job_store": summarize_job_state_store(_job_store(hass, "unknown-render-plan-entry")),
        "render_plans": _render_plans(hass, "unknown-render-plan-entry"),
        "artifacts": _artifacts(hass, "unknown-render-plan-entry"),
        "render_plan_validation": _validate_render_plans([], root),
        "chart_spec_validation": _validate_chart_specs([], root),
    }


def verify_cross_config_entry_render_plan_rejected(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "render-plan-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "render-plan-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "render-plan-entry-a",
        "Show sensor.upstairs_temperature",
        30,
    )
    start_b = _dispatch_start(
        hass,
        websocket_api_module,
        "render-plan-entry-b",
        "Show binary_sensor.office_window",
        31,
    )
    snapshot_a = _first_result_payload(start_a)
    snapshot_b = _first_result_payload(start_b)
    cross_snapshot = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "render-plan-entry-b",
        snapshot_a["job_id"],
        32,
    )
    return {
        "entry_a_start": start_a,
        "entry_b_start": start_b,
        "entry_a_start_snapshot": _snapshot_summary(snapshot_a),
        "entry_b_start_snapshot": _snapshot_summary(snapshot_b),
        "entry_a_start_validation": _validate_snapshot(snapshot_a, root),
        "entry_b_start_validation": _validate_snapshot(snapshot_b, root),
        "cross_snapshot": cross_snapshot,
        "error_codes": _error_codes(cross_snapshot),
        "entry_a_render_plans": _render_plans(hass, "render-plan-entry-a"),
        "entry_b_render_plans": _render_plans(hass, "render-plan-entry-b"),
        "entry_a_artifacts": _artifacts(hass, "render-plan-entry-a"),
        "entry_b_artifacts": _artifacts(hass, "render-plan-entry-b"),
        "entry_b_complete_snapshots": _complete_snapshots(hass, "render-plan-entry-b", snapshot_b["job_id"]),
    }


def verify_valid_render_plans_stay_config_entry_scoped(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "valid-render-plan-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "valid-render-plan-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "valid-render-plan-entry-a",
        "Show sensor.upstairs_temperature",
        40,
    )
    start_b = _dispatch_start(
        hass,
        websocket_api_module,
        "valid-render-plan-entry-b",
        "Show binary_sensor.office_window",
        41,
    )
    snapshot_a = _first_result_payload(start_a)
    snapshot_b = _first_result_payload(start_b)
    plan_a = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "valid-render-plan-entry-a",
        snapshot_a["job_id"],
        42,
    )
    plan_b = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "valid-render-plan-entry-b",
        snapshot_b["job_id"],
        43,
    )
    render_plans_a = _render_plans(hass, "valid-render-plan-entry-a")
    render_plans_b = _render_plans(hass, "valid-render-plan-entry-b")
    artifacts_a = _artifacts(hass, "valid-render-plan-entry-a")
    artifacts_b = _artifacts(hass, "valid-render-plan-entry-b")
    return {
        "entry_a": {
            "start": start_a,
            "snapshot": plan_a,
            "render_plans": [_render_plan_summary(plan) for plan in render_plans_a],
            "artifacts": [_artifact_summary(artifact) for artifact in artifacts_a],
            "orchestration_store": _orchestration_store_summary(hass, "valid-render-plan-entry-a"),
            "render_plan_validation": _validate_render_plans(render_plans_a, root),
            "chart_spec_validation": _validate_chart_specs(render_plans_a, root),
        },
        "entry_b": {
            "start": start_b,
            "snapshot": plan_b,
            "render_plans": [_render_plan_summary(plan) for plan in render_plans_b],
            "artifacts": [_artifact_summary(artifact) for artifact in artifacts_b],
            "orchestration_store": _orchestration_store_summary(hass, "valid-render-plan-entry-b"),
            "render_plan_validation": _validate_render_plans(render_plans_b, root),
            "chart_spec_validation": _validate_chart_specs(render_plans_b, root),
        },
    }


def verify_render_plans_and_chart_specs_validate(root=None) -> dict[str, Any]:
    root = root or repo_root()
    accepted = verify_scaffold_ready_snapshot_records_render_plan(root)
    idempotent = verify_repeated_snapshot_requests_reuse_render_plan(root)
    isolation = verify_valid_render_plans_stay_config_entry_scoped(root)
    return {
        "accepted": {
            "render_plan_valid": all(item["accepted"] for item in accepted["render_plan_validation"]),
            "chart_spec_valid": all(item["accepted"] for item in accepted["chart_spec_validation"]),
            "render_plan_validation": accepted["render_plan_validation"],
            "chart_spec_validation": accepted["chart_spec_validation"],
        },
        "idempotent": {
            "render_plan_valid": all(item["accepted"] for item in idempotent["render_plan_validation"]),
            "chart_spec_valid": all(item["accepted"] for item in idempotent["chart_spec_validation"]),
            "render_plan_validation": idempotent["render_plan_validation"],
            "chart_spec_validation": idempotent["chart_spec_validation"],
        },
        "isolation_entry_a": {
            "render_plan_valid": all(
                item["accepted"] for item in isolation["entry_a"]["render_plan_validation"]
            ),
            "chart_spec_valid": all(
                item["accepted"] for item in isolation["entry_a"]["chart_spec_validation"]
            ),
            "render_plan_validation": isolation["entry_a"]["render_plan_validation"],
            "chart_spec_validation": isolation["entry_a"]["chart_spec_validation"],
        },
        "isolation_entry_b": {
            "render_plan_valid": all(
                item["accepted"] for item in isolation["entry_b"]["render_plan_validation"]
            ),
            "chart_spec_valid": all(
                item["accepted"] for item in isolation["entry_b"]["chart_spec_validation"]
            ),
            "render_plan_validation": isolation["entry_b"]["render_plan_validation"],
            "chart_spec_validation": isolation["entry_b"]["chart_spec_validation"],
        },
    }


def verify_render_plan_side_effect_boundaries() -> dict[str, Any]:
    accepted = verify_scaffold_ready_snapshot_records_render_plan()
    idempotent = verify_repeated_snapshot_requests_reuse_render_plan()
    unknown = verify_unknown_render_plan_job_rejected_before_planning()
    cross_entry = verify_cross_config_entry_render_plan_rejected()
    isolation = verify_valid_render_plans_stay_config_entry_scoped()
    setup = _setup_artifact_hass(
        FakeConfigEntry(
            "side-effects-render-plan-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        )
    )[0].data[DOMAIN]["side-effects-render-plan-entry"]

    observed = [
        {"name": "accepted_render_plan_snapshot", **accepted["snapshot_dispatch"]["orchestration"]},
        {"name": "idempotent_first_snapshot", **idempotent["first"]["orchestration"]},
        {"name": "idempotent_second_snapshot", **idempotent["second"]["orchestration"]},
        {"name": "unknown_render_plan_job", **unknown["snapshot"]["orchestration"]},
        {"name": "cross_config_entry", **cross_entry["cross_snapshot"]["orchestration"]},
        {"name": "entry_a_render_plan", **isolation["entry_a"]["snapshot"]["orchestration"]},
        {"name": "entry_b_render_plan", **isolation["entry_b"]["snapshot"]["orchestration"]},
        {"name": "setup_orchestration", **setup[DATA_JOB_ORCHESTRATION_SETUP]["orchestration"]},
        {"name": "websocket_registration", **setup["websocket_api"]["orchestration"]},
    ]

    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in RENDER_PLANNING_FORBIDDEN_SIDE_EFFECT_KEYS
    }
    allowed_aggregate = {
        "render_plan_bookkeeping_written": any(
            item.get("render_plan_bookkeeping_written") for item in observed
        ),
        "artifact_metadata_bookkeeping_written": any(
            item.get("artifact_metadata_bookkeeping_written") for item in observed
        ),
        "job_state_scaffold_written": any(item.get("job_state_scaffold_written") for item in observed),
        "job_orchestration_scaffold_written": any(
            item.get("job_orchestration_scaffold_written") for item in observed
        ),
        "websocket_command_registered": any(item.get("websocket_command_registered") for item in observed),
    }
    return {
        "expected_forbidden": {key: False for key in RENDER_PLANNING_FORBIDDEN_SIDE_EFFECT_KEYS},
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }


def verify_job_orchestration_render_planning_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_render_planning_files(root)
    accepted = verify_scaffold_ready_snapshot_records_render_plan(root)
    idempotent = verify_repeated_snapshot_requests_reuse_render_plan(root)
    unknown_job = verify_unknown_render_plan_job_rejected_before_planning(root)
    cross_entry = verify_cross_config_entry_render_plan_rejected(root)
    isolation = verify_valid_render_plans_stay_config_entry_scoped(root)
    validation = verify_render_plans_and_chart_specs_validate(root)
    side_effects = verify_render_plan_side_effect_boundaries()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more render planning scaffold files are missing.")
    if not accepted["snapshot_dispatch"]["accepted"]:
        failures.append("Accepted render planning snapshot request did not return a WebSocket result.")
    if accepted["render_plan"] is None:
        failures.append("Render planning request did not store a render plan.")
    elif accepted["render_plan"]["render_plan_id"] != "render-plan-entry-render-plan-001":
        failures.append("Render plan did not use the deterministic render plan ID.")
    if accepted["render_plan"] and accepted["render_plan"]["artifact_id"] != "render-plan-entry-artifact-001":
        failures.append("Render plan did not reference the placeholder artifact metadata.")
    if accepted["render_plan"] and accepted["render_plan"]["source_snapshot_id"] != accepted["start_snapshot"]["snapshot_id"]:
        failures.append("Render plan did not reference the scaffold-ready source snapshot.")
    if idempotent["render_plan_count"] != 1 or idempotent["artifact_count"] != 1:
        failures.append("Repeated snapshot requests created duplicate render plan or artifact state.")
    if not idempotent["same_snapshot_returned"]:
        failures.append("Repeated snapshot request did not return the existing complete snapshot.")
    if not idempotent["same_render_plan_returned"]:
        failures.append("Repeated snapshot request did not return the existing render plan.")
    if unknown_job["error_codes"] != ["unknown_job"]:
        failures.append("Unknown render plan job did not fail closed with unknown_job.")
    if unknown_job["render_plans"]:
        failures.append("Unknown render plan job recorded render-plan metadata.")
    if cross_entry["error_codes"] != ["unknown_job"]:
        failures.append("Cross-config-entry render plan request did not fail closed as unknown_job.")
    if cross_entry["entry_b_render_plans"]:
        failures.append("Cross-config-entry render plan request recorded render-plan metadata in entry B.")
    if cross_entry["entry_b_artifacts"]:
        failures.append("Cross-config-entry render plan request recorded artifact metadata in entry B.")
    if cross_entry["entry_b_complete_snapshots"]:
        failures.append("Cross-config-entry render plan request appended a complete snapshot in entry B.")
    if len(isolation["entry_a"]["render_plans"]) != 1 or len(isolation["entry_b"]["render_plans"]) != 1:
        failures.append("Valid render plans did not stay isolated by config entry.")
    if not validation["accepted"]["render_plan_valid"]:
        failures.append("Accepted render plan did not validate.")
    if not validation["accepted"]["chart_spec_valid"]:
        failures.append("Accepted chart spec did not validate.")
    if not validation["isolation_entry_a"]["render_plan_valid"]:
        failures.append("Entry A render plan did not validate.")
    if not validation["isolation_entry_b"]["render_plan_valid"]:
        failures.append("Entry B render plan did not validate.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("Render planning scaffold reported forbidden side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("Render planning scaffold did not report expected allowed side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "accepted": accepted,
        "idempotent": idempotent,
        "unknown_job": unknown_job,
        "cross_entry": cross_entry,
        "isolation": isolation,
        "validation": validation,
        "side_effects": side_effects,
    }


def _render_plans(hass: Any, entry_id: str) -> list[dict[str, Any]]:
    store = hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION]
    return [
        deepcopy(store.get("render_plans", {})[render_plan_id])
        for render_plan_id in store.get("render_plan_order", [])
        if render_plan_id in store.get("render_plans", {})
    ]


def _latest_render_plan_from_dispatch(dispatch: dict[str, Any]) -> dict[str, Any] | None:
    handler_result = dispatch.get("handler_result")
    if not isinstance(handler_result, dict):
        return None
    job_orchestration = handler_result.get("job_orchestration")
    if not isinstance(job_orchestration, dict):
        return None
    render_plan = job_orchestration.get("render_plan")
    return deepcopy(render_plan) if isinstance(render_plan, dict) else None


def _orchestration_store_summary(hass: Any, entry_id: str) -> dict[str, Any]:
    return summarize_job_orchestration_store(hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION])


def _validate_render_plans(render_plans: list[dict[str, Any]], root) -> list[dict[str, Any]]:
    return [_validate_render_plan(render_plan, root) for render_plan in render_plans]


def _validate_render_plan(render_plan: dict[str, Any], root) -> dict[str, Any]:
    try:
        validate_contract("integration-render-plan", render_plan, repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "contract_validation_failed",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "render_plan_id": render_plan["render_plan_id"],
        "job_id": render_plan["job_id"],
        "source_snapshot_id": render_plan["source_snapshot_id"],
        "artifact_id": render_plan["artifact_id"],
        "status": render_plan["status"],
    }


def _validate_chart_specs(render_plans: list[dict[str, Any]], root) -> list[dict[str, Any]]:
    return [_validate_chart_spec(render_plan.get("chart_spec"), root) for render_plan in render_plans]


def _validate_chart_spec(chart_spec: Any, root) -> dict[str, Any]:
    try:
        validate_contract("chart-spec", chart_spec, repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "contract_validation_failed",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "chart_id": chart_spec["chart_id"],
        "chart_type": chart_spec["chart_type"],
        "series_entity_ids": [
            series["source"]["entity_id"]
            for series in chart_spec["series"]
            if isinstance(series.get("source"), dict) and series["source"].get("type") == "entity"
        ],
    }


def _snapshot_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "snapshot_id": snapshot["snapshot_id"],
        "job_id": snapshot["job_id"],
        "status": snapshot["status"],
        "progress": {
            "stage": snapshot["progress"]["stage"],
        },
        "chart": deepcopy(snapshot.get("chart")),
    }


def _artifact_summary(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_id": artifact["artifact_id"],
        "config_entry_id": artifact["config_entry_id"],
        "job_id": artifact["job_id"],
        "source_snapshot_id": artifact["source_snapshot_id"],
        "status": artifact["status"],
        "series": deepcopy(artifact["series"]),
    }


def _render_plan_summary(render_plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if render_plan is None:
        return None
    return {
        "render_plan_id": render_plan["render_plan_id"],
        "config_entry_id": render_plan["config_entry_id"],
        "job_id": render_plan["job_id"],
        "source_snapshot_id": render_plan["source_snapshot_id"],
        "artifact_id": render_plan["artifact_id"],
        "status": render_plan["status"],
        "render_mode": render_plan["render_mode"],
        "renderer": render_plan["renderer"],
        "history_entity_ids": deepcopy(render_plan["history_entity_ids"]),
        "chart_spec": deepcopy(render_plan["chart_spec"]),
        "output": deepcopy(render_plan["output"]),
        "validation": deepcopy(render_plan["validation"]),
        "warnings": deepcopy(render_plan["warnings"]),
    }
