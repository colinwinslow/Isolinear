"""Durable worker token lifecycle boundary for Isolinear."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from .const import DOMAIN
from .job_state import JobStateSnapshotValidationError, _validate_json_schema
from .worker_readiness import (
    DATA_WORKER_READINESS,
    DATA_WORKER_READINESS_SETUP,
    provision_integration_worker_token,
    repair_integration_worker_token,
    rotate_integration_worker_token,
)
from .worker_renderer import (
    DATA_WORKER_RENDER_CLIENT,
    DATA_WORKER_RENDER_SETUP,
    DATA_WORKER_RENDER_TOKEN,
    is_valid_worker_render_token,
    redact_authorization,
)


DATA_WORKER_TOKEN_LIFECYCLE = "worker_token_lifecycle"
DATA_WORKER_TOKEN_LIFECYCLE_SETUP = "worker_token_lifecycle_setup"
DATA_WORKER_TOKEN_LIFECYCLE_STORE = "worker_token_lifecycle_storage_helper"

TOKEN_LIFECYCLE_STORAGE_KEY = "isolinear_worker_token_lifecycle"
TOKEN_LIFECYCLE_STORAGE_VERSION = 1
TOKEN_LIFECYCLE_FORBIDDEN_RE = re.compile(
    r"bearer\s+(?!<redacted>)\S+|access_token|home_assistant_token|"
    r"long_lived_access_token|test-worker-[a-z0-9-]+-token-[0-9]+",
    re.IGNORECASE,
)
WORKER_TOKEN_LIFECYCLE_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "schemas"
    / "integration-worker-token-lifecycle-state.schema.json"
)

try:
    from homeassistant.helpers.storage import Store as HomeAssistantStore
except ImportError:  # pragma: no cover - Home Assistant is absent in verifier tests.
    HomeAssistantStore = None


class WorkerTokenLifecycleStorageHelper:
    """Small storage-helper surface for durable worker token lifecycle state."""

    def __init__(self, *, ha_store: Any | None = None) -> None:
        self.storage_key = TOKEN_LIFECYCLE_STORAGE_KEY
        self.version = TOKEN_LIFECYCLE_STORAGE_VERSION
        self._ha_store = ha_store
        self.backend = (
            "home_assistant_storage_helper"
            if ha_store is not None
            else "in_memory_scaffold_storage_helper"
        )
        self.data: dict[str, Any] = {
            "version": self.version,
            "entries": {},
        }
        self._deleted_entry_ids: set[str] = set()

    async def async_load(self) -> dict[str, Any]:
        """Load persisted token lifecycle entries when Home Assistant storage is available."""
        async_load = getattr(self._ha_store, "async_load", None)
        if not callable(async_load):
            return self.summary()

        loaded = await async_load()
        if (
            isinstance(loaded, dict)
            and loaded.get("version") == self.version
            and isinstance(loaded.get("entries"), dict)
        ):
            current_entries = self.data.setdefault("entries", {})
            for entry_id, entry in loaded["entries"].items():
                if (
                    entry_id not in current_entries
                    and entry_id not in self._deleted_entry_ids
                    and _loaded_lifecycle_entry_is_valid(entry_id, entry)
                ):
                    current_entries[entry_id] = deepcopy(entry)
        return self.summary()

    def read_lifecycle_entry(self, entry_id: str) -> dict[str, Any] | None:
        entry = self.data["entries"].get(entry_id)
        if not _loaded_lifecycle_entry_is_valid(entry_id, entry):
            return None
        return deepcopy(entry)

    def private_token_for(self, entry_id: str) -> str | None:
        entry = self.read_lifecycle_entry(entry_id)
        token = entry.get("token") if isinstance(entry, dict) else None
        return token if is_valid_worker_render_token(token) else None

    def write_token_entry(
        self,
        entry_id: str,
        token: str | None,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """Write one raw-token/private plus redacted-state lifecycle entry."""
        if token is not None and not is_valid_worker_render_token(token):
            return _lifecycle_rejection("invalid_integration_worker_token_lifecycle")
        validation = validate_worker_token_lifecycle_state_contract(state)
        if not validation["accepted"] or state.get("config_entry_id") != entry_id:
            return _lifecycle_rejection("invalid_integration_worker_token_lifecycle", validation=validation)

        self._deleted_entry_ids.discard(entry_id)
        self.data["entries"][entry_id] = {
            "token": token,
            "state": deepcopy(state),
        }
        self._schedule_save()
        return {
            "accepted": True,
            "code": "worker_token_lifecycle_entry_written",
            "entry_id": entry_id,
            "summary": self.summary(),
            "validation": validation,
        }

    def delete_token_entry(self, entry_id: str) -> bool:
        self._deleted_entry_ids.add(entry_id)
        removed = self.data["entries"].pop(entry_id, None) is not None
        self._schedule_save()
        return removed

    def summary(self) -> dict[str, Any]:
        return {
            "storage_key": self.storage_key,
            "version": self.version,
            "backend": self.backend,
            "entry_ids": sorted(self.data["entries"]),
            "entry_count": len(self.data["entries"]),
        }

    def _schedule_save(self) -> None:
        async_delay_save = getattr(self._ha_store, "async_delay_save", None)
        if callable(async_delay_save):
            async_delay_save(lambda: deepcopy(self.data), 0)


async def async_setup_worker_token_lifecycle(hass: Any, entry: Any) -> dict[str, Any]:
    """Load and restore durable worker token state before readiness setup."""
    store = get_worker_token_lifecycle_storage(hass)
    await store.async_load()
    entry_id = getattr(entry, "entry_id", "scaffold-entry")
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    entry_data["entry"] = entry

    endpoint_configured = _worker_endpoint_configured(entry)
    in_memory_token = entry_data.get(DATA_WORKER_RENDER_TOKEN)
    persisted_token = store.private_token_for(entry_id)
    token_to_store: str | None = None
    token_to_restore: str | None = None

    if not endpoint_configured:
        state = build_worker_token_lifecycle_state(
            entry_id=entry_id,
            endpoint_configured=False,
            token=None,
            code="worker_endpoint_missing",
            durable_token_storage_loaded=True,
            durable_token_storage_written=True,
        )
    elif is_valid_worker_render_token(in_memory_token):
        token_to_store = in_memory_token
        state = build_worker_token_lifecycle_state(
            entry_id=entry_id,
            endpoint_configured=True,
            token=in_memory_token,
            code="worker_token_persisted",
            persisted=True,
            durable_token_storage_loaded=True,
            durable_token_storage_written=True,
        )
    elif is_valid_worker_render_token(persisted_token):
        token_to_store = persisted_token
        token_to_restore = persisted_token
        state = build_worker_token_lifecycle_state(
            entry_id=entry_id,
            endpoint_configured=True,
            token=persisted_token,
            code="worker_token_restored_from_storage",
            persisted=True,
            restored=True,
            durable_token_storage_loaded=True,
            durable_token_storage_written=True,
            in_memory_token_restored=True,
            automatic_token_restore_called=True,
            repair_issue_deleted=True,
        )
    else:
        state = build_worker_token_lifecycle_state(
            entry_id=entry_id,
            endpoint_configured=True,
            token=None,
            code="worker_token_repair_issue_created",
            durable_token_storage_loaded=True,
            durable_token_storage_written=True,
            repair_issue_created=True,
        )

    write_result = store.write_token_entry(entry_id, token_to_store, state)
    if not write_result["accepted"]:
        result = _lifecycle_rejection(write_result["code"], validation=write_result.get("validation"))
    else:
        entry_data[DATA_WORKER_TOKEN_LIFECYCLE] = deepcopy(state)
        if is_valid_worker_render_token(token_to_restore):
            entry_data[DATA_WORKER_RENDER_TOKEN] = token_to_restore
        result = {
            "accepted": True,
            "code": state["code"],
            "entry_id": entry_id,
            "enabled": state["status"] == "ready",
            "lifecycle": deepcopy(state),
            "storage": store.summary(),
            "validation": write_result["validation"],
            "orchestration": deepcopy(state["orchestration"]),
        }
    entry_data[DATA_WORKER_TOKEN_LIFECYCLE_SETUP] = deepcopy(result)
    return result


def provision_durable_integration_worker_token(
    hass: Any,
    entry_id: str,
    *,
    token_factory: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Explicitly provision and persist one integration-owned worker token."""
    return _durable_token_operation(
        hass,
        entry_id,
        operation=lambda: provision_integration_worker_token(
            hass,
            entry_id,
            token_factory=token_factory,
        ),
    )


def rotate_durable_integration_worker_token(
    hass: Any,
    entry_id: str,
    *,
    token_factory: Callable[[], str] | None = None,
    requesting_entry_id: str | None = None,
) -> dict[str, Any]:
    """Explicitly rotate and persist one integration-owned worker token."""
    return _durable_token_operation(
        hass,
        entry_id,
        operation=lambda: rotate_integration_worker_token(
            hass,
            entry_id,
            token_factory=token_factory,
            requesting_entry_id=requesting_entry_id,
        ),
    )


def repair_durable_integration_worker_token(
    hass: Any,
    entry_id: str,
    *,
    token_factory: Callable[[], str] | None = None,
    requesting_entry_id: str | None = None,
) -> dict[str, Any]:
    """Explicitly repair and persist one integration-owned worker token."""
    return _durable_token_operation(
        hass,
        entry_id,
        operation=lambda: repair_integration_worker_token(
            hass,
            entry_id,
            token_factory=token_factory,
            requesting_entry_id=requesting_entry_id,
        ),
    )


def get_worker_token_lifecycle_storage(hass: Any) -> WorkerTokenLifecycleStorageHelper:
    """Return the integration-owned worker token lifecycle storage helper."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    store = domain_data.get(DATA_WORKER_TOKEN_LIFECYCLE_STORE)
    if isinstance(store, WorkerTokenLifecycleStorageHelper):
        return store
    store = WorkerTokenLifecycleStorageHelper(ha_store=_build_home_assistant_store(hass))
    domain_data[DATA_WORKER_TOKEN_LIFECYCLE_STORE] = store
    return store


def get_worker_token_lifecycle_state(hass: Any, entry_id: str) -> dict[str, Any] | None:
    """Return the latest redacted lifecycle state for one config entry."""
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    state = entry_data.get(DATA_WORKER_TOKEN_LIFECYCLE) if isinstance(entry_data, dict) else None
    return deepcopy(state) if isinstance(state, dict) else None


def build_worker_token_lifecycle_state(
    *,
    entry_id: str,
    endpoint_configured: bool,
    token: Any,
    code: str,
    persisted: bool = False,
    restored: bool = False,
    durable_token_storage_loaded: bool = False,
    durable_token_storage_written: bool = False,
    durable_token_storage_deleted: bool = False,
    in_memory_token_restored: bool = False,
    token_generated: bool = False,
    token_stored: bool = False,
    automatic_token_restore_called: bool = False,
    repair_issue_created: bool = False,
    repair_issue_deleted: bool = False,
    readiness_bookkeeping_written: bool = False,
    worker_renderer_setup_gated: bool = False,
) -> dict[str, Any]:
    """Build a redacted IntegrationWorkerTokenLifecycleState payload."""
    token_valid = is_valid_worker_render_token(token)
    if not endpoint_configured:
        status = "disabled"
        token_source = "missing"
        issue = _repair_issue_absent()
        warnings = ["worker_endpoint_not_configured", "worker_token_lifecycle_disabled"]
    elif token_valid:
        status = "ready"
        token_source = "integration_owned"
        issue = _repair_issue_absent()
        warnings = ["worker_token_redacted", "worker_token_lifecycle_ready"]
    else:
        status = "not_ready"
        token_source = "invalid" if isinstance(token, str) and token.strip() else "missing"
        issue = _repair_issue_present(entry_id)
        warnings = ["worker_token_missing", "worker_token_repair_issue_available"]

    return {
        "lifecycle_id": f"{entry_id}-worker-token-lifecycle-001",
        "type": "isolinear_worker_token_lifecycle",
        "config_entry_id": entry_id,
        "status": status,
        "code": code,
        "token": {
            "present": token_valid,
            "persisted": persisted and token_valid,
            "restored": restored and token_valid,
            "source": token_source,
            "authorization": redact_authorization(f"Bearer {token}") if token_valid else "<missing>",
        },
        "repair_issue": issue,
        "validation": {
            "status": "pass",
            "summary": "Durable worker token lifecycle state validates before storage.",
            "checks": [
                {"name": "config_entry_scoped", "status": "pass"},
                {"name": "worker_authorization_redacted", "status": "pass"},
                {"name": "repair_issue_redacted", "status": "pass"},
            ],
        },
        "warnings": warnings,
        "orchestration": worker_token_lifecycle_side_effects(
            durable_token_storage_loaded=durable_token_storage_loaded,
            durable_token_storage_written=durable_token_storage_written,
            durable_token_storage_deleted=durable_token_storage_deleted,
            in_memory_token_restored=in_memory_token_restored,
            token_generated=token_generated,
            token_stored=token_stored,
            automatic_token_restore_called=automatic_token_restore_called,
            repair_issue_created=repair_issue_created or issue["present"],
            repair_issue_deleted=repair_issue_deleted,
            readiness_bookkeeping_written=readiness_bookkeeping_written,
            worker_renderer_setup_gated=worker_renderer_setup_gated,
        ),
    }


def validate_worker_token_lifecycle_state_contract(state: Any) -> dict[str, Any]:
    """Validate IntegrationWorkerTokenLifecycleState against the repo JSON Schema."""
    try:
        schema = json.loads(WORKER_TOKEN_LIFECYCLE_SCHEMA_PATH.read_text(encoding="utf-8"))
        _validate_json_schema(state, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, JobStateSnapshotValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_integration_worker_token_lifecycle",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(WORKER_TOKEN_LIFECYCLE_SCHEMA_PATH),
    }


def worker_token_lifecycle_side_effects(
    *,
    durable_token_storage_loaded: bool = False,
    durable_token_storage_written: bool = False,
    durable_token_storage_deleted: bool = False,
    in_memory_token_restored: bool = False,
    token_generated: bool = False,
    token_stored: bool = False,
    setup_time_token_generation_called: bool = False,
    automatic_token_restore_called: bool = False,
    automatic_token_repair_execution_called: bool = False,
    repair_issue_created: bool = False,
    repair_issue_deleted: bool = False,
    readiness_bookkeeping_written: bool = False,
    worker_renderer_setup_gated: bool = False,
) -> dict[str, bool]:
    """Return side-effect accounting for durable worker token lifecycle."""
    return {
        "durable_token_storage_loaded": durable_token_storage_loaded,
        "durable_token_storage_written": durable_token_storage_written,
        "durable_token_storage_deleted": durable_token_storage_deleted,
        "in_memory_token_restored": in_memory_token_restored,
        "token_generated": token_generated,
        "token_stored": token_stored,
        "setup_time_token_generation_called": setup_time_token_generation_called,
        "automatic_token_restore_called": automatic_token_restore_called,
        "automatic_token_repair_execution_called": automatic_token_repair_execution_called,
        "repair_issue_created": repair_issue_created,
        "repair_issue_deleted": repair_issue_deleted,
        "readiness_bookkeeping_written": readiness_bookkeeping_written,
        "worker_renderer_setup_gated": worker_renderer_setup_gated,
        "home_assistant_history_read": False,
        "semantic_memory_called": False,
        "home_assistant_service_or_state_mutation_called": False,
        "config_entry_options_written": False,
        "recorder_called": False,
        "worker_render_called": False,
        "worker_health_call": False,
        "model_provider_called": False,
        "chart_rendering_called": False,
        "chart_artifact_written": False,
        "durable_retry_storage_written": False,
        "external_queue_or_database_called": False,
        "scheduler_called": False,
        "automatic_rotation_called": False,
        "dashboard_command_registered": False,
        "token_leaked_to_card": False,
        "token_leaked_to_model_provider": False,
    }


def _durable_token_operation(
    hass: Any,
    entry_id: str,
    *,
    operation: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    domain_data = getattr(hass, "data", {}).get(DOMAIN, {})
    entry_data = domain_data.get(entry_id)
    if not isinstance(entry_data, dict) or entry_data.get("entry") is None:
        return _lifecycle_rejection("unknown_config_entry")

    store = get_worker_token_lifecycle_storage(hass)
    snapshot = _snapshot_lifecycle_state(entry_data, store, entry_id)
    result = operation()
    if not result.get("accepted"):
        return result

    entry = entry_data["entry"]
    token = entry_data.get(DATA_WORKER_RENDER_TOKEN)
    state = build_worker_token_lifecycle_state(
        entry_id=entry_id,
        endpoint_configured=_worker_endpoint_configured(entry),
        token=token,
        code=result.get("code", "worker_token_persisted"),
        persisted=True,
        durable_token_storage_written=True,
        token_generated=bool(result.get("orchestration", {}).get("token_generated")),
        token_stored=is_valid_worker_render_token(token),
        repair_issue_deleted=True,
        readiness_bookkeeping_written=True,
        worker_renderer_setup_gated=True,
    )
    write_result = store.write_token_entry(entry_id, token, state)
    if not write_result["accepted"]:
        _restore_lifecycle_state(entry_data, store, entry_id, snapshot)
        return _lifecycle_rejection(
            "invalid_integration_worker_token_lifecycle",
            validation=write_result.get("validation"),
            orchestration=worker_token_lifecycle_side_effects(
                durable_token_storage_written=False,
                token_generated=bool(result.get("orchestration", {}).get("token_generated")),
                token_stored=False,
            ),
        )

    entry_data[DATA_WORKER_TOKEN_LIFECYCLE] = deepcopy(state)
    result["lifecycle"] = deepcopy(state)
    result["lifecycle_storage"] = store.summary()
    result["lifecycle_validation"] = write_result["validation"]
    return result


def _snapshot_lifecycle_state(
    entry_data: dict[str, Any],
    store: WorkerTokenLifecycleStorageHelper,
    entry_id: str,
) -> dict[str, Any]:
    return {
        DATA_WORKER_RENDER_TOKEN: entry_data.get(DATA_WORKER_RENDER_TOKEN),
        DATA_WORKER_RENDER_CLIENT: entry_data.get(DATA_WORKER_RENDER_CLIENT),
        DATA_WORKER_RENDER_SETUP: deepcopy(entry_data.get(DATA_WORKER_RENDER_SETUP)),
        DATA_WORKER_READINESS: deepcopy(entry_data.get(DATA_WORKER_READINESS)),
        DATA_WORKER_READINESS_SETUP: deepcopy(entry_data.get(DATA_WORKER_READINESS_SETUP)),
        DATA_WORKER_TOKEN_LIFECYCLE: deepcopy(entry_data.get(DATA_WORKER_TOKEN_LIFECYCLE)),
        DATA_WORKER_TOKEN_LIFECYCLE_SETUP: deepcopy(entry_data.get(DATA_WORKER_TOKEN_LIFECYCLE_SETUP)),
        "_has_token": DATA_WORKER_RENDER_TOKEN in entry_data,
        "_has_client": DATA_WORKER_RENDER_CLIENT in entry_data,
        "_has_render_setup": DATA_WORKER_RENDER_SETUP in entry_data,
        "_has_readiness": DATA_WORKER_READINESS in entry_data,
        "_has_readiness_setup": DATA_WORKER_READINESS_SETUP in entry_data,
        "_has_lifecycle": DATA_WORKER_TOKEN_LIFECYCLE in entry_data,
        "_has_lifecycle_setup": DATA_WORKER_TOKEN_LIFECYCLE_SETUP in entry_data,
        "_store_entry": deepcopy(store.data["entries"].get(entry_id)),
        "_store_has_entry": entry_id in store.data["entries"],
    }


def _restore_lifecycle_state(
    entry_data: dict[str, Any],
    store: WorkerTokenLifecycleStorageHelper,
    entry_id: str,
    snapshot: dict[str, Any],
) -> None:
    for key, has_key in (
        (DATA_WORKER_RENDER_TOKEN, "_has_token"),
        (DATA_WORKER_RENDER_CLIENT, "_has_client"),
        (DATA_WORKER_RENDER_SETUP, "_has_render_setup"),
        (DATA_WORKER_READINESS, "_has_readiness"),
        (DATA_WORKER_READINESS_SETUP, "_has_readiness_setup"),
        (DATA_WORKER_TOKEN_LIFECYCLE, "_has_lifecycle"),
        (DATA_WORKER_TOKEN_LIFECYCLE_SETUP, "_has_lifecycle_setup"),
    ):
        if snapshot[has_key]:
            entry_data[key] = (
                snapshot[key]
                if key == DATA_WORKER_RENDER_CLIENT
                else deepcopy(snapshot[key])
            )
        else:
            entry_data.pop(key, None)
    if snapshot["_store_has_entry"]:
        store.data["entries"][entry_id] = deepcopy(snapshot["_store_entry"])
    else:
        store.data["entries"].pop(entry_id, None)


def _loaded_lifecycle_entry_is_valid(entry_id: Any, entry: Any) -> bool:
    if not isinstance(entry_id, str) or not isinstance(entry, dict):
        return False
    token = entry.get("token")
    if token is not None and not is_valid_worker_render_token(token):
        return False
    state = entry.get("state")
    if not isinstance(state, dict) or state.get("config_entry_id") != entry_id:
        return False
    if _lifecycle_state_has_forbidden_text(state):
        return False
    return validate_worker_token_lifecycle_state_contract(state)["accepted"] is True


def _lifecycle_state_has_forbidden_text(state: dict[str, Any]) -> bool:
    return TOKEN_LIFECYCLE_FORBIDDEN_RE.search(str(state)) is not None


def _worker_endpoint_configured(entry: Any) -> bool:
    data = getattr(entry, "data", {}) or {}
    endpoint_url = data.get("worker_endpoint_url") if isinstance(data, dict) else None
    return isinstance(endpoint_url, str) and endpoint_url.strip().startswith(("http://", "https://"))


def _repair_issue_present(entry_id: str) -> dict[str, Any]:
    return {
        "present": True,
        "issue_id": f"{entry_id}-worker-token-repair",
        "surface": "home_assistant_repairs_scaffold",
        "severity": "warning",
        "suggested_action": "manual_token_repair",
        "translation_key": "worker_token_repair_available",
    }


def _repair_issue_absent() -> dict[str, Any]:
    return {
        "present": False,
        "issue_id": None,
        "surface": "none",
        "severity": "none",
        "suggested_action": "none",
        "translation_key": None,
    }


def _build_home_assistant_store(hass: Any) -> Any | None:
    if HomeAssistantStore is None:
        return None
    return HomeAssistantStore(hass, TOKEN_LIFECYCLE_STORAGE_VERSION, TOKEN_LIFECYCLE_STORAGE_KEY)


def _lifecycle_rejection(
    code: str,
    *,
    validation: dict[str, Any] | None = None,
    orchestration: dict[str, bool] | None = None,
) -> dict[str, Any]:
    result = {
        "accepted": False,
        "code": code,
        "enabled": False,
        "orchestration": orchestration or worker_token_lifecycle_side_effects(),
    }
    if validation is not None:
        result["validation"] = validation
    return result
