from __future__ import annotations

from copy import deepcopy
from typing import Any

from custom_components.isolinear.const import DOMAIN
from custom_components.isolinear.worker_health import (
    DATA_WORKER_HEALTH,
    DATA_WORKER_HEALTH_SETUP,
    check_worker_health,
    setup_worker_health,
)
from custom_components.isolinear.worker_readiness import provision_integration_worker_token
from custom_components.isolinear.worker_renderer import (
    DATA_WORKER_RENDER_CLIENT,
    DATA_WORKER_RENDER_TOKEN,
    WORKER_HEALTH_PATH,
)

from .contracts import ContractValidationError, validate_contract
from .dashboard_card_anchor import repo_root
from .job_orchestration_scaffold_anchor import _fake_hass
from .websocket_command_registration_anchor import FakeWebSocketApiModule
from .worker_token_provisioning_readiness_anchor import (
    WORKER_ENDPOINT_URL,
    WORKER_READINESS_SECOND_TOKEN,
    WORKER_READINESS_TEST_TOKEN,
    CountingTokenFactory,
    _entry_data,
    _setup_readiness_hass,
    _worker_entry,
)


WORKER_HEALTH_FILES = [
    "custom_components/isolinear/worker_health.py",
    "custom_components/isolinear/worker_renderer.py",
    "custom_components/isolinear/__init__.py",
    "docs/schemas/worker-health-request.schema.json",
    "docs/schemas/integration-worker-health.schema.json",
    "docs/specs/home-assistant-worker-health-readiness-endpoint-scaffold-spec.md",
    "bdd/integration/home-assistant-worker-health-readiness-endpoint-scaffold-bdd.md",
    "bdd/integration/home-assistant-worker-health-readiness-endpoint-scaffold-evidence.md",
    "docs/evals/home_assistant_worker_health_readiness_endpoint_scaffold.yaml",
    "tests/test_worker_health_readiness_endpoint_anchor.py",
    "evals/home_assistant_worker_health_readiness_endpoint_scaffold.py",
    "src/Isolinear/worker_health_readiness_endpoint_anchor.py",
]

WORKER_HEALTH_FORBIDDEN_SIDE_EFFECT_KEYS = [
    "home_assistant_history_read",
    "semantic_memory_called",
    "home_assistant_service_or_state_mutation_called",
    "token_generated",
    "token_rotation_called",
    "worker_render_called",
    "chart_rendering_called",
    "chart_artifact_written",
    "durable_storage_written",
    "durable_retry_storage_written",
    "retry_behavior_called",
    "scheduler_called",
    "automatic_retry_called",
    "automatic_progress_task_called",
    "new_worker_transport_added",
    "token_leaked_to_card",
    "token_leaked_to_model_provider",
]


class FakeWorkerHealthClient:
    provider_type = "http_json_worker"
    role = "renderer"
    api_version = 1

    def __init__(
        self,
        *,
        endpoint_url: str,
        worker_token: str,
        response: dict[str, Any],
    ) -> None:
        self.endpoint_url = endpoint_url.rstrip("/")
        self.worker_token = worker_token
        self.response = response
        self.health_calls = 0
        self.render_calls = 0
        self.received_health_requests: list[dict[str, Any]] = []

    def provider_metadata(self) -> dict[str, Any]:
        return {
            "type": self.provider_type,
            "role": self.role,
            "endpoint_url": self.endpoint_url,
            "api_version": self.api_version,
        }

    def check_health(self, health_request: dict[str, Any]) -> dict[str, Any]:
        self.health_calls += 1
        self.received_health_requests.append(deepcopy(health_request))
        return deepcopy(self.response)

    def render_chart(self, transport_request: dict[str, Any]) -> dict[str, Any]:
        self.render_calls += 1
        return {
            "accepted": False,
            "code": "unexpected_worker_render_call",
            "message": "Health checks must not call worker render.",
        }


def verify_worker_health_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in WORKER_HEALTH_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_ready_worker_health_probe_records_redacted_metadata(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, client, provision, health_setup = _ready_hass_with_fake_health_client(
        "worker-health-ready-entry",
        _accepted_health_response("ready"),
    )

    result = check_worker_health(hass, entry.entry_id)
    health = _health(hass, entry.entry_id)
    raw_request = client.received_health_requests[0]

    return {
        "provision": provision,
        "health_setup": health_setup,
        "result": result,
        "health": health,
        "health_validation": _validate_health(health, root),
        "request_validation": _validate_health_request(raw_request, root),
        "raw_request_authorization_present": raw_request["headers"]["authorization"].startswith("Bearer "),
        "raw_request_uses_worker_token": raw_request["headers"]["authorization"] == f"Bearer {WORKER_READINESS_TEST_TOKEN}",
        "stored_authorization": health["request"]["headers"]["authorization"],
        "health_call_count": client.health_calls,
        "render_call_count": client.render_calls,
        "raw_token_stored": _entry_data(hass, entry.entry_id).get(DATA_WORKER_RENDER_TOKEN)
        == WORKER_READINESS_TEST_TOKEN,
    }


def verify_not_ready_worker_health_response_records_internal_state(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, client, _provision, health_setup = _ready_hass_with_fake_health_client(
        "worker-health-not-ready-entry",
        _accepted_health_response("not_ready", rendering=False),
    )
    renderer_client_before = _entry_data(hass, entry.entry_id).get(DATA_WORKER_RENDER_CLIENT)

    result = check_worker_health(hass, entry.entry_id)
    health = _health(hass, entry.entry_id)
    renderer_client_after = _entry_data(hass, entry.entry_id).get(DATA_WORKER_RENDER_CLIENT)

    return {
        "health_setup": health_setup,
        "result": result,
        "health": health,
        "health_validation": _validate_health(health, root),
        "renderer_client_unchanged": renderer_client_before is renderer_client_after,
        "renderer_client_present": renderer_client_after is client,
        "health_call_count": client.health_calls,
        "render_call_count": client.render_calls,
    }


def verify_worker_health_transport_failure_records_unavailable(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, client, _provision, _health_setup = _ready_hass_with_fake_health_client(
        "worker-health-unavailable-entry",
        {
            "accepted": False,
            "code": "worker_connection_error",
            "message": "Connection refused by worker health endpoint.",
            "retry_safe": True,
        },
    )

    result = check_worker_health(hass, entry.entry_id)
    health = _health(hass, entry.entry_id)

    return {
        "result": result,
        "health": health,
        "health_validation": _validate_health(health, root),
        "health_call_count": client.health_calls,
        "render_call_count": client.render_calls,
        "retry_or_scheduler_side_effects": {
            "retry_behavior_called": health["orchestration"]["retry_behavior_called"],
            "scheduler_called": health["orchestration"]["scheduler_called"],
            "automatic_retry_called": health["orchestration"]["automatic_retry_called"],
            "durable_retry_storage_written": health["orchestration"]["durable_retry_storage_written"],
        },
    }


def verify_malformed_worker_health_response_rejected_before_storage(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass, entry, client, _provision, _health_setup = _ready_hass_with_fake_health_client(
        "worker-health-malformed-entry",
        {
            "accepted": True,
            "code": "worker_health_result_received",
            "health_result": {
                "version": 1,
                "status": "surprising",
                "code": "worker_health_ready",
                "message": "Unexpected status.",
                "checks": [],
                "capabilities": {"rendering": True},
            },
        },
    )

    result = check_worker_health(hass, entry.entry_id)
    entry_data = _entry_data(hass, entry.entry_id)
    return {
        "result": result,
        "health_call_count": client.health_calls,
        "render_call_count": client.render_calls,
        "health_written": DATA_WORKER_HEALTH in entry_data,
        "health_validation": _validate_health(entry_data.get(DATA_WORKER_HEALTH), root)
        if DATA_WORKER_HEALTH in entry_data
        else {"accepted": False, "code": "not_written"},
    }


def verify_no_token_worker_health_rejected_before_call() -> dict[str, Any]:
    entry = _worker_entry("worker-health-no-token-entry")
    hass = _setup_readiness_hass(entry)
    result = check_worker_health(hass, entry.entry_id)
    entry_data = _entry_data(hass, entry.entry_id)
    return {
        "result": result,
        "health_setup": deepcopy(entry_data[DATA_WORKER_HEALTH_SETUP]),
        "health_written": DATA_WORKER_HEALTH in entry_data,
        "worker_client_present": DATA_WORKER_RENDER_CLIENT in entry_data,
    }


def verify_unknown_worker_health_config_entry_rejected_before_call() -> dict[str, Any]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    result = check_worker_health(hass, "missing-worker-health-entry")
    domain_data = hass.data.get(DOMAIN, {})
    return {
        "result": result,
        "entry_created": "missing-worker-health-entry" in domain_data,
        "health_written": (
            isinstance(domain_data.get("missing-worker-health-entry"), dict)
            and DATA_WORKER_HEALTH in domain_data["missing-worker-health-entry"]
        ),
    }


def verify_worker_health_stays_config_entry_scoped(root=None) -> dict[str, Any]:
    root = root or repo_root()
    hass_a, entry_a, client_a, _provision_a, _setup_a = _ready_hass_with_fake_health_client(
        "worker-health-isolation-entry-a",
        _accepted_health_response("ready"),
        token=WORKER_READINESS_TEST_TOKEN,
    )
    hass = hass_a
    entry_b = _worker_entry("worker-health-isolation-entry-b")
    _setup_entry_in_hass(hass, entry_b)
    provision_b = provision_integration_worker_token(
        hass,
        entry_b.entry_id,
        token_factory=CountingTokenFactory(WORKER_READINESS_SECOND_TOKEN),
    )
    client_b = FakeWorkerHealthClient(
        endpoint_url=WORKER_ENDPOINT_URL,
        worker_token=WORKER_READINESS_SECOND_TOKEN,
        response=_accepted_health_response("not_ready", rendering=False),
    )
    _entry_data(hass, entry_b.entry_id)[DATA_WORKER_RENDER_CLIENT] = client_b
    setup_b = setup_worker_health(hass, entry_b)

    result_a = check_worker_health(hass, entry_a.entry_id)
    result_b = check_worker_health(hass, entry_b.entry_id)
    health_a = _health(hass, entry_a.entry_id)
    health_b = _health(hass, entry_b.entry_id)

    return {
        "entry_a": {
            "result": result_a,
            "health": health_a,
            "health_validation": _validate_health(health_a, root),
            "health_call_count": client_a.health_calls,
            "raw_request_authorization_present": (
                client_a.received_health_requests[0]["headers"]["authorization"].startswith("Bearer ")
            ),
            "raw_request_uses_own_token": (
                client_a.received_health_requests[0]["headers"]["authorization"]
                == f"Bearer {WORKER_READINESS_TEST_TOKEN}"
            ),
            "other_token_absent_from_request": WORKER_READINESS_SECOND_TOKEN
            not in str(client_a.received_health_requests[0]),
        },
        "entry_b": {
            "provision": provision_b,
            "setup": setup_b,
            "result": result_b,
            "health": health_b,
            "health_validation": _validate_health(health_b, root),
            "health_call_count": client_b.health_calls,
            "raw_request_authorization_present": (
                client_b.received_health_requests[0]["headers"]["authorization"].startswith("Bearer ")
            ),
            "raw_request_uses_own_token": (
                client_b.received_health_requests[0]["headers"]["authorization"]
                == f"Bearer {WORKER_READINESS_SECOND_TOKEN}"
            ),
            "other_token_absent_from_request": WORKER_READINESS_TEST_TOKEN
            not in str(client_b.received_health_requests[0]),
        },
    }


def verify_worker_health_details_do_not_leak_to_card(root=None) -> dict[str, Any]:
    root = root or repo_root()
    secret_message = f"Bearer {WORKER_READINESS_TEST_TOKEN} should never leak"
    hass, entry, client, _provision, health_setup = _ready_hass_with_fake_health_client(
        "worker-health-leak-entry",
        _accepted_health_response("ready", message=secret_message),
    )
    result = check_worker_health(hass, entry.entry_id)
    entry_data = _entry_data(hass, entry.entry_id)
    health = _health(hass, entry.entry_id)
    dashboard_metadata = entry_data["websocket_api"]
    model_provider_metadata = entry_data["model_provider_setup"]
    dashboard_visible_payload = {
        "websocket_api": dashboard_metadata,
        "card_snapshot_payload": {
            "accepted": True,
            "code": "no_card_health_command",
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
        "health_message": health["response"]["message"],
        "raw_worker_authorization_received": client.received_health_requests[0]["headers"]["authorization"].startswith(
            "Bearer "
        ),
        "stored_authorization": health["request"]["headers"]["authorization"],
        "token_absent_from_health": WORKER_READINESS_TEST_TOKEN not in str(health),
        "token_absent_from_setup": WORKER_READINESS_TEST_TOKEN not in str(health_setup),
        "token_absent_from_evidence_payload": WORKER_READINESS_TEST_TOKEN not in str(evidence_payload),
        "token_absent_from_dashboard_card_metadata": WORKER_READINESS_TEST_TOKEN not in str(dashboard_metadata),
        "token_absent_from_model_provider_metadata": WORKER_READINESS_TEST_TOKEN not in str(model_provider_metadata),
        "endpoint_absent_from_dashboard_payload": WORKER_ENDPOINT_URL not in str(dashboard_visible_payload),
        "request_absent_from_dashboard_payload": "request" not in str(dashboard_visible_payload),
        "health_absent_from_dashboard_payload": "isolinear_worker_health" not in str(dashboard_visible_payload),
    }


def verify_worker_health_side_effect_boundaries() -> dict[str, Any]:
    ready = verify_ready_worker_health_probe_records_redacted_metadata()
    not_ready = verify_not_ready_worker_health_response_records_internal_state()
    unavailable = verify_worker_health_transport_failure_records_unavailable()
    malformed = verify_malformed_worker_health_response_rejected_before_storage()
    no_token = verify_no_token_worker_health_rejected_before_call()
    unknown = verify_unknown_worker_health_config_entry_rejected_before_call()
    isolation = verify_worker_health_stays_config_entry_scoped()

    observed = [
        {"name": "ready_health", **ready["health"]["orchestration"]},
        {"name": "not_ready_health", **not_ready["health"]["orchestration"]},
        {"name": "unavailable_health", **unavailable["health"]["orchestration"]},
        {"name": "malformed_rejection", **malformed["result"]["orchestration"]},
        {"name": "no_token_rejection", **no_token["result"]["orchestration"]},
        {"name": "unknown_rejection", **unknown["result"]["orchestration"]},
        {"name": "isolation_entry_a", **isolation["entry_a"]["health"]["orchestration"]},
        {"name": "isolation_entry_b", **isolation["entry_b"]["health"]["orchestration"]},
    ]
    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in WORKER_HEALTH_FORBIDDEN_SIDE_EFFECT_KEYS
    }
    allowed_aggregate = {
        "worker_health_check_called": any(item.get("worker_health_check_called") for item in observed),
        "worker_health_bookkeeping_written": any(
            item.get("worker_health_bookkeeping_written") for item in observed
        ),
        "worker_health_request_validated": any(
            item.get("worker_health_request_validated") for item in observed
        ),
        "worker_health_response_validated": any(
            item.get("worker_health_response_validated") for item in observed
        ),
    }
    return {
        "expected_forbidden": {key: False for key in WORKER_HEALTH_FORBIDDEN_SIDE_EFFECT_KEYS},
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }


def verify_worker_health_readiness_endpoint_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_worker_health_files(root)
    ready = verify_ready_worker_health_probe_records_redacted_metadata(root)
    not_ready = verify_not_ready_worker_health_response_records_internal_state(root)
    unavailable = verify_worker_health_transport_failure_records_unavailable(root)
    malformed = verify_malformed_worker_health_response_rejected_before_storage(root)
    no_token = verify_no_token_worker_health_rejected_before_call()
    unknown = verify_unknown_worker_health_config_entry_rejected_before_call()
    isolation = verify_worker_health_stays_config_entry_scoped(root)
    leakage = verify_worker_health_details_do_not_leak_to_card(root)
    side_effects = verify_worker_health_side_effect_boundaries()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more worker health scaffold files are missing.")
    if ready["health"]["status"] != "ready" or not ready["health_validation"]["accepted"]:
        failures.append("Ready health probe did not store schema-valid ready health metadata.")
    if ready["stored_authorization"] != "Bearer <redacted>":
        failures.append("Ready health metadata did not redact worker authorization.")
    if not ready["request_validation"]["accepted"]:
        failures.append("Ready health request did not validate before worker call.")
    if ready["health_call_count"] != 1 or ready["render_call_count"] != 0:
        failures.append("Ready health probe did not make exactly one health call and zero render calls.")
    if not_ready["health"]["status"] != "not_ready" or not not_ready["renderer_client_unchanged"]:
        failures.append("Not-ready health response changed renderer setup or stored the wrong status.")
    if unavailable["health"]["status"] != "unavailable" or not unavailable["health_validation"]["accepted"]:
        failures.append("Transport failure did not store schema-valid unavailable health metadata.")
    if any(unavailable["retry_or_scheduler_side_effects"].values()):
        failures.append("Unavailable health metadata reported retry or scheduler side effects.")
    if malformed["result"]["code"] != "invalid_worker_health_response" or malformed["health_written"]:
        failures.append("Malformed accepted health response did not fail before health metadata storage.")
    if no_token["result"]["code"] != "worker_health_not_ready" or no_token["health_written"]:
        failures.append("No-token entry did not fail before health metadata storage.")
    if unknown["result"]["code"] != "unknown_config_entry" or unknown["entry_created"]:
        failures.append("Unknown config entry created health state.")
    if isolation["entry_a"]["health"]["config_entry_id"] == isolation["entry_b"]["health"]["config_entry_id"]:
        failures.append("Health metadata did not stay config-entry scoped.")
    if not isolation["entry_a"]["other_token_absent_from_request"] or not isolation["entry_b"]["other_token_absent_from_request"]:
        failures.append("A worker health request included another config entry's token.")
    if not all(
        leakage[key]
        for key in (
            "token_absent_from_health",
            "token_absent_from_setup",
            "token_absent_from_evidence_payload",
            "token_absent_from_dashboard_card_metadata",
            "token_absent_from_model_provider_metadata",
            "endpoint_absent_from_dashboard_payload",
            "request_absent_from_dashboard_payload",
            "health_absent_from_dashboard_payload",
        )
    ):
        failures.append("Worker health details leaked to evidence or dashboard-facing payloads.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("Worker health scaffold reported forbidden side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("Worker health scaffold did not report expected allowed side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "ready": ready,
        "not_ready": not_ready,
        "unavailable": unavailable,
        "malformed": malformed,
        "no_token": no_token,
        "unknown": unknown,
        "isolation": isolation,
        "leakage": leakage,
        "side_effects": side_effects,
    }


def _ready_hass_with_fake_health_client(
    entry_id: str,
    response: dict[str, Any],
    *,
    token: str = WORKER_READINESS_TEST_TOKEN,
) -> tuple[Any, Any, FakeWorkerHealthClient, dict[str, Any], dict[str, Any]]:
    entry = _worker_entry(entry_id)
    hass = _setup_readiness_hass(entry)
    provision = provision_integration_worker_token(
        hass,
        entry.entry_id,
        token_factory=CountingTokenFactory(token),
    )
    client = FakeWorkerHealthClient(
        endpoint_url=WORKER_ENDPOINT_URL,
        worker_token=token,
        response=response,
    )
    _entry_data(hass, entry.entry_id)[DATA_WORKER_RENDER_CLIENT] = client
    health_setup = setup_worker_health(hass, entry)
    return hass, entry, client, provision, health_setup


def _setup_entry_in_hass(hass: Any, entry: Any) -> None:
    from custom_components.isolinear import async_setup_entry

    from .job_orchestration_scaffold_anchor import _run

    setup_accepted = _run(async_setup_entry(hass, entry))
    if not setup_accepted:
        raise AssertionError(f"async_setup_entry rejected {entry.entry_id}")


def _accepted_health_response(
    status: str,
    *,
    message: str | None = None,
    rendering: bool = True,
) -> dict[str, Any]:
    return {
        "accepted": True,
        "code": "worker_health_result_received",
        "health_result": {
            "version": 1,
            "status": status,
            "code": f"worker_health_{status}",
            "message": message or f"Worker health endpoint reports {status}.",
            "checks": [
                {"name": "worker_process", "status": "pass"},
                {"name": "renderer", "status": "pass" if rendering else "not_ready"},
            ],
            "capabilities": {
                "rendering": rendering,
            },
        },
    }


def _health(hass: Any, entry_id: str) -> dict[str, Any]:
    return deepcopy(_entry_data(hass, entry_id)[DATA_WORKER_HEALTH])


def _validate_health(health: Any, root) -> dict[str, Any]:
    try:
        validate_contract("integration-worker-health", health, repo_root=root)
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
        "authorization": health["request"]["headers"]["authorization"],
        "health_path": health["worker"]["health_path"],
    }


def _validate_health_request(request: Any, root) -> dict[str, Any]:
    try:
        validate_contract("worker-health-request", request, repo_root=root)
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
        "authorization_present": request["headers"]["authorization"].startswith("Bearer "),
        "uses_health_path": request["path"] == WORKER_HEALTH_PATH,
    }
