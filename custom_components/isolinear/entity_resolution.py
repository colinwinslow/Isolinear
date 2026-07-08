"""Entity resolution for job orchestration (ADR-0035 step 1).

The selection seam (invariant #1): semantic-alias injection, the D1
deterministic specificity ranking, the D2 model selector + ADR-0024 expansion
+ ADR-0028 composition prune, clarification-answer entity resolution, and the
ADR-0022/0023 deterministic render-family/envelope routing with overlay
composition (family routes from entity KIND before planning; the model never
chooses chart_type). Layer L1. See docs/specs/job-orchestration-split.md.
"""
from __future__ import annotations

import logging
import re

from .const import DOMAIN
from copy import deepcopy
from .entity_catalog import DATA_ENTITY_CATALOG
from .history_retrieval import (
    backfill_catalog_units_from_state,
    classify_series_kind,
)
from .model_provider import (
    get_model_provider_planner,
    load_entity_selector_schema,
)
from .orchestration_store import (
    SELECT_ENTITY_PHASE_LABEL,
    _call_planner_with_optional_reasoning,
    _live_reasoning_callback,
)
from .semantic_memory import (
    _iso_utc_now,
    _sanitize_prompt_for_storage,
    resolve_alias_injection,
    save_semantic_alias,
    semantic_memory_store_for,
)
from .snapshot_assembly import (
    _clarification_option_for_item,
    _option_id_for_entity,
)
from typing import Any

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_IN_PROMPT = re.compile(r"\b[a-z0-9_]+\.[a-z0-9_]+\b")


# ADR-0024 D2 expansion: deterministic D1 results whose token scoring may be
# *incomplete* and so warrant a model validation/expansion pass. Explicit
# entity IDs (already certain) and semantic-alias injection (user-confirmed,
# deterministic) are left unchanged. Overlay composition is handled by the
# separate ADR-0028 prune pass (it may *over*-include, not under-include).
_D2_EXPANSION_SOURCES = frozenset({"catalog_label", "catalog_label_specificity"})


def _composition_has_shared_token(prompt: str, items: list[dict[str, Any]]) -> bool:
    """True if two or more composition candidates match the prompt on a shared token.

    A shared prompt token across candidates (e.g. the location word "kitchen"
    matching both ``sensor.kitchen_ecobee_temperature`` and
    ``binary_sensor.kitchen_door``) is the noise-match signal ADR-0028 routes to the
    model: at least one candidate may rest only on that shared word rather than being
    the prompt's subject. When every candidate matches on a distinct token there is no
    noise to prune and the deterministic composition stands.
    """
    prompt_token_set = set(_prompt_tokens(prompt))
    seen: set[str] = set()
    for item in items:
        matched = _catalog_item_meaningful_tokens(item) & prompt_token_set
        if matched & seen:
            return True
        seen |= matched
    return False


def _prune_composition_with_model(
    hass: Any,
    entry_id: str,
    prompt: str,
    catalog_items: list[dict[str, Any]],
    selection: dict[str, Any],
    *,
    store: dict[str, Any] | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    """ADR-0028 D6: drop noise matches from an overlay composition via the model.

    The deterministic matcher composes any numeric + state entity sharing a prompt
    token, so an entity matched only on a shared location word ("kitchen") can enter
    the set and break planning ("when was the kitchen door open" composed the kitchen
    *temperature* as the primary). When the composition's candidates share a token,
    hand the candidate set to the D2 selector and keep the subset the prompt is
    actually about; the pruned set then re-routes through ``_resolve_render_family``
    by entity kind (invariant #9 unchanged). On model abstention/failure, or an empty
    or unchanged result, the deterministic composition stands — never worse than today.
    """
    candidate_items = selection.get("candidate_items") or []
    if len(candidate_items) < 2 or not _composition_has_shared_token(prompt, candidate_items):
        return selection
    pruned = _run_model_entity_selection(
        hass, entry_id, prompt, catalog_items,
        candidate_items=candidate_items,
        store=store, job_id=job_id,
    )
    if not pruned["accepted"]:
        return selection
    pruned_ids = pruned["entity_ids"]
    if not pruned_ids or set(pruned_ids) == set(selection["entity_ids"]):
        return selection
    _LOGGER.debug(
        "Isolinear entity resolution: composition prune %s -> %s "
        "(source: model_entity_selection)",
        selection["entity_ids"],
        pruned_ids,
    )
    return pruned


def _resolve_entity_selection_with_model(
    hass: Any,
    entry_id: str,
    prompt: str,
    catalog_items: list[dict[str, Any]],
    selection: dict[str, Any],
    *,
    store: dict[str, Any] | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    """Apply ADR-0024 D2 model entity selection to a D1 result.

    * **Residue path** — D1 returned a clarification (tie / zero match). The
      model picks from the candidate set; on acceptance it replaces the
      clarification, otherwise the caller falls through to user clarification.
    * **Expansion path** — D1 confidently resolved a single token-match entity
      (``catalog_label`` / ``catalog_label_specificity``). The model re-runs
      against the full catalog with the D1 pick as context to confirm, expand,
      or correct it. If the model abstains or is absent, D1's result stands.

    Other accepted sources (explicit entity ID, overlay composition, semantic
    alias) are returned unchanged.
    """
    if not selection["accepted"]:
        if selection["code"] != "entity_selection_requires_clarification":
            return selection
        d2 = _run_model_entity_selection(
            hass, entry_id, prompt, catalog_items,
            candidate_items=selection.get("candidate_items", catalog_items),
            store=store, job_id=job_id,
        )
        return d2 if d2["accepted"] else selection

    if selection.get("source") == "numeric_with_overlay":
        # ADR-0028 D6: prune noise matches from an overlay composition.
        return _prune_composition_with_model(
            hass, entry_id, prompt, catalog_items, selection,
            store=store, job_id=job_id,
        )

    if selection.get("source") not in _D2_EXPANSION_SOURCES:
        return selection
    d1_ids = selection["entity_ids"]
    selected = set(d1_ids)
    if all(item["entity_id"] in selected for item in catalog_items):
        # D1 already covers the whole catalog — nothing left to expand to.
        return selection
    d2 = _run_model_entity_selection(
        hass, entry_id, prompt, catalog_items,
        candidate_items=catalog_items,
        store=store, job_id=job_id,
        d1_selected_ids=d1_ids,
    )
    if d2["accepted"]:
        _LOGGER.debug(
            "Isolinear entity resolution: D2 expansion %s -> %s (source: model_entity_selection)",
            d1_ids,
            d2["entity_ids"],
        )
        return d2
    return selection


def _run_model_entity_selection(
    hass: Any,
    entry_id: str,
    prompt: str,
    catalog_items: list[dict[str, Any]],
    candidate_items: list[dict[str, Any]],
    *,
    store: dict[str, Any] | None = None,
    job_id: str | None = None,
    d1_selected_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Try model-driven entity selection for ADR-0024 D2.

    Two callers, one mechanism:

    * **Residue path** — D1 could not resolve (a top-score tie or zero matches).
      ``candidate_items`` is the tied subset or the full catalog, and
      ``d1_selected_ids`` is ``None``.
    * **Expansion path** (D2 expansion, 2026-06-23) — D1 confidently resolved a
      single token-match entity. ``candidate_items`` is the *full* catalog and
      ``d1_selected_ids`` carries the D1 pick so the model can validate it and
      add any entity the prompt mentions that token scoring missed (e.g. "AC"
      → ``climate.kitchen_ecobee``, which shares no token with the word "AC").

    Returns an accepted selection with ``source: model_entity_selection`` when
    the model picks a valid approved set, or a rejected result when the model
    abstains, the provider is absent, or the chosen IDs are off-allowlist. The
    caller falls through to user clarification (residue) or to D1's confident
    result (expansion) on any rejection.
    """
    planner = get_model_provider_planner(hass, entry_id)
    if planner is None or not hasattr(planner, "select_entity"):
        return {"accepted": False, "code": "no_model_provider_for_entity_selection"}

    candidate_entity_ids = [item["entity_id"] for item in candidate_items]
    if not candidate_entity_ids:
        return {"accepted": False, "code": "no_candidates_for_entity_selection"}

    catalog_entity_ids = {item["entity_id"] for item in catalog_items}
    request = {
        "prompt": prompt,
        "candidate_entity_ids": candidate_entity_ids,
        "candidate_labels": {
            item["entity_id"]: item.get("friendly_name") or item["entity_id"]
            for item in candidate_items
        },
    }
    if d1_selected_ids:
        request["already_selected_entity_ids"] = list(d1_selected_ids)
    schema = load_entity_selector_schema(candidate_entity_ids)
    # ADR-0025 D1/D7: stream the selection thinking into the per-job live slot so
    # the wait-feedback covers this model call too. Only when streaming is
    # supported (callback accepted) and we have a job to attribute it to.
    on_reasoning = (
        _live_reasoning_callback(store, job_id, stage=SELECT_ENTITY_PHASE_LABEL)
        if store is not None and job_id is not None
        else None
    )
    result = _call_planner_with_optional_reasoning(
        planner.select_entity, request, result_schema=schema, on_reasoning=on_reasoning
    )
    if not result.get("accepted"):
        return {"accepted": False, "code": "model_entity_selection_provider_failure"}

    selection_result = result.get("selection_result")
    if not isinstance(selection_result, dict):
        return {"accepted": False, "code": "model_entity_selection_malformed_result"}

    if selection_result.get("status") != "entity_selected":
        return {"accepted": False, "code": "model_entity_selection_abstained"}

    chosen_ids = selection_result.get("entity_ids")
    if not isinstance(chosen_ids, list) or not chosen_ids:
        return {"accepted": False, "code": "model_entity_selection_empty_result"}

    candidate_set = set(candidate_entity_ids)
    invalid_ids = [
        eid for eid in chosen_ids
        if not isinstance(eid, str) or eid not in catalog_entity_ids or eid not in candidate_set
    ]
    if invalid_ids:
        return {"accepted": False, "code": "model_entity_selection_out_of_allowlist"}

    return {
        "accepted": True,
        "code": "accepted",
        "entity_ids": list(dict.fromkeys(eid for eid in chosen_ids if isinstance(eid, str))),
        "source": "model_entity_selection",
    }


def _inject_semantic_aliases(
    hass: Any,
    entry_id: str,
    prompt: str,
    catalog_items: list[dict[str, Any]],
    selection: dict[str, Any],
) -> dict[str, Any]:
    """Compose user-confirmed semantic-alias entities into the entity selection.

    A saved alias whose natural names match the prompt resolves a concept the
    prompt's own words never name (e.g. "AC" -> ``climate.kitchen_ecobee``). The
    mapping was user-confirmed, so selecting it is deterministic, not a silent
    guess (invariant #1); the injected entities compose with whatever resolved
    directly. With no store (the default) or no match, the selection is returned
    unchanged. See ADR-0009/0010 and docs/specs/semantic-alias-live-wiring.md.
    """
    store = semantic_memory_store_for(hass, entry_id)
    injection = resolve_alias_injection(
        semantic_memory_store=store,
        entity_catalog=catalog_items,
        prompt=prompt,
    )
    injected = injection["injected_entity_ids"]
    if not injected:
        return selection

    direct_ids = list(selection["entity_ids"]) if selection.get("accepted") else []
    composed = direct_ids + [eid for eid in injected if eid not in direct_ids]
    _LOGGER.debug(
        "Isolinear entity resolution: semantic alias injection matched %s -> "
        "injected %s; composed selection %s (source: semantic_alias)",
        injection["matched_alias_ids"],
        injected,
        composed,
    )
    return {
        "accepted": True,
        "code": "accepted",
        "entity_ids": composed,
        "source": "semantic_alias",
        "matched_alias_ids": injection["matched_alias_ids"],
    }


def _alias_display_entries(
    hass: Any,
    entry_id: str,
    matched_alias_ids: list[str],
) -> list[dict[str, str]]:
    """Build ``snapshot.aliases`` display entries for matched semantic aliases.

    Fail-open: a missing store or unfound alias ID is silently skipped (display
    sugar, not an error). See docs/specs/semantic-alias-save-tranche2.md.
    """
    if not matched_alias_ids:
        return []
    store = semantic_memory_store_for(hass, entry_id)
    if not isinstance(store, dict):
        return []
    by_id = {alias["alias_id"]: alias for alias in store.get("aliases", [])}
    entries: list[dict[str, str]] = []
    for alias_id in matched_alias_ids:
        alias = by_id.get(alias_id)
        if not isinstance(alias, dict):
            continue
        names = alias.get("natural_names") or []
        meaning = alias.get("meaning", {})
        entity_id = meaning.get("entity_id")
        meaning_type = meaning.get("type")
        if names and entity_id and meaning_type:
            # entity_id lets the card show the alias inside the matching legend
            # row's disclosure rather than a separate list (ADR-0027 D6/C5).
            entries.append({
                "name": names[0],
                "meaning": f"{entity_id} ({meaning_type})",
                "entity_id": entity_id,
            })
    return entries


def _maybe_save_semantic_alias(
    hass: Any,
    entry_id: str,
    job: dict[str, Any],
    *,
    option_id: str,
    selected_entity_id: str,
) -> None:
    """Save a user-confirmed semantic alias on "Use and remember" (Tranche 2).

    Best-effort and non-blocking: a missing suggestion (job started before this
    version), a validation failure, or a save failure logs and returns — the
    clarification answer proceeds exactly as ``remember: false`` would. See
    docs/specs/semantic-alias-save-tranche2.md §5.
    """
    suggestion = job.get("alias_suggestions", {}).get(option_id)
    if not suggestion or suggestion.get("entity_id") != selected_entity_id:
        return

    alias = {
        "alias_id": suggestion["alias_id"],
        "natural_names": suggestion["natural_names"],
        "meaning": {"type": "entity", "entity_id": selected_entity_id},
        "source": "user_confirmed",
        "created_from_prompt": _sanitize_prompt_for_storage(job.get("prompt", "")),
        "created_at": _iso_utc_now(),
        "enabled": True,
    }
    result = save_semantic_alias(hass, entry_id, alias)
    if result["accepted"]:
        _LOGGER.info(
            "Isolinear semantic memory: saved alias %s -> %s (names %s)",
            alias["alias_id"],
            selected_entity_id,
            alias["natural_names"],
        )
    else:
        _LOGGER.warning(
            "Isolinear semantic memory: alias save failed for %s (%s); "
            "clarification answer proceeds without remembering",
            selected_entity_id,
            result.get("error"),
        )


def select_prompt_entity_ids(prompt: str, catalog_items: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministically select scaffold entity IDs from prompt text and catalog labels."""
    _LOGGER.debug(
        "Isolinear entity resolution: catalog has %d approved entities: %s",
        len(catalog_items),
        [item.get("entity_id") for item in catalog_items],
    )

    explicit_entity_ids = _unique(ENTITY_ID_IN_PROMPT.findall(prompt.lower()))
    if explicit_entity_ids:
        _LOGGER.debug(
            "Isolinear entity resolution: explicit entity IDs in prompt -> %s",
            explicit_entity_ids,
        )
        return {
            "accepted": True,
            "code": "accepted",
            "entity_ids": explicit_entity_ids,
            "source": "explicit_entity_id",
        }

    matches = [
        item
        for item in catalog_items
        if _catalog_item_matches_prompt(prompt, item)
    ]
    _LOGGER.debug(
        "Isolinear entity resolution: %d catalog match(es) for prompt %r: %s",
        len(matches),
        prompt,
        [
            {"entity_id": item.get("entity_id"), "score": _catalog_item_match_score(prompt, item)}
            for item in matches
        ],
    )

    if len(matches) == 1:
        _LOGGER.debug(
            "Isolinear entity resolution: single match -> %s (source: catalog_label)",
            matches[0].get("entity_id"),
        )
        return {
            "accepted": True,
            "code": "accepted",
            "entity_ids": [matches[0]["entity_id"]],
            "source": "catalog_label",
        }
    if len(matches) > 1:
        # A fuzzy prompt that matches one or more numeric series plus one or more
        # state (binary/categorical) entities composes deterministically into
        # numeric lines + shaded overlays rather than asking the user to pick one.
        # All-numeric and all-state multi-matches still clarify.
        match_kinds = [(item, classify_series_kind(item)) for item in matches]
        numeric_matches = [item for item, kind in match_kinds if kind == "numeric"]
        binary_matches = [item for item, kind in match_kinds if kind == "binary_state"]
        categorical_matches = [item for item, kind in match_kinds if kind not in ("numeric", "binary_state")]
        # Categorical entities (e.g. climate) compose as overlays only when the
        # match included a domain synonym token — otherwise it's a noise match on a
        # shared location word like "kitchen". Binary entities always compose.
        prompt_token_set = set(_prompt_tokens(prompt))
        intentional_categorical = [
            item for item in categorical_matches
            if _entity_matches_via_domain_synonym(item, prompt_token_set)
        ]
        state_matches = binary_matches + intentional_categorical
        # Type-hint filter: when the prompt contains measurement-type tokens
        # (e.g. "temperatures") and multiple numeric entities have incompatible
        # device_classes, keep only the ones matching the hinted type. This
        # prevents e.g. a power sensor sharing a location name from being charted
        # alongside temperature sensors because both score on the location token.
        numeric_matches = _filter_numerics_by_type_hint(numeric_matches, prompt_token_set)
        if numeric_matches and state_matches:
            composition_items = numeric_matches + state_matches
            selected = [item["entity_id"] for item in composition_items]
            _LOGGER.debug(
                "Isolinear entity resolution: overlay composition "
                "(%d numeric + %d state) -> %s (source: numeric_with_overlay)",
                len(numeric_matches),
                len(state_matches),
                selected,
            )
            return {
                "accepted": True,
                "code": "accepted",
                "entity_ids": selected,
                "source": "numeric_with_overlay",
                # ADR-0028: carry the matched items so the orchestration can route
                # this composition through the model prune pass (D6) when its
                # candidates share a non-distinctive token.
                "candidate_items": composition_items,
            }
        # Specificity tie-break (ADR-0024 D1): when one candidate matches strictly
        # more of its distinctive tokens than every other, the prompt named it
        # ("kitchen door" → kitchen_door, not kitchen_ecobee). Selecting the
        # uniquely best-specified approved entity is not a silent guess (invariant
        # #1); a top-score tie is genuine ambiguity and still clarifies.
        scored = [(item, _catalog_item_match_score(prompt, item)) for item in matches]
        best_score = max(score for _, score in scored)
        top_matches = [item for item, score in scored if score == best_score]
        _LOGGER.debug(
            "Isolinear entity resolution: specificity scores %s; best=%d; "
            "top_matches=%s",
            [(item.get("entity_id"), score) for item, score in scored],
            best_score,
            [item.get("entity_id") for item in top_matches],
        )
        if len(top_matches) == 1:
            _LOGGER.debug(
                "Isolinear entity resolution: unique top scorer -> %s (source: catalog_label_specificity)",
                top_matches[0].get("entity_id"),
            )
            return {
                "accepted": True,
                "code": "accepted",
                "entity_ids": [top_matches[0]["entity_id"]],
                "source": "catalog_label_specificity",
            }
        _LOGGER.debug(
            "Isolinear entity resolution: tie at score %d -> clarification needed for %s",
            best_score,
            [item.get("entity_id") for item in top_matches],
        )
        return {
            "accepted": False,
            "code": "entity_selection_requires_clarification",
            "message": "Multiple approved entities match this question; choose one.",
            "options": [
                _clarification_option_for_item(item, can_remember=True) for item in top_matches
            ],
            "candidate_items": top_matches,
        }

    return {
        "accepted": False,
        "code": "entity_selection_requires_clarification" if catalog_items else "no_approved_entities_available",
        "message": (
            "Choose which approved entity Isolinear should use for this question."
            if catalog_items
            else "No approved entities are available for this config entry."
        ),
        "options": [
            _clarification_option_for_item(item, can_remember=True) for item in catalog_items
        ],
        "candidate_items": catalog_items,
    }


def _resolve_render_envelope(
    catalog_items: list[dict[str, Any]],
    requested_entity_ids: list[str],
) -> dict[str, Any]:
    """Compute the capability envelope for the resolved entity set (ADR-0023).

    Returns the ADR-0022 routing dict augmented with:

    - ``families``: ordered list of families the data shape can support (first
      is the safe default; empty for ``mixed``).
    - ``default_family``: first family in the list, or ``"mixed"`` when none.
    - ``shape``: human-readable label for the resolved data shape.

    Single-numeric entities get the full ``[time_series, histogram,
    aggregate_bar]`` envelope so the model can choose intent.  All other shapes
    keep a single-member envelope identical to the ADR-0022 single-family path.
    """
    routing = _resolve_render_family(catalog_items, requested_entity_ids)
    family = routing["family"]
    if family == "time_series":
        if len(routing["numeric_entity_ids"]) == 1:
            families: list[str] = ["time_series", "histogram", "aggregate_bar"]
            shape = "single_numeric"
        else:
            families = ["time_series"]
            shape = "multi_numeric"
    elif family == "timeline":
        families = ["timeline"]
        shape = "all_categorical"
    elif family == "time_series_overlay":
        families = ["time_series_overlay"]
        shape = "numeric_with_overlay"
    else:
        families = []
        shape = "mixed_unsupported"
    return {
        **routing,
        "families": families,
        "default_family": families[0] if families else family,
        "shape": shape,
    }


def _resolve_render_family(
    catalog_items: list[dict[str, Any]],
    requested_entity_ids: list[str],
) -> dict[str, Any]:
    """Deterministically choose the render family from resolved entity kinds (ADR-0022).

    Families: ``time_series`` (all numeric), ``timeline`` (all binary/categorical),
    ``time_series_overlay`` (exactly one numeric primary line + one or more
    binary/categorical ``shaded_intervals`` overlays — ADR-0022 D4/D5), and
    ``mixed`` (an ambiguous numeric+categorical set, e.g. two numeric series mixed
    with a binary, where the primary line cannot be chosen deterministically).
    """
    by_id = {item["entity_id"]: item for item in catalog_items}
    numeric_entity_ids: list[str] = []
    binary_entity_ids: list[str] = []
    state_entity_ids: list[str] = []  # all non-numeric (binary + categorical), for the timeline family
    kinds: set[str] = set()
    for entity_id in requested_entity_ids:
        item = by_id.get(entity_id)
        if item is None:
            continue
        kind = classify_series_kind(item)
        kinds.add(kind)
        if kind == "numeric":
            numeric_entity_ids.append(entity_id)
        elif kind == "binary_state":
            binary_entity_ids.append(entity_id)
            state_entity_ids.append(entity_id)
        else:
            state_entity_ids.append(entity_id)
    has_numeric = bool(numeric_entity_ids)
    has_state = bool(state_entity_ids)
    # Overlay composition: one or more numeric series + one or more state entities
    # (binary or categorical). All numerics plot; state entities shade colored
    # bands behind them (binary = "on" region; categorical = per-value colored).
    overlay_eligible = bool(numeric_entity_ids) and bool(state_entity_ids)
    if has_numeric and has_state:
        family = "time_series_overlay" if overlay_eligible else "mixed"
    elif has_state:
        family = "timeline"
    else:
        family = "time_series"
    return {
        "family": family,
        "kinds": sorted(kinds),
        "numeric_entity_ids": numeric_entity_ids,
        "categorical_entity_ids": state_entity_ids,
        "overlay_entity_ids": state_entity_ids,
    }


# Binary states treated as "on"/active for shaded_intervals overlays (ADR-0022).
_OVERLAY_ACTIVE_VALUES = ["on"]


# Color maps for well-known categorical overlay domains (hex RGB strings, light tints).
_CLIMATE_OVERLAY_COLOR_MAP = {"cooling": "#B8D4EE", "heating": "#FFCF9E"}


_ENTITY_ID_SHAPED = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")


def _resolve_overlay_label(
    entity_id: str,
    item: dict[str, Any],
    overlay_labels: dict[str, Any] | None,
) -> str:
    """Resolve an overlay's display label (ADR-0027 D4/C3).

    Fallback order: the model-authored ``overlay_labels`` entry (when present and
    not just the raw entity_id) → the catalog friendly name → a derived
    ``"<friendly_name> — running state"`` when only the entity_id is known.
    """
    model_label = (overlay_labels or {}).get(entity_id)
    if isinstance(model_label, str) and model_label.strip() and not _ENTITY_ID_SHAPED.match(model_label.strip()):
        return model_label.strip()
    friendly = item.get("friendly_name")
    if isinstance(friendly, str) and friendly.strip():
        return friendly.strip()
    return f"{entity_id} — running state"


def _compose_state_overlays(
    chart_spec: dict[str, Any],
    *,
    overlay_entity_ids: list[str],
    catalog_items: list[dict[str, Any]],
    overlay_labels: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Inject state entities as shaded_intervals overlays on a numeric spec.

    Binary entities shade "on" regions (ADR-0022 D4/D5). Categorical entities
    shade per-state-value colored bands: climate entities use blue for cooling
    and orange for heating; other categorical entities use a renderer auto-palette.
    Overlay labels are model-authored (``overlay_labels``) with a deterministic
    fallback (ADR-0027 D4); overlay structure stays integration-composed.
    """
    by_id = {item["entity_id"]: item for item in catalog_items}
    composed = deepcopy(chart_spec)
    overlays = list(composed.get("overlays") or [])
    for index, entity_id in enumerate(overlay_entity_ids, start=1):
        item = by_id.get(entity_id, {})
        label = _resolve_overlay_label(entity_id, item, overlay_labels)
        kind = classify_series_kind(item)
        overlay: dict[str, Any] = {
            "overlay_id": f"overlay-{index:03d}",
            "label": label,
            "source": {"type": "entity", "entity_id": entity_id, "attribute": None},
            "render_as": "shaded_intervals",
        }
        if kind == "binary_state":
            overlay["active_values"] = list(_OVERLAY_ACTIVE_VALUES)
        else:
            domain = entity_id.split(".")[0] if "." in entity_id else ""
            if domain == "climate":
                overlay["color_map"] = dict(_CLIMATE_OVERLAY_COLOR_MAP)
                overlay["source"]["attribute"] = "hvac_action"
        overlays.append(overlay)
    composed["overlays"] = overlays
    return composed


def _compose_binary_overlays(
    chart_spec: dict[str, Any],
    *,
    overlay_entity_ids: list[str],
    catalog_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Backward-compatible alias for _compose_state_overlays."""
    return _compose_state_overlays(
        chart_spec,
        overlay_entity_ids=overlay_entity_ids,
        catalog_items=catalog_items,
    )


def _approved_catalog_items(hass: Any, entry_id: str) -> list[dict[str, Any]]:
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    store = entry_data.get(DATA_ENTITY_CATALOG, {}) if isinstance(entry_data, dict) else {}
    items = store.get("items", []) if isinstance(store, dict) else []
    if not isinstance(items, list):
        return []
    return backfill_catalog_units_from_state(
        hass,
        [
            item
            for item in items
            if isinstance(item, dict) and item.get("visible_to_agent") is True
        ],
    )


# Domain-level synonym tokens that supplement entity_id/friendly_name for matching.
# These bypass the ≥4-char filter so short abbreviations like "ac" work.
_DOMAIN_SYNONYMS: dict[str, frozenset[str]] = {
    "climate": frozenset({
        "ac", "hvac", "thermostat", "conditioning",
        "cooling", "heating", "heat", "cool", "furnace",
    }),
}


def _catalog_item_meaningful_tokens(item: dict[str, Any]) -> set[str]:
    item_tokens = set(_prompt_tokens(" ".join(str(value or "") for value in [
        item.get("entity_id", "").replace(".", " "),
        item.get("friendly_name", ""),
        item.get("area", ""),
        item.get("device_name", ""),
    ])))
    meaningful = {
        token
        for token in item_tokens
        if len(token) >= 4 and token not in {"sensor", "binary"}
    }
    domain = item.get("entity_id", "").split(".")[0]
    meaningful |= _DOMAIN_SYNONYMS.get(domain, frozenset())
    return meaningful


def _entity_matches_via_domain_synonym(item: dict[str, Any], prompt_token_set: set[str]) -> bool:
    """True if the entity matched the prompt on at least one domain synonym token."""
    domain = item.get("entity_id", "").split(".")[0]
    return bool(_DOMAIN_SYNONYMS.get(domain, frozenset()) & prompt_token_set)


# Measurement-type hint tokens → device_class values they imply.
# When these tokens appear in the prompt, numeric matches are filtered to
# entities whose device_class matches, preventing e.g. a power sensor sharing
# a location label from being charted alongside temperature sensors.
_NUMERIC_TYPE_HINTS: list[tuple[frozenset[str], frozenset[str]]] = [
    (
        frozenset({"temp", "temps", "temperature", "temperatures"}),
        frozenset({"temperature"}),
    ),
    (
        frozenset({"humidity", "humid"}),
        frozenset({"humidity"}),
    ),
    (
        frozenset({"power", "watt", "watts"}),
        frozenset({"power"}),
    ),
    (
        frozenset({"energy", "kwh"}),
        frozenset({"energy"}),
    ),
    (
        frozenset({"current", "amps", "ampere"}),
        frozenset({"current"}),
    ),
]


def _filter_numerics_by_type_hint(
    numeric_matches: list[dict[str, Any]],
    prompt_token_set: set[str],
) -> list[dict[str, Any]]:
    """Narrow numeric matches to entities whose device_class matches a prompt type hint.

    If the prompt contains measurement-type tokens (e.g. "temperatures") and the
    numeric matches include entities with incompatible device_classes, keep only
    those whose device_class matches a hinted type. A prompt may hint several
    distinct measurement types at once (e.g. "is the temperature correlated with
    the humidity") — target classes across every firing hint are unioned so a
    cross-metric prompt keeps every metric it names, not just the first hint
    category checked. When no type hint fires or all numerics already match, the
    list is returned unchanged.
    """
    target_classes: set[str] = set()
    for hint_tokens, hint_target_classes in _NUMERIC_TYPE_HINTS:
        if hint_tokens & prompt_token_set:
            target_classes |= hint_target_classes
    if not target_classes:
        return numeric_matches
    matching = [
        item for item in numeric_matches
        if item.get("device_class") in target_classes
    ]
    if matching and len(matching) < len(numeric_matches):
        return matching
    return numeric_matches


def _catalog_item_match_score(prompt: str, item: dict[str, Any]) -> int:
    """Count how many of an entity's distinctive tokens appear in the prompt.

    The count (not just a boolean) is what separates false ambiguity — one entity
    matched on its specific tokens while another shares only a generic word
    ("kitchen door" vs "kitchen ecobee") — from genuine ambiguity, where rivals
    tie on a shared term ("show thermostat history" with two thermostats).
    See ADR-0024 D1.
    """
    prompt_tokens = set(_prompt_tokens(prompt))
    return len(_catalog_item_meaningful_tokens(item) & prompt_tokens)


def _catalog_item_matches_prompt(prompt: str, item: dict[str, Any]) -> bool:
    return _catalog_item_match_score(prompt, item) >= 1


def _prompt_tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", value.lower())


def _unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _selected_clarification_entity(
    hass: Any,
    entry_id: str,
    clarification: dict[str, Any],
    option_id: str,
) -> dict[str, Any]:
    returned_option_ids = {
        option.get("option_id")
        for option in clarification.get("options", [])
        if isinstance(option, dict)
    }
    if option_id not in returned_option_ids:
        return {
            "accepted": False,
            "code": "unknown_clarification_option",
            "approved_entity_catalog_read": False,
        }

    catalog_items = _approved_catalog_items(hass, entry_id)
    matches = [
        item
        for item in catalog_items
        if isinstance(item.get("entity_id"), str) and _option_id_for_entity(item["entity_id"]) == option_id
    ]
    if len(matches) == 1:
        return {
            "accepted": True,
            "code": "accepted",
            "entity_id": matches[0]["entity_id"],
            "catalog_items": catalog_items,
            "approved_entity_catalog_read": True,
        }
    if len(matches) > 1:
        return {
            "accepted": False,
            "code": "ambiguous_clarification_option",
            "approved_entity_catalog_read": True,
        }

    return {
        "accepted": False,
        "code": "clarification_option_not_in_approved_catalog",
        "approved_entity_catalog_read": True,
    }
