"""Unit tests for the answer-grounding check (ADR-0031 D8a).

Scenarios (per spec docs/specs/answer-grounding-check.md):
  A  — Seeded false-Yes: verdict contradicts rule at reference → repair_contradicted
  B  — Grounded verdict passes end-to-end → verified
  C  — Parametric hours_above with window + threshold → verified
  D  — Event anchors (tranche 2, §1a): fabricated event → anchor_unfound;
       mismatched resolved_at → anchor_mismatch; a correctly re-detected
       anchor → verified; an irreproducible-by-construction anchor → caveat
  E  — Unknown metric → unverified_caveat (never error)
  F  — Borderline non-flap: reference at band edge → pass (not a contradiction)
  G  — Sentence tripwire: answer starts yes/no, no claim carries verdict
  H  — No claims, no tripwire → pass, answer_verification absent
  J  — TWO_TIER_GUARANTEE text appears verbatim in diagnostics
  +  — Longest-match negation safety, repair_soft withheld=False vs repair_contradicted withheld=True
"""
import pytest

from custom_components.isolinear.answer_grounding import (
    TWO_TIER_GUARANTEE,
    _TOLERANCE,
    _apply_rule,
    _check_claim,
    _longest_matching_label,
    run_grounding_check,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _series(entity_id: str, values: list, start_ms: int = 0, step_ms: int = 3_600_000) -> dict:
    return {
        "entity_id": entity_id,
        "points": [
            {"ts_epoch_ms": start_ms + i * step_ms, "value": v}
            for i, v in enumerate(values)
        ],
    }


def _raw_state_series(
    entity_id: str,
    states: list,
    start_ms: int = 0,
    step_ms: int = 3_600_000,
    kind: str = "binary_state",
) -> dict:
    return {
        "entity_id": entity_id,
        "kind": kind,
        "points": [
            {"ts_epoch_ms": start_ms + i * step_ms, "raw_state": s}
            for i, s in enumerate(states)
        ],
    }


def _mean_rule() -> dict:
    """Rule: ≥10 → 'High', otherwise 'Low'."""
    return {"bands": [[10, "High"], [None, "Low"]], "basis": "value"}


def _corr_rule() -> dict:
    """Rule: ≥0.30 → 'Yes', otherwise 'Not really'."""
    return {"bands": [[0.30, "Yes"], [None, "Not really"]], "basis": "value"}


# ---------------------------------------------------------------------------
# Scenario A — Seeded false-Yes: contradicted, withheld
# ---------------------------------------------------------------------------

class TestScenarioA:
    """The anchor artifact: honest value (mean=3.0) satisfies step-4 tolerance
    but the rule at that reference yields 'Low', while the claim says 'High'.
    Result: grounding_verdict_contradicted → repair_contradicted, withheld=True.
    """

    SERIES = [_series("sensor.temp", [1.0, 3.0, 5.0])]  # mean = 3.0

    CLAIM = {
        "metric": "mean",
        "inputs": ["sensor.temp"],
        "value": 3.0,         # honest value — passes step 4
        "verdict": "High",    # but rule at 3.0 says "Low" — caught at step 6
        "rule": _mean_rule(),
    }

    def test_repair_contradicted(self):
        result = run_grounding_check(
            {"answer_text": "High — above the threshold", "claims": [self.CLAIM]},
            self.SERIES,
        )
        assert result["outcome"] == "repair_contradicted"
        assert result["withheld"] is True
        assert result["answer_verification"] == "unverified"
        assert result["synthetic_error"]["code"] == "grounding_verdict_contradicted"

    def test_synthetic_error_is_feedable(self):
        """The synthetic error dict has at minimum 'code' and 'message'."""
        result = run_grounding_check(
            {"answer_text": "High — above the threshold", "claims": [self.CLAIM]},
            self.SERIES,
        )
        err = result["synthetic_error"]
        assert isinstance(err, dict)
        assert err.get("code")
        assert err.get("message")

    def test_guarantee_in_diagnostics(self):
        result = run_grounding_check(
            {"answer_text": "High", "claims": [self.CLAIM]},
            self.SERIES,
        )
        assert result["diagnostics"]["guarantee"] == TWO_TIER_GUARANTEE


# ---------------------------------------------------------------------------
# Scenario B — Grounded verdict passes end-to-end
# ---------------------------------------------------------------------------

class TestScenarioB:
    """mean=15.0, rule says ≥10 = 'High'; verdict 'High' is correct → verified."""

    SERIES = [_series("sensor.temp", [10.0, 15.0, 20.0])]  # mean = 15.0

    CLAIM = {
        "metric": "mean",
        "inputs": ["sensor.temp"],
        "value": 15.0,
        "verdict": "High",
        "rule": _mean_rule(),
    }

    def test_verified(self):
        result = run_grounding_check(
            {"answer_text": "High — well above the threshold", "claims": [self.CLAIM]},
            self.SERIES,
        )
        assert result["outcome"] == "verified"
        assert result["answer_verification"] == "verified"
        assert result["withheld"] is False
        assert result["synthetic_error"] is None

    def test_claim_result_verified(self):
        result = run_grounding_check(
            {"answer_text": "High", "claims": [self.CLAIM]},
            self.SERIES,
        )
        assert result["diagnostics"]["claim_results"][0]["outcome"] == "verified"


# ---------------------------------------------------------------------------
# Scenario C — Parametric hours_above with window + threshold
# ---------------------------------------------------------------------------

class TestScenarioC:
    """hours_above 21°C for exactly 2 hours, using a window within the delivered span.

    Series layout (step = 1 hour).  A 4th sentinel point at t=3h extends the
    delivered span so the window [0, 2h+1ms] passes _window_within_span.

      t=0h: 25°C → above 21
      t=1h: 25°C → above 21
      t=2h: 19°C → below 21  (excluded by window end exclusive boundary)
      t=3h: 19°C → sentinel, extends span

    _in_window with end=7_200_001 keeps t=0, t=1h, t=2h (ts < 7200001).
    Integration:
      0→1h: 25°C > 21  →  +1 hour
      1→2h: 25°C > 21  →  +1 hour
    Total = 2.0 hours.
    """

    STEP = 3_600_000  # 1 hour in ms

    SERIES = [
        _series("sensor.temp", [25.0, 25.0, 19.0, 19.0], start_ms=0, step_ms=STEP)
    ]

    CLAIM = {
        "metric": "hours_above",
        "inputs": ["sensor.temp"],
        "params": {"threshold": 21.0},
        "value": 2.0,
        "verdict": "Yes",
        "rule": {"bands": [[1.0, "Yes"], [None, "No"]], "basis": "value"},
        # window end = 7_200_001 ms (just after t=2h) — exclusive upper bound
        # captures points at t=0, t=1h, t=2h for the 2-segment integration.
        "window": {"start": 0, "end": 2 * STEP + 1},
    }

    def test_verified(self):
        result = run_grounding_check(
            {"answer_text": "Yes — temperature was above threshold for 2 hours", "claims": [self.CLAIM]},
            self.SERIES,
        )
        assert result["outcome"] == "verified"
        assert result["answer_verification"] == "verified"
        assert result["withheld"] is False

    def test_reference_matches(self):
        result = run_grounding_check(
            {"answer_text": "Yes", "claims": [self.CLAIM]},
            self.SERIES,
        )
        ref = result["diagnostics"]["claim_results"][0].get("details", {}).get("reference")
        assert ref is not None
        assert abs(ref - 2.0) < _TOLERANCE


# ---------------------------------------------------------------------------
# Scenario D — Event anchors (§1a): fabricated/mismatched/verified/irreproducible
# ---------------------------------------------------------------------------

class TestScenarioD:
    """The fabricated-anchor artifact: a narrated event with no matching raw-state
    transition must not ride through as an unverified caveat — it is positive
    evidence of a contradiction (§3a), same tier as a value mismatch.
    """

    DOOR_NO_EVENT = _raw_state_series("binary_sensor.door", ["off", "off", "off"])
    DOOR_ONE_EVENT = _raw_state_series("binary_sensor.door", ["off", "on", "off"])

    def _anchor(self, resolved_at: int, entity: str = "binary_sensor.door") -> dict:
        return {
            "entity": entity,
            "to": "on",
            "from": "off",
            "occurrence": 1,
            "search": {"start": 0, "end": 7_200_000},
            "resolved_at": resolved_at,
        }

    def test_fabricated_anchor_unfound(self):
        """No 'off'->'on' transition exists anywhere → grounding_anchor_unfound,
        contradicted, withheld — the fabricated-event proof requirement."""
        claim = {
            "metric": "mean",
            "inputs": ["binary_sensor.door"],
            "value": 1.0,
            "window": {"anchor": self._anchor(3_600_000), "direction": "after", "duration_ms": 1_000_000},
        }
        result = run_grounding_check(
            {"answer_text": "The door opened around then and stayed open a while.", "claims": [claim]},
            [self.DOOR_NO_EVENT],
        )
        assert result["outcome"] == "repair_contradicted"
        assert result["withheld"] is True
        assert result["answer_verification"] == "unverified"
        assert result["synthetic_error"]["code"] == "grounding_anchor_unfound"

    def test_anchor_mismatch(self):
        """A real transition exists, but not at the claimed resolved_at →
        grounding_anchor_mismatch (identity, not just existence, per §1a-4)."""
        claim = {
            "metric": "mean",
            "inputs": ["binary_sensor.door"],
            "value": 1.0,
            # real transition is at t=3_600_000; claim asserts a different instant
            "window": {"anchor": self._anchor(999), "direction": "after", "duration_ms": 1_000_000},
        }
        result = _check_claim(claim, [self.DOOR_ONE_EVENT], {"binary_sensor.door"}, None)
        assert result["outcome"] == "repair_contradicted"
        assert result["code"] == "grounding_anchor_mismatch"

    def test_verified_via_anchor(self):
        """A correctly re-detected anchor resolves an absolute window that the
        registry recompute independently confirms → verified, the strong
        value↔data guarantee extended to an event-scoped claim."""
        temp = _series("sensor.temp", [10.0, 20.0, 30.0])  # ts 0, 3.6M, 7.2M
        claim = {
            "metric": "mean",
            "inputs": ["sensor.temp"],
            "value": 20.0,
            # door transitions off->on at t=3.6M; window [3.6M, 7.2M) keeps
            # only the t=3.6M temp point (7.2M excluded, half-open) → mean 20.0
            "window": {"anchor": self._anchor(3_600_000), "direction": "after", "duration_ms": 3_600_000},
        }
        result = run_grounding_check(
            {"answer_text": "It was 20 degrees after the door opened.", "claims": [claim]},
            [self.DOOR_ONE_EVENT, temp],
        )
        assert result["outcome"] == "verified"
        assert result["answer_verification"] == "verified"

    def test_irreproducible_out_of_kind_entity_is_caveat(self):
        """Anchoring on a numeric (non-raw-state) entity is explicitly NOT
        reproducible (§1a criterion 2) → unverified caveat, never attempted."""
        claim = {
            "metric": "mean",
            "inputs": ["sensor.temp"],
            "value": 1.0,
            "window": {
                "anchor": self._anchor(3_600_000, entity="sensor.temp"),
                "direction": "after",
                "duration_ms": 1_000_000,
            },
        }
        result = _check_claim(claim, [_series("sensor.temp", [1.0, 2.0, 3.0])], {"sensor.temp"}, None)
        assert result["outcome"] == "unverified_caveat"
        assert result["code"] == "grounding_anchor_unreproducible"

    def test_irreproducible_missing_search_is_caveat(self):
        """An anchor missing search/occurrence is irreproducible by construction."""
        anchor = {"entity": "binary_sensor.door", "to": "on"}  # no occurrence/search/resolved_at
        claim = {
            "metric": "mean",
            "inputs": ["binary_sensor.door"],
            "value": 1.0,
            "window": {"anchor": anchor, "direction": "after", "duration_ms": 1_000_000},
        }
        result = _check_claim(claim, [self.DOOR_ONE_EVENT], {"binary_sensor.door"}, None)
        assert result["outcome"] == "unverified_caveat"
        assert result["code"] == "grounding_anchor_unreproducible"


# ---------------------------------------------------------------------------
# Scenario E — Unknown metric → unverified_caveat (never error)
# ---------------------------------------------------------------------------

class TestScenarioE:
    """A metric not in the registry is always unverified_caveat, never contradicted."""

    SERIES = [_series("sensor.a", [1.0, 2.0, 3.0])]

    CLAIM = {
        "metric": "fuzzy_regression",  # not in registry
        "inputs": ["sensor.a"],
        "value": 0.7,
    }

    def test_unverified_caveat(self):
        result = run_grounding_check(
            {"answer_text": "The trend shows a positive slope.", "claims": [self.CLAIM]},
            self.SERIES,
        )
        assert result["outcome"] == "unverified_caveat"
        assert result["answer_verification"] == "unverified"
        assert result["withheld"] is False
        assert result["synthetic_error"] is None

    def test_not_contradicted(self):
        result = run_grounding_check(
            {"answer_text": "Yes — the slope is steep.", "claims": [self.CLAIM]},
            self.SERIES,
        )
        assert result["outcome"] != "repair_contradicted"


# ---------------------------------------------------------------------------
# Scenario F — Borderline non-flap
# ---------------------------------------------------------------------------

class TestScenarioF:
    """Reference = 0.29, stated value = 0.31, threshold = 0.30.

    Step-4: |0.31 - 0.29| = 0.02 < 0.05 → passes.
    Step-6: rule at reference 0.29 → "Not really"; verdict = "Yes" → mismatch.
    Borderline guard: at 0.29 ± 0.05 → "Not really" vs "Yes" (straddle) → pass.
    Outcome: verified (in registry, reference computed), code: grounding_borderline.
    """

    # mean([0.19, 0.29, 0.39]) = 0.29
    SERIES = [_series("sensor.x", [0.19, 0.29, 0.39])]

    CLAIM = {
        "metric": "mean",
        "inputs": ["sensor.x"],
        "value": 0.31,       # slightly above reference 0.29; within tolerance
        "verdict": "Yes",
        "rule": _corr_rule(),
    }

    def test_borderline_pass_not_contradicted(self):
        result = run_grounding_check(
            {"answer_text": "Yes — just above the threshold", "claims": [self.CLAIM]},
            self.SERIES,
        )
        assert result["outcome"] in ("verified", "unverified_caveat")
        assert result["outcome"] != "repair_contradicted"
        claim_res = result["diagnostics"]["claim_results"][0]
        assert claim_res["code"] == "grounding_borderline"

    def test_borderline_outcome_is_verified(self):
        result = run_grounding_check(
            {"answer_text": "Yes", "claims": [self.CLAIM]},
            self.SERIES,
        )
        # mean is in registry and reference was computed → outcome = verified
        assert result["diagnostics"]["claim_results"][0]["outcome"] == "verified"


# ---------------------------------------------------------------------------
# Scenario G — Sentence tripwire
# ---------------------------------------------------------------------------

class TestScenarioG:
    """answer_text starts 'yes' but no claim has a 'verdict' key → repair_soft."""

    SERIES = [_series("sensor.a", [1.0, 2.0, 3.0])]

    def test_tripwire_fires(self):
        result = run_grounding_check(
            {
                "answer_text": "Yes — temperature was above average",
                "claims": [
                    {"metric": "mean", "inputs": ["sensor.a"], "value": 2.0}
                    # intentionally no 'verdict' key
                ],
            },
            self.SERIES,
        )
        assert result["outcome"] == "repair_soft"
        assert result["synthetic_error"]["code"] == "grounding_verdict_unbacked"
        assert result["withheld"] is False  # soft failure → caveat, not withhold

    def test_tripwire_no_claim(self):
        """Tripwire also fires when there are no claims at all."""
        result = run_grounding_check(
            {"answer_text": "No — not significant", "claims": []},
            self.SERIES,
        )
        assert result["outcome"] == "repair_soft"
        assert result["synthetic_error"]["code"] == "grounding_verdict_unbacked"

    def test_tripwire_case_insensitive(self):
        result = run_grounding_check(
            {"answer_text": "YES — very high", "claims": []},
            self.SERIES,
        )
        assert result["outcome"] == "repair_soft"

    def test_no_tripwire_when_verdict_claim_exists(self):
        """If at least one claim carries a verdict, the tripwire does not fire."""
        result = run_grounding_check(
            {
                "answer_text": "Yes — above average",
                "claims": [
                    {
                        "metric": "mean",
                        "inputs": ["sensor.a"],
                        "value": 2.0,
                        "verdict": "Yes",
                        "rule": {"bands": [[1.5, "Yes"], [None, "No"]], "basis": "value"},
                    }
                ],
            },
            self.SERIES,
        )
        # Tripwire suppressed; claim is verified
        assert result["outcome"] != "repair_soft" or result["synthetic_error"]["code"] != "grounding_verdict_unbacked"


# ---------------------------------------------------------------------------
# Scenario H — No claims, no tripwire → pass
# ---------------------------------------------------------------------------

class TestScenarioH:
    """No claims and answer_text does not start with yes/no → pass, no verification."""

    def test_pass_no_verification(self):
        result = run_grounding_check(
            {"answer_text": "The maximum temperature was 25°C."},
            [],
        )
        assert result["outcome"] == "pass"
        assert result["answer_verification"] is None
        assert result["withheld"] is False
        assert result["synthetic_error"] is None

    def test_pass_no_answer_text(self):
        result = run_grounding_check({}, [])
        assert result["outcome"] == "pass"
        assert result["answer_verification"] is None

    def test_pass_empty_claims(self):
        result = run_grounding_check({"answer_text": "Chart shows the last 24 hours.", "claims": []}, [])
        assert result["outcome"] == "pass"


# ---------------------------------------------------------------------------
# Scenario I2 — Degenerate answer tripwire (nan/inf never served)
# ---------------------------------------------------------------------------

class TestDegenerateAnswerTripwire:
    """A non-finite value stringified into answer_text ("nan"/"inf") must be
    routed through the repair loop and withheld on exhaustion — even with NO
    claim (a plain aggregate emits an answer_text but no verdict claim, so the
    per-claim degeneracy check never runs). Live-observed 0.2.32: an empty
    cross-sensor average served "…the average … was nan °F".
    """

    def test_nan_answer_no_claim_is_contradicted_and_withheld(self):
        result = run_grounding_check(
            {"answer_text": "The average temperature across the kitchen and basement was nan °F."},
            [_series("sensor.temp", [1.0, 2.0])],
        )
        assert result["outcome"] == "repair_contradicted"
        assert result["withheld"] is True
        assert result["answer_verification"] == "unverified"
        assert result["synthetic_error"]["code"] == "grounding_nonfinite_answer"

    def test_inf_answer_is_contradicted(self):
        result = run_grounding_check({"answer_text": "The rate was inf per hour."}, [])
        assert result["outcome"] == "repair_contradicted"
        assert result["synthetic_error"]["code"] == "grounding_nonfinite_answer"

    def test_unfilled_template_placeholder_is_contradicted(self):
        # An f-string that never evaluated ("{mean_avg:.2f}") leaked into the sentence.
        result = run_grounding_check(
            {"answer_text": "The average was {mean_avg:.2f} °F."}, []
        )
        assert result["outcome"] == "repair_contradicted"
        assert result["synthetic_error"]["code"] == "grounding_nonfinite_answer"

    def test_zero_result_is_not_degenerate(self):
        # A genuine zero (delta of 0.00) is a VALID answer, not degenerate.
        result = run_grounding_check(
            {"answer_text": "The difference between the two sensors was 0.00 °F."}, []
        )
        assert result["outcome"] == "pass"
        assert result["withheld"] is False

    def test_finite_answer_with_lookalike_word_still_passes(self):
        # "info"/"important" must not trip the whole-word nan/inf matcher.
        result = run_grounding_check(
            {"answer_text": "The info panel shows an important average of 74.44 °F."},
            [],
        )
        assert result["outcome"] == "pass"
        assert result["withheld"] is False


# ---------------------------------------------------------------------------
# Scenario J — TWO_TIER_GUARANTEE text verbatim in diagnostics
# ---------------------------------------------------------------------------

class TestScenarioJ:
    """The two-tier guarantee appears verbatim in every diagnostics payload."""

    def test_guarantee_in_pass(self):
        result = run_grounding_check({}, [])
        assert result["diagnostics"]["guarantee"] == TWO_TIER_GUARANTEE

    def test_guarantee_in_tripwire(self):
        result = run_grounding_check({"answer_text": "Yes — looks correlated"}, [])
        assert result["diagnostics"]["guarantee"] == TWO_TIER_GUARANTEE

    def test_guarantee_in_contradicted(self):
        series = [_series("sensor.temp", [1.0, 3.0, 5.0])]
        result = run_grounding_check(
            {
                "answer_text": "High",
                "claims": [{
                    "metric": "mean",
                    "inputs": ["sensor.temp"],
                    "value": 3.0,
                    "verdict": "High",
                    "rule": _mean_rule(),
                }],
            },
            series,
        )
        assert result["diagnostics"]["guarantee"] == TWO_TIER_GUARANTEE

    def test_guarantee_in_verified(self):
        series = [_series("sensor.temp", [10.0, 15.0, 20.0])]
        result = run_grounding_check(
            {
                "answer_text": "High",
                "claims": [{
                    "metric": "mean",
                    "inputs": ["sensor.temp"],
                    "value": 15.0,
                    "verdict": "High",
                    "rule": _mean_rule(),
                }],
            },
            series,
        )
        assert result["diagnostics"]["guarantee"] == TWO_TIER_GUARANTEE

    def test_guarantee_in_unverified_caveat(self):
        series = [_series("sensor.a", [1.0, 2.0])]
        result = run_grounding_check(
            {
                "answer_text": "The curve shows a positive slope.",
                "claims": [{"metric": "fuzzy_model", "inputs": ["sensor.a"], "value": 0.5}],
            },
            series,
        )
        assert result["diagnostics"]["guarantee"] == TWO_TIER_GUARANTEE


# ---------------------------------------------------------------------------
# Longest-match negation safety
# ---------------------------------------------------------------------------

class TestLongestMatchNegation:
    """'not correlated' must beat 'correlated' — negation-safe longest match."""

    def test_not_correlated_beats_correlated(self):
        labels = ["Yes", "Not really"]
        match = _longest_matching_label(labels, "Not really — correlation is low")
        assert match == "Not really"

    def test_longer_label_wins(self):
        labels = ["related", "strongly related"]
        match = _longest_matching_label(labels, "strongly related by the evidence")
        assert match == "strongly related"

    def test_no_match_returns_none(self):
        labels = ["High", "Low"]
        match = _longest_matching_label(labels, "The temperature was moderate.")
        assert match is None

    def test_word_boundary_respected(self):
        """'High' must not match 'Highest'."""
        labels = ["High", "Low"]
        match = _longest_matching_label(labels, "The Highest value is shown above.")
        assert match is None

    def test_case_insensitive(self):
        labels = ["Yes", "No"]
        assert _longest_matching_label(labels, "YES — confirmed") == "Yes"


# ---------------------------------------------------------------------------
# _apply_rule unit tests
# ---------------------------------------------------------------------------

class TestApplyRule:
    def test_descending_bands(self):
        rule = {"bands": [[0.8, "Strong"], [0.5, "Moderate"], [None, "Weak"]], "basis": "value"}
        assert _apply_rule(rule, 0.9) == "Strong"
        assert _apply_rule(rule, 0.65) == "Moderate"
        assert _apply_rule(rule, 0.3) == "Weak"

    def test_abs_basis(self):
        rule = {"bands": [[0.5, "Significant"], [None, "Not significant"]], "basis": "abs"}
        assert _apply_rule(rule, -0.7) == "Significant"
        assert _apply_rule(rule, 0.7) == "Significant"
        assert _apply_rule(rule, 0.3) == "Not significant"

    def test_empty_bands(self):
        rule = {"bands": [], "basis": "value"}
        assert _apply_rule(rule, 0.5) is None


# ---------------------------------------------------------------------------
# withheld flag semantics
# ---------------------------------------------------------------------------

class TestWithheldFlag:
    """repair_contradicted → withheld=True; repair_soft → withheld=False."""

    SERIES = [_series("sensor.t", [1.0, 2.0, 3.0])]

    def test_contradicted_withheld_true(self):
        result = run_grounding_check(
            {
                "answer_text": "High",
                "claims": [{
                    "metric": "mean",
                    "inputs": ["sensor.t"],
                    "value": 2.0,
                    "verdict": "High",
                    "rule": _mean_rule(),  # rule at 2.0 → "Low" → contradicted
                }],
            },
            self.SERIES,
        )
        assert result["outcome"] == "repair_contradicted"
        assert result["withheld"] is True

    def test_repair_soft_withheld_false(self):
        # Malformed claim → repair_soft
        result = run_grounding_check(
            {
                "answer_text": "High",
                "claims": [{"not_metric": "oops"}],  # missing metric
            },
            self.SERIES,
        )
        assert result["outcome"] == "repair_soft"
        assert result["withheld"] is False


# ---------------------------------------------------------------------------
# _check_claim: recipe completeness for registry metrics
# ---------------------------------------------------------------------------

class TestRecipeCompleteness:
    SERIES = [_series("sensor.t", [1.0, 2.0, 3.0])]

    def test_missing_required_param_is_soft(self):
        claim = {
            "metric": "hours_above",
            "inputs": ["sensor.t"],
            "value": 1.0,
            # missing required param 'threshold'
        }
        from custom_components.isolinear.answer_grounding import _check_claim
        result = _check_claim(claim, self.SERIES, {"sensor.t"}, None)
        assert result["outcome"] == "repair_soft"
        assert result["code"] == "grounding_recipe_incomplete"

    def test_malformed_anchor_shape_is_caveat(self):
        """A window carrying an 'anchor' key that isn't a proper §1a anchor dict
        (here: a bare string) is irreproducible by construction → caveat, not
        an attempted-and-failed check."""
        claim = {
            "metric": "mean",
            "inputs": ["sensor.t"],
            "value": 2.0,
            "window": {"anchor": "some_event", "start": 0, "end": 3_600_000},
        }
        from custom_components.isolinear.answer_grounding import _check_claim
        result = _check_claim(claim, self.SERIES, {"sensor.t"}, None)
        assert result["outcome"] == "unverified_caveat"
        assert result["code"] == "grounding_anchor_unreproducible"

    def test_nonfinite_value_contradicted(self):
        claim = {
            "metric": "mean",
            "inputs": ["sensor.t"],
            "value": float("inf"),
        }
        from custom_components.isolinear.answer_grounding import _check_claim
        result = _check_claim(claim, self.SERIES, {"sensor.t"}, None)
        assert result["outcome"] == "repair_contradicted"
        assert result["code"] == "grounding_nonfinite_value"

    def test_undelivered_input_is_malformed(self):
        """Spec §1: a claim citing an entity not in the delivered series is a
        structural failure (repair_soft), not a silent unverified caveat —
        closing the allowlist gap (invariant #1)."""
        claim = {
            "metric": "mean",
            "inputs": ["sensor.not_delivered"],
            "value": 2.0,
        }
        from custom_components.isolinear.answer_grounding import _check_claim
        result = _check_claim(claim, self.SERIES, {"sensor.t"}, None)
        assert result["outcome"] == "repair_soft"
        assert result["code"] == "grounding_claim_malformed"
        assert "sensor.not_delivered" in result["details"]["undelivered_inputs"]

    def test_mixed_delivered_and_undelivered_is_malformed(self):
        """Even one undelivered input among otherwise-valid inputs fails."""
        claim = {
            "metric": "pearson_r",
            "inputs": ["sensor.t", "sensor.ghost"],
            "value": 0.5,
        }
        from custom_components.isolinear.answer_grounding import _check_claim
        result = _check_claim(claim, self.SERIES, {"sensor.t"}, None)
        assert result["outcome"] == "repair_soft"
        assert result["code"] == "grounding_claim_malformed"

    def test_undelivered_input_end_to_end(self):
        """Through run_grounding_check: undelivered input → repair_soft, not caveat."""
        result = run_grounding_check(
            {
                "answer_text": "The average is 2.0.",
                "claims": [{"metric": "mean", "inputs": ["sensor.ghost"], "value": 2.0}],
            },
            self.SERIES,
        )
        assert result["outcome"] == "repair_soft"
        assert result["synthetic_error"]["code"] == "grounding_claim_malformed"
