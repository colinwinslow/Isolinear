#!/usr/bin/env python3
"""Reliability sweep: run each planner prompt N times per model, tally statuses.

Confirms whether the live not_chart_spec_ready failures are deterministic bugs
or model-reliability flakiness (item (j)). Uses the real allowlist entity IDs.
"""
import json
import sys
import urllib.request
from collections import Counter

sys.path.insert(0, "custom_components")
from isolinear.model_provider import (
    OllamaCompatiblePlannerClient as OllamaPlanner,
    load_planner_result_schema,
)

ENDPOINT = "http://10.0.1.39:11434"
NOW = "2026-06-26T12:00:00-04:00"
TZ = "America/New_York"
N = 6

CASES = [
    {
        "name": "TEMP+AC OVERLAY",
        "prompt": "show kitchen temp and when the AC was running",
        "family": "time_series",
        "families": ["time_series"],
        "approved": ["sensor.kitchen_ecobee_temperature"],
        "overlay": ["climate.kitchen_ecobee"],
    },
    {
        "name": "KITCHEN DOOR TIMELINE",
        "prompt": "when was the kitchen door open today",
        "family": "timeline",
        "families": ["timeline"],
        "approved": ["binary_sensor.kitchen_door"],
        "overlay": [],
    },
]


def call(model, case):
    planner = OllamaPlanner(endpoint_url=ENDPOINT, planner_model=model)
    schema = load_planner_result_schema(case["family"], envelope=case["families"], entity_ids=case["approved"])
    request = {
        "prompt": case["prompt"],
        "approved_entity_ids": case["approved"],
        "history_entity_ids": case["approved"],
        "now": NOW,
        "time_zone": TZ,
        "output_schema": "PlannerResult",
    }
    if case["overlay"]:
        request["overlay_entity_ids"] = case["overlay"]
    payload = planner._chat_payload(request, schema, stream=False)
    body = json.dumps(payload).encode()
    req = urllib.request.Request(f"{ENDPOINT}/api/chat", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    content = data.get("message", {}).get("content", "")
    try:
        parsed = json.loads(content)
        status = parsed.get("status", "?")
        # also flag duplicate-entity contract risk for chart_spec_ready
        if status == "chart_spec_ready":
            ids = [s.get("source", {}).get("entity_id") for s in parsed.get("chart_spec", {}).get("series", [])]
            if len(ids) != len(set(ids)):
                status = "chart_spec_ready(DUP_SERIES)"
        return status
    except json.JSONDecodeError:
        return "NON_JSON"


def main():
    models = sys.argv[1:] or ["gemma4:e4b"]
    for model in models:
        print(f"\n######## MODEL: {model} ########")
        for case in CASES:
            tally = Counter()
            for _ in range(N):
                try:
                    tally[call(model, case)] += 1
                except Exception as exc:  # noqa: BLE001
                    tally[f"ERROR:{type(exc).__name__}"] += 1
            print(f"  {case['name']:24} {dict(tally)}")


if __name__ == "__main__":
    main()
