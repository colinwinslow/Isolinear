from __future__ import annotations

from copy import deepcopy
from typing import Any

import custom_components.isolinear.worker_readiness as worker_readiness
from custom_components.isolinear import async_setup_entry
from custom_components.isolinear.const import DOMAIN
from custom_components.isolinear.worker_readiness import (
    DATA_WORKER_READINESS,
    DATA_WORKER_READINESS_SETUP,
    provision_integration_worker_token,
)
from custom_components.isolinear.worker_renderer import (
    DATA_WORKER_RENDER_CLIENT,
    DATA_WORKER_RENDER_SETUP,
    DATA_WORKER_RENDER_TOKEN,
    setup_worker_renderer,
)

from .contracts import ContractValidationError, validate_contract
from .dashboard_card_anchor import repo_root
from .entity_catalog_scaffold_anchor import FakeConfigEntry
from .job_orchestration_scaffold_anchor import _fake_hass, _run
from .websocket_command_registration_anchor import FakeWebSocketApiModule


WORKER_READINESS_TEST_TOKEN = "test-worker-readiness-token-000000000"
WORKER_READINESS_SECOND_TOKEN = "test-worker-readiness-token-111111111"
WORKER_ENDPOINT_URL = "http://worker.local:8765"

WORKER_TOKEN_READINESS_FILES = [
    "custom_components/isolinear/worker_readiness.py",
    "custom_components/isolinear/worker_renderer.py",
    "custom_components/isolinear/__init__.py",
    "docs/schemas/integration-worker-readiness.schema.json",
    "docs/specs/home-assistant-worker-token-provisioning-readiness-scaffold-spec.md",
    "bdd/integration/home-assistant-worker-token-provisioning-readiness-scaffold-bdd.md",
    "bdd/integration/home-assistant-worker-token-provisioning-readiness-scaffold-evidence.md",
    "docs/evals/home_assistant_worker_token_provisioning_readiness_scaffold.yaml",
    "tests/test_worker_token_provisioning_readiness_anchor.py",
    "evals/home_assistant_worker_token_provisioning_readiness_scaffold.py",
    "src/Isolinear/worker_token_provisioning_readiness_anchor.py",
]

WORKER_READINESS_FORBIDDEN_SIDE_EFFECT_KEYS = [
    "home_assistant_history_read",
    "semantic_memory_called",
    "home_assistant_service_or_state_mutation_called",
    "worker_called",
    "chart_rendering_called",
    "chart_artifact_written",
    "durable_token_storage_written",
    "token_rotation_called",
    "worker_health_check_called",
    "retry_behavior_called",
    "automatic_progress_task_called",
    "worker_streaming_called",
    "token_leaked_to_card",
    "token_leaked_to_model_provider",
]


class CountingTokenFactory:
    def __init__(self, token: str = WORKER_READINESS_TEST_TOKEN) -> None:
        self.token = token
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        return self.token


def verify_worker_token_readiness_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in WORKER_TOKEN_READINESS_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_explicit_token_provisioning_records_ready_state(root=None) -> dict[str, Any]:
    root = root or repo_root()
    entry = _worker_entry("worker-ready-entry")
    hass = _setup_readiness_hass(entry)
    initial_setup = deepcopy(_entry_data(hass, entry.entry_id)[DATA_WORKER_READINESS_SETUP])
    initial_readiness = _readiness(hass, entry.entry_id)
    token_factory = CountingTokenFactory()

    provision = provision_integration_worker_token(hass, entry.entry_id, token_factory=token_factory)
    renderer_setup = setup_worker_renderer(hass, entry)
    readiness = _readiness(hass, entry.entry_id)

    return {
        "initial_setup": initial_setup,
        "initial_readiness": initial_readiness,
        "provision": provision,
        "readiness": readiness,
        "readiness_validation": _validate_readiness(readiness, root),
        "renderer_setup": renderer_setup,
        "renderer_client_present": DATA_WORKER_RENDER_CLIENT in _entry_data(hass, entry.entry_id),
        "raw_token_stored": _entry_data(hass, entry.entry_id).get(DATA_WORKER_RENDER_TOKEN) == WORKER_READINESS_TEST_TOKEN,
        "token_factory_call_count": token_factory.calls,
    }


def verify_no_token_setup_reports_not_ready(root=None) -> dict[str, Any]:
    root = root or repo_root()
    entry = _worker_entry("worker-no-token-entry")
    hass = _setup_readiness_hass(entry)
    entry_data = _entry_data(hass, entry.entry_id)
    return {
        "setup": deepcopy(entry_data[DATA_WORKER_READINESS_SETUP]),
        "readiness": _readiness(hass, entry.entry_id),
        "readiness_validation": _validate_readiness(_readiness(hass, entry.entry_id), root),
        "renderer_setup": deepcopy(entry_data["worker_renderer_setup"]),
        "worker_render_setup": deepcopy(entry_data[DATA_WORKER_RENDER_SETUP]),
        "renderer_client_present": DATA_WORKER_RENDER_CLIENT in entry_data,
    }


def verify_missing_worker_endpoint_reports_disabled(root=None) -> dict[str, Any]:
    root = root or repo_root()
    entry = FakeConfigEntry("worker-disabled-entry")
    hass = _setup_readiness_hass(entry)
    entry_data = _entry_data(hass, entry.entry_id)
    return {
        "setup": deepcopy(entry_data[DATA_WORKER_READINESS_SETUP]),
        "readiness": _readiness(hass, entry.entry_id),
        "readiness_validation": _validate_readiness(_readiness(hass, entry.entry_id), root),
        "renderer_setup": deepcopy(entry_data["worker_renderer_setup"]),
        "worker_render_setup": deepcopy(entry_data[DATA_WORKER_RENDER_SETUP]),
        "renderer_client_present": DATA_WORKER_RENDER_CLIENT in entry_data,
    }


def verify_repeated_provisioning_reuses_token(root=None) -> dict[str, Any]:
    root = root or repo_root()
    entry = _worker_entry("worker-idempotent-ready-entry")
    hass = _setup_readiness_hass(entry)
    token_factory = CountingTokenFactory()
    first = provision_integration_worker_token(hass, entry.entry_id, token_factory=token_factory)
    stored_after_first = _entry_data(hass, entry.entry_id).get(DATA_WORKER_RENDER_TOKEN)
    second = provision_integration_worker_token(hass, entry.entry_id, token_factory=token_factory)
    stored_after_second = _entry_data(hass, entry.entry_id).get(DATA_WORKER_RENDER_TOKEN)
    second_readiness = _readiness(hass, entry.entry_id)
    return {
        "first": first,
        "second": second,
        "first_readiness": first["readiness"],
        "second_readiness": second_readiness,
        "second_readiness_validation": _validate_readiness(second_readiness, root),
        "token_factory_call_count": token_factory.calls,
        "stored_token_unchanged": stored_after_first == stored_after_second == WORKER_READINESS_TEST_TOKEN,
    }


def verify_unknown_config_entry_rejected_before_token_generation() -> dict[str, Any]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    token_factory = CountingTokenFactory()
    provision = provision_integration_worker_token(hass, "missing-worker-entry", token_factory=token_factory)
    domain_data = hass.data.get(DOMAIN, {})
    return {
        "provision": provision,
        "token_factory_call_count": token_factory.calls,
        "entry_created": "missing-worker-entry" in domain_data,
        "readiness_written": (
            isinstance(domain_data.get("missing-worker-entry"), dict)
            and DATA_WORKER_READINESS in domain_data["missing-worker-entry"]
        ),
    }


def verify_readiness_validation_failure_does_not_store_token(root=None) -> dict[str, Any]:
    root = root or repo_root()
    entry = _worker_entry("worker-validation-failure-entry")
    hass = _setup_readiness_hass(entry)
    token_factory = CountingTokenFactory()
    original_schema_path = worker_readiness.WORKER_READINESS_SCHEMA_PATH
    try:
        worker_readiness.WORKER_READINESS_SCHEMA_PATH = root / "docs" / "schemas" / "missing-worker-readiness.schema.json"
        provision = worker_readiness.provision_integration_worker_token(
            hass,
            entry.entry_id,
            token_factory=token_factory,
        )
    finally:
        worker_readiness.WORKER_READINESS_SCHEMA_PATH = original_schema_path

    entry_data = _entry_data(hass, entry.entry_id)
    return {
        "provision": provision,
        "token_factory_call_count": token_factory.calls,
        "token_present_after_failure": DATA_WORKER_RENDER_TOKEN in entry_data,
        "readiness_written_after_failure": entry_data.get(DATA_WORKER_READINESS, {}).get("code") == "worker_token_provisioned",
        "stored_readiness": _readiness(hass, entry.entry_id),
    }


def verify_readiness_and_tokens_stay_config_entry_scoped(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = _worker_entry("worker-ready-entry-a")
    entry_b = _worker_entry("worker-ready-entry-b")
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))

    provision_a = provision_integration_worker_token(
        hass,
        entry_a.entry_id,
        token_factory=CountingTokenFactory(WORKER_READINESS_TEST_TOKEN),
    )
    renderer_setup_a = setup_worker_renderer(hass, entry_a)
    renderer_setup_b = setup_worker_renderer(hass, entry_b)

    readiness_a = _readiness(hass, entry_a.entry_id)
    readiness_b = _readiness(hass, entry_b.entry_id)
    return {
        "entry_a": {
            "provision": provision_a,
            "readiness": readiness_a,
            "readiness_validation": _validate_readiness(readiness_a, root),
            "renderer_setup": renderer_setup_a,
            "token_present": DATA_WORKER_RENDER_TOKEN in _entry_data(hass, entry_a.entry_id),
            "renderer_client_present": DATA_WORKER_RENDER_CLIENT in _entry_data(hass, entry_a.entry_id),
        },
        "entry_b": {
            "readiness": readiness_b,
            "readiness_validation": _validate_readiness(readiness_b, root),
            "renderer_setup": renderer_setup_b,
            "token_present": DATA_WORKER_RENDER_TOKEN in _entry_data(hass, entry_b.entry_id),
            "renderer_client_present": DATA_WORKER_RENDER_CLIENT in _entry_data(hass, entry_b.entry_id),
        },
    }


def verify_worker_token_does_not_leak(root=None) -> dict[str, Any]:
    accepted = verify_explicit_token_provisioning_records_ready_state(root)
    entry = _worker_entry("worker-leak-entry")
    hass = _setup_readiness_hass(entry)
    provision = provision_integration_worker_token(
        hass,
        entry.entry_id,
        token_factory=CountingTokenFactory(WORKER_READINESS_TEST_TOKEN),
    )
    renderer_setup = setup_worker_renderer(hass, entry)
    entry_data = _entry_data(hass, entry.entry_id)
    readiness = _readiness(hass, entry.entry_id)
    setup_payload = {
        "readiness_setup": entry_data[DATA_WORKER_READINESS_SETUP],
        "renderer_setup": renderer_setup,
    }
    evidence_payload = {
        "provision": provision,
        "readiness": readiness,
        "renderer_setup": renderer_setup,
        "accepted": accepted["provision"],
    }
    return {
        "token_absent_from_readiness": WORKER_READINESS_TEST_TOKEN not in str(readiness),
        "token_absent_from_setup": WORKER_READINESS_TEST_TOKEN not in str(setup_payload),
        "token_absent_from_dashboard_card_metadata": WORKER_READINESS_TEST_TOKEN not in str(entry_data["websocket_api"]),
        "token_absent_from_model_provider_metadata": WORKER_READINESS_TEST_TOKEN not in str(entry_data["model_provider_setup"]),
        "token_absent_from_evidence_payload": WORKER_READINESS_TEST_TOKEN not in str(evidence_payload),
        "stored_authorization": readiness["token"]["authorization"],
        "readiness": readiness,
        "provision": provision,
    }


def verify_worker_readiness_side_effect_boundaries() -> dict[str, Any]:
    accepted = verify_explicit_token_provisioning_records_ready_state()
    no_token = verify_no_token_setup_reports_not_ready()
    disabled = verify_missing_worker_endpoint_reports_disabled()
    repeated = verify_repeated_provisioning_reuses_token()
    unknown = verify_unknown_config_entry_rejected_before_token_generation()
    validation_failure = verify_readiness_validation_failure_does_not_store_token()
    isolation = verify_readiness_and_tokens_stay_config_entry_scoped()

    observed = [
        {"name": "accepted_initial_readiness", **accepted["initial_readiness"]["orchestration"]},
        {"name": "accepted_provision", **accepted["provision"]["orchestration"]},
        {"name": "accepted_readiness", **accepted["readiness"]["orchestration"]},
        {"name": "no_token_readiness", **no_token["readiness"]["orchestration"]},
        {"name": "disabled_readiness", **disabled["readiness"]["orchestration"]},
        {"name": "repeated_first", **repeated["first"]["orchestration"]},
        {"name": "repeated_second", **repeated["second"]["orchestration"]},
        {"name": "unknown_config_entry", **unknown["provision"]["orchestration"]},
        {"name": "validation_failure", **validation_failure["provision"]["orchestration"]},
        {"name": "isolation_entry_a", **isolation["entry_a"]["readiness"]["orchestration"]},
        {"name": "isolation_entry_b", **isolation["entry_b"]["readiness"]["orchestration"]},
    ]
    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in WORKER_READINESS_FORBIDDEN_SIDE_EFFECT_KEYS
    }
    allowed_aggregate = {
        "token_generated": any(item.get("token_generated") for item in observed),
        "token_stored": any(item.get("token_stored") for item in observed),
        "readiness_bookkeeping_written": any(item.get("readiness_bookkeeping_written") for item in observed),
        "worker_renderer_setup_gated": any(item.get("worker_renderer_setup_gated") for item in observed),
    }
    return {
        "expected_forbidden": {key: False for key in WORKER_READINESS_FORBIDDEN_SIDE_EFFECT_KEYS},
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }


def verify_worker_token_provisioning_readiness_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_worker_token_readiness_files(root)
    accepted = verify_explicit_token_provisioning_records_ready_state(root)
    no_token = verify_no_token_setup_reports_not_ready(root)
    disabled = verify_missing_worker_endpoint_reports_disabled(root)
    repeated = verify_repeated_provisioning_reuses_token(root)
    unknown = verify_unknown_config_entry_rejected_before_token_generation()
    validation_failure = verify_readiness_validation_failure_does_not_store_token(root)
    isolation = verify_readiness_and_tokens_stay_config_entry_scoped(root)
    leakage = verify_worker_token_does_not_leak(root)
    side_effects = verify_worker_readiness_side_effect_boundaries()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more worker token/readiness scaffold files are missing.")
    if accepted["readiness"]["status"] != "ready":
        failures.append("Explicit token provisioning did not record ready readiness.")
    if not accepted["readiness_validation"]["accepted"]:
        failures.append("Provisioned readiness did not validate.")
    if not accepted["renderer_setup"]["enabled"] or not accepted["renderer_client_present"]:
        failures.append("Worker renderer setup was not enabled after explicit token provisioning.")
    if WORKER_READINESS_TEST_TOKEN in str(accepted["provision"]) or WORKER_READINESS_TEST_TOKEN in str(accepted["readiness"]):
        failures.append("Provisioning or readiness result leaked raw worker token.")
    if no_token["readiness"]["status"] != "not_ready" or no_token["renderer_client_present"]:
        failures.append("No-token setup did not stay not-ready with renderer disabled.")
    if disabled["readiness"]["status"] != "disabled" or disabled["renderer_client_present"]:
        failures.append("Missing-endpoint setup did not stay disabled with renderer disabled.")
    if repeated["token_factory_call_count"] != 1 or not repeated["stored_token_unchanged"]:
        failures.append("Repeated provisioning did not reuse the existing token.")
    if unknown["provision"]["code"] != "unknown_config_entry" or unknown["token_factory_call_count"] != 0:
        failures.append("Unknown config entry did not fail before token generation.")
    if unknown["entry_created"] or unknown["readiness_written"]:
        failures.append("Unknown config entry created token/readiness state.")
    if validation_failure["provision"]["code"] != "invalid_integration_worker_readiness":
        failures.append("Readiness validation failure did not return the schema failure code.")
    if validation_failure["token_present_after_failure"] or validation_failure["readiness_written_after_failure"]:
        failures.append("Readiness validation failure left token or provisioned readiness state behind.")
    if isolation["entry_a"]["readiness"]["status"] != "ready" or isolation["entry_b"]["readiness"]["status"] != "not_ready":
        failures.append("Readiness status did not stay isolated by config entry.")
    if isolation["entry_b"]["token_present"] or isolation["entry_b"]["renderer_client_present"]:
        failures.append("Entry B received entry A worker token or renderer client.")
    if not all(
        leakage[key]
        for key in (
            "token_absent_from_readiness",
            "token_absent_from_setup",
            "token_absent_from_dashboard_card_metadata",
            "token_absent_from_model_provider_metadata",
            "token_absent_from_evidence_payload",
        )
    ):
        failures.append("Raw worker token leaked into user-visible or evidence metadata.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("Worker readiness scaffold reported forbidden side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("Worker readiness scaffold did not report expected allowed side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "accepted": accepted,
        "no_token": no_token,
        "disabled": disabled,
        "repeated": repeated,
        "unknown": unknown,
        "validation_failure": validation_failure,
        "isolation": isolation,
        "leakage": leakage,
        "side_effects": side_effects,
    }


def _worker_entry(entry_id: str) -> FakeConfigEntry:
    return FakeConfigEntry(
        entry_id,
        data={"worker_endpoint_url": WORKER_ENDPOINT_URL},
    )


def _setup_readiness_hass(entry: FakeConfigEntry) -> Any:
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    setup_accepted = _run(async_setup_entry(hass, entry))
    if not setup_accepted:
        raise AssertionError(f"async_setup_entry rejected {entry.entry_id}")
    return hass


def _entry_data(hass: Any, entry_id: str) -> dict[str, Any]:
    return hass.data[DOMAIN][entry_id]


def _readiness(hass: Any, entry_id: str) -> dict[str, Any]:
    return deepcopy(_entry_data(hass, entry_id)[DATA_WORKER_READINESS])


def _validate_readiness(readiness: dict[str, Any], root) -> dict[str, Any]:
    try:
        validate_contract("integration-worker-readiness", readiness, repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "contract_validation_failed",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "readiness_id": readiness["readiness_id"],
        "config_entry_id": readiness["config_entry_id"],
        "status": readiness["status"],
        "authorization": readiness["token"]["authorization"],
    }
