"""Open-queue (u): bounded re-plan on a recoverable planner-quality rejection.

A single unlucky planner sample that trips a recoverable validation gate (a
variance tail — e.g. a duplicate-source / incomplete ChartSpec) should not fall
straight through to the fallback when the next sample would validate. These tests
pin the bounded, deterministic re-plan loop in `_record_model_provider_plan`, and
— critically — that it never overrides a legitimate `clarification_needed`.

The default is 1 (promoted from the opt-in slice-1 landing); tests that pin a
specific cap set the option explicitly. See
docs/specs/planner-replan-on-validation-failure.md.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.isolinear.const import DOMAIN  # noqa: E402

from test_first_real_vertical_slice import (  # noqa: E402
    PNG_SIGNATURE,
    FakePlanner,
    InvalidPlannerResultPlanner,
    _snapshot_job,
    _start_job,
    configured_real_slice_hass,
)


def _incomplete_planner_response(planner: FakePlanner, request: dict[str, Any]) -> dict[str, Any]:
    """A schema-valid planner result whose ChartSpec fails the contract check.

    Mirrors ``InvalidPlannerResultPlanner`` — an incomplete chart_spec that trips
    ``validate_chart_spec_contract`` → ``invalid_model_provider_chart_spec`` (a
    recoverable, re-plannable rejection).
    """
    return {
        "accepted": True,
        "code": "model_provider_planner_result_received",
        "provider": planner.provider_metadata(),
        "planner_result": {
            "status": "chart_spec_ready",
            "chart_spec": {"chart_id": "flaky-first-sample", "chart_type": "time_series"},
            "clarification_question": None,
            "memory_proposals": [],
            "reasoning_summary": "Intentionally incomplete first sample.",
            "warnings": [],
        },
        "provider_response": {"model": "llama3.1", "done": True},
    }


class FlakyThenValidPlanner(FakePlanner):
    """First `bad_samples` calls return a contract-failing ChartSpec; then valid."""

    def __init__(self, *, bad_samples: int = 1, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._bad_samples = bad_samples

    def plan_chart(self, request, *, result_schema=None):
        if len(self.calls) < self._bad_samples:
            self.calls.append(request)
            return _incomplete_planner_response(self, request)
        return super().plan_chart(request, result_schema=result_schema)


class ClarifyPlanner(FakePlanner):
    """Returns a schema-valid `clarification_needed` — a legitimate terminal."""

    def plan_chart(self, request, *, result_schema=None):
        self.calls.append(request)
        return {
            "accepted": True,
            "code": "model_provider_planner_result_received",
            "provider": self.provider_metadata(),
            "planner_result": {
                "status": "clarification_needed",
                "chart_spec": None,
                "clarification_question": {
                    "question_id": "q1",
                    "prompt": "Which sensor did you mean?",
                    "options": [],
                },
                "memory_proposals": [],
                "reasoning_summary": "Ambiguous request.",
                "warnings": [],
            },
            "provider_response": {"model": "llama3.1", "done": True},
        }


class PlannerReplanOnValidationFailureTests(unittest.TestCase):
    # Scenario A — a rejected sample is recovered by one re-plan.
    def test_recoverable_rejection_is_recovered_by_one_replan(self):
        planner = FlakyThenValidPlanner(bad_samples=1)
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(planner=planner, artifact_dir=artifact_dir)
            entry.options["max_planner_replan_attempts"] = 1

            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "complete", snapshot)
            image_url = snapshot["snapshot"]["chart"]["image_url"]
            artifact_path = artifact_dir / image_url.rsplit("/", 1)[-1]
            self.assertEqual(artifact_path.read_bytes()[:8], PNG_SIGNATURE)
            # One bad sample + one recovered sample = two planner calls.
            self.assertEqual(len(planner.calls), 2)

    # Scenario B — exhaustion returns the last failure unchanged.
    def test_exhaustion_returns_last_failure_unchanged(self):
        planner = InvalidPlannerResultPlanner()
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(planner=planner, artifact_dir=artifact_dir)
            entry.options["max_planner_replan_attempts"] = 1

            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "failed")
            self.assertEqual(
                snapshot["snapshot"]["failure"]["code"], "invalid_model_provider_chart_spec"
            )
            self.assertEqual(snapshot["snapshot"]["failure"]["stage"], "model_provider_planning")
            # First attempt + one exhausted re-plan = two planner calls; the
            # failure surface is identical to a single-attempt run.
            self.assertEqual(len(planner.calls), 2)
            self.assertFalse(snapshot["orchestration"]["chart_rendering_called"])
            self.assertEqual(list(artifact_dir.glob("*.png")), [])

    # Scenario C — a legitimate clarification is never re-planned.
    def test_clarification_is_never_replanned(self):
        planner = ClarifyPlanner()
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(planner=planner, artifact_dir=artifact_dir)
            entry.options["max_planner_replan_attempts"] = 3

            start = _start_job(hass, entry)
            _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            # Even with a generous cap, a clarification terminal is not re-sampled.
            self.assertEqual(len(planner.calls), 1)

    # Scenario D — zero attempts reproduces today's single-attempt behavior.
    def test_zero_attempts_reproduces_single_attempt_behavior(self):
        planner = FlakyThenValidPlanner(bad_samples=1)
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(planner=planner, artifact_dir=artifact_dir)
            entry.options["max_planner_replan_attempts"] = 0

            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            # No re-plan: the first (bad) sample fails terminally, exactly as before.
            self.assertEqual(snapshot["snapshot"]["status"], "failed")
            self.assertEqual(
                snapshot["snapshot"]["failure"]["code"], "invalid_model_provider_chart_spec"
            )
            self.assertEqual(len(planner.calls), 1)

    # Default (option absent) is ON with one extra sample: a bad first sample is
    # recovered by one re-plan without any configuration.
    def test_default_is_one_replan(self):
        planner = FlakyThenValidPlanner(bad_samples=1)
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(planner=planner, artifact_dir=artifact_dir)
            # No max_planner_replan_attempts set → reader default 1.
            entry.options.pop("max_planner_replan_attempts", None)

            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "complete", snapshot)
            self.assertEqual(len(planner.calls), 2)

    # Fresh-sample guarantee: the planner's structured pass runs at temperature 0
    # (near-greedy), so an unperturbed re-plan mostly reproduces the rejected
    # plan. Re-plan attempts must carry the nonzero override; the first attempt
    # must not (reproducible default).
    def test_replan_attempt_samples_at_nonzero_temperature(self):
        from custom_components.isolinear.job_orchestration import (
            _PLANNER_REPLAN_TEMPERATURE,
        )

        temperatures: list[Any] = []

        class TemperatureRecordingPlanner(FlakyThenValidPlanner):
            def plan_chart(self, request, *, result_schema=None, temperature=None):
                temperatures.append(temperature)
                return super().plan_chart(request, result_schema=result_schema)

        planner = TemperatureRecordingPlanner(bad_samples=1)
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(planner=planner, artifact_dir=artifact_dir)
            entry.options["max_planner_replan_attempts"] = 1

            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertEqual(snapshot["snapshot"]["status"], "complete", snapshot)
            # First attempt: default sampling (None). Re-plan: the fresh-sample override.
            self.assertEqual(temperatures, [None, _PLANNER_REPLAN_TEMPERATURE])

    # Scenario E — a deterministic non-trigger rejection is not re-planned:
    # re-sampling cannot change it, so it returns immediately with zero re-plans.
    #
    # DEVIATION from the BDD's "resolved routing is mixed" setup: since commit
    # 372a437 (multi-numeric overlays), every numeric+state set routes to
    # time_series_overlay, so the "mixed" family — and with it
    # `mixed_chart_composition_unsupported` — is unreachable through
    # `_resolve_render_family`. The defensive gate remains in `_plan_once`, so
    # this pins the loop's non-trigger discipline at that seam: given `_plan_once`
    # returns the deterministic rejection, the loop never retries it.
    def test_non_trigger_rejection_is_not_replanned(self):
        from custom_components.isolinear import job_orchestration

        hass, entry = configured_real_slice_hass(planner=FakePlanner())
        entry.options["max_planner_replan_attempts"] = 2

        plan_once_calls: list[dict[str, Any]] = []

        def deterministic_mixed_rejection(store, *, hass, entry_id, job, source_snapshot, replan_attempt=0):
            plan_once_calls.append({"job_id": job["job_id"]})
            return {
                "accepted": False,
                "code": "mixed_chart_composition_unsupported",
                "model_provider_called": False,
                "model_provider_plan": None,
                "chart_spec": None,
                "validation": {
                    "accepted": False,
                    "code": "mixed_chart_composition_unsupported",
                    "error": "deterministic routing rejection",
                    "kinds": ["binary_state", "numeric"],
                },
            }

        original_plan_once = job_orchestration._plan_once
        job_orchestration._plan_once = deterministic_mixed_rejection
        try:
            result = job_orchestration._record_model_provider_plan(
                {},
                hass=hass,
                entry_id=entry.entry_id,
                job={"job_id": "job-mixed"},
                source_snapshot={"entities": []},
            )
        finally:
            job_orchestration._plan_once = original_plan_once

        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "mixed_chart_composition_unsupported")
        self.assertEqual(result["planner_replan_attempts"], 0)
        # Deterministic rejection: exactly one planning attempt, no re-sample.
        self.assertEqual(len(plan_once_calls), 1)


if __name__ == "__main__":
    unittest.main()
