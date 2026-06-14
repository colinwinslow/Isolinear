from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import custom_components.isolinear.worker_renderer as worker_renderer_module
from custom_components.isolinear import async_setup_entry
from custom_components.isolinear.const import DOMAIN
from custom_components.isolinear.job_orchestration import (
    DATA_JOB_ORCHESTRATION,
    DATA_JOB_ORCHESTRATION_SETUP,
    NO_JOB_ORCHESTRATION_CALLS,
    summarize_job_orchestration_store,
)
from custom_components.isolinear.job_state import summarize_job_state_store
from custom_components.isolinear.worker_renderer import DATA_WORKER_RENDER_CLIENT, HttpJsonWorkerRenderClient

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
    _render_plans,
    _validate_chart_specs,
    _validate_render_plans,
)
from .job_orchestration_scaffold_anchor import _fake_hass, _first_result_payload, _run
from .job_orchestration_subscription_progress_anchor import _dispatch_subscribe, _subscriptions
from .job_orchestration_worker_dispatch_rendering_anchor import (
    WORKER_TEST_TOKEN,
    FakeWorkerRenderer,
    _latest_worker_dispatch_from_dispatch,
    _validate_render_requests,
    _validate_worker_dispatch_render_results,
    _validate_worker_dispatches,
    _validate_worker_history_series,
    _validate_worker_transport_requests,
    _worker_call_summaries,
    _worker_dispatches,
    _worker_dispatch_summary,
)
from .websocket_command_registration_anchor import FakeWebSocketApiModule


WORKER_PROGRESS_FILES = [
    "custom_components/isolinear/job_orchestration.py",
    "custom_components/isolinear/worker_renderer.py",
    "custom_components/isolinear/websocket_api.py",
    "custom_components/isolinear/__init__.py",
    "docs/specs/home-assistant-worker-progress-streaming-scaffold-spec.md",
    "bdd/integration/home-assistant-worker-progress-streaming-scaffold-bdd.md",
    "bdd/integration/home-assistant-worker-progress-streaming-scaffold-evidence.md",
    "docs/evals/home_assistant_worker_progress_streaming_scaffold.yaml",
    "docs/schemas/integration-worker-progress.schema.json",
    "docs/schemas/integration-worker-dispatch.schema.json",
    "docs/schemas/worker-transport-request.schema.json",
    "docs/schemas/render-request.schema.json",
    "docs/schemas/render-result.schema.json",
    "docs/schemas/integration-job-snapshot.schema.json",
    "tests/test_worker_progress_streaming_anchor.py",
    "evals/home_assistant_worker_progress_streaming_scaffold.py",
    "src/Isolinear/worker_progress_streaming_anchor.py",
]

WORKER_PROGRESS_FORBIDDEN_SIDE_EFFECT_KEYS = [
    key
    for key in NO_JOB_ORCHESTRATION_CALLS
    if key
    not in {
        "worker_called",
        "chart_rendering_called",
        "subscription_progress_streaming_called",
        "worker_progress_streaming_called",
    }
] + [
    "home_assistant_history_read",
    "history_retrieval_scaffold_written",
]


class FakeStreamingWorkerRenderer(FakeWorkerRenderer):
    def __init__(
        self,
        *,
        endpoint_url: str = "http://worker.local:8765",
        worker_token: str = WORKER_TEST_TOKEN,
        invalid_progress: bool = False,
        leak_token_in_progress: bool = False,
    ) -> None:
        super().__init__(endpoint_url=endpoint_url, worker_token=worker_token)
        self.invalid_progress = invalid_progress
        self.leak_token_in_progress = leak_token_in_progress

    def render_chart(self, transport_request: dict[str, Any]) -> dict[str, Any]:
        response = super().render_chart(transport_request)
        if not response.get("accepted"):
            return response

        if self.invalid_progress:
            response["progress_events"] = [
                {
                    "sequence": 1,
                    "stage": "",
                    "message": "Invalid worker progress payload.",
                    "percent_complete": 125,
                }
            ]
            return response

        if self.leak_token_in_progress:
            response["progress_events"] = [
                {
                    "sequence": 1,
                    "stage": "worker_render_started",
                    "message": f"Worker echoed {self.worker_token}",
                    "percent_complete": 25,
                }
            ]
            return response

        response["progress_events"] = [
            {
                "sequence": 1,
                "stage": "worker_render_started",
                "message": "Worker accepted the render request.",
                "percent_complete": 25,
            },
            {
                "sequence": 2,
                "stage": "worker_render_finished",
                "message": "Worker produced a render result.",
                "percent_complete": 100,
            },
        ]
        return response


class _FakeHttpWorkerResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeHttpWorkerResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class _MalformedHttpProgressUrlopen:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.progress_events = {
            "sequence": 1,
            "stage": "worker_render_started",
            "message": "This malformed HTTP response is not a progress list.",
            "percent_complete": 10,
        }

    def __call__(self, request, timeout: int | float) -> _FakeHttpWorkerResponse:
        body = json.loads(request.data.decode("utf-8"))
        render_request = body["render_request"]
        self.calls.append(
            {
                "url": request.full_url,
                "timeout": timeout,
                "request_id": render_request["request_id"],
            }
        )
        return _FakeHttpWorkerResponse(
            {
                "render_result": {
                    "request_id": render_request["request_id"],
                    "status": "success",
                    "image_id": f"{render_request['request_id']}-image",
                    "image_mime_type": "image/png",
                    "image_path": f"worker://{render_request['request_id']}.png",
                    "error": None,
                    "render_metadata": {
                        "warnings": ["fake_http_worker_renderer"],
                        "codegen_attempts": 0,
                    },
                },
                "progress_events": self.progress_events,
            }
        )


def verify_worker_progress_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in WORKER_PROGRESS_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_subscribed_worker_progress_records_rendering_snapshots(root=None) -> dict[str, Any]:
    root = root or repo_root()
    worker = FakeStreamingWorkerRenderer()
    hass, websocket_api_module = _setup_streaming_hass(
        FakeConfigEntry(
            "worker-progress-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        worker,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-progress-entry",
        "Show sensor.upstairs_temperature",
        1,
    )
    start_snapshot = _first_result_payload(start)
    subscribe = _dispatch_subscribe(
        hass,
        websocket_api_module,
        "worker-progress-entry",
        start_snapshot["job_id"],
        2,
    )
    snapshot_dispatch = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "worker-progress-entry",
        start_snapshot["job_id"],
        3,
    )
    complete_snapshot = _first_result_payload(snapshot_dispatch)
    job = _job(hass, "worker-progress-entry", start_snapshot["job_id"])
    worker_progress_events = _worker_progress_events(hass, "worker-progress-entry")
    worker_dispatches = _worker_dispatches(hass, "worker-progress-entry")
    render_plans = _render_plans(hass, "worker-progress-entry")
    artifacts = _artifacts(hass, "worker-progress-entry")
    return {
        "start": start,
        "subscribe": subscribe,
        "snapshot_dispatch": snapshot_dispatch,
        "start_snapshot": _snapshot_summary(start_snapshot),
        "complete_snapshot": _snapshot_summary(complete_snapshot),
        "rendering_snapshots": [_snapshot_summary(snapshot) for snapshot in _rendering_snapshots(job)],
        "worker_call_count": len(worker.calls),
        "worker_calls": _worker_call_summaries(worker),
        "subscriptions": _subscriptions(_job_store(hass, "worker-progress-entry")),
        "worker_progress_event": _worker_progress_summary(worker_progress_events[0]) if worker_progress_events else None,
        "worker_progress_events": [_worker_progress_summary(event) for event in worker_progress_events],
        "worker_dispatch": _worker_dispatch_summary(worker_dispatches[0]) if worker_dispatches else None,
        "worker_dispatches": [_worker_dispatch_summary(dispatch) for dispatch in worker_dispatches],
        "render_plans": [_render_plan_summary(plan) for plan in render_plans],
        "artifacts": [_artifact_summary(artifact) for artifact in artifacts],
        "job_store": summarize_job_state_store(_job_store(hass, "worker-progress-entry")),
        "orchestration_store": _orchestration_store_summary(hass, "worker-progress-entry"),
        "worker_progress_validation": _validate_worker_progress_events(worker_progress_events, root),
        "worker_progress_snapshot_validation": _validate_worker_progress_snapshots(worker_progress_events, root),
        "worker_dispatch_validation": _validate_worker_dispatches(worker_dispatches, root),
        "worker_transport_validation": _validate_worker_transport_requests(worker.calls, root),
        "render_request_validation": _validate_render_requests(worker.calls, root),
        "render_result_validation": _validate_worker_dispatch_render_results(worker_dispatches, root),
        "render_plan_validation": _validate_render_plans(render_plans, root),
        "chart_spec_validation": _validate_chart_specs(render_plans, root),
        "history_series_validation": _validate_worker_history_series(worker.calls, root),
    }


def verify_worker_progress_links_existing_subscriptions(root=None) -> dict[str, Any]:
    result = verify_subscribed_worker_progress_records_rendering_snapshots(root)
    subscription_ids = [item["subscription_id"] for item in result["subscriptions"]]
    return {
        "subscription_ids": subscription_ids,
        "worker_progress_subscription_ids": [
            event["subscription_ids"]
            for event in result["worker_progress_events"]
        ],
        "all_progress_events_link_subscription": all(
            event["subscription_ids"] == subscription_ids
            for event in result["worker_progress_events"]
        ),
        "worker_progress_events": result["worker_progress_events"],
    }


def verify_worker_progress_contracts_validate(root=None) -> dict[str, Any]:
    root = root or repo_root()
    accepted = verify_subscribed_worker_progress_records_rendering_snapshots(root)
    idempotent = verify_repeated_snapshot_requests_reuse_worker_progress(root)
    isolation = verify_valid_worker_progress_stays_config_entry_scoped(root)
    return {
        "accepted": _validation_summary(accepted),
        "idempotent": {
            "worker_progress_valid": all(item["accepted"] for item in idempotent["worker_progress_validation"]),
            "worker_progress_validation": idempotent["worker_progress_validation"],
        },
        "isolation_entry_a": {
            "worker_progress_valid": all(
                item["accepted"] for item in isolation["entry_a"]["worker_progress_validation"]
            ),
            "worker_progress_snapshot_valid": all(
                item["accepted"] for item in isolation["entry_a"]["worker_progress_snapshot_validation"]
            ),
            "worker_progress_validation": isolation["entry_a"]["worker_progress_validation"],
        },
        "isolation_entry_b": {
            "worker_progress_valid": all(
                item["accepted"] for item in isolation["entry_b"]["worker_progress_validation"]
            ),
            "worker_progress_snapshot_valid": all(
                item["accepted"] for item in isolation["entry_b"]["worker_progress_snapshot_validation"]
            ),
            "worker_progress_validation": isolation["entry_b"]["worker_progress_validation"],
        },
    }


def verify_worker_progress_authorization_redaction(root=None) -> dict[str, Any]:
    result = verify_subscribed_worker_progress_records_rendering_snapshots(root)
    secret_text = verify_worker_progress_secret_text_rejected_before_storage(root)
    stored_authorizations = [
        event["worker"]["authorization"]
        for event in result["worker_progress_events"]
    ]
    evidence_text = str(result) + str(secret_text)
    return {
        "raw_worker_authorization_received": all(
            call["raw_authorization_was_bearer"] for call in result["worker_calls"]
        ),
        "stored_authorizations": stored_authorizations,
        "stored_authorization_redacted": stored_authorizations
        and all(value == "Bearer <redacted>" for value in stored_authorizations),
        "worker_token_absent_from_evidence": WORKER_TEST_TOKEN not in evidence_text,
        "worker_progress_events": result["worker_progress_events"],
        "secret_text": secret_text,
    }


def verify_repeated_snapshot_requests_reuse_worker_progress(root=None) -> dict[str, Any]:
    root = root or repo_root()
    worker = FakeStreamingWorkerRenderer()
    hass, websocket_api_module = _setup_streaming_hass(
        FakeConfigEntry(
            "worker-progress-idempotent-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        worker,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-progress-idempotent-entry",
        "Show sensor.upstairs_temperature",
        10,
    )
    job_id = _first_result_payload(start)["job_id"]
    _dispatch_subscribe(hass, websocket_api_module, "worker-progress-idempotent-entry", job_id, 11)
    first = _dispatch_snapshot(hass, websocket_api_module, "worker-progress-idempotent-entry", job_id, 12)
    second = _dispatch_snapshot(hass, websocket_api_module, "worker-progress-idempotent-entry", job_id, 13)
    first_snapshot = _first_result_payload(first)
    second_snapshot = _first_result_payload(second)
    events = _worker_progress_events(hass, "worker-progress-idempotent-entry")
    worker_dispatches = _worker_dispatches(hass, "worker-progress-idempotent-entry")
    render_plans = _render_plans(hass, "worker-progress-idempotent-entry")
    artifacts = _artifacts(hass, "worker-progress-idempotent-entry")
    job = _job(hass, "worker-progress-idempotent-entry", job_id)
    return {
        "first": first,
        "second": second,
        "first_snapshot": _snapshot_summary(first_snapshot),
        "second_snapshot": _snapshot_summary(second_snapshot),
        "worker_call_count": len(worker.calls),
        "same_snapshot_returned": first_snapshot == second_snapshot,
        "first_worker_dispatch": _worker_dispatch_summary(_latest_worker_dispatch_from_dispatch(first)),
        "second_worker_dispatch": _worker_dispatch_summary(_latest_worker_dispatch_from_dispatch(second)),
        "worker_progress_count": len(events),
        "worker_progress_events": [_worker_progress_summary(event) for event in events],
        "worker_dispatch_count": len(worker_dispatches),
        "render_plan_count": len(render_plans),
        "artifact_count": len(artifacts),
        "complete_snapshot_count": len(
            [snapshot for snapshot in job["snapshots"] if snapshot.get("status") == "complete"]
        ),
        "worker_progress_validation": _validate_worker_progress_events(events, root),
    }


def verify_invalid_worker_progress_rejected_before_storage(root=None) -> dict[str, Any]:
    root = root or repo_root()
    worker = FakeStreamingWorkerRenderer(invalid_progress=True)
    hass, websocket_api_module = _setup_streaming_hass(
        FakeConfigEntry(
            "worker-progress-invalid-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        worker,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-progress-invalid-entry",
        "Show sensor.upstairs_temperature",
        20,
    )
    job_id = _first_result_payload(start)["job_id"]
    _dispatch_subscribe(hass, websocket_api_module, "worker-progress-invalid-entry", job_id, 21)
    snapshot = _dispatch_snapshot(hass, websocket_api_module, "worker-progress-invalid-entry", job_id, 22)
    return {
        "snapshot": snapshot,
        "worker_call_count": len(worker.calls),
        "worker_calls": _worker_call_summaries(worker),
        "error_codes": _error_codes(snapshot),
        "worker_progress_events": _worker_progress_events(hass, "worker-progress-invalid-entry"),
        "worker_dispatches": _worker_dispatches(hass, "worker-progress-invalid-entry"),
        "render_plans": _render_plans(hass, "worker-progress-invalid-entry"),
        "artifacts": _artifacts(hass, "worker-progress-invalid-entry"),
        "complete_snapshots": _complete_snapshots(hass, "worker-progress-invalid-entry", job_id),
    }


def verify_http_worker_non_list_progress_rejected_before_storage(root=None) -> dict[str, Any]:
    opener = _MalformedHttpProgressUrlopen()
    original_urlopen = worker_renderer_module.urllib.request.urlopen
    worker_renderer_module.urllib.request.urlopen = opener
    try:
        worker = HttpJsonWorkerRenderClient(
            endpoint_url="http://worker.local:8765",
            worker_token=WORKER_TEST_TOKEN,
            timeout_seconds=5,
        )
        hass, websocket_api_module = _setup_streaming_hass(
            FakeConfigEntry(
                "worker-progress-http-invalid-entry",
                options={"entity_allowlist": ["sensor.upstairs_temperature"]},
            ),
            worker,
        )
        start = _dispatch_start(
            hass,
            websocket_api_module,
            "worker-progress-http-invalid-entry",
            "Show sensor.upstairs_temperature",
            23,
        )
        job_id = _first_result_payload(start)["job_id"]
        snapshot = _dispatch_snapshot(
            hass,
            websocket_api_module,
            "worker-progress-http-invalid-entry",
            job_id,
            24,
        )
    finally:
        worker_renderer_module.urllib.request.urlopen = original_urlopen

    return {
        "snapshot": snapshot,
        "worker_http_call_count": len(opener.calls),
        "forwarded_progress_type": type(opener.progress_events).__name__,
        "error_codes": _error_codes(snapshot),
        "worker_progress_events": _worker_progress_events(hass, "worker-progress-http-invalid-entry"),
        "worker_dispatches": _worker_dispatches(hass, "worker-progress-http-invalid-entry"),
        "render_plans": _render_plans(hass, "worker-progress-http-invalid-entry"),
        "artifacts": _artifacts(hass, "worker-progress-http-invalid-entry"),
        "complete_snapshots": _complete_snapshots(hass, "worker-progress-http-invalid-entry", job_id),
        "token_absent_from_result": WORKER_TEST_TOKEN not in str(snapshot),
    }


def verify_worker_progress_secret_text_rejected_before_storage(root=None) -> dict[str, Any]:
    worker = FakeStreamingWorkerRenderer(leak_token_in_progress=True)
    hass, websocket_api_module = _setup_streaming_hass(
        FakeConfigEntry(
            "worker-progress-secret-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        worker,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-progress-secret-entry",
        "Show sensor.upstairs_temperature",
        25,
    )
    job_id = _first_result_payload(start)["job_id"]
    _dispatch_subscribe(hass, websocket_api_module, "worker-progress-secret-entry", job_id, 26)
    snapshot = _dispatch_snapshot(hass, websocket_api_module, "worker-progress-secret-entry", job_id, 27)
    return {
        "snapshot": snapshot,
        "worker_call_count": len(worker.calls),
        "error_codes": _error_codes(snapshot),
        "worker_progress_events": _worker_progress_events(hass, "worker-progress-secret-entry"),
        "worker_dispatches": _worker_dispatches(hass, "worker-progress-secret-entry"),
        "render_plans": _render_plans(hass, "worker-progress-secret-entry"),
        "artifacts": _artifacts(hass, "worker-progress-secret-entry"),
        "complete_snapshots": _complete_snapshots(hass, "worker-progress-secret-entry", job_id),
        "token_absent_from_result": WORKER_TEST_TOKEN not in str(snapshot),
    }


def verify_unknown_worker_progress_job_rejected_before_call(root=None) -> dict[str, Any]:
    worker = FakeStreamingWorkerRenderer()
    hass, websocket_api_module = _setup_streaming_hass(
        FakeConfigEntry(
            "worker-progress-unknown-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        worker,
    )
    snapshot = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "worker-progress-unknown-entry",
        "worker-progress-unknown-entry-job-404",
        30,
    )
    return {
        "snapshot": snapshot,
        "worker_call_count": len(worker.calls),
        "error_codes": _error_codes(snapshot),
        "job_store": summarize_job_state_store(_job_store(hass, "worker-progress-unknown-entry")),
        "worker_progress_events": _worker_progress_events(hass, "worker-progress-unknown-entry"),
        "worker_dispatches": _worker_dispatches(hass, "worker-progress-unknown-entry"),
        "render_plans": _render_plans(hass, "worker-progress-unknown-entry"),
        "artifacts": _artifacts(hass, "worker-progress-unknown-entry"),
    }


def verify_cross_config_entry_worker_progress_rejected_before_call(root=None) -> dict[str, Any]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "worker-progress-cross-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "worker-progress-cross-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    worker_a = _install_fake_worker(hass, "worker-progress-cross-entry-a", FakeStreamingWorkerRenderer())
    worker_b = _install_fake_worker(hass, "worker-progress-cross-entry-b", FakeStreamingWorkerRenderer())
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-progress-cross-entry-a",
        "Show sensor.upstairs_temperature",
        40,
    )
    start_b = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-progress-cross-entry-b",
        "Show binary_sensor.office_window",
        41,
    )
    snapshot_a = _first_result_payload(start_a)
    snapshot_b = _first_result_payload(start_b)
    _dispatch_subscribe(hass, websocket_api_module, "worker-progress-cross-entry-a", snapshot_a["job_id"], 42)
    _dispatch_subscribe(hass, websocket_api_module, "worker-progress-cross-entry-b", snapshot_b["job_id"], 43)
    cross_snapshot = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "worker-progress-cross-entry-b",
        snapshot_a["job_id"],
        44,
    )
    return {
        "entry_a_start": start_a,
        "entry_b_start": start_b,
        "cross_snapshot": cross_snapshot,
        "entry_a_worker_call_count": len(worker_a.calls),
        "entry_b_worker_call_count": len(worker_b.calls),
        "error_codes": _error_codes(cross_snapshot),
        "entry_b_worker_progress_events": _worker_progress_events(hass, "worker-progress-cross-entry-b"),
        "entry_b_worker_dispatches": _worker_dispatches(hass, "worker-progress-cross-entry-b"),
        "entry_b_render_plans": _render_plans(hass, "worker-progress-cross-entry-b"),
        "entry_b_artifacts": _artifacts(hass, "worker-progress-cross-entry-b"),
        "entry_b_complete_snapshots": _complete_snapshots(hass, "worker-progress-cross-entry-b", snapshot_b["job_id"]),
    }


def verify_valid_worker_progress_stays_config_entry_scoped(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "worker-progress-isolation-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "worker-progress-isolation-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    worker_a = _install_fake_worker(hass, "worker-progress-isolation-entry-a", FakeStreamingWorkerRenderer())
    worker_b = _install_fake_worker(hass, "worker-progress-isolation-entry-b", FakeStreamingWorkerRenderer())
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-progress-isolation-entry-a",
        "Show sensor.upstairs_temperature",
        50,
    )
    start_b = _dispatch_start(
        hass,
        websocket_api_module,
        "worker-progress-isolation-entry-b",
        "Show binary_sensor.office_window",
        51,
    )
    snapshot_a = _first_result_payload(start_a)
    snapshot_b = _first_result_payload(start_b)
    subscribe_a = _dispatch_subscribe(
        hass,
        websocket_api_module,
        "worker-progress-isolation-entry-a",
        snapshot_a["job_id"],
        52,
    )
    subscribe_b = _dispatch_subscribe(
        hass,
        websocket_api_module,
        "worker-progress-isolation-entry-b",
        snapshot_b["job_id"],
        53,
    )
    dispatch_a = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "worker-progress-isolation-entry-a",
        snapshot_a["job_id"],
        54,
    )
    dispatch_b = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "worker-progress-isolation-entry-b",
        snapshot_b["job_id"],
        55,
    )
    events_a = _worker_progress_events(hass, "worker-progress-isolation-entry-a")
    events_b = _worker_progress_events(hass, "worker-progress-isolation-entry-b")
    return {
        "entry_a": {
            "subscribe": subscribe_a,
            "snapshot": dispatch_a,
            "worker_call_count": len(worker_a.calls),
            "worker_progress_events": [_worker_progress_summary(event) for event in events_a],
            "subscriptions": _subscriptions(_job_store(hass, "worker-progress-isolation-entry-a")),
            "orchestration_store": _orchestration_store_summary(hass, "worker-progress-isolation-entry-a"),
            "worker_progress_validation": _validate_worker_progress_events(events_a, root),
            "worker_progress_snapshot_validation": _validate_worker_progress_snapshots(events_a, root),
        },
        "entry_b": {
            "subscribe": subscribe_b,
            "snapshot": dispatch_b,
            "worker_call_count": len(worker_b.calls),
            "worker_progress_events": [_worker_progress_summary(event) for event in events_b],
            "subscriptions": _subscriptions(_job_store(hass, "worker-progress-isolation-entry-b")),
            "orchestration_store": _orchestration_store_summary(hass, "worker-progress-isolation-entry-b"),
            "worker_progress_validation": _validate_worker_progress_events(events_b, root),
            "worker_progress_snapshot_validation": _validate_worker_progress_snapshots(events_b, root),
        },
    }


def verify_worker_progress_side_effect_boundaries() -> dict[str, Any]:
    accepted = verify_subscribed_worker_progress_records_rendering_snapshots()
    idempotent = verify_repeated_snapshot_requests_reuse_worker_progress()
    invalid = verify_invalid_worker_progress_rejected_before_storage()
    http_non_list = verify_http_worker_non_list_progress_rejected_before_storage()
    unknown = verify_unknown_worker_progress_job_rejected_before_call()
    cross_entry = verify_cross_config_entry_worker_progress_rejected_before_call()
    isolation = verify_valid_worker_progress_stays_config_entry_scoped()
    setup = _setup_streaming_hass(
        FakeConfigEntry(
            "worker-progress-side-effects-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        FakeStreamingWorkerRenderer(),
    )[0].data[DOMAIN]["worker-progress-side-effects-entry"]

    observed = [
        {"name": "accepted_worker_progress_snapshot", **accepted["snapshot_dispatch"]["orchestration"]},
        {"name": "accepted_subscribe", **accepted["subscribe"]["orchestration"]},
        {"name": "idempotent_first_snapshot", **idempotent["first"]["orchestration"]},
        {"name": "idempotent_second_snapshot", **idempotent["second"]["orchestration"]},
        {"name": "invalid_worker_progress", **invalid["snapshot"]["orchestration"]},
        {"name": "http_non_list_worker_progress", **http_non_list["snapshot"]["orchestration"]},
        {"name": "unknown_worker_progress_job", **unknown["snapshot"]["orchestration"]},
        {"name": "cross_config_entry", **cross_entry["cross_snapshot"]["orchestration"]},
        {"name": "entry_a_worker_progress", **isolation["entry_a"]["snapshot"]["orchestration"]},
        {"name": "entry_b_worker_progress", **isolation["entry_b"]["snapshot"]["orchestration"]},
        {"name": "setup_orchestration", **setup[DATA_JOB_ORCHESTRATION_SETUP]["orchestration"]},
        {"name": "websocket_registration", **setup["websocket_api"]["orchestration"]},
    ]

    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in WORKER_PROGRESS_FORBIDDEN_SIDE_EFFECT_KEYS
    }
    allowed_aggregate = {
        "worker_called": any(item.get("worker_called") for item in observed),
        "chart_rendering_called": any(item.get("chart_rendering_called") for item in observed),
        "worker_progress_streaming_called": any(
            item.get("worker_progress_streaming_called") for item in observed
        ),
        "worker_progress_bookkeeping_written": any(
            item.get("worker_progress_bookkeeping_written") for item in observed
        ),
        "worker_dispatch_bookkeeping_written": any(
            item.get("worker_dispatch_bookkeeping_written") for item in observed
        ),
        "render_plan_bookkeeping_written": any(item.get("render_plan_bookkeeping_written") for item in observed),
        "artifact_metadata_bookkeeping_written": any(
            item.get("artifact_metadata_bookkeeping_written") for item in observed
        ),
        "subscription_bookkeeping_written": any(
            item.get("subscription_bookkeeping_written") for item in observed
        ),
        "subscription_progress_streaming_called": any(
            item.get("subscription_progress_streaming_called") for item in observed
        ),
        "job_state_scaffold_written": any(item.get("job_state_scaffold_written") for item in observed),
        "job_orchestration_scaffold_written": any(
            item.get("job_orchestration_scaffold_written") for item in observed
        ),
        "websocket_command_registered": any(item.get("websocket_command_registered") for item in observed),
    }
    return {
        "expected_forbidden": {key: False for key in WORKER_PROGRESS_FORBIDDEN_SIDE_EFFECT_KEYS},
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }


def verify_worker_progress_streaming_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_worker_progress_files(root)
    accepted = verify_subscribed_worker_progress_records_rendering_snapshots(root)
    subscription_linkage = verify_worker_progress_links_existing_subscriptions(root)
    validation = verify_worker_progress_contracts_validate(root)
    redaction = verify_worker_progress_authorization_redaction(root)
    idempotent = verify_repeated_snapshot_requests_reuse_worker_progress(root)
    invalid = verify_invalid_worker_progress_rejected_before_storage(root)
    http_non_list = verify_http_worker_non_list_progress_rejected_before_storage(root)
    unknown_job = verify_unknown_worker_progress_job_rejected_before_call(root)
    cross_entry = verify_cross_config_entry_worker_progress_rejected_before_call(root)
    isolation = verify_valid_worker_progress_stays_config_entry_scoped(root)
    side_effects = verify_worker_progress_side_effect_boundaries()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more worker progress streaming scaffold files are missing.")
    if not accepted["snapshot_dispatch"]["accepted"]:
        failures.append("Accepted worker progress snapshot request did not return a WebSocket result.")
    if accepted["worker_call_count"] != 1:
        failures.append("Accepted worker progress snapshot request did not call the worker exactly once.")
    if len(accepted["rendering_snapshots"]) != 2:
        failures.append("Accepted worker progress did not append two rendering snapshots.")
    if [item["status"] for item in accepted["rendering_snapshots"]] != ["rendering", "rendering"]:
        failures.append("Worker progress snapshots were not stored as rendering snapshots.")
    if len(accepted["worker_progress_events"]) != 2:
        failures.append("Accepted worker progress did not store two progress events.")
    if accepted["worker_progress_event"] and accepted["worker_progress_event"]["event_id"] != "worker-progress-entry-worker-progress-001":
        failures.append("Accepted worker progress did not use the deterministic progress event ID.")
    if accepted["complete_snapshot"]["status"] != "complete":
        failures.append("Worker progress job did not finish with a complete snapshot.")
    if not subscription_linkage["all_progress_events_link_subscription"]:
        failures.append("Worker progress events did not link the existing subscription IDs.")
    if not validation["accepted"]["worker_progress_valid"]:
        failures.append("Accepted worker progress events did not validate.")
    if not validation["accepted"]["worker_progress_snapshot_valid"]:
        failures.append("Accepted worker progress snapshots did not validate.")
    if not validation["accepted"]["worker_transport_valid"]:
        failures.append("Accepted worker transport request did not validate.")
    if not validation["accepted"]["worker_dispatch_valid"]:
        failures.append("Accepted worker dispatch did not validate.")
    if not redaction["raw_worker_authorization_received"]:
        failures.append("Fake worker did not receive bearer authorization.")
    if not redaction["stored_authorization_redacted"] or not redaction["worker_token_absent_from_evidence"]:
        failures.append("Worker progress metadata or evidence leaked authorization.")
    if idempotent["worker_call_count"] != 1:
        failures.append("Repeated snapshot request called the worker more than once.")
    if idempotent["worker_progress_count"] != 2 or idempotent["worker_dispatch_count"] != 1:
        failures.append("Repeated snapshot requests created duplicate worker progress or dispatch state.")
    if not idempotent["same_snapshot_returned"]:
        failures.append("Repeated snapshot request did not return the existing complete snapshot.")
    if invalid["error_codes"] != ["invalid_integration_worker_progress"]:
        failures.append("Invalid worker progress did not fail closed with invalid_integration_worker_progress.")
    if invalid["worker_progress_events"] or invalid["worker_dispatches"] or invalid["render_plans"] or invalid["artifacts"]:
        failures.append("Invalid worker progress stored metadata after rejection.")
    if http_non_list["error_codes"] != ["invalid_integration_worker_progress"]:
        failures.append("Malformed HTTP worker progress did not fail closed with invalid_integration_worker_progress.")
    if (
        http_non_list["worker_progress_events"]
        or http_non_list["worker_dispatches"]
        or http_non_list["render_plans"]
        or http_non_list["artifacts"]
    ):
        failures.append("Malformed HTTP worker progress stored metadata after rejection.")
    if not http_non_list["token_absent_from_result"]:
        failures.append("Malformed HTTP worker progress rejection leaked token material.")
    if redaction["secret_text"]["error_codes"] != ["invalid_integration_worker_progress"]:
        failures.append("Worker progress secret text did not fail closed with invalid_integration_worker_progress.")
    if (
        redaction["secret_text"]["worker_progress_events"]
        or redaction["secret_text"]["worker_dispatches"]
        or redaction["secret_text"]["render_plans"]
        or redaction["secret_text"]["artifacts"]
    ):
        failures.append("Worker progress secret text stored metadata after rejection.")
    if not redaction["secret_text"]["token_absent_from_result"]:
        failures.append("Worker progress secret text rejection leaked token material.")
    if unknown_job["worker_call_count"] != 0 or unknown_job["error_codes"] != ["unknown_job"]:
        failures.append("Unknown worker progress job did not fail before worker call.")
    if unknown_job["worker_progress_events"]:
        failures.append("Unknown worker progress job recorded progress metadata.")
    if cross_entry["entry_a_worker_call_count"] != 0 or cross_entry["entry_b_worker_call_count"] != 0:
        failures.append("Cross-config-entry worker progress request called a worker.")
    if cross_entry["error_codes"] != ["unknown_job"]:
        failures.append("Cross-config-entry worker progress request did not fail closed as unknown_job.")
    if cross_entry["entry_b_worker_progress_events"]:
        failures.append("Cross-config-entry worker progress request recorded entry B progress.")
    if len(isolation["entry_a"]["worker_progress_events"]) != 2 or len(isolation["entry_b"]["worker_progress_events"]) != 2:
        failures.append("Valid worker progress events did not stay isolated by config entry.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("Worker progress scaffold reported forbidden side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("Worker progress scaffold did not report expected allowed side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "accepted": accepted,
        "subscription_linkage": subscription_linkage,
        "validation": validation,
        "redaction": redaction,
        "idempotent": idempotent,
        "invalid": invalid,
        "http_non_list": http_non_list,
        "unknown_job": unknown_job,
        "cross_entry": cross_entry,
        "isolation": isolation,
        "side_effects": side_effects,
    }


def _setup_streaming_hass(
    entry: FakeConfigEntry,
    worker: Any,
) -> tuple[Any, FakeWebSocketApiModule]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    setup_accepted = _run(async_setup_entry(hass, entry))
    if not setup_accepted:
        raise AssertionError(f"async_setup_entry rejected {entry.entry_id}")
    _install_fake_worker(hass, entry.entry_id, worker)
    return hass, websocket_api_module


def _install_fake_worker(hass: Any, entry_id: str, worker: Any) -> Any:
    hass.data[DOMAIN][entry_id][DATA_WORKER_RENDER_CLIENT] = worker
    return worker


def _worker_progress_events(hass: Any, entry_id: str) -> list[dict[str, Any]]:
    store = hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION]
    return [
        deepcopy(store.get("worker_progress_events", {})[event_id])
        for event_id in store.get("worker_progress_event_order", [])
        if event_id in store.get("worker_progress_events", {})
    ]


def _rendering_snapshots(job: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        deepcopy(snapshot)
        for snapshot in job.get("snapshots", [])
        if snapshot.get("status") == "rendering"
    ]


def _orchestration_store_summary(hass: Any, entry_id: str) -> dict[str, Any]:
    return summarize_job_orchestration_store(hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION])


def _validate_worker_progress_events(events: list[dict[str, Any]], root) -> list[dict[str, Any]]:
    return [_validate_worker_progress_event(event, root) for event in events]


def _validate_worker_progress_event(event: dict[str, Any], root) -> dict[str, Any]:
    try:
        validate_contract("integration-worker-progress", event, repo_root=root)
        validate_contract("integration-job-snapshot", event["snapshot"], repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "contract_validation_failed",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "event_id": event["event_id"],
        "job_id": event["job_id"],
        "snapshot_id": event["snapshot_id"],
        "stage": event["stage"],
        "authorization": event["worker"]["authorization"],
    }


def _validate_worker_progress_snapshots(events: list[dict[str, Any]], root) -> list[dict[str, Any]]:
    results = []
    for event in events:
        try:
            validate_contract("integration-job-snapshot", event["snapshot"], repo_root=root)
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
                    "snapshot_id": event["snapshot"]["snapshot_id"],
                    "job_id": event["snapshot"]["job_id"],
                    "status": event["snapshot"]["status"],
                    "progress_stage": event["snapshot"]["progress"]["stage"],
                }
            )
    return results


def _validation_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "worker_progress_valid": all(item["accepted"] for item in result["worker_progress_validation"]),
        "worker_progress_snapshot_valid": all(
            item["accepted"] for item in result["worker_progress_snapshot_validation"]
        ),
        "worker_dispatch_valid": all(item["accepted"] for item in result["worker_dispatch_validation"]),
        "worker_transport_valid": all(item["accepted"] for item in result["worker_transport_validation"]),
        "render_request_valid": all(item["accepted"] for item in result["render_request_validation"]),
        "render_result_valid": all(item["accepted"] for item in result["render_result_validation"]),
        "render_plan_valid": all(item["accepted"] for item in result["render_plan_validation"]),
        "chart_spec_valid": all(item["accepted"] for item in result["chart_spec_validation"]),
        "history_series_valid": all(item["accepted"] for item in result["history_series_validation"]),
        "worker_progress_validation": result["worker_progress_validation"],
        "worker_progress_snapshot_validation": result["worker_progress_snapshot_validation"],
        "worker_dispatch_validation": result["worker_dispatch_validation"],
        "worker_transport_validation": result["worker_transport_validation"],
        "render_request_validation": result["render_request_validation"],
        "render_result_validation": result["render_result_validation"],
        "render_plan_validation": result["render_plan_validation"],
        "chart_spec_validation": result["chart_spec_validation"],
        "history_series_validation": result["history_series_validation"],
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


def _render_plan_summary(render_plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "render_plan_id": render_plan["render_plan_id"],
        "config_entry_id": render_plan["config_entry_id"],
        "job_id": render_plan["job_id"],
        "source_snapshot_id": render_plan["source_snapshot_id"],
        "artifact_id": render_plan["artifact_id"],
        "status": render_plan["status"],
        "history_entity_ids": deepcopy(render_plan["history_entity_ids"]),
    }


def _worker_progress_summary(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event["event_id"],
        "type": event["type"],
        "config_entry_id": event["config_entry_id"],
        "job_id": event["job_id"],
        "worker": deepcopy(event["worker"]),
        "request_id": event["request_id"],
        "sequence": event["sequence"],
        "stage": event["stage"],
        "message": event["message"],
        "percent_complete": event["percent_complete"],
        "subscription_ids": deepcopy(event["subscription_ids"]),
        "snapshot_id": event["snapshot_id"],
        "snapshot": _snapshot_summary(event["snapshot"]),
        "validation": deepcopy(event["validation"]),
        "warnings": deepcopy(event["warnings"]),
    }
