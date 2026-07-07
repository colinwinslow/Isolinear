#!/usr/bin/env python3
"""Probe the PROPOSED planner routing fix for heatmap prompts (open-queue (w)).

Baseline (repro_e2e15_planner.py): the ADR-0023 multi-family chart_type_rule
glosses histogram as "for value distributions" and the planner deterministically
(6/6) routes "heatmap by hour of day and day" to chart_type=histogram — whose
spec then fights user_request inside codegen (the e2e-15 garbage).

This probe patches ONLY the chart_type_rule sentence in the outgoing payload
(monkeypatched _chat_payload, no production change) to add the proposed
heatmap→time_series routing clause, and reports what the planner picks.
"""
import json
import os
import sys

sys.path.insert(0, "custom_components")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from isolinear import model_provider as mp  # noqa: E402
from repro_planner import run  # noqa: E402

PROMPT = "Show a heatmap of the kitchen temperature by hour of day and day over the last week"
N = int(os.environ.get("RUNS", "3"))

ADDITION = (
    " A heatmap or matrix request (e.g. 'by hour of day and day') is a TIME-based "
    "analysis, NOT a value distribution: choose time_series for it (downstream "
    "generated code pivots the series and draws the heatmap)."
)

_orig = mp.OllamaCompatiblePlannerClient._chat_payload


def _patched(self, request, result_schema, *, stream=False):
    payload = _orig(self, request, result_schema, stream=stream)
    for msg in payload.get("messages", []):
        if "Choose chart_type from" in str(msg.get("content", "")):
            content = json.loads(msg["content"]) if msg["content"].startswith("{") else None
            if content and isinstance(content.get("rules"), list):
                content["rules"] = [
                    r + ADDITION if isinstance(r, str) and "Choose chart_type from" in r else r
                    for r in content["rules"]
                ]
                msg["content"] = json.dumps(content)
    return payload


mp.OllamaCompatiblePlannerClient._chat_payload = _patched

if __name__ == "__main__":
    for i in range(1, N + 1):
        run(
            {"name": f"E2E15 heatmap prompt, PATCHED routing rule (run {i})", "prompt": PROMPT},
            family="time_series",
            families=["time_series", "histogram", "aggregate_bar"],
            approved=["sensor.kitchen_ecobee_temperature"],
            overlay=[],
        )
