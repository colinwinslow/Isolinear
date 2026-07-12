#!/usr/bin/env python3
"""Eval-gate the in-sandbox analysis helper library (ADR-0036, draft).

Tests, BEFORE committing to the direction, whether prescribing
`isolinear_analysis.align()` beats the current literal alignment/keying idiom
on the cross-math family — the variance basin where every recent live failure
occurred (0.2.31 entity-id KeyError, the 0.2.32 "nan °F" empty frame, the
e2e-18 deviation repair exhaustion).

Two arms through the PRODUCTION codegen path (real `generate_chart_code` /
`repair_chart_code`) against live gemma4:e4b:

  * with_helper    — production `_CODEGEN_PROMPT_RULES` as-is (the ADR-0036
    helper prescription, shipped 0.2.34: call `isolinear_analysis.align()`,
    then one-liners against the entity-keyed frame).
  * without_helper — the retired 0.2.24→0.2.33 literal idiom (per-entity
    resample + entity-id-keyed concat) reconstructed via marker surgery, so
    the baseline the gate first beat stays re-runnable.

GATED RESULT (2026-07-12, pre-ship run with the arms reversed — helper text in
the eval, idiom in production): mean/delta/correlation 6/6 first-attempt +
6/6 fired in BOTH arms (no regression); deviation 0/6 first-attempt in BOTH
arms (an identical deterministic SyntaxError — a mis-bracketed literal, the
same line all 12 runs — a separate emission quirk, likely a series-valued
claims attempt), then the arms diverge: with_helper repairs converge in ONE
round → 6/6 fired; without_helper repairs cascade through hand-rolled plumbing
errors (UnboundLocalError/NameError/KeyError) → 4/6 with 2 repair-exhaustions —
the live e2e-18 Pillow fallback reproduced offline. Helper adoption 24/24.

Four prompts — the cross-math family members, mirroring the e2e twins:
mean (e2e-11/19), delta (e2e-12), deviation (e2e-18, the live residual FAIL —
the headline), correlation (e2e-13/20). Synthetic two-sensor data with
genuinely DISJOINT irregular timestamps (the shape that makes alignment
load-bearing) and known analytics: kitchen = 74 ± 2 sine, basement = 72 ± 2
same phase → delta ≈ 2.0, corr ≈ 1.0, deviations = ±1.0 centered on 0.

Execution-truth judging per member (run the code, inspect what was plotted and
answered — never inspect the source, EXCEPT the with-arm `helper_used` signal
which greps the code for the import). Metrics per arm: first-attempt execute
rate, eventual execute rate (≤ MAX_REPAIRS), intent-fire rate, and for the
with arm, helper adoption.

The harness executes locally with `worker/` on sys.path so
`import isolinear_analysis` resolves (the in-image `-I` proof is separate —
the packet-3 pattern on the rebuilt CT103 image).

Config via env: OLLAMA_URL, MODEL, EXEC_PY, RUNS (default 6), MAX_REPAIRS
(default 2), RESULTS_JSON, ONLY_ARM, ONLY_MEMBER.
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
RUNS = int(os.environ.get("RUNS", "6"))
MAX_REPAIRS = int(os.environ.get("MAX_REPAIRS", "2"))
RESULTS_JSON = Path(os.environ.get("RESULTS_JSON", HERE / "prompts" / "analysis_helper_gate_results.json"))

_BASE_MS = 1_782_000_000_000  # 2026-06-29T00:00:00Z

# ---------------------------------------------------------------------------
# Arm construction. PRODUCTION rules carry the ADR-0036 helper prescription
# (0.2.34); the without arm reconstructs the retired 0.2.31/0.2.24 literal
# idiom (resample + entity-id-keyed concat) via marker surgery on the ONE plot
# rule — fail loudly on drift.
# ---------------------------------------------------------------------------

HELPER_START = "Each entity's points are sampled IRREGULARLY"
HELPER_RE = re.compile(
    r"Each entity's points are sampled IRREGULARLY.*?the only "
    r"correct way to combine series\. ", re.S)

# The retired pre-ADR-0036 idiom text (shipped 0.2.24→0.2.33), preserved so the
# without arm stays re-runnable against the exact baseline the gate first beat.
LEGACY_IDIOM = (
    "Each entity's points are sampled IRREGULARLY at "
    "different times (two entities share NO timestamps), so before ANY math across "
    "two series (average, difference, correlation, deviation) align each one FIRST "
    "with exactly this per-entity idiom: aligned = pandas.Series([p['value'] for p in "
    "pts], index=pandas.to_datetime([p['ts_epoch_ms'] for p in pts], "
    "unit='ms')).resample('5min').mean().interpolate() — resample EACH series "
    "separately BEFORE combining them; only then combine the aligned results (they "
    "now share a grid) and .dropna(). Build that combined frame KEYED BY ENTITY_ID: "
    "combined = pandas.concat({s['entity_id']: aligned_for_s for each series s}, "
    "axis=1).dropna() — so its columns ARE the entity_id strings. Then reference a "
    "column by that exact entity_id (combined[s['entity_id']]) or by position "
    "(combined.iloc[:, i]), and compute a cross-sensor average as combined.mean(axis=1). "
    "NEVER index a bare-list concat by an entity_id: pandas.concat([s1, s2], axis=1) "
    "gives POSITIONAL columns 0,1,…, so combined['sensor.…'] raises KeyError (a live "
    "cross-math failure). NEVER join or intersect raw series on exact "
    "timestamps, and NEVER call .dropna() on a DataFrame built from two "
    "un-resampled series (their indexes are disjoint, so it deletes every row and "
    "everything downstream becomes NaN). "
)


def rules_without_helper() -> list[str]:
    hits = [i for i, r in enumerate(mp._CODEGEN_PROMPT_RULES) if HELPER_START in r]
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one rule containing {HELPER_START!r}, found {len(hits)}")
    rules = list(mp._CODEGEN_PROMPT_RULES)
    replaced = HELPER_RE.sub(LEGACY_IDIOM, rules[hits[0]])
    if "isolinear_analysis" in replaced or ".resample('5min')" not in replaced:
        raise SystemExit("helper → legacy-idiom replacement failed — update HELPER_RE")
    rules[hits[0]] = replaced
    return rules


# ---------------------------------------------------------------------------
# Family members: prompt + chart_spec + execution-truth judge
# ---------------------------------------------------------------------------

def _sensor(entity_id: str, label: str, base: float, *, amp: float, phase: float,
            offset_ms: int, n: int = 48) -> dict:
    """~24h irregular series; different offsets share NO timestamps. Different
    amp/phase per sensor so deviation-from-mean series genuinely OSCILLATE
    (same-phase sines would make deviations constant ±offset, which no judge
    can distinguish from an axhline)."""
    points = []
    for i in range(n):
        ms = _BASE_MS + i * 30 * 60_000 + offset_ms + (i % 7) * 11_000
        v = base + amp * math.sin(i / n * 2 * math.pi + phase)
        iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(ms / 1000))
        points.append({"ts": iso, "ts_epoch_ms": ms, "value": round(v, 2),
                       "raw_state": None, "quality": "ok"})
    return {"series_id": f"s-{entity_id}", "entity_id": entity_id, "label": label,
            "kind": "numeric", "unit": "°F", "points": points, "source": "recorder",
            "source_entity_ids": [entity_id], "warnings": []}


KITCHEN = "sensor.kitchen_ecobee_temperature"
BASEMENT = "sensor.basement_temperature"


def _request(title: str) -> dict:
    return {
        "chart_spec": {
            "chart_id": "cross_math", "chart_type": "time_series", "title": title,
            "time_range": {"type": "relative", "duration": "24h"},
            "series": [
                {"series_id": "kitchen", "label": "Kitchen Temperature", "role": "primary",
                 "render_as": "line", "transform": {"operation": "none", "window": None},
                 "unit": "°F", "source": {"type": "entity", "entity_id": KITCHEN, "attribute": None}},
                {"series_id": "basement", "label": "Basement Temperature", "role": "primary",
                 "render_as": "line", "transform": {"operation": "none", "window": None},
                 "unit": "°F", "source": {"type": "entity", "entity_id": BASEMENT, "attribute": None}},
            ],
            "overlays": [], "x_axis": {"type": "time"}, "y_axis": {},
        },
        "history_series": [
            _sensor(KITCHEN, "Kitchen Temperature", 74.0, amp=2.0, phase=0.0, offset_ms=0),
            _sensor(BASEMENT, "Basement Temperature", 72.0, amp=1.0, phase=0.9,
                    offset_ms=137_000),
        ],
        "derived_intervals": [],
        "output": {"format": "png", "width": 800, "height": 480},
    }


_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _answer_number(answer, lo, hi):
    if not isinstance(answer, str):
        return None
    for m in _NUM_RE.finditer(answer):
        v = float(m.group(0))
        if lo <= v <= hi:
            return v
    return None


def judge_mean(ex):
    """One derived line BETWEEN the inputs (72-74 band centre ~73) + finite answer ~73."""
    lines = [ln for a in ex.get("axes", []) for ln in a["lines"]
             if ln["mean"] is not None and 72.4 <= ln["mean"] <= 73.6 and ln["n"] > 10]
    return {"fired": bool(lines) and _answer_number(ex.get("answer_text"), 71.0, 75.0) is not None,
            "why": f"derived_line={bool(lines)} answer={ex.get('answer_text')!r}"}


def judge_delta(ex):
    """A difference series near 2.0 °F and/or an answer number near 2.0."""
    lines = [ln for a in ex.get("axes", []) for ln in a["lines"]
             if ln["mean"] is not None and 1.0 <= ln["mean"] <= 3.0 and ln["n"] > 10]
    ans = _answer_number(ex.get("answer_text"), 0.5, 3.5)
    return {"fired": bool(lines) or ans is not None,
            "why": f"delta_line={bool(lines)} answer={ex.get('answer_text')!r}"}


def judge_deviation(ex):
    """Per-sensor deviation series: oscillating line(s) with |time-average| ≤ 1.6
    and real spread — separated from raw temps (means 72/74), the mean series
    (~73), and the delta series (~2.0)."""
    lines = [ln for a in ex.get("axes", []) for ln in a["lines"]
             if ln["mean"] is not None and abs(ln["mean"]) <= 1.6
             and ln["min"] is not None and ln["max"] is not None
             and (ln["max"] - ln["min"]) > 0.4 and ln["n"] > 10]
    return {"fired": bool(lines),
            "why": f"deviation_lines={len(lines)} answer={ex.get('answer_text')!r}"}


def judge_correlation(ex):
    """A computed coefficient in [-1, 1] formatted into the answer."""
    ans = ex.get("answer_text")
    val = None
    if isinstance(ans, str):
        for m in _NUM_RE.finditer(ans):
            v = float(m.group(0))
            if -1.0 <= v <= 1.0:
                val = v
                break
    return {"fired": val is not None and ex.get("ok", False),
            "why": f"coefficient={val} answer={ans!r}"}


MEMBERS = {
    "mean": ("What is the average of the kitchen and basement temperatures?",
             "Average of Kitchen and Basement Temperature", judge_mean),
    "delta": ("How much warmer is the kitchen than the basement?",
              "Kitchen vs Basement Temperature Difference", judge_delta),
    "deviation": ("Show how far the kitchen and basement temperatures deviate from their average",
                  "Temperature Deviation from Average", judge_deviation),
    "correlation": ("Are the kitchen and basement temperatures correlated?",
                    "Kitchen and Basement Temperature Correlation", judge_correlation),
}


# ---------------------------------------------------------------------------
# Local executor (worker/ on sys.path so `import isolinear_analysis` resolves)
# ---------------------------------------------------------------------------

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
    axes = []
    for num in plt.get_fignums():
        for ax in plt.figure(num).axes:
            lines = []
            for ln in ax.get_lines():
                ys = [float(y) for y in ln.get_ydata()]
                lines.append({"n": len(ys),
                              "min": min(ys) if ys else None,
                              "max": max(ys) if ys else None,
                              "mean": (sum(ys) / len(ys)) if ys else None})
            axes.append({"n_lines": len(ax.get_lines()), "lines": lines})
    answer_text = meta.get("answer_text") if isinstance(meta, dict) else None
    import os
    print("__R__" + json.dumps({"ok": True, "axes": axes, "answer_text": answer_text,
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


def run_one(client, arm, member, run_n, results) -> None:
    key = f"{arm}::{member}::run{run_n}"
    if results["runs"].get(key, {}).get("done"):
        return
    prompt, title, judge = MEMBERS[member]
    request = _request(title)
    rec = {"arm": arm, "member": member, "run": run_n, "attempts": [], "done": False,
           "first_attempt_ok": False, "executed": False, "fired": False, "helper_used": False}
    code, sandbox_error = None, None
    for attempt in range(MAX_REPAIRS + 1):
        t0 = time.time()
        gen = (client.generate_chart_code(request, user_request=prompt) if code is None
               else client.repair_chart_code(code, sandbox_error, request, user_request=prompt))
        gen_s = round(time.time() - t0, 1)
        if not gen.get("accepted"):
            rec["attempts"].append({"n": attempt, "gen_s": gen_s, "provider_failure": gen.get("code")})
            break
        code = gen["python_code"]
        rec["helper_used"] = "isolinear_analysis" in code
        ex = execute(code, request)
        att = {"n": attempt, "gen_s": gen_s, "loc": len(code.splitlines()), "ok": ex.get("ok")}
        if ex.get("ok"):
            rec["executed"] = True
            rec["first_attempt_ok"] = attempt == 0
            verdict = judge(ex)
            rec["fired"] = verdict["fired"]
            rec["why"] = verdict["why"]
            rec["attempts"].append(att)
            break
        att["error"] = ex.get("error")
        rec["attempts"].append(att)
        if attempt == MAX_REPAIRS:
            rec["why"] = f"exhausted: {ex.get('error')}"
            break
        sandbox_error = {"code": "runtime_error", "message": ex.get("error") or "failed",
                         "details": {"traceback": ex.get("traceback") or ""}}
    rec["done"] = True
    results["runs"][key] = rec
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    tag = "FIRED" if rec["fired"] else ("ok-nofire" if rec["executed"] else "FAILED")
    print(f"[{key}] {tag} first_attempt={rec['first_attempt_ok']} helper={rec['helper_used']} "
          f"— {rec.get('why', 'n/a')}", flush=True)


def main() -> int:
    arms = {"without_helper": rules_without_helper(),
            "with_helper": list(mp._CODEGEN_PROMPT_RULES)}
    only_arm = os.environ.get("ONLY_ARM", "").strip()
    if only_arm:
        arms = {only_arm: arms[only_arm]}
    members = list(MEMBERS)
    only_member = os.environ.get("ONLY_MEMBER", "").strip()
    if only_member:
        members = [only_member]

    results = json.loads(RESULTS_JSON.read_text()) if RESULTS_JSON.exists() else {"meta": {}, "runs": {}}
    results["meta"] = {"model": MODEL, "ollama": OLLAMA_URL, "runs": RUNS,
                       "max_repairs": MAX_REPAIRS,
                       "started": results["meta"].get("started")
                       or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    client = mp.OllamaCompatiblePlannerClient(endpoint_url=OLLAMA_URL, planner_model=MODEL)
    original = list(mp._CODEGEN_PROMPT_RULES)
    try:
        for arm, rules in arms.items():
            mp._CODEGEN_PROMPT_RULES = rules
            for member in members:
                for run_n in range(1, RUNS + 1):
                    run_one(client, arm, member, run_n, results)
    finally:
        mp._CODEGEN_PROMPT_RULES = original

    tally: dict[str, dict] = {}
    for rec in results["runs"].values():
        t = tally.setdefault(f"{rec['arm']}::{rec['member']}",
                             {"runs": 0, "first": 0, "executed": 0, "fired": 0, "helper": 0})
        t["runs"] += 1
        t["first"] += bool(rec.get("first_attempt_ok"))
        t["executed"] += bool(rec.get("executed"))
        t["fired"] += bool(rec.get("fired"))
        t["helper"] += bool(rec.get("helper_used"))
    print("\n=== tally (first-attempt / executed / intent-fired / helper-used, per runs) ===")
    for k in sorted(tally):
        t = tally[k]
        print(f"{k}: {t['first']}/{t['runs']} first, {t['executed']}/{t['runs']} executed, "
              f"{t['fired']}/{t['runs']} fired, {t['helper']}/{t['runs']} helper")
    results["tally"] = tally
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
