from __future__ import annotations

from copy import deepcopy
from typing import Any

from custom_components.isolinear import async_setup_entry
from custom_components.isolinear.const import DOMAIN
from custom_components.isolinear.job_orchestration import (
    DATA_JOB_ORCHESTRATION,
    DATA_JOB_ORCHESTRATION_SETUP,
    NO_JOB_ORCHESTRATION_CALLS,
    summarize_job_orchestration_store,
)
from custom_components.isolinear.job_state import summarize_job_state_store
from custom_components.isolinear.model_provider import DATA_MODEL_PROVIDER_PLANNER

from .contracts import ContractValidationError, validate_contract
from .dashboard_card_anchor import repo_root
from .entity_catalog_scaffold_anchor import FakeConfigEntry
from .job_orchestration_artifact_storage_anchor import (
    _artifacts,
    _complete_snapshots,
    _dispatch_snapshot,
    _dispatch_start,
    _error_codes,
    _job,
    _job_store,
)
from .job_orchestration_model_provider_planning_anchor import _provider_plans
from .job_orchestration_render_planning_anchor import _render_plans
from .job_orchestration_scaffold_anchor import _fake_hass, _first_result_payload, _run
from .websocket_command_registration_anchor import FakeWebSocketApiModule


MODEL_PROVIDER_RETRY_BACKOFF_POLICY_FILES = [
    "custom_components/isolinear/job_orchestration.py",
    "custom_components/isolinear/model_provider.py",
    "custom_components/isolinear/websocket_api.py",
    "custom_components/isolinear/__init__.py",
    "docs/specs/home-assistant-model-provider-retry-backoff-policy-scaffold-spec.md",
    "bdd/integration/home-assistant-model-provider-retry-backoff-policy-scaffold-bdd.md",
    "bdd/integration/home-assistant-model-provider-retry-backoff-policy-scaffold-evidence.md",
    "docs/evals/home_assistant_model_provider_retry_backoff_policy_scaffold.yaml",
    "docs/schemas/integration-model-provider-retry-policy.schema.json",
    "tests/test_model_provider_retry_backoff_policy_anchor.py",
    "evals/home_assistant_model_provider_retry_backoff_policy_scaffold.py",
    "src/Isolinear/model_provider_retry_backoff_policy_anchor.py",
]

MODEL_PROVIDER_RETRY_POLICY_FORBIDDEN_SIDE_EFFECT_KEYS = [
    key
    for key in NO_JOB_ORCHESTRATION_CALLS
    if key not in {"model_provider_called", "model_provider_retry_policy_bookkeeping_written"}
] + [
    "home_assistant_history_read",
    "history_retrieval_scaffold_written",
    "subscription_bookkeeping_written",
    "subscription_progress_streaming_called",
    "model_provider_plan_bookkeeping_written",
    "render_plan_bookkeeping_written",
    "artifact_metadata_bookkeeping_written",
    "worker_dispatch_bookkeeping_written",
    "worker_progress_bookkeeping_written",
    "worker_progress_streaming_called",
    "worker_retry_policy_bookkeeping_written",
    "worker_transport_failure_classification_bookkeeping_written",
]


class FakeFailingOllamaPlanner:
    provider_type = "ollama_compatible"
    role = "planner"

    def __init__(
        self,
        failure: dict[str, Any] | None = None,
        *,
        endpoint_url: str = "http://ollama.local:11434",
        planner_model: str = "llama3.1",
    ) -> None:
        self.failure = deepcopy(
            failure
            or {
                "accepted": False,
                "code": "model_provider_connection_error",
                "message": "Planner connection failed before a chart spec was accepted.",
                "retry_safe": True,
            }
        )
        self.endpoint_url = endpoint_url
        self.planner_model = planner_model
        self.calls: list[dict[str, Any]] = []

    def provider_metadata(self) -> dict[str, str]:
        return {
            "type": self.provider_type,
            "role": self.role,
            "endpoint_url": self.endpoint_url,
            "model": self.planner_model,
        }

    def plan_chart(
        self,
        request: dict[str, Any],
        *,
        result_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "request": deepcopy(request),
                "result_schema_title": result_schema.get("title") if isinstance(result_schema, dict) else None,
            }
        )
        failure = deepcopy(self.failure)
        failure.setdefault("provider", self.provider_metadata())
        return failure


def verify_model_provider_retry_policy_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in MODEL_PROVIDER_RETRY_BACKOFF_POLICY_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_provider_failure_records_retry_policy(root=None) -> dict[str, Any]:
    root = root or repo_root()
    planner = FakeFailingOllamaPlanner()
    hass, websocket_api_module = _setup_failing_provider_hass(
        FakeConfigEntry(
            "provider-retry-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        planner,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        "provider-retry-entry",
        "Show sensor.upstairs_temperature",
        1,
    )
    job_id = _first_result_payload(start)["job_id"]
    snapshot = _dispatch_snapshot(hass, websocket_api_module, "provider-retry-entry", job_id, 2)
    policies = _model_provider_retry_policies(hass, "provider-retry-entry")
    job = _job(hass, "provider-retry-entry", job_id)
    card_snapshot = _first_result_payload(snapshot)
    return {
        "start": start,
        "snapshot": snapshot,
        "card_snapshot": _snapshot_summary(card_snapshot),
        "planner_call_count": len(planner.calls),
        "planner_calls": deepcopy(planner.calls),
        "error_codes": _error_codes(snapshot),
        "model_provider_retry_policy": _policy_summary(policies[0]) if policies else None,
        "model_provider_retry_policies": [_policy_summary(policy) for policy in policies],
        "model_provider_retry_policy_validation": _validate_model_provider_retry_policies(policies, root),
        "provider_plans": _provider_plans(hass, "provider-retry-entry"),
        "render_plans": _render_plans(hass, "provider-retry-entry"),
        "artifacts": _artifacts(hass, "provider-retry-entry"),
        "complete_snapshots": _complete_snapshots(hass, "provider-retry-entry", job_id),
        "failed_snapshots": [
            _snapshot_summary(item)
            for item in job["snapshots"]
            if item.get("status") == "failed"
        ],
        "job_store": summarize_job_state_store(_job_store(hass, "provider-retry-entry")),
        "orchestration_store": _orchestration_store_summary(hass, "provider-retry-entry"),
    }


def verify_model_provider_retry_policy_contracts_validate(root=None) -> dict[str, Any]:
    root = root or repo_root()
    accepted = verify_provider_failure_records_retry_policy(root)
    isolation = verify_valid_provider_retry_policies_stay_config_entry_scoped(root)
    return {
        "accepted": {
            "model_provider_retry_policy_valid": all(
                item["accepted"] for item in accepted["model_provider_retry_policy_validation"]
            ),
        },
        "isolation_entry_a": {
            "model_provider_retry_policy_valid": all(
                item["accepted"] for item in isolation["entry_a"]["model_provider_retry_policy_validation"]
            ),
        },
        "isolation_entry_b": {
            "model_provider_retry_policy_valid": all(
                item["accepted"] for item in isolation["entry_b"]["model_provider_retry_policy_validation"]
            ),
        },
    }


def verify_provider_retry_policy_failure_details_are_sanitized(root=None) -> dict[str, Any]:
    accepted = verify_provider_failure_records_retry_policy(root or repo_root())
    card_snapshot_text = str(accepted["snapshot"]["connection"]["results"])
    policy = accepted["model_provider_retry_policy"]
    secret_failure = verify_secret_provider_failure_rejected_before_policy(root or repo_root())
    return {
        "stored_failure_code": policy["failure"]["code"],
        "stored_failure_message": policy["failure"]["message"],
        "card_snapshot_excludes_provider_endpoint": policy["provider"]["endpoint_url"] not in card_snapshot_text,
        "card_snapshot_excludes_provider_model": policy["provider"]["model"] not in card_snapshot_text,
        "card_snapshot_excludes_policy_id": policy["policy_id"] not in card_snapshot_text,
        "card_snapshot_excludes_policy_type": "isolinear_model_provider_retry_policy" not in card_snapshot_text,
        "secret_failure": {
            "error_codes": secret_failure["error_codes"],
            "policy_count": len(secret_failure["model_provider_retry_policies"]),
            "secret_absent_from_result": "Bearer super-secret" not in str(secret_failure),
        },
    }


def verify_secret_provider_failure_rejected_before_policy(root=None) -> dict[str, Any]:
    return _rejected_provider_failure_case(
        root or repo_root(),
        entry_id="provider-secret-failure-entry",
        failure={
            "accepted": False,
            "code": "model_provider_connection_error",
            "message": "Planner returned Bearer super-secret in a failure.",
            "retry_safe": True,
        },
    )


def verify_malformed_provider_failure_rejected_before_policy(root=None) -> dict[str, Any]:
    return _rejected_provider_failure_case(
        root or repo_root(),
        entry_id="provider-malformed-failure-entry",
        failure={
            "accepted": False,
            "code": "model_provider_connection_error",
            "message": "Planner failure retry metadata was malformed.",
            "retry_safe": "yes",
        },
    )


def verify_unknown_provider_retry_policy_job_rejected_before_call(root=None) -> dict[str, Any]:
    root = root or repo_root()
    planner = FakeFailingOllamaPlanner()
    hass, websocket_api_module = _setup_failing_provider_hass(
        FakeConfigEntry(
            "provider-retry-unknown-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        planner,
    )
    snapshot = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "provider-retry-unknown-entry",
        "provider-retry-unknown-entry-job-404",
        40,
    )
    policies = _model_provider_retry_policies(hass, "provider-retry-unknown-entry")
    return {
        "snapshot": snapshot,
        "planner_call_count": len(planner.calls),
        "error_codes": _error_codes(snapshot),
        "model_provider_retry_policies": [_policy_summary(policy) for policy in policies],
        "provider_plans": _provider_plans(hass, "provider-retry-unknown-entry"),
        "render_plans": _render_plans(hass, "provider-retry-unknown-entry"),
        "artifacts": _artifacts(hass, "provider-retry-unknown-entry"),
        "policy_validation": _validate_model_provider_retry_policies(policies, root),
    }


def verify_cross_config_entry_provider_retry_policy_rejected_before_call(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "provider-retry-cross-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "provider-retry-cross-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    planner_a = _install_fake_failing_planner(hass, "provider-retry-cross-entry-a")
    planner_b = _install_fake_failing_planner(hass, "provider-retry-cross-entry-b")
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "provider-retry-cross-entry-a",
        "Show sensor.upstairs_temperature",
        50,
    )
    start_b = _dispatch_start(
        hass,
        websocket_api_module,
        "provider-retry-cross-entry-b",
        "Show binary_sensor.office_window",
        51,
    )
    snapshot_a = _first_result_payload(start_a)
    snapshot_b = _first_result_payload(start_b)
    cross_snapshot = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "provider-retry-cross-entry-b",
        snapshot_a["job_id"],
        52,
    )
    policies_b = _model_provider_retry_policies(hass, "provider-retry-cross-entry-b")
    return {
        "entry_a_start": start_a,
        "entry_b_start": start_b,
        "entry_b_start_snapshot": _snapshot_summary(snapshot_b),
        "cross_snapshot": cross_snapshot,
        "entry_a_planner_call_count": len(planner_a.calls),
        "entry_b_planner_call_count": len(planner_b.calls),
        "error_codes": _error_codes(cross_snapshot),
        "entry_b_model_provider_retry_policies": [_policy_summary(policy) for policy in policies_b],
        "entry_b_provider_plans": _provider_plans(hass, "provider-retry-cross-entry-b"),
        "entry_b_render_plans": _render_plans(hass, "provider-retry-cross-entry-b"),
        "entry_b_artifacts": _artifacts(hass, "provider-retry-cross-entry-b"),
        "entry_b_complete_snapshots": _complete_snapshots(hass, "provider-retry-cross-entry-b", snapshot_b["job_id"]),
        "policy_validation": _validate_model_provider_retry_policies(policies_b, root),
    }


def verify_valid_provider_retry_policies_stay_config_entry_scoped(root=None) -> dict[str, Any]:
    root = root or repo_root()
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = FakeConfigEntry(
        "provider-retry-isolation-entry-a",
        options={"entity_allowlist": ["sensor.upstairs_temperature"]},
    )
    entry_b = FakeConfigEntry(
        "provider-retry-isolation-entry-b",
        options={"entity_allowlist": ["binary_sensor.office_window"]},
    )
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    planner_a = _install_fake_failing_planner(hass, "provider-retry-isolation-entry-a")
    planner_b = _install_fake_failing_planner(
        hass,
        "provider-retry-isolation-entry-b",
        failure={
            "accepted": False,
            "code": "model_provider_http_error",
            "message": "Planner HTTP request failed before a chart spec was accepted.",
            "retry_safe": True,
        },
    )
    start_a = _dispatch_start(
        hass,
        websocket_api_module,
        "provider-retry-isolation-entry-a",
        "Show sensor.upstairs_temperature",
        60,
    )
    start_b = _dispatch_start(
        hass,
        websocket_api_module,
        "provider-retry-isolation-entry-b",
        "Show binary_sensor.office_window",
        61,
    )
    snapshot_a = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "provider-retry-isolation-entry-a",
        _first_result_payload(start_a)["job_id"],
        62,
    )
    snapshot_b = _dispatch_snapshot(
        hass,
        websocket_api_module,
        "provider-retry-isolation-entry-b",
        _first_result_payload(start_b)["job_id"],
        63,
    )
    policies_a = _model_provider_retry_policies(hass, "provider-retry-isolation-entry-a")
    policies_b = _model_provider_retry_policies(hass, "provider-retry-isolation-entry-b")
    return {
        "entry_a": {
            "snapshot": snapshot_a,
            "planner_call_count": len(planner_a.calls),
            "model_provider_retry_policies": [_policy_summary(policy) for policy in policies_a],
            "orchestration_store": _orchestration_store_summary(hass, "provider-retry-isolation-entry-a"),
            "model_provider_retry_policy_validation": _validate_model_provider_retry_policies(policies_a, root),
        },
        "entry_b": {
            "snapshot": snapshot_b,
            "planner_call_count": len(planner_b.calls),
            "model_provider_retry_policies": [_policy_summary(policy) for policy in policies_b],
            "orchestration_store": _orchestration_store_summary(hass, "provider-retry-isolation-entry-b"),
            "model_provider_retry_policy_validation": _validate_model_provider_retry_policies(policies_b, root),
        },
    }


def verify_model_provider_retry_policy_side_effect_boundaries() -> dict[str, Any]:
    accepted = verify_provider_failure_records_retry_policy()
    secret = verify_secret_provider_failure_rejected_before_policy()
    malformed = verify_malformed_provider_failure_rejected_before_policy()
    unknown = verify_unknown_provider_retry_policy_job_rejected_before_call()
    cross_entry = verify_cross_config_entry_provider_retry_policy_rejected_before_call()
    isolation = verify_valid_provider_retry_policies_stay_config_entry_scoped()
    setup = _setup_failing_provider_hass(
        FakeConfigEntry(
            "side-effects-provider-retry-entry",
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        FakeFailingOllamaPlanner(),
    )[0].data[DOMAIN]["side-effects-provider-retry-entry"]

    observed = [
        {"name": "provider_failure_snapshot", **accepted["snapshot"]["orchestration"]},
        {"name": "secret_provider_failure", **secret["snapshot"]["orchestration"]},
        {"name": "malformed_provider_failure", **malformed["snapshot"]["orchestration"]},
        {"name": "unknown_provider_job", **unknown["snapshot"]["orchestration"]},
        {"name": "cross_config_entry", **cross_entry["cross_snapshot"]["orchestration"]},
        {"name": "entry_a_provider_failure", **isolation["entry_a"]["snapshot"]["orchestration"]},
        {"name": "entry_b_provider_failure", **isolation["entry_b"]["snapshot"]["orchestration"]},
        {"name": "setup_orchestration", **setup[DATA_JOB_ORCHESTRATION_SETUP]["orchestration"]},
        {"name": "websocket_registration", **setup["websocket_api"]["orchestration"]},
    ]

    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in MODEL_PROVIDER_RETRY_POLICY_FORBIDDEN_SIDE_EFFECT_KEYS
    }
    allowed_aggregate = {
        "model_provider_called": any(item.get("model_provider_called") for item in observed),
        "model_provider_retry_policy_bookkeeping_written": any(
            item.get("model_provider_retry_policy_bookkeeping_written") for item in observed
        ),
        "job_state_scaffold_written": any(item.get("job_state_scaffold_written") for item in observed),
        "job_orchestration_scaffold_written": any(
            item.get("job_orchestration_scaffold_written") for item in observed
        ),
        "websocket_command_registered": any(item.get("websocket_command_registered") for item in observed),
    }
    return {
        "expected_forbidden": {key: False for key in MODEL_PROVIDER_RETRY_POLICY_FORBIDDEN_SIDE_EFFECT_KEYS},
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }


def verify_model_provider_retry_backoff_policy_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_model_provider_retry_policy_files(root)
    accepted = verify_provider_failure_records_retry_policy(root)
    validation = verify_model_provider_retry_policy_contracts_validate(root)
    sanitization = verify_provider_retry_policy_failure_details_are_sanitized(root)
    secret = verify_secret_provider_failure_rejected_before_policy(root)
    malformed = verify_malformed_provider_failure_rejected_before_policy(root)
    unknown_job = verify_unknown_provider_retry_policy_job_rejected_before_call(root)
    cross_entry = verify_cross_config_entry_provider_retry_policy_rejected_before_call(root)
    isolation = verify_valid_provider_retry_policies_stay_config_entry_scoped(root)
    side_effects = verify_model_provider_retry_policy_side_effect_boundaries()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more model-provider retry/backoff policy scaffold files are missing.")
    if not accepted["snapshot"]["accepted"]:
        failures.append("Retry-safe provider failure did not return a card-facing failed snapshot.")
    if accepted["card_snapshot"]["status"] != "failed" or accepted["card_snapshot"]["retry_allowed"] is not True:
        failures.append("Retry-safe provider failure did not produce a retryable failed snapshot.")
    if accepted["planner_call_count"] != 1:
        failures.append("Retry-safe provider failure did not call the planner exactly once.")
    if len(accepted["model_provider_retry_policies"]) != 1:
        failures.append("Retry-safe provider failure did not store exactly one retry policy.")
    elif accepted["model_provider_retry_policy"]["policy_id"] != "provider-retry-entry-model-provider-retry-policy-001":
        failures.append("Provider retry policy did not use the deterministic policy ID.")
    if accepted["provider_plans"] or accepted["render_plans"] or accepted["artifacts"] or accepted["complete_snapshots"]:
        failures.append("Provider failure policy handling stored plan/render/artifact/complete state.")
    if not validation["accepted"]["model_provider_retry_policy_valid"]:
        failures.append("Accepted provider retry policy did not validate.")
    if not all(
        sanitization[key]
        for key in (
            "card_snapshot_excludes_provider_endpoint",
            "card_snapshot_excludes_provider_model",
            "card_snapshot_excludes_policy_id",
            "card_snapshot_excludes_policy_type",
        )
    ):
        failures.append("Provider retry details leaked into the card-facing snapshot.")
    if secret["error_codes"] != ["model_provider_failure_forbidden_material"]:
        failures.append("Secret-bearing provider failure did not fail closed with forbidden material.")
    if secret["model_provider_retry_policies"]:
        failures.append("Secret-bearing provider failure stored retry policy metadata.")
    if malformed["error_codes"] != ["invalid_model_provider_failure"]:
        failures.append("Malformed provider failure did not fail closed with invalid_model_provider_failure.")
    if malformed["model_provider_retry_policies"]:
        failures.append("Malformed provider failure stored retry policy metadata.")
    if unknown_job["planner_call_count"] != 0 or unknown_job["error_codes"] != ["unknown_job"]:
        failures.append("Unknown provider retry-policy job did not fail before provider call.")
    if unknown_job["model_provider_retry_policies"]:
        failures.append("Unknown provider retry-policy job recorded policy metadata.")
    if cross_entry["entry_a_planner_call_count"] != 0 or cross_entry["entry_b_planner_call_count"] != 0:
        failures.append("Cross-config-entry provider retry-policy request called a provider.")
    if cross_entry["error_codes"] != ["unknown_job"]:
        failures.append("Cross-config-entry provider retry-policy request did not fail as unknown_job.")
    if cross_entry["entry_b_model_provider_retry_policies"]:
        failures.append("Cross-config-entry provider retry-policy request recorded entry B policy.")
    if (
        len(isolation["entry_a"]["model_provider_retry_policies"]) != 1
        or len(isolation["entry_b"]["model_provider_retry_policies"]) != 1
    ):
        failures.append("Valid provider retry policies did not stay isolated by config entry.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("Model-provider retry policy scaffold reported forbidden side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("Model-provider retry policy scaffold did not report expected allowed side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "accepted": accepted,
        "validation": validation,
        "sanitization": sanitization,
        "secret": secret,
        "malformed": malformed,
        "unknown_job": unknown_job,
        "cross_entry": cross_entry,
        "isolation": isolation,
        "side_effects": side_effects,
    }


def _rejected_provider_failure_case(
    root,
    *,
    entry_id: str,
    failure: dict[str, Any],
) -> dict[str, Any]:
    planner = FakeFailingOllamaPlanner(failure)
    hass, websocket_api_module = _setup_failing_provider_hass(
        FakeConfigEntry(
            entry_id,
            options={"entity_allowlist": ["sensor.upstairs_temperature"]},
        ),
        planner,
    )
    start = _dispatch_start(
        hass,
        websocket_api_module,
        entry_id,
        "Show sensor.upstairs_temperature",
        30,
    )
    job_id = _first_result_payload(start)["job_id"]
    snapshot = _dispatch_snapshot(hass, websocket_api_module, entry_id, job_id, 31)
    policies = _model_provider_retry_policies(hass, entry_id)
    return {
        "snapshot": snapshot,
        "planner_call_count": len(planner.calls),
        "error_codes": _error_codes(snapshot),
        "model_provider_retry_policies": [_policy_summary(policy) for policy in policies],
        "provider_plans": _provider_plans(hass, entry_id),
        "render_plans": _render_plans(hass, entry_id),
        "artifacts": _artifacts(hass, entry_id),
        "complete_snapshots": _complete_snapshots(hass, entry_id, job_id),
        "policy_validation": _validate_model_provider_retry_policies(policies, root),
    }


def _setup_failing_provider_hass(
    entry: FakeConfigEntry,
    planner: FakeFailingOllamaPlanner,
) -> tuple[Any, FakeWebSocketApiModule]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    setup_accepted = _run(async_setup_entry(hass, entry))
    if not setup_accepted:
        raise AssertionError(f"async_setup_entry rejected {entry.entry_id}")
    hass.data[DOMAIN][entry.entry_id][DATA_MODEL_PROVIDER_PLANNER] = planner
    return hass, websocket_api_module


def _install_fake_failing_planner(
    hass: Any,
    entry_id: str,
    failure: dict[str, Any] | None = None,
) -> FakeFailingOllamaPlanner:
    planner = FakeFailingOllamaPlanner(failure)
    hass.data[DOMAIN][entry_id][DATA_MODEL_PROVIDER_PLANNER] = planner
    return planner


def _model_provider_retry_policies(hass: Any, entry_id: str) -> list[dict[str, Any]]:
    store = hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION]
    return [
        deepcopy(store.get("model_provider_retry_policies", {})[policy_id])
        for policy_id in store.get("model_provider_retry_policy_order", [])
        if policy_id in store.get("model_provider_retry_policies", {})
    ]


def _orchestration_store_summary(hass: Any, entry_id: str) -> dict[str, Any]:
    return summarize_job_orchestration_store(hass.data[DOMAIN][entry_id][DATA_JOB_ORCHESTRATION])


def _validate_model_provider_retry_policies(policies: list[dict[str, Any]], root) -> list[dict[str, Any]]:
    return [_validate_model_provider_retry_policy(policy, root) for policy in policies]


def _validate_model_provider_retry_policy(policy: dict[str, Any], root) -> dict[str, Any]:
    try:
        validate_contract("integration-model-provider-retry-policy", policy, repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "contract_validation_failed",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "policy_id": policy["policy_id"],
        "job_id": policy["job_id"],
        "source_snapshot_id": policy["source_snapshot_id"],
        "delay_seconds": policy["backoff"]["delay_seconds"],
    }


def _snapshot_summary(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    failure = snapshot.get("failure") if isinstance(snapshot.get("failure"), dict) else None
    return {
        "snapshot_id": snapshot["snapshot_id"],
        "job_id": snapshot["job_id"],
        "status": snapshot["status"],
        "progress": deepcopy(snapshot.get("progress")),
        "failure": deepcopy(failure),
        "retry_allowed": snapshot.get("retry_allowed"),
        "warnings": deepcopy(snapshot.get("warnings", [])),
    }


def _policy_summary(policy: dict[str, Any] | None) -> dict[str, Any] | None:
    if policy is None:
        return None
    return {
        "policy_id": policy["policy_id"],
        "type": policy["type"],
        "config_entry_id": policy["config_entry_id"],
        "job_id": policy["job_id"],
        "source_snapshot_id": policy["source_snapshot_id"],
        "provider": deepcopy(policy["provider"]),
        "request": deepcopy(policy["request"]),
        "failure": deepcopy(policy["failure"]),
        "decision": deepcopy(policy["decision"]),
        "backoff": deepcopy(policy["backoff"]),
        "validation": deepcopy(policy["validation"]),
        "warnings": deepcopy(policy["warnings"]),
    }
