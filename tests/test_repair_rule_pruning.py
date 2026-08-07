"""Repair prompt rules are pruned to the failure class (2026-08-07).

Root cause, measured with the real tokenizer (scripts/measure_codegen_prompt.py,
LIVE_TOKENS=1, gemma4:e4b): the GENERATION prompt fits _CODEGEN_NUM_CTX (58-79%
across the stable e2e failure cases) but every REPAIR prompt hit
prompt_eval_count == 8192 exactly — silently truncated. Ollama drops LEADING
tokens on overflow, i.e. the system prompt and the rules, so the repair loop
evicted the very contract it was enforcing and the model emitted generic
matplotlib boilerplate with fabricated data (np.random.seed(42), mock arrays —
the stable 7-failure signature of both 2026-07-31 e2e runs; no repair spiral
ever recovered).

The fix (`_repair_prompt_rules`): repair sends the contract-critical core plus
only the rule families relevant to the failure class — static violations get
core only, runtime errors add the analysis-plumbing rules (+ precomputed-bands
rules when the request carries derived_intervals), grounding synthetic errors
add the emission/claims block. Generation is untouched. Selection is by marker
substring against the live module list so eval arms that monkeypatch
_CODEGEN_PROMPT_RULES flow through; an unmatched (fully replaced) list fails
open to everything.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from custom_components.isolinear import model_provider  # noqa: E402
from custom_components.isolinear.model_provider import (  # noqa: E402
    OllamaCompatiblePlannerClient,
)

STATIC_ERROR = {"code": "unsafe_code", "message": "static gate", "traceback": None}
RUNTIME_ERROR = {"code": "runtime_error", "message": "boom", "traceback": "Traceback ..."}
GROUNDING_ERROR = {
    "code": "grounding_verdict_unbacked",
    "message": "verdict not backed by a claim",
    "traceback": None,
}

BARE_REQUEST = {"chart_spec": {}, "history_series": []}
BANDS_REQUEST = {
    "chart_spec": {},
    "history_series": [],
    "derived_intervals": [{"start_ms": 0, "end_ms": 1, "color": "#abc", "label": "cool"}],
}

# Marker text unique to representative members of each family.
ENTRY_POINT = "Define exactly one top-level function"
IMPORTS = "Import nothing"
ALIGN = "isolinear_analysis.align is the only"
FAMILY = "Render only these chart families"
OVERLAY_BANDS = "precomputed shaded background bands"
TIMELINE = "TIMELINE step track"
CLAIMS = "return a 'claims' list"
CORRELATION = "IMPORTANT for correlation questions"
LEGEND = "Do NOT call ax.legend()"  # cosmetic — never in a repair prompt


def _rules_for(error: dict, request: dict) -> list[str]:
    return model_provider._repair_prompt_rules(error, request)


def _has(rules: list[str], marker: str) -> bool:
    return any(marker in rule for rule in rules)


class RepairRulePruningTests(unittest.TestCase):
    def test_static_class_gets_core_only(self) -> None:
        rules = _rules_for(STATIC_ERROR, BARE_REQUEST)
        self.assertTrue(_has(rules, ENTRY_POINT))
        self.assertTrue(_has(rules, IMPORTS))
        self.assertFalse(_has(rules, ALIGN))
        self.assertFalse(_has(rules, CLAIMS))
        self.assertFalse(_has(rules, CORRELATION))
        self.assertFalse(_has(rules, LEGEND))

    def test_runtime_class_adds_analysis_plumbing(self) -> None:
        rules = _rules_for(RUNTIME_ERROR, BARE_REQUEST)
        self.assertTrue(_has(rules, ENTRY_POINT))
        self.assertTrue(_has(rules, ALIGN))
        self.assertTrue(_has(rules, FAMILY))
        self.assertFalse(_has(rules, CLAIMS))
        self.assertFalse(_has(rules, OVERLAY_BANDS))

    def test_runtime_with_derived_intervals_adds_band_rules(self) -> None:
        rules = _rules_for(RUNTIME_ERROR, BANDS_REQUEST)
        self.assertTrue(_has(rules, OVERLAY_BANDS))
        self.assertTrue(_has(rules, TIMELINE))

    def test_grounding_class_adds_the_emission_block(self) -> None:
        rules = _rules_for(GROUNDING_ERROR, BARE_REQUEST)
        self.assertTrue(_has(rules, ALIGN))
        self.assertTrue(_has(rules, CLAIMS))
        self.assertTrue(_has(rules, CORRELATION))
        self.assertFalse(_has(rules, LEGEND))

    def test_pruned_static_rules_are_a_fraction_of_the_full_list(self) -> None:
        # The budget claim itself: a static-class repair must send well under
        # half the full rules text, or the truncation this fixes comes back.
        full = sum(len(r) for r in model_provider._CODEGEN_PROMPT_RULES)
        pruned = sum(len(r) for r in _rules_for(STATIC_ERROR, BARE_REQUEST))
        self.assertLess(pruned, full * 0.4)

    def test_selection_preserves_module_list_order(self) -> None:
        rules = _rules_for(GROUNDING_ERROR, BANDS_REQUEST)
        positions = [model_provider._CODEGEN_PROMPT_RULES.index(r) for r in rules]
        self.assertEqual(positions, sorted(positions))

    def test_unmatched_replacement_list_fails_open(self) -> None:
        original = model_provider._CODEGEN_PROMPT_RULES
        model_provider._CODEGEN_PROMPT_RULES = ["custom rule A", "custom rule B"]
        try:
            rules = _rules_for(STATIC_ERROR, BARE_REQUEST)
            self.assertEqual(rules, ["custom rule A", "custom rule B"])
        finally:
            model_provider._CODEGEN_PROMPT_RULES = original

    def test_monkeypatched_arm_flows_through_the_filter(self) -> None:
        # Eval arms drop a rule by rebinding the module list (the emission
        # gate's without-arm); the filter must respect the live list.
        original = model_provider._CODEGEN_PROMPT_RULES
        model_provider._CODEGEN_PROMPT_RULES = [
            r for r in original if CORRELATION not in r
        ]
        try:
            rules = _rules_for(GROUNDING_ERROR, BARE_REQUEST)
            self.assertFalse(_has(rules, CORRELATION))
            self.assertTrue(_has(rules, CLAIMS))
        finally:
            model_provider._CODEGEN_PROMPT_RULES = original


class RepairPayloadIntegrationTests(unittest.TestCase):
    def _client(self) -> OllamaCompatiblePlannerClient:
        return OllamaCompatiblePlannerClient(
            endpoint_url="http://ollama.invalid:11434",
            planner_model="gemma4:e4b",
            timeout_seconds=1,
        )

    def test_repair_payload_rules_are_pruned(self) -> None:
        payload = self._client()._codegen_repair_payload(
            "def render_chart(data, output_path):\n    return {}",
            STATIC_ERROR,
            BARE_REQUEST,
            model=None,
        )
        parsed = json.loads(payload["messages"][1]["content"])
        self.assertLess(len(parsed["rules"]), len(model_provider._CODEGEN_PROMPT_RULES))
        self.assertTrue(_has(parsed["rules"], ENTRY_POINT))
        self.assertFalse(_has(parsed["rules"], CLAIMS))
        # And the task now pins the change to the error instead of a rewrite.
        self.assertIn("keep everything in previous_code", parsed["task"].lower())

    def test_generation_payload_still_sends_the_full_list(self) -> None:
        payload = self._client()._codegen_payload(BARE_REQUEST, model=None)
        parsed = json.loads(payload["messages"][1]["content"])
        self.assertEqual(parsed["rules"], model_provider._CODEGEN_PROMPT_RULES)


if __name__ == "__main__":
    unittest.main()
