from __future__ import annotations

from copy import deepcopy
from typing import Any

from custom_components.isolinear import async_setup_entry
from custom_components.isolinear.const import DOMAIN, INTEGRATION_COMMAND_TYPES, INTEGRATION_WS_VERSION
from custom_components.isolinear.history_retrieval import DATA_HISTORY_RETRIEVAL, DATA_HISTORY_SOURCE
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


RETRY_CONTINUATION_FILES = [
    "custom_components/isolinear/job_orchestration.py",
    "custom_components/isolinear/websocket_api.py",
    "docs/specs/home-assistant-job-orchestration-retry-continuation-scaffold-spec.md",
    "bdd/integration/home-assistant-job-orchestration-retry-continuation-scaffold-bdd.md",
    "bdd/integration/home-assistant-job-orchestration-retry-continuation-scaffold-evidence.md",
    "docs/evals/home_assistant_job_orchestration_retry_continuation_scaffold.yaml",
    "tests/test_job_orchestration_retry_continuation_anchor.py",
    "evals/home_assistant_job_orchestration_retry_continuation_scaffold.py",
    "src/Isolinear/job_orchestration_retry_continuation_anchor.py",
]

RETRY_FORBIDDEN_SIDE_EFFECT_KEYS = [
    key
    for key in NO_JOB_ORCHESTRATION_CALLS
    if key != "retry_behavior_called"
]


def verify_retry_continuation_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in RETRY_CONTINUATION_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_accepted_retry_resumes_same_failed_job(root=None) -> dict[str, Any]:
    root = root or repo_root()
    history = deepcopy(fake_history_data())
    history.pop("sensor.downstairs_temperature", None)
    hass, websocket_api_module = _setup_retry_hass(
        FakeConfigEntry(
            "retry-entry",
            options={"entity_allowlist": ["sensor.downstairs_temperature"]},
        ),
        history_by_entity=history,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "retry-entry",
        "Show sensor.downstairs_temperature",
        1,
    )
    failed_snapshot = _first_result_payload(start)
    job = _job(hass, "retry-entry", failed_snapshot["job_id"])
    snapshot_count_before = len(job["snapshots"])
    hass.data[DOMAIN][DATA_HISTORY_SOURCE]["sensor.downstairs_temperature"] = fake_history_data()[
        "sensor.downstairs_temperature"
    ]
    retry = _dispatch_retry(
        hass,
        websocket_api_module,
        "retry-entry",
        failed_snapshot["job_id"],
        2,
    )
    retry_snapshot = _first_result_payload(retry)
    snapshots = list(job["snapshots"])
    return {
        "start": start,
        "retry": retry,
        "failed_snapshot": failed_snapshot,
        "retry_snapshot": retry_snapshot,
        "snapshot_count_before": snapshot_count_before,
        "snapshot_count_after": len(snapshots),
        "job_snapshot_ids": [item["snapshot_id"] for item in snapshots],
        "job_snapshot_statuses": [item["status"] for item in snapshots],
        "job_progress_stages": [item["progress"]["stage"] for item in snapshots],
        "same_job_id": retry_snapshot["job_id"] == failed_snapshot["job_id"] if isinstance(retry_snapshot, dict) else False,
        "job_store": summarize_job_state_store(_job_store(hass, "retry-entry")),
        "history_store": _history_store_summary(hass, "retry-entry"),
        "orchestration_store": _orchestration_store_summary(hass, "retry-entry"),
        "run": _latest_run(hass, "retry-entry"),
        "snapshot_validation": _validate_snapshots(snapshots, root),
    }


def verify_unknown_retry_job_rejected_before_history(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_retry_hass(
        FakeConfigEntry(
            "unknown-retry-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        )
    )
    history_before = _history_store_summary(hass, "unknown-retry-entry")
    retry = _dispatch_retry(
        hass,
        websocket_api_module,
        "unknown-retry-entry",
        "unknown-retry-entry-job-404",
        10,
    )
    history_after = _history_store_summary(hass, "unknown-retry-entry")
    return {
        "retry": retry,
        "error_codes": _error_codes(retry),
        "job_store": summarize_job_state_store(_job_store(hass, "unknown-retry-entry")),
        "history_before": history_before,
        "history_after": history_after,
        "snapshot_validation": _validate_snapshots([], root),
    }


def verify_non_retryable_job_rejected_before_history(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_retry_hass(
        FakeConfigEntry(
            "non-retryable-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        )
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "non-retryable-entry",
        "Show sensor.upstairs_temperature",
        20,
    )
    snapshot = _first_result_payload(start)
    job = _job(hass, "non-retryable-entry", snapshot["job_id"])
    snapshot_count_before = len(job["snapshots"])
    history_before = _history_store_summary(hass, "non-retryable-entry")
    retry = _dispatch_retry(
        hass,
        websocket_api_module,
        "non-retryable-entry",
        snapshot["job_id"],
        21,
    )
    history_after = _history_store_summary(hass, "non-retryable-entry")
    return {
        "start": start,
        "retry": retry,
        "error_codes": _error_codes(retry),
        "snapshot_count_before": snapshot_count_before,
        "snapshot_count_after": len(job["snapshots"]),
        "history_before": history_before,
        "history_after": history_after,
        "orchestration_store": _orchestration_store_summary(hass, "non-retryable-entry"),
        "start_snapshot_validation": _validate_snapshot(snapshot, root),
    }


def verify_cross_config_entry_retry_rejected(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    history = deepcopy(fake_history_data())
    history.pop("sensor.downstairs_temperature", None)
    hass = _fake_hass(websocket_api_module, history_by_entity=history)
    entry_a = FakeConfigEntry(
        "retry-entry-a",
        options={"entity_allowlist": ["sensor.downstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "retry-entry-b",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "retry-entry-a",
        "Show sensor.downstairs_temperature",
        30,
    )
    start_b = _dispatch_start(
        hass,
        websocket_api_module,
        "retry-entry-b",
        "Show sensor.upstairs_temperature",
        31,
    )
    snapshot_a = _first_result_payload(start_a)
    snapshot_b = _first_result_payload(start_b)
    history_b_before = _history_store_summary(hass, "retry-entry-b")
    cross_retry = _dispatch_retry(
        hass,
        websocket_api_module,
        "retry-entry-b",
        snapshot_a["job_id"],
        32,
    )
    history_b_after = _history_store_summary(hass, "retry-entry-b")
    return {
        "entry_a_start": start_a,
        "entry_b_start": start_b,
        "cross_retry": cross_retry,
        "error_codes": _error_codes(cross_retry),
        "entry_a_snapshot_validation": _validate_snapshot(snapshot_a, root),
        "entry_b_snapshot_validation": _validate_snapshot(snapshot_b, root),
        "entry_a_history_store": _history_store_summary(hass, "retry-entry-a"),
        "entry_b_history_before": history_b_before,
        "entry_b_history_after": history_b_after,
        "entry_a_orchestration_store": _orchestration_store_summary(hass, "retry-entry-a"),
        "entry_b_orchestration_store": _orchestration_store_summary(hass, "retry-entry-b"),
    }


def verify_valid_retries_stay_config_entry_scoped(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    history = deepcopy(fake_history_data())
    history.pop("sensor.upstairs_temperature", None)
    history.pop("binary_sensor.office_window", None)
    hass = _fake_hass(websocket_api_module, history_by_entity=history)
    entry_a = FakeConfigEntry(
        "valid-retry-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "valid-retry-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "valid-retry-entry-a",
        "Show sensor.upstairs_temperature",
        40,
    )
    start_b = _dispatch_start(
        hass,
        websocket_api_module,
        "valid-retry-entry-b",
        "Show binary_sensor.office_window",
        41,
    )
    snapshot_a = _first_result_payload(start_a)
    snapshot_b = _first_result_payload(start_b)
    hass.data[DOMAIN][DATA_HISTORY_SOURCE]["sensor.upstairs_temperature"] = fake_history_data()[
        "sensor.upstairs_temperature"
    ]
    hass.data[DOMAIN][DATA_HISTORY_SOURCE]["binary_sensor.office_window"] = fake_history_data()[
        "binary_sensor.office_window"
    ]
    retry_a = _dispatch_retry(
        hass,
        websocket_api_module,
        "valid-retry-entry-a",
        snapshot_a["job_id"],
        42,
    )
    retry_b = _dispatch_retry(
        hass,
        websocket_api_module,
        "valid-retry-entry-b",
        snapshot_b["job_id"],
        43,
    )
    return {
        "entry_a": {
            "start": start_a,
            "retry": retry_a,
            "snapshot": _first_result_payload(retry_a),
            "history_store": _history_store_summary(hass, "valid-retry-entry-a"),
            "orchestration_store": _orchestration_store_summary(hass, "valid-retry-entry-a"),
            "run": _latest_run(hass, "valid-retry-entry-a"),
            "snapshot_validation": _validate_snapshots(
                _job(hass, "valid-retry-entry-a", snapshot_a["job_id"])["snapshots"],
                root,
            ),
        },
        "entry_b": {
            "start": start_b,
            "retry": retry_b,
            "snapshot": _first_result_payload(retry_b),
            "history_store": _history_store_summary(hass, "valid-retry-entry-b"),
            "orchestration_store": _orchestration_store_summary(hass, "valid-retry-entry-b"),
            "run": _latest_run(hass, "valid-retry-entry-b"),
            "snapshot_validation": _validate_snapshots(
                _job(hass, "valid-retry-entry-b", snapshot_b["job_id"])["snapshots"],
                root,
            ),
        },
    }


def verify_retry_snapshots_validate(root=None) -> dict[str, Any]:
    root = root or repo_root()
    success = verify_accepted_retry_resumes_same_failed_job(root)
    isolation = verify_valid_retries_stay_config_entry_scoped(root)
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


def verify_retry_continuation_side_effect_boundaries() -> dict[str, Any]:
    success = verify_accepted_retry_resumes_same_failed_job()
    unknown = verify_unknown_retry_job_rejected_before_history()
    non_retryable = verify_non_retryable_job_rejected_before_history()
    cross_entry = verify_cross_config_entry_retry_rejected()
    isolation = verify_valid_retries_stay_config_entry_scoped()
    setup = _setup_retry_hass(
        FakeConfigEntry(
            "side-effects-retry-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        )
    )[0].data[DOMAIN]["side-effects-retry-entry"]

    observed = [
        {"name": "accepted_retry", **success["retry"]["orchestration"]},
        {"name": "unknown_retry_job", **unknown["retry"]["orchestration"]},
        {"name": "non_retryable_job", **non_retryable["retry"]["orchestration"]},
        {"name": "cross_config_entry", **cross_entry["cross_retry"]["orchestration"]},
        {"name": "entry_a_retry", **isolation["entry_a"]["retry"]["orchestration"]},
        {"name": "entry_b_retry", **isolation["entry_b"]["retry"]["orchestration"]},
        {"name": "setup_orchestration", **setup[DATA_JOB_ORCHESTRATION_SETUP]["orchestration"]},
        {"name": "websocket_registration", **setup["websocket_api"]["orchestration"]},
    ]

    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in RETRY_FORBIDDEN_SIDE_EFFECT_KEYS
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
        "retry_behavior_called": any(item.get("retry_behavior_called") for item in observed),
        "websocket_command_registered": any(item.get("websocket_command_registered") for item in observed),
    }
    return {
        "expected_forbidden": {key: NO_JOB_ORCHESTRATION_CALLS[key] for key in RETRY_FORBIDDEN_SIDE_EFFECT_KEYS},
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }


def verify_job_orchestration_retry_continuation_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_retry_continuation_files(root)
    accepted = verify_accepted_retry_resumes_same_failed_job(root)
    unknown_job = verify_unknown_retry_job_rejected_before_history(root)
    non_retryable = verify_non_retryable_job_rejected_before_history(root)
    cross_entry = verify_cross_config_entry_retry_rejected(root)
    isolation = verify_valid_retries_stay_config_entry_scoped(root)
    snapshot_validation = verify_retry_snapshots_validate(root)
    side_effects = verify_retry_continuation_side_effect_boundaries()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more retry continuation files are missing.")
    if not accepted["retry"]["accepted"]:
        failures.append("Accepted retry did not return a WebSocket result.")
    if accepted["retry_snapshot"]["snapshot_id"] != "retry-entry-job-001-snapshot-006":
        failures.append("Accepted retry did not append deterministic continuation snapshots.")
    if not accepted["same_job_id"]:
        failures.append("Accepted retry did not resume the same job.")
    if accepted["history_store"]["entity_ids"] != ["sensor.downstairs_temperature"]:
        failures.append("Accepted retry did not retrieve only the retried approved entity.")
    if accepted["run"]["prompt"] != "Show sensor.downstairs_temperature":
        failures.append("Accepted retry did not reuse the original job prompt.")
    if "job_orchestration_retry_accepted" not in accepted["job_progress_stages"]:
        failures.append("Accepted retry did not append a retry-accepted snapshot.")
    if unknown_job["error_codes"] != ["unknown_job"]:
        failures.append("Unknown retry job did not fail closed with unknown_job.")
    if unknown_job["history_after"]["request_count"] != unknown_job["history_before"]["request_count"]:
        failures.append("Unknown retry job read history.")
    if non_retryable["error_codes"] != ["job_not_retryable"]:
        failures.append("Non-retryable job did not fail closed with job_not_retryable.")
    if non_retryable["snapshot_count_after"] != non_retryable["snapshot_count_before"]:
        failures.append("Non-retryable job appended a retry continuation snapshot.")
    if non_retryable["history_after"]["request_count"] != non_retryable["history_before"]["request_count"]:
        failures.append("Non-retryable job read history.")
    if cross_entry["error_codes"] != ["unknown_job"]:
        failures.append("Cross-config-entry retry did not fail as unknown_job.")
    if cross_entry["entry_b_history_after"]["request_count"] != cross_entry["entry_b_history_before"]["request_count"]:
        failures.append("Cross-config-entry retry read history.")
    if isolation["entry_a"]["history_store"]["entity_ids"] != ["sensor.upstairs_temperature"]:
        failures.append("Entry A retry history isolation failed.")
    if isolation["entry_b"]["history_store"]["entity_ids"] != ["binary_sensor.office_window"]:
        failures.append("Entry B retry history isolation failed.")
    if not snapshot_validation["success"]["all_snapshots_valid"]:
        failures.append("Accepted retry snapshots did not all validate.")
    if not snapshot_validation["isolation_entry_a"]["all_snapshots_valid"]:
        failures.append("Entry A retry snapshots did not all validate.")
    if not snapshot_validation["isolation_entry_b"]["all_snapshots_valid"]:
        failures.append("Entry B retry snapshots did not all validate.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("Retry continuation reported forbidden side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("Retry continuation did not report expected allowed side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "accepted": accepted,
        "unknown_job": unknown_job,
        "non_retryable": non_retryable,
        "cross_entry": cross_entry,
        "isolation": isolation,
        "snapshot_validation": snapshot_validation,
        "side_effects": side_effects,
    }


def _setup_retry_hass(
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


def _dispatch_retry(
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
            "type": INTEGRATION_COMMAND_TYPES["retry_job"],
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
        "retry_allowed": snapshot.get("retry_allowed"),
    }
