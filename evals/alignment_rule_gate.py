#!/usr/bin/env python3
"""Eval-gate the ADR-0034 follow-up alignment rule (live e2e-11/12/13 root).

The 0.2.23 live e2e run showed the newly-firing analysis layer combining
irregular series wrongly: the cross-sensor mean (e2e-11) swung ABOVE both
inputs (a union-index/NaN artifact — impossible for a true mean), the delta
(e2e-12) came back empty/unplottable, and correlation (e2e-13) found "no
common timestamps" (the 8th-session exact-intersection gap, live). Root
cause: the production codegen rules carried the D9 epoch-ms lesson but never
the 4th-session benchmark's OTHER data-loading lesson — "sampling is
IRREGULAR and differs per entity; resample/align before combining" (it lived
only in the benchmark's system prompt). The analysis-intent probe used
perfectly aligned grids for all series, so it could not see this class.

This gate drives the PRODUCTION codegen path against live gemma4:e4b with
IRREGULAR per-entity sampling (different step + deterministic jitter + phase
offset per sensor), two arms:

  * without_alignment — production rules minus the alignment sentence
    (marker-gated surgery, rule-gate pattern) — the 0.2.23-shipped behavior;
  * with_alignment    — production rules as-is (the alignment prescription).

Execution-truth judges tuned to the observed live failures:
  * t_mean — a derived line with mean ≈ combined mean AND bounded std (the
    union artifact swings between the raw series → std blows past the true
    mean's); catches e2e-11's impossible spikes.
  * t_delta — answer_text carries the known delta (a naive exact-join on
    irregular indexes yields empty → no number).
  * corr — a coefficient actually computes (exact-timestamp intersection on
    irregular series is empty → "insufficient data", the e2e-13 failure).

Config via env: OLLAMA_URL, MODEL, EXEC_PY, RUNS (default 2), MAX_REPAIRS
(default 2), RESULTS_JSON, ONLY_CASES, ONLY_ARM.
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
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

from custom_components.isolinear import model_provider as mp  # noqa: E402

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.0.1.39:11434").rstrip("/")
MODEL = os.environ.get("MODEL", "gemma4:e4b")
EXEC_PY = os.environ.get("EXEC_PY", "/home/claude/.expenv/bin/python")
RUNS = int(os.environ.get("RUNS", "2"))
MAX_REPAIRS = int(os.environ.get("MAX_REPAIRS", "2"))
RESULTS_JSON = Path(os.environ.get("RESULTS_JSON", HERE / "prompts" / "alignment_rule_gate_results.json"))

# The alignment sentence under the gate, identified by distinctive phrasing —
# fail loudly if the rule text drifts (rule-gate pattern).
ALIGN_MARKER = "sampled IRREGULARLY at"
ALIGN_RE = re.compile(
    r" Each entity's points are sampled IRREGULARLY.*?everything downstream becomes "
    r"NaN\)\.", re.S)


def rules_without_alignment() -> list[str]:
    hits = [i for i, r in enumerate(mp._CODEGEN_PROMPT_RULES) if ALIGN_MARKER in r]
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one rule containing {ALIGN_MARKER!r}, found {len(hits)}")
    rules = list(mp._CODEGEN_PROMPT_RULES)
    stripped = ALIGN_RE.sub(" ", rules[hits[0]])
    if ALIGN_MARKER in stripped:
        raise SystemExit("alignment sentence removal failed — update ALIGN_RE")
    rules[hits[0]] = stripped
    return rules


# ------------------------ irregular production-shaped data -------------------
_BASE_MS = 1751500800000  # 2026-07-03T00:00:00Z


def _pt(offset_s: float, value) -> dict:
    ms = _BASE_MS + int(offset_s * 1000)
    iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(ms / 1000))
    return {"ts": iso, "ts_epoch_ms": ms, "value": round(value, 2), "raw_state": str(round(value, 2)),
            "quality": "ok"}


def _irregular_series(sid, eid, label, base, amp, *, hours, step_s, jitter_s, phase_s) -> dict:
    """Sine series on an IRREGULAR grid: fixed step + deterministic jitter,
    offset by phase_s so no two sensors share a single timestamp."""
    pts = []
    t = float(phase_s)
    while t < hours * 3600:
        jitter = ((int(t) * 2654435761) % 1000) / 1000.0 * 2 * jitter_s - jitter_s
        at = max(0.0, t + jitter)
        v = base + amp * math.sin((at / (hours * 3600)) * 2 * math.pi * (hours / 24) - 1.6)
        pts.append(_pt(at, v))
        t += step_s
    return {"series_id": sid, "entity_id": eid, "label": label, "kind": "numeric",
            "unit": "°F", "points": pts, "source_entity_ids": [eid], "warnings": []}


def _series_spec(sid, label, eid, role="primary") -> dict:
    return {"series_id": sid, "label": label, "role": role, "render_as": "line",
            "unit": "°F", "source": {"type": "entity", "entity_id": eid}}


def _request(title, series_specs, series_list) -> dict:
    return {"chart_spec": {"chart_id": "gate", "chart_type": "time_series", "title": title,
                           "time_range": {"type": "relative", "duration": "24h"},
                           "series": series_specs, "overlays": []},
            "history_series": series_list, "derived_intervals": [],
            "output": {"format": "png", "width": 800, "height": 480}}


def build_cases() -> dict[str, dict]:
    # kitchen: 7-min step, ±90s jitter; basement: 11-min step, ±150s jitter,
    # 3-min phase offset → zero shared timestamps (exact intersection is empty).
    k = _irregular_series("kitchen", "sensor.kitchen_temperature", "Kitchen Temperature",
                          71, 4, hours=48, step_s=420, jitter_s=90, phase_s=0)
    b = _irregular_series("basement", "sensor.basement_temperature", "Basement Temperature",
                          64, 2, hours=48, step_s=660, jitter_s=150, phase_s=180)
    two = [_series_spec("kitchen", "Kitchen", "sensor.kitchen_temperature"),
           _series_spec("basement", "Basement", "sensor.basement_temperature", role="secondary")]
    return {
        # e2e-11 twin. True combined mean 67.5, true derived std ≈ 2.1; the
        # union artifact swings 64↔71 (std ≥ 3.4) and spikes outside the mean.
        "t_mean": {
            "prompt": "What is the average of the kitchen and basement temperatures over the last day?",
            "request": _request("Average of kitchen and basement temperatures", two, [k, b]),
            "judge": {"kind": "derived_mean", "target": 67.5, "mean_tol": 1.0, "max_std": 2.8},
        },
        # e2e-12 twin. Delta 7±2; exact-join on disjoint indexes → empty → no number.
        "t_delta": {
            "prompt": "How much warmer is the kitchen than the basement over the last 2 days?",
            "request": _request("Kitchen vs basement difference", two, [k, b]),
            "judge": {"kind": "answer_number", "target": 7.0, "tol": 2.0},
        },
        # e2e-13 twin. Same-phase sines → r ≈ +1; exact intersection is EMPTY.
        "corr": {
            "prompt": "Are the kitchen and basement temperatures correlated over the last 2 days?",
            "request": _request("Kitchen and basement correlation", two, [k, b]),
            "judge": {"kind": "correlation", "min_abs": 0.5},
        },
    }


# ---------------------------- execution harness ------------------------------
_HARNESS = r'''
import json, sys, traceback, warnings
warnings.simplefilter("ignore")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.close = lambda *a, **k: None

code_file, data_file, out_png = sys.argv[1], sys.argv[2], sys.argv[3]
data = json.load(open(data_file))

def _stats(values):
    vals = [float(v) for v in values if v == v]
    if not vals:
        return None
    n = len(vals); mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / n
    return {"n": n, "mean": mean, "std": var ** 0.5, "min": min(vals), "max": max(vals)}

def _san(o):
    try: return float(o)
    except Exception: return str(o)

try:
    ns = {}
    exec(open(code_file).read(), ns)
    meta = ns["render_chart"](data, out_png)
    lines = []
    for num in plt.get_fignums():
        for ax in plt.figure(num).axes:
            for line in ax.get_lines():
                st = _stats(line.get_ydata())
                if st:
                    st["label"] = str(line.get_label())
                    lines.append(st)
    import os
    print("__R__" + json.dumps({"ok": True,
        "answer_text": meta.get("answer_text") if isinstance(meta, dict) else None,
        "claims": meta.get("claims") if isinstance(meta, dict) else None,
        "lines": lines,
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


_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def judge(case: dict, execution: dict) -> dict:
    spec = case["judge"]
    kind = spec["kind"]
    lines = execution.get("lines") or []
    answer = execution.get("answer_text")
    claims = execution.get("claims") or []
    nums = [float(t) for t in _NUM_RE.findall(answer)] if isinstance(answer, str) else []
    v = {"kind": kind, "fired": False, "why": "", "answer_text": answer}

    if kind == "derived_mean":
        hits = [ln for ln in lines
                if abs(ln["mean"] - spec["target"]) <= spec["mean_tol"] and ln["std"] <= spec["max_std"]]
        artifact = [ln for ln in lines
                    if abs(ln["mean"] - spec["target"]) <= spec["mean_tol"] and ln["std"] > spec["max_std"]]
        v["fired"] = bool(hits)
        v["why"] = (f"derived line mean {hits[0]['mean']:.2f} std {hits[0]['std']:.2f} (clean)" if hits
                    else f"UNION ARTIFACT: mean ok but std {artifact[0]['std']:.2f} > {spec['max_std']}" if artifact
                    else f"no derived line: {[(round(l['mean'],1), round(l['std'],2)) for l in lines]}")
    elif kind == "answer_number":
        hits = [n for n in nums if abs(n - spec["target"]) <= spec["tol"]]
        claim_hits = [c for c in claims if isinstance(c, dict) and isinstance(c.get("value"), (int, float))
                      and abs(c["value"] - spec["target"]) <= spec["tol"]]
        v["fired"] = bool(hits or claim_hits)
        v["why"] = (f"answer carries {hits[0]:.2f}" if hits
                    else f"claim {claim_hits[0]['value']:.2f}" if claim_hits
                    else f"no number near {spec['target']} in {answer!r}")
    elif kind == "correlation":
        cnums = [n for n in nums if spec["min_abs"] <= abs(n) <= 1.001]
        claim_hits = [c for c in claims if isinstance(c, dict) and c.get("metric") == "pearson_r"
                      and isinstance(c.get("value"), (int, float)) and abs(c["value"]) >= spec["min_abs"]]
        v["fired"] = bool(cnums or claim_hits)
        v["why"] = (f"coefficient {cnums[0]:.2f}" if cnums
                    else f"pearson_r claim {claim_hits[0]['value']:.2f}" if claim_hits
                    else f"no coefficient (exact-intersection empty?): {answer!r}")
    v["n_claims"] = len([c for c in claims if isinstance(c, dict)])
    return v


# --------------------------------- run loop ----------------------------------

def run_one(client, case_id, case, arm, run_n, results) -> None:
    key = f"{case_id}::{arm}::run{run_n}"
    if results["runs"].get(key, {}).get("done"):
        return
    request = case["request"]
    rec = {"case": case_id, "arm": arm, "run": run_n, "attempts": [], "done": False,
           "executed": False, "fired": False}
    code, sandbox_error = None, None
    for attempt in range(MAX_REPAIRS + 1):
        t0 = time.time()
        gen = (client.generate_chart_code(request, user_request=case["prompt"]) if code is None
               else client.repair_chart_code(code, sandbox_error, request, user_request=case["prompt"]))
        gen_s = round(time.time() - t0, 1)
        if not gen.get("accepted"):
            rec["attempts"].append({"n": attempt, "gen_s": gen_s, "provider_failure": gen.get("code")})
            break
        code = gen["python_code"]
        execution = execute(code, request)
        att = {"n": attempt, "gen_s": gen_s, "loc": len(code.splitlines()), "ok": execution.get("ok")}
        if execution.get("ok"):
            rec["executed"] = True
            rec["verdict"] = judge(case, execution)
            rec["fired"] = rec["verdict"]["fired"]
            rec["attempts"].append(att)
            rec["final_code"] = code
            break
        att["error"] = execution.get("error")
        rec["attempts"].append(att)
        if attempt == MAX_REPAIRS:
            rec["final_code"] = code
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
    cases = build_cases()
    only = {s.strip() for s in os.environ.get("ONLY_CASES", "").split(",") if s.strip()}
    if only:
        cases = {k: v for k, v in cases.items() if k in only}
    arms = {"without_alignment": rules_without_alignment(),
            "with_alignment": list(mp._CODEGEN_PROMPT_RULES)}
    only_arm = os.environ.get("ONLY_ARM", "").strip()
    if only_arm:
        arms = {only_arm: arms[only_arm]}

    results = json.loads(RESULTS_JSON.read_text()) if RESULTS_JSON.exists() else {"meta": {}, "runs": {}}
    results["meta"] = {"model": MODEL, "ollama": OLLAMA_URL, "runs": RUNS,
                       "max_repairs": MAX_REPAIRS,
                       "started": results["meta"].get("started")
                       or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    client = mp.OllamaCompatiblePlannerClient(endpoint_url=OLLAMA_URL, planner_model=MODEL)
    original = list(mp._CODEGEN_PROMPT_RULES)
    try:
        for case_id, case in cases.items():
            for arm, rules in arms.items():
                mp._CODEGEN_PROMPT_RULES = rules
                for run_n in range(1, RUNS + 1):
                    run_one(client, case_id, case, arm, run_n, results)
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
        print(f"{arm}: {t['fired']}/{t['runs']} clean analyses ({t['executed']} executed)")
    results["tally"] = tally
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
