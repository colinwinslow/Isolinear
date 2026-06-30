"""Self-contained JSON Schema validation for the isolated worker.

ADR-0029 requires the worker to be deployable in its own container with no
access to the Home Assistant integration. This module is therefore a deliberate,
standalone copy of the integration's minimal schema validator
(`src/Isolinear/contracts.py`): the worker must not import from
`custom_components/isolinear/` or `src/Isolinear/`. It loads schemas bundled
inside the worker package (`isolinear_worker/schemas/`) and supports only the
subset of JSON Schema the contracts use (type/const/enum/oneOf, object/array
constraints, string pattern + date-time, numeric bounds, and internal `#/`
refs).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_NAMES = {
    "chart-spec": "chart-spec.schema.json",
    "codegen-sandbox-policy": "codegen-sandbox-policy.schema.json",
    "history-series": "history-series.schema.json",
    "render-request": "render-request.schema.json",
    "render-result": "render-result.schema.json",
}

_SCHEMA_DIRECTORY = Path(__file__).resolve().parent / "schemas"


class ContractValidationError(ValueError):
    pass


def validate_contract(contract_name: str, payload: Any) -> None:
    schema = _load_schema(contract_name)
    _validate(payload, schema, root_schema=schema, path="$")


def _load_schema(contract_name: str) -> dict[str, Any]:
    if contract_name not in SCHEMA_NAMES:
        raise ContractValidationError(f"Unknown contract '{contract_name}'.")

    schema_path = _SCHEMA_DIRECTORY / SCHEMA_NAMES[contract_name]
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
