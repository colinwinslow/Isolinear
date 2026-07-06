#!/usr/bin/env python3
"""Open-queue (q) design probe — does the analysis layer fire when the codegen
prompt carries the user's request?

The 16th-session live e2e run proved the model-authored analysis layer does NOT
fire on the live floor model: every transform/correlation/question prompt
collapsed to plotting the raw input series with an analysis-flavored title and
an empty answer_text. Diagnosis (17th session): the codegen payload never
carries the user's prompt — its task is "render the supplied ChartSpec", the
answer rule is conditioned on "if the prompt asks a question" (a prompt the
model never sees), and the 0.2.19 grounding rule hard-instructs "plot each
numeric series as a line". The benchmark that "proved" the capability
(evals/analysis_benchmark) handed the model the QUESTION with an
"analysis engine" identity — the opposite framing on all three counts.

This probe measures the candidate fix on the PRODUCTION codegen path (real
``generate_chart_code`` / ``repair_chart_code``, real rules + prompt-view
projection) against live gemma4:e4b, in two arms:

  * baseline — production payload exactly as shipped (no user prompt anywhere);
    expected to reproduce the e2e failure offline (raw series, no answer).
  * intent   — the candidate delta: the payload gains ``user_request`` (the
    user's prompt text), the task is reframed to "fulfill user_request", the
    plot-every-numeric-series rule becomes the DEFAULT with a compute-the-
    derived-series exception, and the answer rule references user_request.

Ground truth is EXECUTION, not inspection (15th-session method): each accepted
generation runs in a real venv against the full synthetic data, and the judge
checks what was actually plotted (line stats via matplotlib) and what
answer_text/claims came back. The synthetic series have known analytics
(means, delta, correlation, noise for smoothing), so "did it compute?" is a
numeric check, not a vibe.

Sandbox parity note: no live worker in the loop (the design question is "does
the model compute", not "does it pass the sandbox") — but the harness flags
any import outside the production allowlist, and runtime failures get the
production repair loop with a worker-shaped runtime_error.

Config via env:
  OLLAMA_URL   (default http://10.0.1.39:11434)
  MODEL        (default gemma4:e4b — the production floor model)
  EXEC_PY      (default /home/claude/.expenv/bin/python — venv with
                matplotlib/pandas/numpy/scipy/seaborn)
  RUNS         (default 2)
  MAX_REPAIRS  (default 2 — runtime-only, mirrors production behavior)
  RESULTS_JSON (default evals/prompts/analysis_intent_probe_results.json)
  ONLY_CASES   (comma list of case ids; default all)
  ONLY_ARM     (baseline | intent; default both)
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
RESULTS_JSON = Path(os.environ.get("RESULTS_JSON", HERE / "prompts" / "analysis_intent_probe_results.json"))

# Markers identifying the two production rules the intent arm rewrites.
# Fail loudly on drift (rule-gate pattern) rather than silently testing nothing.
PLOT_RULE_MARKER = "Plot each series in data['history_series'] whose 'kind' is 'numeric'"
ANSWER_RULE_MARKER = "If the prompt asks a question"

# The candidate rewrites (the design delta under measurement — if adopted,
# these move into _CODEGEN_PROMPT_RULES / _codegen_payload).
INTENT_TASK = (
    "Fulfill user_request: write Python matplotlib code that renders a chart "
    "answering the user's request from the supplied history_series data, guided "
    "by the supplied already-validated Isolinear ChartSpec."
)
INTENT_PLOT_RULE = (
    "By default plot each series in data['history_series'] whose 'kind' is "
    "'numeric' as a line, iterating that list directly and using each series' own "
    "'label' and 'unit'. EXCEPTION: when user_request asks for a computed analysis "
    "— an average or combination across sensors, a difference ('how much warmer'), "
    "a correlation, a deviation from average, a smoothed/rolling series, or "
    "similar — COMPUTE that derived series from the numeric history_series points "
    "with pandas/numpy/scipy and plot the DERIVED result, labelled for what it is; "
    "plot the raw inputs only if they help answer the request. Never plot a series "
    "whose 'kind' is 'binary_state' or 'categorical_state' as a line (its value is "
    "a state string like 'cool', not a number) — those are state overlays, already "
    "provided to you as shaded bands (see the derived_intervals rule). The "
    "chart_spec is intent/metadata only (title, requested series) — NEVER read the "
    "data to plot, the list of series, or the unit from chart_spec; a chart_spec "
    "unit may be wrong. Use data['history_series'][i]['entity_id'] for identity."
)
INTENT_ANSWER_RULE = (
    "If user_request asks a question (e.g. 'are they correlated?', 'how much…?', "
    "'what was the average…?'), also return an 'answer_text' string in the "
    "metadata dict answering it in one plain sentence."
)

# Production sandbox import allowlist (worker/isolinear_worker/codegen_sandbox.py)
# — the harness flags imports outside it so a prompt change that pushes the model
# off-allowlist is visible even without a live worker in the loop.
ALLOWED_IMPORT_ROOTS = {
    "matplotlib", "pandas", "numpy", "scipy", "seaborn", "datetime",
    "itertools", "functools", "collections", "typing", "math", "statistics",
}


class IntentArmClient(mp.OllamaCompatiblePlannerClient):
    """Production client + the candidate payload delta, applied by decoding and
    mutating the REAL payload (so everything not under test stays production)."""

    user_request: str = ""

    def _codegen_payload(self, request, *, model):
        payload = super()._codegen_payload(request, model=model)
        body = json.loads(payload["messages"][1]["content"])
        body["task"] = INTENT_TASK
        body["user_request"] = self.user_request
        rules = list(body["rules"])
        plot_hits = [i for i, r in enumerate(rules) if PLOT_RULE_MARKER in r]
        answer_hits = [i for i, r in enumerate(rules) if ANSWER_RULE_MARKER in r]
        if len(plot_hits) != 1 or len(answer_hits) != 1:
            raise SystemExit(
                f"rule markers drifted (plot={len(plot_hits)}, answer={len(answer_hits)}) "
                "— update PLOT_RULE_MARKER/ANSWER_RULE_MARKER"
            )
        rules[plot_hits[0]] = INTENT_PLOT_RULE
        rules[answer_hits[0]] = INTENT_ANSWER_RULE
        body["rules"] = rules
        payload["messages"][1]["content"] = json.dumps(body, separators=(",", ":"))
        return payload

    def _codegen_repair_payload(self, previous_code, sandbox_error, request, *, model):
        payload = super()._codegen_repair_payload(previous_code, sandbox_error, request, model=model)
        body = json.loads(payload["messages"][1]["content"])
        body["user_request"] = self.user_request
        rules = list(body["rules"])
        for i, r in enumerate(rules):
            if PLOT_RULE_MARKER in r:
                rules[i] = INTENT_PLOT_RULE
            elif ANSWER_RULE_MARKER in r:
                rules[i] = INTENT_ANSWER_RULE
        body["rules"] = rules
        payload["messages"][1]["content"] = json.dumps(body, separators=(",", ":"))
        return payload


# ------------------------- production-shaped cases --------------------------
# Points carry ts (schema) + ts_epoch_ms (D9) + value/raw_state/quality; units
# are real HA strings. Analytics are known by construction so the judge is
# numeric: kitchen 71±4 sin, basement 64±2 sin (same phase → r≈+1, delta 7±2,
# combined mean 67.5); the rolling case uses a low-amplitude sine + strong
# deterministic noise so smoothing measurably reduces std.

_BASE_MS = 1751500800000  # 2026-07-03T00:00:00Z


def _pt(offset_min: int, value) -> dict:
    ms = _BASE_MS + offset_min * 60_000
    iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(ms / 1000))
    return {"ts": iso, "ts_epoch_ms": ms, "value": value, "raw_state": str(value), "quality": "ok"}


def _numeric_series(sid, eid, label, unit, base, amp, hours=24, step_min=10, noise=0.0) -> dict:
    pts = []
    for i in range(0, hours * 60, step_min):
        v = base + amp * math.sin((i / (hours * 60)) * 2 * math.pi * (hours / 24) - 1.6)
        if noise:
            v += (((i * 2654435761) % 1000) / 1000.0 - 0.5) * 2 * noise
        pts.append(_pt(i, round(v, 2)))
    return {"series_id": sid, "entity_id": eid, "label": label, "kind": "numeric",
            "unit": unit, "points": pts, "source_entity_ids": [eid], "warnings": []}


def _series_spec(sid, label, eid, unit, role="primary") -> dict:
    return {"series_id": sid, "label": label, "role": role, "render_as": "line",
            "unit": unit, "source": {"type": "entity", "entity_id": eid}}


def _spec(title, series) -> dict:
    return {"chart_id": "probe", "chart_type": "time_series", "title": title,
            "time_range": {"type": "relative", "duration": "24h"},
            "series": series, "overlays": []}


def _request(spec, series_list) -> dict:
    return {"chart_spec": spec, "history_series": series_list, "derived_intervals": [],
            "output": {"format": "png", "width": 800, "height": 480}}


def build_cases() -> dict[str, dict]:
    k24 = _numeric_series("kitchen", "sensor.kitchen_temperature", "Kitchen Temperature", "°F", 71, 4)
    b24 = _numeric_series("basement", "sensor.basement_temperature", "Basement Temperature", "°F", 64, 2)
    k48 = _numeric_series("kitchen", "sensor.kitchen_temperature", "Kitchen Temperature", "°F", 71, 4, hours=48)
    b48 = _numeric_series("basement", "sensor.basement_temperature", "Basement Temperature", "°F", 64, 2, hours=48)
    k7d = _numeric_series("kitchen", "sensor.kitchen_temperature", "Kitchen Temperature", "°F", 71, 4,
                          hours=7 * 24, step_min=30)
    knoisy = _numeric_series("kitchen", "sensor.kitchen_temperature", "Kitchen Temperature", "°F", 71, 1,
                             hours=48, noise=3.0)

    return {
        # e2e-06: the plain answer_text question. PASS = answer_text carries the
        # computed weekly mean (sine mean = base = 71).
        "q_mean": {
            "prompt": "What was the average kitchen temperature over the last week?",
            "request": _request(_spec("Average kitchen temperature, last week",
                                      [_series_spec("kitchen", "Kitchen", "sensor.kitchen_temperature", "°F")]),
                                [k7d]),
            "judge": {"kind": "answer_number", "target": 71.0, "tol": 1.5},
        },
        # e2e-11: cross-sensor mean. PASS = a plotted line ≈ the combined mean
        # (67.5), clearly distinct from either raw series (71 / 64).
        "t_mean": {
            "prompt": "What is the average of the kitchen and basement temperatures over the last day?",
            "request": _request(_spec("Average of kitchen and basement temperatures",
                                      [_series_spec("kitchen", "Kitchen", "sensor.kitchen_temperature", "°F"),
                                       _series_spec("basement", "Basement", "sensor.basement_temperature", "°F",
                                                    role="secondary")]),
                                [k24, b24]),
            "judge": {"kind": "line_mean", "target": 67.5, "tol": 1.0},
        },
        # e2e-12: delta + verdict. PASS = answer_text (or a delta claim) carries
        # the computed difference (7±2 → mean 7).
        "t_delta": {
            "prompt": "How much warmer is the kitchen than the basement over the last 2 days?",
            "request": _request(_spec("Kitchen vs basement temperature difference",
                                      [_series_spec("kitchen", "Kitchen", "sensor.kitchen_temperature", "°F"),
                                       _series_spec("basement", "Basement", "sensor.basement_temperature", "°F",
                                                    role="secondary")]),
                                [k48, b48]),
            "judge": {"kind": "answer_number", "target": 7.0, "tol": 2.0},
        },
        # e2e-13: correlation. Same-phase sines → r ≈ +1. PASS = a coefficient
        # ≥ 0.5 in answer_text or a pearson_r claim.
        "corr": {
            "prompt": "Are the kitchen and basement temperatures correlated over the last 2 days?",
            "request": _request(_spec("Kitchen and basement temperature correlation",
                                      [_series_spec("kitchen", "Kitchen", "sensor.kitchen_temperature", "°F"),
                                       _series_spec("basement", "Basement", "sensor.basement_temperature", "°F",
                                                    role="secondary")]),
                                [k48, b48]),
            "judge": {"kind": "correlation", "min_abs": 0.5},
        },
        # e2e-17: rolling mean. Noise dominates the low-amplitude sine, so a
        # real rolling mean cuts the plotted std vs the raw series.
        "roll": {
            "prompt": "Show the kitchen temperature smoothed with a rolling average over the last 2 days",
            "request": _request(_spec("Kitchen temperature, rolling average",
                                      [_series_spec("kitchen", "Kitchen", "sensor.kitchen_temperature", "°F")]),
                                [knoisy]),
            "judge": {"kind": "smoothed", "max_std_ratio": 0.75},
        },
        # e2e-18: deviation from average. PASS = a plotted line centered near 0
        # (own-mean → 0, house-mean → ±3.5); raw lines sit at 64/71.
        "dev": {
            "prompt": "Show how far the kitchen and basement temperatures deviate from their average over the last day",
            "request": _request(_spec("Temperature deviation from average",
                                      [_series_spec("kitchen", "Kitchen", "sensor.kitchen_temperature", "°F"),
                                       _series_spec("basement", "Basement", "sensor.basement_temperature", "°F",
                                                    role="secondary")]),
                                [k24, b24]),
            "judge": {"kind": "line_mean", "target": 0.0, "tol": 4.5},
        },
    }


# ---------------------------- execution harness -----------------------------

_HARNESS = r'''
import json, sys, traceback, warnings
warnings.simplefilter("ignore")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.close = lambda *a, **k: None  # keep figures alive for line inspection

code_file, data_file, out_png = sys.argv[1], sys.argv[2], sys.argv[3]
data = json.load(open(data_file))

def _stats(values):
    vals = [float(v) for v in values if v == v]
    if not vals:
        return None
    n = len(vals)
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / n
    return {"n": n, "mean": mean, "std": var ** 0.5,
            "min": min(vals), "max": max(vals)}

def _san(o):
    try:
        return float(o)
    except Exception:
        return str(o)

try:
    ns = {}
    exec(open(code_file).read(), ns)
    meta = ns["render_chart"](data, out_png)
    lines = []
    for num in plt.get_fignums():
        fig = plt.figure(num)
        for ax in fig.axes:
            for line in ax.get_lines():
                st = _stats(line.get_ydata())
                if st:
                    st["label"] = str(line.get_label())
                    lines.append(st)
    answer = meta.get("answer_text") if isinstance(meta, dict) else None
    claims = meta.get("claims") if isinstance(meta, dict) else None
    import os
    print("__R__" + json.dumps({"ok": True, "answer_text": answer, "claims": claims,
                                "lines": lines, "png": os.path.getsize(out_png) if os.path.exists(out_png) else 0},
                               default=_san))
except Exception as exc:
    print("__R__" + json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}",
                                "traceback": traceback.format_exc()[-1200:]}))
'''


def execute(code: str, request: dict) -> dict:
    """Run render_chart in the exec venv against the FULL runtime-shaped data."""
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
            capture_output=True, text=True, timeout=120,
        )
    for stream in (proc.stdout, proc.stderr):
        for ln in stream.splitlines():
            if ln.startswith("__R__"):
                return json.loads(ln[len("__R__"):])
    return {"ok": False, "error": f"harness produced no result (rc={proc.returncode})",
            "traceback": (proc.stderr or proc.stdout)[-1200:]}


def offlist_imports(code: str) -> list[str]:
    roots = set()
    for m in re.finditer(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_.]*)", code, re.M):
        roots.add(m.group(1).split(".")[0])
    return sorted(roots - ALLOWED_IMPORT_ROOTS)


# --------------------------------- judging -----------------------------------

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _answer_numbers(answer: Any) -> list[float]:
    if not isinstance(answer, str):
        return []
    return [float(t) for t in _NUM_RE.findall(answer)]


def judge(case: dict, execution: dict) -> dict:
    spec = case["judge"]
    kind = spec["kind"]
    lines = execution.get("lines") or []
    answer = execution.get("answer_text")
    claims = execution.get("claims") or []
    verdict = {"kind": kind, "fired": False, "why": ""}

    if kind == "answer_number":
        hits = [n for n in _answer_numbers(answer)
                if abs(n - spec["target"]) <= spec["tol"]]
        claim_hits = [c for c in claims if isinstance(c, dict)
                      and isinstance(c.get("value"), (int, float))
                      and abs(c["value"] - spec["target"]) <= spec["tol"]]
        verdict["fired"] = bool(hits or claim_hits)
        verdict["why"] = (f"answer carries {hits[0]:.2f}" if hits
                          else f"claim carries {claim_hits[0]['value']:.2f}" if claim_hits
                          else f"no number near {spec['target']} in answer_text={answer!r}")
    elif kind == "line_mean":
        hits = [ln for ln in lines if abs(ln["mean"] - spec["target"]) <= spec["tol"]]
        verdict["fired"] = bool(hits)
        verdict["why"] = (f"plotted line mean {hits[0]['mean']:.2f} ≈ {spec['target']}" if hits
                          else f"line means {[round(ln['mean'], 1) for ln in lines]} — none near {spec['target']}")
    elif kind == "correlation":
        nums = [n for n in _answer_numbers(answer) if spec["min_abs"] <= abs(n) <= 1.001]
        claim_hits = [c for c in claims if isinstance(c, dict) and c.get("metric") == "pearson_r"
                      and isinstance(c.get("value"), (int, float)) and abs(c["value"]) >= spec["min_abs"]]
        verdict["fired"] = bool(nums or claim_hits)
        verdict["why"] = (f"coefficient {nums[0]:.2f} in answer" if nums
                          else f"pearson_r claim {claim_hits[0]['value']:.2f}" if claim_hits
                          else f"no coefficient in answer_text={answer!r} or claims")
    elif kind == "smoothed":
        raw = case["request"]["history_series"][0]["points"]
        vals = [p["value"] for p in raw]
        mean = sum(vals) / len(vals)
        raw_std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
        candidates = [ln for ln in lines if ln["n"] >= 50]
        smooth = [ln for ln in candidates if ln["std"] <= spec["max_std_ratio"] * raw_std]
        verdict["fired"] = bool(smooth)
        verdict["why"] = (f"line std {smooth[0]['std']:.2f} < {spec['max_std_ratio']}×raw {raw_std:.2f}" if smooth
                          else f"line stds {[round(ln['std'], 2) for ln in candidates]} vs raw {raw_std:.2f} — no smoothing")
    verdict["answer_text"] = answer
    verdict["n_claims"] = len([c for c in claims if isinstance(c, dict)])
    return verdict


# --------------------------------- run loop ----------------------------------

def run_one(client, case_id: str, case: dict, arm: str, run_n: int, results: dict) -> None:
    key = f"{case_id}::{arm}::run{run_n}"
    if results["runs"].get(key, {}).get("done"):
        return
    if isinstance(client, IntentArmClient):
        client.user_request = case["prompt"]
    request = case["request"]
    rec = {"case": case_id, "arm": arm, "run": run_n, "attempts": [], "done": False,
           "executed": False, "fired": False}
    code, sandbox_error = None, None
    for attempt in range(MAX_REPAIRS + 1):
        t0 = time.time()
        gen = client.generate_chart_code(request) if code is None else \
            client.repair_chart_code(code, sandbox_error, request)
        gen_s = round(time.time() - t0, 1)
        if not gen.get("accepted"):
            rec["attempts"].append({"n": attempt, "gen_s": gen_s, "provider_failure": gen.get("code")})
            break
        code = gen["python_code"]
        execution = execute(code, request)
        att = {"n": attempt, "gen_s": gen_s, "loc": len(code.splitlines()),
               "ok": execution.get("ok"), "offlist_imports": offlist_imports(code)}
        if execution.get("ok"):
            rec["executed"] = True
            rec["verdict"] = judge(case, execution)
            rec["fired"] = rec["verdict"]["fired"]
            rec["lines"] = execution.get("lines")
            rec["attempts"].append(att)
            rec["final_code"] = code
            break
        att["error"] = execution.get("error")
        rec["attempts"].append(att)
        if attempt == MAX_REPAIRS:
            rec["final_code"] = code
            break
        sandbox_error = {"code": "runtime_error", "message": execution.get("error") or "execution failed",
                         "details": {"traceback": execution.get("traceback") or ""}}
    rec["done"] = True
    results["runs"][key] = rec
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    v = rec.get("verdict") or {}
    print(f"[{key}] {'FIRED' if rec['fired'] else 'silent'} "
          f"executed={rec['executed']} attempts={len(rec['attempts'])} — {v.get('why', 'n/a')}",
          flush=True)


def main() -> int:
    cases = build_cases()
    only = {s.strip() for s in os.environ.get("ONLY_CASES", "").split(",") if s.strip()}
    if only:
        cases = {k: v for k, v in cases.items() if k in only}
    arms = ["baseline", "intent"]
    only_arm = os.environ.get("ONLY_ARM", "").strip()
    if only_arm:
        arms = [only_arm]

    results = json.loads(RESULTS_JSON.read_text()) if RESULTS_JSON.exists() else {"meta": {}, "runs": {}}
    results["meta"] = {"model": MODEL, "ollama": OLLAMA_URL, "runs": RUNS,
                       "max_repairs": MAX_REPAIRS,
                       "intent_task": INTENT_TASK,
                       "intent_plot_rule": INTENT_PLOT_RULE,
                       "intent_answer_rule": INTENT_ANSWER_RULE,
                       "started": results["meta"].get("started")
                       or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    clients = {
        "baseline": mp.OllamaCompatiblePlannerClient(endpoint_url=OLLAMA_URL, planner_model=MODEL),
        "intent": IntentArmClient(endpoint_url=OLLAMA_URL, planner_model=MODEL),
    }
    for case_id, case in cases.items():
        for arm in arms:
            for run_n in range(1, RUNS + 1):
                run_one(clients[arm], case_id, case, arm, run_n, results)

    # ---- tally ----
    tally: dict[str, dict] = {}
    for rec in results["runs"].values():
        t = tally.setdefault(rec["arm"], {"runs": 0, "executed": 0, "fired": 0})
        t["runs"] += 1
        t["executed"] += bool(rec.get("executed"))
        t["fired"] += bool(rec.get("fired"))
    print("\n=== tally ===")
    for arm, t in sorted(tally.items()):
        print(f"{arm}: {t['fired']}/{t['runs']} fired analysis ({t['executed']} executed)")
    results["tally"] = tally
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
