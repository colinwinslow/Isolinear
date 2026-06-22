"""TDD for ADR-0025 — live planner reasoning streaming as wait feedback.

Covers three units:
  1. ``sanitize_reasoning`` — redaction + rolling-tail length cap (D5, R1, R2).
  2. The streaming NDJSON read in ``OllamaCompatiblePlannerClient`` behind the
     optional ``on_reasoning`` callback (D1, D6 fallback).
  3. The orchestration live-reasoning slot: per-poll update, both-call phase
     labels, clear-on-complete / clear-on-failed, and the in-progress poll
     surfacing ``progress.reasoning`` (D2, D3, D4, R3, R4).

Spec: docs/specs/live-planner-reasoning-streaming-spec.md
BDD:  docs/bdd/live-planner-reasoning.feature
"""

import io
import json
import sys
import unittest
import unittest.mock
import urllib.error
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from custom_components.isolinear import model_provider  # noqa: E402
from custom_components.isolinear.model_provider import (  # noqa: E402
    REASONING_CHAR_CAP,
    OllamaCompatiblePlannerClient,
    sanitize_reasoning,
)
from custom_components.isolinear.job_state import (  # noqa: E402
    validate_job_snapshot_contract,
)
from custom_components.isolinear.job_orchestration import (  # noqa: E402
    apply_live_reasoning,
    SELECT_ENTITY_PHASE_LABEL,
    PLAN_CHART_PHASE_LABEL,
    _live_reasoning_slot,
)

# Reuse the real-slice integration harness (FakeHass/FakePlanner/_start_job/...).
from tests.test_first_real_vertical_slice import (  # noqa: E402
    FakePlanner,
    configured_real_slice_hass,
    _orchestration_store,
    _snapshot_job,
    _start_job,
)


def _ndjson_response(chunks: list[dict]) -> io.BytesIO:
    """Build a fake urlopen body: one JSON object per NDJSON line."""
    body = "\n".join(json.dumps(chunk) for chunk in chunks).encode("utf-8")
    return io.BytesIO(body)


class _FakeUrlopenCtx:
    def __init__(self, fp):
        self._fp = fp

    def __enter__(self):
        return self._fp

    def __exit__(self, *exc):
        return False


class SanitizeReasoningTests(unittest.TestCase):
    def test_cap_is_2000(self):
        self.assertEqual(REASONING_CHAR_CAP, 2000)

    def test_short_clean_text_passes_through(self):
        text = "Looking at sensor.upstairs_temperature for the user's prompt."
        self.assertEqual(sanitize_reasoning(text), text)

    def test_redacts_worker_url(self):
        out = sanitize_reasoning("I will call http://worker.local:8099/render now")
        self.assertNotIn("worker.local", out)
        self.assertNotIn("http://", out)

    def test_redacts_https_endpoint(self):
        out = sanitize_reasoning("endpoint https://ollama.example:11434/api/chat")
        self.assertNotIn("ollama.example", out)
        self.assertNotIn("https://", out)

    def test_redacts_bearer_token(self):
        out = sanitize_reasoning("auth Bearer abc123SECRETtoken456 used")
        self.assertNotIn("abc123SECRETtoken456", out)

    def test_redacts_unix_path(self):
        out = sanitize_reasoning("reading /home/hass/.storage/secrets.json here")
        self.assertNotIn("/home/hass/.storage/secrets.json", out)

    def test_redacts_windows_path(self):
        out = sanitize_reasoning(r"reading C:\Users\hass\token.txt here")
        self.assertNotIn(r"C:\Users\hass\token.txt", out)

    def test_redacts_named_secret_with_value(self):
        # ADR-0025 D5: named secret vocabulary mirrors job_orchestration's
        # forbidden-text guard. The key and its attached value are both removed.
        out = sanitize_reasoning("using access_token=eyJhbG.foo.bar to call HA")
        self.assertNotIn("eyJhbG.foo.bar", out)
        self.assertNotIn("access_token=", out)

    def test_redacts_long_lived_access_token_keyword(self):
        out = sanitize_reasoning("the long_lived_access_token is set")
        self.assertNotIn("long_lived_access_token", out)

    def test_redacts_openai_style_api_key(self):
        out = sanitize_reasoning("key sk-proj-AAAA1111BBBB2222 echoed by model")
        self.assertNotIn("sk-proj-AAAA1111BBBB2222", out)

    def test_redacts_bare_jwt(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w"
        out = sanitize_reasoning(f"token {jwt} leaked")
        self.assertNotIn(jwt, out)

    def test_keeps_approved_entity_id(self):
        out = sanitize_reasoning("The entity sensor.upstairs_temperature is approved.")
        self.assertIn("sensor.upstairs_temperature", out)

    def test_rolling_tail_caps_to_2000_with_leading_ellipsis(self):
        raw = "A" * 5000
        out = sanitize_reasoning(raw)
        self.assertLessEqual(len(out), REASONING_CHAR_CAP)
        self.assertTrue(out.startswith("…"))
        # The tail (newest content) is retained.
        self.assertTrue(out.endswith("A"))

    def test_empty_in_empty_out(self):
        self.assertEqual(sanitize_reasoning(""), "")


class StreamingPlannerTransportTests(unittest.TestCase):
    def _client(self):
        return OllamaCompatiblePlannerClient(
            endpoint_url="http://localhost:11434",
            planner_model="gemma",
        )

    def test_non_streaming_default_unchanged(self):
        """on_reasoning=None must keep stream:false single-read behavior."""
        client = self._client()
        captured = {}
        final = {
            "message": {
                "content": json.dumps(
                    {"status": "chart_spec_ready", "chart_spec": {"x": 1}}
                )
            },
            "done": True,
            "model": "gemma",
        }

        def fake_urlopen(req, timeout=None):
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return _FakeUrlopenCtx(io.BytesIO(json.dumps(final).encode("utf-8")))

        with unittest.mock.patch.object(
            model_provider.urllib.request, "urlopen", fake_urlopen
        ):
            result = client.plan_chart({"approved_entity_ids": []})

        self.assertFalse(captured["body"]["stream"])
        # Non-streaming calls must not request thinking tokens (would change
        # the single-read behavior unnecessarily).
        self.assertNotIn("think", captured["body"])
        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["planner_result"]["status"], "chart_spec_ready")

    def test_streaming_request_sets_think_true(self):
        """Streaming plan_chart makes two calls: the first (think pass) must
        carry stream:true + think:true; the second (plan pass) carries format."""
        client = self._client()
        think_chunks = [{"message": {"thinking": "ponder", "content": ""}, "done": True}]
        plan_response = {"message": {"content": json.dumps({"status": "chart_spec_ready", "chart_spec": {"ok": True}}), "role": "assistant"}, "done": True}
        calls: list[dict] = []

        def fake_urlopen(req, timeout=None):
            body = json.loads(req.data.decode("utf-8"))
            calls.append(body)
            if body.get("stream"):
                return _FakeUrlopenCtx(_ndjson_response(think_chunks))
            return _FakeUrlopenCtx(io.BytesIO(json.dumps(plan_response).encode("utf-8")))

        with unittest.mock.patch.object(
            model_provider.urllib.request, "urlopen", fake_urlopen
        ):
            client.plan_chart({"approved_entity_ids": []}, on_reasoning=lambda _t: None)

        self.assertEqual(len(calls), 2)
        # First call is the think pass.
        self.assertTrue(calls[0]["stream"])
        self.assertTrue(calls[0]["think"])
        self.assertNotIn("format", calls[0])
        # Second call is the plan pass.
        self.assertFalse(calls[1]["stream"])
        self.assertNotIn("think", calls[1])
        self.assertIn("format", calls[1])

    def test_streaming_select_entity_request_sets_think_true(self):
        """Streaming select_entity also makes two calls: think pass then select pass."""
        client = self._client()
        think_chunks = [{"message": {"thinking": "pick", "content": ""}, "done": True}]
        select_response = {"message": {"content": json.dumps({"status": "entity_selected", "entity_ids": ["sensor.upstairs_temperature"]}), "role": "assistant"}, "done": True}
        calls: list[dict] = []

        def fake_urlopen(req, timeout=None):
            body = json.loads(req.data.decode("utf-8"))
            calls.append(body)
            if body.get("stream"):
                return _FakeUrlopenCtx(_ndjson_response(think_chunks))
            return _FakeUrlopenCtx(io.BytesIO(json.dumps(select_response).encode("utf-8")))

        with unittest.mock.patch.object(
            model_provider.urllib.request, "urlopen", fake_urlopen
        ):
            client.select_entity(
                {"candidate_entity_ids": ["sensor.upstairs_temperature"]},
                on_reasoning=lambda _t: None,
            )

        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0]["stream"])
        self.assertTrue(calls[0]["think"])
        self.assertNotIn("format", calls[0])
        self.assertFalse(calls[1]["stream"])
        self.assertNotIn("think", calls[1])
        self.assertIn("format", calls[1])

    def test_non_streaming_select_entity_omits_think(self):
        client = self._client()
        captured = {}
        final = {
            "message": {
                "content": json.dumps(
                    {
                        "status": "entity_selected",
                        "entity_ids": ["sensor.upstairs_temperature"],
                    }
                )
            },
            "done": True,
        }

        def fake_urlopen(req, timeout=None):
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return _FakeUrlopenCtx(io.BytesIO(json.dumps(final).encode("utf-8")))

        with unittest.mock.patch.object(
            model_provider.urllib.request, "urlopen", fake_urlopen
        ):
            client.select_entity(
                {"candidate_entity_ids": ["sensor.upstairs_temperature"]}
            )

        self.assertFalse(captured["body"]["stream"])
        self.assertNotIn("think", captured["body"])

    def test_streaming_accumulates_thinking_and_invokes_callback(self):
        """Think pass streams reasoning to callback; plan pass provides valid JSON."""
        client = self._client()
        think_chunks = [
            {"message": {"thinking": "First I read ", "content": ""}, "done": False},
            {"message": {"thinking": "the entities.", "content": ""}, "done": False},
            {"message": {"thinking": "", "content": ""}, "done": True},
        ]
        plan_response = {
            "message": {"content": json.dumps({"status": "chart_spec_ready", "chart_spec": {"ok": True}}), "role": "assistant"},
            "done": True,
        }
        seen: list[str] = []

        def fake_urlopen(req, timeout=None):
            body = json.loads(req.data.decode("utf-8"))
            if body.get("stream"):
                return _FakeUrlopenCtx(_ndjson_response(think_chunks))
            return _FakeUrlopenCtx(io.BytesIO(json.dumps(plan_response).encode("utf-8")))

        with unittest.mock.patch.object(
            model_provider.urllib.request, "urlopen", fake_urlopen
        ):
            result = client.plan_chart(
                {"approved_entity_ids": []}, on_reasoning=seen.append
            )

        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["planner_result"]["status"], "chart_spec_ready")
        # Callback saw accumulated thinking from the think pass, growing each delta.
        self.assertTrue(seen)
        self.assertIn("First I read ", seen[-1])
        self.assertIn("the entities.", seen[-1])
        self.assertGreaterEqual(len(seen[-1]), len(seen[0]))

    def test_streaming_select_entity_also_streams(self):
        """Think pass streams reasoning; select pass provides valid selection JSON."""
        client = self._client()
        think_chunks = [
            {"message": {"thinking": "Pick the ", "content": ""}, "done": False},
            {"message": {"thinking": "best entity.", "content": ""}, "done": True},
        ]
        select_response = {
            "message": {"content": json.dumps({"status": "entity_selected", "entity_ids": ["sensor.upstairs_temperature"]}), "role": "assistant"},
            "done": True,
        }
        seen: list[str] = []

        def fake_urlopen(req, timeout=None):
            body = json.loads(req.data.decode("utf-8"))
            if body.get("stream"):
                return _FakeUrlopenCtx(_ndjson_response(think_chunks))
            return _FakeUrlopenCtx(io.BytesIO(json.dumps(select_response).encode("utf-8")))

        with unittest.mock.patch.object(
            model_provider.urllib.request, "urlopen", fake_urlopen
        ):
            result = client.select_entity(
                {"candidate_entity_ids": ["sensor.upstairs_temperature"]},
                on_reasoning=seen.append,
            )

        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["selection_result"]["status"], "entity_selected")
        self.assertIn("best entity.", seen[-1])

    def test_streaming_non_reasoning_model_never_calls_back(self):
        """A model that emits no thinking in the think pass degrades gracefully (D6)."""
        client = self._client()
        # Think pass: model emits no thinking tokens.
        think_chunks = [{"message": {"content": ""}, "done": True}]
        plan_response = {
            "message": {"content": json.dumps({"status": "chart_spec_ready", "chart_spec": {"ok": True}}), "role": "assistant"},
            "done": True,
        }
        seen: list[str] = []

        def fake_urlopen(req, timeout=None):
            body = json.loads(req.data.decode("utf-8"))
            if body.get("stream"):
                return _FakeUrlopenCtx(_ndjson_response(think_chunks))
            return _FakeUrlopenCtx(io.BytesIO(json.dumps(plan_response).encode("utf-8")))

        with unittest.mock.patch.object(
            model_provider.urllib.request, "urlopen", fake_urlopen
        ):
            result = client.plan_chart(
                {"approved_entity_ids": []}, on_reasoning=seen.append
            )

        self.assertTrue(result["accepted"], result)
        self.assertEqual(seen, [])

    def test_streaming_transport_error_returns_failure(self):
        """Mid-stream transport error falls to the failure path (R4)."""
        client = self._client()

        def fake_urlopen(req, timeout=None):
            raise urllib.error.URLError("connection reset")

        with unittest.mock.patch.object(
            model_provider.urllib.request, "urlopen", fake_urlopen
        ):
            result = client.plan_chart(
                {"approved_entity_ids": []}, on_reasoning=lambda _t: None
            )

        self.assertFalse(result["accepted"], result)
        self.assertEqual(result["code"], "model_provider_connection_error")


class ApplyLiveReasoningTests(unittest.TestCase):
    def _planning_snapshot(self) -> dict:
        return {
            "snapshot_id": "job-001-snapshot-003",
            "job_id": "job-001",
            "status": "planning",
            "prompt": "Show the upstairs temperature",
            "state_label": "Planning",
            "message": "Planning the chart.",
            "progress": {
                "stage": "model_provider_planning",
                "message": "Calling the model provider.",
            },
            "validation": {"status": "in_progress", "summary": "Planning."},
            "warnings": [],
        }

    def test_phase_labels_defined(self):
        self.assertEqual(SELECT_ENTITY_PHASE_LABEL, "Selecting entities…")
        self.assertEqual(PLAN_CHART_PHASE_LABEL, "Planning chart…")

    def test_injects_reasoning_and_stage_and_revalidates(self):
        snapshot = self._planning_snapshot()
        slot = {"stage": PLAN_CHART_PHASE_LABEL, "text": "Reading sensor history."}
        out = apply_live_reasoning(snapshot, slot)

        self.assertEqual(out["progress"]["reasoning"], "Reading sensor history.")
        self.assertEqual(out["progress"]["stage"], PLAN_CHART_PHASE_LABEL)
        self.assertEqual(out["state_label"], PLAN_CHART_PHASE_LABEL)
        # Stays schema-valid.
        self.assertTrue(validate_job_snapshot_contract(out)["accepted"], out)
        # Does not mutate the stored snapshot.
        self.assertNotIn("reasoning", snapshot["progress"])

    def test_no_slot_returns_snapshot_unchanged(self):
        snapshot = self._planning_snapshot()
        out = apply_live_reasoning(snapshot, None)
        self.assertNotIn("reasoning", out["progress"])

    def test_empty_text_omits_reasoning(self):
        snapshot = self._planning_snapshot()
        slot = {"stage": SELECT_ENTITY_PHASE_LABEL, "text": ""}
        out = apply_live_reasoning(snapshot, slot)
        self.assertNotIn("reasoning", out["progress"])
        # Phase label still applied.
        self.assertEqual(out["progress"]["stage"], SELECT_ENTITY_PHASE_LABEL)

    def test_reasoning_is_capped_in_schema(self):
        snapshot = self._planning_snapshot()
        snapshot["progress"]["reasoning"] = "A" * (REASONING_CHAR_CAP + 50)
        result = validate_job_snapshot_contract(snapshot)
        self.assertFalse(result["accepted"], result)

    def test_reasoning_at_cap_is_schema_valid(self):
        snapshot = self._planning_snapshot()
        snapshot["progress"]["reasoning"] = "A" * REASONING_CHAR_CAP
        result = validate_job_snapshot_contract(snapshot)
        self.assertTrue(result["accepted"], result)


class _StreamingFakePlanner(FakePlanner):
    """A FakePlanner that streams thinking via on_reasoning and, mid-call, fires
    a re-entrant snapshot poll so the in-progress branch (which holds the
    planning lock) is observed surfacing the live reasoning slot."""

    def __init__(self, *, hass, entry, reasoning: str, **kwargs):
        super().__init__(**kwargs)
        self._hass = hass
        self._entry = entry
        self._reasoning = reasoning
        self.in_progress_poll = None

    def plan_chart(self, request, *, result_schema=None, on_reasoning=None):
        if on_reasoning is not None:
            on_reasoning(self._reasoning)
            # While we are still "inside" plan_chart the outer poll holds the
            # planning lock; a concurrent poll must hit the in-progress branch.
            job_id = request.get("job_id") or self._job_id
            self.in_progress_poll = _snapshot_job(
                self._hass, self._entry, job_id, message_id=99
            )
        return super().plan_chart(request, result_schema=result_schema)

    _job_id = None


class EndToEndLiveReasoningTests(unittest.TestCase):
    def test_in_progress_poll_surfaces_reasoning_then_png_clears_it(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            # Build the harness with a placeholder, then swap in a streaming
            # planner that can reach back into hass/entry for the re-entrant poll.
            hass, entry = configured_real_slice_hass(
                planner=FakePlanner(), artifact_dir=artifact_dir
            )
            planner = _StreamingFakePlanner(
                hass=hass,
                entry=entry,
                reasoning="Reading sensor.upstairs_temperature history…",
            )
            from custom_components.isolinear.model_provider import (
                DATA_MODEL_PROVIDER_PLANNER,
            )

            hass.data["isolinear"][entry.entry_id][DATA_MODEL_PROVIDER_PLANNER] = planner

            start = _start_job(hass, entry)
            job_id = start["snapshot"]["job_id"]
            planner._job_id = job_id

            snapshot = _snapshot_job(hass, entry, job_id)

            # The terminal snapshot is the rendered chart with no reasoning (D4).
            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "complete")
            self.assertNotIn("reasoning", snapshot["snapshot"].get("progress", {}))

            # The re-entrant in-progress poll fired during plan_chart surfaced
            # the live reasoning tail + the coarse phase (D2/D3/R3).
            in_progress = planner.in_progress_poll
            self.assertIsNotNone(in_progress)
            self.assertTrue(in_progress["accepted"], in_progress)
            in_progress_snapshot = in_progress["snapshot"]
            self.assertEqual(
                in_progress_snapshot["progress"]["reasoning"],
                "Reading sensor.upstairs_temperature history…",
            )
            self.assertEqual(
                in_progress_snapshot["progress"]["stage"], PLAN_CHART_PHASE_LABEL
            )
            self.assertEqual(in_progress_snapshot["state_label"], PLAN_CHART_PHASE_LABEL)

            # Slot cleared once the model phase concluded (D4).
            store = _orchestration_store(hass, entry)
            self.assertIsNone(_live_reasoning_slot(store, job_id))

    def test_non_streaming_planner_shows_no_reasoning(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            # Plain FakePlanner.plan_chart has no on_reasoning kwarg → graceful
            # fallback (D6): no slot is ever written.
            hass, entry = configured_real_slice_hass(
                planner=FakePlanner(), artifact_dir=artifact_dir
            )
            start = _start_job(hass, entry)
            job_id = start["snapshot"]["job_id"]
            snapshot = _snapshot_job(hass, entry, job_id)

            self.assertEqual(snapshot["snapshot"]["status"], "complete")
            self.assertNotIn("reasoning", snapshot["snapshot"].get("progress", {}))
            store = _orchestration_store(hass, entry)
            self.assertIsNone(_live_reasoning_slot(store, job_id))


if __name__ == "__main__":
    unittest.main()
