"""Planning pipeline for job orchestration (ADR-0035 step 1).

The model-provider planning seam: the planner request builder, _plan_once
(one full plan + gate pass: contract validation, family/envelope gate, entity
allowlist, deterministic catalog-unit overwrite), and the bounded re-plan
loop over recoverable output-quality gates (spec planner-replan; fresh-sample
temperature on attempts >= 1; never re-plans a legitimate clarify), plus the
model-provider plan/retry-policy record builders. Layer L2 (imports
contracts/store/entity_resolution downward). See
docs/specs/job-orchestration-split.md.
"""
from __future__ import annotations

import logging

from .const import DOMAIN
from copy import deepcopy
from .entity_resolution import (
    _LOGGER,
    _approved_catalog_items,
    _compose_state_overlays,
    _resolve_render_envelope,
)
from .history_dispatch import (
    _hass_time_zone,
    _history_now,
)
from .in_process_renderer import first_real_vertical_slice_enabled
from .model_provider import (
    PLANNER_RENDER_FAMILIES,
    get_model_provider_planner,
    load_planner_result_schema,
    planner_client_metadata,
)
from .orchestration_contracts import (
    _source_snapshot_entity_ids,
    validate_chart_spec_contract,
    validate_model_provider_output_entities,
    validate_model_provider_plan_contract,
    validate_model_provider_retry_policy_contract,
    validate_planner_result_contract,
)
from .orchestration_store import (
    PLAN_CHART_PHASE_LABEL,
    _call_planner_with_optional_reasoning,
    _live_reasoning_callback,
    _model_provider_retry_policy_attempt_number,
    _store_validated_model_provider_retry_policy,
)
from .snapshot_assembly import (
    _model_provider_failure_contains_forbidden_material,
    _safe_model_provider_failure_code,
    _safe_model_provider_failure_message,
)
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Plan-quality rejections a fresh planner sample can plausibly recover from —
# the model produced structurally-broken output, never a legitimate terminal.
# `model_provider_planner_not_chart_spec_ready` is deliberately EXCLUDED: after
# `validate_planner_result_contract` passes, that code necessarily means the
# model returned a non-ready but legitimate terminal status — `clarification_needed`
# or `cannot_resolve` (the planner-result schema enum is {chart_spec_ready,
# clarification_needed, cannot_resolve}) — so re-planning it would override the
# model's correct choice. See docs/specs/planner-replan-on-validation-failure.md.
_PLANNER_REPLAN_TRIGGER_CODES = frozenset(
    {"invalid_model_provider_chart_spec", "invalid_planner_result"}
)


# A re-plan re-sends the SAME request, but the planner's structured pass runs at
# temperature 0 (near-greedy decoding), so an unperturbed retry mostly reproduces
# the rejected plan token-for-token (probed live against gemma4:e4b: identical
# outputs on a frozen request, modulo GPU-scheduling noise). Re-plan attempts
# therefore sample at a nonzero temperature so the "fresh sample" the spec
# intends is real; constrained decoding still enforces the result schema, and
# the first attempt keeps the reproducible temperature-0 default.
_PLANNER_REPLAN_TEMPERATURE = 0.7


def _record_model_provider_plan(
    store: dict[str, Any],
    *,
    hass: Any,
    entry_id: str,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Plan a chart, re-planning up to a bounded cap on a recoverable rejection.

    A single planner sample that trips a recoverable quality gate (a variance
    tail — e.g. a duplicate-source ChartSpec) should not fall straight through to
    the fallback when the next sample would validate. This wraps the single
    planning attempt (:func:`_plan_once`) in a bounded, deterministic re-plan
    loop. On exhaustion the last attempt's failure is returned unchanged, so no
    failure surface differs from today when re-plan doesn't help. Every result
    carries ``planner_replan_attempts`` (extra samples taken; 0 = first plan
    validated). See docs/specs/planner-replan-on-validation-failure.md.
    """
    max_replan = _configured_max_planner_replan_attempts(hass, entry_id)
    replan_attempts = 0
    while True:
        result = _plan_once(
            store,
            hass=hass,
            entry_id=entry_id,
            job=job,
            source_snapshot=source_snapshot,
            replan_attempt=replan_attempts,
        )
        recoverable = (
            not result.get("accepted")
            and result.get("code") in _PLANNER_REPLAN_TRIGGER_CODES
        )
        if recoverable and replan_attempts < max_replan:
            replan_attempts += 1
            continue
        result["planner_replan_attempts"] = replan_attempts
        if replan_attempts and result.get("accepted"):
            _LOGGER.info(
                "Isolinear planner recovered a valid plan after %d re-plan "
                "attempt(s) (a prior sample failed %s)",
                replan_attempts,
                result.get("code"),
            )
        elif replan_attempts:
            _LOGGER.warning(
                "Isolinear planner exhausted %d re-plan attempt(s); returning "
                "failure %s",
                replan_attempts,
                result.get("code"),
            )
        return result


def _plan_once(
    store: dict[str, Any],
    *,
    hass: Any,
    entry_id: str,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    replan_attempt: int = 0,
) -> dict[str, Any]:
    planner = get_model_provider_planner(hass, entry_id)
    if planner is None:
        if first_real_vertical_slice_enabled(hass, entry_id):
            return {
                "accepted": False,
                "code": "model_provider_planner_not_configured",
                "model_provider_called": False,
                "model_provider_plan": None,
                "chart_spec": None,
                "validation": {
                    "accepted": False,
                    "code": "model_provider_planner_not_configured",
                    "error": "The real render path requires a configured model-provider planner.",
                },
            }
        return {
            "accepted": True,
            "code": "model_provider_planner_not_configured",
            "model_provider_called": False,
            "model_provider_plan": None,
            "chart_spec": None,
        }

    # Compute the capability envelope (ADR-0023): derives the ordered set of
    # chart families the resolved entities can support, then lets the model
    # select intent within that set.  Wraps ADR-0022 routing for backward compat.
    catalog_items = _approved_catalog_items(hass, entry_id)
    requested_entity_ids = _source_snapshot_entity_ids(source_snapshot)
    routing = _resolve_render_envelope(catalog_items, requested_entity_ids)
    if routing["family"] == "mixed":
        return {
            "accepted": False,
            "code": "mixed_chart_composition_unsupported",
            "model_provider_called": False,
            "model_provider_plan": None,
            "chart_spec": None,
            "validation": {
                "accepted": False,
                "code": "mixed_chart_composition_unsupported",
                "error": (
                    "This question mixes more than one numeric series with a state entity, so the primary "
                    "chart cannot be chosen automatically; ask about a single numeric series with the state "
                    "overlay."
                ),
                "kinds": routing["kinds"],
            },
        }

    # The model only ever produces the chartable *series* (ADR-0022 D5): for the
    # overlay composition it plans the single numeric primary as a time_series
    # line, and the integration injects the state entities (binary or categorical)
    # as shaded_intervals overlays afterwards. The planner sees only series entities.
    is_overlay = routing["family"] == "time_series_overlay"
    planner_family = "time_series" if is_overlay else routing["family"]
    series_entity_ids = (
        routing["numeric_entity_ids"]
        if planner_family == "time_series"
        else routing["categorical_entity_ids"]
    )
    request = _model_provider_planner_request(
        hass=hass,
        job=job,
        source_snapshot=source_snapshot,
        entity_ids=series_entity_ids or None,
        overlay_entity_ids=routing.get("overlay_entity_ids") or [] if is_overlay else [],
    )
    # Pass the full capability envelope so chart_type becomes a multi-value enum
    # when multiple families are available (ADR-0023 D2).  Entity IDs remain
    # pinned to exactly the disclosed set (invariant #1).
    result_schema = load_planner_result_schema(
        planner_family, envelope=routing["families"], entity_ids=request["approved_entity_ids"]
    )
    # ADR-0025 D1: stream the chart-planning thinking into the per-job live slot
    # so concurrent ~1s polls surface it in the chart area while the model runs.
    plan_on_reasoning = _live_reasoning_callback(
        store, job["job_id"], stage=PLAN_CHART_PHASE_LABEL
    )
    provider_response = _call_planner_with_optional_reasoning(
        planner.plan_chart,
        request,
        result_schema=result_schema,
        on_reasoning=plan_on_reasoning,
        # Re-plan attempts sample fresh (see _PLANNER_REPLAN_TEMPERATURE); the
        # first attempt keeps the reproducible temperature-0 default.
        temperature=_PLANNER_REPLAN_TEMPERATURE if replan_attempt > 0 else None,
    )
    provider_summary = {
        "provider": planner_client_metadata(planner),
        "response_code": provider_response.get("code") if isinstance(provider_response, dict) else None,
    }
    if not isinstance(provider_response, dict) or not provider_response.get("accepted"):
        if isinstance(provider_response, dict):
            retry_policy_result = _record_model_provider_retry_policy(
                store,
                job=job,
                source_snapshot=source_snapshot,
                provider=planner_client_metadata(planner),
                request=request,
                provider_response=provider_response,
            )
            if retry_policy_result["accepted"]:
                policy = retry_policy_result["model_provider_retry_policy"]
                return {
                    "accepted": False,
                    "code": policy["failure"]["code"],
                    "model_provider_called": True,
                    "model_provider": provider_summary,
                    "model_provider_retry_policy": policy,
                    "model_provider_retry_policy_written": True,
                    "validation": retry_policy_result.get("validation"),
                }
            return {
                "accepted": False,
                "code": retry_policy_result["code"],
                "validation": retry_policy_result.get("validation"),
                "model_provider_called": True,
                "model_provider": provider_summary,
            }
        return {
            "accepted": False,
            "code": "model_provider_planning_failed",
            "model_provider_called": True,
            "model_provider": provider_summary,
        }

    planner_result = provider_response.get("planner_result")
    planner_result_validation = validate_planner_result_contract(planner_result)
    if not planner_result_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_planner_result",
            "validation": planner_result_validation,
            "model_provider_called": True,
            "model_provider": provider_summary,
        }

    if not isinstance(planner_result, dict) or planner_result.get("status") != "chart_spec_ready":
        return {
            "accepted": False,
            "code": "model_provider_planner_not_chart_spec_ready",
            "validation": planner_result_validation,
            "model_provider_called": True,
            "model_provider": provider_summary,
        }

    chart_spec = planner_result.get("chart_spec")
    chart_spec_validation = validate_chart_spec_contract(chart_spec)
    if not chart_spec_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_model_provider_chart_spec",
            "validation": chart_spec_validation,
            "model_provider_called": True,
            "model_provider": provider_summary,
        }

    # The planner must emit a `unit` per series but is never told the real one, so
    # it guesses (observed live: °C on °F sensors). Overwrite it deterministically
    # from the authoritative catalog unit so no model-guessed unit ships to the
    # renderer (codegen reads history_series units; the Pillow fallback reads these).
    _apply_catalog_units(chart_spec, catalog_items)

    # Out-of-envelope gate (ADR-0023 D3): reject a model-chosen chart_type that
    # is outside the deterministic capability envelope computed before planning.
    family_validation = validate_model_provider_chart_family(chart_spec, routing)
    if not family_validation["accepted"]:
        return {
            "accepted": False,
            "code": family_validation["code"],
            "validation": family_validation,
            "model_provider_called": True,
            "model_provider": provider_summary,
        }

    # Deterministically inject state overlays (binary + categorical) as shaded_intervals (ADR-0022 D4/D5).
    if is_overlay and isinstance(chart_spec, dict):
        overlay_labels = planner_result.get("overlay_labels") if isinstance(planner_result, dict) else None
        chart_spec = _compose_state_overlays(
            chart_spec,
            overlay_entity_ids=routing["overlay_entity_ids"],
            catalog_items=catalog_items,
            overlay_labels=overlay_labels if isinstance(overlay_labels, dict) else None,
        )
        composed_validation = validate_chart_spec_contract(chart_spec)
        if not composed_validation["accepted"]:
            return {
                "accepted": False,
                "code": "invalid_model_provider_chart_spec",
                "validation": composed_validation,
                "model_provider_called": True,
                "model_provider": provider_summary,
            }
        planner_result = deepcopy(planner_result)
        planner_result["chart_spec"] = chart_spec

    entity_validation = validate_model_provider_output_entities(
        planner_result,
        chart_spec,
        source_snapshot,
        approved_catalog_entity_ids=[item["entity_id"] for item in catalog_items],
    )
    if not entity_validation["accepted"]:
        return {
            "accepted": False,
            "code": entity_validation["code"],
            "validation": entity_validation,
            "model_provider_called": True,
            "model_provider": provider_summary,
        }

    provider_plan = _build_model_provider_plan(
        store,
        job=job,
        source_snapshot=source_snapshot,
        request=request,
        provider=provider_response.get("provider") or planner_client_metadata(planner),
        planner_result=planner_result,
        chart_spec=chart_spec,
    )
    provider_plan_validation = validate_model_provider_plan_contract(provider_plan)
    if not provider_plan_validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_integration_model_provider_plan",
            "validation": provider_plan_validation,
            "model_provider_called": True,
            "model_provider": provider_summary,
        }

    return {
        "accepted": True,
        "code": "accepted",
        "model_provider_called": True,
        "model_provider_plan": provider_plan,
        "chart_spec": deepcopy(chart_spec),
        "validation": provider_plan_validation,
        "model_provider": provider_summary,
    }


def _configured_max_planner_replan_attempts(hass: Any, entry_id: str) -> int:
    """Extra planner samples allowed when a plan fails a recoverable quality gate.

    Mirrors :func:`_configured_max_codegen_repair_attempts`. ``0`` disables the
    re-plan loop (single-attempt behavior — the clean revert switch). Default
    ``1`` (promoted from the opt-in slice-1 landing): one extra sample recovers
    the observed variance tails. See
    ``docs/specs/planner-replan-on-validation-failure.md``.
    """
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    entry = entry_data.get("entry") if isinstance(entry_data, dict) else None
    options = getattr(entry, "options", {}) or {}
    value = options.get("max_planner_replan_attempts") if hasattr(options, "get") else None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 1
    return value


def _build_model_provider_plan(
    store: dict[str, Any],
    *,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    request: dict[str, Any],
    provider: dict[str, Any],
    planner_result: dict[str, Any],
    chart_spec: dict[str, Any],
) -> dict[str, Any]:
    provider_plan_number = store["next_model_provider_plan_number"]
    provider_plan_id = f"{store['entry_id']}-provider-plan-{provider_plan_number:03d}"
    return {
        "provider_plan_id": provider_plan_id,
        "config_entry_id": store["entry_id"],
        "job_id": job["job_id"],
        "source_snapshot_id": source_snapshot["snapshot_id"],
        "provider": {
            "type": provider.get("type") or "ollama_compatible",
            "role": provider.get("role") or "planner",
            "endpoint_url": provider.get("endpoint_url") or "",
            "model": provider.get("model") or provider.get("planner_model") or "",
        },
        "request": deepcopy(request),
        "status": "chart_spec_ready",
        "planner_result": deepcopy(planner_result),
        "chart_spec": deepcopy(chart_spec),
        "validation": {
            "status": "pass",
            "summary": "PlannerResult and provider-produced ChartSpec validate before storage.",
            "checks": [
                {"name": "planner_result_schema", "status": "pass"},
                {"name": "chart_spec_schema", "status": "pass"},
                {"name": "entity_allowlist", "status": "pass"},
                {"name": "worker", "status": "not_called"},
                {"name": "chart_rendering", "status": "not_called"},
            ],
        },
        "warnings": [
            "model_provider_planning_scaffold",
            "ollama_compatible_planner",
            "worker_not_called",
            "chart_rendering_not_started",
        ],
    }


def _record_model_provider_retry_policy(
    store: dict[str, Any],
    *,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    provider: dict[str, Any],
    request: dict[str, Any],
    provider_response: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(provider_response.get("retry_safe"), bool):
        return {
            "accepted": False,
            "code": "invalid_model_provider_failure",
            "validation": {
                "accepted": False,
                "code": "invalid_model_provider_failure",
                "error": "Provider failure retry_safe must be boolean.",
            },
        }
    if _model_provider_failure_contains_forbidden_material(provider_response):
        return {
            "accepted": False,
            "code": "model_provider_failure_forbidden_material",
            "validation": {
                "accepted": False,
                "code": "model_provider_failure_forbidden_material",
                "error": "Provider failure text contained forbidden material.",
            },
        }

    policy = _build_model_provider_retry_policy(
        store,
        job=job,
        source_snapshot=source_snapshot,
        provider=provider,
        request=request,
        provider_response=provider_response,
    )
    validation = validate_model_provider_retry_policy_contract(policy)
    if not validation["accepted"]:
        return {
            "accepted": False,
            "code": "invalid_integration_model_provider_retry_policy",
            "validation": validation,
        }

    _store_validated_model_provider_retry_policy(store, policy)
    return {
        "accepted": True,
        "code": "model_provider_retry_policy_recorded",
        "model_provider_retry_policy": deepcopy(policy),
        "validation": validation,
    }


def _build_model_provider_retry_policy(
    store: dict[str, Any],
    *,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    provider: dict[str, Any],
    request: dict[str, Any],
    provider_response: dict[str, Any],
) -> dict[str, Any]:
    policy_number = store["next_model_provider_retry_policy_number"]
    attempt_number = _model_provider_retry_policy_attempt_number(store, job["job_id"])
    eligible = provider_response.get("retry_safe") is True
    delay_seconds = min(60, 5 * (2 ** (attempt_number - 1))) if eligible else 0
    return {
        "policy_id": f"{store['entry_id']}-model-provider-retry-policy-{policy_number:03d}",
        "type": "isolinear_model_provider_retry_policy",
        "config_entry_id": store["entry_id"],
        "job_id": job["job_id"],
        "source_snapshot_id": source_snapshot["snapshot_id"],
        "provider": {
            "type": provider.get("type") or "ollama_compatible",
            "role": provider.get("role") or "planner",
            "endpoint_url": provider.get("endpoint_url") or "",
            "model": provider.get("model") or provider.get("planner_model") or "",
        },
        "request": deepcopy(request),
        "failure": {
            "stage": "model_provider_planning",
            "code": _safe_model_provider_failure_code(provider_response.get("code")),
            "message": _safe_model_provider_failure_message(provider_response.get("message")),
            "retry_safe": eligible,
        },
        "decision": {
            "eligible": eligible,
            "reason": "model_provider_failure_retry_safe" if eligible else "model_provider_failure_not_retry_safe",
            "manual_retry_allowed": eligible,
            "automatic_retry_scheduled": False,
        },
        "backoff": {
            "strategy": "bounded_exponential_scaffold",
            "attempt_number": attempt_number,
            "delay_seconds": delay_seconds,
            "max_delay_seconds": 60,
            "jitter_applied": False,
        },
        "validation": {
            "status": "pass",
            "summary": "Model-provider retry/backoff policy validates before storage.",
            "checks": [
                {"name": "model_provider_failure_observed", "status": "pass"},
                {"name": "model_provider_retry_policy_schema", "status": "pass"},
                {"name": "model_provider_failure_text_sanitized", "status": "pass"},
                {"name": "automatic_retry_not_scheduled", "status": "pass"},
            ],
        },
        "warnings": [
            "model_provider_retry_backoff_policy_scaffold",
            "automatic_retry_not_scheduled",
            "bounded_in_memory_retry_policy",
        ],
    }


def validate_model_provider_chart_family(
    chart_spec: dict[str, Any],
    envelope: dict[str, Any],
) -> dict[str, Any]:
    """Gate: reject a model-chosen chart_type outside the capability envelope (ADR-0023 D3).

    ``envelope`` is the routing dict returned by ``_resolve_render_envelope``.
    When the envelope is empty (mixed shape) or has a single member, this gate
    is a no-op — existing mixed/overlay checks already handle those cases.
    """
    families = envelope.get("families") or []
    if len(families) <= 1:
        return {"accepted": True}
    allowed_chart_types = [
        PLANNER_RENDER_FAMILIES[f]["chart_type"]
        for f in families
        if f in PLANNER_RENDER_FAMILIES
    ]
    chosen = chart_spec.get("chart_type") if isinstance(chart_spec, dict) else None
    if chosen in allowed_chart_types:
        return {"accepted": True}
    return {
        "accepted": False,
        "code": "model_provider_chart_family_out_of_envelope",
        "chosen_family": chosen,
        "allowed_families": allowed_chart_types,
    }


def _model_provider_planner_request(
    *,
    hass: Any,
    job: dict[str, Any],
    source_snapshot: dict[str, Any],
    entity_ids: list[str] | None = None,
    overlay_entity_ids: list[str] | None = None,
) -> dict[str, Any]:
    # ``entity_ids`` restricts what the planner may chart as series; for the
    # overlay composition only the numeric primary is disclosed (ADR-0022 D5).
    entity_ids = entity_ids if entity_ids is not None else _source_snapshot_entity_ids(source_snapshot)
    request: dict[str, Any] = {
        "prompt": job.get("prompt") if isinstance(job.get("prompt"), str) else "",
        "approved_entity_ids": entity_ids,
        "history_entity_ids": entity_ids,
        "now": _history_now(hass).isoformat(timespec="seconds"),
        "time_zone": _hass_time_zone(hass),
        "output_schema": "PlannerResult",
    }
    if overlay_entity_ids:
        request["overlay_entity_ids"] = list(overlay_entity_ids)
    return request


def _apply_catalog_units(chart_spec: Any, catalog_items: list[dict[str, Any]]) -> None:
    """Overwrite each series' ``unit`` with the authoritative catalog unit, in place.

    The PlannerResult schema requires a ``unit`` on every series, but the planner
    prompt never carries the real unit, so the model guesses (observed live: ``°C``
    on ``°F`` sensors). The authoritative unit is the catalog's
    ``unit_of_measurement``; setting it here means no model-guessed unit reaches
    either render path. Only overwrites series whose entity is in the catalog;
    aggregate sources use their first resolvable entity. Overlays (binary/
    categorical, unit ``None``) are left untouched.
    """
    if not isinstance(chart_spec, dict):
        return
    units = {
        item["entity_id"]: item.get("unit_of_measurement")
        for item in catalog_items
        if isinstance(item, dict) and isinstance(item.get("entity_id"), str)
    }
    for series in chart_spec.get("series", []):
        if not isinstance(series, dict):
            continue
        source = series.get("source")
        if not isinstance(source, dict):
            continue
        entity_id = source.get("entity_id")
        if not isinstance(entity_id, str):
            entity_id = next(
                (e for e in source.get("entity_ids", []) if isinstance(e, str)), None
            )
        if isinstance(entity_id, str) and entity_id in units:
            series["unit"] = units[entity_id]
