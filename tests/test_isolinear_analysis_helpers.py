"""Unit tests for the in-sandbox analysis helper library (ADR-0036, draft).

`isolinear_analysis.align` removes the align/combine plumbing step every live
cross-series failure died in (0.2.31 entity-id KeyError, the 0.2.32 "nan °F"
empty frame, e2e-18 repair exhaustion) from the floor model's transcription
burden. These tests pin the ADR's contract:

  - columns ARE the entity_id strings, in history_series order
  - shared DatetimeIndex grid; irregular/disjoint inputs align (the proven
    per-entity resample+interpolate idiom)
  - the fumbled one-liners work against the result (mean/delta/corr/deviation)
  - degenerate inputs raise a specific ValueError — never an empty or all-NaN
    frame (the nan-answer class, killed structurally)
  - parity with the integration-side answer_grounding registry within its own
    tolerance on dense data (independence preserved; drift testable)
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "worker"))

try:  # pandas-gated, like the matplotlib-gated sandbox tests (skip cleanly
    import pandas  # noqa: F401  # in the pandas-less integration test env;
except ImportError:  # run in-container / under the eval env where pandas exists)
    raise unittest.SkipTest("pandas not installed in this environment")

import isolinear_analysis  # noqa: E402
from custom_components.isolinear.answer_grounding import (  # noqa: E402
    _REGISTRY,
    _TOLERANCE,
)

BASE_MS = 1_782_000_000_000  # 2026-06-29T00:00:00Z


def _series(entity_id: str, values: list[float], *, start_ms: int = BASE_MS,
            step_ms: int = 60_000, kind: str = "numeric") -> dict:
    return {
        "entity_id": entity_id,
        "kind": kind,
        "unit": "°F",
        "label": entity_id.split(".")[-1],
        "points": [
            {"ts_epoch_ms": start_ms + i * step_ms, "value": v}
            for i, v in enumerate(values)
        ],
    }


def _irregular(entity_id: str, base: float, *, offset_ms: int, n: int = 48) -> dict:
    """~24h of irregular samples; two calls with different offsets share NO timestamps."""
    points = []
    for i in range(n):
        ts = BASE_MS + i * 30 * 60_000 + offset_ms + (i % 7) * 11_000
        points.append({"ts_epoch_ms": ts, "value": base + 2.0 * math.sin(i / n * 6.28)})
    return {"entity_id": entity_id, "kind": "numeric", "unit": "°F",
            "label": entity_id, "points": points}


class AlignShapeTests(unittest.TestCase):
    def test_columns_are_entity_ids_in_series_order(self):
        # Samples ON the 5-min grid → resample is identity → exact values.
        frame = isolinear_analysis.align([
            _series("sensor.kitchen", [70, 71, 72], step_ms=300_000),
            _series("sensor.basement", [60, 61, 62], step_ms=300_000),
        ])
        self.assertEqual(list(frame.columns), ["sensor.kitchen", "sensor.basement"])
        # The 0.2.31 failure mode is structurally impossible: indexing by
        # entity_id works because the columns ARE entity_ids.
        self.assertAlmostEqual(float(frame["sensor.kitchen"].iloc[0]), 70.0)

    def test_disjoint_timestamps_align_onto_shared_grid(self):
        a = _irregular("sensor.a", 71.5, offset_ms=0)
        b = _irregular("sensor.b", 69.0, offset_ms=137_000)
        shared_ts = {p["ts_epoch_ms"] for p in a["points"]} & {
            p["ts_epoch_ms"] for p in b["points"]}
        self.assertEqual(shared_ts, set())  # precondition: truly disjoint
        frame = isolinear_analysis.align([a, b])
        self.assertGreater(len(frame), 10)
        self.assertFalse(frame.isna().any().any())

    def test_state_series_are_ignored(self):
        frame = isolinear_analysis.align([
            _series("sensor.temp", [70, 71, 72]),
            {"entity_id": "binary_sensor.door", "kind": "binary_state",
             "points": [{"ts_epoch_ms": BASE_MS, "value": "on"}]},
        ])
        self.assertEqual(list(frame.columns), ["sensor.temp"])

    def test_duplicate_timestamps_collapse(self):
        s = _series("sensor.a", [70, 72])
        s["points"].append({"ts_epoch_ms": s["points"][0]["ts_epoch_ms"], "value": 74})
        frame = isolinear_analysis.align([s])
        self.assertFalse(frame.isna().any().any())


class AlignOneLinerTests(unittest.TestCase):
    """The exact one-liners the codegen prompt will prescribe."""

    def setUp(self):
        self.frame = isolinear_analysis.align([
            _irregular("sensor.kitchen", 74.0, offset_ms=0),
            _irregular("sensor.basement", 72.0, offset_ms=137_000),
        ])

    def test_cross_sensor_mean(self):
        mean_series = self.frame.mean(axis=1)
        self.assertGreater(len(mean_series), 10)
        # sits between the inputs
        self.assertTrue(
            (mean_series >= self.frame.min(axis=1)).all()
            and (mean_series <= self.frame.max(axis=1)).all()
        )

    def test_delta(self):
        delta = self.frame["sensor.kitchen"] - self.frame["sensor.basement"]
        self.assertAlmostEqual(float(delta.mean()), 2.0, delta=0.3)

    def test_correlation(self):
        r = self.frame.corr().iloc[0, 1]
        self.assertGreater(float(r), 0.9)  # same sine, phase-aligned

    def test_deviation_from_mean(self):
        dev = self.frame.sub(self.frame.mean(axis=1), axis=0)
        self.assertAlmostEqual(float(dev.sum(axis=1).abs().max()), 0.0, places=9)


class AlignDegenerateTests(unittest.TestCase):
    """Degenerate inputs raise specific errors — never an empty/all-NaN frame."""

    def test_no_numeric_series_raises(self):
        with self.assertRaisesRegex(ValueError, "no numeric series"):
            isolinear_analysis.align([
                {"entity_id": "binary_sensor.door", "kind": "binary_state", "points": []}
            ])

    def test_empty_points_raises_with_entity_named(self):
        with self.assertRaisesRegex(ValueError, "sensor.empty.*no.*finite points"):
            isolinear_analysis.align([_series("sensor.empty", [])])

    def test_non_finite_only_points_raises(self):
        s = {"entity_id": "sensor.nans", "kind": "numeric",
             "points": [{"ts_epoch_ms": BASE_MS, "value": float("nan")},
                        {"ts_epoch_ms": BASE_MS + 60_000, "value": float("inf")}]}
        with self.assertRaisesRegex(ValueError, "no.*finite points"):
            isolinear_analysis.align([s])

    def test_no_overlap_raises(self):
        day = 86_400_000
        with self.assertRaisesRegex(ValueError, "no overlapping data"):
            isolinear_analysis.align([
                _series("sensor.a", [70, 71], start_ms=BASE_MS),
                _series("sensor.b", [60, 61], start_ms=BASE_MS + 30 * day),
            ])

    def test_not_a_list_raises(self):
        with self.assertRaisesRegex(ValueError, "history_series"):
            isolinear_analysis.align({"points": []})  # type: ignore[arg-type]


class RegistryParityTests(unittest.TestCase):
    """Aligned-frame results agree with the integration-side answer_grounding
    registry (separate implementation — drift is testable, not shared code)
    within the grounding check's own tolerance. Registry semantics (verified
    against the implementations): `mean` = mean of inputs[0] only; `delta` =
    last-minus-first of inputs[0] over time. Samples sit ON the 5-min grid so
    resampling is identity and parity is exact."""

    def setUp(self):
        self.hs = [
            _series("sensor.a", [70 + 0.1 * i for i in range(60)], step_ms=300_000),
            _series("sensor.b", [65 + 0.05 * i for i in range(60)], step_ms=300_000),
        ]
        self.frame = isolinear_analysis.align(self.hs)

    def test_mean_parity_single_entity(self):
        registry_mean = _REGISTRY["mean"][0](["sensor.a"], None, {}, self.hs)
        helper_mean = float(self.frame["sensor.a"].mean())
        self.assertLessEqual(abs(helper_mean - registry_mean), _TOLERANCE)

    def test_delta_parity_change_over_time(self):
        registry_delta = _REGISTRY["delta"][0](["sensor.a"], None, {}, self.hs)
        helper_delta = float(
            self.frame["sensor.a"].iloc[-1] - self.frame["sensor.a"].iloc[0]
        )
        self.assertLessEqual(abs(helper_delta - registry_delta), _TOLERANCE)

    def test_pearson_parity_cross_entity(self):
        registry_r = _REGISTRY["pearson_r"][0](["sensor.a", "sensor.b"], None, {}, self.hs)
        helper_r = float(self.frame.corr().iloc[0, 1])
        self.assertLessEqual(abs(helper_r - registry_r), _TOLERANCE)


class VersionSurfaceTests(unittest.TestCase):
    def test_version_and_all(self):
        self.assertTrue(isolinear_analysis.__version__)
        self.assertIn("align", isolinear_analysis.__all__)


if __name__ == "__main__":
    unittest.main()
