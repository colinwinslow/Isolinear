#!/usr/bin/env python3
"""Eval-gate the correlation-answer emission rule (open-queue (ff)).

Live symptom (28th-session e2e-13/14/20 + scripts/repro_correlation_answer.py):
a correlation prompt renders the two input sensor lines but the model returns
WITHOUT an answer_text — the analysis-answer layer fires for mean/delta/
deviation/distribution/rolling but under-fires for correlation. Root cause: a
correlation is a single SCALAR with nothing new to plot, so the floor model
plots the two raw sensors, treats the chart as the deliverable, and stops
(the probe measured 3/5 plot-only runs even after the grounding fix).

Two coupled fixes land together for (ff):
  1. GROUNDING (answer_grounding.py::_compute_pearson_r) — recompute correlation
     on the shared 5-min align() grid, not the empty exact-timestamp
     intersection, so an emitted coefficient actually VERIFIES. (Deterministic;
     proven by unit tests, not this gate.)
  2. PROMPT (this gate) — a _CODEGEN_PROMPT_RULES sentence making the coefficient
     the mandatory deliverable of a correlation question, so the model emits an
     answer_text instead of plotting-and-stopping.

This gate drives the PRODUCTION codegen path against live gemma4:e4b with a
correlation prompt over two genuinely-correlated sensors, two arms:

  * without_rule — production rules minus the correlation-emission sentence
    (marker-gated surgery, rule-gate pattern) — reproduces the plot-only miss;
  * with_rule    — production rules as-is (the emission prescription).

Execution-truth judge: run the model's generated render_chart, then run the REAL
answer_grounding.run_grounding_check. The rule FIRES for a run when a correlation
answer REACHES THE USER — an answer_text is emitted AND grounding does not
withhold it. (With fix #1 in place, an emitted pearson_r claim also verifies; the
gate records that but does not require it, so the gate isolates the EMISSION
effect the prompt owns.)

Config via env: OLLAMA_URL, MODEL, EXEC_PY, RUNS (default 4), MAX_REPAIRS
(default 1), RESULTS_JSON, ONLY_ARM.
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
from custom_components.isolinear.answer_grounding import run_grounding_check  # noqa: E402

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.0.1.39:11434").rstrip("/")
MODEL = os.environ.get("MODEL", "gemma4:e4b")
EXEC_PY = os.environ.get("EXEC_PY", "/home/claude/.expenv/bin/python")
RUNS = int(os.environ.get("RUNS", "4"))
MAX_REPAIRS = int(os.environ.get("MAX_REPAIRS", "1"))
RESULTS_JSON = Path(os.environ.get("RESULTS_JSON", HERE / "prompts" / "correlation_answer_gate_results.json"))

# The correlation-emission sentence under the gate, identified by distinctive
# phrasing — fail loudly if the rule text drifts (rule-gate pattern).
EMIT_MARKER = "IMPORTANT for correlation questions"
EMIT_RE = re.compile(
    r"IMPORTANT for correlation questions .*?two sensors are correlated\.", re.S)

PROMPT = "Are the kitchen and basement temperatures correlated?"
_BASE_MS = 1782000000000  # 2026-06-29T00:00:00Z


def rules_without_emission() -> list[str]:
    hits = [i for i, r in enumerate(mp._CODEGEN_PROMPT_RULES) if EMIT_MARKER in r]
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one rule containing {EMIT_MARKER!r}, found {len(hits)}")
    rules = list(mp._CODEGEN_PROMPT_RULES)
    stripped = EMIT_RE.sub(" ", rules[hits[0]])
    if EMIT_MARKER in stripped:
        raise SystemExit("correlation-emission sentence removal failed — update EMIT_RE")
    rules[hits[0]] = stripped
    return rules


def _sensor_series(entity_id: str, label: str, base: float, phase: float, share: float) -> dict:
    """~1 day of 5-min numeric points, irregular per sensor (the two share NO
    exact timestamps — real recorder shape). A shared sinusoidal driver makes the
    sensors genuinely correlated (real r well above the 0.3 band)."""
    points = []
    step = 300 * 1000
    for i in range(288):
        ms = _BASE_MS + i * step + (0 if "kitchen" in entity_id else 37 * 1000)
        shared = 1.4 * math.sin(i / 288 * 2 * math.pi)
        own = 0.6 * math.sin(i / 288 * 2 * math.pi + phase) + 0.2 * math.sin(i / 12)
        v = base + share * shared + (1 - share) * own
        iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(ms / 1000))
        points.append({"ts": iso, "ts_epoch_ms": ms, "value": round(v, 2),
                       "raw_state": None, "quality": "ok"})
    return {"series_id": f"series-{entity_id}", "entity_id": entity_id, "label": label,
            "kind": "numeric", "unit": "°F", "points": points, "source": "recorder",
            "resolution": "raw", "source_entity_ids": [entity_id], "warnings": []}


def _history() -> list[dict]:
    return [
        _sensor_series("sensor.kitchen_ecobee_temperature", "Kitchen Temperature", 73.5, 0.0, 0.8),
        _sensor_series("sensor.basement_temperature", "Basement Temperature", 72.0, 0.9, 0.8),
    ]


def _request() -> dict:
    return {
        "chart_spec": {
            "chart_id": "kitchen_basement_corr", "chart_type": "time_series",
            "title": "Kitchen and Basement Temperature",
            "time_range": {"type": "relative", "duration": "2d"},
            "series": [
                {"series_id": "kitchen", "label": "Kitchen Temperature", "role": "primary",
                 "render_as": "line", "transform": {"operation": "none", "window": None},
                 "unit": "°F", "source": {"type": "entity",
                 "entity_id": "sensor.kitchen_ecobee_temperature", "attribute": None}},
                {"series_id": "basement", "label": "Basement Temperature", "role": "primary",
                 "render_as": "line", "transform": {"operation": "none", "window": None},
                 "unit": "°F", "source": {"type": "entity",
                 "entity_id": "sensor.basement_temperature", "attribute": None}},
            ],
            "overlays": [], "x_axis": {"type": "time"}, "y_axis": {},
        },
        "history_series": _history(), "derived_intervals": [],
        "output": {"format": "png", "width": 800, "height": 480},
    }


_HARNESS = r'''
import json, sys, traceback, warnings
warnings.simplefilter("ignore")
sys.path.insert(0, sys.argv[4])  # repo worker/ dir → isolinear_analysis importable
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
    print("__R__" + json.dumps({"ok": True,
        "answer_text": meta.get("answer_text"),
        "claims": meta.get("claims"),
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
    """The (ff) target: a correlation ANSWER reaches the user. Fire when an
    answer_text is emitted AND grounding does not withhold it. Record whether an
    emitted pearson_r claim verified (the grounding fix's job) without requiring
    it, so the gate isolates the EMISSION effect the prompt owns."""
    v = {"fired": False, "why": ""}
    answer_text = execution.get("answer_text")
    claims = execution.get("claims") if isinstance(execution.get("claims"), list) else []
    if not answer_text:
        v["why"] = "no answer_text (plot only) — the (ff) miss"
        return v
    grounding = run_grounding_check(
        {"answer_text": answer_text, "claims": claims}, request["history_series"])
    outcome = grounding.get("outcome")
    withheld = bool(grounding.get("withheld"))
    synth = grounding.get("synthetic_error") or {}
    corr_claims = [c for c in claims if isinstance(c, dict) and c.get("metric") == "pearson_r"]
    v.update({"outcome": outcome, "withheld": withheld, "synthetic_code": synth.get("code"),
              "answer_text": answer_text, "verified": outcome == "verified",
              "corr_value": corr_claims[0].get("value") if corr_claims else None})
    if withheld:
        v["why"] = f"answer WITHHELD ({synth.get('code') or outcome})"
        return v
    v["fired"] = True
    v["why"] = f"served: outcome={outcome}, corr={v['corr_value']}"
    return v


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
            rec["verdict"] = judge(execution, request)
            rec["fired"] = rec["verdict"]["fired"]
            att["answer_text"] = execution.get("answer_text")
            att["claims"] = execution.get("claims")
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
    print(f"[{key}] {'SERVED' if rec['fired'] else 'miss'} executed={rec['executed']} "
          f"attempts={len(rec['attempts'])} — {vv.get('why', 'n/a')}", flush=True)


def main() -> int:
    arms = {"without_rule": rules_without_emission(),
            "with_rule": list(mp._CODEGEN_PROMPT_RULES)}
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
        t = tally.setdefault(rec["arm"], {"runs": 0, "executed": 0, "served": 0, "verified": 0})
        t["runs"] += 1
        t["executed"] += bool(rec.get("executed"))
        t["served"] += bool(rec.get("fired"))
        t["verified"] += bool((rec.get("verdict") or {}).get("verified"))
    print("\n=== tally ===")
    for arm, t in sorted(tally.items()):
        print(f"{arm}: {t['served']}/{t['runs']} served a correlation answer "
              f"({t['verified']} verified, {t['executed']} executed)")
    results["tally"] = tally
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
