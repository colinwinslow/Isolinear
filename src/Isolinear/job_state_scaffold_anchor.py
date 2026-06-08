from __future__ import annotations

import asyncio
from typing import Any

from custom_components.isolinear import async_setup_entry, async_unload_entry
from custom_components.isolinear.const import DOMAIN, INTEGRATION_COMMAND_TYPES, INTEGRATION_WS_VERSION
from custom_components.isolinear.job_state import (
    DATA_JOB_STATE,
    NO_JOB_STATE_ORCHESTRATION_CALLS,
    store_validated_job_snapshot,
    summarize_job_state_store,
)

from .contracts import ContractValidationError, validate_contract
from .dashboard_card_anchor import repo_root
from .websocket_command_registration_anchor import (
    FakeConfigEntry,
    FakeHass,
    FakeWebSocketApiModule,
)


JOB_STATE_SCAFFOLD_FILES = [
    "custom_components/isolinear/job_state.py",
    "custom_components/isolinear/websocket_api.py",
    "custom_components/isolinear/__init__.py",
    "docs/specs/home-assistant-job-state-scaffold-spec.md",
    "bdd/integration/home-assistant-job-state-scaffold-bdd.md",
    "docs/evals/home_assistant_job_state_scaffold.yaml",
    "tests/test_job_state_scaffold_anchor.py",
    "evals/home_assistant_job_state_scaffold.py",
]


def verify_job_state_scaffold_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in JOB_STATE_SCAFFOLD_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_start_job_creates_deterministic_state(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_registered_hass("fake-config-entry")
    command = _start_command("fake-config-entry")
    dispatch = websocket_api_module.dispatch(hass, {"id": 1, **command})
    snapshot = _first_result_payload(dispatch)
    snapshot_validation = _validate_snapshot(snapshot, root)
    store = summarize_job_state_store(_raw_store(hass, "fake-config-entry"))
    return {
        "command": command,
        "dispatch": dispatch,
        "snapshot": snapshot,
        "snapshot_validation": snapshot_validation,
        "store": store,
    }


def verify_existing_job_command_updates(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_registered_hass("fake-config-entry")
    start = websocket_api_module.dispatch(hass, {"id": 10, **_start_command("fake-config-entry")})
    job_id = _first_result_payload(start)["job_id"]

    get_snapshot = websocket_api_module.dispatch(
        hass,
        {"id": 11, **_job_command("fake-config-entry", "get_snapshot", job_id)},
    )
    retry = websocket_api_module.dispatch(
        hass,
        {"id": 12, **_job_command("fake-config-entry", "retry_job", job_id)},
    )
    answer = websocket_api_module.dispatch(
        hass,
        {
            "id": 13,
            **_clarification_command("fake-config-entry", job_id),
        },
    )
    results = {
        "start": start,
        "get_snapshot": get_snapshot,
        "retry": retry,
        "answer_clarification": answer,
    }
    snapshots = {
        name: _first_result_payload(result)
        for name, result in results.items()
    }
    snapshot_validation = {
        name: _validate_snapshot(snapshot, root)
        for name, snapshot in snapshots.items()
    }
    store = _raw_store(hass, "fake-config-entry")
    return {
        **results,
        "snapshot_ids": [snapshot["snapshot_id"] for snapshot in snapshots.values()],
        "snapshots": snapshots,
        "snapshot_validation": snapshot_validation,
        "store": {
            **summarize_job_state_store(store),
            "latest_snapshot_id": store["jobs"][job_id]["latest_snapshot"]["snapshot_id"],
            "clarification_answers": list(store["jobs"][job_id]["clarification_answers"]),
        },
    }


def verify_subscription_callback_shape(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_registered_hass("fake-config-entry")
    start = websocket_api_module.dispatch(hass, {"id": 20, **_start_command("fake-config-entry")})
    job_id = _first_result_payload(start)["job_id"]
    subscribe = websocket_api_module.dispatch(
        hass,
        {"id": 21, **_job_command("fake-config-entry", "subscribe_job", job_id)},
    )
    snapshot = _first_result_payload(subscribe)
    store = _raw_store(hass, "fake-config-entry")
    subscription = store["subscriptions"][store["subscription_order"][0]]
    return {
        "start": start,
        "subscribe": subscribe,
        "connection": subscribe["connection"],
        "snapshot": snapshot,
        "snapshot_validation": _validate_snapshot(snapshot, root),
        "subscription": subscription,
        "store": summarize_job_state_store(store),
    }


def verify_config_entry_job_isolation(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_registered_hass("entry-a", "entry-b")
    entry_a_start = websocket_api_module.dispatch(hass, {"id": 30, **_start_command("entry-a")})
    entry_b_start = websocket_api_module.dispatch(hass, {"id": 31, **_start_command("entry-b")})
    entry_a_job_id = _first_result_payload(entry_a_start)["job_id"]
    cross_entry_snapshot = websocket_api_module.dispatch(
        hass,
        {"id": 32, **_job_command("entry-b", "get_snapshot", entry_a_job_id)},
    )
    return {
        "entry_a_start": entry_a_start,
        "entry_b_start": entry_b_start,
        "cross_entry_snapshot": cross_entry_snapshot,
        "entry_a_snapshot_validation": _validate_snapshot(_first_result_payload(entry_a_start), root),
        "entry_b_snapshot_validation": _validate_snapshot(_first_result_payload(entry_b_start), root),
        "entry_a_store": summarize_job_state_store(_raw_store(hass, "entry-a")),
        "entry_b_store": summarize_job_state_store(_raw_store(hass, "entry-b")),
    }


def verify_unknown_jobs_fail_closed() -> dict[str, Any]:
    hass, websocket_api_module = _setup_registered_hass("fake-config-entry")
    commands = {
        "get_snapshot": _job_command("fake-config-entry", "get_snapshot", "missing-job"),
        "retry_job": _job_command("fake-config-entry", "retry_job", "missing-job"),
        "answer_clarification": _clarification_command("fake-config-entry", "missing-job"),
        "subscribe_job": _job_command("fake-config-entry", "subscribe_job", "missing-job"),
    }
    dispatch_results = {
        name: websocket_api_module.dispatch(hass, {"id": index, **command})
        for index, (name, command) in enumerate(commands.items(), start=40)
    }
    return {
        "commands": commands,
        "dispatch_results": dispatch_results,
        "store": summarize_job_state_store(_raw_store(hass, "fake-config-entry")),
    }


def verify_malformed_snapshot_rejected_before_storage() -> dict[str, Any]:
    job = {
        "job_id": "malformed-job-001",
        "prompt": "Bad scaffold snapshot",
        "next_snapshot_number": 1,
        "snapshots": [],
        "latest_snapshot": None,
        "clarification_answers": [],
    }
    malformed_snapshot = {
        "snapshot_id": "malformed-job-001-snapshot-001",
        "job_id": "malformed-job-001",
        "status": "planning",
    }
    result = store_validated_job_snapshot(job, malformed_snapshot)
    return {
        "malformed_snapshot": malformed_snapshot,
        "result": result,
        "snapshots_after_attempt": list(job["snapshots"]),
        "latest_snapshot_after_attempt": job["latest_snapshot"],
    }


def verify_unload_removes_job_state() -> dict[str, Any]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = FakeHass(websocket_api_module, include_entry=False)
    entry = FakeConfigEntry("fake-config-entry")
    setup_accepted = _run(async_setup_entry(hass, entry))
    start = websocket_api_module.dispatch(hass, {"id": 50, **_start_command(entry.entry_id)})
    job_id = _first_result_payload(start)["job_id"]
    subscribe = websocket_api_module.dispatch(
        hass,
        {"id": 51, **_job_command(entry.entry_id, "subscribe_job", job_id)},
    )
    had_job_state_before_unload = DATA_JOB_STATE in hass.data[DOMAIN][entry.entry_id]
    unload_accepted = _run(async_unload_entry(hass, entry))
    return {
        "setup_accepted": setup_accepted,
        "start": start,
        "subscribe": subscribe,
        "had_job_state_before_unload": had_job_state_before_unload,
        "unload_accepted": unload_accepted,
        "entry_present_after_unload": entry.entry_id in hass.data[DOMAIN],
    }


def verify_job_state_side_effect_boundaries() -> dict[str, Any]:
    start = verify_start_job_creates_deterministic_state()
    updates = verify_existing_job_command_updates()
    subscription = verify_subscription_callback_shape()
    isolation = verify_config_entry_job_isolation()
    unknown = verify_unknown_jobs_fail_closed()
    malformed = verify_malformed_snapshot_rejected_before_storage()

    observed = [
        {"name": "start_job", **start["dispatch"]["orchestration"]},
        {"name": "get_snapshot", **updates["get_snapshot"]["orchestration"]},
        {"name": "retry_job", **updates["retry"]["orchestration"]},
        {"name": "answer_clarification", **updates["answer_clarification"]["orchestration"]},
        {"name": "subscribe_job", **subscription["subscribe"]["orchestration"]},
        {"name": "cross_config_entry_snapshot", **isolation["cross_entry_snapshot"]["orchestration"]},
    ]
    observed.extend(
        {"name": f"unknown_{name}", **result["orchestration"]}
        for name, result in unknown["dispatch_results"].items()
    )
    observed.append({"name": "malformed_snapshot_rejection", **malformed["result"].get("orchestration", {})})
    setup_registration = _setup_registered_hass("side-effects-entry")[0].data[DOMAIN]["side-effects-entry"]["websocket_api"]
    observed.append({"name": "websocket_registration", **setup_registration["orchestration"]})

    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in NO_JOB_STATE_ORCHESTRATION_CALLS
    }
    allowed_aggregate = {
        "job_state_scaffold_written": any(item.get("job_state_scaffold_written") for item in observed),
        "subscription_bookkeeping_written": any(
            item.get("subscription_bookkeeping_written") for item in observed
        ),
        "websocket_command_registered": any(item.get("websocket_command_registered") for item in observed),
    }
    return {
        "expected_forbidden": dict(NO_JOB_STATE_ORCHESTRATION_CALLS),
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }


def verify_job_state_scaffold_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_job_state_scaffold_files(root)
    start = verify_start_job_creates_deterministic_state(root)
    updates = verify_existing_job_command_updates(root)
    subscription = verify_subscription_callback_shape(root)
    isolation = verify_config_entry_job_isolation(root)
    unknown = verify_unknown_jobs_fail_closed()
    malformed = verify_malformed_snapshot_rejected_before_storage()
    unload = verify_unload_removes_job_state()
    side_effects = verify_job_state_side_effect_boundaries()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more job state scaffold files are missing.")
    if not start["dispatch"]["accepted"] or not start["snapshot_validation"]["accepted"]:
        failures.append("Starting a job did not return a schema-valid snapshot.")
    if start["snapshot"]["job_id"] != "fake-config-entry-job-001":
        failures.append("Job ID is not deterministic for a fresh runtime.")
    if not all(
        result["accepted"]
        for result in [
            updates["get_snapshot"],
            updates["retry"],
            updates["answer_clarification"],
            subscription["subscribe"],
        ]
    ):
        failures.append("One or more existing-job commands were rejected.")
    if subscription["store"]["subscription_count"] != 1:
        failures.append("Subscribe did not record exactly one subscription shape.")
    if isolation["cross_entry_snapshot"]["accepted"]:
        failures.append("A config entry was able to read another config entry's job.")
    if not all(not result["accepted"] for result in unknown["dispatch_results"].values()):
        failures.append("One or more unknown-job commands were accepted.")
    if malformed["result"]["accepted"] or malformed["snapshots_after_attempt"]:
        failures.append("A malformed job snapshot was stored before schema validation.")
    if unload["entry_present_after_unload"]:
        failures.append("Config-entry unload left job state behind.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("Job state scaffold reported forbidden orchestration side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("Job state scaffold did not report all allowed side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "start": start,
        "updates": updates,
        "subscription": subscription,
        "isolation": isolation,
        "unknown": unknown,
        "malformed": malformed,
        "unload": unload,
        "side_effects": side_effects,
    }


def _setup_registered_hass(*entry_ids: str) -> tuple[FakeHass, FakeWebSocketApiModule]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = FakeHass(websocket_api_module, include_entry=False)
    for entry_id in entry_ids:
        _run(async_setup_entry(hass, FakeConfigEntry(entry_id)))
    return hass, websocket_api_module


def _start_command(entry_id: str, prompt: str = "Compare upstairs and downstairs temperatures") -> dict[str, Any]:
    return {
        "type": INTEGRATION_COMMAND_TYPES["start_job"],
        "version": INTEGRATION_WS_VERSION,
        "config_entry_id": entry_id,
        "prompt": prompt,
    }


def _job_command(entry_id: str, command_name: str, job_id: str) -> dict[str, Any]:
    return {
        "type": INTEGRATION_COMMAND_TYPES[command_name],
        "version": INTEGRATION_WS_VERSION,
        "config_entry_id": entry_id,
        "job_id": job_id,
    }


def _clarification_command(entry_id: str, job_id: str) -> dict[str, Any]:
    return {
        "type": INTEGRATION_COMMAND_TYPES["answer_clarification"],
        "version": INTEGRATION_WS_VERSION,
        "config_entry_id": entry_id,
        "job_id": job_id,
        "question_id": "clarify_upstairs_temperature",
        "option_id": "average_upstairs_temperature",
        "remember": True,
    }


def _raw_store(hass: Any, entry_id: str) -> dict[str, Any]:
    return hass.data[DOMAIN][entry_id][DATA_JOB_STATE]


def _first_result_payload(dispatch_result: dict[str, Any]) -> Any:
    results = dispatch_result["connection"]["results"]
    if not results:
        return None
    return results[0]["result"]


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
        "warnings": snapshot["warnings"],
    }


def _run(coro):
    return asyncio.run(coro)
