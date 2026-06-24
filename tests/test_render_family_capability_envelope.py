"""Tests for ADR-0023: model-proposed render family within a deterministic capability envelope.

Covers:
  - _resolve_render_envelope shape→families mapping (all shapes)
  - validate_model_provider_chart_family accept/reject
  - load_planner_result_schema multi-family envelope (chart_type enum, source types)
  - _render_histogram_png happy path, sparse (fail-soft), no-data (fail-closed)
  - _render_aggregate_bar_png happy path, sparse (fail-soft), no-data (fail-closed)
  - Renderer unsupported checks for histogram and aggregate_bar
  - Regression: single-member envelopes behave identically to ADR-0022
"""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from custom_components.isolinear.job_orchestration import (  # noqa: E402
    _resolve_render_envelope,
    _resolve_render_family,
    validate_model_provider_chart_family,
)
from custom_components.isolinear.model_provider import (  # noqa: E402
    PLANNER_RENDER_FAMILIES,
    load_planner_result_schema,
)
from custom_components.isolinear.in_process_renderer import (  # noqa: E402
    render_in_process_chart,
    _unsupported_histogram_request,
    _unsupported_aggregate_bar_request,
)

RENDER_MODE_SAFE = "safe"
NOW = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)

CATALOG = [
    {"entity_id": "sensor.upstairs_temp", "domain": "sensor", "state_class": "measurement"},
    {"entity_id": "sensor.basement_temp", "domain": "sensor", "state_class": "measurement"},
    {"entity_id": "binary_sensor.kitchen_door", "domain": "binary_sensor"},
    {"entity_id": "sensor.washer_status", "domain": "sensor"},
]


def _numeric_history(entity_id: str, n_points: int = 48) -> dict:
    """Build a numeric HistorySeries with n_points spread over 24 h."""
    start = NOW - timedelta(hours=24)
    interval = timedelta(hours=24) / max(n_points, 1)
    points = [
        {
            "ts": (start + interval * i).isoformat(timespec="seconds"),
            "value": 20.0 + i * 0.1,
            "quality": "ok",
        }
        for i in range(n_points)
    ]
    return {
        "series_id": entity_id.replace(".", "_"),
        "entity_id": entity_id,
        "label": entity_id,
        "kind": "numeric",
        "unit": "°C",
        "points": points,
        "source": "recorder_states",
        "resolution": "raw",
        "source_entity_ids": [entity_id],
        "warnings": [],
    }


def _sparse_numeric_history(entity_id: str) -> dict:
    """Numeric history with only 3 points — deliberately sparse."""
    return _numeric_history(entity_id, n_points=3)


def _empty_numeric_history(entity_id: str) -> dict:
    """Numeric history with no usable points."""
    return {**_numeric_history(entity_id, n_points=0), "points": []}


def _base_render_request(chart_type: str, entity_id: str, history: dict, **extra) -> dict:
    chart_spec: dict = {
        "chart_id": f"test-{chart_type}",
        "chart_type": chart_type,
        "title": f"Test {chart_type}",
        "time_range": {
            "type": "absolute",
            "start": (NOW - timedelta(hours=24)).isoformat(timespec="seconds"),
            "end": NOW.isoformat(timespec="seconds"),
        },
        **extra,
    }
    return {
        "request_id": f"test-{chart_type}-request",
        "render_mode": RENDER_MODE_SAFE,
        "output": {"format": "png"},
        "chart_spec": chart_spec,
        "history_series": [history],
        "approved_entity_ids": [entity_id],
        "source_snapshot_id": "snap-001",
    }


class TestResolveRenderEnvelope(unittest.TestCase):
    """_resolve_render_envelope returns the right families for each data shape."""

    def test_single_numeric_gets_three_family_envelope(self):
        routing = _resolve_render_envelope(CATALOG, ["sensor.upstairs_temp"])
        self.assertEqual(routing["families"], ["time_series", "histogram", "aggregate_bar"])
        self.assertEqual(routing["default_family"], "time_series")
        self.assertEqual(routing["shape"], "single_numeric")
        # Legacy key still present for backward compat
        self.assertEqual(routing["family"], "time_series")

    def test_multi_numeric_gets_time_series_only(self):
        routing = _resolve_render_envelope(CATALOG, ["sensor.upstairs_temp", "sensor.basement_temp"])
        self.assertEqual(routing["families"], ["time_series"])
        self.assertEqual(routing["default_family"], "time_series")
        self.assertEqual(routing["shape"], "multi_numeric")

    def test_binary_gets_timeline_only(self):
        routing = _resolve_render_envelope(CATALOG, ["binary_sensor.kitchen_door"])
        self.assertEqual(routing["families"], ["timeline"])
        self.assertEqual(routing["default_family"], "timeline")
        self.assertEqual(routing["shape"], "all_categorical")

    def test_categorical_gets_timeline_only(self):
        routing = _resolve_render_envelope(CATALOG, ["sensor.washer_status"])
        self.assertEqual(routing["families"], ["timeline"])
        self.assertEqual(routing["shape"], "all_categorical")

    def test_numeric_with_binary_overlay_gets_overlay_only(self):
        routing = _resolve_render_envelope(
            CATALOG, ["sensor.upstairs_temp", "binary_sensor.kitchen_door"]
        )
        self.assertEqual(routing["families"], ["time_series_overlay"])
        self.assertEqual(routing["shape"], "numeric_with_overlay")

    def test_multi_numeric_with_overlay_gets_overlay_family(self):
        # Two numeric + binary now composes into overlay (both numerics plot)
        routing = _resolve_render_envelope(
            CATALOG, ["sensor.upstairs_temp", "sensor.basement_temp", "binary_sensor.kitchen_door"]
        )
        self.assertEqual(routing["families"], ["time_series_overlay"])
        self.assertEqual(routing["shape"], "numeric_with_overlay")
        self.assertEqual(routing["family"], "time_series_overlay")

    def test_envelope_is_superset_of_resolve_render_family(self):
        """_resolve_render_envelope must not change the ADR-0022 routing keys."""
        ids = ["sensor.upstairs_temp"]
        old_routing = _resolve_render_family(CATALOG, ids)
        new_routing = _resolve_render_envelope(CATALOG, ids)
        for key in old_routing:
            self.assertEqual(new_routing[key], old_routing[key])


class TestValidateModelProviderChartFamily(unittest.TestCase):
    """validate_model_provider_chart_family accepts in-envelope and rejects out-of-envelope."""

    def _envelope(self, families):
        return {"families": families}

    def test_accepts_time_series_in_multi_family_envelope(self):
        result = validate_model_provider_chart_family(
            {"chart_type": "time_series"}, self._envelope(["time_series", "histogram", "aggregate_bar"])
        )
        self.assertTrue(result["accepted"])

    def test_accepts_histogram_in_envelope(self):
        result = validate_model_provider_chart_family(
            {"chart_type": "histogram"}, self._envelope(["time_series", "histogram", "aggregate_bar"])
        )
        self.assertTrue(result["accepted"])

    def test_accepts_bar_in_envelope(self):
        result = validate_model_provider_chart_family(
            {"chart_type": "bar"}, self._envelope(["time_series", "histogram", "aggregate_bar"])
        )
        self.assertTrue(result["accepted"])

    def test_rejects_histogram_for_binary_single_member_envelope(self):
        result = validate_model_provider_chart_family(
            {"chart_type": "histogram"}, self._envelope(["timeline"])
        )
        # Single-member envelope: gate is a no-op (existing gates handle it)
        self.assertTrue(result["accepted"])

    def test_rejects_out_of_envelope_family(self):
        result = validate_model_provider_chart_family(
            {"chart_type": "histogram"},
            self._envelope(["time_series"]),
        )
        # Single-member: no-op
        self.assertTrue(result["accepted"])

    def test_rejects_unknown_chart_type_in_multi_family(self):
        result = validate_model_provider_chart_family(
            {"chart_type": "scatter"},
            self._envelope(["time_series", "histogram", "aggregate_bar"]),
        )
        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "model_provider_chart_family_out_of_envelope")
        self.assertEqual(result["chosen_family"], "scatter")
        self.assertIn("time_series", result["allowed_families"])
        self.assertIn("histogram", result["allowed_families"])
        self.assertIn("bar", result["allowed_families"])

    def test_accepts_when_families_empty(self):
        # Mixed shape: no families → gate passes (mixed already blocked upstream)
        result = validate_model_provider_chart_family({"chart_type": "time_series"}, {"families": []})
        self.assertTrue(result["accepted"])


class TestLoadPlannerResultSchemaEnvelope(unittest.TestCase):
    """load_planner_result_schema with envelope param builds the right chart_type enum."""

    def _chart_type_enum(self, schema):
        return schema["properties"]["chart_spec"]["properties"]["chart_type"]["enum"]

    def _render_as_enum(self, schema):
        return schema["properties"]["chart_spec"]["properties"]["series"]["items"]["properties"]["render_as"]["enum"]

    def _source_type_enum(self, schema):
        return schema["properties"]["chart_spec"]["properties"]["series"]["items"]["properties"]["source"]["properties"]["type"]["enum"]

    def test_single_family_envelope_keeps_single_chart_type(self):
        schema = load_planner_result_schema("time_series", envelope=["time_series"])
        self.assertEqual(self._chart_type_enum(schema), ["time_series"])

    def test_multi_family_envelope_widens_chart_type_enum(self):
        schema = load_planner_result_schema(
            "time_series", envelope=["time_series", "histogram", "aggregate_bar"]
        )
        chart_types = self._chart_type_enum(schema)
        self.assertIn("time_series", chart_types)
        self.assertIn("histogram", chart_types)
        self.assertIn("bar", chart_types)
        self.assertEqual(len(chart_types), 3)

    def test_multi_family_envelope_includes_aggregate_source_type(self):
        schema = load_planner_result_schema(
            "time_series", envelope=["time_series", "histogram", "aggregate_bar"]
        )
        source_types = self._source_type_enum(schema)
        self.assertIn("entity", source_types)
        self.assertIn("aggregate", source_types)

    def test_no_aggregate_in_source_type_for_time_series_only_envelope(self):
        schema = load_planner_result_schema("time_series", envelope=["time_series"])
        source_types = self._source_type_enum(schema)
        self.assertIn("entity", source_types)
        self.assertNotIn("aggregate", source_types)

    def test_entity_ids_still_pinned_in_multi_family_schema(self):
        schema = load_planner_result_schema(
            "time_series",
            envelope=["time_series", "histogram", "aggregate_bar"],
            entity_ids=["sensor.upstairs_temp"],
        )
        source_props = schema["properties"]["chart_spec"]["properties"]["series"]["items"]["properties"]["source"]["properties"]
        self.assertEqual(source_props["entity_id"], {"enum": ["sensor.upstairs_temp"]})

    def test_no_envelope_behaves_like_single_family(self):
        schema_old = load_planner_result_schema("time_series")
        schema_new = load_planner_result_schema("time_series", envelope=None)
        self.assertEqual(self._chart_type_enum(schema_old), self._chart_type_enum(schema_new))

    def test_timeline_single_member_unchanged(self):
        schema = load_planner_result_schema("timeline", envelope=["timeline"])
        self.assertEqual(self._chart_type_enum(schema), ["timeline"])
        self.assertEqual(self._render_as_enum(schema), ["step"])


class TestHistogramRenderer(unittest.TestCase):
    """render_in_process_chart for histogram family."""

    def _histogram_request(self, history, bin_count=8):
        entity_id = history["entity_id"]
        req = _base_render_request("histogram", entity_id, history)
        req["chart_spec"]["series"] = [
            {
                "series_id": "temp-dist",
                "label": "Temperature Distribution",
                "source": {"type": "entity", "entity_id": entity_id, "attribute": None},
                "role": "primary",
                "render_as": "histogram",
                "transform": {"operation": "none", "window": None},
                "unit": "°C",
            }
        ]
        req["chart_spec"]["x_axis"] = {"type": "value", "bin_count": bin_count}
        return req

    def test_happy_path_renders_png(self):
        history = _numeric_history("sensor.upstairs_temp", n_points=48)
        result = render_in_process_chart(self._histogram_request(history))
        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["code"], "in_process_render_succeeded")
        png = result["png_bytes"]
        self.assertTrue(png[:8] == b"\x89PNG\r\n\x1a\n", "Expected PNG signature")
        self.assertIn("temp-dist", result["render_result"]["render_metadata"]["series_plotted"])

    def test_sparse_fails_soft_not_error(self):
        # ADR-0023 D6: 3 points → render a thin histogram, not unsupported_chart_spec
        history = _sparse_numeric_history("sensor.upstairs_temp")
        result = render_in_process_chart(self._histogram_request(history))
        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["code"], "in_process_render_succeeded")

    def test_zero_points_fails_closed(self):
        history = _empty_numeric_history("sensor.upstairs_temp")
        result = render_in_process_chart(self._histogram_request(history))
        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "in_process_renderer_failed")

    def test_single_bin_renders(self):
        history = _numeric_history("sensor.upstairs_temp", n_points=10)
        result = render_in_process_chart(self._histogram_request(history, bin_count=1))
        self.assertTrue(result["accepted"], result)

    def test_wrong_chart_type_is_unsupported(self):
        history = _numeric_history("sensor.upstairs_temp")
        req = self._histogram_request(history)
        req["chart_spec"]["chart_type"] = "time_series"
        issues = _unsupported_histogram_request(req)
        codes = [i["reason"] for i in issues]
        self.assertIn("histogram_required", codes)

    def test_non_entity_source_is_unsupported(self):
        history = _numeric_history("sensor.upstairs_temp")
        req = self._histogram_request(history)
        req["chart_spec"]["series"][0]["source"]["type"] = "aggregate"
        issues = _unsupported_histogram_request(req)
        codes = [i["reason"] for i in issues]
        self.assertIn("entity_source_required", codes)


class TestAggregateBarRenderer(unittest.TestCase):
    """render_in_process_chart for aggregate_bar (bar) family."""

    def _bar_request(self, history, operation="mean", group_by="day"):
        entity_id = history["entity_id"]
        req = _base_render_request("bar", entity_id, history)
        req["chart_spec"]["series"] = [
            {
                "series_id": "temp-avg",
                "label": "Average Temperature",
                "source": {
                    "type": "aggregate",
                    "entity_id": entity_id,
                    "operation": operation,
                },
                "role": "primary",
                "render_as": "bar",
                "transform": {"operation": "none", "window": None},
                "unit": "°C",
            }
        ]
        req["chart_spec"]["x_axis"] = {"type": "category", "group_by": group_by}
        return req

    def _multi_day_history(self, n_days=5):
        start = NOW - timedelta(days=n_days)
        points = []
        for d in range(n_days):
            for h in range(6):  # 6 readings per day
                ts = start + timedelta(days=d, hours=h * 4)
                points.append({
                    "ts": ts.isoformat(timespec="seconds"),
                    "value": 20.0 + d + h * 0.5,
                    "quality": "ok",
                })
        return {
            "series_id": "upstairs_temp",
            "entity_id": "sensor.upstairs_temp",
            "label": "Upstairs Temp",
            "kind": "numeric",
            "unit": "°C",
            "points": points,
            "source": "recorder_states",
            "resolution": "raw",
            "source_entity_ids": ["sensor.upstairs_temp"],
            "warnings": [],
        }

    def test_happy_path_renders_png(self):
        history = self._multi_day_history(n_days=5)
        result = render_in_process_chart(self._bar_request(history))
        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["code"], "in_process_render_succeeded")
        png = result["png_bytes"]
        self.assertTrue(png[:8] == b"\x89PNG\r\n\x1a\n", "Expected PNG signature")
        self.assertIn("temp-avg", result["render_result"]["render_metadata"]["series_plotted"])

    def test_group_by_hour(self):
        history = _numeric_history("sensor.upstairs_temp", n_points=24)
        result = render_in_process_chart(self._bar_request(history, group_by="hour"))
        self.assertTrue(result["accepted"], result)

    def test_all_operations_render(self):
        for operation in ("mean", "min", "max", "sum", "count"):
            with self.subTest(operation=operation):
                history = self._multi_day_history(n_days=3)
                result = render_in_process_chart(self._bar_request(history, operation=operation))
                self.assertTrue(result["accepted"], f"{operation}: {result}")

    def test_sparse_single_day_fails_soft(self):
        # ADR-0023 D6: one bucket → render a single bar, not an error
        history = _sparse_numeric_history("sensor.upstairs_temp")
        result = render_in_process_chart(self._bar_request(history))
        self.assertTrue(result["accepted"], result)

    def test_zero_points_fails_closed(self):
        history = _empty_numeric_history("sensor.upstairs_temp")
        result = render_in_process_chart(self._bar_request(history))
        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "in_process_renderer_failed")

    def test_wrong_chart_type_is_unsupported(self):
        history = self._multi_day_history()
        req = self._bar_request(history)
        req["chart_spec"]["chart_type"] = "histogram"
        issues = _unsupported_aggregate_bar_request(req)
        codes = [i["reason"] for i in issues]
        self.assertIn("bar_required", codes)

    def test_entity_source_is_unsupported(self):
        history = self._multi_day_history()
        req = self._bar_request(history)
        req["chart_spec"]["series"][0]["source"]["type"] = "entity"
        issues = _unsupported_aggregate_bar_request(req)
        codes = [i["reason"] for i in issues]
        self.assertIn("aggregate_source_required", codes)

    def test_invalid_operation_is_unsupported(self):
        history = self._multi_day_history()
        req = self._bar_request(history)
        req["chart_spec"]["series"][0]["source"]["operation"] = "median"
        issues = _unsupported_aggregate_bar_request(req)
        codes = [i["reason"] for i in issues]
        self.assertIn("valid_operation_required", codes)


class TestSingleMemberEnvelopeRegression(unittest.TestCase):
    """Single-member envelopes are byte-equivalent to ADR-0022 behavior."""

    def test_binary_timeline_schema_unchanged(self):
        schema_legacy = load_planner_result_schema("timeline")
        schema_envelope = load_planner_result_schema("timeline", envelope=["timeline"])
        ct_legacy = schema_legacy["properties"]["chart_spec"]["properties"]["chart_type"]["enum"]
        ct_envelope = schema_envelope["properties"]["chart_spec"]["properties"]["chart_type"]["enum"]
        self.assertEqual(ct_legacy, ct_envelope)

    def test_overlay_family_envelope_behaves_as_time_series(self):
        schema = load_planner_result_schema("time_series", envelope=["time_series_overlay"])
        # time_series_overlay is not in PLANNER_RENDER_FAMILIES → falls back to time_series
        ct = schema["properties"]["chart_spec"]["properties"]["chart_type"]["enum"]
        self.assertEqual(ct, ["time_series"])

    def test_gate_is_noop_for_single_member(self):
        envelope = {"families": ["timeline"]}
        result = validate_model_provider_chart_family({"chart_type": "histogram"}, envelope)
        # single-member: gate is a no-op (existing structural checks handle it)
        self.assertTrue(result["accepted"])

    def test_gate_rejects_out_of_multi_member_envelope(self):
        envelope = {"families": ["time_series", "histogram", "aggregate_bar"]}
        result = validate_model_provider_chart_family({"chart_type": "scatter"}, envelope)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "model_provider_chart_family_out_of_envelope")


class TestPlannerRenderFamilies(unittest.TestCase):
    """PLANNER_RENDER_FAMILIES includes the new ADR-0023 entries."""

    def test_histogram_entry(self):
        self.assertIn("histogram", PLANNER_RENDER_FAMILIES)
        self.assertEqual(PLANNER_RENDER_FAMILIES["histogram"]["chart_type"], "histogram")
        self.assertEqual(PLANNER_RENDER_FAMILIES["histogram"]["render_as"], "histogram")

    def test_aggregate_bar_entry(self):
        self.assertIn("aggregate_bar", PLANNER_RENDER_FAMILIES)
        self.assertEqual(PLANNER_RENDER_FAMILIES["aggregate_bar"]["chart_type"], "bar")
        self.assertEqual(PLANNER_RENDER_FAMILIES["aggregate_bar"]["render_as"], "bar")

    def test_existing_families_unchanged(self):
        self.assertEqual(PLANNER_RENDER_FAMILIES["time_series"]["chart_type"], "time_series")
        self.assertEqual(PLANNER_RENDER_FAMILIES["timeline"]["chart_type"], "timeline")


if __name__ == "__main__":
    unittest.main()
