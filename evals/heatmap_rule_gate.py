#!/usr/bin/env python3
"""Eval-gate the family-degrade rule (open-queue (w), live e2e-15 root).

The 18th-session live e2e run judged e2e-15 ("Show a heatmap of the kitchen
temperature by hour of day and day over the last week") a hard FAIL: the
single-numeric ADR-0023 envelope has NO heatmap family, so the planner
deterministically routes the prompt to `histogram` (repro
scripts/repro_e2e15_planner.py, 6/6) — then the ADR-0034 conduit hands codegen
a `user_request` that says "heatmap", and codegen tries to honour both the
histogram chart_spec AND the heatmap word at once. The live result was a
garbage 1/2-bar chart on an epoch-ms axis; the repro produced everything from a
perfect calendar heatmap to a frequency 2-D histogram to that nonsense —
per-sample roulette, all sandbox-ACCEPTED (accept≠quality).

Design decision (2026-07-07, Colin — "ship simple"): the integration owns the
chart FAMILY (line/histogram/bar, invariant #9); the model owns the
COMPUTATION within it. A heatmap is a family, not a computation, so codegen
must never invent one — a single-sensor "heatmap by hour and day" request
degrades to the histogram (distribution) the planner already chose. "heatmap"
the word stays reserved for a future spatial/floorplan renderer (open-queue
(c)); a temporal calendar heatmap, if ever built, becomes its own named family.

This gate drives the PRODUCTION codegen path against live gemma4:e4b with the
EXACT histogram chart_spec the live planner emits for this prompt (title,
render_as: histogram, x_axis {type: value, bin_count: 8}) plus the heatmap
user_request, two arms:

  * without_degrade — production rules minus the family-degrade sentence
    (marker-gated surgery, rule-gate pattern) — the 0.2.25-shipped behaviour;
  * with_degrade    — production rules as-is (the family-degrade prescription).

Execution-truth judge: a CLEAN 1-D histogram (several bar patches, value-range
x-axis, NO 2-D QuadMesh/image) fires; a 2-D heatmap (collections/images) or a
non-histogram is a fail — catches both the garbage and the "accidentally a real
heatmap" outcomes, since the shipped behaviour is a histogram either way.

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
RESULTS_JSON = Path(os.environ.get("RESULTS_JSON", HERE / "prompts" / "heatmap_rule_gate_results.json"))

# The family-degrade sentence under the gate, identified by distinctive phrasing
# — fail loudly if the rule text drifts (rule-gate pattern).
DEGRADE_MARKER = "Render only these chart families"
DEGRADE_RE = re.compile(
    r"Render only these chart families:.*?NEVER which of these three chart "
    r"families you draw\.", re.S)

PROMPT = "Show a heatmap of the kitchen temperature by hour of day and day over the last week"
_BASE_MS = 1782000000000  # 2026-06-29T00:00:00Z


def rules_without_degrade() -> list[str]:
    hits = [i for i, r in enumerate(mp._CODEGEN_PROMPT_RULES) if DEGRADE_MARKER in r]
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one rule containing {DEGRADE_MARKER!r}, found {len(hits)}")
    rules = list(mp._CODEGEN_PROMPT_RULES)
    stripped = DEGRADE_RE.sub(" ", rules[hits[0]])
    if DEGRADE_MARKER in stripped:
        raise SystemExit("family-degrade sentence removal failed — update DEGRADE_RE")
    rules[hits[0]] = stripped
    return rules


def _hourly_stats_series() -> dict:
    """168 hourly long-term-statistics buckets, shaped like the real
    _normalize_statistics_series output (+ ts_epoch_ms per the D9 build site)."""
    points = []
    for h in range(24 * 7):
        ms = _BASE_MS + h * 3600 * 1000
        v = 71.5 + 3.2 * math.sin((h % 24) / 24 * 2 * math.pi - 1.9) + 0.4 * math.sin(h / 168 * 2 * math.pi)
        iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(ms / 1000))
        points.append({"ts": iso, "ts_epoch_ms": ms, "value": round(v, 2),
                       "value_min": round(v - 0.6, 2), "value_max": round(v + 0.6, 2),
                       "raw_state": None, "quality": "ok"})
    return {"series_id": "series-001", "entity_id": "sensor.kitchen_ecobee_temperature",
            "label": "Kitchen Temperature", "kind": "numeric", "unit": "°F", "points": points,
            "source": "long_term_statistics", "resolution": "hourly",
            "source_entity_ids": ["sensor.kitchen_ecobee_temperature"], "warnings": []}


def _request() -> dict:
    # The EXACT histogram chart_spec the live planner emits for this prompt
    # (scripts/repro_e2e15_planner.py, 6/6): distribution-flavoured routing of a
    # heatmap ask, which is the conflict codegen must resolve cleanly.
    return {
        "chart_spec": {
            "chart_id": "kitchen_temperature_heatmap", "chart_type": "histogram",
            "title": "Kitchen Temperature Distribution Over the Last Week",
            "time_range": {"type": "relative", "duration": "7d"},
            "series": [{"series_id": "kitchen_temperature", "label": "Kitchen Temperature",
                        "role": "primary", "render_as": "histogram",
                        "transform": {"operation": "none", "window": None}, "unit": "°F",
                        "source": {"type": "entity",
                                   "entity_id": "sensor.kitchen_ecobee_temperature",
                                   "attribute": None}}],
            "overlays": [], "x_axis": {"type": "value", "bin_count": 8}, "y_axis": {},
        },
        "history_series": [_hourly_stats_series()], "derived_intervals": [],
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
            xl = [float(v) for v in ax.get_xlim()]
            axes.append({"xlabel": str(ax.get_xlabel()), "ylabel": str(ax.get_ylabel()),
                         "xlim": xl, "n_lines": len(ax.get_lines()),
                         "n_patches": len(ax.patches), "n_images": len(ax.images),
                         "n_collections": len(ax.collections)})
    import os
    print("__R__" + json.dumps({"ok": True, "axes": axes,
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


def judge(execution: dict) -> dict:
    """CLEAN histogram fires; a 2-D heatmap (QuadMesh/image collection) or a
    non-histogram fails. Temperature °F values sit ~68-75, so a histogram's
    x-axis (binned VALUES) lands in that range; a mesh/image populates
    collections/images instead of bar patches."""
    axes = execution.get("axes") or []
    v = {"fired": False, "why": ""}
    twod = [a for a in axes if a["n_collections"] > 0 or a["n_images"] > 0]
    if twod:
        v["why"] = f"2-D grid drawn (collections/images): {twod[0]}"
        return v
    hist = [a for a in axes
            if a["n_patches"] >= 4 and a["n_lines"] == 0 and 60.0 <= a["xlim"][0] <= 80.0
            and 60.0 <= a["xlim"][1] <= 80.0]
    if hist:
        v["fired"] = True
        v["why"] = f"clean histogram: {a_summary(hist[0])}"
    else:
        v["why"] = f"no value-range histogram: {[a_summary(a) for a in axes]}"
    return v


def a_summary(a: dict) -> str:
    return (f"patches={a['n_patches']} lines={a['n_lines']} coll={a['n_collections']} "
            f"img={a['n_images']} x={[round(x, 1) for x in a['xlim']]}")


def run_one(client, arm, run_n, results) -> None:
    key = f"{arm}::run{run_n}"
    if results["runs"].get(key, {}).get("done"):
        return
    request = _request()
    rec = {"arm": arm, "run": run_n, "attempts": [], "done": False, "executed": False, "fired": False}
    code, sandbox_error = None, None
    for attempt in range(MAX_REPAIRS + 1):
        t0 = time.time()
        gen = (client.generate_chart_code(request, user_request=PROMPT) if code is None
               else client.repair_chart_code(code, sandbox_error, request, user_request=PROMPT))
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
            rec["fired"] = rec["verdict"]["fired"]
            att["axes"] = execution.get("axes")
            rec["attempts"].append(att)
            break
        att["error"] = execution.get("error")
        rec["attempts"].append(att)
        if attempt == MAX_REPAIRS:
            break
        sandbox_error = {"code": "runtime_error", "message": execution.get("error") or "failed",
                         "details": {"traceback": execution.get("traceback") or ""}}
    rec["done"] = True
    results["runs"][key] = rec
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    vv = rec.get("verdict") or {}
    print(f"[{key}] {'CLEAN' if rec['fired'] else 'fail'} executed={rec['executed']} "
          f"attempts={len(rec['attempts'])} — {vv.get('why', 'n/a')}", flush=True)


def main() -> int:
    arms = {"without_degrade": rules_without_degrade(),
            "with_degrade": list(mp._CODEGEN_PROMPT_RULES)}
    only_arm = os.environ.get("ONLY_ARM", "").strip()
    if only_arm:
        arms = {only_arm: arms[only_arm]}

    results = json.loads(RESULTS_JSON.read_text()) if RESULTS_JSON.exists() else {"meta": {}, "runs": {}}
    results["meta"] = {"model": MODEL, "ollama": OLLAMA_URL, "runs": RUNS,
                       "max_repairs": MAX_REPAIRS, "prompt": PROMPT,
                       "started": results["meta"].get("started")
                       or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    client = mp.OllamaCompatiblePlannerClient(endpoint_url=OLLAMA_URL, planner_model=MODEL)
    original = list(mp._CODEGEN_PROMPT_RULES)
    try:
        for arm, rules in arms.items():
            mp._CODEGEN_PROMPT_RULES = rules
            for run_n in range(1, RUNS + 1):
                run_one(client, arm, run_n, results)
    finally:
        mp._CODEGEN_PROMPT_RULES = original

    tally: dict[str, dict] = {}
    for rec in results["runs"].values():
        t = tally.setdefault(rec["arm"], {"runs": 0, "executed": 0, "fired": 0})
        t["runs"] += 1
        t["executed"] += bool(rec.get("executed"))
        t["fired"] += bool(rec.get("fired"))
    print("\n=== tally ===")
    for arm, t in sorted(tally.items()):
        print(f"{arm}: {t['fired']}/{t['runs']} clean histograms ({t['executed']} executed)")
    results["tally"] = tally
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
