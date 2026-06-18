from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from custom_components.isolinear.config_schema import (
    default_config_data,
    default_options_data,
    invalid_config_examples,
    redacted_config_result,
    validate_config_and_options,
    validate_default_config_and_options,
)
from custom_components.isolinear.const import (
    DOMAIN,
    INTEGRATION_COMMAND_TYPES,
    INTEGRATION_VERSION,
    INTEGRATION_WS_NAMESPACE,
    INTEGRATION_WS_VERSION,
)
from custom_components.isolinear.websocket_api import (
    NO_ORCHESTRATION_CALLS,
    handle_scaffold_ws_command,
    invalid_command_examples,
)

from .contracts import ContractValidationError, validate_contract
from .dashboard_card_anchor import repo_root
from .transport_auth_anchor import sample_integration_ws_commands


SCAFFOLD_FILES = [
    "custom_components/isolinear/manifest.json",
    "custom_components/isolinear/__init__.py",
    "custom_components/isolinear/const.py",
    "custom_components/isolinear/config_schema.py",
    "custom_components/isolinear/websocket_api.py",
]

CONFIG_FLOW_BLOCKING_REQUIREMENT_PREFIXES = ("matplotlib",)


def load_manifest(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    manifest_path = root / "custom_components" / "isolinear" / "manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def verify_manifest(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    manifest = load_manifest(root)
    files = {
        path: (root / path).exists()
        for path in SCAFFOLD_FILES
    }
    return {
        "manifest": manifest,
        "files": files,
        "domain_matches": manifest.get("domain") == DOMAIN,
        "version_present": isinstance(manifest.get("version"), str) and bool(manifest["version"]),
        "const_version": INTEGRATION_VERSION,
        "const_version_matches_manifest": manifest.get("version") == INTEGRATION_VERSION,
        "runtime_requirements": manifest.get("requirements"),
        "config_flow_blocking_requirements_deferred": not any(
            requirement.startswith(prefix)
            for requirement in manifest.get("requirements", [])
            for prefix in CONFIG_FLOW_BLOCKING_REQUIREMENT_PREFIXES
        ),
        "all_scaffold_files_present": all(files.values()),
    }


def verify_config_shape() -> dict[str, Any]:
    default_result = validate_default_config_and_options()
    invalid_results = {
        name: validate_config_and_options(example["config_data"], example["options_data"])
        for name, example in invalid_config_examples().items()
    }
    return {
        "defaults": {
            "config_data": default_config_data(),
            "options_data": default_options_data(),
            "result": redacted_config_result(default_result),
        },
        "invalid_results": invalid_results,
    }


def verify_command_stubs(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    commands = sample_integration_ws_commands()
    accepted_results = {}
    snapshot_validation = {}
    for name, command in commands.items():
        result = handle_scaffold_ws_command(command)
        accepted_results[name] = result
        snapshot = result.get("snapshot")
        try:
            validate_contract("integration-ws-command", command, repo_root=root)
            validate_contract("integration-job-snapshot", snapshot, repo_root=root)
        except ContractValidationError as exc:
            snapshot_validation[name] = {
                "accepted": False,
                "code": "contract_validation_failed",
                "error": str(exc),
            }
        else:
            snapshot_validation[name] = {
                "accepted": True,
                "code": "accepted",
                "status": snapshot["status"],
            }

    invalid_results = {
        name: handle_scaffold_ws_command(command)
        for name, command in invalid_command_examples().items()
    }
    return {
        "namespace": INTEGRATION_WS_NAMESPACE,
        "version": INTEGRATION_WS_VERSION,
        "commands": commands,
        "command_types": INTEGRATION_COMMAND_TYPES,
        "accepted_results": accepted_results,
        "snapshot_validation": snapshot_validation,
        "invalid_results": invalid_results,
    }


def verify_no_orchestration_calls(command_results: dict[str, Any]) -> dict[str, Any]:
    observed = []
    for name, result in command_results.items():
        orchestration = result.get("orchestration", {})
        observed.append({"name": name, **orchestration})
    aggregate = {
        key: any(item.get(key) for item in observed)
        for key in NO_ORCHESTRATION_CALLS
    }
    return {
        "expected": dict(NO_ORCHESTRATION_CALLS),
        "observed": observed,
        "aggregate": aggregate,
    }


def verify_integration_scaffold_anchor(root: Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    manifest_result = verify_manifest(root)
    config_result = verify_config_shape()
    command_result = verify_command_stubs(root)
    no_orchestration = verify_no_orchestration_calls(
        {
            **command_result["accepted_results"],
            **command_result["invalid_results"],
        }
    )

    failures = []
    if not manifest_result["domain_matches"]:
        failures.append("Manifest domain does not match the Isolinear domain constant.")
    if not manifest_result["version_present"]:
        failures.append("Manifest does not include a version.")
    if not manifest_result["const_version_matches_manifest"]:
        failures.append("Manifest version does not match the integration version constant.")
    if not manifest_result["config_flow_blocking_requirements_deferred"]:
        failures.append("Manifest declares a renderer-only requirement that can block config-flow loading.")
    if not manifest_result["all_scaffold_files_present"]:
        failures.append("One or more scaffold files are missing on disk.")
    if not config_result["defaults"]["result"]["accepted"]:
        failures.append("Default integration config/options shape was rejected.")
    if not all(not result["accepted"] for result in config_result["invalid_results"].values()):
        failures.append("One or more invalid config examples were accepted.")
    if not all(result["accepted"] for result in command_result["accepted_results"].values()):
        failures.append("One or more known integration commands were rejected.")
    if not all(result["accepted"] for result in command_result["snapshot_validation"].values()):
        failures.append("One or more accepted command snapshots failed schema validation.")
    if not all(not result["accepted"] for result in command_result["invalid_results"].values()):
        failures.append("One or more invalid integration commands were accepted.")
    if any(no_orchestration["aggregate"].values()):
        failures.append("Scaffold command handling reported orchestration calls.")

    return {
        "passed": not failures,
        "failures": failures,
        "manifest": manifest_result,
        "config": config_result,
        "commands": command_result,
        "no_orchestration": no_orchestration,
    }
