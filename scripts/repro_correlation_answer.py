#!/usr/bin/env python3
"""Repro probe for open-queue (ff): the correlation-answer gap.

Live symptom (28th-session e2e-13/14/20): correlation prompts render the two
input series but the analysis-answer layer never serves a computed Pearson r +
verdict. mean/delta/deviation/distribution/rolling all serve grounded answers.

This probe drives the PRODUCTION codegen path (real generate_chart_code +
_CODEGEN_PROMPT_RULES) against live gemma4:e4b with a correlation prompt, then
executes the returned code in the sandbox exec env and runs the REAL
answer_grounding.run_grounding_check. It reports, per run, exactly where the
answer lands: not-emitted (plot only), unsafe/runtime (Pillow fallback tail),
emitted-but-unverified (grounding can't confirm the coefficient), or served+
verified.

Diagnostic only — no arms, no pass/fail. Config via env:
  OLLAMA_URL (default http://10.0.1.39:11434), MODEL (gemma4:e4b),
  EXEC_PY (/home/claude/.expenv/bin/python), RUNS (default 3), MAX_REPAIRS (2).
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
from custom_components.isolinear.answer_grounding import run_grounding_check  # noqa: E402

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.0.1.39:11434").rstrip("/")
MODEL = os.environ.get("MODEL", "gemma4:e4b")
EXEC_PY = os.environ.get("EXEC_PY", "/home/claude/.expenv/bin/python")
RUNS = int(os.environ.get("RUNS", "3"))
MAX_REPAIRS = int(os.environ.get("MAX_REPAIRS", "2"))
RESULTS_JSON = Path(os.environ.get("RESULTS_JSON", HERE.parent / "evals" / "prompts" / "repro_correlation_answer_results.json"))

PROMPT = "Are the kitchen and basement temperatures correlated?"
_BASE_MS = 1782000000000  # 2026-06-29T00:00:00Z


def _sensor_series(entity_id: str, label: str, base: float, phase: float, corr_share: float) -> dict:
    """~1 day of 5-min numeric points, irregular per sensor (the two share NO
    exact timestamps, mirroring real recorder data). corr_share blends a shared
    driver so the sensors are genuinely correlated (real r well above 0)."""
    points = []
    step = 300 * 1000
    for i in range(288):
        ms = _BASE_MS + i * step + (0 if "kitchen" in entity_id else 37 * 1000)
        shared = 1.4 * math.sin(i / 288 * 2 * math.pi)
        own = 0.6 * math.sin(i / 288 * 2 * math.pi + phase) + 0.2 * math.sin(i / 12)
        v = base + corr_share * shared + (1 - corr_share) * own
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


def classify(execution: dict, request: dict) -> dict:
    answer_text = execution.get("answer_text")
    claims = execution.get("claims") if isinstance(execution.get("claims"), list) else []
    if not answer_text:
        return {"bucket": "NOT_EMITTED", "why": "no answer_text (plot only)", "claims": claims}
    grounding = run_grounding_check(
        {"answer_text": answer_text, "claims": claims}, request["history_series"])
    outcome = grounding.get("outcome")
    withheld = bool(grounding.get("withheld"))
    synth = grounding.get("synthetic_error") or {}
    corr_claims = [c for c in claims if isinstance(c, dict) and c.get("metric") == "pearson_r"]
    info = {"outcome": outcome, "withheld": withheld, "synthetic_code": synth.get("code"),
            "answer_text": answer_text, "n_claims": len(claims),
            "corr_claim_value": corr_claims[0].get("value") if corr_claims else None}
    if withheld:
        info["bucket"] = "WITHHELD"
        info["why"] = f"withheld ({synth.get('code') or outcome})"
    elif outcome and str(outcome).startswith("unverified"):
        info["bucket"] = "EMITTED_UNVERIFIED"
        info["why"] = f"served but grounding could not verify: {outcome}"
    else:
        info["bucket"] = "SERVED_VERIFIED"
        info["why"] = f"served + verified: {outcome}"
    return info


def run_one(run_n: int, results: dict) -> None:
    key = f"run{run_n}"
    request = _request()
    client = mp.OllamaCompatiblePlannerClient(endpoint_url=OLLAMA_URL, planner_model=MODEL)
    rec = {"run": run_n, "attempts": []}
    code, sandbox_error = None, None
    for attempt in range(MAX_REPAIRS + 1):
        t0 = time.time()
        gen = (client.generate_chart_code(request, user_request=PROMPT) if code is None
               else client.repair_chart_code(code, sandbox_error, request, user_request=PROMPT))
        gen_s = round(time.time() - t0, 1)
        if not gen.get("accepted"):
            rec["attempts"].append({"n": attempt, "gen_s": gen_s, "provider_failure": gen.get("code")})
            rec["bucket"] = "PROVIDER_REJECT"
            rec["why"] = f"codegen not accepted: {gen.get('code')}"
            break
        code = gen["python_code"]
        execution = execute(code, request)
        att = {"n": attempt, "gen_s": gen_s, "loc": len(code.splitlines()), "ok": execution.get("ok")}
        if execution.get("ok"):
            info = classify(execution, request)
            rec.update(info)
            rec["final_code"] = code
            att["answer_text"] = execution.get("answer_text")
            rec["attempts"].append(att)
            break
        att["error"] = execution.get("error")
        rec["attempts"].append(att)
        if attempt == MAX_REPAIRS:
            rec["bucket"] = "RUNTIME_EXHAUSTED"
            rec["why"] = f"exec failed all attempts: {execution.get('error')}"
            rec["final_code"] = code
            break
        sandbox_error = {"code": "runtime_error", "message": execution.get("error") or "failed",
                         "details": {"traceback": execution.get("traceback") or ""}}
    results["runs"][key] = rec
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    print(f"[{key}] {rec.get('bucket')} — {rec.get('why')}"
          f"{'  corr=' + str(rec.get('corr_claim_value')) if rec.get('corr_claim_value') is not None else ''}",
          flush=True)


def main() -> int:
    results = {"meta": {"model": MODEL, "ollama": OLLAMA_URL, "prompt": PROMPT,
                        "runs": RUNS, "max_repairs": MAX_REPAIRS,
                        "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
               "runs": {}}
    for run_n in range(1, RUNS + 1):
        run_one(run_n, results)
    buckets: dict[str, int] = {}
    for rec in results["runs"].values():
        buckets[rec.get("bucket", "?")] = buckets.get(rec.get("bucket", "?"), 0) + 1
    print("\n=== buckets ===")
    for b, n in sorted(buckets.items()):
        print(f"  {b}: {n}")
    results["buckets"] = buckets
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
