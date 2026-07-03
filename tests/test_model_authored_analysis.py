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
    _CODEGEN_PROMPT_RULES,
    _codegen_request_view,
)
from custom_components.isolinear.job_orchestration import (  # noqa: E402
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
                [{"entity_id": "sensor.x", "points": [
                    {"ts": "2026-06-05T08:00:00Z", "value": 71.2},
                ]}]
            ),
        }
        view = _codegen_request_view(request)
        point = view["history_series"][0]["points"][0]
        # The model never sees a raw ISO timestamp string.
        self.assertNotIn("ts", point)
        self.assertIn("ts_epoch_ms", point)
        self.assertIsInstance(point["ts_epoch_ms"], int)

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


class CodegenPromptGroundingTests(unittest.TestCase):
    """The codegen prompt instructs COMPUTE-and-format, verdicts derived (ADR-0031 D3)."""

    def test_prompt_rules_carry_the_grounding_instruction(self):
        rules = " ".join(_CODEGEN_PROMPT_RULES).lower()
        self.assertIn("answer_text", rules)
        self.assertIn("f-string", rules)
        self.assertIn("verdict", rules)

    def test_prompt_rules_direct_the_model_to_epoch_ms(self):
        # Packet 2 (D9): the prompt names ts_epoch_ms and forbids parsing raw strings.
        rules = " ".join(_CODEGEN_PROMPT_RULES).lower()
        self.assertIn("ts_epoch_ms", rules)
        self.assertIn("epoch", rules)

    def test_prompt_rules_document_the_anchored_claim_window(self):
        # Spec §1 (answer-grounding-check): event-scoped claims carry an anchored
        # window the integration can re-detect (4d shipped the check side; the
        # prompt must teach the emission side or the anchor path never exercises).
        rules = " ".join(_CODEGEN_PROMPT_RULES).lower()
        self.assertIn("anchor", rules)
        self.assertIn("duration_ms", rules)
        self.assertIn("resolved_at", rules)
        self.assertIn("occurrence", rules)


if __name__ == "__main__":
    unittest.main()
