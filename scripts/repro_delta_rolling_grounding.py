#!/usr/bin/env python3
"""Diagnostic for the delta / rolling_mean grounding gap (live e2e-08 + e2e-17).

Both prompts SERVE an answer live but only as an `unverified_caveat` — the
grounding recompute can't produce a reference:

  e2e-08: "The average difference between the kitchen and basement humidity
           over the last two days was 7.13 %."   (answer_verification: unverified)
  e2e-17: "The rolling average of the kitchen temperature over the last two days
           was approximately 73.37 °F."          (answer_verification: unverified)

`_compute_delta` reads only `inputs[0]` (last - first of ONE series) and
`_compute_rolling_mean` averages a raw-point rolling window — neither mirrors
what the model actually computes on the ADR-0036 `align()` grid. This is the
documented third application of the align-grid pattern (after the 0.2.37
multi-input `_compute_mean` fix and the 0.2.41 `_compute_pearson_r` fix).

BEFORE designing the fix, this script establishes ground truth: what claim
shape does the model ACTUALLY emit for these two prompts? ([[feedback-e2e-over-
synthetic]] — the 0.2.41 synthetic probe reproduced the wrong failure.)

Drives the production codegen path (real generate_chart_code + the real
_CODEGEN_PROMPT_RULES) against live gemma with REAL recorder history and the
exact e2e prompts, executes the generated code, and records for every run:
  * the emitted claim(s) verbatim (metric / inputs / params / value);
  * what the CURRENT grounding check makes of it (bucket + outcome code);
  * the model's own value, so a candidate reference can be checked against it.

Env: HA_URL, HA_TOKEN (required), OLLAMA_URL, MODEL, EXEC_PY,
     RUNS (default 4 per case), MAX_REPAIRS (default 1), CASES (delta,rolling),
     RESULTS_JSON.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

from custom_components.isolinear import model_provider as mp  # noqa: E402
from custom_components.isolinear.answer_grounding import run_grounding_check  # noqa: E402

HA_URL = os.environ.get("HA_URL", "http://10.0.1.200:8123").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.0.1.39:11434").rstrip("/")
MODEL = os.environ.get("MODEL", "gemma4:e4b")
EXEC_PY = os.environ.get("EXEC_PY", "/home/claude/.expenv/bin/python")
RUNS = int(os.environ.get("RUNS", "4"))
MAX_REPAIRS = int(os.environ.get("MAX_REPAIRS", "1"))
CASES = [c.strip() for c in os.environ.get("CASES", "delta,rolling").split(",") if c.strip()]
RESULTS_JSON = Path(os.environ.get(
    "RESULTS_JSON", REPO / "evals" / "prompts" / "repro_delta_rolling_grounding_results.json"))

KITCHEN_T = "sensor.kitchen_ecobee_temperature"
KITCHEN_H = "sensor.kitchen_ecobee_humidity"
BASEMENT_H = "sensor.basement_humidity"
BASEMENT_T = "sensor.basement_temperature"

# The exact live e2e prompts (evals/prompts/e2e_prompts.json).
CASE_SPECS = {
    "delta": {
        "prompt": "Compare the kitchen and basement humidity over the last 2 days",
        "entities": [(KITCHEN_H, "Kitchen Humidity", "%"), (BASEMENT_H, "Basement Humidity", "%")],
        "title": "Comparison of Kitchen and Basement Humidity",
    },
    "rolling": {
        "prompt": "Show the kitchen temperature smoothed with a rolling average over the last 2 days",
        "entities": [(KITCHEN_T, "Kitchen Temperature", "°F")],
        "title": "Kitchen Temperature with Rolling Average",
    },
    # Cross-sensor rolling: does gemma emit a TWO-INPUT rolling_mean claim? This
    # is the one un-reproduced member of the multi-input family (mean 0.2.37,
    # pearson_r 0.2.41, delta 0.2.46 all patched; rolling_mean still reads
    # inputs[0] only). Reproduce-first before touching _compute_rolling_mean.
    "rolling_cross": {
        "prompt": "Show the average of the kitchen and basement temperatures smoothed with a rolling average over the last 2 days",
        "entities": [(KITCHEN_T, "Kitchen Temperature", "°F"), (BASEMENT_T, "Basement Temperature", "°F")],
        "title": "Kitchen and Basement Temperature — Rolling Average",
    },
}


def _fetch_series(entity_id: str, label: str, unit_default: str) -> dict:
    start = (datetime.now(timezone.utc) - timedelta(days=2)).replace(microsecond=0).isoformat()
    url = f"{HA_URL}/api/history/period/{start}?filter_entity_id={urllib.parse.quote(entity_id)}&minimal_response"
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + HA_TOKEN})
    raw = json.load(urllib.request.urlopen(req, timeout=40))
    states = raw[0] if raw else []
    points = []
    unit = unit_default
    for s in states:
        st = s.get("state")
        if st in (None, "unknown", "unavailable") or not re.match(r"^-?\d+(\.\d+)?$", str(st)):
            continue
        ts = s.get("last_changed") or s.get("last_updated")
        if not ts:
            continue
        ms = int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000)
        points.append({"ts": ts, "ts_epoch_ms": ms, "value": round(float(st), 2),
                       "raw_state": st, "quality": "ok"})
        u = s.get("attributes", {}).get("unit_of_measurement")
        if u:
            unit = u
    return {"series_id": f"series-{entity_id}", "entity_id": entity_id, "label": label,
            "kind": "numeric", "unit": unit, "points": points, "source": "recorder",
            "resolution": "raw", "source_entity_ids": [entity_id], "warnings": []}


def _request(case: str, history: list[dict]) -> dict:
    spec = CASE_SPECS[case]
    series = []
    for idx, (eid, label, unit) in enumerate(spec["entities"]):
        series.append({
            "series_id": f"s{idx}", "label": label, "role": "primary", "render_as": "line",
            "transform": {"operation": "none", "window": None}, "unit": unit,
            "source": {"type": "entity", "entity_id": eid, "attribute": None},
        })
    return {
        "chart_spec": {
            "chart_id": f"{case}_repro", "chart_type": "time_series", "title": spec["title"],
            "time_range": {"type": "relative", "duration": "2d"},
            "series": series, "overlays": [], "x_axis": {"type": "time"}, "y_axis": {},
        },
        "history_series": history, "derived_intervals": [],
        "output": {"format": "png", "width": 800, "height": 480},
    }


_HARNESS = r'''
import json, sys, traceback, warnings
warnings.simplefilter("ignore")
sys.path.insert(0, sys.argv[4])
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
    import os
    meta = meta if isinstance(meta, dict) else {}
    print("__R__" + json.dumps({"ok": True, "answer_text": meta.get("answer_text"),
        "claims": meta.get("claims"), "meta_keys": list(meta.keys()),
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
             str(tdp / "data.json"), str(tdp / "out.png"), str(REPO / "worker")],
            capture_output=True, text=True, timeout=120)
    for stream in (proc.stdout, proc.stderr):
        for ln in stream.splitlines():
            if ln.startswith("__R__"):
                return json.loads(ln[len("__R__"):])
    return {"ok": False, "error": f"harness no result rc={proc.returncode}",
            "traceback": (proc.stderr or proc.stdout)[-800:]}


def classify(execution: dict, request: dict) -> dict:
    """Bucket a run AND record the emitted claim shape verbatim (the point of this script)."""
    answer_text = execution.get("answer_text")
    claims = execution.get("claims") if isinstance(execution.get("claims"), list) else []
    png = execution.get("png") or 0
    shapes = [{"metric": c.get("metric"), "inputs": c.get("inputs"), "params": c.get("params"),
               "value": c.get("value"), "has_verdict": c.get("verdict") is not None,
               "window": c.get("window")}
              for c in claims if isinstance(c, dict)]
    if not answer_text:
        return {"bucket": "PLOT_ONLY" if png > 1000 else "EMPTY", "claim_shapes": shapes,
                "why": f"no answer_text (png={png}, meta_keys={execution.get('meta_keys')})"}
    grounding = run_grounding_check({"answer_text": answer_text, "claims": claims},
                                    request["history_series"])
    outcome = grounding.get("outcome")
    rec = {"claim_shapes": shapes, "answer_text": answer_text, "why": outcome,
           "answer_verification": grounding.get("answer_verification"),
           "grounding_checks": grounding.get("checks")}
    if grounding.get("withheld"):
        rec["bucket"] = "WITHHELD"
    elif outcome == "pass":
        # No claims at all → nothing to verify. `answer_verification` is absent,
        # so the card shows the answer with NO caveat. Distinct from a verified
        # answer: the value was never checked against the data. Bucketing this
        # as SERVED_VERIFIED would overstate the result.
        rec["bucket"] = "SERVED_NO_CLAIMS"
    elif outcome == "repair_soft" or str(outcome).startswith("unverified"):
        rec["bucket"] = "SERVED_UNVERIFIED"
    else:
        rec["bucket"] = "SERVED_VERIFIED"
    return rec


def run_one(client, case: str, run_n: int, request: dict, results: dict) -> None:
    prompt = CASE_SPECS[case]["prompt"]
    rec = {"case": case, "run": run_n, "attempts": []}
    code, sandbox_error = None, None
    for attempt in range(MAX_REPAIRS + 1):
        gen = (client.generate_chart_code(request, user_request=prompt) if code is None
               else client.repair_chart_code(code, sandbox_error, request, user_request=prompt))
        if not gen.get("accepted"):
            rec.update({"bucket": "PROVIDER_REJECT", "why": gen.get("code")})
            break
        code = gen["python_code"]
        execution = execute(code, request)
        if execution.get("ok"):
            rec.update(classify(execution, request))
            rec["final_code"] = code
            break
        rec["attempts"].append({"n": attempt, "error": execution.get("error")})
        if attempt == MAX_REPAIRS:
            rec.update({"bucket": "RUNTIME_EXHAUSTED", "why": execution.get("error"), "final_code": code})
            break
        sandbox_error = {"code": "runtime_error", "message": execution.get("error") or "failed",
                         "details": {"traceback": execution.get("traceback") or ""}}
    results["runs"][f"{case}-run{run_n}"] = rec
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    shapes = rec.get("claim_shapes") or []
    shape_s = "; ".join(f"{s['metric']} inputs={len(s['inputs'] or [])} params={s['params']} value={s['value']}"
                        for s in shapes) or "—"
    print(f"[{case}-run{run_n}] {rec.get('bucket')} — {rec.get('why')}\n"
          f"    claims: {shape_s}", flush=True)


def main() -> int:
    if not HA_TOKEN:
        raise SystemExit("HA_TOKEN required")
    client = mp.OllamaCompatiblePlannerClient(endpoint_url=OLLAMA_URL, planner_model=MODEL)
    results = {"meta": {"model": MODEL, "runs_per_case": RUNS, "cases": CASES,
                        "max_repairs": MAX_REPAIRS,
                        "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, "runs": {}}
    for case in CASES:
        spec = CASE_SPECS[case]
        history = [_fetch_series(eid, label, unit) for eid, label, unit in spec["entities"]]
        print(f"\n=== {case}: '{spec['prompt']}'\n    history: "
              + ", ".join(f"{s['entity_id']}={len(s['points'])}pts" for s in history), flush=True)
        request = _request(case, history)
        results["meta"].setdefault("history_points", {})[case] = {
            s["entity_id"]: len(s["points"]) for s in history}
        for run_n in range(1, RUNS + 1):
            run_one(client, case, run_n, request, results)
    buckets: dict[str, int] = {}
    for rec in results["runs"].values():
        key = f"{rec.get('case')}:{rec.get('bucket', '?')}"
        buckets[key] = buckets.get(key, 0) + 1
    print("\n=== buckets ===")
    for b, n in sorted(buckets.items()):
        print(f"  {b}: {n}")
    results["buckets"] = buckets
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
