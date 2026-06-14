from __future__ import annotations

from copy import deepcopy
from typing import Any

import custom_components.isolinear.worker_token_lifecycle as worker_token_lifecycle
from custom_components.isolinear import async_setup_entry
from custom_components.isolinear.const import DOMAIN
from custom_components.isolinear.worker_readiness import (
    DATA_WORKER_READINESS,
    DATA_WORKER_READINESS_SETUP,
)
from custom_components.isolinear.worker_renderer import (
    DATA_WORKER_RENDER_CLIENT,
    DATA_WORKER_RENDER_SETUP,
    DATA_WORKER_RENDER_TOKEN,
    worker_client_token,
)
from custom_components.isolinear.worker_token_lifecycle import (
    DATA_WORKER_TOKEN_LIFECYCLE,
    DATA_WORKER_TOKEN_LIFECYCLE_STORE,
    WorkerTokenLifecycleStorageHelper,
    build_worker_token_lifecycle_state,
    provision_durable_integration_worker_token,
    repair_durable_integration_worker_token,
    rotate_durable_integration_worker_token,
)

from .contracts import ContractValidationError, validate_contract
from .dashboard_card_anchor import repo_root
from .entity_catalog_scaffold_anchor import FakeConfigEntry
from .job_orchestration_scaffold_anchor import _fake_hass, _run
from .websocket_command_registration_anchor import FakeWebSocketApiModule
from .worker_token_provisioning_readiness_anchor import (
    WORKER_ENDPOINT_URL,
    WORKER_READINESS_TEST_TOKEN,
    CountingTokenFactory,
    _entry_data,
    _worker_entry,
)


WORKER_LIFECYCLE_PERSISTED_TOKEN = "test-worker-lifecycle-persisted-token-444444444"
WORKER_LIFECYCLE_PROVISIONED_TOKEN = "test-worker-lifecycle-provisioned-token-555555555"
WORKER_LIFECYCLE_ROTATED_TOKEN = "test-worker-lifecycle-rotated-token-666666666"
WORKER_LIFECYCLE_REPAIRED_TOKEN = "test-worker-lifecycle-repaired-token-777777777"

WORKER_TOKEN_LIFECYCLE_FILES = [
    "docs/decisions/0016-durable-worker-token-lifecycle.md",
    "custom_components/isolinear/worker_token_lifecycle.py",
    "custom_components/isolinear/__init__.py",
    "docs/schemas/integration-worker-token-lifecycle-state.schema.json",
    "docs/specs/home-assistant-durable-worker-token-lifecycle-scaffold-spec.md",
    "bdd/integration/home-assistant-durable-worker-token-lifecycle-scaffold-bdd.md",
    "bdd/integration/home-assistant-durable-worker-token-lifecycle-scaffold-evidence.md",
    "docs/evals/home_assistant_durable_worker_token_lifecycle_scaffold.yaml",
    "tests/test_worker_token_lifecycle_anchor.py",
    "evals/home_assistant_durable_worker_token_lifecycle_scaffold.py",
    "src/Isolinear/worker_token_lifecycle_anchor.py",
]

WORKER_TOKEN_LIFECYCLE_FORBIDDEN_SIDE_EFFECT_KEYS = [
    "home_assistant_history_read",
    "semantic_memory_called",
    "home_assistant_service_or_state_mutation_called",
    "config_entry_options_written",
    "recorder_called",
    "worker_render_called",
    "worker_health_call",
    "model_provider_called",
    "chart_rendering_called",
    "chart_artifact_written",
    "durable_retry_storage_written",
    "external_queue_or_database_called",
    "scheduler_called",
    "automatic_rotation_called",
    "automatic_token_repair_execution_called",
    "setup_time_token_generation_called",
    "dashboard_command_registered",
    "token_leaked_to_card",
    "token_leaked_to_model_provider",
]


class FailingTokenLifecycleStorageHelper(WorkerTokenLifecycleStorageHelper):
    def __init__(self) -> None:
        super().__init__()
        self.fail_writes = False

    def write_token_entry(
        self,
        entry_id: str,
        token: str | None,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        if self.fail_writes:
            return {
                "accepted": False,
                "code": "invalid_integration_worker_token_lifecycle",
                "validation": {
                    "accepted": False,
                    "code": "forced_lifecycle_storage_failure",
                },
            }
        return super().write_token_entry(entry_id, token, state)


def verify_worker_token_lifecycle_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in WORKER_TOKEN_LIFECYCLE_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_setup_restores_persisted_token_before_readiness(root=None) -> dict[str, Any]:
    root = root or repo_root()
    entry = _worker_entry("worker-lifecycle-restore-entry")
    store = WorkerTokenLifecycleStorageHelper()
    seed_state = build_worker_token_lifecycle_state(
        entry_id=entry.entry_id,
        endpoint_configured=True,
        token=WORKER_LIFECYCLE_PERSISTED_TOKEN,
        code="worker_token_persisted",
        persisted=True,
    )
    store.write_token_entry(entry.entry_id, WORKER_LIFECYCLE_PERSISTED_TOKEN, seed_state)
    hass = _setup_lifecycle_hass(entry, store)
    entry_data = _entry_data(hass, entry.entry_id)
    lifecycle = deepcopy(entry_data[DATA_WORKER_TOKEN_LIFECYCLE])
    readiness = deepcopy(entry_data[DATA_WORKER_READINESS])
    renderer_client = entry_data.get(DATA_WORKER_RENDER_CLIENT)

    return {
        "lifecycle": lifecycle,
        "lifecycle_validation": _validate_lifecycle(lifecycle, root),
        "readiness": readiness,
        "readiness_status": readiness["status"],
        "readiness_setup": deepcopy(entry_data[DATA_WORKER_READINESS_SETUP]),
        "renderer_setup": deepcopy(entry_data[DATA_WORKER_RENDER_SETUP]),
        "stored_token_restored_to_memory": (
            entry_data.get(DATA_WORKER_RENDER_TOKEN) == WORKER_LIFECYCLE_PERSISTED_TOKEN
        ),
        "renderer_client_uses_restored_token": (
            worker_client_token(renderer_client) == WORKER_LIFECYCLE_PERSISTED_TOKEN
        ),
        "private_store_has_token": store.private_token_for(entry.entry_id) == WORKER_LIFECYCLE_PERSISTED_TOKEN,
    }


def verify_missing_persisted_token_records_repair_issue(root=None) -> dict[str, Any]:
    root = root or repo_root()
    entry = _worker_entry("worker-lifecycle-repair-issue-entry")
    hass = _setup_lifecycle_hass(entry)
    entry_data = _entry_data(hass, entry.entry_id)
    lifecycle = deepcopy(entry_data[DATA_WORKER_TOKEN_LIFECYCLE])
    return {
        "lifecycle": lifecycle,
        "lifecycle_validation": _validate_lifecycle(lifecycle, root),
        "readiness": deepcopy(entry_data[DATA_WORKER_READINESS]),
        "token_present": DATA_WORKER_RENDER_TOKEN in entry_data,
        "repair_issue": deepcopy(lifecycle["repair_issue"]),
    }


def verify_missing_worker_endpoint_records_disabled_lifecycle(root=None) -> dict[str, Any]:
    root = root or repo_root()
    entry = FakeConfigEntry("worker-lifecycle-disabled-entry")
    hass = _setup_lifecycle_hass(entry)
    entry_data = _entry_data(hass, entry.entry_id)
    lifecycle = deepcopy(entry_data[DATA_WORKER_TOKEN_LIFECYCLE])
    return {
        "lifecycle": lifecycle,
        "lifecycle_validation": _validate_lifecycle(lifecycle, root),
        "readiness": deepcopy(entry_data[DATA_WORKER_READINESS]),
        "token_present": DATA_WORKER_RENDER_TOKEN in entry_data,
        "repair_issue": deepcopy(lifecycle["repair_issue"]),
    }


def verify_durable_explicit_operations_persist_private_tokens(root=None) -> dict[str, Any]:
    root = root or repo_root()
    provision_entry = _worker_entry("worker-lifecycle-provision-entry")
    provision_hass = _setup_lifecycle_hass(provision_entry)
    provision_factory = CountingTokenFactory(WORKER_LIFECYCLE_PROVISIONED_TOKEN)
    provision = provision_durable_integration_worker_token(
        provision_hass,
        provision_entry.entry_id,
        token_factory=provision_factory,
    )
    provision_store = _lifecycle_store(provision_hass)

    rotation_factory = CountingTokenFactory(WORKER_LIFECYCLE_ROTATED_TOKEN)
    rotation = rotate_durable_integration_worker_token(
        provision_hass,
        provision_entry.entry_id,
        token_factory=rotation_factory,
    )

    repair_entry = _worker_entry("worker-lifecycle-repair-entry")
    repair_hass = _setup_lifecycle_hass(repair_entry)
    repair_factory = CountingTokenFactory(WORKER_LIFECYCLE_REPAIRED_TOKEN)
    repair = repair_durable_integration_worker_token(
        repair_hass,
        repair_entry.entry_id,
        token_factory=repair_factory,
    )
    repair_store = _lifecycle_store(repair_hass)

    provision_lifecycle = deepcopy(
        _entry_data(provision_hass, provision_entry.entry_id)[DATA_WORKER_TOKEN_LIFECYCLE]
    )
    repair_lifecycle = deepcopy(_entry_data(repair_hass, repair_entry.entry_id)[DATA_WORKER_TOKEN_LIFECYCLE])
    return {
        "provision": provision,
        "rotation": rotation,
        "repair": repair,
        "provision_lifecycle": provision_lifecycle,
        "provision_lifecycle_validation": _validate_lifecycle(provision_lifecycle, root),
        "repair_lifecycle": repair_lifecycle,
        "repair_lifecycle_validation": _validate_lifecycle(repair_lifecycle, root),
        "private_provision_token_persisted": (
            provision_store.private_token_for(provision_entry.entry_id) == WORKER_LIFECYCLE_ROTATED_TOKEN
        ),
        "private_repair_token_persisted": (
            repair_store.private_token_for(repair_entry.entry_id) == WORKER_LIFECYCLE_REPAIRED_TOKEN
        ),
        "rotation_replaced_private_token": (
            provision_store.private_token_for(provision_entry.entry_id) != WORKER_LIFECYCLE_PROVISIONED_TOKEN
        ),
        "repair_issue_cleared_after_success": not repair_lifecycle["repair_issue"]["present"],
        "token_factory_calls": {
            "provision": provision_factory.calls,
            "rotation": rotation_factory.calls,
            "repair": repair_factory.calls,
        },
    }


def verify_invalid_persisted_entries_skipped_before_restore(root=None) -> dict[str, Any]:
    root = root or repo_root()
    entry = _worker_entry("worker-lifecycle-invalid-entry")
    store = WorkerTokenLifecycleStorageHelper()
    mismatched_state = build_worker_token_lifecycle_state(
        entry_id="another-entry",
        endpoint_configured=True,
        token=WORKER_LIFECYCLE_PERSISTED_TOKEN,
        code="worker_token_persisted",
        persisted=True,
    )
    store.data["entries"][entry.entry_id] = {
        "token": WORKER_LIFECYCLE_PERSISTED_TOKEN,
        "state": mismatched_state,
    }
    store.data["entries"]["malformed-token-entry"] = {
        "token": "short",
        "state": build_worker_token_lifecycle_state(
            entry_id="malformed-token-entry",
            endpoint_configured=True,
            token="short",
            code="worker_token_persisted",
            persisted=True,
        ),
    }
    hass = _setup_lifecycle_hass(entry, store)
    entry_data = _entry_data(hass, entry.entry_id)
    lifecycle = deepcopy(entry_data[DATA_WORKER_TOKEN_LIFECYCLE])
    return {
        "lifecycle": lifecycle,
        "lifecycle_validation": _validate_lifecycle(lifecycle, root),
        "readiness": deepcopy(entry_data[DATA_WORKER_READINESS]),
        "token_restored": DATA_WORKER_RENDER_TOKEN in entry_data,
        "repair_issue": deepcopy(lifecycle["repair_issue"]),
    }


def verify_setup_lifecycle_storage_failure_blocks_restore() -> dict[str, Any]:
    entry = _worker_entry("worker-lifecycle-setup-failure-entry")
    store = FailingTokenLifecycleStorageHelper()
    seed_state = build_worker_token_lifecycle_state(
        entry_id=entry.entry_id,
        endpoint_configured=True,
        token=WORKER_LIFECYCLE_PERSISTED_TOKEN,
        code="worker_token_persisted",
        persisted=True,
    )
    store.write_token_entry(entry.entry_id, WORKER_LIFECYCLE_PERSISTED_TOKEN, seed_state)
    store.fail_writes = True
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    hass.data.setdefault(DOMAIN, {})[DATA_WORKER_TOKEN_LIFECYCLE_STORE] = store

    setup_accepted = _run(async_setup_entry(hass, entry))
    entry_data = _entry_data(hass, entry.entry_id)
    lifecycle_setup = deepcopy(entry_data["worker_token_lifecycle_setup"])
    return {
        "setup_accepted": setup_accepted,
        "lifecycle_setup": lifecycle_setup,
        "token_restored": DATA_WORKER_RENDER_TOKEN in entry_data,
        "readiness_written": DATA_WORKER_READINESS in entry_data,
        "renderer_setup_written": DATA_WORKER_RENDER_SETUP in entry_data,
        "private_token_retained": store.private_token_for(entry.entry_id) == WORKER_LIFECYCLE_PERSISTED_TOKEN,
    }


def verify_lifecycle_validation_failure_rolls_back(root=None) -> dict[str, Any]:
    root = root or repo_root()
    entry = _worker_entry("worker-lifecycle-rollback-entry")
    store = WorkerTokenLifecycleStorageHelper()
    seed_state = build_worker_token_lifecycle_state(
        entry_id=entry.entry_id,
        endpoint_configured=True,
        token=WORKER_READINESS_TEST_TOKEN,
        code="worker_token_persisted",
        persisted=True,
    )
    store.write_token_entry(entry.entry_id, WORKER_READINESS_TEST_TOKEN, seed_state)
    hass = _setup_lifecycle_hass(entry, store)
    entry_data = _entry_data(hass, entry.entry_id)
    old_renderer_client = entry_data[DATA_WORKER_RENDER_CLIENT]
    old_lifecycle = deepcopy(entry_data[DATA_WORKER_TOKEN_LIFECYCLE])
    old_readiness = deepcopy(entry_data[DATA_WORKER_READINESS])
    old_renderer_setup = deepcopy(entry_data[DATA_WORKER_RENDER_SETUP])
    old_private_token = store.private_token_for(entry.entry_id)
    token_factory = CountingTokenFactory(WORKER_LIFECYCLE_ROTATED_TOKEN)

    original_schema_path = worker_token_lifecycle.WORKER_TOKEN_LIFECYCLE_SCHEMA_PATH
    try:
        worker_token_lifecycle.WORKER_TOKEN_LIFECYCLE_SCHEMA_PATH = (
            root / "docs" / "schemas" / "missing-token-lifecycle.schema.json"
        )
        rotation = rotate_durable_integration_worker_token(
            hass,
            entry.entry_id,
            token_factory=token_factory,
        )
    finally:
        worker_token_lifecycle.WORKER_TOKEN_LIFECYCLE_SCHEMA_PATH = original_schema_path

    return {
        "rotation": rotation,
        "token_factory_call_count": token_factory.calls,
        "private_token_restored": store.private_token_for(entry.entry_id) == old_private_token,
        "rotated_token_absent_from_private_store": (
            store.private_token_for(entry.entry_id) != WORKER_LIFECYCLE_ROTATED_TOKEN
        ),
        "in_memory_token_restored": entry_data.get(DATA_WORKER_RENDER_TOKEN) == old_private_token,
        "old_renderer_client_restored": entry_data.get(DATA_WORKER_RENDER_CLIENT) is old_renderer_client,
        "lifecycle_before_failure": old_lifecycle,
        "lifecycle_after_failure": deepcopy(entry_data[DATA_WORKER_TOKEN_LIFECYCLE]),
        "readiness_before_failure": old_readiness,
        "readiness_after_failure": deepcopy(entry_data[DATA_WORKER_READINESS]),
        "renderer_setup_before_failure": old_renderer_setup,
        "renderer_setup_after_failure": deepcopy(entry_data[DATA_WORKER_RENDER_SETUP]),
    }


def verify_worker_token_lifecycle_stays_config_entry_scoped(root=None) -> dict[str, Any]:
    root = root or repo_root()
    entry_a = _worker_entry("worker-lifecycle-isolation-a")
    entry_b = _worker_entry("worker-lifecycle-isolation-b")
    store = WorkerTokenLifecycleStorageHelper()
    store.write_token_entry(
        entry_a.entry_id,
        WORKER_LIFECYCLE_PERSISTED_TOKEN,
        build_worker_token_lifecycle_state(
            entry_id=entry_a.entry_id,
            endpoint_configured=True,
            token=WORKER_LIFECYCLE_PERSISTED_TOKEN,
            code="worker_token_persisted",
            persisted=True,
        ),
    )
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    hass.data.setdefault(DOMAIN, {})[DATA_WORKER_TOKEN_LIFECYCLE_STORE] = store
    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    entry_b_before = {
        "lifecycle": deepcopy(_entry_data(hass, entry_b.entry_id)[DATA_WORKER_TOKEN_LIFECYCLE]),
        "readiness": deepcopy(_entry_data(hass, entry_b.entry_id)[DATA_WORKER_READINESS]),
        "token_present": DATA_WORKER_RENDER_TOKEN in _entry_data(hass, entry_b.entry_id),
    }

    rotate_durable_integration_worker_token(
        hass,
        entry_a.entry_id,
        token_factory=CountingTokenFactory(WORKER_LIFECYCLE_ROTATED_TOKEN),
    )

    return {
        "entry_a": {
            "lifecycle": deepcopy(_entry_data(hass, entry_a.entry_id)[DATA_WORKER_TOKEN_LIFECYCLE]),
            "lifecycle_validation": _validate_lifecycle(
                _entry_data(hass, entry_a.entry_id)[DATA_WORKER_TOKEN_LIFECYCLE],
                root,
            ),
            "private_token": store.private_token_for(entry_a.entry_id) == WORKER_LIFECYCLE_ROTATED_TOKEN,
            "renderer_client_uses_own_token": worker_client_token(
                _entry_data(hass, entry_a.entry_id).get(DATA_WORKER_RENDER_CLIENT)
            )
            == WORKER_LIFECYCLE_ROTATED_TOKEN,
        },
        "entry_b_before": entry_b_before,
        "entry_b": {
            "lifecycle": deepcopy(_entry_data(hass, entry_b.entry_id)[DATA_WORKER_TOKEN_LIFECYCLE]),
            "lifecycle_validation": _validate_lifecycle(
                _entry_data(hass, entry_b.entry_id)[DATA_WORKER_TOKEN_LIFECYCLE],
                root,
            ),
            "readiness": deepcopy(_entry_data(hass, entry_b.entry_id)[DATA_WORKER_READINESS]),
            "token_present": DATA_WORKER_RENDER_TOKEN in _entry_data(hass, entry_b.entry_id),
            "private_token": store.private_token_for(entry_b.entry_id),
        },
    }


def verify_worker_token_lifecycle_details_do_not_leak(root=None) -> dict[str, Any]:
    restore = verify_setup_restores_persisted_token_before_readiness(root)
    repair_issue = verify_missing_persisted_token_records_repair_issue(root)
    explicit = verify_durable_explicit_operations_persist_private_tokens(root)
    invalid = verify_invalid_persisted_entries_skipped_before_restore(root)
    tokens = [
        WORKER_LIFECYCLE_PERSISTED_TOKEN,
        WORKER_LIFECYCLE_PROVISIONED_TOKEN,
        WORKER_LIFECYCLE_ROTATED_TOKEN,
        WORKER_LIFECYCLE_REPAIRED_TOKEN,
        WORKER_READINESS_TEST_TOKEN,
    ]
    dashboard_visible_payload = {
        "snapshot": {
            "status": "failed",
            "message": "Worker token needs attention.",
            "retry": {"available": False},
        }
    }
    dashboard_metadata = _setup_lifecycle_hass(_worker_entry("worker-lifecycle-leak-entry")).data[DOMAIN][
        "websocket_registration"
    ]
    evidence_payload = {
        "restore": restore,
        "repair_issue": repair_issue,
        "explicit": explicit,
        "invalid": invalid,
    }

    return {
        "tokens_absent_from_lifecycle_state": not any(
            token in str(
                [
                    restore["lifecycle"],
                    repair_issue["lifecycle"],
                    explicit["provision_lifecycle"],
                    explicit["repair_lifecycle"],
                    invalid["lifecycle"],
                ]
            )
            for token in tokens
        ),
        "tokens_absent_from_setup_results": not any(
            token in str(
                [
                    restore["readiness_setup"],
                    restore["renderer_setup"],
                    explicit["provision"].get("readiness"),
                    explicit["rotation"].get("readiness"),
                    explicit["repair"].get("readiness"),
                ]
            )
            for token in tokens
        ),
        "tokens_absent_from_repair_issue_metadata": not any(
            token in str([repair_issue["repair_issue"], invalid["repair_issue"]])
            for token in tokens
        ),
        "tokens_absent_from_dashboard_card_metadata": not any(token in str(dashboard_metadata) for token in tokens),
        "tokens_absent_from_model_provider_metadata": not any(
            token
            in str(_entry_data(_setup_lifecycle_hass(_worker_entry("worker-lifecycle-model-entry")), "worker-lifecycle-model-entry")["model_provider_setup"])
            for token in tokens
        ),
        "tokens_absent_from_evidence_payload": not any(token in str(evidence_payload) for token in tokens),
        "lifecycle_absent_from_dashboard_payload": "worker_token_lifecycle" not in str(dashboard_visible_payload),
        "repair_issue_absent_from_dashboard_payload": "repair_issue" not in str(dashboard_visible_payload),
        "endpoint_absent_from_dashboard_payload": WORKER_ENDPOINT_URL not in str(dashboard_visible_payload),
        "dashboard_payload": dashboard_visible_payload,
    }


def verify_worker_token_lifecycle_side_effect_boundaries() -> dict[str, Any]:
    restore = verify_setup_restores_persisted_token_before_readiness()
    repair_issue = verify_missing_persisted_token_records_repair_issue()
    disabled = verify_missing_worker_endpoint_records_disabled_lifecycle()
    explicit = verify_durable_explicit_operations_persist_private_tokens()
    invalid = verify_invalid_persisted_entries_skipped_before_restore()
    setup_failure = verify_setup_lifecycle_storage_failure_blocks_restore()
    rollback = verify_lifecycle_validation_failure_rolls_back()
    isolation = verify_worker_token_lifecycle_stays_config_entry_scoped()

    observed = [
        {"name": "restore", **restore["lifecycle"]["orchestration"]},
        {"name": "repair_issue", **repair_issue["lifecycle"]["orchestration"]},
        {"name": "disabled", **disabled["lifecycle"]["orchestration"]},
        {"name": "explicit_provision", **explicit["provision_lifecycle"]["orchestration"]},
        {"name": "explicit_repair", **explicit["repair_lifecycle"]["orchestration"]},
        {"name": "invalid", **invalid["lifecycle"]["orchestration"]},
        {"name": "setup_failure", **setup_failure["lifecycle_setup"]["orchestration"]},
        {"name": "rollback", **rollback["rotation"]["orchestration"]},
        {"name": "isolation_a", **isolation["entry_a"]["lifecycle"]["orchestration"]},
        {"name": "isolation_b", **isolation["entry_b"]["lifecycle"]["orchestration"]},
    ]
    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in WORKER_TOKEN_LIFECYCLE_FORBIDDEN_SIDE_EFFECT_KEYS
    }
    allowed_aggregate = {
        "durable_token_storage_loaded": any(item.get("durable_token_storage_loaded") for item in observed),
        "durable_token_storage_written": any(item.get("durable_token_storage_written") for item in observed),
        "in_memory_token_restored": any(item.get("in_memory_token_restored") for item in observed),
        "automatic_token_restore_called": any(item.get("automatic_token_restore_called") for item in observed),
        "repair_issue_created": any(item.get("repair_issue_created") for item in observed),
        "repair_issue_deleted": any(item.get("repair_issue_deleted") for item in observed),
    }
    return {
        "expected_forbidden": {key: False for key in WORKER_TOKEN_LIFECYCLE_FORBIDDEN_SIDE_EFFECT_KEYS},
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }


def verify_worker_token_lifecycle_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_worker_token_lifecycle_files(root)
    restore = verify_setup_restores_persisted_token_before_readiness(root)
    repair_issue = verify_missing_persisted_token_records_repair_issue(root)
    disabled = verify_missing_worker_endpoint_records_disabled_lifecycle(root)
    explicit = verify_durable_explicit_operations_persist_private_tokens(root)
    invalid = verify_invalid_persisted_entries_skipped_before_restore(root)
    setup_failure = verify_setup_lifecycle_storage_failure_blocks_restore()
    rollback = verify_lifecycle_validation_failure_rolls_back(root)
    isolation = verify_worker_token_lifecycle_stays_config_entry_scoped(root)
    leakage = verify_worker_token_lifecycle_details_do_not_leak(root)
    side_effects = verify_worker_token_lifecycle_side_effect_boundaries()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more durable worker token lifecycle files are missing.")
    if restore["lifecycle"]["status"] != "ready" or not restore["lifecycle_validation"]["accepted"]:
        failures.append("Persisted token restore did not write schema-valid ready lifecycle state.")
    if not restore["stored_token_restored_to_memory"] or restore["readiness_status"] != "ready":
        failures.append("Persisted token restore did not happen before readiness setup.")
    if not restore["renderer_setup"]["enabled"] or not restore["renderer_client_uses_restored_token"]:
        failures.append("Persisted token restore did not enable same-entry worker renderer setup.")
    if repair_issue["lifecycle"]["status"] != "not_ready" or not repair_issue["repair_issue"]["present"]:
        failures.append("Missing persisted token did not record repair issue metadata.")
    if repair_issue["token_present"]:
        failures.append("Missing persisted token generated or stored a token during setup.")
    if disabled["lifecycle"]["status"] != "disabled" or disabled["repair_issue"]["present"]:
        failures.append("Missing worker endpoint did not stay disabled without repair issue metadata.")
    if not explicit["private_provision_token_persisted"]:
        failures.append("Durable provision/rotation did not persist the private token.")
    if not explicit["private_repair_token_persisted"]:
        failures.append("Durable repair did not persist the private token.")
    if not explicit["repair_issue_cleared_after_success"]:
        failures.append("Successful durable repair did not clear repair issue metadata.")
    if invalid["token_restored"] or not invalid["repair_issue"]["present"]:
        failures.append("Invalid persisted entry restored a token or skipped repair issue metadata.")
    if setup_failure["setup_accepted"] or setup_failure["token_restored"]:
        failures.append("Setup lifecycle storage failure restored a token or accepted setup.")
    if setup_failure["readiness_written"] or setup_failure["renderer_setup_written"]:
        failures.append("Setup lifecycle storage failure continued into readiness or renderer setup.")
    if not setup_failure["private_token_retained"]:
        failures.append("Setup lifecycle storage failure dropped previous private token state.")
    if rollback["rotation"]["code"] != "invalid_integration_worker_token_lifecycle":
        failures.append("Lifecycle validation failure did not return the lifecycle failure code.")
    if not rollback["private_token_restored"] or not rollback["in_memory_token_restored"]:
        failures.append("Lifecycle validation failure did not restore durable and in-memory token state.")
    if rollback["lifecycle_after_failure"] != rollback["lifecycle_before_failure"]:
        failures.append("Lifecycle validation failure did not restore lifecycle state.")
    if rollback["readiness_after_failure"] != rollback["readiness_before_failure"]:
        failures.append("Lifecycle validation failure did not restore readiness state.")
    if rollback["renderer_setup_after_failure"] != rollback["renderer_setup_before_failure"]:
        failures.append("Lifecycle validation failure did not restore renderer setup.")
    if isolation["entry_b"]["lifecycle"] != isolation["entry_b_before"]["lifecycle"]:
        failures.append("Entry B lifecycle changed during entry A durable token operation.")
    if isolation["entry_b"]["token_present"] != isolation["entry_b_before"]["token_present"]:
        failures.append("Entry B token state changed during entry A durable token operation.")
    if not all(
        leakage[key]
        for key in (
            "tokens_absent_from_lifecycle_state",
            "tokens_absent_from_setup_results",
            "tokens_absent_from_repair_issue_metadata",
            "tokens_absent_from_dashboard_card_metadata",
            "tokens_absent_from_model_provider_metadata",
            "tokens_absent_from_evidence_payload",
            "lifecycle_absent_from_dashboard_payload",
            "repair_issue_absent_from_dashboard_payload",
            "endpoint_absent_from_dashboard_payload",
        )
    ):
        failures.append("Durable token lifecycle leaked token material or internals.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("Durable token lifecycle reported forbidden side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("Durable token lifecycle did not report expected allowed side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "restore": restore,
        "repair_issue": repair_issue,
        "disabled": disabled,
        "explicit": explicit,
        "invalid": invalid,
        "setup_failure": setup_failure,
        "rollback": rollback,
        "isolation": isolation,
        "leakage": leakage,
        "side_effects": side_effects,
    }


def _setup_lifecycle_hass(
    entry: FakeConfigEntry,
    store: WorkerTokenLifecycleStorageHelper | None = None,
) -> Any:
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    if store is not None:
        hass.data.setdefault(DOMAIN, {})[DATA_WORKER_TOKEN_LIFECYCLE_STORE] = store
    setup_accepted = _run(async_setup_entry(hass, entry))
    if not setup_accepted:
        raise AssertionError(f"async_setup_entry rejected {entry.entry_id}")
    return hass


def _lifecycle_store(hass: Any) -> WorkerTokenLifecycleStorageHelper:
    return hass.data[DOMAIN][DATA_WORKER_TOKEN_LIFECYCLE_STORE]


def _validate_lifecycle(lifecycle: dict[str, Any], root) -> dict[str, Any]:
    try:
        validate_contract("integration-worker-token-lifecycle-state", lifecycle, repo_root=root)
    except ContractValidationError as exc:
        return {
            "accepted": False,
            "code": "contract_validation_failed",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "lifecycle_id": lifecycle["lifecycle_id"],
        "config_entry_id": lifecycle["config_entry_id"],
        "status": lifecycle["status"],
        "authorization": lifecycle["token"]["authorization"],
        "repair_issue_present": lifecycle["repair_issue"]["present"],
    }
