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
from custom_components.isolinear.job_state import summarize_job_state_store
from custom_components.isolinear.model_provider import DATA_MODEL_PROVIDER_PLANNER

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
)
from .job_orchestration_render_planning_anchor import (
    _latest_render_plan_from_dispatch,
    _render_plans,
    _validate_chart_specs,
    _validate_render_plans,
)
from .job_orchestration_scaffold_anchor import _fake_hass, _first_result_payload, _run
from .websocket_command_registration_anchor import FakeWebSocketApiModule


MODEL_PROVIDER_PLANNING_FILES = [
    "custom_components/isolinear/job_orchestration.py",
    "custom_components/isolinear/model_provider.py",
    "custom_components/isolinear/websocket_api.py",
    "custom_components/isolinear/__init__.py",
    "docs/specs/home-assistant-job-orchestration-model-provider-planning-scaffold-spec.md",
    "bdd/integration/home-assistant-job-orchestration-model-provider-planning-scaffold-bdd.md",
    "bdd/integration/home-assistant-job-orchestration-model-provider-planning-scaffold-evidence.md",
    "docs/evals/home_assistant_job_orchestration_model_provider_planning_scaffold.yaml",
    "docs/schemas/integration-model-provider-plan.schema.json",
    "docs/schemas/planner-result.schema.json",
    "docs/schemas/integration-render-plan.schema.json",
    "docs/schemas/chart-spec.schema.json",
    "tests/test_job_orchestration_model_provider_planning_anchor.py",
    "evals/home_assistant_job_orchestration_model_provider_planning_scaffold.py",
    "src/Isolinear/job_orchestration_model_provider_planning_anchor.py",
]

MODEL_PROVIDER_PLANNING_FORBIDDEN_SIDE_EFFECT_KEYS = [
    key for key in NO_JOB_ORCHESTRATION_CALLS if key != "model_provider_called"
] + [
    "home_assistant_history_read",
    "history_retrieval_scaffold_written",
    "subscription_bookkeeping_written",
]


class FakeOllamaPlanner:
    provider_type = "ollama_compatible"
    role = "planner"

    def __init__(
        self,
        planner_result: dict[str, Any],
        *,
        endpoint_url: str = "http://ollama.local:11434",
        planner_model: str = "llama3.1",
    ) -> None:
        self.planner_result = deepcopy(planner_result)
        self.endpoint_url = endpoint_url
        self.planner_model = planner_model
        self.calls: list[dict[str, Any]] = []

    def provider_metadata(self) -> dict[str, str]:
        return {
            "type": self.provider_type,
            "role": self.role,
            "endpoint_url": self.endpoint_url,
            "model": self.planner_model,
        }

    def plan_chart(
        self,
        request: dict[str, Any],
        *,
        result_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "request": deepcopy(request),
                "result_schema_title": result_schema.get("title") if isinstance(result_schema, dict) else None,
            }
        )
        return {
            "accepted": True,
            "code": "fake_ollama_planner_result",
            "planner_result": deepcopy(self.planner_result),
            "provider": self.provider_metadata(),
        }


def verify_model_provider_planning_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in MODEL_PROVIDER_PLANNING_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_provider_produced_chart_spec_records_provider_plan(root=None) -> dict[str, Any]:
    root = root or repo_root()
    planner = FakeOllamaPlanner(_planner_result(_provider_chart_spec("provider-chart-001")))
    hass, websocket_api_module = _setup_provider_hass(
        FakeConfigEntry(
            "model-provider-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        planner,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "model-provider-entry",
        "Show sensor.upstairs_temperature",
        1,
    )
    start_snapshot = _first_result_payload(start)
    snapshot_dispatch = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "model-provider-entry",
        start_snapshot["job_id"],
        2,
    )
    artifact_snapshot = _first_result_payload(snapshot_dispatch)
    provider_plans = _provider_plans(hass, "model-provider-entry")
    render_plans = _render_plans(hass, "model-provider-entry")
    artifacts = _artifacts(hass, "model-provider-entry")
    job = _job(hass, "model-provider-entry", start_snapshot["job_id"])
    return {
        "start": start,
        "snapshot_dispatch": snapshot_dispatch,
        "planner_call_count": len(planner.calls),
        "planner_calls": deepcopy(planner.calls),
        "start_snapshot": _snapshot_summary(start_snapshot),
        "artifact_snapshot": _snapshot_summary(artifact_snapshot),
        "provider_plan": _provider_plan_summary(provider_plans[0]) if provider_plans else None,
        "provider_plans": [_provider_plan_summary(plan) for plan in provider_plans],
        "render_plan": _render_plan_summary(render_plans[0]) if render_plans else None,
        "render_plans": [_render_plan_summary(plan) for plan in render_plans],
        "artifact": _artifact_summary(artifacts[0]) if artifacts else None,
        "artifacts": [_artifact_summary(artifact) for artifact in artifacts],
        "complete_snapshots": [
            _snapshot_summary(snapshot)
            for snapshot in job["snapshots"]
            if snapshot.get("status") == "complete"
        ],
        "job_store": summarize_job_state_store(_job_store(hass, "model-provider-entry")),
        "orchestration_store": _orchestration_store_summary(hass, "model-provider-entry"),
        "provider_plan_validation": _validate_provider_plans(provider_plans, root),
        "planner_result_validation": _validate_planner_results(provider_plans, root),
        "chart_spec_validation": _validate_provider_chart_specs(provider_plans, root),
        "render_plan_validation": _validate_render_plans(render_plans, root),
    }


def verify_repeated_snapshot_requests_reuse_provider_plan(root=None) -> dict[str, Any]:
    root = root or repo_root()
    planner = FakeOllamaPlanner(_planner_result(_provider_chart_spec("provider-idempotent-chart")))
    hass, websocket_api_module = _setup_provider_hass(
        FakeConfigEntry(
            "model-provider-idempotent-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        planner,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "model-provider-idempotent-entry",
        "Show sensor.upstairs_temperature",
        10,
    )
    job_id = _first_result_payload(start)["job_id"]
    first = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "model-provider-idempotent-entry",
        job_id,
        11,
    )
    second = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "model-provider-idempotent-entry",
        job_id,
        12,
    )
    first_snapshot = _first_result_payload(first)
    second_snapshot = _first_result_payload(second)
    provider_plans = _provider_plans(hass, "model-provider-idempotent-entry")
    render_plans = _render_plans(hass, "model-provider-idempotent-entry")
    artifacts = _artifacts(hass, "model-provider-idempotent-entry")
    job = _job(hass, "model-provider-idempotent-entry", job_id)
    return {
        "first": first,
        "second": second,
        "first_snapshot": _snapshot_summary(first_snapshot),
        "second_snapshot": _snapshot_summary(second_snapshot),
        "first_provider_plan": _provider_plan_summary(_latest_provider_plan_from_dispatch(first)),
        "second_provider_plan": _provider_plan_summary(_latest_provider_plan_from_dispatch(second)),
        "first_render_plan": _render_plan_summary(_latest_render_plan_from_dispatch(first)),
        "second_render_plan": _render_plan_summary(_latest_render_plan_from_dispatch(second)),
        "planner_call_count": len(planner.calls),
        "same_snapshot_returned": first_snapshot == second_snapshot,
        "same_provider_plan_returned": _latest_provider_plan_from_dispatch(first)
        == _latest_provider_plan_from_dispatch(second),
        "same_render_plan_returned": _latest_render_plan_from_dispatch(first)
        == _latest_render_plan_from_dispatch(second),
        "provider_plans": [_provider_plan_summary(plan) for plan in provider_plans],
        "provider_plan_count": len(provider_plans),
        "render_plans": [_render_plan_summary(plan) for plan in render_plans],
        "render_plan_count": len(render_plans),
        "artifacts": [_artifact_summary(artifact) for artifact in artifacts],
        "artifact_count": len(artifacts),
        "complete_snapshot_count": len(
            [snapshot for snapshot in job["snapshots"] if snapshot.get("status") == "complete"]
        ),
        "provider_plan_validation": _validate_provider_plans(provider_plans, root),
        "planner_result_validation": _validate_planner_results(provider_plans, root),
        "chart_spec_validation": _validate_provider_chart_specs(provider_plans, root),
        "render_plan_validation": _validate_render_plans(render_plans, root),
    }


def verify_hidden_provider_entity_rejected_before_storage(root=None) -> dict[str, Any]:
    root = root or repo_root()
    chart_spec = _provider_chart_spec("hidden-entity-chart", entity_id="sensor.secret_temperature")
    planner = FakeOllamaPlanner(_planner_result(chart_spec))
    hass, websocket_api_module = _setup_provider_hass(
        FakeConfigEntry(
            "hidden-provider-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        planner,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "hidden-provider-entry",
        "Show sensor.upstairs_temperature",
        20,
    )
    job_id = _first_result_payload(start)["job_id"]
    snapshot = _dispatch_snapshot(hass, websocket_api_module, "hidden-provider-entry", job_id, 21)
    return _rejected_provider_snapshot_payload(
        root,
        hass=hass,
        entry_id="hidden-provider-entry",
        job_id=job_id,
        planner=planner,
        snapshot=snapshot,
    )


def verify_hidden_memory_proposal_entity_rejected(root=None) -> dict[str, Any]:
    """An off-allowlist entity in a persisted ``memory_proposals`` reference is a
    real, reusable reference and must still fail closed at creation time."""
    root = root or repo_root()
    case = _hidden_provider_output_case(
        root,
        entry_id="hidden-provider-memory-entry",
        planner_result_overrides={
            "memory_proposals": [
                {
                    "alias_id": "hidden-temperature",
                    "entity_id": "sensor.secret_temperature",
                }
            ],
        },
    )
    return {"case": case}


def verify_entity_named_chart_id_renders(root=None) -> dict[str, Any]:
    """A chart whose free-text fields contain entity-shaped tokens (a small
    model naming its chart after its own entity, e.g.
    ``sensor.upstairs_temperature_history``) must render, not be rejected as an
    off-allowlist reference. This reproduces the live 0.1.27 binary-door
    failure, where ``chart_id`` was mistaken for an entity reference."""
    root = root or repo_root()
    case = _hidden_provider_output_case(
        root,
        entry_id="entity-named-chart-id-entry",
        chart_spec_overrides={
            "chart_id": "sensor.upstairs_temperature_history",
            "notes": [
                "The model compared sensor.upstairs_temperature over time.",
            ],
        },
    )
    return {"case": case}


def verify_invalid_provider_chart_spec_rejected_before_storage(root=None) -> dict[str, Any]:
    root = root or repo_root()
    invalid_chart_spec = {
        "chart_id": "invalid-provider-chart",
        "chart_type": "time_series",
        "title": "Invalid Provider Chart",
        "time_range": {"type": "relative", "duration": "approved scaffold history window"},
    }
    planner = FakeOllamaPlanner(_planner_result(invalid_chart_spec))
    hass, websocket_api_module = _setup_provider_hass(
        FakeConfigEntry(
            "invalid-provider-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        planner,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "invalid-provider-entry",
        "Show sensor.upstairs_temperature",
        30,
    )
    job_id = _first_result_payload(start)["job_id"]
    snapshot = _dispatch_snapshot(hass, websocket_api_module, "invalid-provider-entry", job_id, 31)
    return _rejected_provider_snapshot_payload(
        root,
        hass=hass,
        entry_id="invalid-provider-entry",
        job_id=job_id,
        planner=planner,
        snapshot=snapshot,
    )


def verify_unknown_model_provider_job_rejected_before_call(root=None) -> dict[str, Any]:
    root = root or repo_root()
    planner = FakeOllamaPlanner(_planner_result(_provider_chart_spec("unknown-chart")))
    hass, websocket_api_module = _setup_provider_hass(
        FakeConfigEntry(
            "unknown-provider-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        planner,
    )
    snapshot = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "unknown-provider-entry",
        "unknown-provider-entry-job-404",
        40,
    )
    return {
        "snapshot": snapshot,
        "planner_call_count": len(planner.calls),
        "error_codes": _error_codes(snapshot),
        "job_store": summarize_job_state_store(_job_store(hass, "unknown-provider-entry")),
        "provider_plans": _provider_plans(hass, "unknown-provider-entry"),
        "render_plans": _render_plans(hass, "unknown-provider-entry"),
        "artifacts": _artifacts(hass, "unknown-provider-entry"),
        "provider_plan_validation": _validate_provider_plans([], root),
    }


def verify_cross_config_entry_model_provider_rejected_before_call(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "provider-cross-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "provider-cross-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    planner_a = _install_fake_planner(
        hass,
        "provider-cross-entry-a",
        _planner_result(_provider_chart_spec("cross-entry-a-chart")),
    )
    planner_b = _install_fake_planner(
        hass,
        "provider-cross-entry-b",
        _planner_result(_provider_chart_spec("cross-entry-b-chart", entity_id="binary_sensor.office_window")),
    )
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "provider-cross-entry-a",
        "Show sensor.upstairs_temperature",
        50,
    )
    start_b = _dispatch_start(
        hass,
        websocket_api_module,
        "provider-cross-entry-b",
        "Show binary_sensor.office_window",
        51,
    )
    snapshot_a = _first_result_payload(start_a)
    snapshot_b = _first_result_payload(start_b)
    cross_snapshot = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "provider-cross-entry-b",
        snapshot_a["job_id"],
        52,
    )
    return {
        "entry_a_start": start_a,
        "entry_b_start": start_b,
        "entry_a_start_snapshot": _snapshot_summary(snapshot_a),
        "entry_b_start_snapshot": _snapshot_summary(snapshot_b),
        "cross_snapshot": cross_snapshot,
        "entry_a_planner_call_count": len(planner_a.calls),
        "entry_b_planner_call_count": len(planner_b.calls),
        "error_codes": _error_codes(cross_snapshot),
        "entry_a_provider_plans": _provider_plans(hass, "provider-cross-entry-a"),
        "entry_b_provider_plans": _provider_plans(hass, "provider-cross-entry-b"),
        "entry_b_render_plans": _render_plans(hass, "provider-cross-entry-b"),
        "entry_b_artifacts": _artifacts(hass, "provider-cross-entry-b"),
        "entry_b_complete_snapshots": _complete_snapshots(hass, "provider-cross-entry-b", snapshot_b["job_id"]),
        "provider_plan_validation": _validate_provider_plans([], root),
    }


def verify_model_provider_plans_stay_config_entry_scoped(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "provider-isolation-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "provider-isolation-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    planner_a = _install_fake_planner(
        hass,
        "provider-isolation-entry-a",
        _planner_result(_provider_chart_spec("provider-isolation-a-chart")),
    )
    planner_b = _install_fake_planner(
        hass,
        "provider-isolation-entry-b",
        _planner_result(
            _provider_chart_spec(
                "provider-isolation-b-chart",
                entity_id="binary_sensor.office_window",
                title="Provider Office Window",
                chart_type="timeline",
                render_as="step",
            )
        ),
    )
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "provider-isolation-entry-a",
        "Show sensor.upstairs_temperature",
        60,
    )
    start_b = _dispatch_start(
        hass,
        websocket_api_module,
        "provider-isolation-entry-b",
        "Show binary_sensor.office_window",
        61,
    )
    snapshot_a = _first_result_payload(start_a)
    snapshot_b = _first_result_payload(start_b)
    plan_a = _dispatch_snapshot(hass, websocket_api_module, "provider-isolation-entry-a", snapshot_a["job_id"], 62)
    plan_b = _dispatch_snapshot(hass, websocket_api_module, "provider-isolation-entry-b", snapshot_b["job_id"], 63)
    provider_plans_a = _provider_plans(hass, "provider-isolation-entry-a")
    provider_plans_b = _provider_plans(hass, "provider-isolation-entry-b")
    render_plans_a = _render_plans(hass, "provider-isolation-entry-a")
    render_plans_b = _render_plans(hass, "provider-isolation-entry-b")
    return {
        "entry_a": {
            "start": start_a,
            "snapshot": plan_a,
            "planner_call_count": len(planner_a.calls),
            "provider_plans": [_provider_plan_summary(plan) for plan in provider_plans_a],
            "render_plans": [_render_plan_summary(plan) for plan in render_plans_a],
            "artifacts": [_artifact_summary(artifact) for artifact in _artifacts(hass, "provider-isolation-entry-a")],
            "orchestration_store": _orchestration_store_summary(hass, "provider-isolation-entry-a"),
            "provider_plan_validation": _validate_provider_plans(provider_plans_a, root),
            "planner_result_validation": _validate_planner_results(provider_plans_a, root),
            "chart_spec_validation": _validate_provider_chart_specs(provider_plans_a, root),
            "render_plan_validation": _validate_render_plans(render_plans_a, root),
        },
        "entry_b": {
            "start": start_b,
            "snapshot": plan_b,
            "planner_call_count": len(planner_b.calls),
            "provider_plans": [_provider_plan_summary(plan) for plan in provider_plans_b],
            "render_plans": [_render_plan_summary(plan) for plan in render_plans_b],
            "artifacts": [_artifact_summary(artifact) for artifact in _artifacts(hass, "provider-isolation-entry-b")],
            "orchestration_store": _orchestration_store_summary(hass, "provider-isolation-entry-b"),
            "provider_plan_validation": _validate_provider_plans(provider_plans_b, root),
            "planner_result_validation": _validate_planner_results(provider_plans_b, root),
            "chart_spec_validation": _validate_provider_chart_specs(provider_plans_b, root),
            "render_plan_validation": _validate_render_plans(render_plans_b, root),
        },
    }


def verify_model_provider_schema_validation(root=None) -> dict[str, Any]:
    root = root or repo_root()
    accepted = verify_provider_produced_chart_spec_records_provider_plan(root)
    idempotent = verify_repeated_snapshot_requests_reuse_provider_plan(root)
    isolation = verify_model_provider_plans_stay_config_entry_scoped(root)
    return {
        "accepted": _validation_summary(accepted),
        "idempotent": _validation_summary(idempotent),
        "isolation_entry_a": _validation_summary(isolation["entry_a"]),
        "isolation_entry_b": _validation_summary(isolation["entry_b"]),
    }


def verify_model_provider_plan_side_effect_boundaries() -> dict[str, Any]:
    accepted = verify_provider_produced_chart_spec_records_provider_plan()
    idempotent = verify_repeated_snapshot_requests_reuse_provider_plan()
    hidden = verify_hidden_provider_entity_rejected_before_storage()
    invalid = verify_invalid_provider_chart_spec_rejected_before_storage()
    unknown = verify_unknown_model_provider_job_rejected_before_call()
    cross_entry = verify_cross_config_entry_model_provider_rejected_before_call()
    isolation = verify_model_provider_plans_stay_config_entry_scoped()
    setup = _setup_provider_hass(
        FakeConfigEntry(
            "side-effects-provider-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        FakeOllamaPlanner(_planner_result(_provider_chart_spec("side-effects-chart"))),
    )[0].data[DOMAIN]["side-effects-provider-entry"]

    observed = [
        {"name": "accepted_provider_snapshot", **accepted["snapshot_dispatch"]["orchestration"]},
        {"name": "idempotent_first_snapshot", **idempotent["first"]["orchestration"]},
        {"name": "idempotent_second_snapshot", **idempotent["second"]["orchestration"]},
        {"name": "hidden_entity_failure", **hidden["snapshot"]["orchestration"]},
        {"name": "invalid_chart_spec_failure", **invalid["snapshot"]["orchestration"]},
        {"name": "unknown_provider_job", **unknown["snapshot"]["orchestration"]},
        {"name": "cross_config_entry", **cross_entry["cross_snapshot"]["orchestration"]},
        {"name": "entry_a_provider_plan", **isolation["entry_a"]["snapshot"]["orchestration"]},
        {"name": "entry_b_provider_plan", **isolation["entry_b"]["snapshot"]["orchestration"]},
        {"name": "setup_orchestration", **setup[DATA_JOB_ORCHESTRATION_SETUP]["orchestration"]},
        {"name": "websocket_registration", **setup["websocket_api"]["orchestration"]},
    ]

    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in MODEL_PROVIDER_PLANNING_FORBIDDEN_SIDE_EFFECT_KEYS
    }
    allowed_aggregate = {
        "model_provider_called": any(item.get("model_provider_called") for item in observed),
        "model_provider_plan_bookkeeping_written": any(
            item.get("model_provider_plan_bookkeeping_written") for item in observed
        ),
        "render_plan_bookkeeping_written": any(item.get("render_plan_bookkeeping_written") for item in observed),
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
        "expected_forbidden": {key: False for key in MODEL_PROVIDER_PLANNING_FORBIDDEN_SIDE_EFFECT_KEYS},
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }


def verify_job_orchestration_model_provider_planning_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_model_provider_planning_files(root)
    accepted = verify_provider_produced_chart_spec_records_provider_plan(root)
    idempotent = verify_repeated_snapshot_requests_reuse_provider_plan(root)
    hidden = verify_hidden_provider_entity_rejected_before_storage(root)
    hidden_memory = verify_hidden_memory_proposal_entity_rejected(root)
    entity_named_chart_id = verify_entity_named_chart_id_renders(root)
    invalid = verify_invalid_provider_chart_spec_rejected_before_storage(root)
    unknown_job = verify_unknown_model_provider_job_rejected_before_call(root)
    cross_entry = verify_cross_config_entry_model_provider_rejected_before_call(root)
    isolation = verify_model_provider_plans_stay_config_entry_scoped(root)
    validation = verify_model_provider_schema_validation(root)
    side_effects = verify_model_provider_plan_side_effect_boundaries()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more model-provider planning scaffold files are missing.")
    if not accepted["snapshot_dispatch"]["accepted"]:
        failures.append("Accepted model-provider snapshot request did not return a WebSocket result.")
    if accepted["planner_call_count"] != 1:
        failures.append("Accepted model-provider snapshot request did not call the planner exactly once.")
    if accepted["provider_plan"] is None:
        failures.append("Model-provider snapshot request did not store a provider plan.")
    elif accepted["provider_plan"]["provider_plan_id"] != "model-provider-entry-provider-plan-001":
        failures.append("Provider plan did not use the deterministic provider plan ID.")
    if accepted["render_plan"] and "placeholder_chart_spec" in accepted["render_plan"]["warnings"]:
        failures.append("Provider-produced render plan still reported placeholder chart spec.")
    if idempotent["planner_call_count"] != 1:
        failures.append("Repeated snapshot request called the provider more than once.")
    if idempotent["provider_plan_count"] != 1 or idempotent["render_plan_count"] != 1 or idempotent["artifact_count"] != 1:
        failures.append("Repeated snapshot requests created duplicate provider, render, or artifact state.")
    if not idempotent["same_snapshot_returned"]:
        failures.append("Repeated snapshot request did not return the existing complete snapshot.")
    if hidden["error_codes"] != ["model_provider_referenced_unapproved_entity"]:
        failures.append(
            "Hidden provider entity did not fail closed with model_provider_referenced_unapproved_entity."
        )
    if hidden["provider_plans"] or hidden["render_plans"] or hidden["artifacts"] or hidden["complete_snapshots"]:
        failures.append("Hidden provider entity failure stored state after rejection.")
    memory_case = hidden_memory["case"]
    if memory_case["error_codes"] != ["model_provider_referenced_unapproved_entity"]:
        failures.append("Off-allowlist memory_proposals entity did not fail closed.")
    if (
        memory_case["provider_plans"]
        or memory_case["render_plans"]
        or memory_case["artifacts"]
        or memory_case["complete_snapshots"]
    ):
        failures.append("Off-allowlist memory_proposals entity stored state after rejection.")
    chart_id_case = entity_named_chart_id["case"]
    if chart_id_case["error_codes"]:
        failures.append(
            "Entity-named chart_id was rejected instead of rendered: "
            f"{chart_id_case['error_codes']}."
        )
    if not chart_id_case["complete_snapshots"]:
        failures.append("Entity-named chart_id did not produce a complete snapshot.")
    if invalid["error_codes"] != ["invalid_model_provider_chart_spec"]:
        failures.append("Invalid provider chart spec did not fail closed with invalid_model_provider_chart_spec.")
    if invalid["provider_plans"] or invalid["render_plans"] or invalid["artifacts"] or invalid["complete_snapshots"]:
        failures.append("Invalid provider chart spec failure stored state after rejection.")
    if unknown_job["planner_call_count"] != 0 or unknown_job["error_codes"] != ["unknown_job"]:
        failures.append("Unknown model-provider job did not fail before provider call.")
    if cross_entry["entry_a_planner_call_count"] != 0 or cross_entry["entry_b_planner_call_count"] != 0:
        failures.append("Cross-config-entry request called a provider.")
    if cross_entry["error_codes"] != ["unknown_job"]:
        failures.append("Cross-config-entry model-provider request did not fail closed as unknown_job.")
    if cross_entry["entry_b_provider_plans"] or cross_entry["entry_b_render_plans"] or cross_entry["entry_b_artifacts"]:
        failures.append("Cross-config-entry model-provider request recorded entry B state.")
    if len(isolation["entry_a"]["provider_plans"]) != 1 or len(isolation["entry_b"]["provider_plans"]) != 1:
        failures.append("Valid provider plans did not stay isolated by config entry.")
    if not validation["accepted"]["provider_plan_valid"]:
        failures.append("Accepted provider plan did not validate.")
    if not validation["accepted"]["planner_result_valid"]:
        failures.append("Accepted planner result did not validate.")
    if not validation["accepted"]["chart_spec_valid"]:
        failures.append("Accepted provider chart spec did not validate.")
    if not validation["accepted"]["render_plan_valid"]:
        failures.append("Accepted render plan did not validate.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("Model-provider planning scaffold reported forbidden side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("Model-provider planning scaffold did not report expected allowed side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "accepted": accepted,
        "idempotent": idempotent,
        "hidden": hidden,
        "hidden_memory": hidden_memory,
        "entity_named_chart_id": entity_named_chart_id,
        "invalid": invalid,
        "unknown_job": unknown_job,
        "cross_entry": cross_entry,
        "isolation": isolation,
        "validation": validation,
        "side_effects": side_effects,
    }


def _hidden_provider_output_case(
    root,
    *,
    entry_id: str,
    chart_spec_overrides: dict[str, Any] | None = None,
    planner_result_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    chart_spec = _provider_chart_spec(f"{entry_id}-chart")
    chart_spec.update(deepcopy(chart_spec_overrides or {}))
    planner_result = _planner_result(chart_spec)
    planner_result.update(deepcopy(planner_result_overrides or {}))
    planner = FakeOllamaPlanner(planner_result)
    hass, websocket_api_module = _setup_provider_hass(
        FakeConfigEntry(
            entry_id,
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        planner,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        entry_id,
        "Show sensor.upstairs_temperature",
        70,
    )
    job_id = _first_result_payload(start)["job_id"]
    snapshot = _dispatch_snapshot(hass, websocket_api_module, entry_id, job_id, 71)
    return _rejected_provider_snapshot_payload(
        root,
        hass=hass,
        entry_id=entry_id,
        job_id=job_id,
        planner=planner,
        snapshot=snapshot,
    )


def _setup_provider_hass(
    entry: FakeConfigEntry,
    planner: FakeOllamaPlanner,
) -> tuple[Any, FakeWebSocketApiModule]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    setup_accepted = _run(async_setup_entry(hass, entry))
    if not setup_accepted:
        raise AssertionError(f"async_setup_entry rejected {entry.entry_id}")
    hass.data[DOMAIN][entry.entry_id][DATA_MODEL_PROVIDER_PLANNER] = planner
    return hass, websocket_api_module


def _install_fake_planner(
    hass: Any,
    entry_id: str,
    planner_result: dict[str, Any],
) -> FakeOllamaPlanner:
    planner = FakeOllamaPlanner(planner_result)
    hass.data[DOMAIN][entry_id][DATA_MODEL_PROVIDER_PLANNER] = planner
    return planner


def _provider_chart_spec(
    chart_id: str,
    *,
    entity_id: str = "sensor.upstairs_temperature",
    title: str = "Provider Upstairs Temperature",
    chart_type: str = "time_series",
    render_as: str = "line",
) -> dict[str, Any]:
    return {
        "chart_id": chart_id,
        "chart_type": chart_type,
        "title": title,
        "time_range": {
            "type": "relative",
            "duration": "approved scaffold history window",
        },
        "series": [
            {
                "series_id": "series-001",
                "label": title,
                "source": {
                    "type": "entity",
                    "entity_id": entity_id,
                    "attribute": None,
                },
                "role": "primary",
                "render_as": render_as,
                "transform": {
                    "operation": "none",
                    "window": None,
                },
                "unit": None,
            }
        ],
        "overlays": [],
        "x_axis": {
            "type": "time",
        },
        "y_axis": {},
        "notes": [
            "model_provider_planning_scaffold",
            "provider_produced_chart_spec",
        ],
    }


def _planner_result(chart_spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "chart_spec_ready",
        "chart_spec": deepcopy(chart_spec),
        "clarification_question": None,
        "memory_proposals": [],
        "reasoning_summary": "Fake planner selected an approved entity-backed chart spec.",
        "warnings": ["fake_ollama_planner"],
    }


def _provider_plans(hass: Any, entry_id: str) -> list[dict[str, Any]]:
    store = hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION]
    return [
        deepcopy(store.get("model_provider_plans", {})[provider_plan_id])
        for provider_plan_id in store.get("model_provider_plan_order", [])
        if provider_plan_id in store.get("model_provider_plans", {})
    ]


def _latest_provider_plan_from_dispatch(dispatch: dict[str, Any]) -> dict[str, Any] | None:
    handler_result = dispatch.get("handler_result")
    if not isinstance(handler_result, dict):
        return None
    job_orchestration = handler_result.get("job_orchestration")
    if not isinstance(job_orchestration, dict):
        return None
    provider_plan = job_orchestration.get("model_provider_plan")
    return deepcopy(provider_plan) if isinstance(provider_plan, dict) else None


def _rejected_provider_snapshot_payload(
    root,
    *,
    hass: Any,
    entry_id: str,
    job_id: str,
    planner: FakeOllamaPlanner,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    provider_plans = _provider_plans(hass, entry_id)
    render_plans = _render_plans(hass, entry_id)
    artifacts = _artifacts(hass, entry_id)
    complete_snapshots = _complete_snapshots(hass, entry_id, job_id)
    return {
        "snapshot": snapshot,
        "planner_call_count": len(planner.calls),
        "planner_calls": deepcopy(planner.calls),
        "error_codes": _error_codes(snapshot),
        "provider_plans": [_provider_plan_summary(plan) for plan in provider_plans],
        "render_plans": [_render_plan_summary(plan) for plan in render_plans],
        "artifacts": [_artifact_summary(artifact) for artifact in artifacts],
        "complete_snapshots": [_snapshot_summary(item) for item in complete_snapshots],
        "orchestration_store": _orchestration_store_summary(hass, entry_id),
        "provider_plan_validation": _validate_provider_plans(provider_plans, root),
    }


def _orchestration_store_summary(hass: Any, entry_id: str) -> dict[str, Any]:
    return summarize_job_orchestration_store(hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION])


def _validate_provider_plans(provider_plans: list[dict[str, Any]], root) -> list[dict[str, Any]]:
    return [_validate_provider_plan(provider_plan, root) for provider_plan in provider_plans]


def _validate_provider_plan(provider_plan: dict[str, Any], root) -> dict[str, Any]:
    try:
        validate_contract("integration-model-provider-plan", provider_plan, repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "contract_validation_failed",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "provider_plan_id": provider_plan["provider_plan_id"],
        "job_id": provider_plan["job_id"],
        "source_snapshot_id": provider_plan["source_snapshot_id"],
        "status": provider_plan["status"],
    }


def _validate_planner_results(provider_plans: list[dict[str, Any]], root) -> list[dict[str, Any]]:
    return [_validate_planner_result(provider_plan.get("planner_result"), root) for provider_plan in provider_plans]


def _validate_planner_result(planner_result: Any, root) -> dict[str, Any]:
    try:
        validate_contract("planner-result", planner_result, repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "contract_validation_failed",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "status": planner_result["status"],
    }


def _validate_provider_chart_specs(provider_plans: list[dict[str, Any]], root) -> list[dict[str, Any]]:
    return [_validate_provider_chart_spec(provider_plan.get("chart_spec"), root) for provider_plan in provider_plans]


def _validate_provider_chart_spec(chart_spec: Any, root) -> dict[str, Any]:
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


def _validation_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider_plan_valid": all(item["accepted"] for item in result["provider_plan_validation"]),
        "planner_result_valid": all(item["accepted"] for item in result["planner_result_validation"]),
        "chart_spec_valid": all(item["accepted"] for item in result["chart_spec_validation"]),
        "render_plan_valid": all(item["accepted"] for item in result["render_plan_validation"]),
        "provider_plan_validation": result["provider_plan_validation"],
        "planner_result_validation": result["planner_result_validation"],
        "chart_spec_validation": result["chart_spec_validation"],
        "render_plan_validation": result["render_plan_validation"],
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


def _provider_plan_summary(provider_plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if provider_plan is None:
        return None
    return {
        "provider_plan_id": provider_plan["provider_plan_id"],
        "config_entry_id": provider_plan["config_entry_id"],
        "job_id": provider_plan["job_id"],
        "source_snapshot_id": provider_plan["source_snapshot_id"],
        "provider": deepcopy(provider_plan["provider"]),
        "request": deepcopy(provider_plan["request"]),
        "status": provider_plan["status"],
        "planner_result": deepcopy(provider_plan["planner_result"]),
        "chart_spec": deepcopy(provider_plan["chart_spec"]),
        "validation": deepcopy(provider_plan["validation"]),
        "warnings": deepcopy(provider_plan["warnings"]),
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
