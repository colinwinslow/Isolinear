#!/usr/bin/env python3
"""Eval gate for the cross-sensor SMOOTHED-AVERAGE emission fidelity fix.

The gap (live-reproduced on deployed 0.2.46 BEFORE designing the fix — see
`scripts/repro_delta_rolling_grounding.py`, case `rolling_cross`, 4/4 WITHHELD):
"Show the average of the kitchen and basement temperatures smoothed with a
rolling average over the last 2 days" made gemma compute

    avg = align(...).mean(axis=1)
    rolling = avg.rolling(window='2D', min_periods=1).mean()
    value = rolling.mean()          # ← the mean OF a rolling average

and emit it under a {'metric': 'mean', 'inputs': [kitchen, basement]} claim. The
mean of a rolling average is a different, window-dependent quantity — with a
window near the query span and min_periods=1 it is edge-weighted ~0.11 °F off the
plain mean (measured on live data: plain 73.7497 vs mean-of-2d-rolling 73.6383,
gap 0.1114 ≫ the 0.05 tolerance). So the REAL `run_grounding_check` recomputed the
plain cross-sensor mean via `_compute_mean` and WITHHELD a correct-looking answer.

The fix is emission-only (grounding is behaving correctly and stays untouched),
the same family as the 0.2.44 correlation `basis` fix: a `_CODEGEN_PROMPT_RULES`
sentence pins the stated average to the RAW aligned frame (frame.mean(axis=1)
.mean()) — smoothing applies only to the plotted line — so the {'metric':'mean'}
claim recomputes to the same quantity and verifies.

Arms:
  * with_rule    — production `_CODEGEN_PROMPT_RULES`
  * without_rule — production rules minus the smoothed-average pin sentence
                   (the positive control: this must reproduce the withhold)

Judge = EXECUTION TRUTH, not a regex: the generated code runs against REAL
recorder history and the REAL `run_grounding_check` must SERVE (withheld=False)
AND return answer_verification == "verified" — only possible if the stated
average equals the plain cross-sensor mean within tolerance.

Real data (not synthetic) on purpose: the 0.2.41 synthetic correlation probe
reproduced the WRONG failure ([[feedback-e2e-over-synthetic]]). A blind pass
proves nothing without the without_rule control ([[feedback-negative-scan-needs-
control]]).

Env: HA_URL, HA_TOKEN (required), OLLAMA_URL, MODEL, EXEC_PY, RUNS (default 3
     per arm), MAX_REPAIRS (default 2), ONLY_ARM, RESULTS_JSON.

EXEC_PY MUST run pandas 2.x to match the deployed worker (`worker/requirements.txt`
pins `pandas>=2,<3`). The default `/home/claude/.expenv` drifted to pandas 3.0.x,
which REJECTS uppercase offset aliases like '6H' — turning a real production
mean-of-rolling WITHHELD into a spurious runtime error and muddying the without_rule
control. Point EXEC_PY at a pandas-2.x venv (e.g. /home/claude/.workerenv) with
`worker/` importable for isolinear_analysis. [[feedback-e2e-over-synthetic]].
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
from custom_components.isolinear.answer_grounding import (  # noqa: E402
    _compute_mean,
    run_grounding_check,
)

HA_URL = os.environ.get("HA_URL", "http://10.0.1.200:8123").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.0.1.39:11434").rstrip("/")
MODEL = os.environ.get("MODEL", "gemma4:e4b")
EXEC_PY = os.environ.get("EXEC_PY", "/home/claude/.expenv/bin/python")
RUNS = int(os.environ.get("RUNS", "3"))
MAX_REPAIRS = int(os.environ.get("MAX_REPAIRS", "2"))
RESULTS_JSON = Path(os.environ.get("RESULTS_JSON", HERE / "prompts" / "rolling_avg_emission_gate_results.json"))

# The smoothed-average pin sentence under the gate, identified by distinctive
# phrasing — fail loudly if the rule text drifts (rule-gate pattern).
EMIT_MARKER = "asks for BOTH an average and smoothing"
EMIT_RE = re.compile(
    r"When the request asks for BOTH an average and smoothing .*?withholding "
    r"your answer\.", re.S)

PROMPT = "Show the average of the kitchen and basement temperatures smoothed with a rolling average over the last 2 days"
KITCHEN_T = "sensor.kitchen_ecobee_temperature"
BASEMENT_T = "sensor.basement_temperature"


def rules_without_emission() -> list[str]:
    hits = [i for i, r in enumerate(mp._CODEGEN_PROMPT_RULES) if EMIT_MARKER in r]
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one rule containing {EMIT_MARKER!r}, found {len(hits)}")
    rules = list(mp._CODEGEN_PROMPT_RULES)
    stripped = EMIT_RE.sub(" ", rules[hits[0]])
    if EMIT_MARKER in stripped:
        raise SystemExit("smoothed-average pin removal failed — update EMIT_RE")
    rules[hits[0]] = stripped
    return rules


def _fetch_series(entity_id: str, label: str) -> dict:
    start = (datetime.now(timezone.utc) - timedelta(days=2)).replace(microsecond=0).isoformat()
    url = f"{HA_URL}/api/history/period/{start}?filter_entity_id={urllib.parse.quote(entity_id)}&minimal_response"
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + HA_TOKEN})
    raw = json.load(urllib.request.urlopen(req, timeout=40))
    points, unit = [], "°F"
    for s in (raw[0] if raw else []):
        st = s.get("state")
        if st in (None, "unknown", "unavailable") or not re.match(r"^-?\d+(\.\d+)?$", str(st)):
            continue
        ts = s.get("last_changed") or s.get("last_updated")
        if not ts:
            continue
        ms = int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000)
        points.append({"ts": ts, "ts_epoch_ms": ms, "value": round(float(st), 2),
                       "raw_state": st, "quality": "ok"})
        unit = s.get("attributes", {}).get("unit_of_measurement") or unit
    return {"series_id": f"series-{entity_id}", "entity_id": entity_id, "label": label,
            "kind": "numeric", "unit": unit, "points": points, "source": "recorder",
            "resolution": "raw", "source_entity_ids": [entity_id], "warnings": []}


def _request(history: list[dict]) -> dict:
    series = [
        {"series_id": "kitchen", "label": "Kitchen Temperature", "role": "primary", "render_as": "line",
         "transform": {"operation": "none", "window": None}, "unit": "°F",
         "source": {"type": "entity", "entity_id": KITCHEN_T, "attribute": None}},
        {"series_id": "basement", "label": "Basement Temperature", "role": "primary", "render_as": "line",
         "transform": {"operation": "none", "window": None}, "unit": "°F",
         "source": {"type": "entity", "entity_id": BASEMENT_T, "attribute": None}},
    ]
    return {
        "chart_spec": {
            "chart_id": "kitchen_basement_temp_rolling", "chart_type": "time_series",
            "title": "Kitchen and Basement Temperature — Rolling Average",
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


def judge(execution: dict, request: dict) -> dict:
    """Execution truth: the REAL grounding check must SERVE and VERIFY the answer."""
    answer_text = execution.get("answer_text")
    claims = execution.get("claims") if isinstance(execution.get("claims"), list) else []
    png = execution.get("png") or 0
    mean_claims = [c for c in claims if isinstance(c, dict) and c.get("metric") == "mean"]
    rec = {"answer_text": answer_text, "png": png,
           "claim_metrics": [c.get("metric") for c in claims if isinstance(c, dict)],
           "mean_value": mean_claims[0].get("value") if mean_claims else None,
           "mean_inputs": mean_claims[0].get("inputs") if mean_claims else None}
    if not answer_text:
        rec.update({"served": False, "verified": False,
                    "why": "PLOT_ONLY" if png > 1000 else "EMPTY"})
        return rec
    grounding = run_grounding_check({"answer_text": answer_text, "claims": claims},
                                    request["history_series"])
    rec["served"] = not grounding.get("withheld")
    rec["verified"] = grounding.get("answer_verification") == "verified"
    # `pass` (no claims) is served but NEVER checked — explicitly not a win.
    rec["why"] = grounding.get("outcome")
    return rec


def run_one(client, arm: str, run_n: int, request: dict, results: dict) -> None:
    rec = {"arm": arm, "run": run_n, "attempts": []}
    code, sandbox_error = None, None
    for attempt in range(MAX_REPAIRS + 1):
        gen = (client.generate_chart_code(request, user_request=PROMPT) if code is None
               else client.repair_chart_code(code, sandbox_error, request, user_request=PROMPT))
        if not gen.get("accepted"):
            rec.update({"served": False, "verified": False, "why": f"PROVIDER_REJECT:{gen.get('code')}"})
            break
        code = gen["python_code"]
        execution = execute(code, request)
        if execution.get("ok"):
            rec.update(judge(execution, request))
            rec["final_code"] = code
            break
        rec["attempts"].append({"n": attempt, "error": execution.get("error")})
        if attempt == MAX_REPAIRS:
            rec.update({"served": False, "verified": False,
                        "why": f"RUNTIME_EXHAUSTED:{execution.get('error')}", "final_code": code})
            break
        sandbox_error = {"code": "runtime_error", "message": execution.get("error") or "failed",
                         "details": {"traceback": execution.get("traceback") or ""}}
    results["runs"][f"{arm}-run{run_n}"] = rec
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    print(f"[{arm}::run{run_n}] served={rec.get('served')} verified={rec.get('verified')} "
          f"({rec.get('why')})  mean={rec.get('mean_value')} inputs={rec.get('mean_inputs')}",
          flush=True)


def _assert_exec_pandas_2x() -> None:
    """Fail loudly if EXEC_PY runs pandas 3.x — it rejects '6H' and turns a real
    mean-of-rolling WITHHELD into a spurious runtime error, silently corrupting
    the without_rule control ([[isolinear-exec-env-pandas-drift]])."""
    try:
        ver = subprocess.run([EXEC_PY, "-c", "import pandas; print(pandas.__version__)"],
                             capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"cannot probe EXEC_PY pandas version ({EXEC_PY}): {exc}")
    if not ver.startswith("2."):
        raise SystemExit(
            f"EXEC_PY ({EXEC_PY}) runs pandas {ver!r}, but the deployed worker pins "
            f"pandas>=2,<3. A pandas-3 exec env rejects '6H' and corrupts the "
            f"without_rule control — point EXEC_PY at a pandas-2.x venv "
            f"(e.g. /home/claude/.workerenv/bin/python).")


def main() -> int:
    if not HA_TOKEN:
        raise SystemExit("HA_TOKEN required")
    _assert_exec_pandas_2x()
    history = [_fetch_series(KITCHEN_T, "Kitchen Temperature"), _fetch_series(BASEMENT_T, "Basement Temperature")]
    request = _request(history)
    reference = _compute_mean([KITCHEN_T, BASEMENT_T], None, {}, history)
    print(f"real history: kitchen={len(history[0]['points'])}pts basement={len(history[1]['points'])}pts")
    print(f"independent reference (plain cross-sensor mean): {reference:.4f}\n", flush=True)

    client = mp.OllamaCompatiblePlannerClient(endpoint_url=OLLAMA_URL, planner_model=MODEL)
    arms = {"without_rule": rules_without_emission(), "with_rule": list(mp._CODEGEN_PROMPT_RULES)}
    only_arm = os.environ.get("ONLY_ARM", "").strip()
    if only_arm:
        arms = {only_arm: arms[only_arm]}
    results = {"meta": {"model": MODEL, "prompt": PROMPT, "runs_per_arm": RUNS,
                        "max_repairs": MAX_REPAIRS, "reference": reference,
                        "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, "runs": {}}
    original = list(mp._CODEGEN_PROMPT_RULES)
    try:
        for arm, rules in arms.items():
            mp._CODEGEN_PROMPT_RULES = rules
            for run_n in range(1, RUNS + 1):
                run_one(client, arm, run_n, request, results)
    finally:
        mp._CODEGEN_PROMPT_RULES = original

    print("\n=== summary ===")
    summary: dict[str, dict] = {}
    for rec in results["runs"].values():
        s = summary.setdefault(rec["arm"], {"served": 0, "verified": 0, "n": 0})
        s["n"] += 1
        s["served"] += 1 if rec.get("served") else 0
        s["verified"] += 1 if rec.get("verified") else 0
    for arm, s in summary.items():
        print(f"  {arm}: served {s['served']}/{s['n']}, VERIFIED {s['verified']}/{s['n']}")
    results["summary"] = summary
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
