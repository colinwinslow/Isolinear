#!/usr/bin/env python3
"""Eval-gate the verdict/rule-omission rule (open-queue (cc), 0.2.40).

Live symptom (25th-session e2e-11, `scripts/ha_logs.py`): a plain descriptive
mean answer ("The average temperature of the kitchen and basement over the last
day was 72.89 °F") reached the grounding check with a claim the model had
decorated with a spurious `verdict`+`rule` (band-label structure). The grounding
check's step-5 verdict containment (answer_grounding.py) requires the claimed
verdict to appear verbatim as a band label in answer_text; a descriptive
sentence has no Yes/No label, so it fails `grounding_verdict_ambiguous` — and
because every re-generation recomputes the SAME correct number, all repair
attempts hit the identical wall (masked until the 0.2.37 value-mismatch fix
stopped withholding earlier at step 4).

The fix is a codegen PROMPT rule (not a grounding change — the check at
answer_grounding.py:625 is correct): value/descriptive claims omit
`verdict`+`rule`, so grounding skips step 5 entirely and the mean is still
value-verified by the step-4 recompute (the 0.2.37 multi-input mean grounding).

This gate drives the PRODUCTION codegen path against live gemma4:e4b with the
e2e-11-shaped descriptive two-sensor mean prompt + chart_spec, two arms:

  * without_rule — production rules minus the verdict-omission sentence
    (marker-gated surgery, rule-gate pattern) — the pre-0.2.40 behaviour;
  * with_rule    — production rules as-is (the verdict-omission prescription).

Execution-truth judge: run the model's generated render_chart, capture the
returned metadata (answer_text + claims), then run the REAL
`answer_grounding.run_grounding_check` against the same history_series. The rule
FIRES for a run when the emitted claim(s) omit verdict+rule AND grounding
produces no `grounding_verdict_*` outcome (the live symptom is gone). A run
where the model attaches a verdict+rule and grounding trips verdict-ambiguity is
a fail — exactly the e2e-11 cascade, reproduced offline.

Config via env: OLLAMA_URL, MODEL, EXEC_PY, RUNS (default 3), MAX_REPAIRS
(default 2), RESULTS_JSON, ONLY_ARM.
"""
from __future__ import annotations

import json
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
RUNS = int(os.environ.get("RUNS", "3"))
MAX_REPAIRS = int(os.environ.get("MAX_REPAIRS", "2"))
RESULTS_JSON = Path(os.environ.get("RESULTS_JSON", HERE / "prompts" / "verdict_omission_gate_results.json"))

# The verdict-omission sentence under the gate, identified by distinctive phrasing
# — fail loudly if the rule text drifts (rule-gate pattern).
OMIT_MARKER = "Attach 'verdict' and 'rule' to a claim ONLY when"
OMIT_RE = re.compile(
    r"Attach 'verdict' and 'rule' to a claim ONLY when .*?makes the grounding "
    r"check reject a correct answer\.", re.S)

PROMPT = "What was the average of the kitchen and basement temperatures over the last day?"
_BASE_MS = 1782000000000  # 2026-06-29T00:00:00Z


def rules_without_omission() -> list[str]:
    hits = [i for i, r in enumerate(mp._CODEGEN_PROMPT_RULES) if OMIT_MARKER in r]
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one rule containing {OMIT_MARKER!r}, found {len(hits)}")
    rules = list(mp._CODEGEN_PROMPT_RULES)
    stripped = OMIT_RE.sub(" ", rules[hits[0]])
    if OMIT_MARKER in stripped:
        raise SystemExit("verdict-omission sentence removal failed — update OMIT_RE")
    rules[hits[0]] = stripped
    return rules


def _sensor_series(entity_id: str, label: str, base: float, phase: float) -> dict:
    """~1 day of 5-min numeric points, slightly irregular per sensor so the
    grounding recompute exercises the multi-input align path (0.2.37)."""
    import math
    points = []
    step = 300 * 1000
    for i in range(288):
        ms = _BASE_MS + i * step + (0 if "kitchen" in entity_id else 37 * 1000)
        v = base + 1.4 * math.sin(i / 288 * 2 * math.pi + phase) + 0.2 * math.sin(i / 12)
        iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(ms / 1000))
        points.append({"ts": iso, "ts_epoch_ms": ms, "value": round(v, 2),
                       "raw_state": None, "quality": "ok"})
    return {"series_id": f"series-{entity_id}", "entity_id": entity_id, "label": label,
            "kind": "numeric", "unit": "°F", "points": points, "source": "recorder",
            "resolution": "raw", "source_entity_ids": [entity_id], "warnings": []}


def _history() -> list[dict]:
    return [
        _sensor_series("sensor.kitchen_ecobee_temperature", "Kitchen Temperature", 73.5, 0.0),
        _sensor_series("sensor.basement_temperature", "Basement Temperature", 72.0, 0.9),
    ]


def _request() -> dict:
    return {
        "chart_spec": {
            "chart_id": "kitchen_basement_avg", "chart_type": "time_series",
            "title": "Kitchen and Basement Temperature",
            "time_range": {"type": "relative", "duration": "1d"},
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
                                 # (mirrors the ADR-0036 in-image helper)
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
    """The (cc) target is behavioral: a CORRECT descriptive answer is SERVED,
    not withheld by a spurious verdict the grounding step-5 containment rejects.
    So we run the REAL grounding check and fire when the answer is served
    (withheld=False). A non-null verdict is only a problem if it makes grounding
    withhold — a verdict that happens to verify is a served, grounded answer, and
    a null verdict + inert empty-rule stub is value-verified at step 4."""
    v = {"fired": False, "why": ""}
    answer_text = execution.get("answer_text")
    claims = execution.get("claims") if isinstance(execution.get("claims"), list) else []
    if not answer_text:
        v["why"] = "no answer_text emitted"
        return v
    grounding = run_grounding_check(
        {"answer_text": answer_text, "claims": claims}, request["history_series"])
    outcome = grounding.get("outcome")
    withheld = bool(grounding.get("withheld"))
    synth = grounding.get("synthetic_error") or {}
    non_null_verdict = sum(
        1 for c in claims if isinstance(c, dict) and c.get("verdict") is not None
    )
    v.update({"outcome": outcome, "withheld": withheld,
              "synthetic_code": synth.get("code"), "n_claims": len(claims),
              "non_null_verdict": non_null_verdict})
    if withheld:
        v["why"] = f"answer WITHHELD ({synth.get('code') or outcome})"
        return v
    v["fired"] = True
    v["why"] = f"served: outcome={outcome}, non-null verdicts={non_null_verdict}"
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
    print(f"[{key}] {'CLEAN' if rec['fired'] else 'fail'} executed={rec['executed']} "
          f"attempts={len(rec['attempts'])} — {vv.get('why', 'n/a')}", flush=True)


def main() -> int:
    arms = {"without_rule": rules_without_omission(),
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
        t = tally.setdefault(rec["arm"], {"runs": 0, "executed": 0, "fired": 0})
        t["runs"] += 1
        t["executed"] += bool(rec.get("executed"))
        t["fired"] += bool(rec.get("fired"))
    print("\n=== tally ===")
    for arm, t in sorted(tally.items()):
        print(f"{arm}: {t['fired']}/{t['runs']} served (answer reaches the user) "
              f"({t['executed']} executed)")
    results["tally"] = tally
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
