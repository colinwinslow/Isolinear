from __future__ import annotations

from copy import deepcopy
from typing import Any

from custom_components.isolinear import async_setup_entry
from custom_components.isolinear.const import DOMAIN
from custom_components.isolinear.history_retrieval import DATA_HISTORY_RETRIEVAL
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
    _job,
    _job_store,
)
from .job_orchestration_render_planning_anchor import _render_plans
from .job_orchestration_retry_continuation_anchor import _dispatch_retry
from .job_orchestration_scaffold_anchor import _fake_hass, _first_result_payload, _run
from .job_orchestration_worker_dispatch_rendering_anchor import (
    WORKER_TEST_TOKEN,
    FakeWorkerRenderer,
    _install_fake_worker,
    _setup_worker_hass,
    _worker_call_summaries,
    _worker_dispatches,
)
from .worker_progress_streaming_anchor import _worker_progress_events
from .worker_retry_backoff_policy_anchor import (
    _validate_worker_retry_policies,
    _worker_retry_policies,
    _worker_retry_policy_summary,
)
from .worker_transport_failure_classification_anchor import (
    FakeTransportFailureWorker,
    _validate_worker_transport_failure_classifications,
    _worker_transport_failure_classification_summary,
    _worker_transport_failure_classifications,
)
from .websocket_command_registration_anchor import FakeWebSocketApiModule


WORKER_FAILURE_SNAPSHOT_MANUAL_RETRY_FILES = [
    "custom_components/isolinear/job_orchestration.py",
    "custom_components/isolinear/worker_renderer.py",
    "custom_components/isolinear/websocket_api.py",
    "custom_components/isolinear/__init__.py",
    "docs/specs/home-assistant-worker-failure-snapshot-manual-retry-integration-scaffold-spec.md",
    "bdd/integration/home-assistant-worker-failure-snapshot-manual-retry-integration-scaffold-bdd.md",
    "bdd/integration/home-assistant-worker-failure-snapshot-manual-retry-integration-scaffold-evidence.md",
    "docs/evals/home_assistant_worker_failure_snapshot_manual_retry_integration_scaffold.yaml",
    "docs/schemas/integration-job-snapshot.schema.json",
    "docs/schemas/integration-worker-retry-policy.schema.json",
    "docs/schemas/integration-worker-transport-failure-classification.schema.json",
    "tests/test_worker_failure_snapshot_manual_retry_anchor.py",
    "evals/home_assistant_worker_failure_snapshot_manual_retry_integration_scaffold.py",
    "src/Isolinear/worker_failure_snapshot_manual_retry_anchor.py",
]

WORKER_FAILURE_SNAPSHOT_FORBIDDEN_SIDE_EFFECT_KEYS = [
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
    "durable_retry_storage_written",
    "token_rotation_called",
    "token_leaked_to_card",
    "token_leaked_to_model_provider",
    "worker_health_check_called",
    "scheduler_called",
    "new_worker_transport_added",
    "worker_metadata_exposed_to_card",
]


def verify_worker_failure_snapshot_manual_retry_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in WORKER_FAILURE_SNAPSHOT_MANUAL_RETRY_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_worker_render_failure_returns_failed_snapshot(root=None) -> dict[str, Any]:
    root = root or repo_root()
    worker = FakeWorkerRenderer(fail_code="worker_safe_renderer_failed")
    hass, websocket_api_module = _setup_worker_hass(
        FakeConfigEntry(
            "worker-failure-render-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        worker,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-failure-render-entry",
        "Show sensor.upstairs_temperature",
        1,
    )
    job_id = _first_result_payload(start)["job_id"]
    snapshot = _dispatch_snapshot(hass, websocket_api_module, "worker-failure-render-entry", job_id, 2)
    policies = _worker_retry_policies(hass, "worker-failure-render-entry")
    failed_snapshots = _failed_snapshots(hass, "worker-failure-render-entry", job_id)
    return {
        "start": start,
        "snapshot": snapshot,
        "card_snapshot": _snapshot_summary(_first_result_payload(snapshot)),
        "worker_call_count": len(worker.calls),
        "worker_calls": _worker_call_summaries(worker),
        "error_codes": _error_codes(snapshot),
        "failed_snapshots": [_snapshot_summary(item) for item in failed_snapshots],
        "worker_retry_policy": _worker_retry_policy_summary(policies[0]) if policies else None,
        "worker_retry_policies": [_worker_retry_policy_summary(policy) for policy in policies],
        "worker_dispatches": _worker_dispatches(hass, "worker-failure-render-entry"),
        "worker_progress_events": _worker_progress_events(hass, "worker-failure-render-entry"),
        "transport_classifications": _worker_transport_failure_classifications(
            hass,
            "worker-failure-render-entry",
        ),
        "render_plans": _render_plans(hass, "worker-failure-render-entry"),
        "artifacts": _artifacts(hass, "worker-failure-render-entry"),
        "complete_snapshots": _complete_snapshots(hass, "worker-failure-render-entry", job_id),
        "job_store": summarize_job_state_store(_job_store(hass, "worker-failure-render-entry")),
        "orchestration_store": _orchestration_store_summary(hass, "worker-failure-render-entry"),
        "failed_snapshot_validation": _validate_snapshots(failed_snapshots, root),
        "worker_retry_policy_validation": _validate_worker_retry_policies(policies, root),
    }


def verify_worker_transport_failure_returns_failed_snapshot(root=None) -> dict[str, Any]:
    root = root or repo_root()
    worker = FakeTransportFailureWorker(code="worker_connection_error", retry_safe=True)
    hass, websocket_api_module = _setup_transport_failure_hass(
        FakeConfigEntry(
            "worker-failure-transport-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        worker,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-failure-transport-entry",
        "Show sensor.upstairs_temperature",
        10,
    )
    job_id = _first_result_payload(start)["job_id"]
    snapshot = _dispatch_snapshot(hass, websocket_api_module, "worker-failure-transport-entry", job_id, 11)
    classifications = _worker_transport_failure_classifications(hass, "worker-failure-transport-entry")
    failed_snapshots = _failed_snapshots(hass, "worker-failure-transport-entry", job_id)
    return {
        "start": start,
        "snapshot": snapshot,
        "card_snapshot": _snapshot_summary(_first_result_payload(snapshot)),
        "worker_call_count": len(worker.calls),
        "worker_calls": _worker_call_summaries(worker),
        "error_codes": _error_codes(snapshot),
        "failed_snapshots": [_snapshot_summary(item) for item in failed_snapshots],
        "classification": (
            _worker_transport_failure_classification_summary(classifications[0])
            if classifications
            else None
        ),
        "classifications": [
            _worker_transport_failure_classification_summary(classification)
            for classification in classifications
        ],
        "worker_retry_policies": _worker_retry_policies(hass, "worker-failure-transport-entry"),
        "worker_dispatches": _worker_dispatches(hass, "worker-failure-transport-entry"),
        "worker_progress_events": _worker_progress_events(hass, "worker-failure-transport-entry"),
        "render_plans": _render_plans(hass, "worker-failure-transport-entry"),
        "artifacts": _artifacts(hass, "worker-failure-transport-entry"),
        "complete_snapshots": _complete_snapshots(hass, "worker-failure-transport-entry", job_id),
        "job_store": summarize_job_state_store(_job_store(hass, "worker-failure-transport-entry")),
        "orchestration_store": _orchestration_store_summary(hass, "worker-failure-transport-entry"),
        "failed_snapshot_validation": _validate_snapshots(failed_snapshots, root),
        "classification_validation": _validate_worker_transport_failure_classifications(classifications, root),
    }


def verify_manual_retry_resumes_worker_failure_snapshot(root=None) -> dict[str, Any]:
    root = root or repo_root()
    worker = FakeWorkerRenderer(fail_code="worker_safe_renderer_failed")
    hass, websocket_api_module = _setup_worker_hass(
        FakeConfigEntry(
            "worker-failure-manual-retry-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        worker,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-failure-manual-retry-entry",
        "Show sensor.upstairs_temperature",
        20,
    )
    job_id = _first_result_payload(start)["job_id"]
    failure_snapshot = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "worker-failure-manual-retry-entry",
        job_id,
        21,
    )
    history_before = _history_store_summary(hass, "worker-failure-manual-retry-entry")
    retry = _dispatch_retry(hass, websocket_api_module, "worker-failure-manual-retry-entry", job_id, 22)
    retry_snapshot = _first_result_payload(retry)
    job = _job(hass, "worker-failure-manual-retry-entry", job_id)
    history_after = _history_store_summary(hass, "worker-failure-manual-retry-entry")
    snapshots = list(job["snapshots"])
    return {
        "start": start,
        "failure_snapshot_dispatch": failure_snapshot,
        "failed_snapshot": _snapshot_summary(_first_result_payload(failure_snapshot)),
        "retry": retry,
        "retry_snapshot": _snapshot_summary(retry_snapshot),
        "same_job_id": retry_snapshot["job_id"] == job_id if isinstance(retry_snapshot, dict) else False,
        "job_snapshot_ids": [item["snapshot_id"] for item in snapshots],
        "job_progress_stages": [item["progress"]["stage"] for item in snapshots],
        "history_before": history_before,
        "history_after": history_after,
        "history_request_count_delta": history_after["request_count"] - history_before["request_count"],
        "worker_call_count": len(worker.calls),
        "run": _latest_run(hass, "worker-failure-manual-retry-entry"),
        "snapshot_validation": _validate_snapshots(snapshots, root),
    }


def verify_non_retry_safe_transport_failure_rejects_manual_retry(root=None) -> dict[str, Any]:
    root = root or repo_root()
    worker = FakeTransportFailureWorker(code="worker_response_error", retry_safe=False)
    hass, websocket_api_module = _setup_transport_failure_hass(
        FakeConfigEntry(
            "worker-failure-not-retry-safe-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        worker,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-failure-not-retry-safe-entry",
        "Show sensor.upstairs_temperature",
        30,
    )
    job_id = _first_result_payload(start)["job_id"]
    failure_snapshot = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "worker-failure-not-retry-safe-entry",
        job_id,
        31,
    )
    job = _job(hass, "worker-failure-not-retry-safe-entry", job_id)
    snapshot_count_before = len(job["snapshots"])
    history_before = _history_store_summary(hass, "worker-failure-not-retry-safe-entry")
    retry = _dispatch_retry(hass, websocket_api_module, "worker-failure-not-retry-safe-entry", job_id, 32)
    history_after = _history_store_summary(hass, "worker-failure-not-retry-safe-entry")
    return {
        "start": start,
        "failure_snapshot_dispatch": failure_snapshot,
        "failed_snapshot": _snapshot_summary(_first_result_payload(failure_snapshot)),
        "retry": retry,
        "retry_error_codes": _error_codes(retry),
        "snapshot_count_before_retry": snapshot_count_before,
        "snapshot_count_after_retry": len(job["snapshots"]),
        "history_before": history_before,
        "history_after": history_after,
        "history_request_count_delta": history_after["request_count"] - history_before["request_count"],
        "classification_validation": _validate_worker_transport_failure_classifications(
            _worker_transport_failure_classifications(hass, "worker-failure-not-retry-safe-entry"),
            root,
        ),
    }


def verify_worker_failure_snapshot_contracts_validate(root=None) -> dict[str, Any]:
    root = root or repo_root()
    render = verify_worker_render_failure_returns_failed_snapshot(root)
    transport = verify_worker_transport_failure_returns_failed_snapshot(root)
    return {
        "render_failure": {
            "failed_snapshot_valid": all(item["accepted"] for item in render["failed_snapshot_validation"]),
            "worker_retry_policy_valid": all(item["accepted"] for item in render["worker_retry_policy_validation"]),
        },
        "transport_failure": {
            "failed_snapshot_valid": all(item["accepted"] for item in transport["failed_snapshot_validation"]),
            "transport_classification_valid": all(item["accepted"] for item in transport["classification_validation"]),
        },
    }


def verify_card_payload_excludes_worker_internals(root=None) -> dict[str, Any]:
    render = verify_worker_render_failure_returns_failed_snapshot(root or repo_root())
    transport = verify_worker_transport_failure_returns_failed_snapshot(root or repo_root())
    render_payload = _first_result_payload(render["snapshot"])
    transport_payload = _first_result_payload(transport["snapshot"])
    forbidden_values = [
        WORKER_TEST_TOKEN,
        "Bearer <redacted>",
        "http://worker.local:8765",
        "worker_retry_policy",
        "worker_transport_failure_classification",
        "render_request",
        "worker_dispatch",
        "render_plan",
        "artifact_id",
    ]
    render_forbidden = _forbidden_payload_hits(render_payload, forbidden_values)
    transport_forbidden = _forbidden_payload_hits(transport_payload, forbidden_values)
    return {
        "render_card_payload": _snapshot_summary(render_payload),
        "transport_card_payload": _snapshot_summary(transport_payload),
        "render_forbidden_hits": render_forbidden,
        "transport_forbidden_hits": transport_forbidden,
        "card_payloads_exclude_worker_internals": not render_forbidden and not transport_forbidden,
        "internal_render_policy_authorization": render["worker_retry_policy"]["worker"]["authorization"],
        "internal_transport_classification_authorization": transport["classification"]["worker"]["authorization"],
        "worker_authorization_redacted_in_internal_metadata": (
            render["worker_retry_policy"]["worker"]["authorization"] == "Bearer <redacted>"
            and transport["classification"]["worker"]["authorization"] == "Bearer <redacted>"
        ),
        "worker_token_absent_from_card_payloads": (
            WORKER_TEST_TOKEN not in str(render_payload)
            and WORKER_TEST_TOKEN not in str(transport_payload)
        ),
    }


def verify_unknown_worker_failure_snapshot_job_rejected_before_call(root=None) -> dict[str, Any]:
    worker = FakeWorkerRenderer(fail_code="worker_safe_renderer_failed")
    hass, websocket_api_module = _setup_worker_hass(
        FakeConfigEntry(
            "worker-failure-unknown-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        worker,
    )
    snapshot = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "worker-failure-unknown-entry",
        "worker-failure-unknown-entry-job-404",
        40,
    )
    return {
        "snapshot": snapshot,
        "worker_call_count": len(worker.calls),
        "error_codes": _error_codes(snapshot),
        "job_store": summarize_job_state_store(_job_store(hass, "worker-failure-unknown-entry")),
        "worker_retry_policies": _worker_retry_policies(hass, "worker-failure-unknown-entry"),
        "transport_classifications": _worker_transport_failure_classifications(
            hass,
            "worker-failure-unknown-entry",
        ),
        "worker_dispatches": _worker_dispatches(hass, "worker-failure-unknown-entry"),
    }


def verify_cross_config_entry_worker_failure_snapshot_and_retry_rejected(root=None) -> dict[str, Any]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "worker-failure-cross-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "worker-failure-cross-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    worker_a = _install_fake_worker(
        hass,
        "worker-failure-cross-entry-a",
        FakeWorkerRenderer(fail_code="entry_a_worker_failed"),
    )
    worker_b = _install_fake_worker(
        hass,
        "worker-failure-cross-entry-b",
        FakeWorkerRenderer(fail_code="entry_b_worker_failed"),
    )
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-failure-cross-entry-a",
        "Show sensor.upstairs_temperature",
        50,
    )
    start_b = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-failure-cross-entry-b",
        "Show binary_sensor.office_window",
        51,
    )
    entry_a_job_id = _first_result_payload(start_a)["job_id"]
    entry_b_job_id = _first_result_payload(start_b)["job_id"]
    cross_snapshot = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "worker-failure-cross-entry-b",
        entry_a_job_id,
        52,
    )
    cross_retry = _dispatch_retry(
        hass,
        websocket_api_module,
        "worker-failure-cross-entry-b",
        entry_a_job_id,
        53,
    )
    return {
        "entry_a_start": start_a,
        "entry_b_start": start_b,
        "cross_snapshot": cross_snapshot,
        "cross_retry": cross_retry,
        "entry_a_worker_call_count": len(worker_a.calls),
        "entry_b_worker_call_count": len(worker_b.calls),
        "error_codes": _error_codes(cross_snapshot) + _error_codes(cross_retry),
        "entry_b_job_id": entry_b_job_id,
        "entry_b_failed_snapshots": _failed_snapshots(hass, "worker-failure-cross-entry-b", entry_b_job_id),
        "entry_b_worker_retry_policies": _worker_retry_policies(hass, "worker-failure-cross-entry-b"),
        "entry_b_transport_classifications": _worker_transport_failure_classifications(
            hass,
            "worker-failure-cross-entry-b",
        ),
        "entry_b_worker_dispatches": _worker_dispatches(hass, "worker-failure-cross-entry-b"),
    }


def verify_valid_worker_failure_snapshots_stay_config_entry_scoped(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "worker-failure-isolation-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "worker-failure-isolation-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    worker_a = _install_fake_worker(
        hass,
        "worker-failure-isolation-entry-a",
        FakeWorkerRenderer(fail_code="entry_a_worker_failed"),
    )
    worker_b = _install_fake_worker(
        hass,
        "worker-failure-isolation-entry-b",
        FakeTransportFailureWorker(code="worker_http_error", retry_safe=True),
    )
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-failure-isolation-entry-a",
        "Show sensor.upstairs_temperature",
        60,
    )
    start_b = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-failure-isolation-entry-b",
        "Show binary_sensor.office_window",
        61,
    )
    job_a = _first_result_payload(start_a)["job_id"]
    job_b = _first_result_payload(start_b)["job_id"]
    snapshot_a = _dispatch_snapshot(hass, websocket_api_module, "worker-failure-isolation-entry-a", job_a, 62)
    snapshot_b = _dispatch_snapshot(hass, websocket_api_module, "worker-failure-isolation-entry-b", job_b, 63)
    failed_a = _failed_snapshots(hass, "worker-failure-isolation-entry-a", job_a)
    failed_b = _failed_snapshots(hass, "worker-failure-isolation-entry-b", job_b)
    return {
        "entry_a": {
            "snapshot": snapshot_a,
            "card_snapshot": _snapshot_summary(_first_result_payload(snapshot_a)),
            "worker_call_count": len(worker_a.calls),
            "failed_snapshots": [_snapshot_summary(item) for item in failed_a],
            "failed_snapshot_validation": _validate_snapshots(failed_a, root),
            "worker_retry_policies": [
                _worker_retry_policy_summary(policy)
                for policy in _worker_retry_policies(hass, "worker-failure-isolation-entry-a")
            ],
            "transport_classifications": _worker_transport_failure_classifications(
                hass,
                "worker-failure-isolation-entry-a",
            ),
        },
        "entry_b": {
            "snapshot": snapshot_b,
            "card_snapshot": _snapshot_summary(_first_result_payload(snapshot_b)),
            "worker_call_count": len(worker_b.calls),
            "failed_snapshots": [_snapshot_summary(item) for item in failed_b],
            "failed_snapshot_validation": _validate_snapshots(failed_b, root),
            "worker_retry_policies": _worker_retry_policies(hass, "worker-failure-isolation-entry-b"),
            "transport_classifications": [
                _worker_transport_failure_classification_summary(classification)
                for classification in _worker_transport_failure_classifications(
                    hass,
                    "worker-failure-isolation-entry-b",
                )
            ],
        },
    }


def verify_worker_failure_snapshot_manual_retry_side_effect_boundaries() -> dict[str, Any]:
    render = verify_worker_render_failure_returns_failed_snapshot(repo_root())
    transport = verify_worker_transport_failure_returns_failed_snapshot(repo_root())
    retry = verify_manual_retry_resumes_worker_failure_snapshot(repo_root())
    non_retry_safe = verify_non_retry_safe_transport_failure_rejects_manual_retry(repo_root())
    unknown = verify_unknown_worker_failure_snapshot_job_rejected_before_call(repo_root())
    cross_entry = verify_cross_config_entry_worker_failure_snapshot_and_retry_rejected(repo_root())
    card_redaction = verify_card_payload_excludes_worker_internals(repo_root())

    setup_hass, _ = _setup_worker_hass(
        FakeConfigEntry(
            "side-effects-worker-failure-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        FakeWorkerRenderer(fail_code="worker_safe_renderer_failed"),
    )
    setup = setup_hass.data[DOMAIN]["side-effects-worker-failure-entry"]

    worker_failure_observed = [
        {"name": "render_failure_snapshot", **render["snapshot"]["orchestration"]},
        {"name": "transport_failure_snapshot", **transport["snapshot"]["orchestration"]},
        {"name": "non_retry_safe_snapshot", **non_retry_safe["failure_snapshot_dispatch"]["orchestration"]},
        {"name": "unknown_job", **unknown["snapshot"]["orchestration"]},
        {"name": "cross_config_entry_snapshot", **cross_entry["cross_snapshot"]["orchestration"]},
        {"name": "cross_config_entry_retry", **cross_entry["cross_retry"]["orchestration"]},
        {"name": "setup_orchestration", **setup[DATA_JOB_ORCHESTRATION_SETUP]["orchestration"]},
        {"name": "websocket_registration", **setup["websocket_api"]["orchestration"]},
    ]
    manual_retry_observed = [
        {"name": "manual_retry", **retry["retry"]["orchestration"]},
        {"name": "non_retry_safe_manual_retry", **non_retry_safe["retry"]["orchestration"]},
    ]
    forbidden_aggregate = {
        key: any(item.get(key) for item in worker_failure_observed)
        for key in WORKER_FAILURE_SNAPSHOT_FORBIDDEN_SIDE_EFFECT_KEYS
    }
    forbidden_aggregate["worker_metadata_exposed_to_card"] = not card_redaction[
        "card_payloads_exclude_worker_internals"
    ]
    allowed_aggregate = {
        "worker_called": any(item.get("worker_called") for item in worker_failure_observed),
        "chart_rendering_called": any(item.get("chart_rendering_called") for item in worker_failure_observed),
        "job_state_scaffold_written": any(item.get("job_state_scaffold_written") for item in worker_failure_observed),
        "job_orchestration_scaffold_written": any(
            item.get("job_orchestration_scaffold_written") for item in worker_failure_observed
        ),
        "worker_retry_policy_bookkeeping_written": any(
            item.get("worker_retry_policy_bookkeeping_written") for item in worker_failure_observed
        ),
        "worker_transport_failure_classification_bookkeeping_written": any(
            item.get("worker_transport_failure_classification_bookkeeping_written")
            for item in worker_failure_observed
        ),
        "retry_behavior_called_for_manual_retry": any(
            item.get("retry_behavior_called") for item in manual_retry_observed
        ),
        "home_assistant_history_read_for_manual_retry": any(
            item.get("home_assistant_history_read") for item in manual_retry_observed
        ),
        "websocket_command_registered": any(item.get("websocket_command_registered") for item in worker_failure_observed),
    }
    return {
        "expected_forbidden_during_worker_failure_snapshot": {
            key: False for key in WORKER_FAILURE_SNAPSHOT_FORBIDDEN_SIDE_EFFECT_KEYS
        },
        "worker_failure_observed": worker_failure_observed,
        "manual_retry_observed": manual_retry_observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
        "card_redaction": card_redaction,
    }


def verify_worker_failure_snapshot_manual_retry_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_worker_failure_snapshot_manual_retry_files(root)
    render = verify_worker_render_failure_returns_failed_snapshot(root)
    transport = verify_worker_transport_failure_returns_failed_snapshot(root)
    retry = verify_manual_retry_resumes_worker_failure_snapshot(root)
    non_retry_safe = verify_non_retry_safe_transport_failure_rejects_manual_retry(root)
    validation = verify_worker_failure_snapshot_contracts_validate(root)
    card_redaction = verify_card_payload_excludes_worker_internals(root)
    unknown_job = verify_unknown_worker_failure_snapshot_job_rejected_before_call(root)
    cross_entry = verify_cross_config_entry_worker_failure_snapshot_and_retry_rejected(root)
    isolation = verify_valid_worker_failure_snapshots_stay_config_entry_scoped(root)
    side_effects = verify_worker_failure_snapshot_manual_retry_side_effect_boundaries()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more worker failure snapshot/manual retry files are missing.")
    if not render["snapshot"]["accepted"] or render["card_snapshot"]["status"] != "failed":
        failures.append("Worker render failure did not return an accepted failed snapshot payload.")
    if render["card_snapshot"]["failure"]["stage"] != "worker_render":
        failures.append("Worker render failure snapshot did not use worker_render stage.")
    if render["card_snapshot"]["retry_allowed"] is not True:
        failures.append("Worker render failure snapshot did not allow manual retry.")
    if len(render["worker_retry_policies"]) != 1:
        failures.append("Worker render failure did not store exactly one retry policy.")
    if render["worker_dispatches"] or render["render_plans"] or render["artifacts"] or render["complete_snapshots"]:
        failures.append("Worker render failure stored dispatch, render-plan, artifact, or complete metadata.")
    if not transport["snapshot"]["accepted"] or transport["card_snapshot"]["status"] != "failed":
        failures.append("Worker transport failure did not return an accepted failed snapshot payload.")
    if transport["card_snapshot"]["failure"]["stage"] != "worker_transport":
        failures.append("Worker transport failure snapshot did not use worker_transport stage.")
    if transport["card_snapshot"]["retry_allowed"] is not True:
        failures.append("Worker transport failure snapshot did not allow manual retry.")
    if len(transport["classifications"]) != 1:
        failures.append("Worker transport failure did not store exactly one classification.")
    if not retry["retry"]["accepted"] or retry["retry_snapshot"]["progress_stage"] != "job_orchestration_retry_continuation_ready":
        failures.append("Manual retry did not resume the failed worker job through retry continuation.")
    if retry["history_request_count_delta"] != 1:
        failures.append("Manual retry did not read approved history exactly once.")
    if non_retry_safe["failed_snapshot"]["retry_allowed"] is not False:
        failures.append("Non-retry-safe transport failure snapshot unexpectedly allowed retry.")
    if non_retry_safe["retry_error_codes"] != ["job_not_retryable"]:
        failures.append("Non-retry-safe transport failure did not reject manual retry as job_not_retryable.")
    if non_retry_safe["history_request_count_delta"] != 0:
        failures.append("Non-retry-safe manual retry rejection read history.")
    if not validation["render_failure"]["failed_snapshot_valid"]:
        failures.append("Worker render failed snapshot did not validate.")
    if not validation["render_failure"]["worker_retry_policy_valid"]:
        failures.append("Worker render retry policy did not validate.")
    if not validation["transport_failure"]["failed_snapshot_valid"]:
        failures.append("Worker transport failed snapshot did not validate.")
    if not validation["transport_failure"]["transport_classification_valid"]:
        failures.append("Worker transport classification did not validate.")
    if not card_redaction["card_payloads_exclude_worker_internals"]:
        failures.append("Card-facing payload exposed worker internals.")
    if not card_redaction["worker_authorization_redacted_in_internal_metadata"]:
        failures.append("Internal worker metadata did not remain redacted.")
    if unknown_job["worker_call_count"] != 0 or unknown_job["error_codes"] != ["unknown_job"]:
        failures.append("Unknown job did not fail before worker failure snapshot handling.")
    if unknown_job["worker_retry_policies"] or unknown_job["transport_classifications"]:
        failures.append("Unknown job recorded worker failure metadata.")
    if cross_entry["entry_a_worker_call_count"] != 0 or cross_entry["entry_b_worker_call_count"] != 0:
        failures.append("Cross-config-entry worker failure request called a worker.")
    if cross_entry["error_codes"] != ["unknown_job", "unknown_job"]:
        failures.append("Cross-config-entry snapshot/retry did not fail as unknown_job.")
    if cross_entry["entry_b_failed_snapshots"]:
        failures.append("Cross-config-entry request stored an entry B failed snapshot.")
    if len(isolation["entry_a"]["failed_snapshots"]) != 1 or len(isolation["entry_b"]["failed_snapshots"]) != 1:
        failures.append("Valid worker failure snapshots did not stay isolated by config entry.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("Worker failure snapshot/manual retry reported forbidden side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("Worker failure snapshot/manual retry did not report expected allowed side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "render": render,
        "transport": transport,
        "retry": retry,
        "non_retry_safe": non_retry_safe,
        "validation": validation,
        "card_redaction": card_redaction,
        "unknown_job": unknown_job,
        "cross_entry": cross_entry,
        "isolation": isolation,
        "side_effects": side_effects,
    }


def _setup_transport_failure_hass(
    entry: FakeConfigEntry,
    worker: FakeTransportFailureWorker,
) -> tuple[Any, FakeWebSocketApiModule]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    setup_accepted = _run(async_setup_entry(hass, entry))
    if not setup_accepted:
        raise AssertionError(f"async_setup_entry rejected {entry.entry_id}")
    _install_fake_worker(hass, entry.entry_id, worker)
    return hass, websocket_api_module


def _failed_snapshots(hass: Any, entry_id: str, job_id: str) -> list[dict[str, Any]]:
    return [
        deepcopy(snapshot)
        for snapshot in _job(hass, entry_id, job_id)["snapshots"]
        if snapshot.get("status") == "failed"
        and snapshot.get("progress", {}).get("stage") == "worker_failure_snapshot_ready"
    ]


def _snapshot_summary(snapshot: Any) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        return {}
    return {
        "snapshot_id": snapshot.get("snapshot_id"),
        "job_id": snapshot.get("job_id"),
        "status": snapshot.get("status"),
        "progress_stage": snapshot.get("progress", {}).get("stage"),
        "failure": deepcopy(snapshot.get("failure")),
        "retry_allowed": snapshot.get("retry_allowed"),
        "validation": deepcopy(snapshot.get("validation")),
        "warnings": list(snapshot.get("warnings", [])),
    }


def _history_store_summary(hass: Any, entry_id: str) -> dict[str, Any]:
    store = hass.data[DOMAIN][entry_id][DATA_HISTORY_RETRIEVAL]
    return {
        "entry_id": store["entry_id"],
        "series_count": len(store["series"]),
        "entity_ids": list(store["entity_ids"]),
        "request_count": store["request_count"],
        "last_time_range": deepcopy(store["last_time_range"]),
    }


def _orchestration_store_summary(hass: Any, entry_id: str) -> dict[str, Any]:
    return summarize_job_orchestration_store(hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION])


def _latest_run(hass: Any, entry_id: str) -> dict[str, Any]:
    return deepcopy(hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION]["latest_run"])


def _validate_snapshots(snapshots: list[dict[str, Any]], root) -> list[dict[str, Any]]:
    return [_validate_snapshot(snapshot, root) for snapshot in snapshots]


def _validate_snapshot(snapshot: Any, root) -> dict[str, Any]:
    try:
        validate_contract("integration-job-snapshot", snapshot, repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "contract_validation_failed",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "snapshot_id": snapshot["snapshot_id"],
        "job_id": snapshot["job_id"],
        "status": snapshot["status"],
        "progress_stage": snapshot["progress"]["stage"],
        "failure_code": snapshot.get("failure", {}).get("code"),
        "failure_stage": snapshot.get("failure", {}).get("stage"),
        "retry_allowed": snapshot.get("retry_allowed"),
    }


def _forbidden_payload_hits(payload: Any, forbidden_values: list[str]) -> list[str]:
    payload_text = str(payload)
    return [value for value in forbidden_values if value in payload_text]
