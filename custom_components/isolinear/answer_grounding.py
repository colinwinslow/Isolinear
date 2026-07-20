"""Answer grounding check — deterministic verdict verification via a claims ledger.

Spec:  docs/specs/answer-grounding-check.md
ADR:   ADR-0031 D8a (the open verdict half)
BDD:   bdd/answer-grounding-check/answer-grounding-check-bdd.md

The check runs in job_orchestration after a successful codegen render, before the
artifact is served.  It uses the ``claims`` list the generated code emits to
independently verify stated values and verdicts.

Return value of ``run_grounding_check``:
    outcome: "pass" | "verified" | "unverified_caveat" | "repair_contradicted"
             | "repair_soft"
    answer_verification: "verified" | "unverified" | None  (None → absent from schema)
    withheld: bool  (True → remove answer_text before serving)
    synthetic_error: dict | None  (fed to repair_chart_code on repair outcomes)
    diagnostics: dict
"""

from __future__ import annotations

import math
import re
from typing import Any

# ---------------------------------------------------------------------------
# Two-tier guarantee (Scenario J — verbatim in spec, card copy, diagnostics)
# ---------------------------------------------------------------------------

TWO_TIER_GUARANTEE = (
    "Inside the boundary: value↔data — the integration independently "
    "recomputed the number from allowlisted history using the claim’s own "
    "recipe; the verdict provably follows from the declared rule at that reference. "
    "Outside the boundary: internal consistency only (value↔verdict↔rule). "
    "The caveat means ‘not independently reproduced,’ not ‘probably fine.’"
)

# A computed answer that stringifies a non-finite float — "nan", "inf",
# "-inf", "infinity" — must never reach the user. The per-claim degeneracy
# check (step 3) only guards a claim's numeric value, but a plain aggregate
# ("what's the average…") emits an answer_text with NO verdict claim, so it
# reaches the "no claims → pass" branch unscanned. This tripwire scans the
# answer_text string directly (whole-word, case-insensitive) so it fires with
# or without claims. Live-observed 0.2.32: "…the average … was nan °F" served.
_DEGENERATE_ANSWER_RE = re.compile(r"(?<![A-Za-z])(nan|[-+]?inf(?:inity)?)(?![A-Za-z])", re.IGNORECASE)
# An unevaluated f-string / format template that leaked into the sentence (e.g.
# "the average was {mean_avg:.2f}") is degenerate too. A natural answer sentence
# never contains braces, so this is near-zero false positive. NOTE: "0.00" is
# intentionally NOT treated as degenerate — a genuinely zero result (e.g. a delta
# of 0.00 °F) is a valid answer.
_UNFILLED_PLACEHOLDER_RE = re.compile(r"\{[^{}]*\}")

# ---------------------------------------------------------------------------
# Numeric tolerance (absolute) for value ↔ reference comparison
# ---------------------------------------------------------------------------

_TOLERANCE = 0.05

# ---------------------------------------------------------------------------
# Helpers: series lookup and windowing
# ---------------------------------------------------------------------------


def _find_series(entity_id: str, history_series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for s in history_series:
        if isinstance(s, dict) and s.get("entity_id") == entity_id:
            return [p for p in s.get("points", []) if isinstance(p, dict)]
    return []


def _find_series_meta(entity_id: str, history_series: list[dict[str, Any]]) -> dict[str, Any] | None:
    for s in history_series:
        if isinstance(s, dict) and s.get("entity_id") == entity_id:
            return s
    return None


def _in_window(pts: list[dict], window: dict | None) -> list[dict]:
    if not window or not isinstance(window, dict):
        return pts
    start = window.get("start")
    end = window.get("end")
    result = pts
    if isinstance(start, (int, float)):
        result = [p for p in result if isinstance(p.get("ts_epoch_ms"), (int, float)) and p["ts_epoch_ms"] >= start]
    if isinstance(end, (int, float)):
        result = [p for p in result if isinstance(p.get("ts_epoch_ms"), (int, float)) and p["ts_epoch_ms"] < end]
    return result


def _numeric_vals(pts: list[dict]) -> list[float]:
    out = []
    for p in pts:
        v = p.get("value")
        if isinstance(v, (int, float)) and math.isfinite(float(v)):
            out.append(float(v))
    return out


def _delivered_span(history_series: list[dict]) -> tuple[int | None, int | None]:
    """Overall [min_ts, max_ts) of all delivered series, in epoch-ms."""
    lo: int | None = None
    hi: int | None = None
    for s in history_series:
        if not isinstance(s, dict):
            continue
        for p in s.get("points", []):
            t = p.get("ts_epoch_ms") if isinstance(p, dict) else None
            if isinstance(t, (int, float)):
                t = int(t)
                if lo is None or t < lo:
                    lo = t
                if hi is None or t > hi:
                    hi = t
    return lo, hi


def _window_within_span(window: dict, history_series: list[dict]) -> bool:
    span_lo, span_hi = _delivered_span(history_series)
    if span_lo is None:
        return False
    w_start = window.get("start")
    w_end = window.get("end")
    if isinstance(w_start, (int, float)) and w_start < span_lo:
        return False
    if isinstance(w_end, (int, float)) and span_hi is not None and w_end > span_hi + 1:
        return False
    return True


# ---------------------------------------------------------------------------
# Metric registry — recompute implementations (pure Python, no external libs)
# ---------------------------------------------------------------------------

# Shared time-grid resolution for multi-input recompute. Mirrors the ADR-0036
# `isolinear_analysis.align()` default (`freq="5min"`) so the grounding reference
# reproduces the SAME cross-sensor aggregate the model's aligned frame produced.
# Kept independent (pure Python, no pandas) — grounding is a drift-detector, not
# a shared code path with the sandbox helper.
_ALIGN_FREQ_MS = 300_000


def _resample_interpolate(pts: list[dict]) -> dict[int, float]:
    """Reproduce `Series.resample("5min").mean().interpolate()` in pure Python.

    Returns a bucket-index → value map over a CONTIGUOUS 5-minute grid from the
    first to the last populated bucket, with interior gaps linearly filled.
    Duplicate raw timestamps collapse to their mean first (matching align()'s
    `groupby(level=0).mean()`), so a timestamp with several samples still counts
    once, not once per sample.
    """
    by_ts: dict[int, list[float]] = {}
    for p in pts:
        ts = p.get("ts_epoch_ms")
        v = p.get("value")
        if isinstance(ts, (int, float)) and not isinstance(ts, bool) and isinstance(v, (int, float)) and math.isfinite(float(v)):
            by_ts.setdefault(int(ts), []).append(float(v))
    if not by_ts:
        return {}
    buckets: dict[int, list[float]] = {}
    for ts, vals in by_ts.items():
        buckets.setdefault(ts // _ALIGN_FREQ_MS, []).append(sum(vals) / len(vals))
    grid = {b: sum(vs) / len(vs) for b, vs in buckets.items()}
    known = sorted(grid)
    filled: dict[int, float] = {}
    for b in range(known[0], known[-1] + 1):
        if b in grid:
            filled[b] = grid[b]
            continue
        left = max(k for k in known if k < b)
        right = min(k for k in known if k > b)
        filled[b] = grid[left] + (grid[right] - grid[left]) * (b - left) / (right - left)
    return filled


def _compute_mean(inputs: list[str], window: dict | None, params: dict, hs: list[dict]) -> float | None:
    # Single input: plain mean of the in-window samples.
    if len(inputs) <= 1:
        vals = _numeric_vals(_in_window(_find_series(inputs[0] if inputs else "", hs), window))
        return (sum(vals) / len(vals)) if vals else None
    # Multi input (e.g. "the average of the kitchen and basement temperatures"):
    # the model plots a single cross-sensor mean series built from the aligned
    # frame (ADR-0036 align()), so the reference must average ACROSS entities on
    # the shared grid — not just inputs[0], which can never match a two-sensor
    # mean within tolerance (the e2e-11 empty-answer root cause). Resample each
    # input like align(), keep only buckets present in ALL inputs (align()'s
    # dropna), average across inputs per bucket, then mean over the grid.
    grids = [_resample_interpolate(_in_window(_find_series(eid, hs), window)) for eid in inputs]
    if any(not g for g in grids):
        return None
    common = set(grids[0])
    for g in grids[1:]:
        common &= set(g)
    if not common:
        return None
    row_means = [sum(g[b] for g in grids) / len(grids) for b in common]
    return sum(row_means) / len(row_means)


def _compute_delta(inputs: list[str], window: dict | None, params: dict, hs: list[dict]) -> float | None:
    vals = _numeric_vals(_in_window(_find_series(inputs[0] if inputs else "", hs), window))
    return (vals[-1] - vals[0]) if len(vals) >= 2 else None


def _compute_pearson_r(inputs: list[str], window: dict | None, params: dict, hs: list[dict]) -> float | None:
    if len(inputs) < 2:
        return None

    # Mirror the model's `align().corr().iloc[0, 1]` (ADR-0036): resample each
    # input onto the shared 5-min grid (like _compute_mean), pair the values on
    # buckets present in BOTH, then Pearson r. The old exact-timestamp
    # intersection returned None for real recorder data — two sensors sampled by
    # separate integrations share NO raw timestamps, so `set(map_a) & set(map_b)`
    # was empty and a correctly-computed correlation could never be verified
    # (open-queue (ff); the same class as the 0.2.37 multi-input _compute_mean
    # fix). Grounding stays an independent pure-Python drift-detector — no pandas.
    grid_a = _resample_interpolate(_in_window(_find_series(inputs[0], hs), window))
    grid_b = _resample_interpolate(_in_window(_find_series(inputs[1], hs), window))
    common = sorted(set(grid_a) & set(grid_b))
    if len(common) < 3:
        return None
    xs = [grid_a[b] for b in common]
    ys = [grid_b[b] for b in common]
    n = len(xs)
    sx, sy = sum(xs), sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sx2 = sum(x * x for x in xs)
    sy2 = sum(y * y for y in ys)
    den_sq = (n * sx2 - sx ** 2) * (n * sy2 - sy ** 2)
    if den_sq <= 0:
        return None
    return (n * sxy - sx * sy) / math.sqrt(den_sq)


def _compute_rolling_mean(inputs: list[str], window: dict | None, params: dict, hs: list[dict]) -> float | None:
    window_ms = params.get("window_ms")
    if not isinstance(window_ms, (int, float)) or window_ms <= 0:
        return None
    pts = _in_window(_find_series(inputs[0] if inputs else "", hs), window)
    ts_vals = sorted(
        [(int(p["ts_epoch_ms"]), float(p["value"])) for p in pts
         if isinstance(p.get("ts_epoch_ms"), (int, float))
         and isinstance(p.get("value"), (int, float))
         and math.isfinite(float(p["value"]))],
        key=lambda x: x[0],
    )
    if not ts_vals:
        return None
    rolling = []
    for i, (t, _) in enumerate(ts_vals):
        w = [v for ts, v in ts_vals if ts <= t and ts >= t - window_ms]
        if w:
            rolling.append(sum(w) / len(w))
    return (sum(rolling) / len(rolling)) if rolling else None


def _compute_daily_max(inputs: list[str], window: dict | None, params: dict, hs: list[dict]) -> float | None:
    vals = _numeric_vals(_in_window(_find_series(inputs[0] if inputs else "", hs), window))
    return max(vals) if vals else None


def _compute_daily_min(inputs: list[str], window: dict | None, params: dict, hs: list[dict]) -> float | None:
    vals = _numeric_vals(_in_window(_find_series(inputs[0] if inputs else "", hs), window))
    return min(vals) if vals else None


def _compute_hours_above(inputs: list[str], window: dict | None, params: dict, hs: list[dict]) -> float | None:
    threshold = params.get("threshold")
    if not isinstance(threshold, (int, float)):
        return None
    pts = _in_window(_find_series(inputs[0] if inputs else "", hs), window)
    pts = sorted(
        [p for p in pts if isinstance(p.get("ts_epoch_ms"), (int, float))],
        key=lambda p: p["ts_epoch_ms"],
    )
    if len(pts) < 2:
        return None
    total_ms = 0
    for i in range(len(pts) - 1):
        v = pts[i].get("value")
        if isinstance(v, (int, float)) and math.isfinite(float(v)) and float(v) > threshold:
            total_ms += max(0, pts[i + 1]["ts_epoch_ms"] - pts[i]["ts_epoch_ms"])
    return total_ms / (1000 * 3600)


# Default "active/on" states when a state_duration claim omits params['active'].
_DEFAULT_ACTIVE_STATES = frozenset({"on", "open", "true", "home", "detected", "1"})


def _compute_state_duration(inputs: list[str], window: dict | None, params: dict, hs: list[dict]) -> float | None:
    """Total milliseconds a binary/categorical entity spent in an active state (spec C4).

    Independent drift-detector for the timeline duration answer: mirrors
    ``_compute_hours_above``'s held-until-next-change accumulation but tests state
    MEMBERSHIP (params['active'], default on/open/…) instead of a numeric
    threshold, and returns milliseconds so it compares against the model's claim
    value (which sums the precomputed derived_intervals, in ms). Recomputed here
    from the RAW points — it does not trust the precompute — so a wrong served
    duration is still caught (grounding stays independent, ADR-0031 D8a).
    """
    active_param = params.get("active")
    if isinstance(active_param, (list, tuple, set)) and active_param:
        active = {str(v).lower() for v in active_param}
    else:
        active = set(_DEFAULT_ACTIVE_STATES)
    pts = _in_window(_find_series(inputs[0] if inputs else "", hs), window)
    pts = sorted(
        [p for p in pts if isinstance(p.get("ts_epoch_ms"), (int, float))],
        key=lambda p: p["ts_epoch_ms"],
    )
    if len(pts) < 2:
        return None
    total_ms = 0
    for i in range(len(pts) - 1):
        state = _state_at(pts[i], None)
        if state is not None and state.lower() in active:
            total_ms += max(0, int(pts[i + 1]["ts_epoch_ms"]) - int(pts[i]["ts_epoch_ms"]))
    # Hold a still-active FINAL segment to the global window end — the latest ts
    # across ALL delivered series — mirroring C1's _binary_on_regions, which holds
    # the last state to _history_window_end_dt (the global max). Without this, a
    # multi-entity timeline whose last point predates another series' end would
    # undercount the trailing on-time vs the precompute the model summed (arch
    # review). For a single entity ending "off" (the door anchor) this adds 0.
    last_state = _state_at(pts[-1], None)
    if last_state is not None and last_state.lower() in active:
        global_end = max(
            (int(p["ts_epoch_ms"]) for s in hs for p in (s.get("points") or [])
             if isinstance(p.get("ts_epoch_ms"), (int, float))),
            default=int(pts[-1]["ts_epoch_ms"]),
        )
        if window and isinstance(window.get("end"), (int, float)):
            global_end = min(global_end, int(window["end"]))
        total_ms += max(0, global_end - int(pts[-1]["ts_epoch_ms"]))
    return float(total_ms)


# metric → (recompute_fn, required_params)
_REGISTRY: dict[str, tuple] = {
    "mean": (_compute_mean, []),
    "delta": (_compute_delta, []),
    "pearson_r": (_compute_pearson_r, []),
    "rolling_mean": (_compute_rolling_mean, ["window_ms"]),
    "daily_max": (_compute_daily_max, []),
    "daily_min": (_compute_daily_min, []),
    "hours_above": (_compute_hours_above, ["threshold"]),
    "state_duration": (_compute_state_duration, []),
}

# Per-metric value tolerance overrides as (relative, absolute_floor). Absent → the
# default absolute _TOLERANCE (tuned for °F-scale values). state_duration values
# are ms-scaled and may be rounded for readability, so a fixed 0.05 is meaningless
# there: allow 2% or 1 minute, whichever is larger.
_METRIC_TOLERANCE: dict[str, tuple[float, float]] = {
    "state_duration": (0.02, 60000.0),
}


def _value_tolerance(metric: str, reference: float) -> float:
    entry = _METRIC_TOLERANCE.get(metric)
    if entry is None:
        return _TOLERANCE
    rel, floor = entry
    return max(floor, rel * abs(reference))


def _recompute(metric: str, inputs: list[str], window: dict | None, params: dict, hs: list[dict]) -> float | None:
    entry = _REGISTRY.get(metric)
    if entry is None:
        return None
    fn, _ = entry
    return fn(inputs, window, params, hs)


# ---------------------------------------------------------------------------
# Event anchors (spec §1a) — reproducibility criteria + re-detection.
#
# An anchor is {entity, attribute (None=state), to, from?, occurrence,
# search:{start,end}, resolved_at}. Reproducible iff ALL of: (1) entity is
# among the delivered series AND its raw-state kind (ADR-0022
# binary_state/categorical_state); (2) a crisp discrete transition — exact
# string equality of `to`/`from`, no fuzzy matching; (3) occurrence + search
# bounds select a unique index into the finite ordered transition list; (4)
# resolved_at lets the check confirm the *same* event. Any failure is
# "irreproducible by construction" — unverified-caveat, never attempted
# further (tranche-2 scope explicitly excludes analog thresholds, rate/shape
# conditions, and out-of-set entities).
# ---------------------------------------------------------------------------

_RAW_STATE_KINDS = ("binary_state", "categorical_state")


def _anchor_criteria_ok(
    anchor: Any,
    delivered_entity_ids: set[str],
    history_series: list[dict[str, Any]],
) -> tuple[bool, str]:
    if not isinstance(anchor, dict):
        return False, "anchor is not a dict"
    entity = anchor.get("entity")
    if not isinstance(entity, str) or entity not in delivered_entity_ids:
        return False, "anchor.entity is not among the delivered series"
    series_meta = _find_series_meta(entity, history_series)
    if series_meta is None or series_meta.get("kind") not in _RAW_STATE_KINDS:
        return False, "anchor.entity is not a raw-state (binary/categorical) series"
    to = anchor.get("to")
    if not isinstance(to, str) or not to:
        return False, "anchor.to must be a non-empty string (crisp discrete transition)"
    from_ = anchor.get("from")
    if from_ is not None and not isinstance(from_, str):
        return False, "anchor.from must be a string when given"
    occurrence = anchor.get("occurrence")
    if not isinstance(occurrence, int) or isinstance(occurrence, bool) or occurrence == 0:
        return False, "anchor.occurrence must be a non-zero integer (1-based; negative from end)"
    search = anchor.get("search")
    if (
        not isinstance(search, dict)
        or not isinstance(search.get("start"), (int, float))
        or not isinstance(search.get("end"), (int, float))
    ):
        return False, "anchor.search must supply numeric start/end bounds"
    if not isinstance(anchor.get("resolved_at"), (int, float)):
        return False, "anchor.resolved_at must be numeric"
    return True, ""


def _state_at(point: dict, attribute: str | None) -> str | None:
    if attribute:
        attrs = point.get("attrs")
        val = attrs.get(attribute) if isinstance(attrs, dict) else None
    else:
        val = point.get("raw_state")
        if val is None:
            val = point.get("value")
    return str(val) if val is not None else None


def _detect_transitions(
    pts: list[dict],
    attribute: str | None,
    to: str,
    from_: str | None,
    search: dict,
) -> list[int]:
    """Every transition INTO `to` (from `from_` if given) on the ordered raw-state
    timeline, restricted to transitions whose own timestamp lies in [start, end].

    Scans the full series (not just the search window) to know the state
    immediately preceding each candidate point — a transition at the search
    boundary still needs the prior state from outside it.
    """
    ordered = sorted(
        (p for p in pts if isinstance(p.get("ts_epoch_ms"), (int, float))),
        key=lambda p: p["ts_epoch_ms"],
    )
    start = search.get("start")
    end = search.get("end")
    transitions: list[int] = []
    prev_state: str | None = None
    for p in ordered:
        cur_state = _state_at(p, attribute)
        ts = int(p["ts_epoch_ms"])
        if prev_state is not None and cur_state == to and (from_ is None or prev_state == from_):
            if (start is None or ts >= start) and (end is None or ts <= end):
                transitions.append(ts)
        prev_state = cur_state
    return transitions


def _select_occurrence(transitions: list[int], occurrence: int) -> int | None:
    if not transitions:
        return None
    idx = occurrence - 1 if occurrence > 0 else occurrence
    try:
        return transitions[idx]
    except IndexError:
        return None


def _resolve_anchor(anchor: dict, history_series: list[dict[str, Any]]) -> int | None:
    """Re-detect the anchor's transition. Returns its ts_epoch_ms, or None if unfound."""
    pts = _find_series(anchor["entity"], history_series)
    transitions = _detect_transitions(
        pts, anchor.get("attribute"), anchor["to"], anchor.get("from"), anchor["search"]
    )
    return _select_occurrence(transitions, anchor["occurrence"])


# ---------------------------------------------------------------------------
# Rule application  (bands: [[threshold, label], …, [None, catch-all]])
# ---------------------------------------------------------------------------

def _apply_rule(rule: dict[str, Any], value: float) -> str | None:
    bands = rule.get("bands")
    if not isinstance(bands, list):
        return None
    basis = rule.get("basis", "value")
    cmp = abs(value) if basis == "abs" else value
    for band in bands:
        if not isinstance(band, (list, tuple)) or len(band) < 2:
            continue
        threshold, label = band[0], band[1]
        if threshold is None:
            return str(label)
        if isinstance(threshold, (int, float)) and cmp >= threshold:
            return str(label)
    return None


# ---------------------------------------------------------------------------
# Verdict matching — longest word-boundary match (negation safety)
# ---------------------------------------------------------------------------

def _longest_matching_label(labels: list[str], answer_text: str) -> str | None:
    answer_cf = answer_text.casefold()
    matched = []
    for label in labels:
        if not label:
            continue
        pattern = r"\b" + re.escape(label.casefold()) + r"\b"
        if re.search(pattern, answer_cf):
            matched.append(label)
    if not matched:
        return None
    return max(matched, key=len)


# ---------------------------------------------------------------------------
# Rule structure validation (step 1 helper)
# ---------------------------------------------------------------------------

def _validate_rule_structure(rule: Any) -> str | None:
    """Return an error string, or None if the rule is valid."""
    if not isinstance(rule, dict):
        return "rule must be a dict"
    bands = rule.get("bands")
    if not isinstance(bands, list) or not bands:
        return "rule.bands missing or empty"
    for b in bands:
        if not isinstance(b, (list, tuple)) or len(b) < 2:
            return "each band must be [threshold_or_null, label]"
    if bands[-1][0] is not None:
        return "last band must have null threshold (catch-all)"
    # Check for descending order (non-None thresholds)
    last_thresh = None
    for b in bands[:-1]:
        t = b[0]
        if not isinstance(t, (int, float)):
            return "non-final band thresholds must be numeric"
        if last_thresh is not None and t > last_thresh:
            return "rule.bands must be in descending threshold order"
        last_thresh = t
    return None


# ---------------------------------------------------------------------------
# Single-claim check (spec §3, steps 1–6)
# ---------------------------------------------------------------------------

def _check_claim(
    claim: Any,
    history_series: list[dict],
    delivered_entity_ids: set[str],
    answer_text: str | None,
) -> dict[str, Any]:
    """Check one claim.  Returns a dict with keys: outcome, code, message, details."""
    if not isinstance(claim, dict):
        return _soft("grounding_claim_malformed", "claim is not a dict", {})

    metric = claim.get("metric")
    inputs = claim.get("inputs") if isinstance(claim.get("inputs"), list) else []
    window = claim.get("window") if isinstance(claim.get("window"), dict) else None
    params = claim.get("params") if isinstance(claim.get("params"), dict) else {}
    value = claim.get("value")
    verdict = claim.get("verdict")
    rule = claim.get("rule")

    # state_duration is inherently descriptive ("how long was it open?") — there is
    # no yes/no judgment to contain, so a duration answer is value-only. gemma
    # nonetheless sometimes attaches a spurious verdict+rule to it despite the
    # prompt, which step-5/6 verdict containment then contradicts, withholding a
    # CORRECT duration (the timeline_render_gate saw this: value 540000 ms right,
    # outcome repair_contradicted). Null the verdict/rule here so the existing
    # value-only path (the (cc) precedent) value-verifies it via step 4. The
    # duration is still fully grounded — a WRONG value is still caught at step 4.
    if metric == "state_duration":
        verdict = None
        rule = None

    # ---- step 1: structure ------------------------------------------------
    if not metric or not isinstance(metric, str):
        return _soft("grounding_claim_malformed", "claim.metric missing or not a string", {})
    if not isinstance(inputs, list) or not inputs:
        return _soft("grounding_claim_malformed", "claim.inputs missing or empty", {})
    # Spec §1: claim.inputs must be among the job's delivered (allowlisted) series.
    # A claim citing a non-delivered entity is structurally malformed — repair it
    # rather than letting a fabricated value+verdict ride through as an
    # unverified caveat (invariant #1: the recompute only trusts delivered data).
    undelivered = [e for e in inputs if e not in delivered_entity_ids]
    if undelivered:
        return _soft(
            "grounding_claim_malformed",
            f"claim.inputs reference entities not in the delivered series: {undelivered}",
            {"undelivered_inputs": undelivered},
        )
    # A rule is only meaningful in service of a verdict — steps 5 (containment)
    # and 6 (consistency) both gate on `verdict is not None and rule is not None`.
    # So a rule with no verdict verifies nothing; validating it is pointlessly
    # strict and rejects the common (cc) shape where a small model omits the
    # verdict on a descriptive claim but leaves a vestigial `rule: {"bands": []}`
    # stub. Treat a verdict-less claim as value-only: skip rule validation, and
    # steps 5/6 are skipped anyway (verdict is None). The value is still
    # recomputed and verified at step 4.
    if rule is not None and verdict is not None:
        rule_err = _validate_rule_structure(rule)
        if rule_err:
            return _soft("grounding_claim_malformed", f"rule invalid: {rule_err}", {"rule_error": rule_err})

    # ---- step 2: recipe completeness --------------------------------------
    in_registry = metric in _REGISTRY
    is_anchored = isinstance(window, dict) and "anchor" in window
    if in_registry:
        required = _REGISTRY[metric][1]
        for rp in required:
            if rp not in params:
                return _soft(
                    "grounding_recipe_incomplete",
                    f"registry metric '{metric}' missing required param '{rp}'",
                    {"metric": metric, "missing_param": rp},
                )
        # Anchored windows resolve to absolute bounds at step 4 (anchor
        # re-detection); span-checking waits until bounds exist.
        if window and not is_anchored and not _window_within_span(window, history_series):
            return _caveat("grounding_window_outside_span", "window lies outside delivered data span", {"window": window})

    # ---- step 3: degeneracy -----------------------------------------------
    if value is not None:
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            return _contradicted(
                "grounding_nonfinite_value",
                f"non-finite value in claim: {value!r}",
                {"value": value},
            )

    # ---- step 4: anchor resolution + reference recompute -------------------
    reference: float | None = None
    effective_window = window
    if is_anchored:
        anchor = window.get("anchor")
        ok, reason = _anchor_criteria_ok(anchor, delivered_entity_ids, history_series)
        if not ok:
            return _caveat("grounding_anchor_unreproducible", reason, {"anchor": anchor})
        # Validate the window shape before the re-detection scan, not after —
        # a malformed direction/duration_ms shouldn't pay for walking the series.
        direction = window.get("direction")
        duration_ms = window.get("duration_ms")
        if direction not in ("after", "before") or not isinstance(duration_ms, (int, float)) or duration_ms < 0:
            return _soft(
                "grounding_claim_malformed",
                "anchored window requires direction ('after'|'before') and a non-negative duration_ms",
                {},
            )
        resolved_ts = _resolve_anchor(anchor, history_series)
        if resolved_ts is None:
            return _contradicted(
                "grounding_anchor_unfound",
                "no transition matching the anchor was found within the search bounds",
                {"anchor": anchor},
            )
        resolved_at = anchor.get("resolved_at")
        if int(resolved_ts) != int(resolved_at):
            return _contradicted(
                "grounding_anchor_mismatch",
                f"re-detected transition at {resolved_ts} does not match claimed resolved_at {resolved_at}",
                {"resolved_ts": resolved_ts, "resolved_at": resolved_at},
            )
        effective_window = (
            {"start": resolved_ts, "end": resolved_ts + duration_ms}
            if direction == "after"
            else {"start": resolved_ts - duration_ms, "end": resolved_ts}
        )
        if not _window_within_span(effective_window, history_series):
            return _caveat(
                "grounding_window_outside_span",
                "the resolved anchor window lies outside the delivered data span",
                {"window": effective_window},
            )

    if in_registry:
        reference = _recompute(metric, inputs, effective_window, params, history_series)
        if reference is not None and isinstance(value, (int, float)):
            tol = _value_tolerance(metric, reference)
            if abs(float(value) - reference) > tol:
                return _contradicted(
                    "grounding_value_mismatch",
                    f"stated value {value} differs from reference {reference:.4f} "
                    f"by more than tolerance {tol}",
                    {"value": value, "reference": reference, "tolerance": tol},
                )

    # ---- step 5: verdict containment --------------------------------------
    check_value = reference if reference is not None else (float(value) if isinstance(value, (int, float)) else None)
    if verdict is not None and rule is not None and isinstance(answer_text, str) and answer_text.strip():
        bands = rule.get("bands", []) if isinstance(rule, dict) else []
        labels = [str(b[1]) for b in bands if isinstance(b, (list, tuple)) and len(b) >= 2 and b[1] is not None]
        matched = _longest_matching_label(labels, answer_text)
        if matched is None:
            return _contradicted(
                "grounding_verdict_absent",
                "no band label found in answer_text (word-boundary search)",
                {"labels": labels, "answer_text_snippet": answer_text[:100]},
            )
        if matched.casefold() != str(verdict).casefold():
            return _contradicted(
                "grounding_verdict_ambiguous",
                f"longest matching label '{matched}' differs from claimed verdict '{verdict}'",
                {"matched": matched, "verdict": verdict},
            )

    # ---- step 6: verdict consistency (check value vs rule) ----------------
    if verdict is not None and rule is not None and check_value is not None:
        expected = _apply_rule(rule, check_value)
        if expected is not None and expected.casefold() != str(verdict).casefold():
            # Borderline guard: evaluate at check_value ± tolerance
            lo_label = _apply_rule(rule, check_value - _TOLERANCE)
            hi_label = _apply_rule(rule, check_value + _TOLERANCE)
            if lo_label != hi_label:
                # Borderline: pass with a diagnostics note
                return {
                    "outcome": "verified" if in_registry and reference is not None else "unverified_caveat",
                    "code": "grounding_borderline",
                    "message": (
                        f"verdict borderline at reference {check_value:.4f} ± {_TOLERANCE}: "
                        f"expected '{expected}' but labels straddle the band edge — pass"
                    ),
                    "details": {
                        "check_value": check_value,
                        "tolerance": _TOLERANCE,
                        "expected": expected,
                        "lo_label": lo_label,
                        "hi_label": hi_label,
                    },
                }
            return _contradicted(
                "grounding_verdict_contradicted",
                f"verdict '{verdict}' contradicts rule at check_value {check_value:.4f}: expected '{expected}'",
                {"verdict": verdict, "expected": expected, "check_value": check_value},
            )

    # ---- All checks passed ------------------------------------------------
    if in_registry and reference is not None:
        return {"outcome": "verified", "code": "verified", "message": "all checks passed", "details": {"reference": reference}}
    return _caveat("unverified_no_reference", "metric not in registry or no reference computed", {"metric": metric})


def _soft(code: str, message: str, details: dict) -> dict:
    return {"outcome": "repair_soft", "code": code, "message": message, "details": details}


def _caveat(code: str, message: str, details: dict) -> dict:
    return {"outcome": "unverified_caveat", "code": code, "message": message, "details": details}


def _contradicted(code: str, message: str, details: dict) -> dict:
    return {"outcome": "repair_contradicted", "code": code, "message": message, "details": details}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_grounding_check(
    render_metadata: dict[str, Any],
    history_series: list[dict[str, Any]],
) -> dict[str, Any]:
    """Check the grounding of a codegen render result.

    Args:
        render_metadata: The render_metadata dict from the sandbox result
                         (contains answer_text and optional claims list).
        history_series:  The history series used for codegen (with ts_epoch_ms).

    Returns a dict:
        outcome:           "pass" | "verified" | "unverified_caveat"
                           | "repair_contradicted" | "repair_soft"
        answer_verification: "verified" | "unverified" | None
        withheld:          True → caller should suppress answer_text before serving
        synthetic_error:   dict for repair_chart_code, or None
        diagnostics:       diagnostic record (includes TWO_TIER_GUARANTEE)
    """
    if not isinstance(render_metadata, dict):
        render_metadata = {}

    answer_text = render_metadata.get("answer_text")
    if isinstance(answer_text, str):
        answer_text = answer_text.strip() or None

    claims_raw = render_metadata.get("claims")
    claims = claims_raw if isinstance(claims_raw, list) else []

    delivered_ids: set[str] = {
        s["entity_id"]
        for s in history_series
        if isinstance(s, dict) and isinstance(s.get("entity_id"), str)
    }

    # ---- Degenerate-answer tripwire ---------------------------------------
    # A non-finite value stringified into the answer ("nan"/"inf") must never be
    # served — even when no claim is emitted (a plain aggregate carries an
    # answer_text but no verdict claim, so step 3 never runs). Route it through
    # the repair loop; on exhaustion the repair_contradicted outcome withholds
    # the answer (chart still served, answer suppressed) rather than showing
    # "nan °F".
    if isinstance(answer_text, str) and (
        _DEGENERATE_ANSWER_RE.search(answer_text)
        or _UNFILLED_PLACEHOLDER_RE.search(answer_text)
    ):
        return {
            "outcome": "repair_contradicted",
            "answer_verification": "unverified",
            "withheld": True,
            "synthetic_error": {
                "code": "grounding_nonfinite_answer",
                "message": (
                    "answer_text contains a non-finite value (nan/inf) or an unfilled "
                    "template placeholder: the computed quantity is undefined or was "
                    "never formatted in. Fix the computation — align each series "
                    "(resample to a shared grid, interpolate) BEFORE combining, and "
                    "guard empty/all-NaN results — then re-emit a finite answer with the "
                    "value formatted in; if the data genuinely cannot support an answer, "
                    "omit answer_text entirely."
                ),
                "details": {"answer_text": answer_text[:120]},
            },
            "diagnostics": {
                "degenerate_answer": True,
                "guarantee": TWO_TIER_GUARANTEE,
            },
        }

    # ---- Sentence tripwire ------------------------------------------------
    # answer_text begins with yes/no but no claim carries a verdict.
    has_verdict_claim = any(isinstance(c, dict) and "verdict" in c for c in claims)
    if (
        isinstance(answer_text, str)
        and re.match(r"^\s*(yes|no)\b", answer_text, re.IGNORECASE)
        and not has_verdict_claim
    ):
        return {
            "outcome": "repair_soft",
            "answer_verification": "unverified",
            "withheld": False,
            "synthetic_error": {
                "code": "grounding_verdict_unbacked",
                "message": (
                    "answer_text begins with a yes/no verdict but no claim carries a "
                    "'verdict' field — add a claims entry with metric/inputs/value/verdict/rule"
                ),
                "details": {"answer_text_prefix": answer_text[:60]},
            },
            "diagnostics": {
                "tripwire": True,
                "guarantee": TWO_TIER_GUARANTEE,
            },
        }

    # ---- No claims: pass without verification -----------------------------
    if not claims:
        return {
            "outcome": "pass",
            "answer_verification": None,  # absent: card shows no caveat
            "withheld": False,
            "synthetic_error": None,
            "diagnostics": {"claims_count": 0, "guarantee": TWO_TIER_GUARANTEE},
        }

    # ---- Check each claim in order ----------------------------------------
    claim_results: list[dict] = []
    for claim in claims:
        result = _check_claim(claim, history_series, delivered_ids, answer_text)
        claim_results.append(result)
        if result["outcome"] == "repair_contradicted":
            # Fail fast on first contradicted claim.
            return {
                "outcome": "repair_contradicted",
                "answer_verification": "unverified",
                "withheld": True,
                "synthetic_error": {
                    "code": result["code"],
                    "message": result["message"],
                    "details": result.get("details", {}),
                },
                "diagnostics": {
                    "claim_results": claim_results,
                    "guarantee": TWO_TIER_GUARANTEE,
                },
            }

    # Any repair_soft?
    soft = next((r for r in claim_results if r["outcome"] == "repair_soft"), None)
    if soft is not None:
        return {
            "outcome": "repair_soft",
            "answer_verification": "unverified",
            "withheld": False,
            "synthetic_error": {
                "code": soft["code"],
                "message": soft["message"],
                "details": soft.get("details", {}),
            },
            "diagnostics": {
                "claim_results": claim_results,
                "guarantee": TWO_TIER_GUARANTEE,
            },
        }

    # All verified or unverified_caveat
    all_verified = all(r["outcome"] in ("verified",) for r in claim_results)
    outcome = "verified" if all_verified else "unverified_caveat"
    return {
        "outcome": outcome,
        "answer_verification": "verified" if all_verified else "unverified",
        "withheld": False,
        "synthetic_error": None,
        "diagnostics": {
            "claim_results": claim_results,
            "guarantee": TWO_TIER_GUARANTEE,
        },
    }
