from __future__ import annotations

from copy import deepcopy
from typing import Any

from custom_components.isolinear import async_setup_entry
from custom_components.isolinear.const import DOMAIN, INTEGRATION_COMMAND_TYPES, INTEGRATION_WS_VERSION
from custom_components.isolinear.job_orchestration import (
    DATA_JOB_ORCHESTRATION,
    DATA_JOB_ORCHESTRATION_SETUP,
    DATA_JOB_ORCHESTRATION_TIME_RANGE,
    NO_JOB_ORCHESTRATION_CALLS,
    summarize_job_orchestration_store,
)
from custom_components.isolinear.job_state import DATA_JOB_STATE, summarize_job_state_store

from .contracts import ContractValidationError, validate_contract
from .dashboard_card_anchor import repo_root
from .entity_catalog_scaffold_anchor import FakeConfigEntry
from .history_retrieval_scaffold_anchor import fake_history_data, history_time_range
from .job_orchestration_scaffold_anchor import _fake_hass, _first_result_payload, _run
from .websocket_command_registration_anchor import FakeWebSocketApiModule


SUBSCRIPTION_PROGRESS_FILES = [
    "custom_components/isolinear/job_orchestration.py",
    "custom_components/isolinear/websocket_api.py",
    "docs/specs/home-assistant-job-orchestration-subscription-progress-streaming-scaffold-spec.md",
    "bdd/integration/home-assistant-job-orchestration-subscription-progress-streaming-scaffold-bdd.md",
    "bdd/integration/home-assistant-job-orchestration-subscription-progress-streaming-scaffold-evidence.md",
    "docs/evals/home_assistant_job_orchestration_subscription_progress_scaffold.yaml",
    "tests/test_job_orchestration_subscription_progress_anchor.py",
    "evals/home_assistant_job_orchestration_subscription_progress_scaffold.py",
    "src/Isolinear/job_orchestration_subscription_progress_anchor.py",
]

SUBSCRIPTION_PROGRESS_FORBIDDEN_SIDE_EFFECT_KEYS = [
    key
    for key in NO_JOB_ORCHESTRATION_CALLS
    if key != "subscription_progress_streaming_called"
]


def verify_subscription_progress_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in SUBSCRIPTION_PROGRESS_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_accepted_subscription_records_progress_event(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_subscription_hass(
        FakeConfigEntry(
            "subscription-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        )
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "subscription-entry",
        "Show sensor.upstairs_temperature",
        1,
    )
    start_snapshot = _first_result_payload(start)
    subscribe = _dispatch_subscribe(
        hass,
        websocket_api_module,
        "subscription-entry",
        start_snapshot["job_id"],
        2,
    )
    subscribe_snapshot = _first_result_payload(subscribe)
    job_store = _job_store(hass, "subscription-entry")
    subscriptions = _subscriptions(job_store)
    progress_events = _progress_events(hass, "subscription-entry")
    return {
        "start": start,
        "subscribe": subscribe,
        "start_snapshot": start_snapshot,
        "subscribe_snapshot": subscribe_snapshot,
        "latest_snapshot_returned": subscribe_snapshot == start_snapshot,
        "job_store": summarize_job_state_store(job_store),
        "subscription": subscriptions[0] if subscriptions else None,
        "progress_event": progress_events[0] if progress_events else None,
        "progress_events": progress_events,
        "orchestration_store": _orchestration_store_summary(hass, "subscription-entry"),
        "snapshot_validation": _validate_snapshot(subscribe_snapshot, root),
        "progress_event_snapshot_validation": _validate_event_snapshots(progress_events, root),
    }


def verify_unknown_subscription_job_rejected_before_storage(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_subscription_hass(
        FakeConfigEntry(
            "unknown-subscription-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        )
    )
    subscribe = _dispatch_subscribe(
        hass,
        websocket_api_module,
        "unknown-subscription-entry",
        "unknown-subscription-entry-job-404",
        10,
    )
    job_store = _job_store(hass, "unknown-subscription-entry")
    return {
        "subscribe": subscribe,
        "error_codes": _error_codes(subscribe),
        "job_store": summarize_job_state_store(job_store),
        "subscriptions": _subscriptions(job_store),
        "progress_events": _progress_events(hass, "unknown-subscription-entry"),
        "snapshot_validation": _validate_event_snapshots([], root),
    }


def verify_cross_config_entry_subscription_rejected(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    hass.data[DOMAIN][DATA_JOB_ORCHESTRATION_TIME_RANGE] = history_time_range()
    entry_a = FakeConfigEntry(
        "subscription-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "subscription-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "subscription-entry-a",
        "Show sensor.upstairs_temperature",
        20,
    )
    start_b = _dispatch_start(
        hass,
        websocket_api_module,
        "subscription-entry-b",
        "Show binary_sensor.office_window",
        21,
    )
    snapshot_a = _first_result_payload(start_a)
    snapshot_b = _first_result_payload(start_b)
    cross_subscribe = _dispatch_subscribe(
        hass,
        websocket_api_module,
        "subscription-entry-b",
        snapshot_a["job_id"],
        22,
    )
    job_store_b = _job_store(hass, "subscription-entry-b")
    return {
        "entry_a_start": start_a,
        "entry_b_start": start_b,
        "entry_a_snapshot_validation": _validate_snapshot(snapshot_a, root),
        "entry_b_snapshot_validation": _validate_snapshot(snapshot_b, root),
        "cross_subscribe": cross_subscribe,
        "error_codes": _error_codes(cross_subscribe),
        "entry_a_subscriptions": _subscriptions(_job_store(hass, "subscription-entry-a")),
        "entry_b_subscriptions": _subscriptions(job_store_b),
        "entry_a_progress_events": _progress_events(hass, "subscription-entry-a"),
        "entry_b_progress_events": _progress_events(hass, "subscription-entry-b"),
    }


def verify_valid_subscriptions_stay_config_entry_scoped(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module, history_by_entity=deepcopy(fake_history_data()))
    hass.data[DOMAIN][DATA_JOB_ORCHESTRATION_TIME_RANGE] = history_time_range()
    entry_a = FakeConfigEntry(
        "valid-subscription-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "valid-subscription-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "valid-subscription-entry-a",
        "Show sensor.upstairs_temperature",
        30,
    )
    start_b = _dispatch_start(
        hass,
        websocket_api_module,
        "valid-subscription-entry-b",
        "Show binary_sensor.office_window",
        31,
    )
    snapshot_a = _first_result_payload(start_a)
    snapshot_b = _first_result_payload(start_b)
    subscribe_a = _dispatch_subscribe(
        hass,
        websocket_api_module,
        "valid-subscription-entry-a",
        snapshot_a["job_id"],
        32,
    )
    subscribe_b = _dispatch_subscribe(
        hass,
        websocket_api_module,
        "valid-subscription-entry-b",
        snapshot_b["job_id"],
        33,
    )
    events_a = _progress_events(hass, "valid-subscription-entry-a")
    events_b = _progress_events(hass, "valid-subscription-entry-b")
    return {
        "entry_a": {
            "start": start_a,
            "subscribe": subscribe_a,
            "snapshot": _first_result_payload(subscribe_a),
            "subscriptions": _subscriptions(_job_store(hass, "valid-subscription-entry-a")),
            "progress_events": events_a,
            "orchestration_store": _orchestration_store_summary(hass, "valid-subscription-entry-a"),
            "snapshot_validation": _validate_snapshot(_first_result_payload(subscribe_a), root),
            "progress_event_snapshot_validation": _validate_event_snapshots(events_a, root),
        },
        "entry_b": {
            "start": start_b,
            "subscribe": subscribe_b,
            "snapshot": _first_result_payload(subscribe_b),
            "subscriptions": _subscriptions(_job_store(hass, "valid-subscription-entry-b")),
            "progress_events": events_b,
            "orchestration_store": _orchestration_store_summary(hass, "valid-subscription-entry-b"),
            "snapshot_validation": _validate_snapshot(_first_result_payload(subscribe_b), root),
            "progress_event_snapshot_validation": _validate_event_snapshots(events_b, root),
        },
    }


def verify_subscription_progress_snapshots_validate(root=None) -> dict[str, Any]:
    root = root or repo_root()
    accepted = verify_accepted_subscription_records_progress_event(root)
    isolation = verify_valid_subscriptions_stay_config_entry_scoped(root)
    return {
        "accepted": {
            "returned_snapshot_valid": accepted["snapshot_validation"]["accepted"],
            "event_snapshots_valid": all(
                item["accepted"] for item in accepted["progress_event_snapshot_validation"]
            ),
            "snapshot_validation": accepted["snapshot_validation"],
            "progress_event_snapshot_validation": accepted["progress_event_snapshot_validation"],
        },
        "isolation_entry_a": {
            "returned_snapshot_valid": isolation["entry_a"]["snapshot_validation"]["accepted"],
            "event_snapshots_valid": all(
                item["accepted"] for item in isolation["entry_a"]["progress_event_snapshot_validation"]
            ),
            "snapshot_validation": isolation["entry_a"]["snapshot_validation"],
            "progress_event_snapshot_validation": isolation["entry_a"]["progress_event_snapshot_validation"],
        },
        "isolation_entry_b": {
            "returned_snapshot_valid": isolation["entry_b"]["snapshot_validation"]["accepted"],
            "event_snapshots_valid": all(
                item["accepted"] for item in isolation["entry_b"]["progress_event_snapshot_validation"]
            ),
            "snapshot_validation": isolation["entry_b"]["snapshot_validation"],
            "progress_event_snapshot_validation": isolation["entry_b"]["progress_event_snapshot_validation"],
        },
    }


def verify_subscription_progress_side_effect_boundaries() -> dict[str, Any]:
    accepted = verify_accepted_subscription_records_progress_event()
    unknown = verify_unknown_subscription_job_rejected_before_storage()
    cross_entry = verify_cross_config_entry_subscription_rejected()
    isolation = verify_valid_subscriptions_stay_config_entry_scoped()
    setup = _setup_subscription_hass(
        FakeConfigEntry(
            "side-effects-subscription-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        )
    )[0].data[DOMAIN]["side-effects-subscription-entry"]

    observed = [
        {"name": "accepted_subscribe", **accepted["subscribe"]["orchestration"]},
        {"name": "unknown_subscribe_job", **unknown["subscribe"]["orchestration"]},
        {"name": "cross_config_entry", **cross_entry["cross_subscribe"]["orchestration"]},
        {"name": "entry_a_subscribe", **isolation["entry_a"]["subscribe"]["orchestration"]},
        {"name": "entry_b_subscribe", **isolation["entry_b"]["subscribe"]["orchestration"]},
        {"name": "setup_orchestration", **setup[DATA_JOB_ORCHESTRATION_SETUP]["orchestration"]},
        {"name": "websocket_registration", **setup["websocket_api"]["orchestration"]},
    ]

    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in SUBSCRIPTION_PROGRESS_FORBIDDEN_SIDE_EFFECT_KEYS
    }
    allowed_aggregate = {
        "subscription_bookkeeping_written": any(
            item.get("subscription_bookkeeping_written") for item in observed
        ),
        "subscription_progress_streaming_called": any(
            item.get("subscription_progress_streaming_called") for item in observed
        ),
        "job_orchestration_scaffold_written": any(
            item.get("job_orchestration_scaffold_written") for item in observed
        ),
        "websocket_command_registered": any(item.get("websocket_command_registered") for item in observed),
    }
    return {
        "expected_forbidden": {
            key: NO_JOB_ORCHESTRATION_CALLS[key]
            for key in SUBSCRIPTION_PROGRESS_FORBIDDEN_SIDE_EFFECT_KEYS
        },
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }


def verify_job_orchestration_subscription_progress_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_subscription_progress_files(root)
    accepted = verify_accepted_subscription_records_progress_event(root)
    unknown_job = verify_unknown_subscription_job_rejected_before_storage(root)
    cross_entry = verify_cross_config_entry_subscription_rejected(root)
    isolation = verify_valid_subscriptions_stay_config_entry_scoped(root)
    snapshot_validation = verify_subscription_progress_snapshots_validate(root)
    side_effects = verify_subscription_progress_side_effect_boundaries()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more subscription/progress scaffold files are missing.")
    if not accepted["subscribe"]["accepted"]:
        failures.append("Accepted subscribe did not return a WebSocket result.")
    if not accepted["latest_snapshot_returned"]:
        failures.append("Accepted subscribe did not immediately return the latest job snapshot.")
    if accepted["subscription"] is None:
        failures.append("Accepted subscribe did not record a job-state subscription.")
    elif accepted["subscription"]["subscription_id"] != "subscription-entry-job-001-subscription-001":
        failures.append("Accepted subscribe did not record the deterministic subscription ID.")
    if accepted["progress_event"] is None:
        failures.append("Accepted subscribe did not record a progress event.")
    elif accepted["progress_event"]["event_id"] != "subscription-entry-progress-event-001":
        failures.append("Accepted subscribe did not record the deterministic progress event ID.")
    if accepted["progress_event"] and accepted["progress_event"]["snapshot_id"] != accepted["start_snapshot"]["snapshot_id"]:
        failures.append("Accepted subscribe progress event did not reference the latest snapshot.")
    if unknown_job["error_codes"] != ["unknown_job"]:
        failures.append("Unknown subscribe job did not fail closed with unknown_job.")
    if unknown_job["subscriptions"]:
        failures.append("Unknown subscribe job recorded a subscription.")
    if unknown_job["progress_events"]:
        failures.append("Unknown subscribe job recorded a progress event.")
    if cross_entry["error_codes"] != ["unknown_job"]:
        failures.append("Cross-config-entry subscribe did not fail closed as unknown_job.")
    if cross_entry["entry_b_subscriptions"]:
        failures.append("Cross-config-entry subscribe recorded a subscription in entry B.")
    if cross_entry["entry_b_progress_events"]:
        failures.append("Cross-config-entry subscribe recorded a progress event in entry B.")
    if len(isolation["entry_a"]["subscriptions"]) != 1 or len(isolation["entry_b"]["subscriptions"]) != 1:
        failures.append("Valid subscriptions did not stay isolated by config entry.")
    if len(isolation["entry_a"]["progress_events"]) != 1 or len(isolation["entry_b"]["progress_events"]) != 1:
        failures.append("Valid progress events did not stay isolated by config entry.")
    if not snapshot_validation["accepted"]["returned_snapshot_valid"]:
        failures.append("Accepted subscribe returned snapshot did not validate.")
    if not snapshot_validation["accepted"]["event_snapshots_valid"]:
        failures.append("Accepted progress event snapshot did not validate.")
    if not snapshot_validation["isolation_entry_a"]["event_snapshots_valid"]:
        failures.append("Entry A progress event snapshot did not validate.")
    if not snapshot_validation["isolation_entry_b"]["event_snapshots_valid"]:
        failures.append("Entry B progress event snapshot did not validate.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("Subscription/progress scaffold reported forbidden side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("Subscription/progress scaffold did not report expected allowed side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "accepted": accepted,
        "unknown_job": unknown_job,
        "cross_entry": cross_entry,
        "isolation": isolation,
        "snapshot_validation": snapshot_validation,
        "side_effects": side_effects,
    }


def _setup_subscription_hass(entry: FakeConfigEntry) -> tuple[Any, FakeWebSocketApiModule]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module, history_by_entity=deepcopy(fake_history_data()))
    hass.data[DOMAIN][DATA_JOB_ORCHESTRATION_TIME_RANGE] = history_time_range()
    setup_accepted = _run(async_setup_entry(hass, entry))
    if not setup_accepted:
        raise AssertionError(f"async_setup_entry rejected {entry.entry_id}")
    return hass, websocket_api_module


def _dispatch_start(
    hass: Any,
    websocket_api_module: FakeWebSocketApiModule,
    entry_id: str,
    prompt: str,
    message_id: int,
) -> dict[str, Any]:
    return websocket_api_module.dispatch(
        hass,
        {
            "id": message_id,
            "type": INTEGRATION_COMMAND_TYPES["start_job"],
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": entry_id,
            "prompt": prompt,
        },
    )


def _dispatch_subscribe(
    hass: Any,
    websocket_api_module: FakeWebSocketApiModule,
    entry_id: str,
    job_id: str,
    message_id: int,
) -> dict[str, Any]:
    return websocket_api_module.dispatch(
        hass,
        {
            "id": message_id,
            "type": INTEGRATION_COMMAND_TYPES["subscribe_job"],
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": entry_id,
            "job_id": job_id,
        },
    )


def _error_codes(dispatch_result: dict[str, Any]) -> list[str]:
    return [
        item["code"]
        for item in dispatch_result["connection"]["errors"]
    ]


def _job_store(hass: Any, entry_id: str) -> dict[str, Any]:
    return hass.data[DOMAIN][entry_id][DATA_JOB_STATE]


def _subscriptions(job_store: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        deepcopy(job_store["subscriptions"][subscription_id])
        for subscription_id in job_store.get("subscription_order", [])
        if subscription_id in job_store.get("subscriptions", {})
    ]


def _progress_events(hass: Any, entry_id: str) -> list[dict[str, Any]]:
    store = hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION]
    return [
        deepcopy(store.get("progress_events", {})[event_id])
        for event_id in store.get("progress_event_order", [])
        if event_id in store.get("progress_events", {})
    ]


def _orchestration_store_summary(hass: Any, entry_id: str) -> dict[str, Any]:
    return summarize_job_orchestration_store(hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION])


def _validate_event_snapshots(events: list[dict[str, Any]], root) -> list[dict[str, Any]]:
    return [_validate_snapshot(event.get("snapshot"), root) for event in events]


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
    }
