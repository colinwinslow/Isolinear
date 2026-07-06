"""Open-queue (u): bounded re-plan on a recoverable planner-quality rejection.

A single unlucky planner sample that trips a recoverable validation gate (a
variance tail — e.g. a duplicate-source / incomplete ChartSpec) should not fall
straight through to the fallback when the next sample would validate. These tests
pin the bounded, deterministic re-plan loop in `_record_model_provider_plan`, and
— critically — that it never overrides a legitimate `clarification_needed`.

The loop is opt-in in slice 1 (`max_planner_replan_attempts` default 0), so each
test sets the option explicitly. See
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

    # Default (option absent) is opt-out: the loop is off, so a bad first sample
    # fails terminally with a single planner call — the additive-landing guarantee.
    def test_default_is_off_single_attempt(self):
        planner = FlakyThenValidPlanner(bad_samples=1)
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(planner=planner, artifact_dir=artifact_dir)
            # No max_planner_replan_attempts set → reader default 0.
            entry.options.pop("max_planner_replan_attempts", None)

            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertEqual(snapshot["snapshot"]["status"], "failed")
            self.assertEqual(len(planner.calls), 1)


if __name__ == "__main__":
    unittest.main()
