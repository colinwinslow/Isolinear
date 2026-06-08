from __future__ import annotations

from copy import deepcopy
from typing import Any

from custom_components.isolinear.const import DOMAIN, INTEGRATION_COMMAND_TYPES, INTEGRATION_WS_VERSION
from custom_components.isolinear.entity_catalog import DATA_ENTITY_METADATA
from custom_components.isolinear.history_retrieval import DATA_HISTORY_RETRIEVAL
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
from custom_components.isolinear import async_setup_entry


CLARIFICATION_CONTINUATION_FILES = [
    "custom_components/isolinear/job_orchestration.py",
    "custom_components/isolinear/websocket_api.py",
    "docs/specs/home-assistant-job-orchestration-clarification-continuation-scaffold-spec.md",
    "bdd/integration/home-assistant-job-orchestration-clarification-continuation-scaffold-bdd.md",
    "bdd/integration/home-assistant-job-orchestration-clarification-continuation-scaffold-evidence.md",
    "docs/evals/home_assistant_job_orchestration_clarification_continuation_scaffold.yaml",
    "tests/test_job_orchestration_clarification_continuation_anchor.py",
    "evals/home_assistant_job_orchestration_clarification_continuation_scaffold.py",
    "src/Isolinear/job_orchestration_clarification_continuation_anchor.py",
]


def verify_clarification_continuation_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in CLARIFICATION_CONTINUATION_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_accepted_clarification_resumes_same_job(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_continuation_hass(
        FakeConfigEntry(
            "clarification-entry",
            options={
                "entity_allowlist": [
                    "sensor.upstairs_temperature",
                    "sensor.downstairs_temperature",
                ]
            },
        )
    )
    start = _dispatch_start(hass, websocket_api_module, "clarification-entry", "Show thermostat history", 1)
    start_snapshot = _first_result_payload(start)
    answer = _dispatch_answer(
        hass,
        websocket_api_module,
        "clarification-entry",
        start_snapshot["job_id"],
        start_snapshot["clarification"]["question_id"],
        "sensor_upstairs_temperature",
        2,
    )
    answer_snapshot = _first_result_payload(answer)
    job = _job(hass, "clarification-entry", start_snapshot["job_id"])
    snapshots = list(job["snapshots"])
    return {
        "start": start,
        "answer": answer,
        "start_snapshot": start_snapshot,
        "answer_snapshot": answer_snapshot,
        "job_snapshot_ids": [item["snapshot_id"] for item in snapshots],
        "job_snapshot_statuses": [item["status"] for item in snapshots],
        "job_progress_stages": [item["progress"]["stage"] for item in snapshots],
        "same_job_id": answer_snapshot["job_id"] == start_snapshot["job_id"] if isinstance(answer_snapshot, dict) else False,
        "job_store": summarize_job_state_store(_job_store(hass, "clarification-entry")),
        "history_store": _history_store_summary(hass, "clarification-entry"),
        "orchestration_store": _orchestration_store_summary(hass, "clarification-entry"),
        "run": _latest_run(hass, "clarification-entry"),
        "snapshot_validation": _validate_snapshots(snapshots, root),
    }


def verify_unknown_option_fails_before_history(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_continuation_hass(
        FakeConfigEntry(
            "unknown-option-entry",
            options={
                "entity_allowlist": [
                    "sensor.upstairs_temperature",
                    "sensor.downstairs_temperature",
                ]
            },
        )
    )
    start = _dispatch_start(hass, websocket_api_module, "unknown-option-entry", "Show thermostat history", 10)
    start_snapshot = _first_result_payload(start)
    job = _job(hass, "unknown-option-entry", start_snapshot["job_id"])
    snapshot_count_before = len(job["snapshots"])
    answer = _dispatch_answer(
        hass,
        websocket_api_module,
        "unknown-option-entry",
        start_snapshot["job_id"],
        start_snapshot["clarification"]["question_id"],
        "sensor_basement_temperature",
        11,
    )
    return {
        "start": start,
        "answer": answer,
        "error_codes": _error_codes(answer),
        "snapshot_count_before": snapshot_count_before,
        "snapshot_count_after": len(job["snapshots"]),
        "history_store": _history_store_summary(hass, "unknown-option-entry"),
        "orchestration_store": _orchestration_store_summary(hass, "unknown-option-entry"),
        "run": _latest_run(hass, "unknown-option-entry"),
        "start_snapshot_validation": _validate_snapshot(start_snapshot, root),
    }


def verify_wrong_question_fails_before_history(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_continuation_hass(
        FakeConfigEntry(
            "wrong-question-entry",
            options={
                "entity_allowlist": [
                    "sensor.upstairs_temperature",
                    "sensor.downstairs_temperature",
                ]
            },
        )
    )
    start = _dispatch_start(hass, websocket_api_module, "wrong-question-entry", "Show thermostat history", 20)
    start_snapshot = _first_result_payload(start)
    job = _job(hass, "wrong-question-entry", start_snapshot["job_id"])
    snapshot_count_before = len(job["snapshots"])
    answer = _dispatch_answer(
        hass,
        websocket_api_module,
        "wrong-question-entry",
        start_snapshot["job_id"],
        "select_different_question",
        "sensor_upstairs_temperature",
        21,
    )
    return {
        "start": start,
        "answer": answer,
        "error_codes": _error_codes(answer),
        "snapshot_count_before": snapshot_count_before,
        "snapshot_count_after": len(job["snapshots"]),
        "history_store": _history_store_summary(hass, "wrong-question-entry"),
        "orchestration_store": _orchestration_store_summary(hass, "wrong-question-entry"),
        "run": _latest_run(hass, "wrong-question-entry"),
        "start_snapshot_validation": _validate_snapshot(start_snapshot, root),
    }


def verify_colliding_option_fails_before_history(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    hass.data[DOMAIN][DATA_ENTITY_METADATA].update(
        {
            "sensor.foo_bar": {
                "friendly_name": "Foo Bar Sensor",
                "device_class": "temperature",
                "state_class": "measurement",
                "unit_of_measurement": "degF",
                "area": "Lab",
                "labels": ["collision"],
                "device_name": "Foo Bar",
                "integration": "demo",
                "current_state": "70.0",
                "attributes": {"friendly_name": "Foo Bar Sensor"},
            },
            "sensor_foo.bar": {
                "friendly_name": "Sensor Foo Bar",
                "device_class": "temperature",
                "state_class": "measurement",
                "unit_of_measurement": "degF",
                "area": "Lab",
                "labels": ["collision"],
                "device_name": "Sensor Foo",
                "integration": "demo",
                "current_state": "71.0",
                "attributes": {"friendly_name": "Sensor Foo Bar"},
            },
        }
    )
    entry = FakeConfigEntry(
        "colliding-option-entry",
        options={"entity_allowlist": ["sensor.foo_bar", "sensor_foo.bar"]},
    )
    _run(async_setup_entry(hass, entry))
    start = _dispatch_start(hass, websocket_api_module, "colliding-option-entry", "Show approved history", 25)
    start_snapshot = _first_result_payload(start)
    job = _job(hass, "colliding-option-entry", start_snapshot["job_id"])
    snapshot_count_before = len(job["snapshots"])
    answer = _dispatch_answer(
        hass,
        websocket_api_module,
        "colliding-option-entry",
        start_snapshot["job_id"],
        start_snapshot["clarification"]["question_id"],
        "sensor_foo_bar",
        26,
    )
    return {
        "start": start,
        "answer": answer,
        "start_options": start_snapshot["clarification"]["options"],
        "error_codes": _error_codes(answer),
        "snapshot_count_before": snapshot_count_before,
        "snapshot_count_after": len(job["snapshots"]),
        "history_store": _history_store_summary(hass, "colliding-option-entry"),
        "orchestration_store": _orchestration_store_summary(hass, "colliding-option-entry"),
        "run": _latest_run(hass, "colliding-option-entry"),
        "start_snapshot_validation": _validate_snapshot(start_snapshot, root),
    }


def verify_cross_config_entry_answer_rejected(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "answer-entry-a",
        options={
            "entity_allowlist": [
                "sensor.upstairs_temperature",
                "sensor.downstairs_temperature",
            ]
        },
    )
    entry_b = FakeConfigEntry(
        "answer-entry-b",
        options={
            "entity_allowlist": [
                "sensor.upstairs_temperature",
                "sensor.downstairs_temperature",
            ]
        },
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    start_a = _dispatch_start(hass, websocket_api_module, "answer-entry-a", "Show thermostat history", 30)
    start_b = _dispatch_start(hass, websocket_api_module, "answer-entry-b", "Show thermostat history", 31)
    snapshot_a = _first_result_payload(start_a)
    snapshot_b = _first_result_payload(start_b)
    cross_answer = _dispatch_answer(
        hass,
        websocket_api_module,
        "answer-entry-b",
        snapshot_a["job_id"],
        snapshot_a["clarification"]["question_id"],
        "sensor_upstairs_temperature",
        32,
    )
    return {
        "entry_a_start": start_a,
        "entry_b_start": start_b,
        "cross_answer": cross_answer,
        "error_codes": _error_codes(cross_answer),
        "entry_a_snapshot_validation": _validate_snapshot(snapshot_a, root),
        "entry_b_snapshot_validation": _validate_snapshot(snapshot_b, root),
        "entry_a_history_store": _history_store_summary(hass, "answer-entry-a"),
        "entry_b_history_store": _history_store_summary(hass, "answer-entry-b"),
        "entry_a_orchestration_store": _orchestration_store_summary(hass, "answer-entry-a"),
        "entry_b_orchestration_store": _orchestration_store_summary(hass, "answer-entry-b"),
    }


def verify_valid_continuations_stay_config_entry_scoped(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "continuation-entry-a",
        options={
            "entity_allowlist": [
                "sensor.upstairs_temperature",
                "sensor.downstairs_temperature",
            ]
        },
    )
    entry_b = FakeConfigEntry(
        "continuation-entry-b",
        options={
            "entity_allowlist": [
                "sensor.downstairs_temperature",
                "binary_sensor.office_window",
            ]
        },
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    start_a = _dispatch_start(hass, websocket_api_module, "continuation-entry-a", "Show thermostat history", 40)
    start_b = _dispatch_start(hass, websocket_api_module, "continuation-entry-b", "Show approved history", 41)
    snapshot_a = _first_result_payload(start_a)
    snapshot_b = _first_result_payload(start_b)
    answer_a = _dispatch_answer(
        hass,
        websocket_api_module,
        "continuation-entry-a",
        snapshot_a["job_id"],
        snapshot_a["clarification"]["question_id"],
        "sensor_upstairs_temperature",
        42,
    )
    answer_b = _dispatch_answer(
        hass,
        websocket_api_module,
        "continuation-entry-b",
        snapshot_b["job_id"],
        snapshot_b["clarification"]["question_id"],
        "binary_sensor_office_window",
        43,
    )
    return {
        "entry_a": {
            "start": start_a,
            "answer": answer_a,
            "snapshot": _first_result_payload(answer_a),
            "history_store": _history_store_summary(hass, "continuation-entry-a"),
            "orchestration_store": _orchestration_store_summary(hass, "continuation-entry-a"),
            "run": _latest_run(hass, "continuation-entry-a"),
            "snapshot_validation": _validate_snapshots(
                _job(hass, "continuation-entry-a", snapshot_a["job_id"])["snapshots"],
                root,
            ),
        },
        "entry_b": {
            "start": start_b,
            "answer": answer_b,
            "snapshot": _first_result_payload(answer_b),
            "history_store": _history_store_summary(hass, "continuation-entry-b"),
            "orchestration_store": _orchestration_store_summary(hass, "continuation-entry-b"),
            "run": _latest_run(hass, "continuation-entry-b"),
            "snapshot_validation": _validate_snapshots(
                _job(hass, "continuation-entry-b", snapshot_b["job_id"])["snapshots"],
                root,
            ),
        },
    }


def verify_continuation_snapshots_validate(root=None) -> dict[str, Any]:
    root = root or repo_root()
    success = verify_accepted_clarification_resumes_same_job(root)
    isolation = verify_valid_continuations_stay_config_entry_scoped(root)
    return {
        "success": {
            "all_snapshots_valid": all(item["accepted"] for item in success["snapshot_validation"]),
            "snapshot_validation": success["snapshot_validation"],
        },
        "isolation_entry_a": {
            "all_snapshots_valid": all(item["accepted"] for item in isolation["entry_a"]["snapshot_validation"]),
            "snapshot_validation": isolation["entry_a"]["snapshot_validation"],
        },
        "isolation_entry_b": {
            "all_snapshots_valid": all(item["accepted"] for item in isolation["entry_b"]["snapshot_validation"]),
            "snapshot_validation": isolation["entry_b"]["snapshot_validation"],
        },
    }


def verify_clarification_continuation_side_effect_boundaries() -> dict[str, Any]:
    success = verify_accepted_clarification_resumes_same_job()
    unknown = verify_unknown_option_fails_before_history()
    wrong_question = verify_wrong_question_fails_before_history()
    collision = verify_colliding_option_fails_before_history()
    cross_entry = verify_cross_config_entry_answer_rejected()
    isolation = verify_valid_continuations_stay_config_entry_scoped()
    setup = _setup_continuation_hass(
        FakeConfigEntry(
            "side-effects-continuation-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        )
    )[0].data[DOMAIN]["side-effects-continuation-entry"]

    observed = [
        {"name": "accepted_clarification", **success["answer"]["orchestration"]},
        {"name": "unknown_option", **unknown["answer"]["orchestration"]},
        {"name": "wrong_question", **wrong_question["answer"]["orchestration"]},
        {"name": "colliding_option", **collision["answer"]["orchestration"]},
        {"name": "cross_config_entry", **cross_entry["cross_answer"]["orchestration"]},
        {"name": "entry_a_continuation", **isolation["entry_a"]["answer"]["orchestration"]},
        {"name": "entry_b_continuation", **isolation["entry_b"]["answer"]["orchestration"]},
        {"name": "setup_orchestration", **setup[DATA_JOB_ORCHESTRATION_SETUP]["orchestration"]},
        {"name": "websocket_registration", **setup["websocket_api"]["orchestration"]},
    ]

    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in NO_JOB_ORCHESTRATION_CALLS
    }
    allowed_aggregate = {
        "approved_entity_catalog_read": any(item.get("approved_entity_catalog_read") for item in observed),
        "home_assistant_history_read": any(item.get("home_assistant_history_read") for item in observed),
        "history_retrieval_scaffold_written": any(
            item.get("history_retrieval_scaffold_written") for item in observed
        ),
        "job_state_scaffold_written": any(item.get("job_state_scaffold_written") for item in observed),
        "job_orchestration_scaffold_written": any(
            item.get("job_orchestration_scaffold_written") for item in observed
        ),
        "websocket_command_registered": any(item.get("websocket_command_registered") for item in observed),
    }
    return {
        "expected_forbidden": dict(NO_JOB_ORCHESTRATION_CALLS),
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }


def verify_job_orchestration_clarification_continuation_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_clarification_continuation_files(root)
    accepted = verify_accepted_clarification_resumes_same_job(root)
    unknown_option = verify_unknown_option_fails_before_history(root)
    wrong_question = verify_wrong_question_fails_before_history(root)
    collision = verify_colliding_option_fails_before_history(root)
    cross_entry = verify_cross_config_entry_answer_rejected(root)
    isolation = verify_valid_continuations_stay_config_entry_scoped(root)
    snapshot_validation = verify_continuation_snapshots_validate(root)
    side_effects = verify_clarification_continuation_side_effect_boundaries()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more clarification continuation files are missing.")
    if not accepted["answer"]["accepted"]:
        failures.append("Accepted clarification answer did not return a WebSocket result.")
    if accepted["answer_snapshot"]["snapshot_id"] != "clarification-entry-job-001-snapshot-005":
        failures.append("Accepted clarification did not append deterministic continuation snapshots.")
    if not accepted["same_job_id"]:
        failures.append("Accepted clarification did not resume the same job.")
    if accepted["history_store"]["entity_ids"] != ["sensor.upstairs_temperature"]:
        failures.append("Accepted clarification did not retrieve only the selected approved entity.")
    if "clarification_answer_accepted" not in accepted["job_progress_stages"]:
        failures.append("Accepted clarification did not append a clarification-accepted snapshot.")
    if unknown_option["error_codes"] != ["unknown_clarification_option"]:
        failures.append("Unknown clarification option did not fail closed with the expected code.")
    if unknown_option["history_store"]["series_count"] != 0:
        failures.append("Unknown clarification option read or stored history.")
    if unknown_option["snapshot_count_after"] != unknown_option["snapshot_count_before"]:
        failures.append("Unknown clarification option appended a continuation snapshot.")
    if wrong_question["error_codes"] != ["clarification_question_mismatch"]:
        failures.append("Wrong clarification question did not fail closed with the expected code.")
    if wrong_question["history_store"]["series_count"] != 0:
        failures.append("Wrong clarification question read or stored history.")
    if collision["error_codes"] != ["ambiguous_clarification_option"]:
        failures.append("Colliding clarification option did not fail closed with the expected code.")
    if collision["history_store"]["series_count"] != 0:
        failures.append("Colliding clarification option read or stored history.")
    if collision["snapshot_count_after"] != collision["snapshot_count_before"]:
        failures.append("Colliding clarification option appended a continuation snapshot.")
    if cross_entry["error_codes"] != ["unknown_job"]:
        failures.append("Cross-config-entry clarification answer did not fail as unknown_job.")
    if cross_entry["entry_a_history_store"]["series_count"] != 0 or cross_entry["entry_b_history_store"]["series_count"] != 0:
        failures.append("Cross-config-entry clarification answer read history.")
    if isolation["entry_a"]["history_store"]["entity_ids"] != ["sensor.upstairs_temperature"]:
        failures.append("Entry A continuation history isolation failed.")
    if isolation["entry_b"]["history_store"]["entity_ids"] != ["binary_sensor.office_window"]:
        failures.append("Entry B continuation history isolation failed.")
    if not snapshot_validation["success"]["all_snapshots_valid"]:
        failures.append("Accepted continuation snapshots did not all validate.")
    if not snapshot_validation["isolation_entry_a"]["all_snapshots_valid"]:
        failures.append("Entry A continuation snapshots did not all validate.")
    if not snapshot_validation["isolation_entry_b"]["all_snapshots_valid"]:
        failures.append("Entry B continuation snapshots did not all validate.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("Clarification continuation reported forbidden side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("Clarification continuation did not report expected allowed side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "accepted": accepted,
        "unknown_option": unknown_option,
        "wrong_question": wrong_question,
        "collision": collision,
        "cross_entry": cross_entry,
        "isolation": isolation,
        "snapshot_validation": snapshot_validation,
        "side_effects": side_effects,
    }


def _setup_continuation_hass(
    entry: FakeConfigEntry,
    *,
    history_by_entity: dict[str, Any] | None = None,
) -> tuple[Any, FakeWebSocketApiModule]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module, history_by_entity=deepcopy(history_by_entity or fake_history_data()))
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


def _dispatch_answer(
    hass: Any,
    websocket_api_module: FakeWebSocketApiModule,
    entry_id: str,
    job_id: str,
    question_id: str,
    option_id: str,
    message_id: int,
    *,
    remember: bool = False,
) -> dict[str, Any]:
    return websocket_api_module.dispatch(
        hass,
        {
            "id": message_id,
            "type": INTEGRATION_COMMAND_TYPES["answer_clarification"],
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": entry_id,
            "job_id": job_id,
            "question_id": question_id,
            "option_id": option_id,
            "remember": remember,
        },
    )


def _error_codes(dispatch_result: dict[str, Any]) -> list[str]:
    return [
        item["code"]
        for item in dispatch_result["connection"]["errors"]
    ]


def _job_store(hass: Any, entry_id: str) -> dict[str, Any]:
    return hass.data[DOMAIN][entry_id][DATA_JOB_STATE]


def _job(hass: Any, entry_id: str, job_id: str) -> dict[str, Any]:
    return _job_store(hass, entry_id)["jobs"][job_id]


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
    }
