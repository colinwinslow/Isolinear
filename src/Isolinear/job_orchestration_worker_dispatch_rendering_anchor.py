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
from custom_components.isolinear.worker_renderer import (
    DATA_WORKER_RENDER_CLIENT,
    redacted_worker_transport_request,
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
)
from .job_orchestration_render_planning_anchor import (
    _latest_render_plan_from_dispatch,
    _render_plans,
    _validate_chart_specs,
    _validate_render_plans,
)
from .job_orchestration_scaffold_anchor import _fake_hass, _first_result_payload, _run
from .websocket_command_registration_anchor import FakeWebSocketApiModule


WORKER_TEST_TOKEN = "test-worker-dispatch-token-000000000"

WORKER_DISPATCH_RENDERING_FILES = [
    "custom_components/isolinear/job_orchestration.py",
    "custom_components/isolinear/worker_renderer.py",
    "custom_components/isolinear/websocket_api.py",
    "custom_components/isolinear/__init__.py",
    "docs/specs/home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-spec.md",
    "bdd/integration/home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-bdd.md",
    "bdd/integration/home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-evidence.md",
    "docs/evals/home_assistant_job_orchestration_worker_dispatch_rendering_scaffold.yaml",
    "docs/schemas/integration-worker-dispatch.schema.json",
    "docs/schemas/worker-transport-request.schema.json",
    "docs/schemas/render-request.schema.json",
    "docs/schemas/render-result.schema.json",
    "docs/schemas/integration-render-plan.schema.json",
    "docs/schemas/chart-spec.schema.json",
    "docs/schemas/history-series.schema.json",
    "tests/test_job_orchestration_worker_dispatch_rendering_anchor.py",
    "evals/home_assistant_job_orchestration_worker_dispatch_rendering_scaffold.py",
    "src/Isolinear/job_orchestration_worker_dispatch_rendering_anchor.py",
]

WORKER_DISPATCH_FORBIDDEN_SIDE_EFFECT_KEYS = [
    key
    for key in NO_JOB_ORCHESTRATION_CALLS
    if key not in {"worker_called", "chart_rendering_called"}
] + [
    "home_assistant_history_read",
    "history_retrieval_scaffold_written",
    "subscription_bookkeeping_written",
    "model_provider_called",
]


class FakeWorkerRenderer:
    provider_type = "http_json_worker"
    role = "renderer"
    api_version = 1

    def __init__(
        self,
        *,
        endpoint_url: str = "http://worker.local:8765",
        worker_token: str = WORKER_TEST_TOKEN,
        fail_code: str | None = None,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.worker_token = worker_token
        self.fail_code = fail_code
        self.calls: list[dict[str, Any]] = []

    def provider_metadata(self) -> dict[str, Any]:
        return {
            "type": self.provider_type,
            "role": self.role,
            "endpoint_url": self.endpoint_url,
            "api_version": self.api_version,
        }

    def render_chart(self, transport_request: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"request": deepcopy(transport_request)})
        render_request = transport_request["body"]["render_request"]
        if self.fail_code is not None:
            return {
                "accepted": True,
                "code": "fake_worker_render_failed",
                "worker": self.provider_metadata(),
                "render_result": {
                    "request_id": render_request["request_id"],
                    "status": "failed",
                    "image_id": None,
                    "image_mime_type": None,
                    "image_path": None,
                    "error": {
                        "code": self.fail_code,
                        "message": "Fake worker failed before a rendered artifact was accepted.",
                        "details": {},
                    },
                    "render_metadata": {},
                },
            }

        chart_spec = render_request["chart_spec"]
        return {
            "accepted": True,
            "code": "fake_worker_render_result",
            "worker": self.provider_metadata(),
            "render_result": {
                "request_id": render_request["request_id"],
                "status": "success",
                "image_id": f"{render_request['request_id']}-image",
                "image_mime_type": "image/png",
                "image_path": f"worker://{render_request['request_id']}.png",
                "error": None,
                "render_metadata": {
                    "title": chart_spec["title"],
                    "series_plotted": [series["series_id"] for series in chart_spec["series"]],
                    "overlays_plotted": [],
                    "warnings": ["fake_worker_renderer"],
                    "codegen_attempts": 0,
                },
            },
        }


def verify_worker_dispatch_rendering_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in WORKER_DISPATCH_RENDERING_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_worker_dispatch_records_render_result(root=None) -> dict[str, Any]:
    root = root or repo_root()
    worker = FakeWorkerRenderer()
    hass, websocket_api_module = _setup_worker_hass(
        FakeConfigEntry(
            "worker-dispatch-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        worker,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-dispatch-entry",
        "Show sensor.upstairs_temperature",
        1,
    )
    start_snapshot = _first_result_payload(start)
    snapshot_dispatch = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "worker-dispatch-entry",
        start_snapshot["job_id"],
        2,
    )
    artifact_snapshot = _first_result_payload(snapshot_dispatch)
    worker_dispatches = _worker_dispatches(hass, "worker-dispatch-entry")
    render_plans = _render_plans(hass, "worker-dispatch-entry")
    artifacts = _artifacts(hass, "worker-dispatch-entry")
    job = _job(hass, "worker-dispatch-entry", start_snapshot["job_id"])
    return {
        "start": start,
        "snapshot_dispatch": snapshot_dispatch,
        "worker_call_count": len(worker.calls),
        "worker_calls": _worker_call_summaries(worker),
        "start_snapshot": _snapshot_summary(start_snapshot),
        "artifact_snapshot": _snapshot_summary(artifact_snapshot),
        "worker_dispatch": _worker_dispatch_summary(worker_dispatches[0]) if worker_dispatches else None,
        "worker_dispatches": [_worker_dispatch_summary(dispatch) for dispatch in worker_dispatches],
        "render_plan": _render_plan_summary(render_plans[0]) if render_plans else None,
        "render_plans": [_render_plan_summary(plan) for plan in render_plans],
        "artifact": _artifact_summary(artifacts[0]) if artifacts else None,
        "artifacts": [_artifact_summary(artifact) for artifact in artifacts],
        "complete_snapshots": [
            _snapshot_summary(snapshot)
            for snapshot in job["snapshots"]
            if snapshot.get("status") == "complete"
        ],
        "job_store": summarize_job_state_store(_job_store(hass, "worker-dispatch-entry")),
        "orchestration_store": _orchestration_store_summary(hass, "worker-dispatch-entry"),
        "worker_dispatch_validation": _validate_worker_dispatches(worker_dispatches, root),
        "worker_transport_validation": _validate_worker_transport_requests(worker.calls, root),
        "render_request_validation": _validate_render_requests(worker.calls, root),
        "render_result_validation": _validate_worker_dispatch_render_results(worker_dispatches, root),
        "render_plan_validation": _validate_render_plans(render_plans, root),
        "chart_spec_validation": _validate_chart_specs(render_plans, root),
        "history_series_validation": _validate_worker_history_series(worker.calls, root),
    }


def verify_repeated_snapshot_requests_reuse_worker_dispatch(root=None) -> dict[str, Any]:
    root = root or repo_root()
    worker = FakeWorkerRenderer()
    hass, websocket_api_module = _setup_worker_hass(
        FakeConfigEntry(
            "worker-idempotent-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        worker,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-idempotent-entry",
        "Show sensor.upstairs_temperature",
        10,
    )
    job_id = _first_result_payload(start)["job_id"]
    first = _dispatch_snapshot(hass, websocket_api_module, "worker-idempotent-entry", job_id, 11)
    second = _dispatch_snapshot(hass, websocket_api_module, "worker-idempotent-entry", job_id, 12)
    first_snapshot = _first_result_payload(first)
    second_snapshot = _first_result_payload(second)
    first_dispatch = _latest_worker_dispatch_from_dispatch(first)
    second_dispatch = _latest_worker_dispatch_from_dispatch(second)
    render_plans = _render_plans(hass, "worker-idempotent-entry")
    worker_dispatches = _worker_dispatches(hass, "worker-idempotent-entry")
    artifacts = _artifacts(hass, "worker-idempotent-entry")
    job = _job(hass, "worker-idempotent-entry", job_id)
    return {
        "first": first,
        "second": second,
        "first_snapshot": _snapshot_summary(first_snapshot),
        "second_snapshot": _snapshot_summary(second_snapshot),
        "first_worker_dispatch": _worker_dispatch_summary(first_dispatch),
        "second_worker_dispatch": _worker_dispatch_summary(second_dispatch),
        "worker_call_count": len(worker.calls),
        "same_snapshot_returned": first_snapshot == second_snapshot,
        "same_worker_dispatch_returned": first_dispatch == second_dispatch,
        "worker_dispatch_count": len(worker_dispatches),
        "render_plan_count": len(render_plans),
        "artifact_count": len(artifacts),
        "complete_snapshot_count": len(
            [snapshot for snapshot in job["snapshots"] if snapshot.get("status") == "complete"]
        ),
        "worker_dispatch_validation": _validate_worker_dispatches(worker_dispatches, root),
    }


def verify_worker_failure_rejected_before_storage(root=None) -> dict[str, Any]:
    root = root or repo_root()
    worker = FakeWorkerRenderer(fail_code="worker_safe_renderer_failed")
    hass, websocket_api_module = _setup_worker_hass(
        FakeConfigEntry(
            "worker-failure-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        worker,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-failure-entry",
        "Show sensor.upstairs_temperature",
        20,
    )
    job_id = _first_result_payload(start)["job_id"]
    snapshot = _dispatch_snapshot(hass, websocket_api_module, "worker-failure-entry", job_id, 21)
    return {
        "snapshot": snapshot,
        "worker_call_count": len(worker.calls),
        "worker_calls": _worker_call_summaries(worker),
        "error_codes": _error_codes(snapshot),
        "worker_dispatches": _worker_dispatches(hass, "worker-failure-entry"),
        "render_plans": _render_plans(hass, "worker-failure-entry"),
        "artifacts": _artifacts(hass, "worker-failure-entry"),
        "complete_snapshots": _complete_snapshots(hass, "worker-failure-entry", job_id),
        "worker_transport_validation": _validate_worker_transport_requests(worker.calls, root),
        "render_request_validation": _validate_render_requests(worker.calls, root),
    }


def verify_unknown_worker_job_rejected_before_call(root=None) -> dict[str, Any]:
    root = root or repo_root()
    worker = FakeWorkerRenderer()
    hass, websocket_api_module = _setup_worker_hass(
        FakeConfigEntry(
            "unknown-worker-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        worker,
    )
    snapshot = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "unknown-worker-entry",
        "unknown-worker-entry-job-404",
        30,
    )
    return {
        "snapshot": snapshot,
        "worker_call_count": len(worker.calls),
        "error_codes": _error_codes(snapshot),
        "job_store": summarize_job_state_store(_job_store(hass, "unknown-worker-entry")),
        "worker_dispatches": _worker_dispatches(hass, "unknown-worker-entry"),
        "render_plans": _render_plans(hass, "unknown-worker-entry"),
        "artifacts": _artifacts(hass, "unknown-worker-entry"),
    }


def verify_cross_config_entry_worker_rejected_before_call(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "worker-cross-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "worker-cross-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    worker_a = _install_fake_worker(hass, "worker-cross-entry-a", FakeWorkerRenderer())
    worker_b = _install_fake_worker(hass, "worker-cross-entry-b", FakeWorkerRenderer())
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-cross-entry-a",
        "Show sensor.upstairs_temperature",
        40,
    )
    start_b = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-cross-entry-b",
        "Show binary_sensor.office_window",
        41,
    )
    snapshot_a = _first_result_payload(start_a)
    snapshot_b = _first_result_payload(start_b)
    cross_snapshot = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "worker-cross-entry-b",
        snapshot_a["job_id"],
        42,
    )
    return {
        "entry_a_start": start_a,
        "entry_b_start": start_b,
        "entry_a_start_snapshot": _snapshot_summary(snapshot_a),
        "entry_b_start_snapshot": _snapshot_summary(snapshot_b),
        "cross_snapshot": cross_snapshot,
        "entry_a_worker_call_count": len(worker_a.calls),
        "entry_b_worker_call_count": len(worker_b.calls),
        "error_codes": _error_codes(cross_snapshot),
        "entry_b_worker_dispatches": _worker_dispatches(hass, "worker-cross-entry-b"),
        "entry_b_render_plans": _render_plans(hass, "worker-cross-entry-b"),
        "entry_b_artifacts": _artifacts(hass, "worker-cross-entry-b"),
        "entry_b_complete_snapshots": _complete_snapshots(hass, "worker-cross-entry-b", snapshot_b["job_id"]),
    }


def verify_valid_worker_dispatches_stay_config_entry_scoped(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "worker-isolation-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "worker-isolation-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    worker_a = _install_fake_worker(hass, "worker-isolation-entry-a", FakeWorkerRenderer())
    worker_b = _install_fake_worker(hass, "worker-isolation-entry-b", FakeWorkerRenderer())
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-isolation-entry-a",
        "Show sensor.upstairs_temperature",
        50,
    )
    start_b = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-isolation-entry-b",
        "Show binary_sensor.office_window",
        51,
    )
    snapshot_a = _first_result_payload(start_a)
    snapshot_b = _first_result_payload(start_b)
    plan_a = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "worker-isolation-entry-a",
        snapshot_a["job_id"],
        52,
    )
    plan_b = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "worker-isolation-entry-b",
        snapshot_b["job_id"],
        53,
    )
    dispatches_a = _worker_dispatches(hass, "worker-isolation-entry-a")
    dispatches_b = _worker_dispatches(hass, "worker-isolation-entry-b")
    render_plans_a = _render_plans(hass, "worker-isolation-entry-a")
    render_plans_b = _render_plans(hass, "worker-isolation-entry-b")
    artifacts_a = _artifacts(hass, "worker-isolation-entry-a")
    artifacts_b = _artifacts(hass, "worker-isolation-entry-b")
    return {
        "entry_a": {
            "start": start_a,
            "snapshot": plan_a,
            "worker_call_count": len(worker_a.calls),
            "worker_calls": _worker_call_summaries(worker_a),
            "worker_dispatches": [_worker_dispatch_summary(dispatch) for dispatch in dispatches_a],
            "render_plans": [_render_plan_summary(plan) for plan in render_plans_a],
            "artifacts": [_artifact_summary(artifact) for artifact in artifacts_a],
            "orchestration_store": _orchestration_store_summary(hass, "worker-isolation-entry-a"),
            "worker_dispatch_validation": _validate_worker_dispatches(dispatches_a, root),
        },
        "entry_b": {
            "start": start_b,
            "snapshot": plan_b,
            "worker_call_count": len(worker_b.calls),
            "worker_calls": _worker_call_summaries(worker_b),
            "worker_dispatches": [_worker_dispatch_summary(dispatch) for dispatch in dispatches_b],
            "render_plans": [_render_plan_summary(plan) for plan in render_plans_b],
            "artifacts": [_artifact_summary(artifact) for artifact in artifacts_b],
            "orchestration_store": _orchestration_store_summary(hass, "worker-isolation-entry-b"),
            "worker_dispatch_validation": _validate_worker_dispatches(dispatches_b, root),
        },
    }


def verify_worker_dispatch_contracts_validate(root=None) -> dict[str, Any]:
    root = root or repo_root()
    accepted = verify_worker_dispatch_records_render_result(root)
    idempotent = verify_repeated_snapshot_requests_reuse_worker_dispatch(root)
    isolation = verify_valid_worker_dispatches_stay_config_entry_scoped(root)
    return {
        "accepted": _validation_summary(accepted),
        "idempotent": {
            "worker_dispatch_valid": all(item["accepted"] for item in idempotent["worker_dispatch_validation"]),
            "worker_dispatch_validation": idempotent["worker_dispatch_validation"],
        },
        "isolation_entry_a": {
            "worker_dispatch_valid": all(
                item["accepted"] for item in isolation["entry_a"]["worker_dispatch_validation"]
            ),
            "worker_dispatch_validation": isolation["entry_a"]["worker_dispatch_validation"],
        },
        "isolation_entry_b": {
            "worker_dispatch_valid": all(
                item["accepted"] for item in isolation["entry_b"]["worker_dispatch_validation"]
            ),
            "worker_dispatch_validation": isolation["entry_b"]["worker_dispatch_validation"],
        },
    }


def verify_worker_authorization_redaction(root=None) -> dict[str, Any]:
    accepted = verify_worker_dispatch_records_render_result(root)
    dispatch = accepted["worker_dispatch"]
    evidence_text = str(accepted)
    return {
        "raw_worker_authorization_received": accepted["worker_calls"][0]["raw_authorization_was_bearer"],
        "stored_authorization": dispatch["request"]["headers"]["authorization"],
        "stored_authorization_redacted": dispatch["request"]["headers"]["authorization"] == "Bearer <redacted>",
        "worker_token_absent_from_evidence": WORKER_TEST_TOKEN not in evidence_text,
        "worker_call_summaries": accepted["worker_calls"],
    }


def verify_worker_dispatch_side_effect_boundaries() -> dict[str, Any]:
    accepted = verify_worker_dispatch_records_render_result()
    idempotent = verify_repeated_snapshot_requests_reuse_worker_dispatch()
    failure = verify_worker_failure_rejected_before_storage()
    unknown = verify_unknown_worker_job_rejected_before_call()
    cross_entry = verify_cross_config_entry_worker_rejected_before_call()
    isolation = verify_valid_worker_dispatches_stay_config_entry_scoped()
    setup = _setup_worker_hass(
        FakeConfigEntry(
            "side-effects-worker-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        FakeWorkerRenderer(),
    )[0].data[DOMAIN]["side-effects-worker-entry"]

    observed = [
        {"name": "accepted_worker_snapshot", **accepted["snapshot_dispatch"]["orchestration"]},
        {"name": "idempotent_first_snapshot", **idempotent["first"]["orchestration"]},
        {"name": "idempotent_second_snapshot", **idempotent["second"]["orchestration"]},
        {"name": "worker_failure", **failure["snapshot"]["orchestration"]},
        {"name": "unknown_worker_job", **unknown["snapshot"]["orchestration"]},
        {"name": "cross_config_entry", **cross_entry["cross_snapshot"]["orchestration"]},
        {"name": "entry_a_worker_dispatch", **isolation["entry_a"]["snapshot"]["orchestration"]},
        {"name": "entry_b_worker_dispatch", **isolation["entry_b"]["snapshot"]["orchestration"]},
        {"name": "setup_orchestration", **setup[DATA_JOB_ORCHESTRATION_SETUP]["orchestration"]},
        {"name": "websocket_registration", **setup["websocket_api"]["orchestration"]},
    ]

    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in WORKER_DISPATCH_FORBIDDEN_SIDE_EFFECT_KEYS
    }
    allowed_aggregate = {
        "worker_called": any(item.get("worker_called") for item in observed),
        "chart_rendering_called": any(item.get("chart_rendering_called") for item in observed),
        "worker_dispatch_bookkeeping_written": any(
            item.get("worker_dispatch_bookkeeping_written") for item in observed
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
        "expected_forbidden": {key: False for key in WORKER_DISPATCH_FORBIDDEN_SIDE_EFFECT_KEYS},
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }


def verify_job_orchestration_worker_dispatch_rendering_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_worker_dispatch_rendering_files(root)
    accepted = verify_worker_dispatch_records_render_result(root)
    idempotent = verify_repeated_snapshot_requests_reuse_worker_dispatch(root)
    validation = verify_worker_dispatch_contracts_validate(root)
    redaction = verify_worker_authorization_redaction(root)
    failure = verify_worker_failure_rejected_before_storage(root)
    unknown_job = verify_unknown_worker_job_rejected_before_call(root)
    cross_entry = verify_cross_config_entry_worker_rejected_before_call(root)
    isolation = verify_valid_worker_dispatches_stay_config_entry_scoped(root)
    side_effects = verify_worker_dispatch_side_effect_boundaries()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more worker dispatch/rendering scaffold files are missing.")
    if not accepted["snapshot_dispatch"]["accepted"]:
        failures.append("Accepted worker snapshot request did not return a WebSocket result.")
    if accepted["worker_call_count"] != 1:
        failures.append("Accepted worker snapshot request did not call the worker exactly once.")
    if accepted["worker_dispatch"] is None:
        failures.append("Worker snapshot request did not store a worker dispatch.")
    elif accepted["worker_dispatch"]["dispatch_id"] != "worker-dispatch-entry-worker-dispatch-001":
        failures.append("Worker dispatch did not use the deterministic dispatch ID.")
    if accepted["worker_dispatch"] and accepted["worker_dispatch"]["request"]["headers"]["authorization"] != "Bearer <redacted>":
        failures.append("Worker dispatch did not redact authorization metadata.")
    if accepted["artifact_snapshot"]["status"] != "complete":
        failures.append("Worker dispatch did not return the artifact-backed complete snapshot.")
    if idempotent["worker_call_count"] != 1:
        failures.append("Repeated snapshot request called the worker more than once.")
    if idempotent["worker_dispatch_count"] != 1 or idempotent["render_plan_count"] != 1 or idempotent["artifact_count"] != 1:
        failures.append("Repeated snapshot requests created duplicate worker/render/artifact state.")
    if not idempotent["same_snapshot_returned"] or not idempotent["same_worker_dispatch_returned"]:
        failures.append("Repeated snapshot request did not return the existing snapshot and worker dispatch.")
    if not validation["accepted"]["worker_dispatch_valid"]:
        failures.append("Accepted worker dispatch did not validate.")
    if not validation["accepted"]["worker_transport_valid"]:
        failures.append("Accepted worker transport request did not validate.")
    if not validation["accepted"]["render_request_valid"]:
        failures.append("Accepted worker render request did not validate.")
    if not validation["accepted"]["render_result_valid"]:
        failures.append("Accepted worker render result did not validate.")
    if not validation["accepted"]["history_series_valid"]:
        failures.append("Accepted worker history series did not validate.")
    if not redaction["raw_worker_authorization_received"]:
        failures.append("Fake worker did not receive the bearer authorization header.")
    if not redaction["stored_authorization_redacted"] or not redaction["worker_token_absent_from_evidence"]:
        failures.append("Worker authorization token was not redacted from stored metadata/evidence.")
    if failure["error_codes"] != ["worker_safe_renderer_failed"]:
        failures.append("Worker failure did not fail closed with the worker error code.")
    if failure["worker_dispatches"] or failure["render_plans"] or failure["artifacts"] or failure["complete_snapshots"]:
        failures.append("Worker failure stored metadata after rejection.")
    if unknown_job["worker_call_count"] != 0 or unknown_job["error_codes"] != ["unknown_job"]:
        failures.append("Unknown worker job did not fail before worker call.")
    if cross_entry["entry_a_worker_call_count"] != 0 or cross_entry["entry_b_worker_call_count"] != 0:
        failures.append("Cross-config-entry request called a worker.")
    if cross_entry["error_codes"] != ["unknown_job"]:
        failures.append("Cross-config-entry worker request did not fail closed as unknown_job.")
    if cross_entry["entry_b_worker_dispatches"] or cross_entry["entry_b_render_plans"] or cross_entry["entry_b_artifacts"]:
        failures.append("Cross-config-entry worker request recorded entry B state.")
    if len(isolation["entry_a"]["worker_dispatches"]) != 1 or len(isolation["entry_b"]["worker_dispatches"]) != 1:
        failures.append("Valid worker dispatches did not stay isolated by config entry.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("Worker dispatch scaffold reported forbidden side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("Worker dispatch scaffold did not report expected allowed side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "accepted": accepted,
        "idempotent": idempotent,
        "validation": validation,
        "redaction": redaction,
        "failure": failure,
        "unknown_job": unknown_job,
        "cross_entry": cross_entry,
        "isolation": isolation,
        "side_effects": side_effects,
    }


def _setup_worker_hass(
    entry: FakeConfigEntry,
    worker: FakeWorkerRenderer,
) -> tuple[Any, FakeWebSocketApiModule]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    setup_accepted = _run(async_setup_entry(hass, entry))
    if not setup_accepted:
        raise AssertionError(f"async_setup_entry rejected {entry.entry_id}")
    _install_fake_worker(hass, entry.entry_id, worker)
    return hass, websocket_api_module


def _install_fake_worker(hass: Any, entry_id: str, worker: FakeWorkerRenderer) -> FakeWorkerRenderer:
    hass.data[DOMAIN][entry_id][DATA_WORKER_RENDER_CLIENT] = worker
    return worker


def _worker_dispatches(hass: Any, entry_id: str) -> list[dict[str, Any]]:
    store = hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION]
    return [
        deepcopy(store.get("worker_dispatches", {})[dispatch_id])
        for dispatch_id in store.get("worker_dispatch_order", [])
        if dispatch_id in store.get("worker_dispatches", {})
    ]


def _latest_worker_dispatch_from_dispatch(dispatch: dict[str, Any]) -> dict[str, Any] | None:
    handler_result = dispatch.get("handler_result")
    if not isinstance(handler_result, dict):
        return None
    job_orchestration = handler_result.get("job_orchestration")
    if not isinstance(job_orchestration, dict):
        return None
    worker_dispatch = job_orchestration.get("worker_dispatch")
    return deepcopy(worker_dispatch) if isinstance(worker_dispatch, dict) else None


def _orchestration_store_summary(hass: Any, entry_id: str) -> dict[str, Any]:
    return summarize_job_orchestration_store(hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION])


def _worker_call_summaries(worker: FakeWorkerRenderer) -> list[dict[str, Any]]:
    summaries = []
    for call in worker.calls:
        request = call["request"]
        authorization = request.get("headers", {}).get("authorization")
        render_request = request["body"]["render_request"]
        summaries.append(
            {
                "request": redacted_worker_transport_request(request),
                "raw_authorization_was_bearer": authorization == f"Bearer {WORKER_TEST_TOKEN}",
                "render_request_id": render_request["request_id"],
                "history_entity_ids": [
                    series.get("entity_id")
                    for series in render_request.get("history_series", [])
                ],
                "chart_entity_ids": _chart_entity_ids(render_request["chart_spec"]),
            }
        )
    return summaries


def _validate_worker_dispatches(dispatches: list[dict[str, Any]], root) -> list[dict[str, Any]]:
    return [_validate_worker_dispatch(dispatch, root) for dispatch in dispatches]


def _validate_worker_dispatch(dispatch: dict[str, Any], root) -> dict[str, Any]:
    try:
        validate_contract("integration-worker-dispatch", dispatch, repo_root=root)
        validate_contract("render-result", dispatch["render_result"], repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "contract_validation_failed",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "dispatch_id": dispatch["dispatch_id"],
        "job_id": dispatch["job_id"],
        "render_plan_id": dispatch["render_plan_id"],
        "artifact_id": dispatch["artifact_id"],
        "status": dispatch["status"],
        "authorization": dispatch["request"]["headers"]["authorization"],
    }


def _validate_worker_transport_requests(calls: list[dict[str, Any]], root) -> list[dict[str, Any]]:
    return [_validate_worker_transport_request(call["request"], root) for call in calls]


def _validate_worker_transport_request(request: dict[str, Any], root) -> dict[str, Any]:
    try:
        validate_contract("worker-transport-request", request, repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "contract_validation_failed",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "request_id": request["body"]["request_id"],
        "render_request_id": request["body"]["render_request"]["request_id"],
    }


def _validate_render_requests(calls: list[dict[str, Any]], root) -> list[dict[str, Any]]:
    return [_validate_render_request(call["request"]["body"]["render_request"], root) for call in calls]


def _validate_render_request(render_request: dict[str, Any], root) -> dict[str, Any]:
    try:
        validate_contract("render-request", render_request, repo_root=root)
        validate_contract("chart-spec", render_request["chart_spec"], repo_root=root)
        for series in render_request["history_series"]:
            validate_contract("history-series", series, repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "contract_validation_failed",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "request_id": render_request["request_id"],
        "history_entity_ids": [
            series.get("entity_id")
            for series in render_request["history_series"]
        ],
        "chart_entity_ids": _chart_entity_ids(render_request["chart_spec"]),
    }


def _validate_worker_dispatch_render_results(dispatches: list[dict[str, Any]], root) -> list[dict[str, Any]]:
    return [_validate_render_result(dispatch["render_result"], root) for dispatch in dispatches]


def _validate_render_result(render_result: dict[str, Any], root) -> dict[str, Any]:
    try:
        validate_contract("render-result", render_result, repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "contract_validation_failed",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "request_id": render_result["request_id"],
        "status": render_result["status"],
    }


def _validate_worker_history_series(calls: list[dict[str, Any]], root) -> list[dict[str, Any]]:
    results = []
    for call in calls:
        for series in call["request"]["body"]["render_request"].get("history_series", []):
            try:
                validate_contract("history-series", series, repo_root=root)
            except ContractValidationError as exc:
                results.append(
                    {
                        "accepted": False,
                        "code": "contract_validation_failed",
                        "error": str(exc),
                    }
                )
            else:
                results.append(
                    {
                        "accepted": True,
                        "code": "accepted",
                        "series_id": series["series_id"],
                        "entity_id": series.get("entity_id"),
                        "kind": series["kind"],
                    }
                )
    return results


def _validation_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "worker_dispatch_valid": all(item["accepted"] for item in result["worker_dispatch_validation"]),
        "worker_transport_valid": all(item["accepted"] for item in result["worker_transport_validation"]),
        "render_request_valid": all(item["accepted"] for item in result["render_request_validation"]),
        "render_result_valid": all(item["accepted"] for item in result["render_result_validation"]),
        "render_plan_valid": all(item["accepted"] for item in result["render_plan_validation"]),
        "chart_spec_valid": all(item["accepted"] for item in result["chart_spec_validation"]),
        "history_series_valid": all(item["accepted"] for item in result["history_series_validation"]),
        "worker_dispatch_validation": result["worker_dispatch_validation"],
        "worker_transport_validation": result["worker_transport_validation"],
        "render_request_validation": result["render_request_validation"],
        "render_result_validation": result["render_result_validation"],
        "render_plan_validation": result["render_plan_validation"],
        "chart_spec_validation": result["chart_spec_validation"],
        "history_series_validation": result["history_series_validation"],
    }


def _chart_entity_ids(chart_spec: dict[str, Any]) -> list[str]:
    entity_ids = []
    for series in chart_spec.get("series", []):
        source = series.get("source") if isinstance(series, dict) else None
        if isinstance(source, dict) and source.get("type") == "entity":
            entity_ids.append(source.get("entity_id"))
        if isinstance(source, dict) and source.get("type") == "aggregate":
            entity_ids.extend(source.get("entity_ids", []))
    return entity_ids


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


def _worker_dispatch_summary(dispatch: dict[str, Any] | None) -> dict[str, Any] | None:
    if dispatch is None:
        return None
    return {
        "dispatch_id": dispatch["dispatch_id"],
        "config_entry_id": dispatch["config_entry_id"],
        "job_id": dispatch["job_id"],
        "source_snapshot_id": dispatch["source_snapshot_id"],
        "render_plan_id": dispatch["render_plan_id"],
        "artifact_id": dispatch["artifact_id"],
        "status": dispatch["status"],
        "worker": deepcopy(dispatch["worker"]),
        "request": deepcopy(dispatch["request"]),
        "render_result": deepcopy(dispatch["render_result"]),
        "validation": deepcopy(dispatch["validation"]),
        "warnings": deepcopy(dispatch["warnings"]),
    }
