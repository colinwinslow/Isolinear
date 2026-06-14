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
    _install_fake_worker,
    _setup_worker_hass,
    _validate_render_requests,
    _validate_worker_transport_requests,
    _worker_call_summaries,
    _worker_dispatches,
)
from .worker_progress_streaming_anchor import _worker_progress_events
from .websocket_command_registration_anchor import FakeWebSocketApiModule


WORKER_TRANSPORT_FAILURE_CLASSIFICATION_FILES = [
    "custom_components/isolinear/job_orchestration.py",
    "custom_components/isolinear/worker_renderer.py",
    "custom_components/isolinear/websocket_api.py",
    "custom_components/isolinear/__init__.py",
    "docs/specs/home-assistant-worker-transport-failure-retry-classification-scaffold-spec.md",
    "bdd/integration/home-assistant-worker-transport-failure-retry-classification-scaffold-bdd.md",
    "bdd/integration/home-assistant-worker-transport-failure-retry-classification-scaffold-evidence.md",
    "docs/evals/home_assistant_worker_transport_failure_retry_classification_scaffold.yaml",
    "docs/schemas/integration-worker-transport-failure-classification.schema.json",
    "docs/schemas/integration-worker-retry-policy.schema.json",
    "docs/schemas/worker-transport-request.schema.json",
    "docs/schemas/render-request.schema.json",
    "docs/schemas/render-result.schema.json",
    "tests/test_worker_transport_failure_classification_anchor.py",
    "evals/home_assistant_worker_transport_failure_retry_classification_scaffold.py",
    "src/Isolinear/worker_transport_failure_classification_anchor.py",
]

WORKER_TRANSPORT_CLASSIFICATION_FORBIDDEN_SIDE_EFFECT_KEYS = [
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
    "worker_retry_policy_bookkeeping_written",
    "render_plan_bookkeeping_written",
    "artifact_metadata_bookkeeping_written",
    "durable_retry_storage_written",
    "token_rotation_called",
    "token_leaked_to_card",
    "token_leaked_to_model_provider",
    "worker_health_check_called",
    "scheduler_called",
    "new_worker_transport_added",
    "worker_render_result_retry_policy_changed",
]


class FakeTransportFailureWorker:
    provider_type = "http_json_worker"
    role = "renderer"
    api_version = 1

    def __init__(
        self,
        *,
        endpoint_url: str = "http://worker.local:8765",
        worker_token: str = WORKER_TEST_TOKEN,
        code: str = "worker_connection_error",
        message: str = "Fake worker transport failed before render result delivery.",
        retry_safe: bool = True,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.worker_token = worker_token
        self.code = code
        self.message = message
        self.retry_safe = retry_safe
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
        return {
            "accepted": False,
            "code": self.code,
            "provider_role": "renderer",
            "retry_safe": self.retry_safe,
            "message": self.message,
        }


def verify_worker_transport_failure_classification_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in WORKER_TRANSPORT_FAILURE_CLASSIFICATION_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_worker_connection_failure_records_retry_classification(root=None) -> dict[str, Any]:
    root = root or repo_root()
    worker = FakeTransportFailureWorker(code="worker_connection_error", retry_safe=True)
    hass, websocket_api_module = _setup_worker_hass(
        FakeConfigEntry(
            "worker-transport-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        worker,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-transport-entry",
        "Show sensor.upstairs_temperature",
        1,
    )
    job_id = _first_result_payload(start)["job_id"]
    snapshot = _dispatch_snapshot(hass, websocket_api_module, "worker-transport-entry", job_id, 2)
    classifications = _worker_transport_failure_classifications(hass, "worker-transport-entry")
    return {
        "start": start,
        "snapshot": snapshot,
        "worker_call_count": len(worker.calls),
        "worker_calls": _worker_call_summaries(worker),
        "error_codes": _error_codes(snapshot),
        "classification": (
            _worker_transport_failure_classification_summary(classifications[0])
            if classifications
            else None
        ),
        "classifications": [
            _worker_transport_failure_classification_summary(classification)
            for classification in classifications
        ],
        "worker_dispatches": _worker_dispatches(hass, "worker-transport-entry"),
        "worker_progress_events": _worker_progress_events(hass, "worker-transport-entry"),
        "worker_retry_policies": _worker_retry_policies(hass, "worker-transport-entry"),
        "render_plans": _render_plans(hass, "worker-transport-entry"),
        "artifacts": _artifacts(hass, "worker-transport-entry"),
        "complete_snapshots": _complete_snapshots(hass, "worker-transport-entry", job_id),
        "job_store": summarize_job_state_store(_job_store(hass, "worker-transport-entry")),
        "orchestration_store": _orchestration_store_summary(hass, "worker-transport-entry"),
        "classification_validation": _validate_worker_transport_failure_classifications(classifications, root),
        "worker_transport_validation": _validate_worker_transport_requests(worker.calls, root),
        "render_request_validation": _validate_render_requests(worker.calls, root),
    }


def verify_worker_transport_failure_family_mapping(root=None) -> dict[str, Any]:
    root = root or repo_root()
    cases = {
        "connection": ("worker_connection_error", True),
        "http": ("worker_http_error", True),
        "malformed_response": ("worker_response_error", False),
    }
    results = {}
    for family, (code, retry_safe) in cases.items():
        worker = FakeTransportFailureWorker(code=code, retry_safe=retry_safe)
        entry_id = f"worker-transport-{family}-entry"
        hass, websocket_api_module = _setup_worker_hass(
            FakeConfigEntry(
                entry_id,
                options={"entity_allowlist": ["sensor.upstairs_temperature"]},
            ),
            worker,
        )
        start = _dispatch_start(
            hass,
            websocket_api_module,
            entry_id,
            "Show sensor.upstairs_temperature",
            10,
        )
        job_id = _first_result_payload(start)["job_id"]
        snapshot = _dispatch_snapshot(hass, websocket_api_module, entry_id, job_id, 11)
        classifications = _worker_transport_failure_classifications(hass, entry_id)
        classification = (
            _worker_transport_failure_classification_summary(classifications[0])
            if classifications
            else None
        )
        results[family] = {
            "snapshot": snapshot,
            "worker_call_count": len(worker.calls),
            "error_codes": _error_codes(snapshot),
            "classification": classification,
            "classification_validation": _validate_worker_transport_failure_classifications(classifications, root),
        }
    return results


def verify_worker_transport_failure_classification_contracts_validate(root=None) -> dict[str, Any]:
    root = root or repo_root()
    accepted = verify_worker_connection_failure_records_retry_classification(root)
    families = verify_worker_transport_failure_family_mapping(root)
    isolation = verify_valid_worker_transport_classifications_stay_config_entry_scoped(root)
    return {
        "accepted": {
            "worker_transport_classification_valid": all(
                item["accepted"] for item in accepted["classification_validation"]
            ),
            "worker_transport_valid": all(item["accepted"] for item in accepted["worker_transport_validation"]),
            "render_request_valid": all(item["accepted"] for item in accepted["render_request_validation"]),
        },
        "families": {
            family: {
                "worker_transport_classification_valid": all(
                    item["accepted"] for item in case["classification_validation"]
                ),
                "observed_family": (
                    case["classification"]["classification"]["family"]
                    if case["classification"]
                    else None
                ),
                "retry_eligible": (
                    case["classification"]["classification"]["retry_eligible"]
                    if case["classification"]
                    else None
                ),
            }
            for family, case in families.items()
        },
        "isolation_entry_a": {
            "worker_transport_classification_valid": all(
                item["accepted"] for item in isolation["entry_a"]["classification_validation"]
            ),
        },
        "isolation_entry_b": {
            "worker_transport_classification_valid": all(
                item["accepted"] for item in isolation["entry_b"]["classification_validation"]
            ),
        },
    }


def verify_worker_transport_failure_classification_redaction(root=None) -> dict[str, Any]:
    accepted = verify_worker_connection_failure_records_retry_classification(root or repo_root())
    classification = accepted["classification"]
    secret_failure = verify_worker_transport_secret_failure_text_redaction(root or repo_root())
    return {
        "raw_worker_authorization_received": accepted["worker_calls"][0]["raw_authorization_was_bearer"],
        "stored_authorization": classification["worker"]["authorization"],
        "stored_request_authorization": classification["request"]["headers"]["authorization"],
        "stored_authorization_redacted": (
            classification["worker"]["authorization"] == "Bearer <redacted>"
            and classification["request"]["headers"]["authorization"] == "Bearer <redacted>"
        ),
        "worker_token_absent_from_evidence": WORKER_TEST_TOKEN not in str(accepted),
        "secret_failure_text": {
            "error_codes": secret_failure["error_codes"],
            "classification_failure_code": secret_failure["classification_failure_code"],
            "classification_failure_message": secret_failure["classification_failure_message"],
            "worker_token_absent_from_result": secret_failure["worker_token_absent_from_result"],
        },
        "worker_call_summaries": accepted["worker_calls"],
    }


def verify_worker_transport_secret_failure_text_redaction(root=None) -> dict[str, Any]:
    root = root or repo_root()
    worker = FakeTransportFailureWorker(
        code=f"Bearer {WORKER_TEST_TOKEN}",
        message=f"worker_token Bearer {WORKER_TEST_TOKEN}",
        retry_safe=True,
    )
    hass, websocket_api_module = _setup_worker_hass(
        FakeConfigEntry(
            "worker-transport-secret-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        worker,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-transport-secret-entry",
        "Show sensor.upstairs_temperature",
        40,
    )
    job_id = _first_result_payload(start)["job_id"]
    snapshot = _dispatch_snapshot(hass, websocket_api_module, "worker-transport-secret-entry", job_id, 41)
    classifications = _worker_transport_failure_classifications(hass, "worker-transport-secret-entry")
    classification = (
        _worker_transport_failure_classification_summary(classifications[0])
        if classifications
        else None
    )
    result = {
        "snapshot": snapshot,
        "worker_call_count": len(worker.calls),
        "error_codes": _error_codes(snapshot),
        "classification": classification,
        "classification_failure_code": classification["failure"]["code"] if classification else None,
        "classification_failure_message": classification["failure"]["message"] if classification else None,
        "classification_validation": _validate_worker_transport_failure_classifications(classifications, root),
    }
    result["worker_token_absent_from_result"] = WORKER_TEST_TOKEN not in str(result)
    return result


def verify_unknown_worker_transport_classification_job_rejected_before_call(root=None) -> dict[str, Any]:
    worker = FakeTransportFailureWorker(code="worker_connection_error")
    hass, websocket_api_module = _setup_worker_hass(
        FakeConfigEntry(
            "worker-transport-unknown-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        worker,
    )
    snapshot = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "worker-transport-unknown-entry",
        "worker-transport-unknown-entry-job-404",
        20,
    )
    return {
        "snapshot": snapshot,
        "worker_call_count": len(worker.calls),
        "error_codes": _error_codes(snapshot),
        "job_store": summarize_job_state_store(_job_store(hass, "worker-transport-unknown-entry")),
        "classifications": _worker_transport_failure_classifications(hass, "worker-transport-unknown-entry"),
        "worker_dispatches": _worker_dispatches(hass, "worker-transport-unknown-entry"),
        "render_plans": _render_plans(hass, "worker-transport-unknown-entry"),
        "artifacts": _artifacts(hass, "worker-transport-unknown-entry"),
    }


def verify_cross_config_entry_worker_transport_classification_rejected_before_call(root=None) -> dict[str, Any]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "worker-transport-cross-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "worker-transport-cross-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    worker_a = _install_fake_worker(
        hass,
        "worker-transport-cross-entry-a",
        FakeTransportFailureWorker(code="worker_connection_error"),
    )
    worker_b = _install_fake_worker(
        hass,
        "worker-transport-cross-entry-b",
        FakeTransportFailureWorker(code="worker_http_error"),
    )
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-transport-cross-entry-a",
        "Show sensor.upstairs_temperature",
        30,
    )
    entry_a_job_id = _first_result_payload(start_a)["job_id"]
    cross_snapshot = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "worker-transport-cross-entry-b",
        entry_a_job_id,
        31,
    )
    return {
        "cross_snapshot": cross_snapshot,
        "entry_a_worker_call_count": len(worker_a.calls),
        "entry_b_worker_call_count": len(worker_b.calls),
        "error_codes": _error_codes(cross_snapshot),
        "entry_b_classifications": _worker_transport_failure_classifications(
            hass,
            "worker-transport-cross-entry-b",
        ),
        "entry_b_worker_dispatches": _worker_dispatches(hass, "worker-transport-cross-entry-b"),
        "entry_b_render_plans": _render_plans(hass, "worker-transport-cross-entry-b"),
        "entry_b_artifacts": _artifacts(hass, "worker-transport-cross-entry-b"),
        "entry_b_complete_snapshots": [],
    }


def verify_valid_worker_transport_classifications_stay_config_entry_scoped(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "worker-transport-isolation-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "worker-transport-isolation-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    worker_a = _install_fake_worker(
        hass,
        "worker-transport-isolation-entry-a",
        FakeTransportFailureWorker(code="worker_connection_error"),
    )
    worker_b = _install_fake_worker(
        hass,
        "worker-transport-isolation-entry-b",
        FakeTransportFailureWorker(code="worker_http_error"),
    )
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-transport-isolation-entry-a",
        "Show sensor.upstairs_temperature",
        50,
    )
    start_b = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-transport-isolation-entry-b",
        "Show binary_sensor.office_window",
        51,
    )
    job_a = _first_result_payload(start_a)["job_id"]
    job_b = _first_result_payload(start_b)["job_id"]
    snapshot_a = _dispatch_snapshot(hass, websocket_api_module, "worker-transport-isolation-entry-a", job_a, 52)
    snapshot_b = _dispatch_snapshot(hass, websocket_api_module, "worker-transport-isolation-entry-b", job_b, 53)
    classifications_a = _worker_transport_failure_classifications(hass, "worker-transport-isolation-entry-a")
    classifications_b = _worker_transport_failure_classifications(hass, "worker-transport-isolation-entry-b")
    return {
        "entry_a": {
            "snapshot": snapshot_a,
            "worker_call_count": len(worker_a.calls),
            "classifications": [
                _worker_transport_failure_classification_summary(classification)
                for classification in classifications_a
            ],
            "classification_validation": _validate_worker_transport_failure_classifications(
                classifications_a,
                root,
            ),
            "orchestration_store": _orchestration_store_summary(hass, "worker-transport-isolation-entry-a"),
        },
        "entry_b": {
            "snapshot": snapshot_b,
            "worker_call_count": len(worker_b.calls),
            "classifications": [
                _worker_transport_failure_classification_summary(classification)
                for classification in classifications_b
            ],
            "classification_validation": _validate_worker_transport_failure_classifications(
                classifications_b,
                root,
            ),
            "orchestration_store": _orchestration_store_summary(hass, "worker-transport-isolation-entry-b"),
        },
    }


def verify_worker_transport_classification_side_effect_boundaries() -> dict[str, Any]:
    accepted = verify_worker_connection_failure_records_retry_classification(repo_root())
    unknown = verify_unknown_worker_transport_classification_job_rejected_before_call(repo_root())
    cross_entry = verify_cross_config_entry_worker_transport_classification_rejected_before_call(repo_root())
    isolation = verify_valid_worker_transport_classifications_stay_config_entry_scoped(repo_root())

    setup_hass, _ = _setup_worker_hass(
        FakeConfigEntry(
            "side-effects-worker-transport-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        FakeTransportFailureWorker(code="worker_connection_error"),
    )
    setup = setup_hass.data[DOMAIN]["side-effects-worker-transport-entry"]

    observed = [
        {"name": "accepted_transport_failure", **accepted["snapshot"]["orchestration"]},
        {"name": "unknown_job", **unknown["snapshot"]["orchestration"]},
        {"name": "cross_config_entry", **cross_entry["cross_snapshot"]["orchestration"]},
        {"name": "entry_a_failure", **isolation["entry_a"]["snapshot"]["orchestration"]},
        {"name": "entry_b_failure", **isolation["entry_b"]["snapshot"]["orchestration"]},
        {"name": "setup_orchestration", **setup[DATA_JOB_ORCHESTRATION_SETUP]["orchestration"]},
        {"name": "websocket_registration", **setup["websocket_api"]["orchestration"]},
    ]
    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in WORKER_TRANSPORT_CLASSIFICATION_FORBIDDEN_SIDE_EFFECT_KEYS
    }
    allowed_aggregate = {
        "worker_called": any(item.get("worker_called") for item in observed),
        "chart_rendering_called": any(item.get("chart_rendering_called") for item in observed),
        "worker_transport_failure_classification_bookkeeping_written": any(
            item.get("worker_transport_failure_classification_bookkeeping_written")
            for item in observed
        ),
        "websocket_command_registered": any(item.get("websocket_command_registered") for item in observed),
    }
    return {
        "expected_forbidden": {
            key: False for key in WORKER_TRANSPORT_CLASSIFICATION_FORBIDDEN_SIDE_EFFECT_KEYS
        },
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }


def verify_worker_transport_failure_classification_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_worker_transport_failure_classification_files(root)
    accepted = verify_worker_connection_failure_records_retry_classification(root)
    families = verify_worker_transport_failure_family_mapping(root)
    validation = verify_worker_transport_failure_classification_contracts_validate(root)
    redaction = verify_worker_transport_failure_classification_redaction(root)
    secret_failure = verify_worker_transport_secret_failure_text_redaction(root)
    unknown_job = verify_unknown_worker_transport_classification_job_rejected_before_call(root)
    cross_entry = verify_cross_config_entry_worker_transport_classification_rejected_before_call(root)
    isolation = verify_valid_worker_transport_classifications_stay_config_entry_scoped(root)
    side_effects = verify_worker_transport_classification_side_effect_boundaries()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more worker transport failure classification scaffold files are missing.")
    if not accepted["snapshot"]["accepted"]:
        failures.append("Worker transport failure did not return a card-facing failed snapshot result.")
    if _first_result_payload(accepted["snapshot"]).get("status") != "failed":
        failures.append("Worker transport failure result payload was not a failed snapshot.")
    if accepted["worker_call_count"] != 1:
        failures.append("Worker transport failure did not call the fake worker exactly once.")
    if len(accepted["classifications"]) != 1:
        failures.append("Worker transport failure did not store exactly one classification.")
    if accepted["classification"] and accepted["classification"]["backoff"]["delay_seconds"] != 5:
        failures.append("Worker transport classification did not record the first deterministic delay.")
    if accepted["worker_dispatches"] or accepted["render_plans"] or accepted["artifacts"]:
        failures.append("Worker transport failure stored dispatch, render-plan, or artifact metadata.")
    if accepted["worker_progress_events"] or accepted["worker_retry_policies"] or accepted["complete_snapshots"]:
        failures.append("Worker transport failure stored progress, retry-policy, or complete snapshot metadata.")
    for expected_family, case in families.items():
        classification = case["classification"]
        if not classification or classification["classification"]["family"] != expected_family:
            failures.append(f"Worker transport failure did not classify {expected_family!r} deterministically.")
    if not validation["accepted"]["worker_transport_classification_valid"]:
        failures.append("Worker transport failure classification did not validate.")
    if not validation["accepted"]["worker_transport_valid"] or not validation["accepted"]["render_request_valid"]:
        failures.append("Worker transport failure request contracts did not validate.")
    if not redaction["raw_worker_authorization_received"]:
        failures.append("Fake worker did not receive bearer authorization.")
    if not redaction["stored_authorization_redacted"] or not redaction["worker_token_absent_from_evidence"]:
        failures.append("Worker transport classification metadata or evidence leaked authorization.")
    if secret_failure["error_codes"] != ["worker_transport_failed"]:
        failures.append("Secret-bearing worker transport failure code was not normalized before returning.")
    if secret_failure["classification_failure_code"] != "worker_transport_failed":
        failures.append("Secret-bearing worker transport failure code was not normalized before classification storage.")
    if not secret_failure["worker_token_absent_from_result"]:
        failures.append("Secret-bearing worker transport failure text leaked token material.")
    if unknown_job["worker_call_count"] != 0 or unknown_job["error_codes"] != ["unknown_job"]:
        failures.append("Unknown worker transport classification job did not fail before worker call.")
    if unknown_job["classifications"]:
        failures.append("Unknown worker transport classification job recorded classification metadata.")
    if cross_entry["entry_a_worker_call_count"] != 0 or cross_entry["entry_b_worker_call_count"] != 0:
        failures.append("Cross-config-entry worker transport classification request called a worker.")
    if cross_entry["error_codes"] != ["unknown_job"]:
        failures.append("Cross-config-entry worker transport classification request did not fail as unknown_job.")
    if cross_entry["entry_b_classifications"]:
        failures.append("Cross-config-entry worker transport classification request recorded entry B metadata.")
    if len(isolation["entry_a"]["classifications"]) != 1 or len(isolation["entry_b"]["classifications"]) != 1:
        failures.append("Valid worker transport classifications did not stay isolated by config entry.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("Worker transport failure classification scaffold reported forbidden side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("Worker transport failure classification scaffold did not report expected allowed side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "accepted": accepted,
        "families": families,
        "validation": validation,
        "redaction": redaction,
        "secret_failure": secret_failure,
        "unknown_job": unknown_job,
        "cross_entry": cross_entry,
        "isolation": isolation,
        "side_effects": side_effects,
    }


def _worker_transport_failure_classifications(hass: Any, entry_id: str) -> list[dict[str, Any]]:
    store = hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION]
    return [
        deepcopy(store.get("worker_transport_failure_classifications", {})[classification_id])
        for classification_id in store.get("worker_transport_failure_classification_order", [])
        if classification_id in store.get("worker_transport_failure_classifications", {})
    ]


def _worker_retry_policies(hass: Any, entry_id: str) -> list[dict[str, Any]]:
    store = hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION]
    return [
        deepcopy(store.get("worker_retry_policies", {})[policy_id])
        for policy_id in store.get("worker_retry_policy_order", [])
        if policy_id in store.get("worker_retry_policies", {})
    ]


def _orchestration_store_summary(hass: Any, entry_id: str) -> dict[str, Any]:
    return summarize_job_orchestration_store(hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION])


def _worker_transport_failure_classification_summary(classification: dict[str, Any]) -> dict[str, Any]:
    return {
        "classification_id": classification["classification_id"],
        "type": classification["type"],
        "config_entry_id": classification["config_entry_id"],
        "job_id": classification["job_id"],
        "source_snapshot_id": classification["source_snapshot_id"],
        "worker": deepcopy(classification["worker"]),
        "request": deepcopy(classification["request"]),
        "failure": deepcopy(classification["failure"]),
        "classification": deepcopy(classification["classification"]),
        "backoff": deepcopy(classification["backoff"]),
        "validation": deepcopy(classification["validation"]),
        "warnings": list(classification["warnings"]),
    }


def _validate_worker_transport_failure_classifications(
    classifications: list[dict[str, Any]],
    root,
) -> list[dict[str, Any]]:
    return [
        _validate_worker_transport_failure_classification(classification, root)
        for classification in classifications
    ]


def _validate_worker_transport_failure_classification(classification: dict[str, Any], root) -> dict[str, Any]:
    try:
        validate_contract("integration-worker-transport-failure-classification", classification, repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "contract_validation_failed",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "classification_id": classification["classification_id"],
        "job_id": classification["job_id"],
        "failure_code": classification["failure"]["code"],
        "failure_family": classification["classification"]["family"],
        "retry_eligible": classification["classification"]["retry_eligible"],
        "delay_seconds": classification["backoff"]["delay_seconds"],
        "authorization": classification["worker"]["authorization"],
    }
