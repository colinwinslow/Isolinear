#!/usr/bin/env python3
"""Reproduce the two live planner failures against the real gemma4:e4b endpoint.

Builds the exact Pass-2 (format-constrained) payload the integration sends, posts
it to Ollama, and prints the raw status the model returned. Lets us see *why*
the planner returns not-chart_spec_ready without DEBUG log access.
"""
import json
import sys
import urllib.request

sys.path.insert(0, "custom_components")
from isolinear.model_provider import (
    OllamaCompatiblePlannerClient as OllamaPlanner,
    load_planner_result_schema,
)

ENDPOINT = "http://10.0.1.39:11434"
NOW = "2026-06-26T12:00:00-04:00"
TZ = "America/New_York"


def run(label, family, families, approved, overlay):
    planner = OllamaPlanner(endpoint_url=ENDPOINT, planner_model="gemma4:e4b")
    schema = load_planner_result_schema(family, envelope=families, entity_ids=approved)
    request = {
        "prompt": label["prompt"],
        "approved_entity_ids": approved,
        "history_entity_ids": approved,
        "now": NOW,
        "time_zone": TZ,
        "output_schema": "PlannerResult",
    }
    if overlay:
        request["overlay_entity_ids"] = overlay
    payload = planner._chat_payload(request, schema, stream=False)
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{ENDPOINT}/api/chat", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    content = data.get("message", {}).get("content", "")
    print(f"\n===== {label['name']} ({family}) =====")
    print(f"prompt: {label['prompt']!r}")
    print(f"approved_entity_ids: {approved}")
    print(f"overlay_entity_ids: {overlay}")
    try:
        parsed = json.loads(content)
        print(f"--> status: {parsed.get('status')!r}")
        if parsed.get("status") != "chart_spec_ready":
            print(f"    clarification_question: {parsed.get('clarification_question')!r}")
        print(json.dumps(parsed, indent=2)[:1400])
    except json.JSONDecodeError:
        print(f"RAW (non-JSON): {content[:1400]}")


if __name__ == "__main__":
    # Case 1: temp + AC overlay (A1) — numeric primary disclosed, AC in overlay only.
    run(
        {"name": "TEMP+AC OVERLAY", "prompt": "show kitchen temp and when the AC was running"},
        family="time_series",
        families=["time_series"],
        approved=["sensor.kitchen_ecobee_temperature"],
        overlay=["climate.kitchen_ecobee"],
    )
    # Case 2: kitchen door pure-binary timeline (G12).
    run(
        {"name": "KITCHEN DOOR TIMELINE", "prompt": "when was the kitchen door open today"},
        family="timeline",
        families=["timeline"],
        approved=["binary_sensor.kitchen_door"],
        overlay=[],
    )
