from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

from custom_components.isolinear import async_setup_entry
from custom_components.isolinear.const import DOMAIN, INTEGRATION_COMMAND_TYPES, INTEGRATION_WS_VERSION
from custom_components.isolinear.entity_catalog import DATA_ENTITY_CATALOG, DATA_ENTITY_CATALOG_SETUP
from custom_components.isolinear.history_retrieval import DATA_HISTORY_RETRIEVAL, DATA_HISTORY_SOURCE
from custom_components.isolinear.job_orchestration import (
    DATA_JOB_ORCHESTRATION,
    DATA_JOB_ORCHESTRATION_SETUP,
    DATA_JOB_ORCHESTRATION_TIME_RANGE,
    NO_JOB_ORCHESTRATION_CALLS,
    summarize_job_orchestration_store,
)
from custom_components.isolinear.job_state import DATA_JOB_STATE, summarize_job_state_store
from custom_components.isolinear.websocket_api import DATA_WEBSOCKET_API_MODULE

from .contracts import ContractValidationError, validate_contract
from .dashboard_card_anchor import repo_root
from .entity_catalog_scaffold_anchor import (
    FakeConfigEntry,
    FakeHass,
    fake_entity_metadata,
    fake_states,
)
from .history_retrieval_scaffold_anchor import fake_history_data, history_time_range
from .websocket_command_registration_anchor import FakeWebSocketApiModule


JOB_ORCHESTRATION_SCAFFOLD_FILES = [
    "custom_components/isolinear/job_orchestration.py",
    "custom_components/isolinear/job_state.py",
    "custom_components/isolinear/websocket_api.py",
    "custom_components/isolinear/__init__.py",
    "docs/specs/home-assistant-job-orchestration-scaffold-spec.md",
    "bdd/integration/home-assistant-job-orchestration-scaffold-bdd.md",
    "bdd/integration/home-assistant-job-orchestration-scaffold-evidence.md",
    "docs/evals/home_assistant_job_orchestration_scaffold.yaml",
    "tests/test_job_orchestration_scaffold_anchor.py",
    "evals/home_assistant_job_orchestration_scaffold.py",
]


def verify_job_orchestration_scaffold_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in JOB_ORCHESTRATION_SCAFFOLD_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_start_job_orchestration_success(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_orchestration_hass(
        FakeConfigEntry(
            "orchestration-entry",
            options={
                "entity_allowlist": [
                    "sensor.upstairs_temperature",
                    "binary_sensor.office_window",
                ]
            },
        )
    )
    dispatch = websocket_api_module.dispatch(
        hass,
        {
            "id": 1,
            **_start_command(
                "orchestration-entry",
                "Compare sensor.upstairs_temperature and binary_sensor.office_window",
            ),
        },
    )
    snapshot = _first_result_payload(dispatch)
    job = _only_job(hass, "orchestration-entry")
    snapshots = list(job["snapshots"])
    return {
        "dispatch": dispatch,
        "snapshot": snapshot,
        "job_store": summarize_job_state_store(_job_store(hass, "orchestration-entry")),
        "job_snapshot_statuses": [item["status"] for item in snapshots],
        "snapshot_validation": _validate_snapshots(snapshots, root),
        "history_store": _history_store_summary(hass, "orchestration-entry"),
        "orchestration_store": _orchestration_store_summary(hass, "orchestration-entry"),
        "run": _latest_run(hass, "orchestration-entry"),
    }


def verify_non_catalog_prompt_entity_failure(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_orchestration_hass(
        FakeConfigEntry(
            "non-catalog-orchestration-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        )
    )
    dispatch = websocket_api_module.dispatch(
        hass,
        {
            "id": 2,
            **_start_command(
                "non-catalog-orchestration-entry",
                "Show light.kitchen compared with the approved climate sensor",
            ),
        },
    )
    snapshot = _first_result_payload(dispatch)
    return {
        "dispatch": dispatch,
        "snapshot": snapshot,
        "snapshot_validation": _validate_snapshot(snapshot, root),
        "history_store": _history_store_summary(hass, "non-catalog-orchestration-entry"),
        "orchestration_store": _orchestration_store_summary(hass, "non-catalog-orchestration-entry"),
        "orchestration": dispatch["orchestration"],
        "run": _latest_run(hass, "non-catalog-orchestration-entry"),
    }


def verify_missing_approved_history_failure(root=None) -> dict[str, Any]:
    root = root or repo_root()
    history = deepcopy(fake_history_data())
    history.pop("sensor.downstairs_temperature", None)
    hass, websocket_api_module = _setup_orchestration_hass(
        FakeConfigEntry(
            "missing-history-orchestration-entry",
            options={"entity_allowlist": ["sensor.downstairs_temperature"]},
        ),
        history_by_entity=history,
    )
    dispatch = websocket_api_module.dispatch(
        hass,
        {
            "id": 3,
            **_start_command(
                "missing-history-orchestration-entry",
                "Show sensor.downstairs_temperature",
            ),
        },
    )
    snapshot = _first_result_payload(dispatch)
    return {
        "dispatch": dispatch,
        "snapshot": snapshot,
        "snapshot_validation": _validate_snapshot(snapshot, root),
        "history_store": _history_store_summary(hass, "missing-history-orchestration-entry"),
        "orchestration_store": _orchestration_store_summary(hass, "missing-history-orchestration-entry"),
        "orchestration": dispatch["orchestration"],
        "run": _latest_run(hass, "missing-history-orchestration-entry"),
    }


def verify_unresolved_allowlist_catalog_failure(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_orchestration_hass(
        FakeConfigEntry(
            "unresolved-allowlist-orchestration-entry",
            options={"entity_allowlist": ["sensor.bathrrom_sensor_temperature"]},
        )
    )
    dispatch = websocket_api_module.dispatch(
        hass,
        {
            "id": 9,
            **_start_command(
                "unresolved-allowlist-orchestration-entry",
                "Show the bathroom temperature",
            ),
        },
    )
    snapshot = _first_result_payload(dispatch)
    start_run = _latest_run(hass, "unresolved-allowlist-orchestration-entry")
    retry_dispatch = websocket_api_module.dispatch(
        hass,
        {
            "id": 10,
            **_retry_command(
                "unresolved-allowlist-orchestration-entry",
                snapshot["job_id"],
            ),
        },
    )
    retry_snapshot = _first_result_payload(retry_dispatch)
    entry_data = hass.data[DOMAIN]["unresolved-allowlist-orchestration-entry"]
    return {
        "dispatch": dispatch,
        "snapshot": snapshot,
        "snapshot_validation": _validate_snapshot(snapshot, root),
        "catalog_setup": entry_data[DATA_ENTITY_CATALOG_SETUP],
        "history_store": _history_store_summary(hass, "unresolved-allowlist-orchestration-entry"),
        "orchestration_store": _orchestration_store_summary(
            hass,
            "unresolved-allowlist-orchestration-entry",
        ),
        "orchestration": dispatch["orchestration"],
        "run": start_run,
        "retry": {
            "dispatch": retry_dispatch,
            "snapshot": retry_snapshot,
            "snapshot_validation": _validate_snapshot(retry_snapshot, root),
            "run": _latest_run(hass, "unresolved-allowlist-orchestration-entry"),
        },
    }


def verify_config_entry_orchestration_isolation(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "orch-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "orch-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))

    entry_a_result = _dispatch_start(
        hass,
        websocket_api_module,
        "orch-entry-a",
        "Show sensor.upstairs_temperature",
        message_id=4,
        root=root,
    )
    entry_b_result = _dispatch_start(
        hass,
        websocket_api_module,
        "orch-entry-b",
        "Show binary_sensor.office_window",
        message_id=5,
        root=root,
    )
    return {
        "entry_a": entry_a_result,
        "entry_b": entry_b_result,
    }


def verify_ambiguous_prompt_requires_clarification(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_orchestration_hass(
        FakeConfigEntry(
            "ambiguous-orchestration-entry",
            options={
                "entity_allowlist": [
                    "sensor.upstairs_temperature",
                    "sensor.downstairs_temperature",
                ]
            },
        )
    )
    dispatch = websocket_api_module.dispatch(
        hass,
        {
            "id": 6,
            **_start_command(
                "ambiguous-orchestration-entry",
                "Show thermostat history",
            ),
        },
    )
    snapshot = _first_result_payload(dispatch)
    return {
        "dispatch": dispatch,
        "snapshot": snapshot,
        "snapshot_validation": _validate_snapshot(snapshot, root),
        "history_store": _history_store_summary(hass, "ambiguous-orchestration-entry"),
        "orchestration_store": _orchestration_store_summary(hass, "ambiguous-orchestration-entry"),
        "orchestration": dispatch["orchestration"],
        "run": _latest_run(hass, "ambiguous-orchestration-entry"),
    }


def verify_setup_entry_orchestration_storage() -> dict[str, Any]:
    hass, _websocket_api_module = _setup_orchestration_hass(
        FakeConfigEntry(
            "setup-orchestration-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        )
    )
    entry_data = hass.data[DOMAIN]["setup-orchestration-entry"]
    store = entry_data[DATA_JOB_ORCHESTRATION]
    return {
        "setup_accepted": True,
        "entry_id": "setup-orchestration-entry",
        "entry_data_keys": sorted(entry_data),
        "setup_result": entry_data[DATA_JOB_ORCHESTRATION_SETUP],
        "catalog_entity_ids": list(entry_data[DATA_ENTITY_CATALOG]["entity_ids"]),
        "store": summarize_job_orchestration_store(store),
    }


def verify_orchestration_snapshots_validate(root=None) -> dict[str, Any]:
    root = root or repo_root()
    success = verify_start_job_orchestration_success(root)
    non_catalog = verify_non_catalog_prompt_entity_failure(root)
    missing_history = verify_missing_approved_history_failure(root)
    unresolved_allowlist = verify_unresolved_allowlist_catalog_failure(root)
    ambiguous = verify_ambiguous_prompt_requires_clarification(root)
    return {
        "success": {
            "all_snapshots_valid": all(item["accepted"] for item in success["snapshot_validation"]),
            "snapshot_validation": success["snapshot_validation"],
        },
        "non_catalog": non_catalog,
        "missing_history": missing_history,
        "unresolved_allowlist": unresolved_allowlist,
        "ambiguous": ambiguous,
    }


def verify_job_orchestration_side_effect_boundaries() -> dict[str, Any]:
    success = verify_start_job_orchestration_success()
    non_catalog = verify_non_catalog_prompt_entity_failure()
    missing_history = verify_missing_approved_history_failure()
    unresolved_allowlist = verify_unresolved_allowlist_catalog_failure()
    ambiguous = verify_ambiguous_prompt_requires_clarification()
    isolation = verify_config_entry_orchestration_isolation()
    setup = verify_setup_entry_orchestration_storage()

    observed = [
        {"name": "successful_start", **success["dispatch"]["orchestration"]},
        {"name": "non_catalog_failure", **non_catalog["dispatch"]["orchestration"]},
        {"name": "missing_history_failure", **missing_history["dispatch"]["orchestration"]},
        {"name": "unresolved_allowlist_failure", **unresolved_allowlist["dispatch"]["orchestration"]},
        {"name": "ambiguous_prompt_clarification", **ambiguous["dispatch"]["orchestration"]},
        {"name": "entry_a_start", **isolation["entry_a"]["dispatch"]["orchestration"]},
        {"name": "entry_b_start", **isolation["entry_b"]["dispatch"]["orchestration"]},
        {"name": "setup_orchestration", **setup["setup_result"]["orchestration"]},
    ]
    observed.append(
        {
            "name": "websocket_registration",
            **_setup_orchestration_hass(
                FakeConfigEntry(
                    "side-effects-orchestration-entry",
                    options={"entity_allowlist": ["sensor.upstairs_temperature"]},
                )
            )[0].data[DOMAIN]["side-effects-orchestration-entry"]["websocket_api"]["orchestration"],
        }
    )

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


def verify_job_orchestration_scaffold_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_job_orchestration_scaffold_files(root)
    success = verify_start_job_orchestration_success(root)
    non_catalog = verify_non_catalog_prompt_entity_failure(root)
    missing_history = verify_missing_approved_history_failure(root)
    unresolved_allowlist = verify_unresolved_allowlist_catalog_failure(root)
    ambiguous = verify_ambiguous_prompt_requires_clarification(root)
    isolation = verify_config_entry_orchestration_isolation(root)
    setup = verify_setup_entry_orchestration_storage()
    side_effects = verify_job_orchestration_side_effect_boundaries()
    snapshot_validation = verify_orchestration_snapshots_validate(root)

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more job orchestration scaffold files are missing.")
    if not success["dispatch"]["accepted"] or success["snapshot"]["status"] != "planning":
        failures.append("Successful start did not return a planning snapshot.")
    if success["snapshot"]["snapshot_id"] != "orchestration-entry-job-001-snapshot-003":
        failures.append("Successful start did not produce deterministic scaffold transitions.")
    if success["history_store"]["entity_ids"] != [
        "sensor.upstairs_temperature",
        "binary_sensor.office_window",
    ]:
        failures.append("Successful start did not retrieve exactly the selected approved history.")
    if not all(item["accepted"] for item in success["snapshot_validation"]):
        failures.append("One or more successful orchestration snapshots failed schema validation.")
    if non_catalog["snapshot"]["failure"]["code"] != "entity_not_in_approved_catalog":
        failures.append("Non-catalog prompt entity did not fail with the catalog gate code.")
    if non_catalog["dispatch"]["orchestration"]["home_assistant_history_read"]:
        failures.append("Non-catalog prompt entity read history before rejection.")
    if missing_history["snapshot"]["failure"]["code"] != "missing_approved_history":
        failures.append("Missing approved history did not return the structured missing-history code.")
    if missing_history["run"]["missing_entity_ids"] != ["sensor.downstairs_temperature"]:
        failures.append("Missing approved history did not report the missing entity ID.")
    if unresolved_allowlist["snapshot"]["failure"]["code"] != "unknown_allowlisted_entity":
        failures.append("Unresolved allowlist entity did not surface the catalog setup failure code.")
    if unresolved_allowlist["run"]["missing_entity_ids"] != ["sensor.bathrrom_sensor_temperature"]:
        failures.append("Unresolved allowlist entity did not report the missing allowlist entity ID.")
    if unresolved_allowlist["retry"]["snapshot"]["failure"]["code"] != "unknown_allowlisted_entity":
        failures.append("Unresolved allowlist retry did not preserve the catalog setup failure code.")
    if unresolved_allowlist["retry"]["run"]["missing_entity_ids"] != ["sensor.bathrrom_sensor_temperature"]:
        failures.append("Unresolved allowlist retry did not report the missing allowlist entity ID.")
    if unresolved_allowlist["dispatch"]["orchestration"]["home_assistant_history_read"]:
        failures.append("Unresolved allowlist entity read history before catalog rejection.")
    if ambiguous["snapshot"]["status"] != "clarification_needed":
        failures.append("Ambiguous prompt did not return a clarification-needed snapshot.")
    if ambiguous["dispatch"]["orchestration"]["home_assistant_history_read"]:
        failures.append("Ambiguous prompt read history before clarification.")
    if isolation["entry_a"]["history_store"]["entity_ids"] != ["sensor.upstairs_temperature"]:
        failures.append("Entry A orchestration history isolation failed.")
    if isolation["entry_b"]["history_store"]["entity_ids"] != ["binary_sensor.office_window"]:
        failures.append("Entry B orchestration history isolation failed.")
    if not setup["setup_result"]["enabled"]:
        failures.append("async_setup_entry did not enable orchestration for an approved catalog.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("Job orchestration scaffold reported forbidden side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("Job orchestration scaffold did not report expected allowed side effects.")
    if not snapshot_validation["success"]["all_snapshots_valid"]:
        failures.append("Observed successful snapshots did not all validate.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "success": success,
        "non_catalog": non_catalog,
        "missing_history": missing_history,
        "unresolved_allowlist": unresolved_allowlist,
        "ambiguous": ambiguous,
        "isolation": isolation,
        "setup": setup,
        "side_effects": side_effects,
        "snapshot_validation": snapshot_validation,
    }


def _setup_orchestration_hass(
    entry: FakeConfigEntry,
    *,
    history_by_entity: dict[str, Any] | None = None,
) -> tuple[FakeHass, FakeWebSocketApiModule]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module, history_by_entity=history_by_entity)
    setup_accepted = _run(async_setup_entry(hass, entry))
    if not setup_accepted:
        raise AssertionError(f"async_setup_entry rejected {entry.entry_id}")
    return hass, websocket_api_module


def _fake_hass(
    websocket_api_module: FakeWebSocketApiModule,
    *,
    history_by_entity: dict[str, Any] | None = None,
) -> FakeHass:
    hass = FakeHass(metadata_by_entity=fake_entity_metadata(), states=fake_states())
    hass.data[DOMAIN][DATA_WEBSOCKET_API_MODULE] = websocket_api_module
    hass.data[DOMAIN][DATA_HISTORY_SOURCE] = deepcopy(history_by_entity or fake_history_data())
    hass.data[DOMAIN][DATA_JOB_ORCHESTRATION_TIME_RANGE] = history_time_range()
    return hass


def _dispatch_start(
    hass: FakeHass,
    websocket_api_module: FakeWebSocketApiModule,
    entry_id: str,
    prompt: str,
    *,
    message_id: int,
    root,
) -> dict[str, Any]:
    dispatch = websocket_api_module.dispatch(
        hass,
        {"id": message_id, **_start_command(entry_id, prompt)},
    )
    snapshot = _first_result_payload(dispatch)
    return {
        "dispatch": dispatch,
        "snapshot": snapshot,
        "snapshot_validation": _validate_snapshot(snapshot, root),
        "job_store": summarize_job_state_store(_job_store(hass, entry_id)),
        "history_store": _history_store_summary(hass, entry_id),
        "orchestration_store": _orchestration_store_summary(hass, entry_id),
        "run": _latest_run(hass, entry_id),
    }


def _start_command(entry_id: str, prompt: str) -> dict[str, Any]:
    return {
        "type": INTEGRATION_COMMAND_TYPES["start_job"],
        "version": INTEGRATION_WS_VERSION,
        "config_entry_id": entry_id,
        "prompt": prompt,
    }


def _retry_command(entry_id: str, job_id: str) -> dict[str, Any]:
    return {
        "type": INTEGRATION_COMMAND_TYPES["retry_job"],
        "version": INTEGRATION_WS_VERSION,
        "config_entry_id": entry_id,
        "job_id": job_id,
    }


def _first_result_payload(dispatch_result: dict[str, Any]) -> Any:
    results = dispatch_result["connection"]["results"]
    if not results:
        return None
    return results[0]["result"]


def _job_store(hass: FakeHass, entry_id: str) -> dict[str, Any]:
    return hass.data[DOMAIN][entry_id][DATA_JOB_STATE]


def _history_store_summary(hass: FakeHass, entry_id: str) -> dict[str, Any]:
    store = hass.data[DOMAIN][entry_id][DATA_HISTORY_RETRIEVAL]
    return {
        "entry_id": store["entry_id"],
        "series_count": len(store["series"]),
        "entity_ids": list(store["entity_ids"]),
        "request_count": store["request_count"],
        "last_time_range": deepcopy(store["last_time_range"]),
    }


def _orchestration_store_summary(hass: FakeHass, entry_id: str) -> dict[str, Any]:
    return summarize_job_orchestration_store(hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION])


def _latest_run(hass: FakeHass, entry_id: str) -> dict[str, Any]:
    return deepcopy(hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION]["latest_run"])


def _only_job(hass: FakeHass, entry_id: str) -> dict[str, Any]:
    store = _job_store(hass, entry_id)
    job_id = store["job_order"][0]
    return store["jobs"][job_id]


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
        "failure_code": snapshot.get("failure", {}).get("code"),
    }


def _run(coro):
    return asyncio.run(coro)
