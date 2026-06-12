from __future__ import annotations

from copy import deepcopy
from typing import Any

from custom_components.isolinear.const import DOMAIN
from custom_components.isolinear.model_provider import DATA_MODEL_PROVIDER_PLANNER
from custom_components.isolinear.model_provider_health import (
    DATA_MODEL_PROVIDER_HEALTH,
    DATA_MODEL_PROVIDER_HEALTH_SETUP,
    check_model_provider_health,
    setup_model_provider_health,
)

from .contracts import ContractValidationError, validate_contract
from .dashboard_card_anchor import repo_root
from .entity_catalog_scaffold_anchor import FakeConfigEntry
from .job_orchestration_scaffold_anchor import _fake_hass, _run
from .websocket_command_registration_anchor import FakeWebSocketApiModule


PROVIDER_ENDPOINT_A = "http://ollama-a.local:11434"
PROVIDER_ENDPOINT_B = "http://ollama-b.local:11434"
PLANNER_MODEL_A = "llama3.1"
PLANNER_MODEL_B = "mistral"

MODEL_PROVIDER_HEALTH_FILES = [
    "custom_components/isolinear/model_provider_health.py",
    "custom_components/isolinear/model_provider.py",
    "custom_components/isolinear/__init__.py",
    "docs/schemas/model-provider-health-request.schema.json",
    "docs/schemas/integration-model-provider-health.schema.json",
    "docs/specs/home-assistant-model-provider-health-diagnostics-scaffold-spec.md",
    "bdd/integration/home-assistant-model-provider-health-diagnostics-scaffold-bdd.md",
    "bdd/integration/home-assistant-model-provider-health-diagnostics-scaffold-evidence.md",
    "docs/evals/home_assistant_model_provider_health_diagnostics_scaffold.yaml",
    "tests/test_model_provider_health_diagnostics_anchor.py",
    "evals/home_assistant_model_provider_health_diagnostics_scaffold.py",
    "src/Isolinear/model_provider_health_diagnostics_anchor.py",
]

MODEL_PROVIDER_HEALTH_FORBIDDEN_SIDE_EFFECT_KEYS = [
    "model_provider_planning_called",
    "model_provider_retry_policy_written",
    "worker_called",
    "worker_health_check_called",
    "home_assistant_history_read",
    "semantic_memory_called",
    "home_assistant_service_or_state_mutation_called",
    "token_generated",
    "token_rotation_called",
    "chart_rendering_called",
    "chart_artifact_written",
    "durable_storage_written",
    "durable_retry_storage_written",
    "retry_behavior_called",
    "scheduler_called",
    "automatic_retry_called",
    "automatic_progress_task_called",
    "new_provider_transport_added",
    "provider_details_leaked_to_card",
]


class FakeProviderHealthClient:
    provider_type = "ollama_compatible"
    role = "planner"

    def __init__(
        self,
        *,
        endpoint_url: str = PROVIDER_ENDPOINT_A,
        planner_model: str = PLANNER_MODEL_A,
        response: dict[str, Any],
    ) -> None:
        self.endpoint_url = endpoint_url.rstrip("/")
        self.planner_model = planner_model
        self.response = deepcopy(response)
        self.health_calls = 0
        self.plan_calls = 0
        self.received_health_requests: list[dict[str, Any]] = []

    def provider_metadata(self) -> dict[str, str]:
        return {
            "type": self.provider_type,
            "role": self.role,
            "endpoint_url": self.endpoint_url,
            "model": self.planner_model,
        }

    def check_health(self, health_request: dict[str, Any]) -> dict[str, Any]:
        self.health_calls += 1
        self.received_health_requests.append(deepcopy(health_request))
        return deepcopy(self.response)

    def plan_chart(self, request: dict[str, Any], *, result_schema: dict[str, Any] | None = None) -> dict[str, Any]:
        self.plan_calls += 1
        return {
            "accepted": False,
            "code": "unexpected_model_provider_planning_call",
            "message": "Provider health diagnostics must not call planner generation.",
            "retry_safe": False,
        }


def verify_model_provider_health_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in MODEL_PROVIDER_HEALTH_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_ready_model_provider_health_probe_records_metadata(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, client, health_setup = _hass_with_fake_provider_health_client(
        "provider-health-ready-entry",
        _accepted_health_response("ready"),
    )

    result = check_model_provider_health(hass, entry.entry_id)
    health = _health(hass, entry.entry_id)
    raw_request = client.received_health_requests[0]

    return {
        "health_setup": health_setup,
        "result": result,
        "health": health,
        "health_validation": _validate_health(health, root),
        "request_validation": _validate_health_request(raw_request, root),
        "health_call_count": client.health_calls,
        "plan_call_count": client.plan_calls,
        "stored_provider_endpoint": health["provider"]["endpoint_url"],
        "stored_provider_model": health["provider"]["model"],
    }


def verify_not_ready_model_provider_health_response_records_internal_state(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, client, health_setup = _hass_with_fake_provider_health_client(
        "provider-health-not-ready-entry",
        _accepted_health_response("not_ready", planning=False),
    )
    planner_before = _entry_data(hass, entry.entry_id).get(DATA_MODEL_PROVIDER_PLANNER)

    result = check_model_provider_health(hass, entry.entry_id)
    health = _health(hass, entry.entry_id)
    planner_after = _entry_data(hass, entry.entry_id).get(DATA_MODEL_PROVIDER_PLANNER)

    return {
        "health_setup": health_setup,
        "result": result,
        "health": health,
        "health_validation": _validate_health(health, root),
        "planner_client_unchanged": planner_before is planner_after,
        "planner_client_present": planner_after is client,
        "health_call_count": client.health_calls,
        "plan_call_count": client.plan_calls,
    }


def verify_model_provider_transport_failure_records_unavailable(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, client, _health_setup = _hass_with_fake_provider_health_client(
        "provider-health-unavailable-entry",
        {
            "accepted": False,
            "code": "model_provider_health_connection_error",
            "message": "Connection refused by provider health endpoint.",
            "retry_safe": True,
        },
    )

    result = check_model_provider_health(hass, entry.entry_id)
    health = _health(hass, entry.entry_id)

    return {
        "result": result,
        "health": health,
        "health_validation": _validate_health(health, root),
        "health_call_count": client.health_calls,
        "plan_call_count": client.plan_calls,
        "retry_or_scheduler_side_effects": {
            "retry_behavior_called": health["orchestration"]["retry_behavior_called"],
            "scheduler_called": health["orchestration"]["scheduler_called"],
            "automatic_retry_called": health["orchestration"]["automatic_retry_called"],
            "durable_retry_storage_written": health["orchestration"]["durable_retry_storage_written"],
            "model_provider_retry_policy_written": health["orchestration"]["model_provider_retry_policy_written"],
        },
    }


def verify_malformed_model_provider_health_response_rejected_before_storage(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, client, _health_setup = _hass_with_fake_provider_health_client(
        "provider-health-malformed-entry",
        {
            "accepted": True,
            "code": "model_provider_health_result_received",
            "health_result": {
                "version": 1,
                "status": "surprising",
                "code": "model_provider_health_ready",
                "message": "Unexpected status.",
                "checks": [],
                "capabilities": {"planning": True, "structured_output": True},
            },
        },
    )

    result = check_model_provider_health(hass, entry.entry_id)
    entry_data = _entry_data(hass, entry.entry_id)
    return {
        "result": result,
        "health_call_count": client.health_calls,
        "plan_call_count": client.plan_calls,
        "health_written": DATA_MODEL_PROVIDER_HEALTH in entry_data,
        "health_validation": _validate_health(entry_data.get(DATA_MODEL_PROVIDER_HEALTH), root)
        if DATA_MODEL_PROVIDER_HEALTH in entry_data
        else {"accepted": False, "code": "not_written"},
    }


def verify_secret_model_provider_health_response_rejected_before_storage(root=None) -> dict[str, Any]:
    root = root or repo_root()
    secret_text = "Bearer super-secret-provider-token"
    hass, entry, client, _health_setup = _hass_with_fake_provider_health_client(
        "provider-health-secret-entry",
        _accepted_health_response("ready", message=secret_text),
    )

    result = check_model_provider_health(hass, entry.entry_id)
    entry_data = _entry_data(hass, entry.entry_id)
    visible_payload = {"result": result, "setup": entry_data.get(DATA_MODEL_PROVIDER_HEALTH_SETUP)}
    return {
        "result": result,
        "health_call_count": client.health_calls,
        "plan_call_count": client.plan_calls,
        "health_written": DATA_MODEL_PROVIDER_HEALTH in entry_data,
        "secret_absent_from_result": secret_text not in str(visible_payload),
    }


def verify_unconfigured_model_provider_health_rejected_before_call() -> dict[str, Any]:
    entry = FakeConfigEntry(
        "provider-health-unconfigured-entry",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    hass = _setup_provider_hass(entry)
    result = check_model_provider_health(hass, entry.entry_id)
    entry_data = _entry_data(hass, entry.entry_id)
    return {
        "result": result,
        "health_setup": deepcopy(entry_data[DATA_MODEL_PROVIDER_HEALTH_SETUP]),
        "health_written": DATA_MODEL_PROVIDER_HEALTH in entry_data,
        "planner_client_present": DATA_MODEL_PROVIDER_PLANNER in entry_data,
    }


def verify_unknown_model_provider_health_config_entry_rejected_before_call() -> dict[str, Any]:
    hass = _fake_hass(FakeWebSocketApiModule())
    result = check_model_provider_health(hass, "missing-provider-health-entry")
    domain_data = hass.data.get(DOMAIN, {})
    return {
        "result": result,
        "entry_created": "missing-provider-health-entry" in domain_data,
        "health_written": (
            isinstance(domain_data.get("missing-provider-health-entry"), dict)
            and DATA_MODEL_PROVIDER_HEALTH in domain_data["missing-provider-health-entry"]
        ),
    }


def verify_model_provider_health_stays_config_entry_scoped(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry_a, client_a, _setup_a = _hass_with_fake_provider_health_client(
        "provider-health-isolation-entry-a",
        _accepted_health_response("ready"),
        endpoint_url=PROVIDER_ENDPOINT_A,
        planner_model=PLANNER_MODEL_A,
    )
    entry_b = FakeConfigEntry(
        "provider-health-isolation-entry-b",
        data={
            "model_provider_type": "ollama_compatible",
            "model_endpoint_url": PROVIDER_ENDPOINT_B,
            "planner_model": PLANNER_MODEL_B,
        },
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    _setup_entry_in_hass(hass, entry_b)
    client_b = FakeProviderHealthClient(
        endpoint_url=PROVIDER_ENDPOINT_B,
        planner_model=PLANNER_MODEL_B,
        response=_accepted_health_response("not_ready", planning=False),
    )
    _entry_data(hass, entry_b.entry_id)[DATA_MODEL_PROVIDER_PLANNER] = client_b
    setup_b = setup_model_provider_health(hass, entry_b)

    result_a = check_model_provider_health(hass, entry_a.entry_id)
    result_b = check_model_provider_health(hass, entry_b.entry_id)
    health_a = _health(hass, entry_a.entry_id)
    health_b = _health(hass, entry_b.entry_id)

    return {
        "entry_a": {
            "result": result_a,
            "health": health_a,
            "health_validation": _validate_health(health_a, root),
            "health_call_count": client_a.health_calls,
            "plan_call_count": client_a.plan_calls,
            "request": deepcopy(client_a.received_health_requests[0]),
            "stored_endpoint": health_a["provider"]["endpoint_url"],
            "other_endpoint_absent": PROVIDER_ENDPOINT_B not in str(health_a),
        },
        "entry_b": {
            "setup": setup_b,
            "result": result_b,
            "health": health_b,
            "health_validation": _validate_health(health_b, root),
            "health_call_count": client_b.health_calls,
            "plan_call_count": client_b.plan_calls,
            "request": deepcopy(client_b.received_health_requests[0]),
            "stored_endpoint": health_b["provider"]["endpoint_url"],
            "other_endpoint_absent": PROVIDER_ENDPOINT_A not in str(health_b),
        },
    }


def verify_model_provider_health_details_do_not_leak_to_card(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, _client, health_setup = _hass_with_fake_provider_health_client(
        "provider-health-leak-entry",
        _accepted_health_response("ready"),
    )
    result = check_model_provider_health(hass, entry.entry_id)
    entry_data = _entry_data(hass, entry.entry_id)
    health = _health(hass, entry.entry_id)
    dashboard_metadata = entry_data["websocket_api"]
    worker_metadata = entry_data["worker_health_setup"]
    dashboard_visible_payload = {
        "websocket_api": dashboard_metadata,
        "card_snapshot_payload": {
            "accepted": True,
            "code": "no_card_provider_health_command",
            "health": None,
        },
    }
    evidence_payload = {
        "result": result,
        "health": health,
        "health_setup": health_setup,
    }

    return {
        "health_validation": _validate_health(health, root),
        "endpoint_absent_from_dashboard_payload": PROVIDER_ENDPOINT_A not in str(dashboard_visible_payload),
        "request_absent_from_dashboard_payload": "request" not in str(dashboard_visible_payload),
        "health_absent_from_dashboard_payload": "isolinear_model_provider_health" not in str(dashboard_visible_payload),
        "response_absent_from_dashboard_payload": "health_result" not in str(dashboard_visible_payload),
        "provider_endpoint_internal_only": PROVIDER_ENDPOINT_A in str(health),
        "endpoint_absent_from_worker_metadata": PROVIDER_ENDPOINT_A not in str(worker_metadata),
        "evidence_contains_internal_health": "isolinear_model_provider_health" in str(evidence_payload),
    }


def verify_model_provider_health_side_effect_boundaries() -> dict[str, Any]:
    ready = verify_ready_model_provider_health_probe_records_metadata()
    not_ready = verify_not_ready_model_provider_health_response_records_internal_state()
    unavailable = verify_model_provider_transport_failure_records_unavailable()
    malformed = verify_malformed_model_provider_health_response_rejected_before_storage()
    secret = verify_secret_model_provider_health_response_rejected_before_storage()
    unconfigured = verify_unconfigured_model_provider_health_rejected_before_call()
    unknown = verify_unknown_model_provider_health_config_entry_rejected_before_call()
    isolation = verify_model_provider_health_stays_config_entry_scoped()

    observed = [
        {"name": "ready_health", **ready["health"]["orchestration"]},
        {"name": "not_ready_health", **not_ready["health"]["orchestration"]},
        {"name": "unavailable_health", **unavailable["health"]["orchestration"]},
        {"name": "malformed_rejection", **malformed["result"]["orchestration"]},
        {"name": "secret_rejection", **secret["result"]["orchestration"]},
        {"name": "unconfigured_rejection", **unconfigured["result"]["orchestration"]},
        {"name": "unknown_rejection", **unknown["result"]["orchestration"]},
        {"name": "isolation_entry_a", **isolation["entry_a"]["health"]["orchestration"]},
        {"name": "isolation_entry_b", **isolation["entry_b"]["health"]["orchestration"]},
    ]
    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in MODEL_PROVIDER_HEALTH_FORBIDDEN_SIDE_EFFECT_KEYS
    }
    allowed_aggregate = {
        "model_provider_health_check_called": any(
            item.get("model_provider_health_check_called") for item in observed
        ),
        "model_provider_health_bookkeeping_written": any(
            item.get("model_provider_health_bookkeeping_written") for item in observed
        ),
        "model_provider_health_request_validated": any(
            item.get("model_provider_health_request_validated") for item in observed
        ),
        "model_provider_health_response_validated": any(
            item.get("model_provider_health_response_validated") for item in observed
        ),
    }
    return {
        "expected_forbidden": {key: False for key in MODEL_PROVIDER_HEALTH_FORBIDDEN_SIDE_EFFECT_KEYS},
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }


def verify_model_provider_health_diagnostics_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_model_provider_health_files(root)
    ready = verify_ready_model_provider_health_probe_records_metadata(root)
    not_ready = verify_not_ready_model_provider_health_response_records_internal_state(root)
    unavailable = verify_model_provider_transport_failure_records_unavailable(root)
    malformed = verify_malformed_model_provider_health_response_rejected_before_storage(root)
    secret = verify_secret_model_provider_health_response_rejected_before_storage(root)
    unconfigured = verify_unconfigured_model_provider_health_rejected_before_call()
    unknown = verify_unknown_model_provider_health_config_entry_rejected_before_call()
    isolation = verify_model_provider_health_stays_config_entry_scoped(root)
    leakage = verify_model_provider_health_details_do_not_leak_to_card(root)
    side_effects = verify_model_provider_health_side_effect_boundaries()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more model-provider health scaffold files are missing.")
    if ready["health"]["status"] != "ready" or not ready["health_validation"]["accepted"]:
        failures.append("Ready provider health probe did not store schema-valid ready metadata.")
    if not ready["request_validation"]["accepted"]:
        failures.append("Ready provider health request did not validate before provider call.")
    if ready["health_call_count"] != 1 or ready["plan_call_count"] != 0:
        failures.append("Ready provider health probe did not make one health call and zero planning calls.")
    if not_ready["health"]["status"] != "not_ready" or not not_ready["planner_client_unchanged"]:
        failures.append("Not-ready provider health response changed planner setup or stored the wrong status.")
    if unavailable["health"]["status"] != "unavailable" or not unavailable["health_validation"]["accepted"]:
        failures.append("Transport failure did not store schema-valid unavailable provider health metadata.")
    if any(unavailable["retry_or_scheduler_side_effects"].values()):
        failures.append("Unavailable provider health metadata reported retry or scheduler side effects.")
    if malformed["result"]["code"] != "invalid_model_provider_health_response" or malformed["health_written"]:
        failures.append("Malformed accepted provider health response did not fail before storage.")
    if secret["result"]["code"] != "invalid_model_provider_health_response" or secret["health_written"]:
        failures.append("Secret-bearing accepted provider health response did not fail before storage.")
    if not secret["secret_absent_from_result"]:
        failures.append("Secret-bearing provider health response leaked into visible result data.")
    if unconfigured["result"]["code"] != "model_provider_health_not_configured" or unconfigured["health_written"]:
        failures.append("Unconfigured provider entry did not fail before health metadata storage.")
    if unknown["result"]["code"] != "unknown_config_entry" or unknown["entry_created"]:
        failures.append("Unknown config entry created provider health state.")
    if isolation["entry_a"]["health"]["config_entry_id"] == isolation["entry_b"]["health"]["config_entry_id"]:
        failures.append("Provider health metadata did not stay config-entry scoped.")
    if not isolation["entry_a"]["other_endpoint_absent"] or not isolation["entry_b"]["other_endpoint_absent"]:
        failures.append("Provider health metadata mixed another config entry's endpoint.")
    if not all(
        leakage[key]
        for key in (
            "endpoint_absent_from_dashboard_payload",
            "request_absent_from_dashboard_payload",
            "health_absent_from_dashboard_payload",
            "response_absent_from_dashboard_payload",
            "endpoint_absent_from_worker_metadata",
        )
    ):
        failures.append("Provider health details leaked to dashboard-facing or worker metadata payloads.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("Model-provider health scaffold reported forbidden side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("Model-provider health scaffold did not report expected allowed side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "ready": ready,
        "not_ready": not_ready,
        "unavailable": unavailable,
        "malformed": malformed,
        "secret": secret,
        "unconfigured": unconfigured,
        "unknown": unknown,
        "isolation": isolation,
        "leakage": leakage,
        "side_effects": side_effects,
    }


def _hass_with_fake_provider_health_client(
    entry_id: str,
    response: dict[str, Any],
    *,
    endpoint_url: str = PROVIDER_ENDPOINT_A,
    planner_model: str = PLANNER_MODEL_A,
) -> tuple[Any, Any, FakeProviderHealthClient, dict[str, Any]]:
    entry = FakeConfigEntry(
        entry_id,
        data={
            "model_provider_type": "ollama_compatible",
            "model_endpoint_url": endpoint_url,
            "planner_model": planner_model,
        },
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    hass = _setup_provider_hass(entry)
    client = FakeProviderHealthClient(
        endpoint_url=endpoint_url,
        planner_model=planner_model,
        response=response,
    )
    _entry_data(hass, entry.entry_id)[DATA_MODEL_PROVIDER_PLANNER] = client
    health_setup = setup_model_provider_health(hass, entry)
    return hass, entry, client, health_setup


def _setup_provider_hass(entry: FakeConfigEntry) -> Any:
    hass = _fake_hass(FakeWebSocketApiModule())
    _setup_entry_in_hass(hass, entry)
    return hass


def _setup_entry_in_hass(hass: Any, entry: FakeConfigEntry) -> None:
    from custom_components.isolinear import async_setup_entry

    setup_accepted = _run(async_setup_entry(hass, entry))
    if not setup_accepted:
        raise AssertionError(f"async_setup_entry rejected {entry.entry_id}")


def _accepted_health_response(
    status: str,
    *,
    message: str | None = None,
    planning: bool = True,
) -> dict[str, Any]:
    return {
        "accepted": True,
        "code": "model_provider_health_result_received",
        "health_result": {
            "version": 1,
            "status": status,
            "code": f"model_provider_health_{status}",
            "message": message or f"Model-provider health endpoint reports {status}.",
            "checks": [
                {"name": "ollama_tags_endpoint", "status": "pass"},
                {"name": "planner_model", "status": "pass" if planning else "not_ready"},
            ],
            "capabilities": {
                "planning": planning,
                "structured_output": planning,
            },
        },
    }


def _entry_data(hass: Any, entry_id: str) -> dict[str, Any]:
    return hass.data[DOMAIN][entry_id]


def _health(hass: Any, entry_id: str) -> dict[str, Any]:
    return deepcopy(_entry_data(hass, entry_id)[DATA_MODEL_PROVIDER_HEALTH])


def _validate_health(health: Any, root) -> dict[str, Any]:
    try:
        validate_contract("integration-model-provider-health", health, repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "contract_validation_failed",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "health_id": health["health_id"],
        "config_entry_id": health["config_entry_id"],
        "status": health["status"],
        "health_path": health["provider"]["health_path"],
    }


def _validate_health_request(request: Any, root) -> dict[str, Any]:
    try:
        validate_contract("model-provider-health-request", request, repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "contract_validation_failed",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "method": request["method"],
        "path": request["path"],
        "uses_health_path": request["path"] == "/api/tags",
    }
