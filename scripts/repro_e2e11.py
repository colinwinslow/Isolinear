#!/usr/bin/env python3
"""Diagnose e2e-11 mean-intent (open-queue (z)) against live gemma4:e4b.

Live 0.2.24 (18th session, e2e run 20260706T205049Z) plotted BOTH raw series
plus a scalar "Average Temperature" axhline and returned NULL answer_text,
where 0.2.23 (17th session, run 20260706T172905Z) plotted a (spiky union-index)
mean SERIES and answered "72.13 °F". The 0.2.24 alignment idiom itself gated
3/3 TRUE mean series offline (alignment_rule_gate t_mean, std 2.12) — so the
idiom is not the regression. The visible delta between the offline gate and the
live run is the planner-authored chart_spec TITLE:

  gate (mean series, 3/3):   "Average of kitchen and basement temperatures"
  live (scalar + no answer): "Kitchen and Basement Temperature History"

Hypothesis: the chart_spec title frames how codegen reads user_request — a
raw-history title pulls the model to plot raw lines + a scalar mean and skip
the answer; an analysis-flavored title keeps the computed-series intent.

Phase 1 — what does the live planner emit? 2 production plans of the e2e-11
prompt (temperature-0, near-greedy: 1-2 samples represent the live mode);
record chart_spec.title / summary / series labels.

Phase 2 — production codegen (generate_chart_code + real rules), same
user_request, two chart_spec-title arms x RUNS, execution-truth classification:
  mean_series — a derived line (n > 50) at the combined mean (67.5 ± 1) with
                the true derived std (0.5–2.8; the union artifact is > 3.4)
  scalar_line — a line at the combined mean with ~zero std (an axhline)
  answer      — answer_text non-null carrying a number near the combined mean

Config via env: OLLAMA_URL, MODEL, EXEC_PY, RUNS (default 3).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "evals"))

from alignment_rule_gate import (  # noqa: E402
    _irregular_series,
    _request,
    _series_spec,
    execute,
)

from custom_components.isolinear import model_provider as mp  # noqa: E402

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.0.1.39:11434").rstrip("/")
MODEL = os.environ.get("MODEL", "gemma4:e4b")
RUNS = int(os.environ.get("RUNS", "3"))
MAX_REPAIRS = int(os.environ.get("MAX_REPAIRS", "3"))

PROMPT = "What is the average of the kitchen and basement temperatures over the last day?"
APPROVED = ["sensor.basement_temperature", "sensor.kitchen_ecobee_temperature"]

# Each arm = (chart_spec.title, chart_spec.summary or None). The live planner
# emits BOTH a raw-history title AND a raw-trends summary sentence (phase 1);
# the alignment gate request carried neither summary — isolate each.
ARMS = {
    "live_history_title": ("Kitchen and Basement Temperature History", None),
    "analysis_title": ("Average of kitchen and basement temperatures", None),
    "live_title_plus_summary": (
        "Kitchen and Basement Temperature History",
        "This chart shows the temperature trends for the kitchen and basement over the last day.",
    ),
    # Real HA recorder data pulled from the live instance (means ~1.4 °F apart,
    # overlapping bands — visually nothing like the 7 °F-apart synthetic sines).
    # Series built from /tmp/e2e11_real_history.json when present.
    "real_data": (
        "Kitchen and Basement Temperature History",
        "This chart shows the temperature trends for the kitchen and basement over the last day.",
    ),
}

REAL_HISTORY = Path("/tmp/e2e11_real_history.json")


def _real_series() -> tuple[list, float]:
    raw = json.loads(REAL_HISTORY.read_text())
    series_list = []
    means = []
    for sid, (eid, label) in {
        "kitchen": ("sensor.kitchen_ecobee_temperature", "Kitchen Temperature"),
        "basement": ("sensor.basement_temperature", "Basement Temperature"),
    }.items():
        pts = raw[eid]
        means.append(sum(p["value"] for p in pts) / len(pts))
        series_list.append({"series_id": sid, "entity_id": eid, "label": label,
                            "kind": "numeric", "unit": "°F", "points": pts,
                            "source_entity_ids": [eid], "warnings": []})
    return series_list, sum(means) / len(means)

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def phase1_planner_framing() -> None:
    print("=== Phase 1: live planner framing (production plan_chart) ===")
    planner = mp.OllamaCompatiblePlannerClient(endpoint_url=OLLAMA_URL, planner_model=MODEL)
    schema = mp.load_planner_result_schema(
        "time_series", envelope=["time_series"], entity_ids=APPROVED
    )
    request = {
        "prompt": PROMPT,
        "approved_entity_ids": APPROVED,
        "history_entity_ids": APPROVED,
        "now": "2026-07-07T12:00:00-04:00",
        "time_zone": "America/New_York",
        "output_schema": "PlannerResult",
    }
    for n in (1, 2):
        result = planner.plan_chart(request, result_schema=schema)
        pr = result.get("planner_result") or {}
        spec = pr.get("chart_spec") or {}
        print(f"[plan {n}] status={pr.get('status')!r} title={spec.get('title')!r}")
        print(f"         summary={spec.get('summary')!r}")
        print(f"         series labels={[s.get('label') for s in spec.get('series', [])]}")


def classify(execution: dict, *, target: float = 67.5, tol: float = 1.0,
             series_std_min: float = 0.5, series_std_max: float = 2.8) -> dict:
    lines = execution.get("lines") or []
    answer = execution.get("answer_text")
    nums = [float(t) for t in _NUM_RE.findall(answer)] if isinstance(answer, str) else []
    mean_series = [
        ln for ln in lines
        if abs(ln["mean"] - target) <= tol
        and series_std_min <= ln["std"] <= series_std_max and ln["n"] > 50
    ]
    scalar_line = [
        ln for ln in lines if abs(ln["mean"] - target) <= tol and ln["std"] <= 0.05
    ]
    answered = any(abs(x - target) <= 1.5 for x in nums)
    return {
        "mean_series": bool(mean_series),
        "scalar_line": bool(scalar_line),
        "answered": answered,
        "answer_text": answer,
        "lines": [
            {"label": ln.get("label"), "n": ln["n"], "mean": round(ln["mean"], 2),
             "std": round(ln["std"], 2)}
            for ln in lines
        ],
    }


def phase2_codegen_arms() -> dict:
    print("\n=== Phase 2: production codegen x title arms ===")
    client = mp.OllamaCompatiblePlannerClient(endpoint_url=OLLAMA_URL, planner_model=MODEL)
    k = _irregular_series("kitchen", "sensor.kitchen_ecobee_temperature",
                          "Kitchen Temperature", 71, 4, hours=48, step_s=420,
                          jitter_s=90, phase_s=0)
    b = _irregular_series("basement", "sensor.basement_temperature",
                          "Basement Temperature", 64, 2, hours=48, step_s=660,
                          jitter_s=150, phase_s=180)
    two = [_series_spec("kitchen", "Kitchen Temperature", "sensor.kitchen_ecobee_temperature"),
           _series_spec("basement", "Basement Temperature", "sensor.basement_temperature",
                        role="secondary")]
    tally: dict = {}
    only = {s.strip() for s in os.environ.get("ONLY_ARMS", "").split(",") if s.strip()}
    for arm, (title, summary) in ARMS.items():
        if only and arm not in only:
            continue
        tally[arm] = {"runs": 0, "mean_series": 0, "scalar_line": 0, "answered": 0,
                      "recovered_via_repair": 0}
        classify_kwargs: dict = {}
        for run_n in range(1, RUNS + 1):
            if arm == "real_data":
                real_series, real_target = _real_series()
                request = _request(title, [
                    _series_spec("kitchen", "Kitchen Temperature",
                                 "sensor.kitchen_ecobee_temperature"),
                    _series_spec("basement", "Basement Temperature",
                                 "sensor.basement_temperature", role="secondary"),
                ], real_series)
                # Real bands overlap: raw means sit ~0.7 °F either side of the
                # combined mean, and the true derived std is well under the
                # synthetic 0.5 floor.
                classify_kwargs = {"target": real_target, "tol": 0.5,
                                   "series_std_min": 0.15, "series_std_max": 1.5}
            else:
                request = _request(title, two, [k, b])
            if summary is not None:
                request["chart_spec"]["summary"] = summary
            # Production-shaped repair loop (the live run's 191 s suggests
            # repairs ran; a repair that "simplifies" away the computed series
            # would explain the live scalar+no-answer render).
            code, sandbox_error, execution, attempt = None, None, None, 0
            for attempt in range(MAX_REPAIRS + 1):
                gen = (client.generate_chart_code(request, user_request=PROMPT)
                       if code is None
                       else client.repair_chart_code(code, sandbox_error, request,
                                                     user_request=PROMPT))
                if not gen.get("accepted"):
                    print(f"[{arm}::run{run_n}] provider failure {gen.get('code')}")
                    execution = None
                    break
                code = gen["python_code"]
                execution = execute(code, request)
                if execution.get("ok"):
                    break
                print(f"[{arm}::run{run_n}] attempt {attempt} runtime error "
                      f"{execution.get('error')}")
                sandbox_error = {"code": "runtime_error",
                                 "message": execution.get("error") or "failed",
                                 "details": {"traceback": execution.get("traceback") or ""}}
            if not execution or not execution.get("ok"):
                continue
            verdict = classify(execution, **classify_kwargs)
            tally[arm]["runs"] += 1
            for key in ("mean_series", "scalar_line", "answered"):
                tally[arm][key] += bool(verdict[key])
            tally[arm]["recovered_via_repair"] += attempt > 0
            print(f"[{arm}::run{run_n}] attempts={attempt + 1} "
                  f"mean_series={verdict['mean_series']} "
                  f"scalar_line={verdict['scalar_line']} answered={verdict['answered']}")
            print(f"    answer_text={verdict['answer_text']!r}")
            print(f"    lines={verdict['lines']}")
    return tally


if __name__ == "__main__":
    if os.environ.get("RULES_0224"):
        # Counterfactual: restore the 0.2.24 rule set (the live-failure version)
        # by stripping the 0.2.26 family-degrade sentence, marker-gated.
        from alignment_rule_gate import re as _re  # reuse module import path

        marker = "Render only these chart families"
        hits = [i for i, r in enumerate(mp._CODEGEN_PROMPT_RULES) if marker in r]
        if len(hits) != 1:
            raise SystemExit(f"expected one rule containing {marker!r}, found {len(hits)}")
        degrade_re = _re.compile(
            r"Render only these chart families:.*?NEVER which of these three chart "
            r"families you draw\.", _re.S)
        rules = list(mp._CODEGEN_PROMPT_RULES)
        stripped = degrade_re.sub(" ", rules[hits[0]])
        if marker in stripped:
            raise SystemExit("family-degrade strip failed — update degrade_re")
        rules[hits[0]] = stripped
        mp._CODEGEN_PROMPT_RULES = rules
        print("(running with the 0.2.24 rule set — family-degrade sentence stripped)")
    if not os.environ.get("SKIP_PHASE1"):
        phase1_planner_framing()
    tally = phase2_codegen_arms()
    print("\n=== tally ===")
    print(json.dumps(tally, indent=1))
