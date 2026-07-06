#!/usr/bin/env python3
"""Reproduce e2e-14 (cross-metric correlation) against live gemma4:e4b.

Isolates the planner from entity resolution: runs the SAME prompt with two
disclosure hypotheses and prints what the planner does. If disclosing both
sensors plans a chart, the live failure was a RESOLUTION gap (only one sensor
resolved); if it still declines, it's a PLANNER capability gap.
"""
from repro_planner import run  # same dir on sys.path when run from scripts/

PROMPT = "Is the kitchen temperature correlated with the kitchen humidity over the last 2 days?"

if __name__ == "__main__":
    # Hypothesis A: both sensors disclosed (what resolution SHOULD produce).
    run(
        {"name": "E2E14 both-disclosed (temp+humidity)", "prompt": PROMPT},
        family="time_series",
        families=["time_series"],
        approved=["sensor.kitchen_ecobee_temperature", "sensor.kitchen_ecobee_humidity"],
        overlay=[],
    )
    # Hypothesis B: only the temperature sensor disclosed (a resolution miss on
    # "kitchen humidity" -> friendly name "Kitchen ecobee Humidity").
    run(
        {"name": "E2E14 temp-only", "prompt": PROMPT},
        family="time_series",
        families=["time_series"],
        approved=["sensor.kitchen_ecobee_temperature"],
        overlay=[],
    )
