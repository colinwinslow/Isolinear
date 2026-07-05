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
from custom_components.isolinear.history_retrieval import (  # noqa: E402
    backfill_catalog_units_from_state,
)
from custom_components.isolinear.job_orchestration import (  # noqa: E402
    _apply_catalog_units,
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

    def test_prompt_rules_forbid_bare_non_ascii_tokens(self):
        # Bare non-ASCII characters (like °) outside string literals cause
        # syntax_error@LN in the sandbox; the prompt must steer models to always
        # put them inside quoted strings.
        rules = " ".join(_CODEGEN_PROMPT_RULES).lower()
        self.assertIn("bare", rules)
        self.assertIn("string literal", rules)
        self.assertIn("°", " ".join(_CODEGEN_PROMPT_RULES))


if __name__ == "__main__":
    unittest.main()
