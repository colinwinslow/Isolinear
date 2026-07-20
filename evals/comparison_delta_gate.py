#!/usr/bin/env python3
"""Eval gate for the two-sensor COMPARISON answer (live e2e-08).

The gap (live-reproduced on the deployed 0.2.45 before designing the fix — see
`scripts/repro_delta_rolling_grounding.py`): "Compare the kitchen and basement
humidity" renders both lines correctly but the answer channel does not fire.
Across 7 executed production-path runs, ZERO emitted a claim; the model either
answered qualitatively ("generally higher") or stated a number with no claim at
all. A claimless answer grounds as `outcome: pass` with answer_verification
ABSENT — served with NO caveat and never checked against the data, so a wrong
number reads as an unqualified fact (one run said "4.0 %" where the aligned
truth was 4.63).

The fix is two-part, the same shape as the (ff) correlation fix:
  1. GROUNDING — `_compute_delta` for two inputs now recomputes the average
     difference on the shared ADR-0036 `align()` grid (it previously returned
     last-minus-first of inputs[0], a different quantity entirely). Verified
     against pandas `align()` on live data to 4 decimals (4.6387).
  2. PROMPT (this gate) — a `_CODEGEN_PROMPT_RULES` sentence making the average
     difference the mandatory deliverable of a comparison question, and pinning
     the subtraction ORDER so the claim and the integration's independent
     reference are the same quantity.

Arms:
  * with_rule    — production `_CODEGEN_PROMPT_RULES`
  * without_rule — production rules minus the comparison-emission sentence

Judge = EXECUTION TRUTH, not a regex: the generated code runs against REAL
recorder history and the REAL `run_grounding_check` must SERVE the answer
(withheld=False) AND return answer_verification == "verified" — which can only
happen if a delta claim was emitted with the right inputs order and a value
matching the independent reference.

Real data (not synthetic) on purpose: the 0.2.41 synthetic correlation probe
reproduced the WRONG failure ([[feedback-e2e-over-synthetic]]).

Env: HA_URL, HA_TOKEN (required), OLLAMA_URL, MODEL, EXEC_PY, RUNS (default 3
     per arm), MAX_REPAIRS (default 2), ONLY_ARM, RESULTS_JSON.
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
    _compute_delta,
    run_grounding_check,
)

HA_URL = os.environ.get("HA_URL", "http://10.0.1.200:8123").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.0.1.39:11434").rstrip("/")
MODEL = os.environ.get("MODEL", "gemma4:e4b")
EXEC_PY = os.environ.get("EXEC_PY", "/home/claude/.expenv/bin/python")
RUNS = int(os.environ.get("RUNS", "3"))
MAX_REPAIRS = int(os.environ.get("MAX_REPAIRS", "2"))
RESULTS_JSON = Path(os.environ.get("RESULTS_JSON", HERE / "prompts" / "comparison_delta_gate_results.json"))

# The comparison-emission sentence under the gate, identified by distinctive
# phrasing — fail loudly if the rule text drifts (rule-gate pattern).
EMIT_MARKER = "IMPORTANT for two-sensor comparison questions"
EMIT_RE = re.compile(
    r"IMPORTANT for two-sensor comparison questions .*?not the difference at a "
    r"single instant\.", re.S)

PROMPT = "Compare the kitchen and basement humidity over the last 2 days"
KITCHEN_H = "sensor.kitchen_ecobee_humidity"
BASEMENT_H = "sensor.basement_humidity"


def rules_without_emission() -> list[str]:
    hits = [i for i, r in enumerate(mp._CODEGEN_PROMPT_RULES) if EMIT_MARKER in r]
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one rule containing {EMIT_MARKER!r}, found {len(hits)}")
    rules = list(mp._CODEGEN_PROMPT_RULES)
    stripped = EMIT_RE.sub(" ", rules[hits[0]])
    if EMIT_MARKER in stripped:
        raise SystemExit("comparison-emission sentence removal failed — update EMIT_RE")
    rules[hits[0]] = stripped
    return rules


def _fetch_series(entity_id: str, label: str) -> dict:
    start = (datetime.now(timezone.utc) - timedelta(days=2)).replace(microsecond=0).isoformat()
    url = f"{HA_URL}/api/history/period/{start}?filter_entity_id={urllib.parse.quote(entity_id)}&minimal_response"
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + HA_TOKEN})
    raw = json.load(urllib.request.urlopen(req, timeout=40))
    points, unit = [], "%"
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
        {"series_id": "kitchen", "label": "Kitchen Humidity", "role": "primary", "render_as": "line",
         "transform": {"operation": "none", "window": None}, "unit": "%",
         "source": {"type": "entity", "entity_id": KITCHEN_H, "attribute": None}},
        {"series_id": "basement", "label": "Basement Humidity", "role": "primary", "render_as": "line",
         "transform": {"operation": "none", "window": None}, "unit": "%",
         "source": {"type": "entity", "entity_id": BASEMENT_H, "attribute": None}},
    ]
    return {
        "chart_spec": {
            "chart_id": "kitchen_basement_humidity", "chart_type": "time_series",
            "title": "Comparison of Kitchen and Basement Humidity",
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
    delta_claims = [c for c in claims if isinstance(c, dict) and c.get("metric") == "delta"]
    rec = {"answer_text": answer_text, "png": png,
           "claim_metrics": [c.get("metric") for c in claims if isinstance(c, dict)],
           "delta_value": delta_claims[0].get("value") if delta_claims else None,
           "delta_inputs": delta_claims[0].get("inputs") if delta_claims else None}
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
          f"({rec.get('why')})  delta={rec.get('delta_value')} inputs={rec.get('delta_inputs')}",
          flush=True)


def main() -> int:
    if not HA_TOKEN:
        raise SystemExit("HA_TOKEN required")
    history = [_fetch_series(KITCHEN_H, "Kitchen Humidity"), _fetch_series(BASEMENT_H, "Basement Humidity")]
    request = _request(history)
    reference = _compute_delta([KITCHEN_H, BASEMENT_H], None, {}, history)
    print(f"real history: kitchen={len(history[0]['points'])}pts basement={len(history[1]['points'])}pts")
    print(f"independent reference (aligned avg difference): {reference:.4f}\n", flush=True)

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
