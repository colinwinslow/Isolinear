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
    SUPPORTED_MODEL_PROVIDER_TYPES,
    SUPPORTED_RENDER_MODES,
)


try:  # pragma: no cover - exercised by Home Assistant, not the repo anchor.
    import voluptuous as vol
    from homeassistant import config_entries
    from homeassistant.core import callback
except ImportError:  # pragma: no cover - deterministic fallback for repo tests.
    vol = None

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
    "entity_allowlist",
)

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
            result = validate_options_flow_user_input(
                getattr(config_entry, "data", {}),
                user_input,
                current_options=current_options,
            )
            if result["accepted"]:
                return self.async_create_entry(title="", data=result["options_data"])
            errors = result["field_errors"]

        return self.async_show_form(
            step_id=OPTIONS_FLOW_STEP,
            data_schema=build_options_flow_schema(current_options),
            errors=errors,
        )


def config_flow_field_metadata() -> dict[str, Any]:
    """Return deterministic field metadata for tests, evals, and evidence."""
    return {
        "config_step": CONFIG_FLOW_STEP,
        "options_step": OPTIONS_FLOW_STEP,
        "config_fields": list(CONFIG_FLOW_FIELDS),
        "options_fields": list(OPTIONS_FLOW_FIELDS),
        "config_defaults": default_config_data(),
        "options_defaults": options_to_form_data(default_options_data()),
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


def build_options_flow_schema(current_options: Mapping[str, Any] | None = None):
    """Build the options-flow form schema or a test-friendly fallback payload."""
    defaults = options_to_form_data({**default_options_data(), **dict(current_options or {})})

    if vol is None:
        return {
            "step": OPTIONS_FLOW_STEP,
            "fields": list(OPTIONS_FLOW_FIELDS),
            "defaults": {key: defaults.get(key) for key in OPTIONS_FLOW_FIELDS},
        }

    return vol.Schema(
        {
            vol.Required(
                "default_render_mode",
                default=defaults["default_render_mode"],
            ): vol.In(SUPPORTED_RENDER_MODES),
            vol.Required(
                "max_codegen_repair_attempts",
                default=defaults["max_codegen_repair_attempts"],
            ): int,
            vol.Optional(
                "entity_allowlist",
                default=defaults["entity_allowlist"],
            ): str,
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

    attempts = options_data.get("max_codegen_repair_attempts")
    if isinstance(attempts, str) and attempts.strip().isdigit():
        options_data["max_codegen_repair_attempts"] = int(attempts.strip())

    options_data["entity_allowlist"] = _normalize_allowlist_value(
        options_data.get("entity_allowlist")
    )
    return options_data


def options_to_form_data(options_data: Mapping[str, Any]) -> dict[str, Any]:
    """Convert stored options into user-facing form defaults."""
    form_data = dict(options_data)
    allowlist = form_data.get("entity_allowlist", [])
    if isinstance(allowlist, (list, tuple)):
        form_data["entity_allowlist"] = "\n".join(str(item) for item in allowlist)
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
