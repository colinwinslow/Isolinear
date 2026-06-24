"""Ollama-compatible model-provider planning boundary for Isolinear."""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any

from ._paths import load_schema_document, schema_path
from .const import DOMAIN, MODEL_PROVIDER_OLLAMA_COMPATIBLE

_LOGGER = logging.getLogger(__name__)


DATA_MODEL_PROVIDER_PLANNER = "model_provider_planner"
DATA_MODEL_PROVIDER_SETUP = "model_provider_setup"

PLANNER_RESULT_SCHEMA_PATH = schema_path("planner-result.schema.json")
# A local gemma planner call observed ~30s for a simple chart; the prior 30s
# cap timed out on anything heavier (mixed/overlay prompts). Give the local
# model real headroom (ADR-0024 also adds a model entity-selection round-trip).
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 90
MODEL_PROVIDER_HEALTH_PATH = "/api/tags"

# ADR-0025 R1: the live reasoning trace surfaced to the card is capped to this
# many characters. The cap bounds snapshot size against a runaway model trace
# (D5) and is mirrored by `progress.reasoning.maxLength` in the snapshot schema.
REASONING_CHAR_CAP = 2000

# ADR-0025 D5: the model thinking trace is unsanitized output. Before it reaches
# the card it gets the same redaction posture as every card-facing field — no
# tokens, endpoints/worker URLs, or local filesystem paths. Approved entity IDs
# and the user's own prompt may remain (already disclosed). These patterns are
# intentionally broad; over-redaction of wait-feedback is harmless.
_REASONING_REDACTIONS: tuple[re.Pattern[str], ...] = (
    # http(s) endpoints / worker URLs (host, port, path).
    re.compile(r"https?://\S+"),
    # Bearer / authorization tokens.
    re.compile(r"(?i)bearer\s+\S+"),
    # Named secret vocabulary, mirroring job_orchestration's
    # FORBIDDEN_WORKER_PROGRESS_TEXT / FORBIDDEN_MODEL_PROVIDER_FAILURE_TEXT so
    # the reasoning surface can't drift from the rest of the card-facing fields.
    # Redact the key *and* any attached value (``access_token=...``, ``token: ...``).
    re.compile(
        r"(?i)\b(?:access_token|home_assistant_token|long_lived_access_token|"
        r"worker_token|model_provider_token|ollama_api_key|api[_-]?key)\b"
        r"(?:\s*[:=]\s*\S+)?"
    ),
    # Bare secret-like tokens: OpenAI-style ``sk-...`` keys and JWTs
    # (three dot-separated base64url segments). The model can echo such
    # material verbatim from a prompt; over-redacting wait-feedback is harmless.
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
    # Windows filesystem paths (drive-letter rooted).
    re.compile(r"[A-Za-z]:\\[^\s\"']+"),
    # Unix-ish absolute paths with at least two segments (avoid eating prose
    # like "and/or"; require a leading slash and a path separator).
    re.compile(r"(?<!\w)/[\w.-]+(?:/[\w.-]+)+"),
)
_REASONING_REDACTION_PLACEHOLDER = "[redacted]"


def sanitize_reasoning(raw: str) -> str:
    """Redact off-limit material and roll-tail-cap a model thinking trace.

    ADR-0025 D5 (redaction), R1 (2000-char cap), R2 (rolling tail). Returns the
    trailing ``REASONING_CHAR_CAP`` characters of the redacted trace; when
    content was elided from the front a single leading ``…`` marks the cut.
    An empty input (or one that redacts to nothing) returns an empty string and
    the caller omits the field.
    """
    if not raw:
        return ""
    text = raw
    for pattern in _REASONING_REDACTIONS:
        text = pattern.sub(_REASONING_REDACTION_PLACEHOLDER, text)
    if len(text) <= REASONING_CHAR_CAP:
        return text
    # Rolling tail: keep the newest content, mark the elision with an ellipsis
    # that itself counts toward the cap.
    tail = text[-(REASONING_CHAR_CAP - 1):]
    return "…" + tail


def setup_model_provider_planner(hass: Any, entry: Any) -> dict[str, Any]:
    """Install an Ollama-compatible planner client when config-entry data exists."""
    entry_id = getattr(entry, "entry_id", "scaffold-entry")
    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    config_data = getattr(entry, "data", {}) or {}
    setup = _setup_disabled(entry_id, "model_provider_config_missing")

    if _has_ollama_planner_config(config_data):
        client = OllamaCompatiblePlannerClient(
            endpoint_url=config_data["model_endpoint_url"],
            planner_model=config_data["planner_model"],
        )
        entry_data[DATA_MODEL_PROVIDER_PLANNER] = client
        setup = {
            "accepted": True,
            "code": "model_provider_planner_configured",
            "entry_id": entry_id,
            "config_entry_scoped": True,
            "enabled": True,
            "provider": client.provider_metadata(),
            "orchestration": model_provider_setup_side_effects(),
        }

    entry_data[DATA_MODEL_PROVIDER_SETUP] = setup
    return setup


def get_model_provider_planner(hass: Any, entry_id: str) -> Any | None:
    """Return the configured planner client for one config entry, if any."""
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    planner = entry_data.get(DATA_MODEL_PROVIDER_PLANNER) if isinstance(entry_data, dict) else None
    return planner if planner is not None else None


# Render families the integration may request from the planner.
# ADR-0022: the integration deterministically picks the family from each
# resolved entity's series kind.  ADR-0023 extends this: the envelope can
# contain multiple families so the model selects intent within the set.
PLANNER_RENDER_FAMILIES = {
    "time_series": {"chart_type": "time_series", "render_as": "line"},
    "timeline": {"chart_type": "timeline", "render_as": "step"},
    "histogram": {"chart_type": "histogram", "render_as": "histogram"},
    "aggregate_bar": {"chart_type": "bar", "render_as": "bar"},
}


def load_planner_result_schema(
    family: str = "time_series",
    *,
    envelope: list[str] | None = None,
    entity_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Load the PlannerResult JSON Schema for Ollama structured output.

    ``family`` is the default/fallback render family (ADR-0022).  ``envelope``
    is the full ADR-0023 capability list; when it contains more than one family
    the ``chart_type`` enum is widened to all members so the model can choose
    intent within the set.  When ``envelope`` has exactly one member (or is
    omitted) the schema is identical to the single-family ADR-0022 form.

    ``entity_ids`` pins ``source.entity_id`` to an enum of exactly the
    disclosed IDs so constrained decoding cannot emit an off-allowlist entity
    (invariant #1).  Without it the field stays a free string.
    """
    effective_envelope = [f for f in (envelope or []) if f in PLANNER_RENDER_FAMILIES]
    if not effective_envelope:
        effective_envelope = [family]
    is_multi_family = len(effective_envelope) > 1

    disclosed_entity_ids = [
        entity_id for entity_id in (entity_ids or []) if isinstance(entity_id, str) and entity_id
    ]
    entity_id_schema: dict[str, Any] = (
        {"enum": list(dict.fromkeys(disclosed_entity_ids))}
        if disclosed_entity_ids
        else {"type": "string"}
    )

    if is_multi_family:
        chart_spec_fragment = _multi_family_chart_spec_schema(effective_envelope, entity_id_schema)
    else:
        single_spec = PLANNER_RENDER_FAMILIES.get(effective_envelope[0], PLANNER_RENDER_FAMILIES["time_series"])
        chart_spec_fragment = _single_family_chart_spec_schema(single_spec, entity_id_schema)

    schema = load_schema_document(PLANNER_RESULT_SCHEMA_PATH)
    schema.setdefault("properties", {})["chart_spec"] = chart_spec_fragment
    return schema


def _time_range_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["type", "start", "end"],
        "additionalProperties": False,
        "properties": {
            "type": {"const": "absolute"},
            "start": {"type": "string", "format": "date-time"},
            "end": {"type": "string", "format": "date-time"},
        },
    }


def _single_family_chart_spec_schema(spec: dict[str, Any], entity_id_schema: dict[str, Any]) -> dict[str, Any]:
    """Build the chart_spec schema fragment for a single-family (ADR-0022) envelope."""
    return {
        "type": "object",
        "required": ["chart_id", "chart_type", "title", "time_range", "series"],
        "additionalProperties": False,
        "properties": {
            "chart_id": {"type": "string"},
            "chart_type": {"enum": [spec["chart_type"]]},
            "title": {"type": "string"},
            "time_range": _time_range_schema(),
            "series": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["series_id", "label", "source", "role", "render_as", "transform", "unit"],
                    "additionalProperties": False,
                    "properties": {
                        "series_id": {"type": "string"},
                        "label": {"type": "string"},
                        "source": {
                            "type": "object",
                            "required": ["type", "entity_id", "attribute"],
                            "additionalProperties": False,
                            "properties": {
                                "type": {"enum": ["entity"]},
                                "entity_id": entity_id_schema,
                                "attribute": {"type": ["string", "null"]},
                            },
                        },
                        "role": {"enum": ["primary", "comparison", "secondary", "annotation"]},
                        "render_as": {"enum": [spec["render_as"]]},
                        "transform": {
                            "type": "object",
                            "required": ["operation", "window"],
                            "additionalProperties": False,
                            "properties": {
                                "operation": {"enum": ["none"]},
                                "window": {"type": ["string", "null"]},
                            },
                        },
                        "unit": {"type": ["string", "null"]},
                    },
                },
            },
            "overlays": {"type": "array", "items": {"type": "object"}},
            "x_axis": {"type": "object"},
            "y_axis": {"type": "object"},
            "notes": {"type": "array", "items": {"type": "string"}},
        },
    }


def _multi_family_chart_spec_schema(families: list[str], entity_id_schema: dict[str, Any]) -> dict[str, Any]:
    """Build the chart_spec schema fragment for a multi-family (ADR-0023) envelope.

    ``chart_type`` is an enum of all families' chart_type values; ``render_as``
    and ``source.type`` are permissive enough for all families.  The
    out-of-envelope gate + renderer validate the actual choice post-hoc.
    """
    chart_types = list(dict.fromkeys(
        PLANNER_RENDER_FAMILIES[f]["chart_type"] for f in families if f in PLANNER_RENDER_FAMILIES
    ))
    render_as_values = list(dict.fromkeys(
        PLANNER_RENDER_FAMILIES[f]["render_as"] for f in families if f in PLANNER_RENDER_FAMILIES
    ))
    has_aggregate = "aggregate_bar" in families
    source_types: list[str] = ["entity", "aggregate"] if has_aggregate else ["entity"]
    return {
        "type": "object",
        "required": ["chart_id", "chart_type", "title", "time_range", "series"],
        "additionalProperties": False,
        "properties": {
            "chart_id": {"type": "string"},
            "chart_type": {"enum": chart_types},
            "title": {"type": "string"},
            "time_range": _time_range_schema(),
            "series": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["series_id", "label", "source", "role", "render_as", "transform", "unit"],
                    "additionalProperties": False,
                    "properties": {
                        "series_id": {"type": "string"},
                        "label": {"type": "string"},
                        "source": {
                            "type": "object",
                            "required": ["type", "entity_id"],
                            "additionalProperties": False,
                            "properties": {
                                "type": {"enum": source_types},
                                "entity_id": entity_id_schema,
                                "attribute": {"type": ["string", "null"]},
                                "operation": {"enum": ["mean", "min", "max", "sum", "count"]},
                            },
                        },
                        "role": {"enum": ["primary", "comparison", "secondary", "annotation"]},
                        "render_as": {"enum": render_as_values},
                        "transform": {
                            "type": "object",
                            "required": ["operation", "window"],
                            "additionalProperties": False,
                            "properties": {
                                "operation": {"enum": ["none"]},
                                "window": {"type": ["string", "null"]},
                            },
                        },
                        "unit": {"type": ["string", "null"]},
                    },
                },
            },
            "overlays": {"type": "array", "items": {"type": "object"}},
            "x_axis": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "bin_count": {"type": "integer", "minimum": 1},
                    "group_by": {"type": "string"},
                },
            },
            "y_axis": {"type": "object"},
            "notes": {"type": "array", "items": {"type": "string"}},
        },
    }


def load_entity_selector_schema(candidate_entity_ids: list[str]) -> dict[str, Any]:
    """Build a structured-output schema for entity selection (ADR-0024 D2).

    Pins candidate entity IDs to an enum so the provider's constrained
    decoding cannot return an entity outside the disclosed candidate set.
    """
    deduped = list(dict.fromkeys(
        eid for eid in candidate_entity_ids if isinstance(eid, str) and eid
    ))
    entity_id_items: dict[str, Any] = {"enum": deduped} if deduped else {"type": "string"}
    return {
        "type": "object",
        "required": ["status"],
        "additionalProperties": False,
        "properties": {
            "status": {"enum": ["entity_selected", "clarification_needed"]},
            "entity_ids": {
                "type": "array",
                "minItems": 1,
                "items": entity_id_items,
            },
            "reasoning_summary": {"type": ["string", "null"]},
        },
    }


def planner_client_metadata(planner: Any) -> dict[str, str]:
    """Return schema-safe provider metadata from a planner client."""
    if hasattr(planner, "provider_metadata"):
        metadata = planner.provider_metadata()
        if isinstance(metadata, dict):
            return {
                "type": str(metadata.get("type") or MODEL_PROVIDER_OLLAMA_COMPATIBLE),
                "role": str(metadata.get("role") or "planner"),
                "endpoint_url": str(metadata.get("endpoint_url") or ""),
                "model": str(metadata.get("model") or metadata.get("planner_model") or ""),
            }

    return {
        "type": str(getattr(planner, "provider_type", MODEL_PROVIDER_OLLAMA_COMPATIBLE)),
        "role": str(getattr(planner, "role", "planner")),
        "endpoint_url": str(getattr(planner, "endpoint_url", "")),
        "model": str(getattr(planner, "planner_model", "")),
    }


def model_provider_setup_side_effects() -> dict[str, bool]:
    """Return side-effect accounting for model-provider setup."""
    return {
        "model_provider_called": False,
        "worker_called": False,
        "home_assistant_history_called": False,
        "home_assistant_service_or_state_mutation_called": False,
        "semantic_memory_called": False,
        "token_generated": False,
    }


class OllamaCompatiblePlannerClient:
    """Small stdlib client for Ollama-compatible planner chat calls."""

    provider_type = MODEL_PROVIDER_OLLAMA_COMPATIBLE
    role = "planner"

    def __init__(
        self,
        *,
        endpoint_url: str,
        planner_model: str,
        timeout_seconds: int = DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    ) -> None:
        self.endpoint_url = endpoint_url.rstrip("/")
        self.planner_model = planner_model
        self.timeout_seconds = timeout_seconds

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
        on_reasoning: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Call `/api/chat` with structured output and return a PlannerResult.

        When ``on_reasoning`` is provided the call uses two passes (ADR-0025 D1):
        Pass 1 streams with ``think:true`` (no format) so reasoning chunks are
        delivered to the card via the callback. Pass 2 is a non-streaming call
        with ``format:result_schema`` for reliable schema-constrained JSON —
        Ollama suppresses thinking when format is set, so they cannot share a
        single call. When ``on_reasoning`` is None a single format-constrained
        call is made (D6 fallback, unchanged behavior).
        """
        schema = result_schema or load_planner_result_schema()
        chat_url = _ollama_chat_url(self.endpoint_url)

        if on_reasoning is not None:
            # Pass 1 — thinking only: stream reasoning to the card, ignore content.
            think_payload = self._chat_payload(request, schema, stream=True)
            _LOGGER.debug(
                "Isolinear -> Ollama plan_chart think request: model=%s url=%s body=%s",
                self.planner_model,
                chat_url,
                json.dumps(think_payload, separators=(",", ":")),
            )
            self._read_chat(chat_url, think_payload, label="plan_chart_think", on_reasoning=on_reasoning)
            # Thinking-pass content is discarded; failures are non-fatal since
            # reasoning is presentational — planning proceeds regardless.

        # Pass 2 (or sole pass when not streaming): format-constrained structured output.
        plan_payload = self._chat_payload(request, schema, stream=False)
        _LOGGER.debug(
            "Isolinear -> Ollama plan_chart request: model=%s url=%s body=%s",
            self.planner_model,
            chat_url,
            json.dumps(plan_payload, separators=(",", ":")),
        )
        content, response_payload, failure = self._read_chat(
            chat_url, plan_payload, label="plan_chart", on_reasoning=None
        )
        if failure is not None:
            return failure
        if not isinstance(content, str) or not content.strip():
            return _provider_failure("model_provider_empty_response", "Planner response content was empty.", retry_safe=True)

        try:
            planner_result = json.loads(_strip_markdown_json(content))
        except json.JSONDecodeError as exc:
            return _provider_failure("model_provider_non_json_response", str(exc), retry_safe=False)

        return {
            "accepted": True,
            "code": "model_provider_planner_result_received",
            "provider": self.provider_metadata(),
            "planner_result": planner_result,
            "provider_response": _provider_response_summary(response_payload),
        }

    def select_entity(
        self,
        request: dict[str, Any],
        *,
        result_schema: dict[str, Any] | None = None,
        on_reasoning: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Call /api/chat to select an approved entity for the prompt (ADR-0024 D2).

        Uses the same two-pass approach as plan_chart when ``on_reasoning`` is
        provided: a streaming think pass delivers reasoning to the card, then a
        format-constrained pass returns the validated selection result.
        """
        schema = result_schema or load_entity_selector_schema(request.get("candidate_entity_ids", []))
        chat_url = _ollama_chat_url(self.endpoint_url)

        if on_reasoning is not None:
            think_payload = self._entity_selector_payload(request, schema, stream=True)
            _LOGGER.debug(
                "Isolinear -> Ollama select_entity think request: model=%s url=%s body=%s",
                self.planner_model,
                chat_url,
                json.dumps(think_payload, separators=(",", ":")),
            )
            self._read_chat(chat_url, think_payload, label="select_entity_think", on_reasoning=on_reasoning)

        select_payload = self._entity_selector_payload(request, schema, stream=False)
        _LOGGER.debug(
            "Isolinear -> Ollama select_entity request: model=%s url=%s body=%s",
            self.planner_model,
            chat_url,
            json.dumps(select_payload, separators=(",", ":")),
        )
        content, response_payload, failure = self._read_chat(
            chat_url, select_payload, label="select_entity", on_reasoning=None
        )
        if failure is not None:
            return failure
        if not isinstance(content, str) or not content.strip():
            return _provider_failure(
                "model_provider_empty_response",
                "Entity selector response content was empty.",
                retry_safe=True,
            )
        try:
            selection_result = json.loads(_strip_markdown_json(content))
        except json.JSONDecodeError as exc:
            return _provider_failure("model_provider_non_json_response", str(exc), retry_safe=False)
        return {
            "accepted": True,
            "code": "model_provider_entity_selection_received",
            "provider": self.provider_metadata(),
            "selection_result": selection_result,
            "provider_response": _provider_response_summary(response_payload),
        }

    def _read_chat(
        self,
        chat_url: str,
        payload: dict[str, Any],
        *,
        label: str,
        on_reasoning: Callable[[str], None] | None,
    ) -> tuple[str | None, dict[str, Any] | None, dict[str, Any] | None]:
        """Execute one /api/chat POST and return (content, response, failure).

        Exactly one of ``failure`` (a sanitized provider-failure dict) or the
        ``(content, response)`` pair is meaningful. When ``on_reasoning`` is
        provided the body is streamed NDJSON (ADR-0025 D1); otherwise it is a
        single JSON read. Transport errors mid-stream return the same failures
        the non-streaming path returns (R4).
        """
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        http_request = urllib.request.Request(
            chat_url,
            data=encoded,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                if on_reasoning is None:
                    response_payload = json.loads(response.read().decode("utf-8"))
                    message = (
                        response_payload.get("message")
                        if isinstance(response_payload, dict)
                        else None
                    )
                    content = message.get("content") if isinstance(message, dict) else None
                    _LOGGER.debug(
                        "Isolinear <- Ollama %s response: %s",
                        label,
                        json.dumps(response_payload, separators=(",", ":")),
                    )
                    return content, response_payload, None
                content, response_payload = self._consume_ndjson(response, on_reasoning)
                _LOGGER.debug(
                    "Isolinear <- Ollama %s streamed response: %s",
                    label,
                    json.dumps(response_payload, separators=(",", ":")),
                )
                return content, response_payload, None
        except urllib.error.HTTPError as exc:
            _LOGGER.debug("Isolinear <- Ollama %s HTTP error: %s", label, exc)
            return None, None, _provider_failure("model_provider_http_error", str(exc), retry_safe=True)
        except (urllib.error.URLError, TimeoutError) as exc:
            _LOGGER.debug("Isolinear <- Ollama %s connection error: %s", label, exc)
            return None, None, _provider_failure("model_provider_connection_error", str(exc), retry_safe=True)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            _LOGGER.debug("Isolinear <- Ollama %s response error: %s", label, exc)
            return None, None, _provider_failure("model_provider_response_error", str(exc), retry_safe=False)

    def _consume_ndjson(
        self,
        response: Any,
        on_reasoning: Callable[[str], None],
    ) -> tuple[str, dict[str, Any]]:
        """Read an Ollama NDJSON chat stream, accumulating thinking + content.

        Calls ``on_reasoning`` with the sanitized accumulated thinking after each
        delta that carries thinking. Models that emit no separate thinking trace
        produce no reasoning callbacks at all — the D6 graceful fallback per
        ADR-0025 (nothing is shown), not a fall-through to content deltas.
        Returns the fully assembled final ``message.content`` (the
        structured-output JSON) and the last raw chunk as the response summary
        source.
        """
        thinking_parts: list[str] = []
        content_parts: list[str] = []
        last_chunk: dict[str, Any] = {}
        for raw_line in response:
            line = raw_line.decode("utf-8").strip() if isinstance(raw_line, (bytes, bytearray)) else str(raw_line).strip()
            if not line:
                continue
            chunk = json.loads(line)
            if not isinstance(chunk, dict):
                continue
            last_chunk = chunk
            message = chunk.get("message")
            if not isinstance(message, dict):
                continue
            thinking_delta = message.get("thinking")
            content_delta = message.get("content")
            saw_thinking = isinstance(thinking_delta, str) and thinking_delta != ""
            if saw_thinking:
                thinking_parts.append(thinking_delta)
            if isinstance(content_delta, str) and content_delta != "":
                content_parts.append(content_delta)
            # Surface accumulated thinking only. Non-thinking models emit no
            # reasoning (D6 graceful fallback per ADR-0025).
            if saw_thinking:
                on_reasoning(sanitize_reasoning("".join(thinking_parts)))
        return "".join(content_parts), last_chunk

    def _entity_selector_payload(
        self, request: dict[str, Any], result_schema: dict[str, Any], *, stream: bool = False
    ) -> dict[str, Any]:
        prompt_payload = {
            "task": "Select the approved Home Assistant entity (or entities) the user is asking about.",
            "rules": [
                "Choose only from the candidate_entity_ids list.",
                "Return status entity_selected with a non-empty entity_ids list if the user's intent is clear.",
                "Home Assistant climate entities represent HVAC systems (thermostats, "
                "heat pumps, mini-splits, AC units); map functional words like 'AC', "
                "'air conditioning', 'heating', or 'the cooling' to the matching climate entity.",
                "If already_selected_entity_ids is present, those entities were resolved "
                "for part of the request. Confirm them and ADD any other candidate entities "
                "the prompt also refers to (a prompt may mention several distinct concepts). "
                "Return the complete entity_ids set, keeping the already-selected ones unless "
                "one is clearly wrong for the prompt.",
                "Return status clarification_needed if you genuinely cannot determine which entity the user means.",
                "Do not guess when genuinely ambiguous.",
                "Do not include raw Home Assistant data, secrets, tokens, or prose outside JSON.",
            ],
            "entity_selector_request": deepcopy(request),
            "entity_selector_result_schema": result_schema,
        }
        return {
            "model": self.planner_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are the Isolinear entity selector. Return only JSON that validates "
                        "against the supplied entity_selector_result_schema."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(prompt_payload, separators=(",", ":")),
                },
            ],
            "stream": stream,
            # Thinking mode and Ollama structured-output format are mutually
            # exclusive: Ollama suppresses thinking when format is set.  When
            # streaming (reasoning requested) we omit format and rely on the
            # system-prompt schema guidance + _strip_markdown_json post-processing.
            # Non-streaming calls keep format for strict constrained decoding.
            **({"think": True} if stream else {"format": result_schema}),
            "options": {
                "temperature": 0,
                # Cap thinking tokens on the think pass so simple queries don't
                # spend 30-40 s generating 1500+ reasoning tokens. The result
                # pass (stream=False) is uncapped: it produces the final JSON and
                # needs enough tokens to complete the structured output.
                **({"num_predict": 512} if stream else {}),
            },
        }

    def check_health(self, request: dict[str, Any]) -> dict[str, Any]:
        """Call the Ollama tags endpoint and return provider health metadata."""
        http_request = urllib.request.Request(
            _ollama_tags_url(self.endpoint_url),
            headers={"Accept": request.get("headers", {}).get("accept", "application/json")},
            method="GET",
        )

        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return _provider_failure("model_provider_health_http_error", str(exc), retry_safe=True)
        except (urllib.error.URLError, TimeoutError) as exc:
            return _provider_failure("model_provider_health_connection_error", str(exc), retry_safe=True)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            return _provider_failure("model_provider_health_response_error", str(exc), retry_safe=False)

        model_names = _ollama_model_names(response_payload)
        model_ready = _planner_model_is_listed(self.planner_model, model_names)
        status = "ready" if model_ready else "not_ready"
        return {
            "accepted": True,
            "code": "model_provider_health_result_received",
            "provider": self.provider_metadata(),
            "health_result": {
                "version": 1,
                "status": status,
                "code": f"model_provider_health_{status}",
                "message": (
                    "Configured planner model is available."
                    if model_ready
                    else "Configured planner model was not listed by the provider."
                ),
                "checks": [
                    {"name": "ollama_tags_endpoint", "status": "pass"},
                    {"name": "planner_model", "status": "pass" if model_ready else "not_ready"},
                ],
                "capabilities": {
                    "planning": model_ready,
                    "structured_output": model_ready,
                },
            },
            "provider_response": {
                "model_count": len(model_names),
            },
        }

    def _chat_payload(self, request: dict[str, Any], result_schema: dict[str, Any], *, stream: bool = False) -> dict[str, Any]:
        chart_type, render_as = _chart_family_from_schema(result_schema)
        # Detect multi-family envelope (ADR-0023): chart_type enum has >1 value.
        try:
            chart_type_enum: list[str] = result_schema["properties"]["chart_spec"]["properties"]["chart_type"]["enum"]
        except (KeyError, TypeError):
            chart_type_enum = [chart_type]
        is_multi_family = len(chart_type_enum) > 1
        if is_multi_family:
            chart_type_rule = (
                f"Choose chart_type from {chart_type_enum} to best match user intent: "
                "time_series for trends over time, histogram for value distributions, "
                "bar for aggregate/summary values per period. "
                "Match render_as to the chosen type: line for time_series, histogram for histogram, bar for bar. "
                "For histogram add x_axis with type 'value' and bin_count (default 8). "
                "For bar add x_axis with type 'category' and group_by ('day' or 'hour'). "
                "For bar series use source type 'aggregate' with entity_id and operation (mean/min/max/sum/count). "
                "For time_series and histogram series use source type 'entity' with entity_id and attribute null."
            )
        else:
            chart_type_rule = (
                f"Use chart_type {chart_type}, render_as {render_as}, transform operation none, "
                "x_axis type time, and overlays []."
            )
        overlay_entity_ids: list[str] = request.get("overlay_entity_ids") or []
        overlay_rule = (
            f"The integration will automatically add shaded overlays for these entities: "
            f"{overlay_entity_ids}. Do NOT include them in series and do NOT treat them as missing — "
            "they are handled by the system. Return status chart_spec_ready for the numeric series only."
        ) if overlay_entity_ids else None
        prompt_payload = {
            "task": "Return one PlannerResult JSON object for an Isolinear chart plan.",
            "rules": [
                "Use only approved_entity_ids supplied in the request.",
                "If the prompt asks about a device, sensor, appliance, or concept (such as AC, thermostat, door, alarm, etc.) "
                "that is NOT represented by any entity in approved_entity_ids, return status clarification_needed with a "
                "clarification_question explaining what could not be found. Never invent, relabel, or reuse an existing "
                "entity to stand in for a missing one.",
                "Only return status chart_spec_ready if every piece of information the user asked for can be represented "
                "using only the approved_entity_ids provided.",
                "Each series must represent a distinct approved entity. Never create multiple series for the same entity_id.",
                "The chart_spec must use chart_type, not graph_type.",
                "Each series must include series_id, label, source, role, render_as, transform, and unit.",
                "Each entity series source must be {\"type\":\"entity\",\"entity_id\":\"<approved id>\",\"attribute\":null}.",
                chart_type_rule,
                *([overlay_rule] if overlay_rule else []),
                "Resolve the requested time window into an absolute time_range "
                "{\"type\":\"absolute\",\"start\":<ISO8601>,\"end\":<ISO8601>} using the "
                "request now and time_zone. Interpret fuzzy phrases (for example "
                "\"last weekend\", \"during the night\", \"since the spring equinox\") "
                "relative to now. Use timezone-aware ISO 8601 timestamps and never set end after now.",
                "Do not include raw Home Assistant history, secrets, worker URLs, tokens, or prose outside JSON.",
            ],
            "planner_request": deepcopy(request),
            "planner_result_schema": result_schema,
            "minimal_chart_spec_example": {
                "chart_id": f"approved_entity_{chart_type}",
                "chart_type": chart_type,
                "title": "Approved entity history",
                "time_range": {
                    "type": "absolute",
                    "start": "2026-06-17T00:00:00+00:00",
                    "end": "2026-06-18T00:00:00+00:00",
                },
                "series": [
                    {
                        "series_id": "approved_entity",
                        "label": "Approved Entity",
                        "source": {
                            "type": "entity",
                            "entity_id": "<one approved_entity_ids value>",
                            "attribute": None,
                        },
                        "role": "primary",
                        "render_as": render_as,
                        "transform": {"operation": "none", "window": None},
                        "unit": None,
                    }
                ],
                "overlays": [],
                "x_axis": {"type": "time"},
                "y_axis": {},
                "notes": [],
            },
        }
        return {
            "model": self.planner_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are the Isolinear planner. Return only JSON that validates "
                        "against the supplied PlannerResult schema."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(prompt_payload, separators=(",", ":")),
                },
            ],
            "stream": stream,
            # Thinking mode and Ollama structured-output format are mutually
            # exclusive: Ollama suppresses thinking when format is set.  When
            # streaming (reasoning requested) we omit format and rely on the
            # system-prompt schema guidance + _strip_markdown_json post-processing.
            # Non-streaming calls keep format for strict constrained decoding.
            **({"think": True} if stream else {"format": result_schema}),
            "options": {
                "temperature": 0,
                # Cap thinking tokens on the think pass so simple queries don't
                # spend 30-40 s generating 1500+ reasoning tokens. The result
                # pass (stream=False) is uncapped: it produces the final JSON and
                # needs enough tokens to complete the structured output.
                **({"num_predict": 512} if stream else {}),
            },
        }


def _chart_family_from_schema(result_schema: Any) -> tuple[str, str]:
    """Derive (chart_type, render_as) from a family-specific planner schema."""
    chart_type = "time_series"
    render_as = "line"
    try:
        chart_spec = result_schema["properties"]["chart_spec"]["properties"]
        chart_type = chart_spec["chart_type"]["enum"][0]
        render_as = chart_spec["series"]["items"]["properties"]["render_as"]["enum"][0]
    except (KeyError, IndexError, TypeError):
        pass
    return chart_type, render_as


def _setup_disabled(entry_id: str, code: str) -> dict[str, Any]:
    return {
        "accepted": True,
        "code": code,
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "enabled": False,
        "provider": None,
        "orchestration": model_provider_setup_side_effects(),
    }


def _has_ollama_planner_config(config_data: Any) -> bool:
    return (
        isinstance(config_data, Mapping)
        and config_data.get("model_provider_type") == MODEL_PROVIDER_OLLAMA_COMPATIBLE
        and isinstance(config_data.get("model_endpoint_url"), str)
        and config_data["model_endpoint_url"].strip().startswith(("http://", "https://"))
        and isinstance(config_data.get("planner_model"), str)
        and bool(config_data["planner_model"].strip())
    )


def _strip_markdown_json(text: str) -> str:
    """Strip markdown code fences that thinking-mode models wrap around JSON output."""
    text = text.strip()
    if text.startswith("```"):
        # Drop the opening fence line (```json or ```)
        text = text.split("\n", 1)[-1]
        # Drop the closing fence
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return text


def _ollama_chat_url(endpoint_url: str) -> str:
    if endpoint_url.rstrip("/").endswith("/api/chat"):
        return endpoint_url.rstrip("/")
    return f"{endpoint_url.rstrip('/')}/api/chat"


def _ollama_tags_url(endpoint_url: str) -> str:
    if endpoint_url.rstrip("/").endswith(MODEL_PROVIDER_HEALTH_PATH):
        return endpoint_url.rstrip("/")
    return f"{endpoint_url.rstrip('/')}{MODEL_PROVIDER_HEALTH_PATH}"


def _provider_failure(code: str, message: str, *, retry_safe: bool) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": code,
        "provider_role": "planner",
        "retry_safe": retry_safe,
        "message": message,
    }


def _provider_response_summary(response_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": response_payload.get("model"),
        "done": response_payload.get("done"),
        "done_reason": response_payload.get("done_reason"),
        "prompt_eval_count": response_payload.get("prompt_eval_count"),
        "eval_count": response_payload.get("eval_count"),
    }


def _ollama_model_names(response_payload: Any) -> list[str]:
    if not isinstance(response_payload, dict) or not isinstance(response_payload.get("models"), list):
        return []
    names: list[str] = []
    for item in response_payload["models"]:
        if not isinstance(item, dict):
            continue
        for key in ("name", "model"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                names.append(value.strip())
    return names


def _planner_model_is_listed(planner_model: str, model_names: list[str]) -> bool:
    return any(name == planner_model or name.startswith(f"{planner_model}:") for name in model_names)
