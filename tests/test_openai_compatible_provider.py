"""Unit tests for the OpenAI-compatible (LiteLLM) model provider — ADR-0037.

Covers the transport that differs from the Ollama client: OpenAI-shaped
payloads (`response_format` json_schema, `reasoning_effort`), the SSE stream
consumer (`delta.reasoning_content` → `on_reasoning`, `delta.content` →
assembled message, D6 fallback), optional bearer auth, the client factory, and
that the default provider is now the OpenAI-compatible proxy.

Live end-to-end proof (health + structured plan with 674 reasoning callbacks +
codegen) was captured against the real proxy at build time; these tests pin the
transport contract without the network.
"""
import io
import json
import sys
import unittest
import unittest.mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from custom_components.isolinear import model_provider  # noqa: E402
from custom_components.isolinear.model_provider import (  # noqa: E402
    DEFAULT_OPENAI_REASONING_EFFORT,
    OllamaCompatiblePlannerClient,
    OpenAICompatiblePlannerClient,
    _build_planner_client,
    _has_planner_config,
)
from custom_components.isolinear.config_schema import default_config_data  # noqa: E402
from custom_components.isolinear.const import (  # noqa: E402
    MODEL_PROVIDER_OLLAMA_COMPATIBLE,
    MODEL_PROVIDER_OPENAI_COMPATIBLE,
    SUPPORTED_MODEL_PROVIDER_TYPES,
)


class _Ctx:
    def __init__(self, fp):
        self._fp = fp

    def __enter__(self):
        return self._fp

    def __exit__(self, *exc):
        return False


def _sse(*chunks: dict) -> io.BytesIO:
    """Build an SSE body: one `data: {json}` line per chunk, then `[DONE]`."""
    lines = [f"data: {json.dumps(c)}" for c in chunks] + ["data: [DONE]"]
    return io.BytesIO(("\n".join(lines) + "\n").encode("utf-8"))


def _json_body(payload: dict) -> io.BytesIO:
    return io.BytesIO(json.dumps(payload).encode("utf-8"))


def _delta(*, reasoning: str | None = None, content: str | None = None) -> dict:
    d = {}
    if reasoning is not None:
        d["reasoning_content"] = reasoning
    if content is not None:
        d["content"] = content
    return {"choices": [{"delta": d}]}


def _client(api_key=None):
    return OpenAICompatiblePlannerClient(
        endpoint_url="http://10.0.1.39:4000/v1", planner_model="ollama/gemma", api_key=api_key
    )


class ProviderShapeTests(unittest.TestCase):
    def test_provider_type_and_url_and_metadata(self):
        c = _client()
        self.assertEqual(c.provider_type, MODEL_PROVIDER_OPENAI_COMPATIBLE)
        self.assertEqual(c._chat_completions_url(), "http://10.0.1.39:4000/v1/chat/completions")
        self.assertEqual(c.provider_metadata()["type"], MODEL_PROVIDER_OPENAI_COMPATIBLE)

    def test_structured_body_streaming_carries_schema_and_reasoning(self):
        c = _client()
        body = c._structured_body([{"role": "user", "content": "x"}], {"type": "object"}, stream=True, temperature=None)
        self.assertEqual(body["response_format"]["type"], "json_schema")
        self.assertEqual(body["response_format"]["json_schema"]["schema"], {"type": "object"})
        self.assertTrue(body["stream"])
        self.assertEqual(body["reasoning_effort"], DEFAULT_OPENAI_REASONING_EFFORT)
        self.assertEqual(body["temperature"], 0)

    def test_structured_body_non_streaming_omits_reasoning(self):
        c = _client()
        body = c._structured_body([], {"type": "object"}, stream=False, temperature=0.7)
        self.assertFalse(body["stream"])
        self.assertNotIn("reasoning_effort", body)
        self.assertEqual(body["temperature"], 0.7)


class SseConsumerTests(unittest.TestCase):
    def test_accumulates_reasoning_and_content_and_fires_callback(self):
        c = _client()
        hits = []
        body = _sse(
            _delta(reasoning="Think"),
            _delta(reasoning="ing…"),
            _delta(content='{"status":'),
            _delta(content='"ok"}'),
        )
        content, last = c._consume_sse(body, hits.append)
        self.assertEqual(content, '{"status":"ok"}')
        # One callback per reasoning-bearing delta, each the accumulated trace.
        self.assertEqual(len(hits), 2)
        self.assertTrue(hits[-1].endswith("Thinking…"))

    def test_no_reasoning_means_no_callback_d6_fallback(self):
        c = _client()
        hits = []
        content, _ = c._consume_sse(_sse(_delta(content="only content")), hits.append)
        self.assertEqual(content, "only content")
        self.assertEqual(hits, [])

    def test_ignores_malformed_and_blank_lines(self):
        c = _client()
        raw = io.BytesIO(b"\n: comment\ndata: not-json\ndata: " + json.dumps(_delta(content="hi")).encode() + b"\ndata: [DONE]\n")
        content, _ = c._consume_sse(raw, None)
        self.assertEqual(content, "hi")


class TransportTests(unittest.TestCase):
    def test_non_streaming_reads_choices_message_content(self):
        c = _client()
        payload = {"choices": [{"message": {"content": '{"status":"chart_spec_ready"}'}}], "model": "ollama/gemma"}
        with unittest.mock.patch.object(model_provider.urllib.request, "urlopen", return_value=_Ctx(_json_body(payload))):
            content, resp, failure = c._read_openai_chat({"stream": False}, label="t", on_reasoning=None)
        self.assertIsNone(failure)
        self.assertEqual(content, '{"status":"chart_spec_ready"}')

    def test_auth_header_present_only_with_key(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["headers"] = {k.lower(): v for k, v in req.header_items()}
            return _Ctx(_json_body({"choices": [{"message": {"content": "{}"}}]}))

        with unittest.mock.patch.object(model_provider.urllib.request, "urlopen", side_effect=fake_urlopen):
            _client(api_key="secret-key-123")._read_openai_chat({"stream": False}, label="t", on_reasoning=None)
        self.assertEqual(captured["headers"].get("authorization"), "Bearer secret-key-123")

        with unittest.mock.patch.object(model_provider.urllib.request, "urlopen", side_effect=fake_urlopen):
            _client(api_key=None)._read_openai_chat({"stream": False}, label="t", on_reasoning=None)
        self.assertNotIn("authorization", captured["headers"])

    def test_http_error_maps_to_provider_failure(self):
        import urllib.error

        c = _client()
        err = urllib.error.HTTPError("http://x", 500, "boom", {}, None)
        with unittest.mock.patch.object(model_provider.urllib.request, "urlopen", side_effect=err):
            content, resp, failure = c._read_openai_chat({"stream": False}, label="t", on_reasoning=None)
        self.assertIsNone(content)
        self.assertFalse(failure["accepted"])
        self.assertEqual(failure["code"], "model_provider_http_error")


class PlanChartTests(unittest.TestCase):
    def test_streaming_plan_returns_planner_result_and_streams_reasoning(self):
        c = _client()
        hits = []
        body = _sse(_delta(reasoning="pondering"), _delta(content=json.dumps({"status": "chart_spec_ready", "chart_spec": {}})))
        with unittest.mock.patch.object(model_provider.urllib.request, "urlopen", return_value=_Ctx(body)):
            result = c.plan_chart({"prompt": "p", "approved_entity_ids": []}, on_reasoning=hits.append)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["planner_result"]["status"], "chart_spec_ready")
        self.assertEqual(hits, ["pondering"])

    def test_non_json_content_is_failure(self):
        c = _client()
        payload = {"choices": [{"message": {"content": "not json at all"}}]}
        with unittest.mock.patch.object(model_provider.urllib.request, "urlopen", return_value=_Ctx(_json_body(payload))):
            result = c.plan_chart({"prompt": "p", "approved_entity_ids": []})
        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "model_provider_non_json_response")

    def test_empty_content_is_retry_safe_failure(self):
        c = _client()
        payload = {"choices": [{"message": {"content": "   "}}]}
        with unittest.mock.patch.object(model_provider.urllib.request, "urlopen", return_value=_Ctx(_json_body(payload))):
            result = c.plan_chart({"prompt": "p", "approved_entity_ids": []})
        self.assertEqual(result["code"], "model_provider_empty_response")
        self.assertTrue(result["retry_safe"])


class CodegenTests(unittest.TestCase):
    REQ = {
        "chart_spec": {"title": "t", "chart_type": "time_series", "render_as": "line", "series": []},
        "history_series": [{"entity_id": "sensor.x", "kind": "numeric", "points": [{"ts_epoch_ms": 0, "value": 1.0}]}],
    }

    def test_generate_extracts_python(self):
        c = _client()
        code = "```python\ndef render_chart(data, output_path):\n    pass\n```"
        payload = {"choices": [{"message": {"content": code}}]}
        with unittest.mock.patch.object(model_provider.urllib.request, "urlopen", return_value=_Ctx(_json_body(payload))):
            result = c.generate_chart_code(self.REQ, user_request="show x")
        self.assertTrue(result["accepted"])
        self.assertEqual(result["code"], "model_provider_chart_code_received")
        self.assertIn("def render_chart", result["python_code"])
        self.assertEqual(result["provider"]["role"], "codegen")

    def test_repair_extracts_python(self):
        c = _client()
        payload = {"choices": [{"message": {"content": "```python\ndef render_chart(d,o):\n    return {}\n```"}}]}
        with unittest.mock.patch.object(model_provider.urllib.request, "urlopen", return_value=_Ctx(_json_body(payload))):
            result = c.repair_chart_code("old", {"code": "syntax_error"}, self.REQ)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["code"], "model_provider_chart_code_repaired")


class HealthTests(unittest.TestCase):
    def test_ready_when_planner_model_listed(self):
        c = _client()
        payload = {"data": [{"id": "ollama/gemma"}, {"id": "ollama/qwen-coder"}]}
        with unittest.mock.patch.object(model_provider.urllib.request, "urlopen", return_value=_Ctx(_json_body(payload))):
            h = c.check_health({})
        self.assertTrue(h["accepted"])
        self.assertEqual(h["health_result"]["status"], "ready")
        self.assertEqual(h["provider_response"]["model_count"], 2)

    def test_not_ready_when_model_absent(self):
        c = _client()
        with unittest.mock.patch.object(model_provider.urllib.request, "urlopen", return_value=_Ctx(_json_body({"data": [{"id": "other"}]}))):
            h = c.check_health({})
        self.assertEqual(h["health_result"]["status"], "not_ready")


class FactoryAndConfigTests(unittest.TestCase):
    def test_factory_selects_openai_client(self):
        cfg = {"model_provider_type": MODEL_PROVIDER_OPENAI_COMPATIBLE, "model_endpoint_url": "http://x/v1", "planner_model": "ollama/gemma"}
        client = _build_planner_client(cfg, {})
        self.assertIsInstance(client, OpenAICompatiblePlannerClient)
        self.assertIsNone(client.api_key)

    def test_factory_selects_ollama_client(self):
        cfg = {"model_provider_type": MODEL_PROVIDER_OLLAMA_COMPATIBLE, "model_endpoint_url": "http://x", "planner_model": "llama3.1"}
        client = _build_planner_client(cfg, {})
        self.assertIsInstance(client, OllamaCompatiblePlannerClient)
        self.assertNotIsInstance(client, OpenAICompatiblePlannerClient)

    def test_factory_threads_timeout(self):
        cfg = {"model_provider_type": MODEL_PROVIDER_OPENAI_COMPATIBLE, "model_endpoint_url": "http://x/v1", "planner_model": "ollama/gemma"}
        client = _build_planner_client(cfg, {"ollama_timeout_seconds": 240})
        self.assertEqual(client.timeout_seconds, 240)

    def test_default_provider_is_openai_compatible(self):
        cfg = default_config_data()
        self.assertEqual(cfg["model_provider_type"], MODEL_PROVIDER_OPENAI_COMPATIBLE)
        self.assertEqual(cfg["planner_model"], "ollama/gemma")
        self.assertTrue(cfg["model_endpoint_url"].endswith("/v1"))

    def test_has_planner_config_accepts_both_types(self):
        self.assertTrue(_has_planner_config({"model_provider_type": MODEL_PROVIDER_OPENAI_COMPATIBLE, "model_endpoint_url": "http://x/v1", "planner_model": "ollama/gemma"}))
        self.assertTrue(_has_planner_config({"model_provider_type": MODEL_PROVIDER_OLLAMA_COMPATIBLE, "model_endpoint_url": "http://x", "planner_model": "llama3.1"}))
        self.assertFalse(_has_planner_config({"model_provider_type": "bogus", "model_endpoint_url": "http://x", "planner_model": "m"}))

    def test_both_types_supported(self):
        self.assertIn(MODEL_PROVIDER_OPENAI_COMPATIBLE, SUPPORTED_MODEL_PROVIDER_TYPES)
        self.assertIn(MODEL_PROVIDER_OLLAMA_COMPATIBLE, SUPPORTED_MODEL_PROVIDER_TYPES)


class ProviderTypeSchemaRegressionTests(unittest.TestCase):
    """Live bug (2026-07-16): the plan/health/retry-policy JSON Schemas hardcoded
    ``provider.type`` to the const ``"ollama_compatible"``, a leftover from before
    ADR-0037 added a second provider. Since 0.2.38 made ``openai_compatible`` the
    DEFAULT, every schema-validated provider record produced by the new client was
    rejected — surfaced live as ``invalid_integration_model_provider_retry_policy``
    the first time a request failed (proxy auth re-enabled, no key configured yet).
    These pin the fix: both provider types validate; the health_path metadata
    correctly reflects each provider's real health endpoint.
    """

    def test_plan_schema_accepts_openai_compatible_provider_type(self):
        """Targets the exact defect: the bundled schema's `provider.type` const,
        checked directly (bypassing the nested PlannerResult/ChartSpec cascade in
        ``validate_model_provider_plan_contract``, which is unrelated to this bug).
        """
        from custom_components.isolinear._paths import load_schema_document
        from custom_components.isolinear.job_state import _validate_json_schema
        from custom_components.isolinear.orchestration_contracts import (
            MODEL_PROVIDER_PLAN_SCHEMA_PATH,
        )

        plan = {
            "provider_plan_id": "entry-provider-plan-001",
            "config_entry_id": "entry",
            "job_id": "entry-job-001",
            "source_snapshot_id": "entry-snapshot-001",
            "provider": {
                "type": MODEL_PROVIDER_OPENAI_COMPATIBLE,
                "role": "planner",
                "endpoint_url": "http://10.0.1.39:4000/v1",
                "model": "ollama/gemma",
            },
            "request": {
                "prompt": "kitchen temperature",
                "approved_entity_ids": ["sensor.kitchen_temperature"],
                "history_entity_ids": ["sensor.kitchen_temperature"],
                "now": "2026-07-16T00:00:00+00:00",
                "time_zone": "UTC",
                "output_schema": "PlannerResult",
            },
            "status": "chart_spec_ready",
            "planner_result": {"status": "chart_spec_ready"},
            "chart_spec": {},
            "validation": {
                "status": "pass",
                "summary": "ok",
                "checks": [],
            },
            "warnings": [],
        }
        schema = load_schema_document(MODEL_PROVIDER_PLAN_SCHEMA_PATH)
        # No exception raised == the top-level schema (incl. provider.type) accepts it.
        _validate_json_schema(plan, schema, root_schema=schema, path="$")

    def test_retry_policy_contract_accepts_openai_compatible_provider(self):
        from custom_components.isolinear.orchestration_contracts import (
            validate_model_provider_retry_policy_contract,
        )

        policy = {
            "policy_id": "entry-model-provider-retry-policy-001",
            "type": "isolinear_model_provider_retry_policy",
            "config_entry_id": "entry",
            "job_id": "entry-job-001",
            "source_snapshot_id": "entry-snapshot-001",
            "provider": {
                "type": MODEL_PROVIDER_OPENAI_COMPATIBLE,
                "role": "planner",
                "endpoint_url": "http://10.0.1.39:4000/v1",
                "model": "ollama/gemma",
            },
            "request": {
                "prompt": "kitchen temperature",
                "approved_entity_ids": ["sensor.kitchen_temperature"],
                "history_entity_ids": ["sensor.kitchen_temperature"],
                "now": "2026-07-16T00:00:00+00:00",
                "time_zone": "UTC",
                "output_schema": "PlannerResult",
            },
            "failure": {
                "stage": "model_provider_planning",
                "code": "model_provider_http_error",
                "message": "HTTP Error 401: Unauthorized",
                "retry_safe": True,
            },
            "decision": {
                "eligible": True,
                "reason": "model_provider_failure_retry_safe",
                "manual_retry_allowed": True,
                "automatic_retry_scheduled": False,
            },
            "backoff": {
                "strategy": "bounded_exponential_scaffold",
                "attempt_number": 1,
                "delay_seconds": 5,
                "max_delay_seconds": 60,
                "jitter_applied": False,
            },
            "validation": {
                "status": "pass",
                "summary": "ok",
                "checks": [],
            },
            "warnings": [],
        }
        result = validate_model_provider_retry_policy_contract(policy)
        self.assertTrue(result["accepted"], result)

    def test_health_contract_accepts_openai_compatible_provider_and_models_path(self):
        from custom_components.isolinear.model_provider_health import (
            validate_model_provider_health_contract,
        )

        health = {
            "health_id": "entry-model-provider-health-001",
            "type": "isolinear_model_provider_health",
            "config_entry_id": "entry",
            "status": "ready",
            "code": "model_provider_health_ready",
            "provider": {
                "type": MODEL_PROVIDER_OPENAI_COMPATIBLE,
                "role": "planner",
                "endpoint_url": "http://10.0.1.39:4000/v1",
                "model": "ollama/gemma",
                "health_path": "/models",
            },
            "request": {
                "protocol_version": 1,
                "method": "GET",
                "path": "/api/tags",
                "headers": {"accept": "application/json"},
            },
            "response": {
                "accepted": True,
                "status": "ready",
                "code": "model_provider_health_ready",
                "message": "Configured planner model is available.",
                "checks": [],
                "capabilities": {"planning": True, "structured_output": True},
            },
            "validation": {
                "status": "pass",
                "summary": "ok",
                "checks": [],
            },
            "warnings": [],
            "orchestration": {
                "model_provider_health_check_called": True,
                "model_provider_health_bookkeeping_written": True,
                "model_provider_health_request_validated": True,
                "model_provider_health_response_validated": True,
                "model_provider_planning_called": False,
                "model_provider_retry_policy_written": False,
                "worker_called": False,
                "worker_health_check_called": False,
                "home_assistant_history_read": False,
                "semantic_memory_called": False,
                "home_assistant_service_or_state_mutation_called": False,
                "token_generated": False,
                "token_rotation_called": False,
                "chart_rendering_called": False,
                "chart_artifact_written": False,
                "durable_storage_written": False,
                "durable_retry_storage_written": False,
                "retry_behavior_called": False,
                "scheduler_called": False,
                "automatic_retry_called": False,
                "automatic_progress_task_called": False,
                "new_provider_transport_added": False,
                "provider_details_leaked_to_card": False,
            },
        }
        result = validate_model_provider_health_contract(health)
        self.assertTrue(result["accepted"], result)

    def test_provider_health_metadata_openai_uses_models_path(self):
        from custom_components.isolinear.model_provider_health import (
            _provider_health_metadata,
        )

        client = _client()
        metadata = _provider_health_metadata(client)
        self.assertEqual(metadata["type"], MODEL_PROVIDER_OPENAI_COMPATIBLE)
        self.assertEqual(metadata["health_path"], "/models")

    def test_provider_health_metadata_ollama_uses_tags_path(self):
        from custom_components.isolinear.model_provider_health import (
            _provider_health_metadata,
        )

        client = OllamaCompatiblePlannerClient(
            endpoint_url="http://10.0.1.39:11434", planner_model="llama3.1"
        )
        metadata = _provider_health_metadata(client)
        self.assertEqual(metadata["type"], MODEL_PROVIDER_OLLAMA_COMPATIBLE)
        self.assertEqual(metadata["health_path"], "/api/tags")

    def test_check_model_provider_health_end_to_end_openai_compatible(self):
        """Full check_model_provider_health() flow with a real OpenAI-compatible
        client — the exact path Colin's live health probe runs, proving the
        schema fix closes the gap all the way through, not just at the unit
        level."""
        from custom_components.isolinear.const import DOMAIN
        from custom_components.isolinear.model_provider_health import (
            check_model_provider_health,
        )

        class FakeHass:
            def __init__(self):
                self.data = {DOMAIN: {"entry": {"entry": object()}}}

        hass = FakeHass()
        client = _client()
        hass.data[DOMAIN]["entry"]["model_provider_planner"] = client

        payload = {"data": [{"id": "ollama/gemma"}]}
        with unittest.mock.patch.object(
            model_provider.urllib.request, "urlopen", return_value=_Ctx(_json_body(payload))
        ):
            result = check_model_provider_health(hass, "entry")

        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["health"]["provider"]["type"], MODEL_PROVIDER_OPENAI_COMPATIBLE)
        self.assertEqual(result["health"]["provider"]["health_path"], "/models")


if __name__ == "__main__":
    unittest.main()
