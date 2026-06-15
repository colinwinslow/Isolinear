from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from custom_components.isolinear.config_flow import (
    CONFIG_FLOW_STEP,
    IsolinearConfigFlow,
    NO_FLOW_ORCHESTRATION_CALLS,
    OPTIONS_FLOW_STEP,
    config_flow_field_metadata,
    validate_config_flow_user_input,
    validate_options_flow_user_input,
)
from custom_components.isolinear.config_schema import default_config_data

from .dashboard_card_anchor import repo_root
from .integration_scaffold_anchor import load_manifest


CONFIG_FLOW_FILES = [
    "custom_components/isolinear/manifest.json",
    "custom_components/isolinear/config_schema.py",
    "custom_components/isolinear/config_flow.py",
]


def sample_config_flow_user_input() -> dict[str, Any]:
    return {
        "model_provider_type": "ollama_compatible",
        "model_endpoint_url": " http://localhost:11434 ",
        "planner_model": " llama3.1 ",
        "codegen_model": "",
        "visual_validator_model": "   ",
        "worker_endpoint_url": "http://localhost:8765",
    }


def sample_options_flow_user_input() -> dict[str, Any]:
    return {
        "default_render_mode": "auto",
        "max_codegen_repair_attempts": "2",
        "entity_allowlist": (
            "sensor.upstairs_temperature\n"
            "sensor.downstairs_temperature, binary_sensor.office_window"
        ),
    }


def invalid_flow_input_examples() -> dict[str, dict[str, dict[str, Any]]]:
    valid_config = default_config_data()
    return {
        "config": {
            "credential_endpoint_url": {
                **sample_config_flow_user_input(),
                "worker_endpoint_url": "http://user:secret@localhost:8765",
            },
            "secret_like_model": {
                **sample_config_flow_user_input(),
                "planner_model": "long_lived_access_token",
            },
            "secret_config_key": {
                **sample_config_flow_user_input(),
                "worker_token": "super-secret-worker-token",
            },
        },
        "options": {
            "invalid_render_mode": {
                **sample_options_flow_user_input(),
                "default_render_mode": "unsafe_direct_python",
            },
            "duplicate_allowlist": {
                **sample_options_flow_user_input(),
                "entity_allowlist": (
                    "sensor.upstairs_temperature\n"
                    "sensor.upstairs_temperature"
                ),
            },
            "malformed_allowlist": {
                **sample_options_flow_user_input(),
                "entity_allowlist": "not-an-entity-id",
            },
            "secret_options_material": {
                **sample_options_flow_user_input(),
                "worker_token": "super-secret-worker-token",
            },
        },
        "valid_config_data": valid_config,
    }


def verify_config_flow_manifest(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    manifest = load_manifest(root)
    file_results = {
        path: (root / path).exists()
        for path in CONFIG_FLOW_FILES
    }
    config_flow_path = root / "custom_components" / "isolinear" / "config_flow.py"
    config_flow_text = config_flow_path.read_text(encoding="utf-8") if config_flow_path.exists() else ""
    return {
        "manifest": manifest,
        "files": file_results,
        "manifest_config_flow_enabled": manifest.get("config_flow") is True,
        "config_flow_file_present": config_flow_path.exists(),
        "config_flow_class_present": "class IsolinearConfigFlow" in config_flow_text,
        "options_flow_class_present": "class IsolinearOptionsFlow" in config_flow_text,
        "flow_steps": {
            "config": CONFIG_FLOW_STEP,
            "options": OPTIONS_FLOW_STEP,
        },
        "metadata": config_flow_field_metadata(),
    }


def verify_config_flow_user_path() -> dict[str, Any]:
    return validate_config_flow_user_input(sample_config_flow_user_input())


def verify_options_flow_path() -> dict[str, Any]:
    config_result = verify_config_flow_user_path()
    return validate_options_flow_user_input(
        config_result["config_data"],
        sample_options_flow_user_input(),
    )


def verify_live_allowlist_input_variants() -> dict[str, Any]:
    valid_config = default_config_data()
    variants = {
        "plain_entity_text": validate_options_flow_user_input(
            valid_config,
            "sensor.family_room_sensor_temperature",
        ),
        "json_array_text": validate_options_flow_user_input(
            valid_config,
            {
                "default_render_mode": "safe",
                "max_codegen_repair_attempts": 1,
                "entity_allowlist": '["sensor.family_room_sensor_temperature"]',
            },
        ),
    }
    return {
        "expected_entity_allowlist": ["sensor.family_room_sensor_temperature"],
        "variants": variants,
    }


def verify_options_flow_uses_passed_config_entry() -> dict[str, Any]:
    config_entry = SimpleNamespace(
        data=default_config_data(),
        options={
            "default_render_mode": "safe",
            "max_codegen_repair_attempts": 1,
            "entity_allowlist": [],
        },
    )
    flow = IsolinearConfigFlow.async_get_options_flow(config_entry)
    result = asyncio.run(
        flow.async_step_init(
            {
                "default_render_mode": "safe",
                "max_codegen_repair_attempts": 1,
                "entity_allowlist": "sensor.family_room_sensor_temperature",
            }
        )
    )
    return {
        "flow_class": type(flow).__name__,
        "retains_passed_config_entry": getattr(flow, "_fallback_config_entry", None) is config_entry,
        "result": result,
    }


def verify_options_flow_tolerates_missing_config_entry_data() -> dict[str, Any]:
    config_entry = SimpleNamespace(
        data=None,
        options={
            "default_render_mode": "safe",
            "max_codegen_repair_attempts": 1,
            "entity_allowlist": [],
        },
    )
    flow = IsolinearConfigFlow.async_get_options_flow(config_entry)
    result = asyncio.run(
        flow.async_step_init(
            {
                "default_render_mode": "safe",
                "max_codegen_repair_attempts": 1,
                "entity_allowlist": "sensor.family_room_sensor_temperature",
            }
        )
    )
    return {
        "accepted": result.get("type") == "create_entry",
        "flow_class": type(flow).__name__,
        "retains_passed_config_entry": getattr(flow, "_fallback_config_entry", None) is config_entry,
        "result": result,
    }


def verify_invalid_flow_inputs() -> dict[str, Any]:
    examples = invalid_flow_input_examples()
    config_results = {
        name: validate_config_flow_user_input(example)
        for name, example in examples["config"].items()
    }
    options_results = {
        name: validate_options_flow_user_input(
            examples["valid_config_data"],
            example,
        )
        for name, example in examples["options"].items()
    }
    return {
        "config": config_results,
        "options": options_results,
    }


def verify_non_orchestration() -> dict[str, Any]:
    observed = [
        {"name": "config_flow_user", **NO_FLOW_ORCHESTRATION_CALLS},
        {"name": "options_flow_init", **NO_FLOW_ORCHESTRATION_CALLS},
        {"name": "invalid_config_flow_input", **NO_FLOW_ORCHESTRATION_CALLS},
        {"name": "invalid_options_flow_input", **NO_FLOW_ORCHESTRATION_CALLS},
    ]
    aggregate = {
        key: any(item[key] for item in observed)
        for key in NO_FLOW_ORCHESTRATION_CALLS
    }
    return {
        "expected": dict(NO_FLOW_ORCHESTRATION_CALLS),
        "observed": observed,
        "aggregate": aggregate,
    }


def verify_config_flow_anchor(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    manifest = verify_config_flow_manifest(root)
    config_flow = verify_config_flow_user_path()
    options_flow = verify_options_flow_path()
    live_allowlist_variants = verify_live_allowlist_input_variants()
    options_flow_config_entry = verify_options_flow_uses_passed_config_entry()
    missing_config_entry_data = verify_options_flow_tolerates_missing_config_entry_data()
    invalid_inputs = verify_invalid_flow_inputs()
    non_orchestration = verify_non_orchestration()

    failures = []
    if not manifest["manifest_config_flow_enabled"]:
        failures.append("Manifest does not enable config_flow.")
    if not manifest["config_flow_file_present"]:
        failures.append("config_flow.py is missing on disk.")
    if not manifest["config_flow_class_present"]:
        failures.append("IsolinearConfigFlow class marker is missing.")
    if not manifest["options_flow_class_present"]:
        failures.append("IsolinearOptionsFlow class marker is missing.")
    if not all(manifest["files"].values()):
        failures.append("One or more config-flow anchor files are missing.")
    if not config_flow["accepted"]:
        failures.append("Valid config-flow user input was rejected.")
    if not options_flow["accepted"]:
        failures.append("Valid options-flow user input was rejected.")
    for name, result in live_allowlist_variants["variants"].items():
        if not result["accepted"]:
            failures.append(f"Live allowlist variant {name} was rejected.")
        elif result["options_data"]["entity_allowlist"] != live_allowlist_variants["expected_entity_allowlist"]:
            failures.append(f"Live allowlist variant {name} normalized to the wrong allowlist.")
    if not options_flow_config_entry["retains_passed_config_entry"]:
        failures.append("Options flow did not retain the Home Assistant config entry.")
    if options_flow_config_entry["result"].get("type") != "create_entry":
        failures.append("Options flow did not persist options through the passed config entry.")
    if not missing_config_entry_data["accepted"]:
        failures.append("Options flow rejected allowlist edits when config-entry data was missing.")
    if not all(not item["accepted"] for item in invalid_inputs["config"].values()):
        failures.append("One or more invalid config-flow examples were accepted.")
    if not all(not item["accepted"] for item in invalid_inputs["options"].values()):
        failures.append("One or more invalid options-flow examples were accepted.")
    if any(non_orchestration["aggregate"].values()):
        failures.append("Config-flow/options anchor reported orchestration calls.")

    return {
        "passed": not failures,
        "failures": failures,
        "manifest": manifest,
        "config_flow": config_flow,
        "options_flow": options_flow,
        "live_allowlist_variants": live_allowlist_variants,
        "options_flow_config_entry": options_flow_config_entry,
        "missing_config_entry_data": missing_config_entry_data,
        "invalid_inputs": invalid_inputs,
        "non_orchestration": non_orchestration,
    }
