#!/usr/bin/env python3
"""Reproduce the e2e-15 heatmap garbage codegen offline (open-queue (w)).

The 18th-session live run judged e2e-15 a hard FAIL: "Show a heatmap of the
kitchen temperature by hour of day and day over the last week" rendered a
nonsense bar chart — y-axis "Temperature (°F)" spanning 0–2 with alternating
1/2 bars, x-axis raw epoch-milliseconds, no colour grid. render_path=codegen
with no fallback, so the sandbox ACCEPTED it (accept≠quality).

This repro drives the PRODUCTION codegen path (real generate_chart_code /
repair_chart_code, real _CODEGEN_PROMPT_RULES + prompt-view projection)
against live gemma with the payload shape the live pipeline serves for a
7-day window: ONE statistics-tier series (hourly buckets, value=mean +
value_min/value_max, source long_term_statistics, resolution hourly) and a
time_series chart_spec (invariant #9 — the planner cannot emit a heatmap
family). Each run's generated code + executed PNG + axes summary land in
evals/e2e_runs/repro_e2e15/ so the failure can be root-caused by reading the
actual code, not guessed from the served render.

Config via env: OLLAMA_URL, MODEL, EXEC_PY, RUNS (default 3), MAX_REPAIRS
(default 2), OUT_DIR, CHART_FAMILY (time_series | histogram — histogram is
what the live planner deterministically picks for this prompt, 6/6 samples).
"""
from __future__ import annotations

import json
import math
import os
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
OUT_DIR = Path(os.environ.get("OUT_DIR", REPO / "evals" / "e2e_runs" / "repro_e2e15"))
CHART_FAMILY = os.environ.get("CHART_FAMILY", "time_series")

PROMPT = "Show a heatmap of the kitchen temperature by hour of day and day over the last week"

# 2026-06-29T00:00:00Z — a week ending at the live run's window.
_BASE_MS = 1782000000000


def _hourly_stats_series() -> dict:
    """168 hourly long-term-statistics buckets shaped like _normalize_statistics_series
    output (+ ts_epoch_ms, which the codegen build site adds per D9)."""
    points = []
    for h in range(24 * 7):
        ms = _BASE_MS + h * 3600 * 1000
        # Daily cycle ~68–75 °F with a slow weekly drift, like the real kitchen.
        v = 71.5 + 3.2 * math.sin((h % 24) / 24 * 2 * math.pi - 1.9) + 0.4 * math.sin(h / 168 * 2 * math.pi)
        iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(ms / 1000))
        points.append({
            "ts": iso,
            "ts_epoch_ms": ms,
            "value": round(v, 2),
            "value_min": round(v - 0.6, 2),
            "value_max": round(v + 0.6, 2),
            "raw_state": None,
            "quality": "ok",
        })
    return {
        "series_id": "series-001",
        "entity_id": "sensor.kitchen_ecobee_temperature",
        "label": "Kitchen Temperature",
        "kind": "numeric",
        "unit": "°F",
        "points": points,
        "source": "long_term_statistics",
        "resolution": "hourly",
        "source_entity_ids": ["sensor.kitchen_ecobee_temperature"],
        "warnings": [],
    }


def _request() -> dict:
    # There is no heatmap chart family in the ADR-0023 envelope. The live
    # planner deterministically picks histogram for this prompt (repro
    # scripts/repro_e2e15_planner.py, 6/6 — its exact title appears on the live
    # garbage render); time_series is the counterfactual arm.
    if CHART_FAMILY == "histogram":
        spec = {
            "chart_id": "kitchen_temperature_heatmap",
            "chart_type": "histogram",
            "title": "Kitchen Temperature Distribution Over the Last Week",
            "time_range": {"type": "relative", "duration": "7d"},
            "series": [{
                "series_id": "kitchen_temperature",
                "label": "Kitchen Temperature",
                "role": "primary",
                "render_as": "histogram",
                "transform": {"operation": "none", "window": None},
                "unit": "°F",
                "source": {"type": "entity", "entity_id": "sensor.kitchen_ecobee_temperature",
                           "attribute": None},
            }],
            "overlays": [],
            "x_axis": {"type": "value", "bin_count": 8},
            "y_axis": {},
        }
    else:
        spec = {
            "chart_id": "repro-e2e15",
            "chart_type": "time_series",
            "title": "Kitchen Temperature Chart",
            "time_range": {"type": "relative", "duration": "7d"},
            "series": [{
                "series_id": "series-001",
                "label": "Kitchen Temperature",
                "role": "primary",
                "render_as": "line",
                "unit": "°F",
                "source": {"type": "entity", "entity_id": "sensor.kitchen_ecobee_temperature"},
            }],
            "overlays": [],
        }
    return {
        "chart_spec": spec,
        "history_series": [_hourly_stats_series()],
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
            axes.append({
                "title": str(ax.get_title()),
                "xlabel": str(ax.get_xlabel()), "ylabel": str(ax.get_ylabel()),
                "xlim": [float(v) for v in ax.get_xlim()],
                "ylim": [float(v) for v in ax.get_ylim()],
                "n_lines": len(ax.get_lines()),
                "n_patches": len(ax.patches),
                "n_images": len(ax.images),
                "n_collections": len(ax.collections),
            })
    import os
    print("__R__" + json.dumps({"ok": True,
        "meta": meta if isinstance(meta, dict) else str(meta),
        "axes": axes,
        "png": os.path.getsize(out_png) if os.path.exists(out_png) else 0}, default=_san))
except Exception as exc:
    print("__R__" + json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}",
                                "traceback": traceback.format_exc()[-1200:]}))
'''


def execute(code: str, request: dict, out_png: Path) -> dict:
    data = {"chart_spec": request["chart_spec"], "history_series": request["history_series"],
            "derived_intervals": request["derived_intervals"], "output": request["output"], "theme": {}}
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        (tdp / "code.py").write_text(code)
        (tdp / "data.json").write_text(json.dumps(data))
        (tdp / "harness.py").write_text(_HARNESS)
        proc = subprocess.run(
            [EXEC_PY, str(tdp / "harness.py"), str(tdp / "code.py"),
             str(tdp / "data.json"), str(out_png)],
            capture_output=True, text=True, timeout=120)
    for stream in (proc.stdout, proc.stderr):
        for ln in stream.splitlines():
            if ln.startswith("__R__"):
                return json.loads(ln[len("__R__"):])
    return {"ok": False, "error": f"harness no result rc={proc.returncode}",
            "traceback": (proc.stderr or proc.stdout)[-800:]}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    request = _request()
    client = mp.OllamaCompatiblePlannerClient(endpoint_url=OLLAMA_URL, planner_model=MODEL)
    summary = []
    for run_n in range(1, RUNS + 1):
        code, sandbox_error = None, None
        rec = {"run": run_n, "attempts": []}
        for attempt in range(MAX_REPAIRS + 1):
            t0 = time.time()
            gen = (client.generate_chart_code(request, user_request=PROMPT) if code is None
                   else client.repair_chart_code(code, sandbox_error, request, user_request=PROMPT))
            gen_s = round(time.time() - t0, 1)
            if not gen.get("accepted"):
                rec["attempts"].append({"n": attempt, "gen_s": gen_s, "provider_failure": gen.get("code")})
                break
            code = gen["python_code"]
            (OUT_DIR / f"run{run_n}_attempt{attempt}.py").write_text(code)
            out_png = OUT_DIR / f"run{run_n}_attempt{attempt}.png"
            execution = execute(code, request, out_png)
            att = {"n": attempt, "gen_s": gen_s, "loc": len(code.splitlines()),
                   "ok": execution.get("ok")}
            if execution.get("ok"):
                att["axes"] = execution.get("axes")
                att["meta"] = execution.get("meta")
                rec["attempts"].append(att)
                break
            att["error"] = execution.get("error")
            rec["attempts"].append(att)
            if attempt == MAX_REPAIRS:
                break
            sandbox_error = {"code": "runtime_error", "message": execution.get("error") or "failed",
                             "details": {"traceback": execution.get("traceback") or ""}}
        summary.append(rec)
        print(f"[run {run_n}] {json.dumps(rec['attempts'][-1], default=str)[:400]}", flush=True)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=1))
    print(f"\nartifacts in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
