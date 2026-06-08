from __future__ import annotations

from copy import deepcopy
from typing import Any

from custom_components.isolinear import async_setup_entry
from custom_components.isolinear.const import DOMAIN, INTEGRATION_COMMAND_TYPES, INTEGRATION_WS_VERSION
from custom_components.isolinear.job_orchestration import (
    DATA_JOB_ORCHESTRATION,
    DATA_JOB_ORCHESTRATION_SETUP,
    NO_JOB_ORCHESTRATION_CALLS,
    summarize_job_orchestration_store,
)
from custom_components.isolinear.job_state import DATA_JOB_STATE, summarize_job_state_store

from .contracts import ContractValidationError, validate_contract
from .dashboard_card_anchor import repo_root
from .entity_catalog_scaffold_anchor import FakeConfigEntry
from .job_orchestration_scaffold_anchor import _fake_hass, _first_result_payload, _run
from .websocket_command_registration_anchor import FakeWebSocketApiModule


ARTIFACT_STORAGE_FILES = [
    "custom_components/isolinear/job_orchestration.py",
    "custom_components/isolinear/websocket_api.py",
    "docs/specs/home-assistant-job-orchestration-artifact-storage-scaffold-spec.md",
    "bdd/integration/home-assistant-job-orchestration-artifact-storage-scaffold-bdd.md",
    "bdd/integration/home-assistant-job-orchestration-artifact-storage-scaffold-evidence.md",
    "docs/evals/home_assistant_job_orchestration_artifact_storage_scaffold.yaml",
    "docs/schemas/integration-artifact-metadata.schema.json",
    "tests/test_job_orchestration_artifact_storage_anchor.py",
    "evals/home_assistant_job_orchestration_artifact_storage_scaffold.py",
    "src/Isolinear/job_orchestration_artifact_storage_anchor.py",
]

ARTIFACT_STORAGE_FORBIDDEN_SIDE_EFFECT_KEYS = [
    *NO_JOB_ORCHESTRATION_CALLS,
    "home_assistant_history_read",
    "history_retrieval_scaffold_written",
    "subscription_bookkeeping_written",
]


def verify_artifact_storage_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in ARTIFACT_STORAGE_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_scaffold_ready_snapshot_records_placeholder_artifact(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_artifact_hass(
        FakeConfigEntry(
            "artifact-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        )
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "artifact-entry",
        "Show sensor.upstairs_temperature",
        1,
    )
    start_snapshot = _first_result_payload(start)
    snapshot_dispatch = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "artifact-entry",
        start_snapshot["job_id"],
        2,
    )
    artifact_snapshot = _first_result_payload(snapshot_dispatch)
    artifacts = _artifacts(hass, "artifact-entry")
    job = _job(hass, "artifact-entry", start_snapshot["job_id"])
    stored_complete_snapshots = [
        snapshot for snapshot in job["snapshots"] if snapshot.get("status") == "complete"
    ]
    return {
        "start": start,
        "snapshot_dispatch": snapshot_dispatch,
        "start_snapshot": start_snapshot,
        "artifact_snapshot": artifact_snapshot,
        "artifact": artifacts[0] if artifacts else None,
        "artifacts": artifacts,
        "stored_complete_snapshots": stored_complete_snapshots,
        "job_store": summarize_job_state_store(_job_store(hass, "artifact-entry")),
        "orchestration_store": _orchestration_store_summary(hass, "artifact-entry"),
        "snapshot_validation": _validate_snapshot(artifact_snapshot, root),
        "stored_snapshot_validation": _validate_snapshots(stored_complete_snapshots, root),
        "artifact_validation": _validate_artifacts(artifacts, root),
    }


def verify_repeated_snapshot_requests_reuse_artifact(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_artifact_hass(
        FakeConfigEntry(
            "artifact-idempotent-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        )
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "artifact-idempotent-entry",
        "Show sensor.upstairs_temperature",
        10,
    )
    job_id = _first_result_payload(start)["job_id"]
    first = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "artifact-idempotent-entry",
        job_id,
        11,
    )
    second = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "artifact-idempotent-entry",
        job_id,
        12,
    )
    first_snapshot = _first_result_payload(first)
    second_snapshot = _first_result_payload(second)
    artifacts = _artifacts(hass, "artifact-idempotent-entry")
    job = _job(hass, "artifact-idempotent-entry", job_id)
    return {
        "first": first,
        "second": second,
        "first_snapshot": first_snapshot,
        "second_snapshot": second_snapshot,
        "same_snapshot_returned": first_snapshot == second_snapshot,
        "artifacts": artifacts,
        "artifact_count": len(artifacts),
        "job_snapshot_ids": [snapshot["snapshot_id"] for snapshot in job["snapshots"]],
        "complete_snapshot_count": len(
            [snapshot for snapshot in job["snapshots"] if snapshot.get("status") == "complete"]
        ),
        "artifact_validation": _validate_artifacts(artifacts, root),
        "snapshot_validation": _validate_snapshot(second_snapshot, root),
    }


def verify_unknown_artifact_job_rejected_before_storage(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, websocket_api_module = _setup_artifact_hass(
        FakeConfigEntry(
            "unknown-artifact-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        )
    )
    snapshot = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "unknown-artifact-entry",
        "unknown-artifact-entry-job-404",
        20,
    )
    return {
        "snapshot": snapshot,
        "error_codes": _error_codes(snapshot),
        "job_store": summarize_job_state_store(_job_store(hass, "unknown-artifact-entry")),
        "artifacts": _artifacts(hass, "unknown-artifact-entry"),
        "snapshot_validation": _validate_snapshots([], root),
        "artifact_validation": _validate_artifacts([], root),
    }


def verify_cross_config_entry_artifact_rejected(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "artifact-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "artifact-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "artifact-entry-a",
        "Show sensor.upstairs_temperature",
        30,
    )
    start_b = _dispatch_start(
        hass,
        websocket_api_module,
        "artifact-entry-b",
        "Show binary_sensor.office_window",
        31,
    )
    snapshot_a = _first_result_payload(start_a)
    snapshot_b = _first_result_payload(start_b)
    cross_snapshot = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "artifact-entry-b",
        snapshot_a["job_id"],
        32,
    )
    return {
        "entry_a_start": start_a,
        "entry_b_start": start_b,
        "entry_a_start_snapshot": snapshot_a,
        "entry_b_start_snapshot": snapshot_b,
        "entry_a_snapshot_validation": _validate_snapshot(snapshot_a, root),
        "entry_b_snapshot_validation": _validate_snapshot(snapshot_b, root),
        "cross_snapshot": cross_snapshot,
        "error_codes": _error_codes(cross_snapshot),
        "entry_a_artifacts": _artifacts(hass, "artifact-entry-a"),
        "entry_b_artifacts": _artifacts(hass, "artifact-entry-b"),
        "entry_b_complete_snapshots": _complete_snapshots(hass, "artifact-entry-b", snapshot_b["job_id"]),
    }


def verify_valid_artifacts_stay_config_entry_scoped(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "valid-artifact-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "valid-artifact-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "valid-artifact-entry-a",
        "Show sensor.upstairs_temperature",
        40,
    )
    start_b = _dispatch_start(
        hass,
        websocket_api_module,
        "valid-artifact-entry-b",
        "Show binary_sensor.office_window",
        41,
    )
    snapshot_a = _first_result_payload(start_a)
    snapshot_b = _first_result_payload(start_b)
    artifact_a = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "valid-artifact-entry-a",
        snapshot_a["job_id"],
        42,
    )
    artifact_b = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "valid-artifact-entry-b",
        snapshot_b["job_id"],
        43,
    )
    artifacts_a = _artifacts(hass, "valid-artifact-entry-a")
    artifacts_b = _artifacts(hass, "valid-artifact-entry-b")
    return {
        "entry_a": {
            "start": start_a,
            "snapshot": artifact_a,
            "artifact_snapshot": _first_result_payload(artifact_a),
            "artifacts": artifacts_a,
            "orchestration_store": _orchestration_store_summary(hass, "valid-artifact-entry-a"),
            "snapshot_validation": _validate_snapshot(_first_result_payload(artifact_a), root),
            "artifact_validation": _validate_artifacts(artifacts_a, root),
        },
        "entry_b": {
            "start": start_b,
            "snapshot": artifact_b,
            "artifact_snapshot": _first_result_payload(artifact_b),
            "artifacts": artifacts_b,
            "orchestration_store": _orchestration_store_summary(hass, "valid-artifact-entry-b"),
            "snapshot_validation": _validate_snapshot(_first_result_payload(artifact_b), root),
            "artifact_validation": _validate_artifacts(artifacts_b, root),
        },
    }


def verify_artifact_metadata_and_snapshots_validate(root=None) -> dict[str, Any]:
    root = root or repo_root()
    accepted = verify_scaffold_ready_snapshot_records_placeholder_artifact(root)
    idempotent = verify_repeated_snapshot_requests_reuse_artifact(root)
    isolation = verify_valid_artifacts_stay_config_entry_scoped(root)
    return {
        "accepted": {
            "returned_snapshot_valid": accepted["snapshot_validation"]["accepted"],
            "stored_snapshots_valid": all(item["accepted"] for item in accepted["stored_snapshot_validation"]),
            "artifact_metadata_valid": all(item["accepted"] for item in accepted["artifact_validation"]),
            "snapshot_validation": accepted["snapshot_validation"],
            "stored_snapshot_validation": accepted["stored_snapshot_validation"],
            "artifact_validation": accepted["artifact_validation"],
        },
        "idempotent": {
            "returned_snapshot_valid": idempotent["snapshot_validation"]["accepted"],
            "artifact_metadata_valid": all(item["accepted"] for item in idempotent["artifact_validation"]),
            "snapshot_validation": idempotent["snapshot_validation"],
            "artifact_validation": idempotent["artifact_validation"],
        },
        "isolation_entry_a": {
            "returned_snapshot_valid": isolation["entry_a"]["snapshot_validation"]["accepted"],
            "artifact_metadata_valid": all(
                item["accepted"] for item in isolation["entry_a"]["artifact_validation"]
            ),
            "snapshot_validation": isolation["entry_a"]["snapshot_validation"],
            "artifact_validation": isolation["entry_a"]["artifact_validation"],
        },
        "isolation_entry_b": {
            "returned_snapshot_valid": isolation["entry_b"]["snapshot_validation"]["accepted"],
            "artifact_metadata_valid": all(
                item["accepted"] for item in isolation["entry_b"]["artifact_validation"]
            ),
            "snapshot_validation": isolation["entry_b"]["snapshot_validation"],
            "artifact_validation": isolation["entry_b"]["artifact_validation"],
        },
    }


def verify_artifact_storage_side_effect_boundaries() -> dict[str, Any]:
    accepted = verify_scaffold_ready_snapshot_records_placeholder_artifact()
    idempotent = verify_repeated_snapshot_requests_reuse_artifact()
    unknown = verify_unknown_artifact_job_rejected_before_storage()
    cross_entry = verify_cross_config_entry_artifact_rejected()
    isolation = verify_valid_artifacts_stay_config_entry_scoped()
    setup = _setup_artifact_hass(
        FakeConfigEntry(
            "side-effects-artifact-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        )
    )[0].data[DOMAIN]["side-effects-artifact-entry"]

    observed = [
        {"name": "accepted_artifact_snapshot", **accepted["snapshot_dispatch"]["orchestration"]},
        {"name": "idempotent_first_snapshot", **idempotent["first"]["orchestration"]},
        {"name": "idempotent_second_snapshot", **idempotent["second"]["orchestration"]},
        {"name": "unknown_artifact_job", **unknown["snapshot"]["orchestration"]},
        {"name": "cross_config_entry", **cross_entry["cross_snapshot"]["orchestration"]},
        {"name": "entry_a_artifact", **isolation["entry_a"]["snapshot"]["orchestration"]},
        {"name": "entry_b_artifact", **isolation["entry_b"]["snapshot"]["orchestration"]},
        {"name": "setup_orchestration", **setup[DATA_JOB_ORCHESTRATION_SETUP]["orchestration"]},
        {"name": "websocket_registration", **setup["websocket_api"]["orchestration"]},
    ]

    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in ARTIFACT_STORAGE_FORBIDDEN_SIDE_EFFECT_KEYS
    }
    allowed_aggregate = {
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
        "expected_forbidden": {key: False for key in ARTIFACT_STORAGE_FORBIDDEN_SIDE_EFFECT_KEYS},
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }


def verify_job_orchestration_artifact_storage_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_artifact_storage_files(root)
    accepted = verify_scaffold_ready_snapshot_records_placeholder_artifact(root)
    idempotent = verify_repeated_snapshot_requests_reuse_artifact(root)
    unknown_job = verify_unknown_artifact_job_rejected_before_storage(root)
    cross_entry = verify_cross_config_entry_artifact_rejected(root)
    isolation = verify_valid_artifacts_stay_config_entry_scoped(root)
    validation = verify_artifact_metadata_and_snapshots_validate(root)
    side_effects = verify_artifact_storage_side_effect_boundaries()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more artifact storage scaffold files are missing.")
    if not accepted["snapshot_dispatch"]["accepted"]:
        failures.append("Accepted artifact snapshot request did not return a WebSocket result.")
    if accepted["artifact_snapshot"]["status"] != "complete":
        failures.append("Artifact snapshot request did not return a complete snapshot.")
    if accepted["artifact_snapshot"]["snapshot_id"] != "artifact-entry-job-001-snapshot-004":
        failures.append("Artifact snapshot request did not append the deterministic complete snapshot.")
    if accepted["artifact"] is None:
        failures.append("Artifact snapshot request did not store artifact metadata.")
    elif accepted["artifact"]["artifact_id"] != "artifact-entry-artifact-001":
        failures.append("Artifact metadata did not use the deterministic artifact ID.")
    if accepted["artifact"] and accepted["artifact"]["source_snapshot_id"] != accepted["start_snapshot"]["snapshot_id"]:
        failures.append("Artifact metadata did not reference the scaffold-ready source snapshot.")
    if idempotent["artifact_count"] != 1 or idempotent["complete_snapshot_count"] != 1:
        failures.append("Repeated snapshot requests created duplicate artifact state.")
    if not idempotent["same_snapshot_returned"]:
        failures.append("Repeated snapshot request did not return the existing complete snapshot.")
    if unknown_job["error_codes"] != ["unknown_job"]:
        failures.append("Unknown artifact job did not fail closed with unknown_job.")
    if unknown_job["artifacts"]:
        failures.append("Unknown artifact job recorded artifact metadata.")
    if cross_entry["error_codes"] != ["unknown_job"]:
        failures.append("Cross-config-entry artifact request did not fail closed as unknown_job.")
    if cross_entry["entry_b_artifacts"]:
        failures.append("Cross-config-entry artifact request recorded artifact metadata in entry B.")
    if cross_entry["entry_b_complete_snapshots"]:
        failures.append("Cross-config-entry artifact request appended a complete snapshot in entry B.")
    if len(isolation["entry_a"]["artifacts"]) != 1 or len(isolation["entry_b"]["artifacts"]) != 1:
        failures.append("Valid artifacts did not stay isolated by config entry.")
    if not validation["accepted"]["returned_snapshot_valid"]:
        failures.append("Accepted artifact request returned snapshot did not validate.")
    if not validation["accepted"]["stored_snapshots_valid"]:
        failures.append("Accepted stored complete snapshots did not validate.")
    if not validation["accepted"]["artifact_metadata_valid"]:
        failures.append("Accepted artifact metadata did not validate.")
    if not validation["isolation_entry_a"]["artifact_metadata_valid"]:
        failures.append("Entry A artifact metadata did not validate.")
    if not validation["isolation_entry_b"]["artifact_metadata_valid"]:
        failures.append("Entry B artifact metadata did not validate.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("Artifact storage scaffold reported forbidden side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("Artifact storage scaffold did not report expected allowed side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "accepted": accepted,
        "idempotent": idempotent,
        "unknown_job": unknown_job,
        "cross_entry": cross_entry,
        "isolation": isolation,
        "validation": validation,
        "side_effects": side_effects,
    }


def _setup_artifact_hass(entry: FakeConfigEntry) -> tuple[Any, FakeWebSocketApiModule]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
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


def _dispatch_snapshot(
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
            "type": INTEGRATION_COMMAND_TYPES["get_snapshot"],
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


def _artifacts(hass: Any, entry_id: str) -> list[dict[str, Any]]:
    store = hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION]
    return [
        deepcopy(store.get("artifact_metadata", {})[artifact_id])
        for artifact_id in store.get("artifact_order", [])
        if artifact_id in store.get("artifact_metadata", {})
    ]


def _complete_snapshots(hass: Any, entry_id: str, job_id: str) -> list[dict[str, Any]]:
    return [
        deepcopy(snapshot)
        for snapshot in _job(hass, entry_id, job_id)["snapshots"]
        if snapshot.get("status") == "complete"
    ]


def _orchestration_store_summary(hass: Any, entry_id: str) -> dict[str, Any]:
    return summarize_job_orchestration_store(hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION])


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
        "chart_image_url": snapshot.get("chart", {}).get("image_url"),
    }


def _validate_artifacts(artifacts: list[dict[str, Any]], root) -> list[dict[str, Any]]:
    return [_validate_artifact(artifact, root) for artifact in artifacts]


def _validate_artifact(artifact: dict[str, Any], root) -> dict[str, Any]:
    try:
        validate_contract("integration-artifact-metadata", artifact, repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "contract_validation_failed",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "artifact_id": artifact["artifact_id"],
        "job_id": artifact["job_id"],
        "source_snapshot_id": artifact["source_snapshot_id"],
        "status": artifact["status"],
    }
