"""Config-entry-scoped in-memory job state for the Isolinear integration."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .const import DOMAIN, INTEGRATION_COMMAND_TYPES


DATA_JOB_STATE = "job_state"
SNAPSHOT_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "docs" / "schemas" / "integration-job-snapshot.schema.json"

NO_JOB_STATE_ORCHESTRATION_CALLS = {
    "worker_called": False,
    "model_provider_called": False,
    "home_assistant_history_called": False,
    "semantic_memory_called": False,
    "home_assistant_service_or_state_mutation_called": False,
    "token_generated": False,
    "chart_artifact_written": False,
    "job_orchestration_called": False,
    "dashboard_resource_metadata_written_or_reused": False,
}


class JobStateSnapshotValidationError(ValueError):
    def __init__(self, result: dict[str, Any]) -> None:
        super().__init__(result.get("error", "Integration job snapshot validation failed."))
        self.result = result


def ensure_job_state_store(hass: Any, entry_id: str) -> dict[str, Any]:
    """Return the in-memory job state store for one Isolinear config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    entry_data = domain_data.setdefault(entry_id, {})
    store = entry_data.get(DATA_JOB_STATE)
    if isinstance(store, dict):
        return store

    store = {
        "entry_id": entry_id,
        "next_job_number": 1,
        "jobs": {},
        "job_order": [],
        "subscriptions": {},
        "subscription_order": [],
    }
    entry_data[DATA_JOB_STATE] = store
    return store


def remove_job_state_store(hass: Any, entry_id: str) -> dict[str, Any]:
    """Remove one config entry's in-memory job state store."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    entry_data = domain_data.get(entry_id)
    removed = False
    if isinstance(entry_data, dict) and DATA_JOB_STATE in entry_data:
        entry_data.pop(DATA_JOB_STATE, None)
        removed = True
    return {
        "accepted": True,
        "code": "job_state_removed" if removed else "job_state_not_present",
        "entry_id": entry_id,
        "removed": removed,
        "orchestration": job_state_side_effects(job_state_written=removed),
    }


def handle_job_state_ws_command(
    hass: Any,
    command: dict[str, Any],
    *,
    message_id: int | str | None = None,
) -> dict[str, Any]:
    """Apply a validated, config-entry-scoped command to the job state store."""
    entry_id = command["config_entry_id"]
    store = ensure_job_state_store(hass, entry_id)
    command_type = command["type"]

    try:
        if command_type == INTEGRATION_COMMAND_TYPES["start_job"]:
            return _start_job(store, command)

        job = store["jobs"].get(command["job_id"])
        if not isinstance(job, dict):
            return _job_rejection("unknown_job", command["job_id"])

        if command_type == INTEGRATION_COMMAND_TYPES["get_snapshot"]:
            return _accepted(
                "job_snapshot_returned",
                command,
                job["latest_snapshot"],
                job_state_written=False,
            )

        if command_type == INTEGRATION_COMMAND_TYPES["retry_job"]:
            snapshot = _append_snapshot(
                job,
                state_label="Planning",
                message="Retry accepted by the job state scaffold; orchestration is not implemented yet.",
                progress_stage="retry_queued",
                progress_message="Retry is waiting for a later orchestration packet.",
                validation_summary="The job state scaffold accepted the retry request only.",
                warnings=["job_state_scaffold", "retry_recorded", "orchestration_not_implemented"],
            )
            return _accepted("job_retry_recorded", command, snapshot, job_state_written=True)

        if command_type == INTEGRATION_COMMAND_TYPES["answer_clarification"]:
            warnings = ["job_state_scaffold", "clarification_answer_recorded", "orchestration_not_implemented"]
            if command["remember"]:
                warnings.append("semantic_memory_not_persisted_in_scaffold")
            snapshot = _append_snapshot(
                job,
                state_label="Planning",
                message=(
                    "Clarification answer accepted by the job state scaffold; "
                    "orchestration is not implemented yet."
                ),
                progress_stage="clarification_answered",
                progress_message="Clarification answer is waiting for a later orchestration packet.",
                validation_summary="The job state scaffold accepted the clarification answer only.",
                warnings=warnings,
            )
            job["clarification_answers"].append(
                {
                    "question_id": command["question_id"],
                    "option_id": command["option_id"],
                    "remember": command["remember"],
                }
            )
            return _accepted("clarification_answer_recorded", command, snapshot, job_state_written=True)

        if command_type == INTEGRATION_COMMAND_TYPES["subscribe_job"]:
            subscription = _record_subscription(store, job, message_id)
            return _accepted(
                "job_subscription_recorded",
                command,
                job["latest_snapshot"],
                subscription=subscription,
                subscription_bookkeeping_written=True,
            )
    except JobStateSnapshotValidationError as exc:
        return _snapshot_validation_rejection(exc.result)

    return _job_rejection("unknown_integration_ws_command", command.get("job_id"))


def job_state_side_effects(
    *,
    job_state_written: bool = False,
    subscription_bookkeeping_written: bool = False,
    websocket_command_registered: bool = False,
) -> dict[str, bool]:
    """Return side-effect accounting for the job state scaffold packet."""
    return {
        **NO_JOB_STATE_ORCHESTRATION_CALLS,
        "job_state_scaffold_written": job_state_written,
        "subscription_bookkeeping_written": subscription_bookkeeping_written,
        "websocket_command_registered": websocket_command_registered,
    }


def summarize_job_state_store(store: dict[str, Any]) -> dict[str, Any]:
    """Return an evidence-friendly summary of a job state store."""
    jobs = store.get("jobs", {})
    ordered_jobs = [
        jobs[job_id]
        for job_id in store.get("job_order", [])
        if job_id in jobs
    ]
    subscriptions = store.get("subscriptions", {})
    ordered_subscriptions = [
        subscriptions[subscription_id]
        for subscription_id in store.get("subscription_order", [])
        if subscription_id in subscriptions
    ]
    return {
        "entry_id": store.get("entry_id"),
        "next_job_number": store.get("next_job_number"),
        "job_ids": [job["job_id"] for job in ordered_jobs],
        "latest_snapshot_ids": [job["latest_snapshot"]["snapshot_id"] for job in ordered_jobs],
        "subscription_ids": [subscription["subscription_id"] for subscription in ordered_subscriptions],
        "subscription_count": len(ordered_subscriptions),
    }


def store_validated_job_snapshot(job: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Validate an IntegrationJobSnapshot before mutating in-memory job state."""
    validation = validate_job_snapshot_contract(snapshot)
    if not validation["accepted"]:
        return validation

    stored_snapshot = deepcopy(snapshot)
    job["snapshots"].append(stored_snapshot)
    job["latest_snapshot"] = stored_snapshot
    return {
        "accepted": True,
        "code": "accepted",
        "snapshot": deepcopy(stored_snapshot),
        "validation": validation,
    }


def append_validated_job_snapshot(
    job: dict[str, Any],
    *,
    status: str,
    state_label: str,
    message: str,
    progress_stage: str,
    progress_message: str,
    validation_status: str,
    validation_summary: str,
    warnings: list[str],
    validation_checks: list[dict[str, str]] | None = None,
    entities: list[dict[str, str]] | None = None,
    clarification: dict[str, Any] | None = None,
    failure: dict[str, str] | None = None,
    retry_allowed: bool | None = None,
) -> dict[str, Any]:
    """Append one schema-valid snapshot to an existing in-memory job."""
    snapshot_number = job["next_snapshot_number"]
    snapshot: dict[str, Any] = {
        "snapshot_id": f"{job['job_id']}-snapshot-{snapshot_number:03d}",
        "job_id": job["job_id"],
        "status": status,
        "prompt": job["prompt"],
        "state_label": state_label,
        "message": message,
        "progress": {
            "stage": progress_stage,
            "message": progress_message,
        },
        "validation": {
            "status": validation_status,
            "summary": validation_summary,
            "checks": validation_checks
            or [
                {
                    "name": "integration_job_state_scaffold",
                    "status": "pass",
                }
            ],
        },
        "warnings": list(warnings),
    }
    if entities is not None:
        snapshot["entities"] = deepcopy(entities)
    if clarification is not None:
        snapshot["clarification"] = deepcopy(clarification)
    if failure is not None:
        snapshot["failure"] = deepcopy(failure)
    if retry_allowed is not None:
        snapshot["retry_allowed"] = retry_allowed

    result = store_validated_job_snapshot(job, snapshot)
    if not result["accepted"]:
        raise JobStateSnapshotValidationError(result)
    job["next_snapshot_number"] = snapshot_number + 1
    return result["snapshot"]


def validate_job_snapshot_contract(snapshot: Any) -> dict[str, Any]:
    """Validate an IntegrationJobSnapshot against the repo JSON Schema."""
    try:
        schema = json.loads(SNAPSHOT_SCHEMA_PATH.read_text(encoding="utf-8"))
        _validate_json_schema(snapshot, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_job_snapshot",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(SNAPSHOT_SCHEMA_PATH),
    }


def _start_job(store: dict[str, Any], command: dict[str, Any]) -> dict[str, Any]:
    job_number = store["next_job_number"]
    job_id = f"{store['entry_id']}-job-{job_number:03d}"
    job = {
        "job_id": job_id,
        "prompt": command["prompt"],
        "next_snapshot_number": 1,
        "snapshots": [],
        "latest_snapshot": None,
        "clarification_answers": [],
    }
    snapshot = _append_snapshot(
        job,
        state_label="Planning",
        message="Prompt accepted by the job state scaffold; orchestration is not implemented yet.",
        progress_stage="job_state_scaffold",
        progress_message="Waiting for a later orchestration packet.",
        validation_summary="The job state scaffold validated only state ownership and command routing.",
        warnings=["job_state_scaffold", "orchestration_not_implemented"],
    )
    store["next_job_number"] += 1
    store["jobs"][job_id] = job
    store["job_order"].append(job_id)
    return _accepted("job_state_created", command, snapshot, job_state_written=True)


def _append_snapshot(
    job: dict[str, Any],
    *,
    state_label: str,
    message: str,
    progress_stage: str,
    progress_message: str,
    validation_summary: str,
    warnings: list[str],
) -> dict[str, Any]:
    return append_validated_job_snapshot(
        job,
        status="planning",
        state_label=state_label,
        message=message,
        progress_stage=progress_stage,
        progress_message=progress_message,
        validation_status="not_run",
        validation_summary=validation_summary,
        validation_checks=[
            {
                "name": "integration_job_state_scaffold",
                "status": "pass",
            },
            {
                "name": "orchestration",
                "status": "not_implemented",
            },
        ],
        warnings=warnings,
    )


def _record_subscription(
    store: dict[str, Any],
    job: dict[str, Any],
    message_id: int | str | None,
) -> dict[str, Any]:
    subscription_number = len(
        [
            subscription_id
            for subscription_id in store["subscription_order"]
            if subscription_id.startswith(f"{job['job_id']}-subscription-")
        ]
    ) + 1
    subscription_id = f"{job['job_id']}-subscription-{subscription_number:03d}"
    subscription = {
        "subscription_id": subscription_id,
        "config_entry_id": store["entry_id"],
        "job_id": job["job_id"],
        "message_id": message_id,
        "event": {
            "type": "isolinear_job_snapshot",
            "job_id": job["job_id"],
            "snapshot": deepcopy(job["latest_snapshot"]),
        },
    }
    store["subscriptions"][subscription_id] = subscription
    store["subscription_order"].append(subscription_id)
    return deepcopy(subscription)


def _accepted(
    code: str,
    command: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    job_state_written: bool = False,
    subscription_bookkeeping_written: bool = False,
    subscription: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "accepted": True,
        "code": code,
        "type": command["type"],
        "version": command["version"],
        "config_entry_id": command["config_entry_id"],
        "job_id": snapshot["job_id"],
        "snapshot": deepcopy(snapshot),
        "orchestration": job_state_side_effects(
            job_state_written=job_state_written,
            subscription_bookkeeping_written=subscription_bookkeeping_written,
        ),
    }
    if subscription is not None:
        result["subscription"] = subscription
    return result


def _job_rejection(code: str, job_id: Any) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": code,
        "job_id": job_id,
        "render_attempted": False,
        "orchestration": job_state_side_effects(),
    }


def _snapshot_validation_rejection(validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": "invalid_integration_job_snapshot",
        "render_attempted": False,
        "validation": validation,
        "orchestration": job_state_side_effects(),
    }


def _validate_json_schema(
    payload: Any,
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any],
    path: str,
) -> None:
    if "$ref" in schema:
        schema = _resolve_ref(schema["$ref"], root_schema)

    if "const" in schema and payload != schema["const"]:
        raise JobStateSnapshotValidationError(_schema_error(f"{path} must equal {schema['const']!r}."))

    if "enum" in schema and payload not in schema["enum"]:
        raise JobStateSnapshotValidationError(_schema_error(f"{path} must be one of {schema['enum']!r}."))

    if "type" in schema:
        _validate_type(payload, schema["type"], path)

    if isinstance(payload, dict):
        _validate_object(payload, schema, root_schema=root_schema, path=path)
    elif isinstance(payload, list):
        _validate_array(payload, schema, root_schema=root_schema, path=path)
    elif isinstance(payload, str):
        _validate_string(payload, schema, path)


def _validate_object(
    payload: dict[str, Any],
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any],
    path: str,
) -> None:
    for property_name in schema.get("required", []):
        if property_name not in payload:
            raise JobStateSnapshotValidationError(_schema_error(f"{path}.{property_name} is required."))

    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        extra_properties = sorted(set(payload) - set(properties))
        if extra_properties:
            raise JobStateSnapshotValidationError(
                _schema_error(f"{path} has unexpected properties: {extra_properties!r}.")
            )

    for property_name, property_schema in properties.items():
        if property_name in payload:
            _validate_json_schema(
                payload[property_name],
                property_schema,
                root_schema=root_schema,
                path=f"{path}.{property_name}",
            )


def _validate_array(
    payload: list[Any],
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any],
    path: str,
) -> None:
    item_schema = schema.get("items")
    if item_schema is None:
        return

    for index, item in enumerate(payload):
        _validate_json_schema(item, item_schema, root_schema=root_schema, path=f"{path}[{index}]")


def _validate_string(payload: str, schema: dict[str, Any], path: str) -> None:
    pattern = schema.get("pattern")
    if pattern is not None and re.search(pattern, payload) is None:
        raise JobStateSnapshotValidationError(_schema_error(f"{path} must match pattern {pattern!r}."))


def _validate_type(payload: Any, schema_type: str | list[str], path: str) -> None:
    expected_types = [schema_type] if isinstance(schema_type, str) else schema_type
    if any(_matches_type(payload, expected_type) for expected_type in expected_types):
        return
    raise JobStateSnapshotValidationError(_schema_error(f"{path} must be of type {expected_types!r}."))


def _matches_type(payload: Any, schema_type: str) -> bool:
    if schema_type == "object":
        return isinstance(payload, dict)
    if schema_type == "array":
        return isinstance(payload, list)
    if schema_type == "string":
        return isinstance(payload, str)
    if schema_type == "integer":
        return isinstance(payload, int) and not isinstance(payload, bool)
    if schema_type == "boolean":
        return isinstance(payload, bool)
    if schema_type == "null":
        return payload is None
    return False


def _resolve_ref(ref: str, root_schema: dict[str, Any]) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise JobStateSnapshotValidationError(_schema_error(f"Unsupported schema ref '{ref}'."))

    current: Any = root_schema
    for part in ref[2:].split("/"):
        current = current[part]
    return current


def _schema_error(error: str) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": "invalid_integration_job_snapshot",
        "error": error,
    }
