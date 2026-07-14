"""Home Assistant config-flow and options-flow anchor for Isolinear."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from .config_schema import (
    default_config_data,
    default_options_data,
    redacted_config_result,
    validate_config_and_options,
)
from .const import (
    DOMAIN,
    MODEL_PROVIDER_OLLAMA_COMPATIBLE,
    NAME,
    RENDER_PATH_AUTO,
    SUPPORTED_MODEL_PROVIDER_TYPES,
    SUPPORTED_RENDER_MODES,
    SUPPORTED_RENDER_PATHS,
)
from .worker_token_storage import (
    get_worker_token_storage,
    is_valid_deployment_worker_token,
)


try:  # pragma: no cover - exercised by Home Assistant, not the repo anchor.
    import voluptuous as vol
    from homeassistant import config_entries
    from homeassistant.core import callback
    from homeassistant.helpers.selector import (
        EntitySelector,
        EntitySelectorConfig,
        TextSelector,
        TextSelectorConfig,
        TextSelectorType,
    )
except ImportError:  # pragma: no cover - deterministic fallback for repo tests.
    vol = None
    EntitySelector = None
    EntitySelectorConfig = None
    TextSelector = None
    TextSelectorConfig = None
    TextSelectorType = None

    def callback(func):
        return func

    class _FallbackFlowBase:
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__()

        def async_show_form(self, *, step_id, data_schema=None, errors=None):
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "errors": errors or {},
            }

        def async_create_entry(self, *, title, data, options=None):
            return {
                "type": "create_entry",
                "title": title,
                "data": data,
                "options": options or {},
            }

    class _FallbackConfigFlow(_FallbackFlowBase):
        pass

    class _FallbackOptionsFlow(_FallbackFlowBase):
        pass

    class _FallbackConfigEntries:
        ConfigFlow = _FallbackConfigFlow
        OptionsFlow = _FallbackOptionsFlow

    config_entries = _FallbackConfigEntries()


CONFIG_FLOW_STEP = "user"
OPTIONS_FLOW_STEP = "init"

CONFIG_FLOW_FIELDS = (
    "model_provider_type",
    "model_endpoint_url",
    "planner_model",
    "codegen_model",
    "visual_validator_model",
    "worker_endpoint_url",
)
OPTIONS_FLOW_FIELDS = (
    "default_render_mode",
    "max_codegen_repair_attempts",
    "max_planner_replan_attempts",
    "ollama_timeout_seconds",
    "render_path",
    "entity_allowlist",
)
ENTITY_ALLOWLIST_SELECTOR_METADATA = {
    "type": "entity",
    "multiple": True,
    "storage": "entity_id_list",
}
# ADR-0032: write-only password field; the value lands in worker_token_storage,
# never in persisted options.
WORKER_TOKEN_SELECTOR_METADATA = {
    "type": "text",
    "input_type": "password",
    "storage": "worker_token_storage",
    "write_only": True,
}

NO_FLOW_ORCHESTRATION_CALLS = {
    "worker_called": False,
    "model_provider_called": False,
    "home_assistant_history_called": False,
    "semantic_memory_called": False,
    "home_assistant_mutation_called": False,
    "token_generated": False,
    "dashboard_resource_registered": False,
}


class IsolinearConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create the Isolinear config entry from local-first setup data."""

    VERSION = 1
    MINOR_VERSION = 0

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Create the Isolinear options flow."""
        return IsolinearOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial user setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            result = validate_config_flow_user_input(user_input)
            if result["accepted"]:
                if hasattr(self, "async_set_unique_id"):
                    await self.async_set_unique_id(DOMAIN)
                if hasattr(self, "_abort_if_unique_id_configured"):
                    self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=result["entry_title"],
                    data=result["config_data"],
                    options=result["options_data"],
                )
            errors = result["field_errors"]

        return self.async_show_form(
            step_id=CONFIG_FLOW_STEP,
            data_schema=build_config_flow_schema(user_input),
            errors=errors,
        )


# ADR-0032: the write-only options field carrying the deployment worker token.
# It is extracted BEFORE options validation/persistence, so options data never
# carries the token and config_schema's secret-vocabulary fail-closed check is
# unaffected.
WORKER_TOKEN_OPTIONS_FIELD = "worker_api_token"
WORKER_TOKEN_CLEAR_SENTINEL = "clear"


def extract_worker_token_action(user_input: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split the write-only worker-token field out of options user input.

    Returns ``(action, remaining_input)`` where action is one of
    ``{"kind": "keep"}`` (field absent/empty — stored token unchanged),
    ``{"kind": "clear"}`` (the literal ``clear``),
    ``{"kind": "save", "token": <token>}`` (a valid >=24-char token), or
    ``{"kind": "too_short"}`` (anything else — form error, nothing stored).
    """
    if not isinstance(user_input, dict):
        return {"kind": "keep"}, user_input if isinstance(user_input, dict) else {}
    remaining = dict(user_input)
    raw = remaining.pop(WORKER_TOKEN_OPTIONS_FIELD, None)
    value = raw.strip() if isinstance(raw, str) else ""
    if not value:
        return {"kind": "keep"}, remaining
    if value.lower() == WORKER_TOKEN_CLEAR_SENTINEL:
        return {"kind": "clear"}, remaining
    if is_valid_deployment_worker_token(value):
        return {"kind": "save", "token": value}, remaining
    return {"kind": "too_short"}, remaining


# The connection endpoints live in config-entry DATA (single source of truth for
# consumers), but are surfaced in the options form so they are editable
# post-install without deleting the integration. Extracted before options
# validation, like the token, and routed to config data.
ENDPOINT_OPTIONS_FIELDS = ("model_endpoint_url", "worker_endpoint_url")


def extract_endpoint_edits(user_input: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split editable connection endpoints out of options user input.

    Returns ``(edits, remaining_input)``. ``edits`` holds any of
    ``model_endpoint_url`` / ``worker_endpoint_url`` present in the form
    (stripped), to be merged into config-entry data and validated there; the
    endpoints never enter the options payload (which enforces exact keys).
    """
    if not isinstance(user_input, dict):
        return {}, user_input if isinstance(user_input, dict) else {}
    remaining = dict(user_input)
    edits: dict[str, Any] = {}
    for key in ENDPOINT_OPTIONS_FIELDS:
        if key in remaining:
            value = remaining.pop(key)
            edits[key] = value.strip() if isinstance(value, str) else value
    return edits, remaining


class IsolinearOptionsFlow(config_entries.OptionsFlow):
    """Update safe Isolinear options for an existing config entry."""

    def __init__(self, config_entry=None):
        super().__init__()
        self._fallback_config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Handle the options flow init step."""
        errors: dict[str, str] = {}
        config_entry = _flow_config_entry(self)
        current_options = getattr(config_entry, "options", {}) or {}

        if user_input is not None:
            token_action, remaining_input = extract_worker_token_action(user_input)
            endpoint_edits, options_input = extract_endpoint_edits(remaining_input)
            updated_config = {
                **normalize_existing_config_entry_data(getattr(config_entry, "data", {})),
                **endpoint_edits,
            }
            if token_action["kind"] == "too_short":
                errors = {WORKER_TOKEN_OPTIONS_FIELD: "worker_token_too_short"}
            else:
                result = validate_options_flow_user_input(
                    updated_config,
                    options_input,
                    current_options=current_options,
                )
                if result["accepted"]:
                    self._apply_worker_token_action(config_entry, token_action)
                    self._apply_endpoint_edits(config_entry, updated_config)
                    return self.async_create_entry(title="", data=result["options_data"])
                errors = result["field_errors"]

        return self.async_show_form(
            step_id=OPTIONS_FLOW_STEP,
            data_schema=build_options_flow_schema(
                current_options, getattr(config_entry, "data", {})
            ),
            errors=errors,
        )

    def _apply_worker_token_action(self, config_entry: Any, action: dict[str, Any]) -> None:
        """Persist a save/clear token action and rebuild the renderer client.

        The rebuild happens HERE, not only in the options-update listener: HA
        fires update listeners only when the options payload actually changed,
        and a token-only re-paste leaves options identical — the listener never
        runs (architecture-review finding).
        """
        if action["kind"] not in ("save", "clear"):
            return
        hass = getattr(self, "hass", None)
        entry_id = getattr(config_entry, "entry_id", None)
        if hass is None or not isinstance(entry_id, str):
            return
        storage = get_worker_token_storage(hass)
        if action["kind"] == "save":
            storage.save_token(entry_id, action["token"])
        else:
            storage.clear_token(entry_id)

        # Drop the cached client so setup rebuilds it from the stored token.
        from .worker_renderer import DATA_WORKER_RENDER_CLIENT, setup_worker_renderer

        entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
        entry_data.pop(DATA_WORKER_RENDER_CLIENT, None)
        entry_data["worker_renderer_setup"] = setup_worker_renderer(hass, config_entry)

    def _apply_endpoint_edits(self, config_entry: Any, updated_config: dict[str, Any]) -> None:
        """Persist edited connection endpoints to config-entry data and rebuild
        the endpoint-dependent setups so the change takes effect without a restart.

        The endpoints are config-entry data (the single source consumers read),
        so the options form routes edits here rather than into the options
        payload. We persist via ``async_update_entry`` and rebuild the model
        provider + worker renderer explicitly (the update listener may also fire,
        but the explicit rebuild makes the new endpoints live immediately).
        """
        hass = getattr(self, "hass", None)
        entry_id = getattr(config_entry, "entry_id", None)
        if hass is None or not isinstance(entry_id, str):
            return
        normalized = normalize_existing_config_entry_data(updated_config)
        update_entry = getattr(
            getattr(hass, "config_entries", None), "async_update_entry", None
        )
        if callable(update_entry):
            update_entry(config_entry, data=normalized)

        from .model_provider import (
            setup_model_provider_codegen,
            setup_model_provider_planner,
        )
        from .worker_renderer import DATA_WORKER_RENDER_CLIENT, setup_worker_renderer

        entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
        entry_data.pop(DATA_WORKER_RENDER_CLIENT, None)
        entry_data["model_provider_setup"] = setup_model_provider_planner(hass, config_entry)
        entry_data["model_provider_codegen_setup"] = setup_model_provider_codegen(
            hass, config_entry
        )
        entry_data["worker_renderer_setup"] = setup_worker_renderer(hass, config_entry)


def config_flow_field_metadata() -> dict[str, Any]:
    """Return deterministic field metadata for tests, evals, and evidence."""
    return {
        "config_step": CONFIG_FLOW_STEP,
        "options_step": OPTIONS_FLOW_STEP,
        "config_fields": list(CONFIG_FLOW_FIELDS),
        "options_fields": list(OPTIONS_FLOW_FIELDS),
        "options_endpoint_fields": list(ENDPOINT_OPTIONS_FIELDS),
        "config_defaults": default_config_data(),
        "options_defaults": options_to_form_data(default_options_data()),
        "options_selectors": {
            "entity_allowlist": dict(ENTITY_ALLOWLIST_SELECTOR_METADATA),
        },
        "supported_model_provider_types": list(SUPPORTED_MODEL_PROVIDER_TYPES),
        "supported_render_modes": list(SUPPORTED_RENDER_MODES),
    }


def build_config_flow_schema(user_input: Mapping[str, Any] | None = None):
    """Build the config-flow form schema or a test-friendly fallback payload."""
    defaults = {**default_config_data(), **dict(user_input or {})}
    defaults["codegen_model"] = defaults.get("codegen_model") or ""
    defaults["visual_validator_model"] = defaults.get("visual_validator_model") or ""

    if vol is None:
        return {
            "step": CONFIG_FLOW_STEP,
            "fields": list(CONFIG_FLOW_FIELDS),
            "defaults": {key: defaults.get(key) for key in CONFIG_FLOW_FIELDS},
        }

    return vol.Schema(
        {
            vol.Required(
                "model_provider_type",
                default=defaults["model_provider_type"],
            ): vol.In(SUPPORTED_MODEL_PROVIDER_TYPES),
            vol.Required(
                "model_endpoint_url",
                default=defaults["model_endpoint_url"],
            ): str,
            vol.Required("planner_model", default=defaults["planner_model"]): str,
            vol.Optional("codegen_model", default=defaults["codegen_model"]): str,
            vol.Optional(
                "visual_validator_model",
                default=defaults["visual_validator_model"],
            ): str,
            vol.Required(
                "worker_endpoint_url",
                default=defaults["worker_endpoint_url"],
            ): str,
        }
    )


def build_options_flow_schema(
    current_options: Mapping[str, Any] | None = None,
    current_config: Mapping[str, Any] | None = None,
):
    """Build the options-flow form schema or a test-friendly fallback payload."""
    defaults = options_to_form_data({**default_options_data(), **dict(current_options or {})})
    config_defaults = {**default_config_data(), **dict(current_config or {})}

    if vol is None:
        return {
            "step": OPTIONS_FLOW_STEP,
            "fields": [
                *ENDPOINT_OPTIONS_FIELDS,
                *OPTIONS_FLOW_FIELDS,
                WORKER_TOKEN_OPTIONS_FIELD,
            ],
            "defaults": {
                **{key: config_defaults.get(key) for key in ENDPOINT_OPTIONS_FIELDS},
                **{key: defaults.get(key) for key in OPTIONS_FLOW_FIELDS},
            },
            "selectors": {
                "entity_allowlist": dict(ENTITY_ALLOWLIST_SELECTOR_METADATA),
                WORKER_TOKEN_OPTIONS_FIELD: dict(WORKER_TOKEN_SELECTOR_METADATA),
            },
        }

    entity_allowlist_selector = (
        EntitySelector(EntitySelectorConfig(multiple=True))
        if EntitySelector is not None and EntitySelectorConfig is not None
        else list
    )
    worker_token_selector = (
        TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
        if TextSelector is not None and TextSelectorConfig is not None
        else str
    )
    return vol.Schema(
        {
            # Connection endpoints first (above the entity picker) — editable
            # post-install; persisted to config-entry data, not options.
            vol.Required(
                "model_endpoint_url",
                default=config_defaults["model_endpoint_url"],
            ): str,
            vol.Required(
                "worker_endpoint_url",
                default=config_defaults["worker_endpoint_url"],
            ): str,
            vol.Required(
                "default_render_mode",
                default=defaults["default_render_mode"],
            ): vol.In(SUPPORTED_RENDER_MODES),
            vol.Required(
                "max_codegen_repair_attempts",
                default=defaults["max_codegen_repair_attempts"],
            ): int,
            vol.Required(
                "max_planner_replan_attempts",
                default=defaults["max_planner_replan_attempts"],
            ): int,
            vol.Required(
                "ollama_timeout_seconds",
                default=defaults["ollama_timeout_seconds"],
            ): int,
            vol.Required(
                "render_path",
                default=defaults["render_path"],
            ): vol.In(SUPPORTED_RENDER_PATHS),
            vol.Optional(
                "entity_allowlist",
                default=defaults["entity_allowlist"],
            ): entity_allowlist_selector,
            # ADR-0032: write-only deployment worker token. Never pre-filled
            # (default stays empty regardless of what is stored); extracted
            # before options validation so it never persists into options.
            vol.Optional(
                WORKER_TOKEN_OPTIONS_FIELD,
                default="",
            ): worker_token_selector,
        }
    )


def validate_config_flow_user_input(user_input: Any) -> dict[str, Any]:
    """Normalize and validate user setup input without touching Home Assistant."""
    config_data = normalize_config_user_input(user_input)
    validation = validate_config_and_options(config_data, default_options_data())
    if not validation["accepted"]:
        return _flow_rejection(validation)

    redacted = redacted_config_result(validation)
    return {
        "accepted": True,
        "code": "accepted",
        "entry_title": NAME,
        "config_data": redacted["config"],
        "options_data": redacted["options"],
        "field_errors": {},
        "orchestration": dict(NO_FLOW_ORCHESTRATION_CALLS),
    }


def validate_options_flow_user_input(
    config_data: Any,
    user_input: Any,
    *,
    current_options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize and validate options input without touching Home Assistant."""
    normalized_config_data = normalize_existing_config_entry_data(config_data)
    options_data = normalize_options_user_input(user_input, current_options=current_options)
    validation = validate_config_and_options(normalized_config_data, options_data)
    if not validation["accepted"]:
        return _flow_rejection(validation)

    redacted = redacted_config_result(validation)
    return {
        "accepted": True,
        "code": "accepted",
        "options_data": redacted["options"],
        "field_errors": {},
        "orchestration": dict(NO_FLOW_ORCHESTRATION_CALLS),
    }


def normalize_config_user_input(user_input: Any) -> Any:
    """Normalize form values into the config-entry data shape."""
    if not isinstance(user_input, Mapping):
        return user_input

    config_data: dict[str, Any] = default_config_data()
    config_data.update(dict(user_input))
    for key in CONFIG_FLOW_FIELDS:
        value = config_data.get(key)
        if isinstance(value, str):
            config_data[key] = value.strip()
    for key in ("codegen_model", "visual_validator_model"):
        if config_data.get(key) == "":
            config_data[key] = None
    if not config_data.get("model_provider_type"):
        config_data["model_provider_type"] = MODEL_PROVIDER_OLLAMA_COMPATIBLE
    return config_data


def normalize_existing_config_entry_data(config_data: Any) -> Any:
    """Normalize existing config-entry data for options-only edits."""
    if config_data is None:
        return default_config_data()
    if not isinstance(config_data, Mapping):
        return config_data
    return normalize_config_user_input({**default_config_data(), **dict(config_data)})


def normalize_options_user_input(
    user_input: Any,
    *,
    current_options: Mapping[str, Any] | None = None,
) -> Any:
    """Normalize form values into the options data shape."""
    if not isinstance(user_input, Mapping):
        if isinstance(user_input, str):
            options_data: dict[str, Any] = default_options_data()
            if isinstance(current_options, Mapping):
                options_data.update(dict(current_options))
            options_data["entity_allowlist"] = _normalize_allowlist_value(user_input)
            return options_data
        return user_input

    options_data: dict[str, Any] = default_options_data()
    if isinstance(current_options, Mapping):
        options_data.update(dict(current_options))
    options_data.update(dict(user_input))

    render_mode = options_data.get("default_render_mode")
    if isinstance(render_mode, str):
        options_data["default_render_mode"] = render_mode.strip()

    for attempts_key in ("max_codegen_repair_attempts", "max_planner_replan_attempts"):
        attempts = options_data.get(attempts_key)
        if isinstance(attempts, str) and attempts.strip().isdigit():
            options_data[attempts_key] = int(attempts.strip())

    timeout = options_data.get("ollama_timeout_seconds")
    if isinstance(timeout, str) and timeout.strip().isdigit():
        options_data["ollama_timeout_seconds"] = int(timeout.strip())

    # ADR-0030: the legacy codegen_enabled boolean is dropped on normalization
    # (both values map to the new render_path default "auto"); an explicit
    # render_path value wins.
    options_data.pop("codegen_enabled", None)
    render_path_value = options_data.get("render_path")
    if isinstance(render_path_value, str):
        options_data["render_path"] = render_path_value.strip().lower()
    if not options_data.get("render_path"):
        options_data["render_path"] = RENDER_PATH_AUTO

    options_data["entity_allowlist"] = _normalize_allowlist_value(
        options_data.get("entity_allowlist")
    )
    return options_data


def options_to_form_data(options_data: Mapping[str, Any]) -> dict[str, Any]:
    """Convert stored options into user-facing form defaults."""
    form_data = dict(options_data)
    allowlist = form_data.get("entity_allowlist", [])
    if isinstance(allowlist, str):
        form_data["entity_allowlist"] = _normalize_allowlist_value(allowlist)
        return form_data
    if isinstance(allowlist, (list, tuple)):
        form_data["entity_allowlist"] = [str(item) for item in allowlist]
    return form_data


def options_to_legacy_text_form_data(options_data: Mapping[str, Any]) -> dict[str, Any]:
    """Convert stored options into the former text-area defaults for regression proof."""
    form_data = dict(options_data)
    allowlist = form_data.get("entity_allowlist", [])
    if isinstance(allowlist, (list, tuple)):
        form_data["entity_allowlist"] = ", ".join(str(item) for item in allowlist)
    return form_data


def _normalize_allowlist_value(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return _normalize_allowlist_value(parsed)
        return [
            item.strip()
            for item in re.split(r"[\n,]+", stripped)
            if item.strip()
        ]
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, list):
        return [
            item.strip() if isinstance(item, str) else item
            for item in value
        ]
    return value


def _flow_rejection(validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": validation["code"],
        "field_errors": _field_errors_from_validation(validation),
        "validation": redacted_config_result(validation),
        "orchestration": dict(NO_FLOW_ORCHESTRATION_CALLS),
    }


def _field_errors_from_validation(validation: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    for item in validation.get("errors", []) + validation.get("forbidden_matches", []):
        field = _field_from_path(item.get("path", ""))
        errors.setdefault(field, item.get("reason", validation["code"]))
    if not errors:
        errors["base"] = validation["code"]
    return errors


def _field_from_path(path: str) -> str:
    for prefix, allowed_fields in (
        ("$.config_data.", CONFIG_FLOW_FIELDS),
        ("$.options_data.", OPTIONS_FLOW_FIELDS),
    ):
        if path.startswith(prefix):
            field = path[len(prefix):].split("[", 1)[0].split(".", 1)[0]
            if field in allowed_fields:
                return field
    return "base"


def _flow_config_entry(flow: IsolinearOptionsFlow) -> Any:
    return getattr(flow, "config_entry", None) or getattr(flow, "_fallback_config_entry", None)
