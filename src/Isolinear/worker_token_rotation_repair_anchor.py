from __future__ import annotations

from copy import deepcopy
from typing import Any

import custom_components.isolinear.worker_readiness as worker_readiness
from custom_components.isolinear.const import DOMAIN
from custom_components.isolinear.worker_readiness import (
    DATA_WORKER_READINESS,
    DATA_WORKER_READINESS_SETUP,
    repair_integration_worker_token,
    rotate_integration_worker_token,
)
from custom_components.isolinear.worker_renderer import (
    DATA_WORKER_RENDER_CLIENT,
    DATA_WORKER_RENDER_SETUP,
    DATA_WORKER_RENDER_TOKEN,
    setup_worker_renderer,
    worker_client_token,
)

from .dashboard_card_anchor import repo_root
from .job_orchestration_scaffold_anchor import _fake_hass
from .websocket_command_registration_anchor import FakeWebSocketApiModule
from .worker_token_provisioning_readiness_anchor import (
    WORKER_READINESS_SECOND_TOKEN,
    WORKER_READINESS_TEST_TOKEN,
    CountingTokenFactory,
    _entry_data,
    _readiness,
    _setup_readiness_hass,
    _validate_readiness,
    _worker_entry,
)


WORKER_ROTATED_TOKEN = "test-worker-rotated-token-222222222"
WORKER_REPAIRED_TOKEN = "test-worker-repaired-token-333333333"

WORKER_TOKEN_ROTATION_REPAIR_FILES = [
    "custom_components/isolinear/worker_readiness.py",
    "custom_components/isolinear/worker_renderer.py",
    "docs/schemas/integration-worker-readiness.schema.json",
    "docs/specs/home-assistant-worker-token-rotation-repair-scaffold-spec.md",
    "bdd/integration/home-assistant-worker-token-rotation-repair-scaffold-bdd.md",
    "bdd/integration/home-assistant-worker-token-rotation-repair-scaffold-evidence.md",
    "docs/evals/home_assistant_worker_token_rotation_repair_scaffold.yaml",
    "tests/test_worker_token_rotation_repair_anchor.py",
    "evals/home_assistant_worker_token_rotation_repair_scaffold.py",
    "src/Isolinear/worker_token_rotation_repair_anchor.py",
]

WORKER_TOKEN_ROTATION_REPAIR_FORBIDDEN_SIDE_EFFECT_KEYS = [
    "home_assistant_history_read",
    "semantic_memory_called",
    "home_assistant_service_or_state_mutation_called",
    "worker_called",
    "worker_health_check_called",
    "chart_rendering_called",
    "chart_artifact_written",
    "durable_token_storage_written",
    "retry_behavior_called",
    "automatic_progress_task_called",
    "worker_streaming_called",
    "token_leaked_to_card",
    "token_leaked_to_model_provider",
]


def verify_worker_token_rotation_repair_files(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = {
        path: (root / path).exists()
        for path in WORKER_TOKEN_ROTATION_REPAIR_FILES
    }
    return {
        "files": files,
        "all_files_present": all(files.values()),
    }


def verify_rotation_invalidates_old_token_and_refreshes_readiness(root=None) -> dict[str, Any]:
    root = root or repo_root()
    entry = _worker_entry("worker-rotation-entry")
    hass = _setup_readiness_hass(entry)
    initial_provision = worker_readiness.provision_integration_worker_token(
        hass,
        entry.entry_id,
        token_factory=CountingTokenFactory(WORKER_READINESS_TEST_TOKEN),
    )
    initial_renderer_setup = setup_worker_renderer(hass, entry)
    old_renderer_client = _entry_data(hass, entry.entry_id).get(DATA_WORKER_RENDER_CLIENT)
    token_factory = CountingTokenFactory(WORKER_ROTATED_TOKEN)

    rotation = rotate_integration_worker_token(
        hass,
        entry.entry_id,
        token_factory=token_factory,
    )
    entry_data = _entry_data(hass, entry.entry_id)
    readiness = _readiness(hass, entry.entry_id)
    renderer_client = entry_data.get(DATA_WORKER_RENDER_CLIENT)

    return {
        "initial_provision": initial_provision,
        "initial_renderer_setup": initial_renderer_setup,
        "rotation": rotation,
        "readiness": readiness,
        "readiness_validation": _validate_readiness(readiness, root),
        "renderer_setup": deepcopy(entry_data[DATA_WORKER_RENDER_SETUP]),
        "renderer_client_refreshed": renderer_client is not old_renderer_client,
        "stored_token_is_new": entry_data.get(DATA_WORKER_RENDER_TOKEN) == WORKER_ROTATED_TOKEN,
        "renderer_client_uses_new_token": worker_client_token(renderer_client) == WORKER_ROTATED_TOKEN,
        "token_factory_call_count": token_factory.calls,
    }


def verify_missing_token_repair_records_ready_state(root=None) -> dict[str, Any]:
    root = root or repo_root()
    entry = _worker_entry("worker-repair-entry")
    hass = _setup_readiness_hass(entry)
    initial_readiness = _readiness(hass, entry.entry_id)
    token_factory = CountingTokenFactory(WORKER_REPAIRED_TOKEN)

    repair = repair_integration_worker_token(
        hass,
        entry.entry_id,
        token_factory=token_factory,
    )
    entry_data = _entry_data(hass, entry.entry_id)
    readiness = _readiness(hass, entry.entry_id)
    renderer_client = entry_data.get(DATA_WORKER_RENDER_CLIENT)

    return {
        "initial_readiness": initial_readiness,
        "repair": repair,
        "readiness": readiness,
        "readiness_validation": _validate_readiness(readiness, root),
        "renderer_setup": deepcopy(entry_data[DATA_WORKER_RENDER_SETUP]),
        "stored_token_is_repaired": entry_data.get(DATA_WORKER_RENDER_TOKEN) == WORKER_REPAIRED_TOKEN,
        "renderer_client_uses_repaired_token": worker_client_token(renderer_client) == WORKER_REPAIRED_TOKEN,
        "token_factory_call_count": token_factory.calls,
    }


def verify_readiness_validation_failure_rolls_back_rotation(root=None) -> dict[str, Any]:
    root = root or repo_root()
    entry = _worker_entry("worker-rotation-rollback-entry")
    hass = _setup_readiness_hass(entry)
    worker_readiness.provision_integration_worker_token(
        hass,
        entry.entry_id,
        token_factory=CountingTokenFactory(WORKER_READINESS_TEST_TOKEN),
    )
    setup_worker_renderer(hass, entry)
    entry_data = _entry_data(hass, entry.entry_id)
    old_renderer_client = entry_data.get(DATA_WORKER_RENDER_CLIENT)
    stored_readiness_before = deepcopy(entry_data[DATA_WORKER_READINESS])
    stored_renderer_setup_before = deepcopy(entry_data[DATA_WORKER_RENDER_SETUP])
    token_factory = CountingTokenFactory(WORKER_ROTATED_TOKEN)
    original_schema_path = worker_readiness.WORKER_READINESS_SCHEMA_PATH
    try:
        worker_readiness.WORKER_READINESS_SCHEMA_PATH = root / "docs" / "schemas" / "missing-worker-readiness.schema.json"
        rotation = rotate_integration_worker_token(
            hass,
            entry.entry_id,
            token_factory=token_factory,
        )
    finally:
        worker_readiness.WORKER_READINESS_SCHEMA_PATH = original_schema_path

    return {
        "rotation": rotation,
        "token_factory_call_count": token_factory.calls,
        "stored_token_restored": entry_data.get(DATA_WORKER_RENDER_TOKEN) == WORKER_READINESS_TEST_TOKEN,
        "rotated_token_absent_after_failure": entry_data.get(DATA_WORKER_RENDER_TOKEN) != WORKER_ROTATED_TOKEN,
        "old_renderer_client_restored": entry_data.get(DATA_WORKER_RENDER_CLIENT) is old_renderer_client,
        "stored_readiness_before_failure": stored_readiness_before,
        "stored_readiness_after_failure": deepcopy(entry_data[DATA_WORKER_READINESS]),
        "stored_renderer_setup_before_failure": stored_renderer_setup_before,
        "stored_renderer_setup_after_failure": deepcopy(entry_data[DATA_WORKER_RENDER_SETUP]),
    }


def verify_unknown_worker_token_rotation_repair_rejected_before_side_effects() -> dict[str, Any]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    rotation_factory = CountingTokenFactory(WORKER_ROTATED_TOKEN)
    repair_factory = CountingTokenFactory(WORKER_REPAIRED_TOKEN)

    rotation = rotate_integration_worker_token(
        hass,
        "missing-worker-rotation-entry",
        token_factory=rotation_factory,
    )
    repair = repair_integration_worker_token(
        hass,
        "missing-worker-rotation-entry",
        token_factory=repair_factory,
    )
    domain_data = hass.data.get(DOMAIN, {})

    return {
        "rotation": rotation,
        "repair": repair,
        "rotation_token_factory_call_count": rotation_factory.calls,
        "repair_token_factory_call_count": repair_factory.calls,
        "entry_created": "missing-worker-rotation-entry" in domain_data,
        "readiness_written": (
            isinstance(domain_data.get("missing-worker-rotation-entry"), dict)
            and DATA_WORKER_READINESS in domain_data["missing-worker-rotation-entry"]
        ),
    }


def verify_cross_entry_worker_token_request_rejected_before_side_effects() -> dict[str, Any]:
    websocket_api_module = FakeWebSocketApiModule()
    hass = _fake_hass(websocket_api_module)
    entry_a = _worker_entry("worker-cross-entry-a")
    entry_b = _worker_entry("worker-cross-entry-b")
    from custom_components.isolinear import async_setup_entry
    from .job_orchestration_scaffold_anchor import _run

    _run(async_setup_entry(hass, entry_a))
    _run(async_setup_entry(hass, entry_b))
    worker_readiness.provision_integration_worker_token(
        hass,
        entry_a.entry_id,
        token_factory=CountingTokenFactory(WORKER_READINESS_TEST_TOKEN),
    )
    worker_readiness.provision_integration_worker_token(
        hass,
        entry_b.entry_id,
        token_factory=CountingTokenFactory(WORKER_READINESS_SECOND_TOKEN),
    )
    entry_a_readiness_before = _readiness(hass, entry_a.entry_id)
    entry_b_readiness_before = _readiness(hass, entry_b.entry_id)
    token_factory = CountingTokenFactory(WORKER_ROTATED_TOKEN)

    rotation = rotate_integration_worker_token(
        hass,
        entry_b.entry_id,
        requesting_entry_id=entry_a.entry_id,
        token_factory=token_factory,
    )

    return {
        "rotation": rotation,
        "token_factory_call_count": token_factory.calls,
        "entry_a_token_unchanged": (
            _entry_data(hass, entry_a.entry_id).get(DATA_WORKER_RENDER_TOKEN) == WORKER_READINESS_TEST_TOKEN
        ),
        "entry_b_token_unchanged": (
            _entry_data(hass, entry_b.entry_id).get(DATA_WORKER_RENDER_TOKEN) == WORKER_READINESS_SECOND_TOKEN
        ),
        "entry_a_readiness_before": entry_a_readiness_before,
        "entry_a_readiness": _readiness(hass, entry_a.entry_id),
        "entry_b_readiness_before": entry_b_readiness_before,
        "entry_b_readiness": _readiness(hass, entry_b.entry_id),
    }


def verify_rotated_and_repaired_tokens_do_not_leak(root=None) -> dict[str, Any]:
    root = root or repo_root()
    rotation_result = verify_rotation_invalidates_old_token_and_refreshes_readiness(root)
    repair_result = verify_missing_token_repair_records_ready_state(root)
    rotation = rotation_result["rotation"]
    repair = repair_result["repair"]
    tokens = [WORKER_READINESS_TEST_TOKEN, WORKER_ROTATED_TOKEN, WORKER_REPAIRED_TOKEN]
    dashboard_visible_payload = {
        "card_snapshot_payload": {
            "accepted": True,
            "code": "no_card_token_rotation_or_repair_command",
            "worker_token_rotation": None,
            "worker_token_repair": None,
        },
    }
    evidence_payload = {
        "rotation": rotation,
        "rotation_readiness": rotation_result["readiness"],
        "repair": repair,
        "repair_readiness": repair_result["readiness"],
    }

    return {
        "rotation_readiness_validation": rotation_result["readiness_validation"],
        "repair_readiness_validation": repair_result["readiness_validation"],
        "rotation_authorization": rotation_result["readiness"]["token"]["authorization"],
        "repair_authorization": repair_result["readiness"]["token"]["authorization"],
        "tokens_absent_from_readiness": not any(
            token in str([rotation_result["readiness"], repair_result["readiness"]])
            for token in tokens
        ),
        "tokens_absent_from_setup": not any(
            token in str([rotation_result["renderer_setup"], repair_result["renderer_setup"]])
            for token in tokens
        ),
        "tokens_absent_from_dashboard_card_metadata": not any(
            token in str(
                [
                    rotation["readiness"]["orchestration"],
                    repair["readiness"]["orchestration"],
                    dashboard_visible_payload,
                ]
            )
            for token in tokens
        ),
        "tokens_absent_from_model_provider_metadata": not any(
            token in str(
                [
                    rotation_result["initial_provision"].get("validation"),
                    repair_result["initial_readiness"].get("validation"),
                ]
            )
            for token in tokens
        ),
        "tokens_absent_from_evidence_payload": not any(token in str(evidence_payload) for token in tokens),
        "rotation_internals_absent_from_dashboard_payload": "worker_token_rotated" not in str(dashboard_visible_payload),
        "repair_internals_absent_from_dashboard_payload": "worker_token_repaired" not in str(dashboard_visible_payload),
    }


def verify_worker_token_rotation_repair_side_effect_boundaries() -> dict[str, Any]:
    rotation = verify_rotation_invalidates_old_token_and_refreshes_readiness()
    repair = verify_missing_token_repair_records_ready_state()
    rollback = verify_readiness_validation_failure_rolls_back_rotation()
    unknown = verify_unknown_worker_token_rotation_repair_rejected_before_side_effects()
    cross_entry = verify_cross_entry_worker_token_request_rejected_before_side_effects()

    observed = [
        {"name": "rotation", **rotation["rotation"]["orchestration"]},
        {"name": "rotation_readiness", **rotation["readiness"]["orchestration"]},
        {"name": "repair", **repair["repair"]["orchestration"]},
        {"name": "repair_readiness", **repair["readiness"]["orchestration"]},
        {"name": "rollback", **rollback["rotation"]["orchestration"]},
        {"name": "unknown_rotation", **unknown["rotation"]["orchestration"]},
        {"name": "unknown_repair", **unknown["repair"]["orchestration"]},
        {"name": "cross_entry", **cross_entry["rotation"]["orchestration"]},
    ]
    forbidden_aggregate = {
        key: any(item.get(key) for item in observed)
        for key in WORKER_TOKEN_ROTATION_REPAIR_FORBIDDEN_SIDE_EFFECT_KEYS
    }
    allowed_aggregate = {
        "token_generated": any(item.get("token_generated") for item in observed),
        "token_stored": any(item.get("token_stored") for item in observed),
        "token_rotation_called": any(item.get("token_rotation_called") for item in observed),
        "readiness_bookkeeping_written": any(item.get("readiness_bookkeeping_written") for item in observed),
        "worker_renderer_setup_gated": any(item.get("worker_renderer_setup_gated") for item in observed),
    }
    return {
        "expected_forbidden": {key: False for key in WORKER_TOKEN_ROTATION_REPAIR_FORBIDDEN_SIDE_EFFECT_KEYS},
        "observed": observed,
        "forbidden_aggregate": forbidden_aggregate,
        "allowed_aggregate": allowed_aggregate,
    }


def verify_worker_token_rotation_repair_anchor(root=None) -> dict[str, Any]:
    root = root or repo_root()
    files = verify_worker_token_rotation_repair_files(root)
    rotation = verify_rotation_invalidates_old_token_and_refreshes_readiness(root)
    repair = verify_missing_token_repair_records_ready_state(root)
    rollback = verify_readiness_validation_failure_rolls_back_rotation(root)
    unknown = verify_unknown_worker_token_rotation_repair_rejected_before_side_effects()
    cross_entry = verify_cross_entry_worker_token_request_rejected_before_side_effects()
    leakage = verify_rotated_and_repaired_tokens_do_not_leak(root)
    side_effects = verify_worker_token_rotation_repair_side_effect_boundaries()

    failures = []
    if not files["all_files_present"]:
        failures.append("One or more worker token rotation/repair scaffold files are missing.")
    if rotation["readiness"]["status"] != "ready" or not rotation["readiness_validation"]["accepted"]:
        failures.append("Rotation did not store schema-valid ready readiness metadata.")
    if not rotation["rotation"]["old_token_invalidated"]:
        failures.append("Rotation did not invalidate the old worker token.")
    if not rotation["renderer_client_refreshed"] or not rotation["renderer_client_uses_new_token"]:
        failures.append("Rotation did not refresh the same-entry worker renderer client.")
    if repair["readiness"]["status"] != "ready" or not repair["readiness_validation"]["accepted"]:
        failures.append("Repair did not store schema-valid ready readiness metadata.")
    if not repair["renderer_client_uses_repaired_token"]:
        failures.append("Repair did not enable a worker renderer client with the repaired token.")
    if rollback["rotation"]["code"] != "invalid_integration_worker_readiness":
        failures.append("Validation failure did not return the readiness validation failure code.")
    if not rollback["stored_token_restored"] or not rollback["rotated_token_absent_after_failure"]:
        failures.append("Validation failure did not restore the old worker token.")
    if not rollback["old_renderer_client_restored"]:
        failures.append("Validation failure did not restore the old worker renderer client.")
    if rollback["stored_readiness_after_failure"] != rollback["stored_readiness_before_failure"]:
        failures.append("Validation failure did not restore old readiness metadata.")
    if unknown["rotation_token_factory_call_count"] or unknown["repair_token_factory_call_count"]:
        failures.append("Unknown config entry generated a worker token.")
    if unknown["entry_created"] or unknown["readiness_written"]:
        failures.append("Unknown config entry created token/readiness state.")
    if cross_entry["token_factory_call_count"] != 0:
        failures.append("Cross-entry request generated a worker token.")
    if cross_entry["entry_a_readiness"] != cross_entry["entry_a_readiness_before"]:
        failures.append("Cross-entry request changed requesting entry readiness.")
    if cross_entry["entry_b_readiness"] != cross_entry["entry_b_readiness_before"]:
        failures.append("Cross-entry request changed target entry readiness.")
    if not all(
        leakage[key]
        for key in (
            "tokens_absent_from_readiness",
            "tokens_absent_from_setup",
            "tokens_absent_from_dashboard_card_metadata",
            "tokens_absent_from_model_provider_metadata",
            "tokens_absent_from_evidence_payload",
            "rotation_internals_absent_from_dashboard_payload",
            "repair_internals_absent_from_dashboard_payload",
        )
    ):
        failures.append("Worker token rotation/repair leaked token material or internals.")
    if any(side_effects["forbidden_aggregate"].values()):
        failures.append("Worker token rotation/repair scaffold reported forbidden side effects.")
    if not all(side_effects["allowed_aggregate"].values()):
        failures.append("Worker token rotation/repair scaffold did not report expected allowed side effects.")

    return {
        "passed": not failures,
        "failures": failures,
        "files": files,
        "rotation": rotation,
        "repair": repair,
        "rollback": rollback,
        "unknown": unknown,
        "cross_entry": cross_entry,
        "leakage": leakage,
        "side_effects": side_effects,
    }
