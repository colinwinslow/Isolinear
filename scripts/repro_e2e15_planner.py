#!/usr/bin/env python3
"""Reproduce the e2e-15 heatmap PLANNER stage against live gemma4:e4b.

e2e-15 ("Show a heatmap of the kitchen temperature by hour of day and day
over the last week") is a single-numeric prompt, so the planner sees the full
ADR-0023 envelope [time_series, histogram, aggregate_bar]. The heatmap family
is NOT in the envelope — this repro shows which family the planner picks (and
how consistently) so the codegen-side repro can use the real chart_spec shape.
Run several times: the pick may vary sample to sample.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from repro_planner import run  # noqa: E402

PROMPT = "Show a heatmap of the kitchen temperature by hour of day and day over the last week"
N = int(os.environ.get("RUNS", "3"))

if __name__ == "__main__":
    for i in range(1, N + 1):
        run(
            {"name": f"E2E15 heatmap prompt, full envelope (run {i})", "prompt": PROMPT},
            family="time_series",
            families=["time_series", "histogram", "aggregate_bar"],
            approved=["sensor.kitchen_ecobee_temperature"],
            overlay=[],
        )
