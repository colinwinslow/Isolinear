"""TDD for ADR-0031 tranche 1, packet 1 — the answer channel.

Spec: docs/specs/model-authored-analysis.md
BDD:  bdd/model-authored-analysis/model-authored-analysis-bdd.md

Packet 1 is the additive answer channel: the sandbox passes a grounded
``answer_text`` through render_metadata, the integration threads it onto the
served artifact and the complete snapshot's chart, and the codegen prompt
instructs the model to COMPUTE and format that answer (never assert it). The
PNG pipeline is untouched. Proven locally with the real packet-1 sandbox and the
in-process SandboxWorkerRenderer harness (no CT103 / remote host).

The grounding proof is deterministic: the sample history is 71.2 and 71.8, so a
render body that computes the mean and f-strings it must yield exactly
"The average reading is 71.50 degF." — the number is the computation.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "worker"))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from isolinear_worker.codegen_sandbox import invoke_codegen_sandbox  # noqa: E402
from isolinear_worker._schema_validation import validate_contract  # noqa: E402

from codegen_sandbox_fixtures import (  # noqa: E402
    SAFE_SAMPLE_PNG_HEX,
    grounded_answer_generated_python,
    safe_generated_python,
    sample_codegen_render_request,
)

from custom_components.isolinear.model_provider import (  # noqa: E402
    _CODEGEN_PROMPT_PREVIEW_POINTS,
    _CODEGEN_PROMPT_RULES,
    _codegen_request_view,
    _downsample_preview,
)
from custom_components.isolinear.answer_grounding import (  # noqa: E402
    run_grounding_check,
)
from custom_components.isolinear.history_retrieval import (  # noqa: E402
    backfill_catalog_units_from_state,
)
from custom_components.isolinear.job_orchestration import (  # noqa: E402
    _apply_catalog_units,
    _compute_derived_intervals,
    _compute_overlay_bands,
    _compute_timeline_bands,
    _history_series_with_epoch_ms,
    _timestamp_to_epoch_ms,
)

# Reuse the proven codegen-path harness (real sandbox + in-process worker).
from test_codegen_generation_path import (  # noqa: E402
    FakeCodegenClient,
    SandboxWorkerRenderer,
    _configured_codegen_hass,
    _orchestration_store,
    _snapshot_job,
    _start_job,
)

GROUNDED_ANSWER = "The average reading is 71.50 degF."
DOCS_SCHEMAS = REPO_ROOT / "docs" / "schemas"


class SandboxAnswerPassthroughTests(unittest.TestCase):
    """Scenario A/B — the sandbox passes the grounded answer through, or omits it."""

    def _run_dir(self):
        (REPO_ROOT / ".test-output").mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=REPO_ROOT / ".test-output")

    def test_grounded_answer_text_is_computed_and_passed_through(self):
        with self._run_dir() as run_directory:
            result = invoke_codegen_sandbox(
                sample_codegen_render_request(python_code=grounded_answer_generated_python()),
                work_root=Path(run_directory),
            )
        self.assertEqual(result["status"], "success", result.get("error"))
        # The number is the computation over 71.2 / 71.8, not a literal.
        self.assertEqual(result["render_metadata"]["answer_text"], GROUNDED_ANSWER)
        # Render-result stays schema-valid with the additive field present.
        validate_contract("render-result", result)

    def test_chart_only_render_carries_no_answer_text(self):
        with self._run_dir() as run_directory:
            result = invoke_codegen_sandbox(
                sample_codegen_render_request(python_code=safe_generated_python()),
                work_root=Path(run_directory),
            )
        self.assertEqual(result["status"], "success", result.get("error"))
        self.assertNotIn("answer_text", result["render_metadata"])
        validate_contract("render-result", result)

    def test_blank_answer_text_is_dropped(self):
        blank_answer_body = (
            "def render_chart(data, output_path):\n"
            f'    png_bytes = bytes.fromhex("{SAFE_SAMPLE_PNG_HEX}")\n'
            '    with open(output_path, "wb") as image_file:\n'
            "        image_file.write(png_bytes)\n"
            '    return {"title": "t", "series_plotted": [], "overlays_plotted": [],\n'
            '            "x_min": None, "x_max": None, "warnings": [],\n'
            '            "answer_text": "   "}\n'
        )
        with self._run_dir() as run_directory:
            result = invoke_codegen_sandbox(
                sample_codegen_render_request(python_code=blank_answer_body),
                work_root=Path(run_directory),
            )
        self.assertEqual(result["status"], "success", result.get("error"))
        # A whitespace-only answer is not an answer.
        self.assertNotIn("answer_text", result["render_metadata"])


class AnswerChannelEndToEndTests(unittest.TestCase):
    """Scenario A — the grounded answer threads to the complete snapshot chart."""

    def test_answer_text_reaches_the_complete_snapshot_and_artifact(self):
        worker = SandboxWorkerRenderer()
        codegen = FakeCodegenClient(generate_code=grounded_answer_generated_python())
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = _configured_codegen_hass(
                codegen_client=codegen, worker=worker, artifact_dir=artifact_dir
            )
            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertEqual(snapshot["snapshot"]["status"], "complete", snapshot)
            chart = snapshot["snapshot"]["chart"]
            # Codegen render path, and a grounded answer delivered to the card.
            # The number is computed over THIS job's real history (grounding proof:
            # it reflects the actual data, not the sandbox fixture's 71.50).
            self.assertEqual(chart.get("render_path"), "codegen")
            self.assertRegex(
                chart.get("answer_text", ""),
                r"^The average reading is \d+\.\d{2} degF\.$",
            )
            # The answer threads consistently onto the served artifact too.
            artifact = _orchestration_store(hass, entry)["latest_artifact"]
            self.assertEqual(artifact.get("answer_text"), chart.get("answer_text"))
            # A real PNG was still served — the answer is purely additive.
            artifact_path = artifact_dir / f"{artifact['artifact_id']}.png"
            self.assertEqual(artifact_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_chart_only_snapshot_has_no_answer_line(self):
        worker = SandboxWorkerRenderer()
        codegen = FakeCodegenClient(generate_code=safe_generated_python())
        with tempfile.TemporaryDirectory() as temp_dir:
            hass, entry = _configured_codegen_hass(
                codegen_client=codegen, worker=worker, artifact_dir=Path(temp_dir)
            )
            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertEqual(snapshot["snapshot"]["status"], "complete", snapshot)
            self.assertNotIn("answer_text", snapshot["snapshot"]["chart"])


class AnswerChannelSchemaTests(unittest.TestCase):
    """answer_text is additive and optional across all three schemas (both copies)."""

    def _schema(self, name: str) -> dict:
        return json.loads((DOCS_SCHEMAS / name).read_text())

    def test_answer_text_optional_on_all_three_schemas(self):
        render_meta = self._schema("render-result.schema.json")["properties"]["render_metadata"]
        self.assertIn("answer_text", render_meta["properties"])
        self.assertNotIn("answer_text", render_meta.get("required", []))

        artifact = self._schema("integration-artifact-metadata.schema.json")
        self.assertIn("answer_text", artifact["properties"])
        self.assertNotIn("answer_text", artifact.get("required", []))

        chart = self._schema("integration-job-snapshot.schema.json")["properties"]["chart"]
        self.assertIn("answer_text", chart["properties"])
        self.assertNotIn("answer_text", chart.get("required", []))

    def test_schema_copies_are_byte_identical(self):
        packaged = REPO_ROOT / "custom_components" / "isolinear" / "schemas"
        worker = REPO_ROOT / "worker" / "isolinear_worker" / "schemas"
        for name in (
            "render-result.schema.json",
            "integration-artifact-metadata.schema.json",
            "integration-job-snapshot.schema.json",
        ):
            canonical = (DOCS_SCHEMAS / name).read_bytes()
            self.assertEqual((packaged / name).read_bytes(), canonical, name)
            if (worker / name).exists():
                self.assertEqual((worker / name).read_bytes(), canonical, f"worker/{name}")


class TimestampNormalizationTests(unittest.TestCase):
    """Packet 2 (ADR-0031 D9) — epoch-ms at the codegen data boundary."""

    def test_parses_on_the_second_and_microsecond_iso(self):
        # HA writes the first state on-the-second, later states with microseconds.
        on_second = _timestamp_to_epoch_ms("2026-06-05T08:00:00Z")
        with_micros = _timestamp_to_epoch_ms("2026-06-05T08:00:00.123456+00:00")
        # Cross-check against an independently-constructed reference.
        ref = int(datetime(2026, 6, 5, 8, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
        self.assertEqual(on_second, ref)
        self.assertEqual(with_micros, ref + 123)

    def test_naive_iso_is_treated_as_utc(self):
        naive = _timestamp_to_epoch_ms("2026-06-05T08:00:00")
        ref = int(datetime(2026, 6, 5, 8, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
        self.assertEqual(naive, ref)

    def test_conversion_is_idempotent_and_fails_soft(self):
        self.assertEqual(_timestamp_to_epoch_ms(1_749_110_400_000), 1_749_110_400_000)
        self.assertIsNone(_timestamp_to_epoch_ms("not-a-timestamp"))
        self.assertIsNone(_timestamp_to_epoch_ms(None))

    def test_history_series_gains_integer_epoch_ms_keeping_raw_ts(self):
        history = [
            {"entity_id": "sensor.x", "points": [
                {"ts": "2026-06-05T08:00:00Z", "value": 71.2},
                {"ts": "2026-06-05T09:00:00.5+00:00", "value": 71.8},
            ]},
        ]
        normalized = _history_series_with_epoch_ms(history)
        point = normalized[0]["points"][0]
        self.assertIsInstance(point["ts_epoch_ms"], int)
        self.assertNotIsInstance(point["ts_epoch_ms"], bool)
        # Raw ts stays on the point for the render-request contract.
        self.assertEqual(point["ts"], "2026-06-05T08:00:00Z")
        # The source is not mutated.
        self.assertNotIn("ts_epoch_ms", history[0]["points"][0])

    def test_prompt_projection_strips_raw_ts_keeps_epoch_ms(self):
        request = {
            "chart_spec": {"title": "t"},
            "history_series": _history_series_with_epoch_ms(
                [{"entity_id": "sensor.x", "unit": "degF", "kind": "numeric", "points": [
                    {"ts": "2026-06-05T08:00:00Z", "value": 71.2},
                ]}]
            ),
        }
        view = _codegen_request_view(request)
        series = view["history_series"][0]
        point = series["points"][0]
        # The model never sees a raw ISO timestamp string.
        self.assertNotIn("ts", point)
        self.assertIn("ts_epoch_ms", point)
        self.assertIsInstance(point["ts_epoch_ms"], int)

    def test_prompt_projection_previews_bounded_points_under_the_runtime_key(self):
        # The full points overflow the model context on real windows; the prompt
        # carries a BOUNDED preview under the same 'points' key the runtime uses
        # (so accessors work), while the sandbox gets every point. A pure summary
        # (no real points) was measured to make the floor model produce empty plots.
        points = [{"ts": "2026-06-05T08:00:00Z", "value": 70.0 + i} for i in range(500)]
        request = {
            "chart_spec": {"title": "t"},
            "history_series": _history_series_with_epoch_ms(
                [{"entity_id": "sensor.x", "unit": "degF", "kind": "numeric", "points": points}]
            ),
        }
        series = _codegen_request_view(request)["history_series"][0]
        # A bounded preview is disclosed under the runtime key 'points' — not the
        # whole 500-point series, and marked truncated so the model reads all at runtime.
        self.assertIn("points", series)
        self.assertLessEqual(len(series["points"]), _CODEGEN_PROMPT_PREVIEW_POINTS)
        self.assertLess(len(series["points"]), 500)
        self.assertTrue(series["points_truncated"])
        # Preview spans the full range (first + last real points are kept).
        self.assertEqual(series["points"][0]["value"], 70.0)
        self.assertEqual(series["points"][-1]["value"], 569.0)
        # Shape + count + range + stats accompany it.
        self.assertEqual(series["point_count"], 500)
        self.assertEqual(series["unit"], "degF")
        self.assertIn("first", series["ts_epoch_ms_range"])
        self.assertIn("last", series["ts_epoch_ms_range"])
        self.assertEqual(series["value_stats"]["min"], 70.0)
        self.assertEqual(series["value_stats"]["max"], 569.0)

    def test_prompt_projection_keeps_all_points_when_below_preview_cap(self):
        # A short series is disclosed whole (not truncated).
        points = [{"ts": "2026-06-05T08:00:00Z", "value": 71.0},
                  {"ts": "2026-06-05T09:00:00Z", "value": 72.0}]
        request = {
            "chart_spec": {"title": "t"},
            "history_series": _history_series_with_epoch_ms(
                [{"entity_id": "sensor.x", "unit": "degF", "kind": "numeric", "points": points}]
            ),
        }
        series = _codegen_request_view(request)["history_series"][0]
        self.assertEqual(len(series["points"]), 2)
        self.assertFalse(series["points_truncated"])

    def test_prompt_projection_summarizes_state_series_with_distinct_states(self):
        # Binary/categorical series get distinct_states (not numeric value_stats),
        # so the model knows every state to handle even if samples miss some.
        points = (
            [{"ts": "2026-06-05T08:00:00Z", "raw_state": "idle"}] * 3
            + [{"ts": "2026-06-05T09:00:00Z", "raw_state": "cooling"}]
            + [{"ts": "2026-06-05T10:00:00Z", "raw_state": "heating"}]
        )
        request = {
            "chart_spec": {"title": "t"},
            "history_series": _history_series_with_epoch_ms(
                [{"entity_id": "climate.x", "kind": "categorical_state", "points": points}]
            ),
        }
        series = _codegen_request_view(request)["history_series"][0]
        self.assertNotIn("value_stats", series)
        self.assertEqual(series["distinct_states"], ["idle", "cooling", "heating"])
        # distinct_states enumerates every state even when the points preview is
        # a bounded subset that could miss a rare state.
        self.assertIn("points", series)

    def test_dispatched_codegen_data_carries_epoch_ms(self):
        # Regression guard: the render_request the sandbox executes against carries
        # integer ts_epoch_ms on every point (the model reads it, never raw ISO).
        worker = SandboxWorkerRenderer()
        codegen = FakeCodegenClient(generate_code=grounded_answer_generated_python())
        with tempfile.TemporaryDirectory() as temp_dir:
            hass, entry = _configured_codegen_hass(
                codegen_client=codegen, worker=worker, artifact_dir=Path(temp_dir)
            )
            start = _start_job(hass, entry)
            _snapshot_job(hass, entry, start["snapshot"]["job_id"])

        self.assertTrue(worker.calls, "no codegen dispatch recorded")
        for series in worker.calls[-1]["history_series"]:
            for point in series["points"]:
                self.assertIn("ts_epoch_ms", point)
                self.assertIsInstance(point["ts_epoch_ms"], int)
                self.assertNotIsInstance(point["ts_epoch_ms"], bool)

    def test_downsample_preview_spans_range_and_is_bounded(self):
        points = [{"value": float(i)} for i in range(100)]
        preview = _downsample_preview(points, 12)
        self.assertLessEqual(len(preview), 12)
        # First and last real points are always kept so the span is visible.
        self.assertEqual(preview[0]["value"], 0.0)
        self.assertEqual(preview[-1]["value"], 99.0)
        # Monotonic (evenly spaced, in order).
        vals = [p["value"] for p in preview]
        self.assertEqual(vals, sorted(vals))

    def test_downsample_preview_returns_all_when_below_cap(self):
        points = [{"value": 1.0}, {"value": 2.0}]
        self.assertEqual(_downsample_preview(points, 12), points)
        self.assertEqual(_downsample_preview([], 12), [])


class PlannerUnitGroundingTests(unittest.TestCase):
    """The planner's guessed series unit is overwritten from the catalog."""

    def _spec(self, unit, entity_id="sensor.kitchen_ecobee_temperature"):
        return {"series": [{"series_id": entity_id, "label": "Kitchen",
                            "source": {"type": "entity", "entity_id": entity_id},
                            "unit": unit}]}

    def test_catalog_unit_overwrites_planner_guess(self):
        # Planner hallucinated °C on an °F sensor (observed live); the catalog wins.
        spec = self._spec("°C")
        catalog = [{"entity_id": "sensor.kitchen_ecobee_temperature",
                    "unit_of_measurement": "°F"}]
        _apply_catalog_units(spec, catalog)
        self.assertEqual(spec["series"][0]["unit"], "°F")

    def test_unknown_entity_left_untouched(self):
        spec = self._spec("°C", entity_id="sensor.not_in_catalog")
        _apply_catalog_units(spec, [{"entity_id": "sensor.other", "unit_of_measurement": "%"}])
        self.assertEqual(spec["series"][0]["unit"], "°C")

    def test_aggregate_source_resolves_first_entity(self):
        spec = {"series": [{"series_id": "agg", "label": "Avg",
                            "source": {"type": "aggregate",
                                       "entity_ids": ["sensor.basement_temperature"]},
                            "unit": "°C"}]}
        _apply_catalog_units(spec, [{"entity_id": "sensor.basement_temperature",
                                     "unit_of_measurement": "°F"}])
        self.assertEqual(spec["series"][0]["unit"], "°F")


class _FakeStates:
    def __init__(self, mapping):
        self._mapping = mapping

    def get(self, entity_id):
        return self._mapping.get(entity_id)


class _FakeState:
    def __init__(self, attributes):
        self.attributes = attributes


class CatalogUnitBackfillTests(unittest.TestCase):
    """A catalog snapshot missing a unit (entity unavailable at build time) is
    backfilled from the live state — the empty-axis-label ("Value ()") fix."""

    def _hass(self, unit):
        states = _FakeStates({
            "sensor.kitchen_ecobee_temperature": _FakeState({"unit_of_measurement": unit})
        })
        return type("Hass", (), {"states": states})()

    def test_missing_unit_backfilled_from_live_state(self):
        items = [{"entity_id": "sensor.kitchen_ecobee_temperature",
                  "unit_of_measurement": None, "visible_to_agent": True}]
        resolved = backfill_catalog_units_from_state(self._hass("°F"), items)
        self.assertEqual(resolved[0]["unit_of_measurement"], "°F")
        # The store item is not mutated (a copy is returned).
        self.assertIsNone(items[0]["unit_of_measurement"])

    def test_present_unit_not_overridden(self):
        items = [{"entity_id": "sensor.kitchen_ecobee_temperature",
                  "unit_of_measurement": "°C"}]
        resolved = backfill_catalog_units_from_state(self._hass("°F"), items)
        self.assertEqual(resolved[0]["unit_of_measurement"], "°C")

    def test_no_live_unit_leaves_item_unchanged(self):
        items = [{"entity_id": "binary_sensor.kitchen_door",
                  "unit_of_measurement": None}]
        # Entity has no unit attribute in state.
        hass = type("Hass", (), {"states": _FakeStates({
            "binary_sensor.kitchen_door": _FakeState({})})})()
        resolved = backfill_catalog_units_from_state(hass, items)
        self.assertIsNone(resolved[0]["unit_of_measurement"])


class OverlayBandTests(unittest.TestCase):
    """ADR-0033: the integration precomputes shaded overlay bands so codegen draws
    them (axvspan) instead of plotting the state as a line."""

    def _climate_point(self, ts, action):
        return {"ts": ts, "value": "cool", "raw_state": "cool", "quality": "ok",
                "attrs": {"hvac_action": action}}

    def _spec(self, **overlay):
        base = {"overlay_id": "overlay-001", "label": "AC running",
                "render_as": "shaded_intervals",
                "source": {"type": "entity", "entity_id": "climate.kitchen_ecobee",
                           "attribute": "hvac_action"}}
        base.update(overlay)
        return {"overlays": [base]}

    def test_bands_use_hvac_action_not_the_mode_state(self):
        # The overlay must shade cooling/heating (hvac_action), NOT the constant
        # "cool" mode — the exact bug Colin saw (a flat "cool" line).
        hs = [{"entity_id": "climate.kitchen_ecobee", "kind": "categorical_state", "points": [
            self._climate_point("2026-07-01T00:00:00+00:00", "idle"),
            self._climate_point("2026-07-01T01:00:00+00:00", "cooling"),
            self._climate_point("2026-07-01T02:00:00+00:00", "idle"),
            self._climate_point("2026-07-01T03:00:00+00:00", "heating"),
            self._climate_point("2026-07-01T04:00:00+00:00", "idle"),
        ]}]
        bands = _compute_overlay_bands(
            self._spec(color_map={"cooling": "#4C78A8", "heating": "#F58518"}), hs)
        self.assertEqual([b["label"] for b in bands], ["cooling", "heating"])
        self.assertEqual(bands[0]["color"], "#4C78A8")
        self.assertEqual(bands[1]["color"], "#F58518")
        # Bands carry epoch-ms bounds spanning exactly the active segment.
        self.assertEqual(bands[0]["end_ms"] - bands[0]["start_ms"], 3600 * 1000)
        self.assertNotIn("cool", [b["label"] for b in bands])

    def test_binary_overlay_uses_active_values(self):
        hs = [{"entity_id": "binary_sensor.kitchen_door", "kind": "binary_state", "points": [
            {"ts": "2026-07-01T00:00:00+00:00", "value": "off", "raw_state": "off", "quality": "ok"},
            {"ts": "2026-07-01T01:00:00+00:00", "value": "on", "raw_state": "on", "quality": "ok"},
            {"ts": "2026-07-01T02:00:00+00:00", "value": "off", "raw_state": "off", "quality": "ok"},
        ]}]
        spec = {"overlays": [{"overlay_id": "overlay-001", "label": "Door open",
                              "render_as": "shaded_intervals", "active_values": ["on"],
                              "source": {"type": "entity", "entity_id": "binary_sensor.kitchen_door"}}]}
        bands = _compute_overlay_bands(spec, hs)
        self.assertEqual(len(bands), 1)
        self.assertEqual(bands[0]["label"], "Door open")

    def test_no_overlays_yields_no_bands(self):
        self.assertEqual(_compute_overlay_bands({"overlays": []}, []), [])
        self.assertEqual(_compute_overlay_bands({}, []), [])


class TimelineBandTests(unittest.TestCase):
    """Spec C1: a PRIMARY timeline series (a door on its own) precomputes state
    intervals the same way an overlay does, so codegen draws a broken_barh lane
    instead of near-zero verticals off raw points (live e2e-09)."""

    def _door_hs(self, points):
        return [{"entity_id": "binary_sensor.kitchen_door", "kind": "binary_state",
                 "points": points}]

    def _timeline_spec(self, label="Kitchen Door"):
        return {"chart_type": "timeline", "series": [
            {"series_id": "series-001", "label": label,
             "source": {"type": "entity", "entity_id": "binary_sensor.kitchen_door"}}]}

    def test_primary_door_timeline_yields_on_bands(self):
        hs = self._door_hs([
            {"ts": "2026-07-01T00:00:00+00:00", "value": "off", "raw_state": "off", "quality": "ok"},
            {"ts": "2026-07-01T01:00:00+00:00", "value": "on", "raw_state": "on", "quality": "ok"},
            {"ts": "2026-07-01T02:00:00+00:00", "value": "off", "raw_state": "off", "quality": "ok"},
        ])
        bands = _compute_timeline_bands(self._timeline_spec(), hs)
        self.assertEqual(len(bands), 1)
        # The lane label is the series label, the band carries the entity id, and
        # the color is a real hex the model can pass to broken_barh.
        self.assertEqual(bands[0]["label"], "Kitchen Door")
        self.assertEqual(bands[0]["entity_id"], "binary_sensor.kitchen_door")
        self.assertRegex(bands[0]["color"], r"^#[0-9a-fA-F]{6}$")
        # The band spans exactly the on segment (01:00 → 02:00 window end).
        self.assertEqual(bands[0]["end_ms"] - bands[0]["start_ms"], 3600 * 1000)

    def test_timeline_bands_match_pillow_regions(self):
        # C1 parity: the precomputed spans equal the trusted region primitive
        # Pillow's _render_timeline_png fills, so codegen and Pillow agree.
        from custom_components.isolinear.in_process_renderer import (
            _BINARY_ON_VALUES, _binary_on_regions,
        )
        from custom_components.isolinear.history_dispatch import _history_window_end_dt
        hs = self._door_hs([
            {"ts": "2026-07-01T00:00:00+00:00", "value": "off", "raw_state": "off", "quality": "ok"},
            {"ts": "2026-07-01T01:00:00+00:00", "value": "on", "raw_state": "on", "quality": "ok"},
            {"ts": "2026-07-01T01:30:00+00:00", "value": "off", "raw_state": "off", "quality": "ok"},
            {"ts": "2026-07-01T02:00:00+00:00", "value": "on", "raw_state": "on", "quality": "ok"},
            {"ts": "2026-07-01T02:15:00+00:00", "value": "off", "raw_state": "off", "quality": "ok"},
        ])
        bands = _compute_timeline_bands(self._timeline_spec(), hs)
        window_end = _history_window_end_dt(hs)
        regions = _binary_on_regions(hs[0], _BINARY_ON_VALUES, window_end=window_end)
        self.assertEqual(len(bands), len(regions))
        for band, (start, end) in zip(bands, regions):
            self.assertEqual(band["start_ms"], int(start.timestamp() * 1000))
            self.assertEqual(band["end_ms"], int(end.timestamp() * 1000))

    def test_categorical_timeline_one_band_per_state(self):
        hs = [{"entity_id": "climate.kitchen_ecobee", "kind": "categorical_state", "points": [
            {"ts": "2026-07-01T00:00:00+00:00", "value": "cool", "raw_state": "cool", "quality": "ok"},
            {"ts": "2026-07-01T01:00:00+00:00", "value": "heat", "raw_state": "heat", "quality": "ok"},
            {"ts": "2026-07-01T02:00:00+00:00", "value": "cool", "raw_state": "cool", "quality": "ok"},
        ]}]
        spec = {"chart_type": "timeline", "series": [
            {"series_id": "series-001", "label": "HVAC mode",
             "source": {"type": "entity", "entity_id": "climate.kitchen_ecobee"}}]}
        bands = _compute_timeline_bands(spec, hs)
        # cool appears twice (two segments), heat once → distinct state labels present.
        self.assertEqual({b["label"] for b in bands}, {"cool", "heat"})

    def test_dispatch_routes_timeline_vs_overlay(self):
        door_points = [
            {"ts": "2026-07-01T00:00:00+00:00", "value": "off", "raw_state": "off", "quality": "ok"},
            {"ts": "2026-07-01T01:00:00+00:00", "value": "on", "raw_state": "on", "quality": "ok"},
            {"ts": "2026-07-01T02:00:00+00:00", "value": "off", "raw_state": "off", "quality": "ok"},
        ]
        hs = self._door_hs(door_points)
        # A timeline family with no overlays routes to the primary-timeline path.
        self.assertEqual(len(_compute_derived_intervals(self._timeline_spec(), hs)), 1)
        # A non-timeline family routes to the overlay path (empty overlays → []).
        self.assertEqual(_compute_derived_intervals({"chart_type": "time_series", "overlays": []}, hs), [])

    def test_empty_timeline_yields_no_bands(self):
        # A door that never opened → no on-regions → an empty lane (C1/Scenario D).
        hs = self._door_hs([
            {"ts": "2026-07-01T00:00:00+00:00", "value": "off", "raw_state": "off", "quality": "ok"},
            {"ts": "2026-07-01T02:00:00+00:00", "value": "off", "raw_state": "off", "quality": "ok"},
        ])
        self.assertEqual(_compute_timeline_bands(self._timeline_spec(), hs), [])


class OverlayPromptRuleTests(unittest.TestCase):
    def test_prompt_rules_direct_axvspan_bands_and_numeric_only_lines(self):
        rules = " ".join(_CODEGEN_PROMPT_RULES).lower()
        self.assertIn("derived_intervals", rules)
        self.assertIn("axvspan", rules)
        # Only numeric series become lines; state series are not plotted as lines.
        self.assertIn("'kind' is 'numeric'", rules)
        self.assertIn("do not compute these intervals yourself", rules)


class TimelinePromptRuleTests(unittest.TestCase):
    """Spec C2: a chart whose every series is a state series is a broken_barh step
    track drawn from precomputed derived_intervals — not a line, not axvspan bands,
    not intervals derived from raw points (the e2e-09 near-zero verticals)."""

    def test_prompt_rules_direct_broken_barh_timeline_from_intervals(self):
        rules = " ".join(_CODEGEN_PROMPT_RULES)
        lowered = rules.lower()
        self.assertIn("broken_barh", lowered)
        self.assertIn("timeline", lowered)
        # Drawn from the precomputed intervals, on a date axis, never derived by the model.
        self.assertIn("data['derived_intervals']", rules)
        self.assertIn("xaxis_date", lowered)
        self.assertIn("do not derive intervals from raw points", lowered)
        # The family is data-driven (every series is a state series), not user_request-driven.
        self.assertIn("every series in data['history_series'] is a state series", rules.lower())
        # Lane style (eyes-on fix): a grey off-baseline track spanning the window +
        # ONE lane per entity labelled by name, not an on/off value axis.
        self.assertIn("off-track", lowered)
        self.assertIn("one fixed horizontal lane", lowered)
        self.assertIn("not 'on'/'off'", lowered)


class FamilyDegradePromptRuleTests(unittest.TestCase):
    """open-queue (w), 0.2.26: codegen owns the computation, not the chart
    FAMILY (invariant #9). A heatmap is a family with no home in the ADR-0023
    envelope, so a single-sensor 'heatmap by hour and day' request degrades to
    the histogram the planner already chose — never a 2-D grid (live e2e-15
    garbage). Eval-gated with evals/heatmap_rule_gate.py."""

    def test_prompt_rules_forbid_2d_heatmap_and_degrade_to_histogram(self):
        rules = " ".join(_CODEGEN_PROMPT_RULES)
        lowered = rules.lower()
        # The three permitted families are named and a heatmap is forbidden.
        self.assertIn("render only these chart families", lowered)
        self.assertIn("never draw a 2-d heatmap", lowered)
        # The specific 2-D drawing calls are named so the model cannot reach for
        # them (seaborn.heatmap burned the live e2e-15 render; the others are the
        # obvious matplotlib routes to the same 2-D grid).
        for call in ("seaborn.heatmap", "pcolormesh", "imshow", "hist2d"):
            self.assertIn(call, lowered)
        # A heatmap ask degrades to the value distribution (a histogram), not a grid.
        self.assertIn("render a histogram", lowered)
        # The boundary: user_request may change the computation, never the family
        # (the family is fixed by the data — timeline-codegen-rendering reworded this).
        self.assertIn("never which chart family you draw", lowered)


class VerdictOmissionPromptRuleTests(unittest.TestCase):
    """open-queue (cc), 0.2.40: value/descriptive claims (mean/delta answering
    'what was X?') omit verdict+rule so the grounding step-5 containment check
    never runs on a sentence that has no Yes/No band label. The live e2e-11
    symptom was `grounding_verdict_ambiguous` burning the whole repair budget on
    a correct descriptive mean. Eval-gated with evals/verdict_omission_gate.py."""

    def test_prompt_rules_scope_verdict_and_rule_to_band_judgments(self):
        rules = " ".join(_CODEGEN_PROMPT_RULES)
        lowered = rules.lower()
        # verdict+rule are attached ONLY for a Yes/No or categorical judgment.
        self.assertIn("attach 'verdict' and 'rule' to a claim only when", lowered)
        # A plain descriptive value answer emits a value-only claim.
        self.assertIn("omit 'verdict' and 'rule'", lowered)
        # The three descriptive metrics that motivated the rule are named.
        for word in ("average", "delta", "total"):
            self.assertIn(word, lowered)

    def _two_sensor_history(self):
        return [
            {
                "entity_id": "sensor.kitchen_ecobee_temperature",
                "kind": "numeric",
                "unit": "°F",
                "points": [
                    {"ts_epoch_ms": 1782000000000 + i * 300000, "value": 73.0}
                    for i in range(12)
                ],
            },
            {
                "entity_id": "sensor.basement_temperature",
                "kind": "numeric",
                "unit": "°F",
                "points": [
                    {"ts_epoch_ms": 1782000000000 + i * 300000, "value": 72.0}
                    for i in range(12)
                ],
            },
        ]

    def test_descriptive_mean_claim_without_verdict_is_served(self):
        # A value-only mean claim (no verdict/rule) must NOT be withheld — it's
        # value-verified by the step-4 recompute instead. This pins the
        # grounding contract the prompt rule targets.
        render_metadata = {
            "answer_text": "The average of the kitchen and basement was 72.50 °F.",
            "claims": [
                {
                    "metric": "mean",
                    "inputs": [
                        "sensor.kitchen_ecobee_temperature",
                        "sensor.basement_temperature",
                    ],
                    "value": 72.5,
                }
            ],
        }
        result = run_grounding_check(render_metadata, self._two_sensor_history())
        self.assertFalse(result.get("withheld"), f"value-only claim withheld: {result}")

    def test_null_verdict_with_vestigial_empty_rule_is_tolerated(self):
        # The shape gemma actually emits under the (cc) rule: verdict=None but a
        # leftover empty-bands rule stub. A rule is inert without a verdict
        # (steps 5/6 both require verdict is not None), so grounding must NOT
        # reject the stub as malformed — the mean is still value-verified.
        render_metadata = {
            "answer_text": "The average of the kitchen and basement was 72.50 °F.",
            "claims": [
                {
                    "metric": "mean",
                    "inputs": [
                        "sensor.kitchen_ecobee_temperature",
                        "sensor.basement_temperature",
                    ],
                    "value": 72.5,
                    "verdict": None,
                    "rule": {"bands": [], "basis": "value"},
                }
            ],
        }
        result = run_grounding_check(render_metadata, self._two_sensor_history())
        self.assertFalse(result.get("withheld"), f"null-verdict claim withheld: {result}")
        synthetic = result.get("synthetic_error") or {}
        self.assertNotEqual(synthetic.get("code"), "grounding_claim_malformed")

    def test_wrong_value_on_verdict_less_claim_still_caught(self):
        # The inert-rule tolerance must NOT weaken step-4 value verification: a
        # verdict-less mean claim with a WRONG value (real mean is 72.5) still
        # trips grounding_value_mismatch and is withheld. Pins that skipping rule
        # validation did not open a path for an unverified number.
        render_metadata = {
            "answer_text": "The average of the kitchen and basement was 99.90 °F.",
            "claims": [
                {
                    "metric": "mean",
                    "inputs": [
                        "sensor.kitchen_ecobee_temperature",
                        "sensor.basement_temperature",
                    ],
                    "value": 99.9,
                    "verdict": None,
                    "rule": {"bands": [], "basis": "value"},
                }
            ],
        }
        result = run_grounding_check(render_metadata, self._two_sensor_history())
        synthetic = result.get("synthetic_error") or {}
        self.assertEqual(synthetic.get("code"), "grounding_value_mismatch", result)


class CorrelationEmissionPromptRuleTests(unittest.TestCase):
    """open-queue (ff): a correlation is a scalar with nothing new to plot, so
    the floor model plots the two raw sensors and returns WITHOUT an answer_text
    (live: 3/5 plot-only). The rule makes the coefficient the mandatory
    deliverable of a correlation question. Eval-gated with
    evals/correlation_answer_gate.py (with-rule 4/4 served + verified vs
    without-rule 0/4)."""

    def test_prompt_rules_make_correlation_answer_mandatory(self):
        rules = " ".join(_CODEGEN_PROMPT_RULES)
        lowered = rules.lower()
        # The distinctive marker the gate strips for its without-arm.
        self.assertIn("important for correlation questions", lowered)
        # Plotting the raw sensors is explicitly NOT sufficient on its own.
        self.assertIn("not enough on its own", lowered)
        # The coefficient MUST be computed and reported in answer_text.
        self.assertIn("must also compute the coefficient", lowered)
        self.assertIn("report it in answer_text", lowered)
        # It names the align()-based idiom, consistent with ADR-0036.
        self.assertIn("frame.corr().iloc[0, 1]", rules)

    def test_prompt_rules_scope_correlation_verdict_to_abs_basis(self):
        # (ff) live root cause: the model derives the verdict from abs(corr) but
        # declared basis 'value', so a negative correlation (-0.40) was withheld
        # as grounding_verdict_contradicted. The rule must tell the model to match
        # 'basis' to the verdict derivation ('abs' for correlation strength) and
        # the pearson_r example must use 'abs'.
        rules = " ".join(_CODEGEN_PROMPT_RULES)
        lowered = rules.lower()
        self.assertIn("'basis' must match how you derived the verdict", lowered)
        self.assertIn("'basis': 'abs'", rules)
        # The pearson_r example carries abs basis, not value.
        self.assertIn("'rule': {'bands': [[0.3, 'yes'], [none, 'not really']], 'basis': 'abs'}", lowered)

    def test_prompt_rules_pin_smoothed_average_to_raw_frame(self):
        # Cross-sensor smoothed-average emission fidelity (2026-07-23, live 4/4
        # withheld): "the average of X and Y smoothed with a rolling average" made
        # the model report the mean OF a rolling average under a {'metric':'mean'}
        # claim — a window-dependent quantity ~0.11 °F off the plain mean, which
        # grounding recomputed and withheld. The rule must pin the STATED average
        # to the raw aligned frame so the mean claim verifies; smoothing is a chart
        # transform only. Distinctive marker is what rolling_avg_emission_gate.py
        # strips for its without-arm.
        rules = " ".join(_CODEGEN_PROMPT_RULES)
        lowered = rules.lower()
        self.assertIn("asks for both an average and smoothing", lowered)
        # The stated average comes from the raw aligned frame, not the rolling one.
        self.assertIn("frame.mean(axis=1).mean()", rules)
        self.assertIn("never from the rolling/smoothed series", lowered)
        # It names the failure mode so the model understands the stakes.
        self.assertIn("recomputes as", lowered)
        self.assertIn("withholding your answer", lowered)


class CodegenPromptGroundingTests(unittest.TestCase):
    """The codegen prompt instructs COMPUTE-and-format, verdicts derived (ADR-0031 D3)."""

    def test_prompt_rules_carry_the_grounding_instruction(self):
        rules = " ".join(_CODEGEN_PROMPT_RULES).lower()
        self.assertIn("answer_text", rules)
        self.assertIn("f-string", rules)
        self.assertIn("verdict", rules)

    def test_prompt_rules_make_history_series_the_data_authority(self):
        # 0.2.19 regression fix: the floor model must plot from history_series
        # directly and never read data/units/the series list from chart_spec
        # (which carries a planner-guessed unit and no top-level entity_id).
        rules = " ".join(_CODEGEN_PROMPT_RULES).lower()
        self.assertIn("chart_spec is intent", rules)
        self.assertIn("iterating that list directly", rules)
        # The preview is named as a bounded preview under the runtime 'points' key.
        self.assertIn("points_truncated", rules)
        self.assertIn("bounded preview", rules)

    def test_prompt_rules_direct_the_model_to_epoch_ms(self):
        # Packet 2 (D9): the prompt names ts_epoch_ms and forbids parsing raw strings.
        rules = " ".join(_CODEGEN_PROMPT_RULES).lower()
        self.assertIn("ts_epoch_ms", rules)
        self.assertIn("epoch", rules)

    def test_prompt_rules_enumerate_the_sandbox_analysis_libraries(self):
        # Packet 3 (D6): the prompt names every allowlisted analysis library —
        # the old "nothing except matplotlib" rule contradicted the pandas
        # epoch-ms hint and would suppress scipy/seaborn analysis outright.
        rules = " ".join(_CODEGEN_PROMPT_RULES).lower()
        for library in ("matplotlib", "pandas", "numpy", "scipy", "seaborn"):
            self.assertIn(library, rules)
        self.assertNotIn("do not import anything except matplotlib", rules)

    def test_prompt_rules_document_the_anchored_claim_window(self):
        # Spec §1 (answer-grounding-check): event-scoped claims carry an anchored
        # window the integration can re-detect (4d shipped the check side; the
        # prompt must teach the emission side or the anchor path never exercises).
        rules = " ".join(_CODEGEN_PROMPT_RULES).lower()
        self.assertIn("anchor", rules)
        self.assertIn("duration_ms", rules)
        self.assertIn("resolved_at", rules)
        self.assertIn("occurrence", rules)

    def test_bare_non_ascii_rule_is_retired_grounding_rule_keeps_degree_out_of_literals(self):
        # open-queue (o), 0.2.22: the failure-driven bare-non-ASCII rule (0.2.13)
        # was eval-gated (evals/codegen_rule_gate.py: 36 runs, 0 incidents in
        # either arm) and RETIRED. It must be gone — the prompt no longer tells
        # the model how to write a bare token — but the ° class stays structurally
        # prevented by the unit-grounding rule, which makes the model read the
        # unit from the data (a str variable) rather than typing it as a literal.
        rules_text = " ".join(_CODEGEN_PROMPT_RULES)
        self.assertNotIn("bare Python token", rules_text)
        # The grounding rule still carries ° (as an example unit string) and
        # instructs reading the unit from the series data.
        self.assertIn("°", rules_text)
        self.assertIn("history_series", rules_text)
        self.assertIn("unit", rules_text.lower())


def _legend_generated_python(computed_color: str = "#2ca02c") -> str:
    """render_chart that writes a fixed PNG and self-reports a two-row legend:
    a solid raw-sensor series and a dashed computed average (spec
    card-level-legend-codegen C1). computed_color is parameterized so a test can
    feed an invalid color and prove the cosmetic drop."""
    return (
        "def render_chart(data, output_path):\n"
        f'    png_bytes = bytes.fromhex("{SAFE_SAMPLE_PNG_HEX}")\n'
        '    with open(output_path, "wb") as image_file:\n'
        "        image_file.write(png_bytes)\n"
        '    return {"title": "t", "series_plotted": ["sensor.a", "sensor.b"],\n'
        '            "overlays_plotted": [], "x_min": None, "x_max": None, "warnings": [],\n'
        '            "summary": "Kitchen and basement with their average.",\n'
        '            "legend": [\n'
        '                {"label": "Kitchen", "entity_id": "sensor.a", "color": "#1f77b4", "kind": "series"},\n'
        f'                {{"label": "Average", "entity_id": "sensor.a", "color": "{computed_color}", "kind": "computed"}}\n'
        "            ]}\n"
    )


class CodegenLegendSandboxTests(unittest.TestCase):
    """spec card-level-legend-codegen C1/C6: the sandbox preserves the
    self-reported legend (previously dropped by _normalize_render_metadata),
    sanitizes it, and never fails the response on a malformed row."""

    def _run_dir(self):
        (REPO_ROOT / ".test-output").mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=REPO_ROOT / ".test-output")

    def test_legend_manifest_passes_through_with_computed_kind(self):
        with self._run_dir() as run_directory:
            result = invoke_codegen_sandbox(
                sample_codegen_render_request(python_code=_legend_generated_python()),
                work_root=Path(run_directory),
            )
        self.assertEqual(result["status"], "success", result.get("error"))
        legend = result["render_metadata"]["legend"]
        self.assertEqual([row["kind"] for row in legend], ["series", "computed"])
        self.assertEqual(legend[1]["color"], "#2ca02c")
        self.assertEqual(result["render_metadata"]["summary"], "Kitchen and basement with their average.")
        # Render-result stays schema-valid with the additive computed kind.
        validate_contract("render-result", result)

    def test_malformed_color_row_is_dropped_not_failed(self):
        # A computed row with a non-hex color cannot render a swatch; it is
        # dropped (cosmetic, C6) — the render still succeeds and stays valid.
        with self._run_dir() as run_directory:
            result = invoke_codegen_sandbox(
                sample_codegen_render_request(python_code=_legend_generated_python(computed_color="tab:green")),
                work_root=Path(run_directory),
            )
        self.assertEqual(result["status"], "success", result.get("error"))
        legend = result["render_metadata"]["legend"]
        self.assertEqual([row["kind"] for row in legend], ["series"])  # the bad computed row dropped
        validate_contract("render-result", result)

    def test_chart_only_render_carries_no_legend(self):
        with self._run_dir() as run_directory:
            result = invoke_codegen_sandbox(
                sample_codegen_render_request(python_code=safe_generated_python()),
                work_root=Path(run_directory),
            )
        self.assertEqual(result["status"], "success", result.get("error"))
        self.assertNotIn("legend", result["render_metadata"])


class CodegenLegendEndToEndTests(unittest.TestCase):
    """spec card-level-legend-codegen C4: the legend + summary thread from the
    codegen render onto the served artifact and the complete snapshot — the
    _build_worker_artifact_metadata parity gap the ADR-0030 cutover left open."""

    def test_legend_reaches_the_complete_snapshot_and_artifact(self):
        worker = SandboxWorkerRenderer()
        codegen = FakeCodegenClient(generate_code=_legend_generated_python())
        with tempfile.TemporaryDirectory() as temp_dir:
            hass, entry = _configured_codegen_hass(
                codegen_client=codegen, worker=worker, artifact_dir=Path(temp_dir)
            )
            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertEqual(snapshot["snapshot"]["status"], "complete", snapshot)
            chart = snapshot["snapshot"]["chart"]
            self.assertEqual(chart.get("render_path"), "codegen")
            legend = chart.get("legend")
            self.assertIsNotNone(legend, "codegen legend dropped before the snapshot")
            self.assertEqual([row["kind"] for row in legend], ["series", "computed"])
            self.assertEqual(chart.get("summary"), "Kitchen and basement with their average.")
            # Threads consistently onto the served artifact too.
            artifact = _orchestration_store(hass, entry)["latest_artifact"]
            self.assertEqual(artifact.get("legend"), legend)


class CodegenLegendPromptRuleTests(unittest.TestCase):
    """spec card-level-legend-codegen C1/C2: the codegen return contract requires
    the legend manifest, solid/dashed line styling, and no in-image ax.legend()."""

    def test_prompt_rules_require_the_legend_manifest(self):
        rules = " ".join(_CODEGEN_PROMPT_RULES)
        lowered = rules.lower()
        # The return-contract dict names legend.
        self.assertIn("title, series_plotted, warnings, legend", lowered)
        # A self-reported hex color manifest with the three kinds.
        self.assertIn("return a 'legend' list", lowered)
        for kind in ("'series'", "'computed'", "'overlay'"):
            self.assertIn(kind, lowered)
        # Colin's convention: solid raw sensors, dashed computed series.
        self.assertIn("solid", lowered)
        self.assertIn("dashed", lowered)
        self.assertIn("linestyle='--'", rules)
        # No redundant in-image legend.
        self.assertIn("do not call ax.legend()", lowered)


class CodegenLegendSchemaTests(unittest.TestCase):
    """The computed kind is additive on both legend schema copies."""

    def _schema(self, name: str) -> dict:
        return json.loads((DOCS_SCHEMAS / name).read_text())

    def test_computed_kind_in_render_result_and_snapshot_schemas(self):
        render_kind = self._schema("render-result.schema.json")[
            "properties"]["render_metadata"]["properties"]["legend"]["items"]["properties"]["kind"]["enum"]
        self.assertEqual(render_kind, ["series", "overlay", "computed"])
        snapshot_kind = self._schema("integration-job-snapshot.schema.json")[
            "$defs"]["legendItem"]["properties"]["kind"]["enum"]
        self.assertEqual(snapshot_kind, ["series", "overlay", "computed"])


if __name__ == "__main__":
    unittest.main()


class ComparisonDeltaEmissionPromptRuleTests(unittest.TestCase):
    """2026-07-20, live-driven (e2e-08): a two-sensor comparison is the same
    emission shape as correlation — the gap size is a scalar with nothing new to
    plot, so the model draws both lines and answers qualitatively ("generally
    higher") with NO claim. A claimless answer grounds as `pass` with
    answer_verification ABSENT, so an unchecked number reads as fact (a live run
    said "4.0 %" where the aligned truth was 4.63). The rule makes the average
    difference the mandatory deliverable AND pins the subtraction order so the
    claim and the integration's reference are the same quantity."""

    def test_prompt_rules_make_comparison_difference_mandatory(self):
        rules = " ".join(_CODEGEN_PROMPT_RULES)
        lowered = rules.lower()
        # The distinctive marker the gate strips for its without-arm.
        self.assertIn("important for two-sensor comparison questions", lowered)
        # Plotting both lines is explicitly NOT sufficient on its own.
        self.assertIn("not enough on its own", lowered)
        # The average difference must be computed off the aligned frame.
        self.assertIn("average difference", lowered)
        self.assertIn("(frame[a] - frame[b]).mean()", lowered)
        # Input ORDER is load-bearing: a swapped order flips the sign and the
        # integration's recompute would reject a correct answer.
        self.assertIn("same order you subtracted", lowered)
        # Window-average reading, not an instantaneous difference.
        self.assertIn("not the difference at a single instant", lowered)

    def test_prompt_rules_require_window_ms_for_stated_rolling_value(self):
        """rolling_mean needs params.window_ms to be verifiable at all, but a
        smoothing request is satisfied by the chart — the rule must NOT force a
        summary number, only make a stated one checkable."""
        rules = " ".join(_CODEGEN_PROMPT_RULES)
        lowered = rules.lower()
        self.assertIn("'params': {'window_ms'", rules)
        self.assertIn("cannot be verified", lowered)
        self.assertIn("do not invent a summary number", lowered)
