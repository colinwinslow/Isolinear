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

def _compute_mean(inputs: list[str], window: dict | None, params: dict, hs: list[dict]) -> float | None:
    vals = _numeric_vals(_in_window(_find_series(inputs[0] if inputs else "", hs), window))
    return (sum(vals) / len(vals)) if vals else None


def _compute_delta(inputs: list[str], window: dict | None, params: dict, hs: list[dict]) -> float | None:
    vals = _numeric_vals(_in_window(_find_series(inputs[0] if inputs else "", hs), window))
    return (vals[-1] - vals[0]) if len(vals) >= 2 else None


def _compute_pearson_r(inputs: list[str], window: dict | None, params: dict, hs: list[dict]) -> float | None:
    if len(inputs) < 2:
        return None

    def ts_map(eid: str) -> dict[int, float]:
        pts = _in_window(_find_series(eid, hs), window)
        return {
            int(p["ts_epoch_ms"]): float(p["value"])
            for p in pts
            if isinstance(p.get("ts_epoch_ms"), (int, float))
            and isinstance(p.get("value"), (int, float))
            and math.isfinite(float(p["value"]))
        }

    map_a = ts_map(inputs[0])
    map_b = ts_map(inputs[1])
    common = sorted(set(map_a) & set(map_b))
    if len(common) < 3:
        return None
    xs = [map_a[t] for t in common]
    ys = [map_b[t] for t in common]
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


# metric → (recompute_fn, required_params)
_REGISTRY: dict[str, tuple] = {
    "mean": (_compute_mean, []),
    "delta": (_compute_delta, []),
    "pearson_r": (_compute_pearson_r, []),
    "rolling_mean": (_compute_rolling_mean, ["window_ms"]),
    "daily_max": (_compute_daily_max, []),
    "daily_min": (_compute_daily_min, []),
    "hours_above": (_compute_hours_above, ["threshold"]),
}


def _recompute(metric: str, inputs: list[str], window: dict | None, params: dict, hs: list[dict]) -> float | None:
    entry = _REGISTRY.get(metric)
    if entry is None:
        return None
    fn, _ = entry
    return fn(inputs, window, params, hs)


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
    if rule is not None:
        rule_err = _validate_rule_structure(rule)
        if rule_err:
            return _soft("grounding_claim_malformed", f"rule invalid: {rule_err}", {"rule_error": rule_err})

    # ---- step 2: recipe completeness --------------------------------------
    in_registry = metric in _REGISTRY
    if in_registry:
        required = _REGISTRY[metric][1]
        for rp in required:
            if rp not in params:
                return _soft(
                    "grounding_recipe_incomplete",
                    f"registry metric '{metric}' missing required param '{rp}'",
                    {"metric": metric, "missing_param": rp},
                )
        # anchored window → defer to tranche 2 (shape defined, re-detection deferred)
        is_anchored = isinstance(window, dict) and "anchor" in window
        if is_anchored:
            return _caveat("grounding_anchor_deferred", "anchor re-detection is tranche 2", {})
        # window outside delivered span → unverifiable caveat
        if window and not _window_within_span(window, history_series):
            return _caveat("grounding_window_outside_span", "window lies outside delivered data span", {"window": window})

    # ---- step 3: degeneracy -----------------------------------------------
    if value is not None:
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            return _contradicted(
                "grounding_nonfinite_value",
                f"non-finite value in claim: {value!r}",
                {"value": value},
            )

    # ---- step 4: reference recompute (registry metrics only) ---------------
    reference: float | None = None
    if in_registry and (window is None or not isinstance(window, dict) or "anchor" not in window):
        reference = _recompute(metric, inputs, window, params, history_series)
        if reference is not None and isinstance(value, (int, float)):
            if abs(float(value) - reference) > _TOLERANCE:
                return _contradicted(
                    "grounding_value_mismatch",
                    f"stated value {value} differs from reference {reference:.4f} "
                    f"by more than tolerance {_TOLERANCE}",
                    {"value": value, "reference": reference, "tolerance": _TOLERANCE},
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
