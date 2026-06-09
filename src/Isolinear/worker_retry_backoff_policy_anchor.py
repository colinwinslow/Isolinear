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

from .contracts import ContractValidationError, validate_contract
from .dashboard_card_anchor import repo_root
from .entity_catalog_scaffold_anchor import FakeConfigEntry
from .job_orchestration_artifact_storage_anchor import (
    _artifacts,
    _complete_snapshots,
    _dispatch_snapshot,
    _dispatch_start,
    _error_codes,
    _job_store,
)
from .job_orchestration_render_planning_anchor import _render_plans
from .job_orchestration_scaffold_anchor import _fake_hass, _first_result_payload, _run
from .job_orchestration_worker_dispatch_rendering_anchor import (
    WORKER_TEST_TOKEN,
    FakeWorkerRenderer,
    _install_fake_worker,
    _setup_worker_hass,
    _validate_render_requests,
    _validate_worker_transport_requests,
    _worker_call_summaries,
    _worker_dispatches,
)
from .worker_progress_streaming_anchor import _worker_progress_events
from .websocket_command_registration_anchor import FakeWebSocketApiModule


WORKER_RETRY_BACKOFF_POLICY_FILES = [
    "custom_components/isolinear/job_orchestration.py",
    "custom_components/isolinear/worker_renderer.py",
    "custom_components/isolinear/websocket_api.py",
    "custom_components/isolinear/__init__.py",
    "docs/specs/home-assistant-worker-retry-backoff-policy-scaffold-spec.md",
    "bdd/integration/home-assistant-worker-retry-backoff-policy-scaffold-bdd.md",
    "bdd/integration/home-assistant-worker-retry-backoff-policy-scaffold-evidence.md",
    "docs/evals/home_assistant_worker_retry_backoff_policy_scaffold.yaml",
    "docs/schemas/integration-worker-retry-policy.schema.json",
    "docs/schemas/worker-transport-request.schema.json",
    "docs/schemas/render-request.schema.json",
    "docs/schemas/render-result.schema.json",
    "tests/test_worker_retry_backoff_policy_anchor.py",
    "evals/home_assistant_worker_retry_backoff_policy_scaffold.py",
    "src/Isolinear/worker_retry_backoff_policy_anchor.py",
]

WORKER_RETRY_POLICY_FORBIDDEN_SIDE_EFFECT_KEYS = [
    key
    for key in NO_JOB_ORCHESTRATION_CALLS
    if key not in {"worker_called", "chart_rendering_called"}
] + [
    "home_assistant_history_read",
    "history_retrieval_scaffold_written",
    "subscription_bookkeeping_written",
    "subscription_progress_streaming_called",
    "model_provider_called",
    "worker_dispatch_bookkeeping_written",
    "worker_progress_bookkeeping_written",
    "worker_progress_streaming_called",
    "render_plan_bookkeeping_written",
    "artifact_metadata_bookkeeping_written",
]


def verify_worker_retry_policy_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in WORKER_RETRY_BACKOFF_POLICY_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_worker_failure_records_retry_policy(root=None) -> dict[str, Any]:
    root = root or repo_root()
    worker = FakeWorkerRenderer(fail_code="worker_safe_renderer_failed")
    hass, websocket_api_module = _setup_worker_hass(
        FakeConfigEntry(
            "worker-retry-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        worker,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-retry-entry",
        "Show sensor.upstairs_temperature",
        1,
    )
    job_id = _first_result_payload(start)["job_id"]
    snapshot = _dispatch_snapshot(hass, websocket_api_module, "worker-retry-entry", job_id, 2)
    worker_retry_policies = _worker_retry_policies(hass, "worker-retry-entry")
    return {
        "start": start,
        "snapshot": snapshot,
        "worker_call_count": len(worker.calls),
        "worker_calls": _worker_call_summaries(worker),
        "error_codes": _error_codes(snapshot),
        "worker_retry_policy": _worker_retry_policy_summary(worker_retry_policies[0]) if worker_retry_policies else None,
        "worker_retry_policies": [_worker_retry_policy_summary(policy) for policy in worker_retry_policies],
        "worker_dispatches": _worker_dispatches(hass, "worker-retry-entry"),
        "worker_progress_events": _worker_progress_events(hass, "worker-retry-entry"),
        "render_plans": _render_plans(hass, "worker-retry-entry"),
        "artifacts": _artifacts(hass, "worker-retry-entry"),
        "complete_snapshots": _complete_snapshots(hass, "worker-retry-entry", job_id),
        "job_store": summarize_job_state_store(_job_store(hass, "worker-retry-entry")),
        "orchestration_store": _orchestration_store_summary(hass, "worker-retry-entry"),
        "worker_retry_policy_validation": _validate_worker_retry_policies(worker_retry_policies, root),
        "worker_transport_validation": _validate_worker_transport_requests(worker.calls, root),
        "render_request_validation": _validate_render_requests(worker.calls, root),
        "render_result_validation": _validate_failed_worker_render_results(worker.calls, worker_retry_policies, root),
    }


def verify_worker_retry_policy_contracts_validate(root=None) -> dict[str, Any]:
    root = root or repo_root()
    accepted = verify_worker_failure_records_retry_policy(root)
    isolation = verify_valid_worker_retry_policies_stay_config_entry_scoped(root)
    return {
        "accepted": {
            "worker_retry_policy_valid": all(
                item["accepted"] for item in accepted["worker_retry_policy_validation"]
            ),
            "worker_transport_valid": all(item["accepted"] for item in accepted["worker_transport_validation"]),
            "render_request_valid": all(item["accepted"] for item in accepted["render_request_validation"]),
            "render_result_valid": all(item["accepted"] for item in accepted["render_result_validation"]),
        },
        "isolation_entry_a": {
            "worker_retry_policy_valid": all(
                item["accepted"] for item in isolation["entry_a"]["worker_retry_policy_validation"]
            ),
        },
        "isolation_entry_b": {
            "worker_retry_policy_valid": all(
                item["accepted"] for item in isolation["entry_b"]["worker_retry_policy_validation"]
            ),
        },
    }


def verify_worker_retry_policy_authorization_redaction(root=None) -> dict[str, Any]:
    accepted = verify_worker_failure_records_retry_policy(root or repo_root())
    policy = accepted["worker_retry_policy"]
    secret_failure_code = verify_worker_retry_policy_secret_failure_code_redaction(root or repo_root())
    return {
        "raw_worker_authorization_received": accepted["worker_calls"][0]["raw_authorization_was_bearer"],
        "stored_authorization": policy["worker"]["authorization"],
        "stored_request_authorization": policy["request"]["headers"]["authorization"],
        "stored_authorization_redacted": (
            policy["worker"]["authorization"] == "Bearer <redacted>"
            and policy["request"]["headers"]["authorization"] == "Bearer <redacted>"
        ),
        "worker_token_absent_from_evidence": WORKER_TEST_TOKEN not in str(accepted),
        "secret_failure_code": {
            "error_codes": secret_failure_code["error_codes"],
            "policy_failure_code": secret_failure_code["policy_failure_code"],
            "worker_token_absent_from_result": secret_failure_code["worker_token_absent_from_result"],
        },
        "worker_call_summaries": accepted["worker_calls"],
    }


def verify_worker_retry_policy_secret_failure_code_redaction(root=None) -> dict[str, Any]:
    root = root or repo_root()
    worker = FakeWorkerRenderer(fail_code=f"Bearer {WORKER_TEST_TOKEN}")
    hass, websocket_api_module = _setup_worker_hass(
        FakeConfigEntry(
            "worker-retry-secret-code-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        worker,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-retry-secret-code-entry",
        "Show sensor.upstairs_temperature",
        40,
    )
    job_id = _first_result_payload(start)["job_id"]
    snapshot = _dispatch_snapshot(hass, websocket_api_module, "worker-retry-secret-code-entry", job_id, 41)
    worker_retry_policies = _worker_retry_policies(hass, "worker-retry-secret-code-entry")
    policy = _worker_retry_policy_summary(worker_retry_policies[0]) if worker_retry_policies else None
    result = {
        "snapshot": snapshot,
        "worker_call_count": len(worker.calls),
        "error_codes": _error_codes(snapshot),
        "worker_retry_policy": policy,
        "policy_failure_code": policy["failure"]["code"] if policy else None,
        "worker_retry_policy_validation": _validate_worker_retry_policies(worker_retry_policies, root),
    }
    result["worker_token_absent_from_result"] = WORKER_TEST_TOKEN not in str(result)
    return result


def verify_unknown_worker_retry_policy_job_rejected_before_call(root=None) -> dict[str, Any]:
    worker = FakeWorkerRenderer(fail_code="worker_safe_renderer_failed")
    hass, websocket_api_module = _setup_worker_hass(
        FakeConfigEntry(
            "worker-retry-unknown-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        worker,
    )
    snapshot = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "worker-retry-unknown-entry",
        "worker-retry-unknown-entry-job-404",
        10,
    )
    return {
        "snapshot": snapshot,
        "worker_call_count": len(worker.calls),
        "error_codes": _error_codes(snapshot),
        "job_store": summarize_job_state_store(_job_store(hass, "worker-retry-unknown-entry")),
        "worker_retry_policies": _worker_retry_policies(hass, "worker-retry-unknown-entry"),
        "worker_dispatches": _worker_dispatches(hass, "worker-retry-unknown-entry"),
        "render_plans": _render_plans(hass, "worker-retry-unknown-entry"),
        "artifacts": _artifacts(hass, "worker-retry-unknown-entry"),
    }


def verify_cross_config_entry_worker_retry_policy_rejected_before_call(root=None) -> dict[str, Any]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "worker-retry-cross-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "worker-retry-cross-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    worker_a = _install_fake_worker(hass, "worker-retry-cross-entry-a", FakeWorkerRenderer(fail_code="a_failed"))
    worker_b = _install_fake_worker(hass, "worker-retry-cross-entry-b", FakeWorkerRenderer(fail_code="b_failed"))
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-retry-cross-entry-a",
        "Show sensor.upstairs_temperature",
        20,
    )
    entry_a_job_id = _first_result_payload(start_a)["job_id"]
    cross_snapshot = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "worker-retry-cross-entry-b",
        entry_a_job_id,
        21,
    )
    return {
        "cross_snapshot": cross_snapshot,
        "entry_a_worker_call_count": len(worker_a.calls),
        "entry_b_worker_call_count": len(worker_b.calls),
        "error_codes": _error_codes(cross_snapshot),
        "entry_b_worker_retry_policies": _worker_retry_policies(hass, "worker-retry-cross-entry-b"),
        "entry_b_worker_dispatches": _worker_dispatches(hass, "worker-retry-cross-entry-b"),
        "entry_b_render_plans": _render_plans(hass, "worker-retry-cross-entry-b"),
        "entry_b_artifacts": _artifacts(hass, "worker-retry-cross-entry-b"),
        "entry_b_complete_snapshots": [],
    }


def verify_valid_worker_retry_policies_stay_config_entry_scoped(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "worker-retry-isolation-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "worker-retry-isolation-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    worker_a = _install_fake_worker(
        hass,
        "worker-retry-isolation-entry-a",
        FakeWorkerRenderer(fail_code="entry_a_worker_failed"),
    )
    worker_b = _install_fake_worker(
        hass,
        "worker-retry-isolation-entry-b",
        FakeWorkerRenderer(fail_code="entry_b_worker_failed"),
    )
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-retry-isolation-entry-a",
        "Show sensor.upstairs_temperature",
        30,
    )
    start_b = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-retry-isolation-entry-b",
        "Show binary_sensor.office_window",
        31,
    )
    job_a = _first_result_payload(start_a)["job_id"]
    job_b = _first_result_payload(start_b)["job_id"]
    snapshot_a = _dispatch_snapshot(hass, websocket_api_module, "worker-retry-isolation-entry-a", job_a, 32)
    snapshot_b = _dispatch_snapshot(hass, websocket_api_module, "worker-retry-isolation-entry-b", job_b, 33)
    policies_a = _worker_retry_policies(hass, "worker-retry-isolation-entry-a")
    policies_b = _worker_retry_policies(hass, "worker-retry-isolation-entry-b")
    return {
        "entry_a": {
            "snapshot": snapshot_a,
            "worker_call_count": len(worker_a.calls),
            "worker_retry_policies": [_worker_retry_policy_summary(policy) for policy in policies_a],
            "worker_retry_policy_validation": _validate_worker_retry_policies(policies_a, root),
            "orchestration_store": _orchestration_store_summary(hass, "worker-retry-isolation-entry-a"),
        },
        "entry_b": {
            "snapshot": snapshot_b,
            "worker_call_count": len(worker_b.calls),
            "worker_retry_policies": [_worker_retry_policy_summary(policy) for policy in policies_b],
            "worker_retry_policy_validation": _validate_worker_retry_policies(policies_b, root),
            "orchestration_store": _orchestration_store_summary(hass, "worker-retry-isolation-entry-b"),
        },
    }


def verify_worker_retry_policy_side_effect_boundaries() -> dict[str, Any]:
    accepted = verify_worker_failure_records_retry_policy(repo_root())
    unknown = verify_unknown_worker_retry_policy_job_rejected_before_call(repo_root())
    cross_entry = verify_cross_config_entry_worker_retry_policy_rejected_before_call(repo_root())
    isolation = verify_valid_worker_retry_policies_stay_config_entry_scoped(repo_root())

    setup_hass, _ = _setup_worker_hass(
        FakeConfigEntry(
            "side-effects-worker-retry-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        FakeWorkerRenderer(fail_code="side_effect_worker_failed"),
    )
    setup = setup_hass.data[DOMAIN]["side-effects-worker-retry-entry"]

    observed = [
        {"name": "accepted_worker_failure", **accepted["snapshot"]["orchestration"]},
        {"name": "unknown_job", **unknown["snapshot"]["orchestration"]},
        {"name": "cross_config_entry", **cross_entry["cross_snapshot"]["orchestration"]},
        {"name": "entry_a_failure", **isolation["entry_a"]["snapshot"]["orchestration"]},
        {"name": "entry_b_failure", **isolation["entry_b"]["snapshot"]["orchestration"]},
        {"name": "setup_orchestration", **setup[DATA_JOB_ORCHESTRATION_SETUP]["orchestration"]},
        {"name": "websocket_registration", **setup["websocket_api"]["orchestration"]},
    ]
    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in WORKER_RETRY_POLICY_FORBIDDEN_SIDE_EFFECT_KEYS
    }
    allowed_aggregate = {
        "worker_called": any(item.get("worker_called") for item in observed),
        "chart_rendering_called": any(item.get("chart_rendering_called") for item in observed),
        "worker_retry_policy_bookkeeping_written": any(
            item.get("worker_retry_policy_bookkeeping_written") for item in observed
        ),
        "websocket_command_registered": any(item.get("websocket_command_registered") for item in observed),
    }
    return {
        "expected_forbidden": {key: False for key in WORKER_RETRY_POLICY_FORBIDDEN_SIDE_EFFECT_KEYS},
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }


def verify_worker_retry_backoff_policy_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_worker_retry_policy_files(root)
    accepted = verify_worker_failure_records_retry_policy(root)
    validation = verify_worker_retry_policy_contracts_validate(root)
    redaction = verify_worker_retry_policy_authorization_redaction(root)
    secret_failure_code = verify_worker_retry_policy_secret_failure_code_redaction(root)
    unknown_job = verify_unknown_worker_retry_policy_job_rejected_before_call(root)
    cross_entry = verify_cross_config_entry_worker_retry_policy_rejected_before_call(root)
    isolation = verify_valid_worker_retry_policies_stay_config_entry_scoped(root)
    side_effects = verify_worker_retry_policy_side_effect_boundaries()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more worker retry/backoff policy scaffold files are missing.")
    if not accepted["snapshot"]["accepted"]:
        failures.append("Worker failure did not return a card-facing failed snapshot result.")
    if _first_result_payload(accepted["snapshot"]).get("status") != "failed":
        failures.append("Worker failure result payload was not a failed snapshot.")
    if accepted["worker_call_count"] != 1:
        failures.append("Worker failure did not call the fake worker exactly once.")
    if len(accepted["worker_retry_policies"]) != 1:
        failures.append("Worker failure did not store exactly one retry/backoff policy.")
    if accepted["worker_retry_policy"] and accepted["worker_retry_policy"]["backoff"]["delay_seconds"] != 5:
        failures.append("Worker retry/backoff policy did not record the first deterministic delay.")
    if accepted["worker_dispatches"] or accepted["render_plans"] or accepted["artifacts"]:
        failures.append("Worker failure stored dispatch, render-plan, or artifact metadata.")
    if accepted["worker_progress_events"] or accepted["complete_snapshots"]:
        failures.append("Worker failure stored progress metadata or complete snapshots.")
    if not validation["accepted"]["worker_retry_policy_valid"]:
        failures.append("Worker retry/backoff policy did not validate.")
    if not validation["accepted"]["worker_transport_valid"] or not validation["accepted"]["render_request_valid"]:
        failures.append("Worker retry/backoff request contracts did not validate.")
    if not validation["accepted"]["render_result_valid"]:
        failures.append("Failed worker render result did not validate.")
    if not redaction["raw_worker_authorization_received"]:
        failures.append("Fake worker did not receive bearer authorization.")
    if not redaction["stored_authorization_redacted"] or not redaction["worker_token_absent_from_evidence"]:
        failures.append("Worker retry/backoff metadata or evidence leaked authorization.")
    if secret_failure_code["error_codes"] != ["worker_render_failed"]:
        failures.append("Secret-bearing worker failure code was not normalized before returning.")
    if secret_failure_code["policy_failure_code"] != "worker_render_failed":
        failures.append("Secret-bearing worker failure code was not normalized before policy storage.")
    if not secret_failure_code["worker_token_absent_from_result"]:
        failures.append("Secret-bearing worker failure code leaked token material.")
    if unknown_job["worker_call_count"] != 0 or unknown_job["error_codes"] != ["unknown_job"]:
        failures.append("Unknown worker retry/backoff job did not fail before worker call.")
    if unknown_job["worker_retry_policies"]:
        failures.append("Unknown worker retry/backoff job recorded policy metadata.")
    if cross_entry["entry_a_worker_call_count"] != 0 or cross_entry["entry_b_worker_call_count"] != 0:
        failures.append("Cross-config-entry worker retry/backoff request called a worker.")
    if cross_entry["error_codes"] != ["unknown_job"]:
        failures.append("Cross-config-entry worker retry/backoff request did not fail as unknown_job.")
    if cross_entry["entry_b_worker_retry_policies"]:
        failures.append("Cross-config-entry worker retry/backoff request recorded entry B policy.")
    if len(isolation["entry_a"]["worker_retry_policies"]) != 1 or len(isolation["entry_b"]["worker_retry_policies"]) != 1:
        failures.append("Valid worker retry/backoff policies did not stay isolated by config entry.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("Worker retry/backoff policy scaffold reported forbidden side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("Worker retry/backoff policy scaffold did not report expected allowed side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "accepted": accepted,
        "validation": validation,
        "redaction": redaction,
        "secret_failure_code": secret_failure_code,
        "unknown_job": unknown_job,
        "cross_entry": cross_entry,
        "isolation": isolation,
        "side_effects": side_effects,
    }


def _worker_retry_policies(hass: Any, entry_id: str) -> list[dict[str, Any]]:
    store = hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION]
    return [
        deepcopy(store.get("worker_retry_policies", {})[policy_id])
        for policy_id in store.get("worker_retry_policy_order", [])
        if policy_id in store.get("worker_retry_policies", {})
    ]


def _orchestration_store_summary(hass: Any, entry_id: str) -> dict[str, Any]:
    return summarize_job_orchestration_store(hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION])


def _worker_retry_policy_summary(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "policy_id": policy["policy_id"],
        "type": policy["type"],
        "config_entry_id": policy["config_entry_id"],
        "job_id": policy["job_id"],
        "source_snapshot_id": policy["source_snapshot_id"],
        "worker": deepcopy(policy["worker"]),
        "request": deepcopy(policy["request"]),
        "failure": deepcopy(policy["failure"]),
        "decision": deepcopy(policy["decision"]),
        "backoff": deepcopy(policy["backoff"]),
        "validation": deepcopy(policy["validation"]),
        "warnings": list(policy["warnings"]),
    }


def _validate_worker_retry_policies(policies: list[dict[str, Any]], root) -> list[dict[str, Any]]:
    return [_validate_worker_retry_policy(policy, root) for policy in policies]


def _validate_worker_retry_policy(policy: dict[str, Any], root) -> dict[str, Any]:
    try:
        validate_contract("integration-worker-retry-policy", policy, repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "contract_validation_failed",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "policy_id": policy["policy_id"],
        "job_id": policy["job_id"],
        "failure_code": policy["failure"]["code"],
        "eligible": policy["decision"]["eligible"],
        "delay_seconds": policy["backoff"]["delay_seconds"],
        "authorization": policy["worker"]["authorization"],
    }


def _validate_failed_worker_render_results(
    calls: list[dict[str, Any]],
    policies: list[dict[str, Any]],
    root,
) -> list[dict[str, Any]]:
    results = []
    for policy in policies:
        render_result = {
            "request_id": policy["request"]["body"]["render_request"]["request_id"],
            "status": "failed",
            "image_id": None,
            "image_mime_type": None,
            "image_path": None,
            "error": {
                "code": policy["failure"]["code"],
                "message": policy["failure"]["message"],
                "details": {},
            },
            "render_metadata": {},
        }
        try:
            validate_contract("render-result", render_result, repo_root=root)
        except ContractValidationError as exc:
            results.append(
                {
                    "accepted": False,
                    "code": "contract_validation_failed",
                    "error": str(exc),
                }
            )
            continue
        results.append(
            {
                "accepted": True,
                "code": "accepted",
                "request_id": render_result["request_id"],
                "worker_call_count": len(calls),
            }
        )
    return results
