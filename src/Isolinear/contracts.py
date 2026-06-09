from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_NAMES = {
    "chart-spec": "chart-spec.schema.json",
    "codegen-sandbox-policy": "codegen-sandbox-policy.schema.json",
    "clarification-question": "clarification-question.schema.json",
    "derived-interval": "derived-interval.schema.json",
    "entity-catalog-item": "entity-catalog-item.schema.json",
    "history-series": "history-series.schema.json",
    "integration-artifact-metadata": "integration-artifact-metadata.schema.json",
    "integration-job-snapshot": "integration-job-snapshot.schema.json",
    "integration-model-provider-plan": "integration-model-provider-plan.schema.json",
    "integration-render-plan": "integration-render-plan.schema.json",
    "integration-worker-readiness": "integration-worker-readiness.schema.json",
    "integration-worker-dispatch": "integration-worker-dispatch.schema.json",
    "integration-worker-progress": "integration-worker-progress.schema.json",
    "integration-worker-retry-policy": "integration-worker-retry-policy.schema.json",
    "integration-worker-transport-failure-classification": (
        "integration-worker-transport-failure-classification.schema.json"
    ),
    "integration-ws-command": "integration-ws-command.schema.json",
    "planner-result": "planner-result.schema.json",
    "render-request": "render-request.schema.json",
    "render-result": "render-result.schema.json",
    "semantic-alias": "semantic-alias.schema.json",
    "semantic-memory-store": "semantic-memory-store.schema.json",
    "validation-result": "validation-result.schema.json",
    "worker-transport-request": "worker-transport-request.schema.json",
}


class ContractValidationError(ValueError):
    pass


def validate_contract(
    contract_name: str,
    payload: Any,
    *,
    repo_root: Path | None = None,
) -> None:
    schema = _load_schema(contract_name, repo_root=repo_root)
    _validate(payload, schema, root_schema=schema, path="$")


def validate_fake_prompt_to_chart_contracts(
    result: dict[str, Any],
    *,
    repo_root: Path | None = None,
) -> None:
    for item in result["entity_catalog"]:
        validate_contract("entity-catalog-item", item, repo_root=repo_root)

    for series in result["history_series"]:
        validate_contract("history-series", series, repo_root=repo_root)

    planner_result = result["planner_result"]
    validate_contract("planner-result", planner_result, repo_root=repo_root)
    if planner_result.get("chart_spec") is not None:
        validate_contract("chart-spec", planner_result["chart_spec"], repo_root=repo_root)
    if planner_result.get("clarification_question") is not None:
        validate_contract(
            "clarification-question",
            planner_result["clarification_question"],
            repo_root=repo_root,
        )

    render_request = result.get("render_request")
    if render_request is not None:
        validate_contract("render-request", render_request, repo_root=repo_root)
        validate_contract("chart-spec", render_request["chart_spec"], repo_root=repo_root)
        for series in render_request["history_series"]:
            validate_contract("history-series", series, repo_root=repo_root)
        for interval in render_request.get("derived_intervals", []):
            validate_contract("derived-interval", interval, repo_root=repo_root)

    render_result = result.get("render_result")
    if render_result is not None:
        validate_contract("render-result", render_result, repo_root=repo_root)

    validation_result = result.get("validation_result")
    if validation_result is not None:
        validate_contract("validation-result", validation_result, repo_root=repo_root)

    for alias in result.get("saved_semantic_aliases", []):
        validate_contract("semantic-alias", alias, repo_root=repo_root)


def _load_schema(contract_name: str, *, repo_root: Path | None) -> dict[str, Any]:
    if contract_name not in SCHEMA_NAMES:
        raise ContractValidationError(f"Unknown contract '{contract_name}'.")

    root = repo_root or Path(__file__).resolve().parents[2]
    schema_path = root / "docs" / "schemas" / SCHEMA_NAMES[contract_name]
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _validate(
    payload: Any,
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any],
    path: str,
) -> None:
    if "$ref" in schema:
        schema = _resolve_ref(schema["$ref"], root_schema)

    if "const" in schema and payload != schema["const"]:
        raise ContractValidationError(f"{path} must equal {schema['const']!r}.")

    if "enum" in schema and payload not in schema["enum"]:
        raise ContractValidationError(f"{path} must be one of {schema['enum']!r}.")

    if "oneOf" in schema:
        matches = []
        errors = []
        for option in schema["oneOf"]:
            try:
                _validate(payload, option, root_schema=root_schema, path=path)
                matches.append(option)
            except ContractValidationError as exc:
                errors.append(str(exc))
        if len(matches) != 1:
            detail = "; ".join(errors[:3])
            raise ContractValidationError(f"{path} must match exactly one schema option. {detail}")
        return

    if "type" in schema:
        _validate_type(payload, schema["type"], path)

    if isinstance(payload, dict):
        _validate_object(payload, schema, root_schema=root_schema, path=path)
    elif isinstance(payload, list):
        _validate_array(payload, schema, root_schema=root_schema, path=path)

    if isinstance(payload, str):
        _validate_string(payload, schema, path)

    if _is_number(payload):
        _validate_number(payload, schema, path)


def _validate_object(
    payload: dict[str, Any],
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any],
    path: str,
) -> None:
    required = schema.get("required", [])
    for property_name in required:
        if property_name not in payload:
            raise ContractValidationError(f"{path}.{property_name} is required.")

    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        extra_properties = sorted(set(payload) - set(properties))
        if extra_properties:
            raise ContractValidationError(f"{path} has unexpected properties: {extra_properties!r}.")

    for property_name, property_schema in properties.items():
        if property_name in payload:
            _validate(
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
    min_items = schema.get("minItems")
    if min_items is not None and len(payload) < min_items:
        raise ContractValidationError(f"{path} must contain at least {min_items} item(s).")

    item_schema = schema.get("items")
    if item_schema is None:
        return

    for index, item in enumerate(payload):
        _validate(item, item_schema, root_schema=root_schema, path=f"{path}[{index}]")


def _validate_string(payload: str, schema: dict[str, Any], path: str) -> None:
    pattern = schema.get("pattern")
    if pattern is not None and re.search(pattern, payload) is None:
        raise ContractValidationError(f"{path} must match pattern {pattern!r}.")

    if schema.get("format") == "date-time":
        try:
            datetime.fromisoformat(payload.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ContractValidationError(f"{path} must be a date-time string.") from exc


def _validate_number(payload: int | float, schema: dict[str, Any], path: str) -> None:
    minimum = schema.get("minimum")
    if minimum is not None and payload < minimum:
        raise ContractValidationError(f"{path} must be greater than or equal to {minimum}.")

    maximum = schema.get("maximum")
    if maximum is not None and payload > maximum:
        raise ContractValidationError(f"{path} must be less than or equal to {maximum}.")


def _validate_type(payload: Any, schema_type: str | list[str], path: str) -> None:
    expected_types = [schema_type] if isinstance(schema_type, str) else schema_type
    if any(_matches_type(payload, expected_type) for expected_type in expected_types):
        return

    raise ContractValidationError(f"{path} must be of type {expected_types!r}.")


def _matches_type(payload: Any, schema_type: str) -> bool:
    if schema_type == "object":
        return isinstance(payload, dict)
    if schema_type == "array":
        return isinstance(payload, list)
    if schema_type == "string":
        return isinstance(payload, str)
    if schema_type == "number":
        return _is_number(payload)
    if schema_type == "integer":
        return isinstance(payload, int) and not isinstance(payload, bool)
    if schema_type == "boolean":
        return isinstance(payload, bool)
    if schema_type == "null":
        return payload is None
    return False


def _is_number(payload: Any) -> bool:
    return isinstance(payload, (int, float)) and not isinstance(payload, bool)


def _resolve_ref(ref: str, root_schema: dict[str, Any]) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ContractValidationError(f"Unsupported schema ref '{ref}'.")

    current: Any = root_schema
    for part in ref[2:].split("/"):
        current = current[part]
    return current
