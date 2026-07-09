#!/usr/bin/env python3
"""Eval-gate the repair-intent-retention instruction (open-queue (B)).

RESULT (2026-07-08, N=3/arm): NO SEPARATION — 3/3 retained in BOTH arms. On a
clean, fixable runtime error gemma4:e4b minimally fixes it and keeps the derived
series + answer_text regardless of the instruction. Per the 0.2.22
"failure-driven hints must earn their accept-rate" principle the retention
instruction was NOT shipped (there is no production constant to toggle anymore;
this gate reconstructs the candidate sentence locally and patches it into the
repair task for the with-arm so the negative result stays re-runnable). The
cross-math variance basin's real fix turned out to be a fix-RATE bug, not intent
erosion: the live runtime_error was an intermittent KeyError from indexing a
concat'd DataFrame by entity_id — see evals/crossmath_frame_keying_gate.py.


Live diagnosis (20th + 23rd sessions): the multi-sensor cross-math family is a
codegen-runtime variance basin. A first codegen attempt that computes a derived
series (a cross-sensor mean / difference / deviation) and emits answer_text
throws an intermittent runtime_error; the repair loop hands the floor model the
previous_code + the error, and — focused on clearing the error — the model
ERODES the analysis: it rewrites the derived series back to plotting the raw
input lines and/or drops answer_text. The 20th session observed a two-repair
chain that kept the mean series but dropped answer_text; the 23rd session watched
e2e-11/12/18 rotate into a Pillow fallback (empty answer) through exactly this
erosion. The failing attempt produced no successful artifact to carry forward
deterministically, so the only carrier of intent across a runtime-error repair
is the previous_code text — the lever is a repair-only instruction to preserve
it (custom_components/.../model_provider.py::_CODEGEN_REPAIR_INTENT_RETENTION).

This gate drives the PRODUCTION repair path (real repair_chart_code) against
live gemma4:e4b. It SEEDS a controlled previous_code that already computes the
cross-sensor mean + returns answer_text but has ONE fixable runtime error
squarely in the derived-series math (an AttributeError: `.mean_across()` instead
of `.mean(axis=1)`), then asks the model to repair it, two arms:

  * without_retention — repair task minus the retention sentence (the pre-(B)
    behaviour; _CODEGEN_REPAIR_INTENT_RETENTION swapped to "");
  * with_retention    — repair task as-is (the (B) prescription).

Execution-truth judge: a run RETAINS iff the repaired code (a) executes and
(b) still returns a non-empty answer_text carrying a computed number — the exact
intent the erosion destroys. A secondary signal records whether the executed
code still computed a derived mean (a single averaged line whose values sit
BETWEEN the two raw inputs) vs. fell back to plotting the raw input lines.

Config via env: OLLAMA_URL, MODEL, EXEC_PY, RUNS (default 3), MAX_REPAIRS
(default 2), RESULTS_JSON, ONLY_ARM.
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

from custom_components.isolinear import model_provider as mp  # noqa: E402

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.0.1.39:11434").rstrip("/")
MODEL = os.environ.get("MODEL", "gemma4:e4b")
EXEC_PY = os.environ.get("EXEC_PY", "/home/claude/.expenv/bin/python")
RUNS = int(os.environ.get("RUNS", "3"))
MAX_REPAIRS = int(os.environ.get("MAX_REPAIRS", "2"))
RESULTS_JSON = Path(os.environ.get("RESULTS_JSON", HERE / "prompts" / "repair_intent_retention_results.json"))

PROMPT = "What is the average of the kitchen and family room temperatures?"
_BASE_MS = 1782000000000  # 2026-06-29T00:00:00Z

# The candidate retention sentence (dropped from production after this gate showed
# no separation). The with-arm patches it onto the repair task; the without-arm
# uses the production repair task unchanged.
_CANDIDATE_RETENTION = (
    " The previous_code was written to fulfill user_request. If it computed a "
    "derived or aggregated series (an average or combination across sensors, a "
    "difference, a correlation, a deviation from average, or a rolling/smoothed "
    "series) or returned an 'answer_text' or 'claims' in its metadata, your "
    "corrected code MUST preserve that SAME analysis and answer — keep the derived "
    "series and keep emitting answer_text (and claims). Change ONLY what is needed "
    "to fix the reported error; never simplify the analysis back to plotting the "
    "raw input lines and never drop answer_text while fixing the error."
)

# The seed previous_code: a realistic cross-sensor mean render (aligns each
# series with the prescribed per-entity resample idiom, plots the derived mean,
# returns a grounded answer_text) with ONE fixable runtime bug in the math —
# `combined.mean_across()` is not a pandas method (correct: combined.mean(axis=1)).
# The error sits inside the derived-series computation, so a repair MUST engage
# the analysis to clear it; whether it keeps the mean + answer_text or bails to
# raw lines is what the arms separate.
SEED_CODE = '''\
def render_chart(data, output_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    numeric = [s for s in data["history_series"] if s.get("kind") == "numeric"]
    aligned = []
    for s in numeric:
        pts = s["points"]
        ser = pd.Series(
            [p["value"] for p in pts],
            index=pd.to_datetime([p["ts_epoch_ms"] for p in pts], unit="ms"),
        ).resample("5min").mean().interpolate()
        aligned.append(ser)
    combined = pd.concat(aligned, axis=1).dropna()
    mean_series = combined.mean_across()  # BUG: no such method

    unit = numeric[0].get("unit") or ""
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=110)
    ax.plot(mean_series.index, mean_series.values, label="Average")
    ax.set_ylabel(f"Temperature ({unit})")
    ax.set_title("Average of Kitchen and Family Room Temperature")
    ax.legend()
    fig.savefig(output_path, format="png", bbox_inches="tight")

    avg = float(mean_series.mean())
    answer_text = f"The average temperature across the two sensors is {avg:.2f} {unit}."
    return {"title": "Average Temperature", "series_plotted": ["average"],
            "warnings": [], "answer_text": answer_text}
'''

SEED_ERROR = {
    "code": "runtime_error",
    "message": "AttributeError: 'DataFrame' object has no attribute 'mean_across'",
    "details": {
        "traceback": (
            "Traceback (most recent call last):\n"
            "  File \"code.py\", line 18, in render_chart\n"
            "    mean_series = combined.mean_across()\n"
            "AttributeError: 'DataFrame' object has no attribute 'mean_across'"
        )
    },
}


def _temp_series(entity_id: str, label: str, base: float, phase: float, jitter_ms: int) -> dict:
    """An irregular ~24h temperature series (disjoint timestamps from its peer so
    the alignment idiom is load-bearing)."""
    points = []
    for i in range(48):
        ms = _BASE_MS + i * 30 * 60 * 1000 + jitter_ms
        v = base + 2.5 * math.sin(i / 48 * 2 * math.pi + phase)
        iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(ms / 1000))
        points.append({"ts": iso, "ts_epoch_ms": ms, "value": round(v, 2),
                       "raw_state": None, "quality": "ok"})
    return {"series_id": f"series-{entity_id}", "entity_id": entity_id, "label": label,
            "kind": "numeric", "unit": "°F", "points": points, "source": "recorder",
            "source_entity_ids": [entity_id], "warnings": []}


def _request() -> dict:
    return {
        "chart_spec": {
            "chart_id": "avg_kitchen_family_temp", "chart_type": "time_series",
            "title": "Average of Kitchen and Family Room Temperature",
            "time_range": {"type": "relative", "duration": "24h"},
            "series": [
                {"series_id": "kitchen", "label": "Kitchen Temperature", "role": "primary",
                 "render_as": "line", "transform": {"operation": "none", "window": None},
                 "unit": "°F", "source": {"type": "entity",
                 "entity_id": "sensor.kitchen_ecobee_temperature", "attribute": None}},
                {"series_id": "family", "label": "Family Room Temperature", "role": "primary",
                 "render_as": "line", "transform": {"operation": "none", "window": None},
                 "unit": "°F", "source": {"type": "entity",
                 "entity_id": "sensor.family_room_temperature", "attribute": None}},
            ],
            "overlays": [], "x_axis": {"type": "time"}, "y_axis": {},
        },
        "history_series": [
            _temp_series("sensor.kitchen_ecobee_temperature", "Kitchen Temperature", 71.5, 0.0, 0),
            _temp_series("sensor.family_room_temperature", "Family Room Temperature", 69.0, 0.9, 137000),
        ],
        "derived_intervals": [],
        "output": {"format": "png", "width": 800, "height": 480},
    }


_HARNESS = r'''
import json, sys, traceback, warnings
warnings.simplefilter("ignore")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.close = lambda *a, **k: None

code_file, data_file, out_png = sys.argv[1], sys.argv[2], sys.argv[3]
data = json.load(open(data_file))

def _san(o):
    try: return float(o)
    except Exception: return str(o)

try:
    ns = {}
    exec(open(code_file).read(), ns)
    meta = ns["render_chart"](data, out_png)
    axes = []
    for num in plt.get_fignums():
        for ax in plt.figure(num).axes:
            lines = []
            for ln in ax.get_lines():
                ys = [float(y) for y in ln.get_ydata()]
                lines.append({"n": len(ys),
                              "min": min(ys) if ys else None,
                              "max": max(ys) if ys else None,
                              "mean": (sum(ys) / len(ys)) if ys else None})
            axes.append({"ylabel": str(ax.get_ylabel()), "n_lines": len(ax.get_lines()),
                         "lines": lines})
    answer_text = None
    if isinstance(meta, dict):
        answer_text = meta.get("answer_text")
    import os
    print("__R__" + json.dumps({"ok": True, "axes": axes, "answer_text": answer_text,
        "png": os.path.getsize(out_png) if os.path.exists(out_png) else 0}, default=_san))
except Exception as exc:
    print("__R__" + json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}",
                                "traceback": traceback.format_exc()[-1200:]}))
'''


def execute(code: str, request: dict) -> dict:
    data = {"chart_spec": request["chart_spec"], "history_series": request["history_series"],
            "derived_intervals": request["derived_intervals"], "output": request["output"], "theme": {}}
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        (tdp / "code.py").write_text(code)
        (tdp / "data.json").write_text(json.dumps(data))
        (tdp / "harness.py").write_text(_HARNESS)
        proc = subprocess.run(
            [EXEC_PY, str(tdp / "harness.py"), str(tdp / "code.py"),
             str(tdp / "data.json"), str(tdp / "out.png")],
            capture_output=True, text=True, timeout=120)
    for stream in (proc.stdout, proc.stderr):
        for ln in stream.splitlines():
            if ln.startswith("__R__"):
                return json.loads(ln[len("__R__"):])
    return {"ok": False, "error": f"harness no result rc={proc.returncode}",
            "traceback": (proc.stderr or proc.stdout)[-800:]}


_NUM_RE = re.compile(r"\d")


def judge(execution: dict) -> dict:
    """RETAINED iff executed AND a non-empty answer_text carrying a number is
    returned — the intent the repair-chain erosion destroys. `derived_line`
    records whether a single averaged line (values between the two raw inputs,
    ~69-72 °F) survived vs. the raw two-line plot; a secondary quality signal."""
    v = {"retained": False, "answer": False, "derived_line": False, "why": ""}
    if not execution.get("ok"):
        v["why"] = f"did not execute: {execution.get('error')}"
        return v
    answer = execution.get("answer_text")
    v["answer"] = bool(isinstance(answer, str) and answer.strip() and _NUM_RE.search(answer))
    axes = execution.get("axes") or []
    for a in axes:
        # A derived mean is ONE line whose values sit inside the inputs' band.
        singles = [ln for ln in a["lines"] if ln["mean"] is not None and 68.0 <= ln["mean"] <= 73.0]
        if a["n_lines"] == 1 and singles:
            v["derived_line"] = True
    v["retained"] = v["answer"]
    v["why"] = (f"answer={'Y' if v['answer'] else 'N'} derived_line={'Y' if v['derived_line'] else 'N'} "
                f"axes={[a['n_lines'] for a in axes]} answer_text={answer!r}")
    return v


def run_one(client, arm, run_n, results) -> None:
    key = f"{arm}::run{run_n}"
    if results["runs"].get(key, {}).get("done"):
        return
    request = _request()
    rec = {"arm": arm, "run": run_n, "attempts": [], "done": False, "executed": False, "retained": False}
    code, sandbox_error = SEED_CODE, SEED_ERROR
    for attempt in range(MAX_REPAIRS + 1):
        t0 = time.time()
        gen = client.repair_chart_code(code, sandbox_error, request, user_request=PROMPT)
        gen_s = round(time.time() - t0, 1)
        if not gen.get("accepted"):
            rec["attempts"].append({"n": attempt, "gen_s": gen_s, "provider_failure": gen.get("code")})
            break
        code = gen["python_code"]
        execution = execute(code, request)
        att = {"n": attempt, "gen_s": gen_s, "loc": len(code.splitlines()), "ok": execution.get("ok")}
        if execution.get("ok"):
            rec["executed"] = True
            rec["verdict"] = judge(execution)
            rec["retained"] = rec["verdict"]["retained"]
            att["answer_text"] = execution.get("answer_text")
            att["axes"] = execution.get("axes")
            rec["attempts"].append(att)
            break
        att["error"] = execution.get("error")
        rec["attempts"].append(att)
        if attempt == MAX_REPAIRS:
            rec["verdict"] = judge(execution)
            break
        sandbox_error = {"code": "runtime_error", "message": execution.get("error") or "failed",
                         "details": {"traceback": execution.get("traceback") or ""}}
    rec["done"] = True
    results["runs"][key] = rec
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    vv = rec.get("verdict") or {}
    print(f"[{key}] {'RETAINED' if rec['retained'] else 'eroded'} executed={rec['executed']} "
          f"attempts={len(rec['attempts'])} — {vv.get('why', 'n/a')}", flush=True)


def main() -> int:
    only_arm = os.environ.get("ONLY_ARM", "").strip()
    arms = ["without_retention", "with_retention"]
    if only_arm:
        arms = [only_arm]

    results = json.loads(RESULTS_JSON.read_text()) if RESULTS_JSON.exists() else {"meta": {}, "runs": {}}
    results["meta"] = {"model": MODEL, "ollama": OLLAMA_URL, "runs": RUNS,
                       "max_repairs": MAX_REPAIRS, "prompt": PROMPT,
                       "started": results["meta"].get("started")
                       or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    client = mp.OllamaCompatiblePlannerClient(endpoint_url=OLLAMA_URL, planner_model=MODEL)
    cls = mp.OllamaCompatiblePlannerClient
    original_payload = cls._codegen_repair_payload

    def _with_retention_payload(self, *args, **kwargs):
        payload = original_payload(self, *args, **kwargs)
        content = json.loads(payload["messages"][1]["content"])
        content["task"] = content["task"] + _CANDIDATE_RETENTION
        payload["messages"][1]["content"] = json.dumps(content, separators=(",", ":"))
        return payload

    try:
        for arm in arms:
            cls._codegen_repair_payload = (
                _with_retention_payload if arm == "with_retention" else original_payload
            )
            for run_n in range(1, RUNS + 1):
                run_one(client, arm, run_n, results)
    finally:
        cls._codegen_repair_payload = original_payload

    tally: dict[str, dict] = {}
    for rec in results["runs"].values():
        t = tally.setdefault(rec["arm"], {"runs": 0, "executed": 0, "retained": 0, "derived_line": 0})
        t["runs"] += 1
        t["executed"] += bool(rec.get("executed"))
        t["retained"] += bool(rec.get("retained"))
        t["derived_line"] += bool((rec.get("verdict") or {}).get("derived_line"))
    print("\n=== tally ===")
    for arm, t in sorted(tally.items()):
        print(f"{arm}: {t['retained']}/{t['runs']} retained answer_text "
              f"({t['derived_line']}/{t['runs']} kept derived line, {t['executed']} executed)")
    results["tally"] = tally
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
