#!/usr/bin/env python3
"""Eval-gate the codegen timeline render path (spec timeline-codegen-rendering).

Live e2e-09 ("When was the kitchen door open today?") on the deployed 0.2.42 is
accept != quality: a primary binary timeline routes to codegen with EMPTY
derived_intervals (overlays:[]), so the model draws near-zero-width axvspan
verticals off raw points and answers "0.0 minutes" (run
evals/e2e_runs/20260717T215239Z/). This packet: the integration precomputes the
state intervals for a PRIMARY timeline (C1, reusing the trusted _binary_on_regions
logic) and the prompt tells the model to draw a broken_barh lane from them (C2)
and to sum THOSE intervals for the duration answer (C3), grounded by an
independent state_duration recompute (C4).

This gate drives the PRODUCTION codegen path against live gemma4:e4b with the
timeline chart_spec + the C1-precomputed derived_intervals, two arms:

  * without_timeline — production rules minus the broken_barh timeline rule
    (marker-gated removal, rule-gate pattern) — reproduces the e2e-09 verticals;
  * with_timeline    — production rules as-is (the timeline prescription).

Execution-truth judge, two parts:
  * RENDER: a broken_barh lane fires (>=1 PolyCollection, NO numeric line); an
    axvspan-verticals draw (patches, no collection) or a state-as-line fails.
  * ANSWER: the returned meta carries a non-degenerate state_duration claim that
    run_grounding_check VERIFIES against the raw points (kills the 0.0-min class).

`fired` = RENDER clean AND ANSWER grounded. If the with arm cannot reach that,
the spec kill-condition triggers (route timeline -> Pillow); record it here.

Config via env: OLLAMA_URL, MODEL, EXEC_PY, RUNS (default 3), MAX_REPAIRS
(default 2), RESULTS_JSON, ONLY_ARM.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

from custom_components.isolinear import model_provider as mp  # noqa: E402
from custom_components.isolinear.render_dispatch import _compute_derived_intervals  # noqa: E402
from custom_components.isolinear.answer_grounding import run_grounding_check  # noqa: E402

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.0.1.39:11434").rstrip("/")
MODEL = os.environ.get("MODEL", "gemma4:e4b")
EXEC_PY = os.environ.get("EXEC_PY", "/home/claude/.expenv/bin/python")
RUNS = int(os.environ.get("RUNS", "3"))
MAX_REPAIRS = int(os.environ.get("MAX_REPAIRS", "2"))
RESULTS_JSON = Path(os.environ.get("RESULTS_JSON", HERE / "prompts" / "timeline_render_gate_results.json"))

PROMPT = "When was the kitchen door open today?"

# The broken_barh timeline rule under the gate, identified by distinctive phrasing
# (fail loudly if the rule text drifts — rule-gate pattern). It is one list entry.
TIMELINE_MARKER = "you are drawing a TIMELINE step track"

# "Today" base: 2026-07-17T00:00:00Z. Three brief openings → 2 + 4 + 3 = 9 min on.
_BASE = datetime(2026, 7, 17, 0, 0, 0, tzinfo=timezone.utc)
_OPENINGS = [(13 * 3600 + 16 * 60, 2 * 60), (15 * 3600, 4 * 60), (20 * 3600, 3 * 60)]
_EXPECTED_ON_MS = sum(dur for _, dur in _OPENINGS) * 1000  # 540_000


def rules_without_timeline() -> list[str]:
    hits = [i for i, r in enumerate(mp._CODEGEN_PROMPT_RULES) if TIMELINE_MARKER in r]
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one rule containing {TIMELINE_MARKER!r}, found {len(hits)}")
    return [r for i, r in enumerate(mp._CODEGEN_PROMPT_RULES) if i != hits[0]]


def _door_series() -> dict:
    """A binary door with three brief openings today. Points carry BOTH 'ts'
    (ISO — read by the region precompute _state_segments) and 'ts_epoch_ms' (read
    by the model + grounding), like the real build site."""
    def _pt(offset_s: int, state: str) -> dict:
        ts = _BASE.timestamp() + offset_s
        iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(ts))
        return {"ts": iso, "ts_epoch_ms": int(ts * 1000), "value": state,
                "raw_state": state, "quality": "ok"}
    pts = [_pt(0, "off")]
    for start_s, dur_s in _OPENINGS:
        pts.append(_pt(start_s, "on"))
        pts.append(_pt(start_s + dur_s, "off"))
    pts.append(_pt(24 * 3600 - 60, "off"))  # end-of-day sentinel
    return {"series_id": "series-001", "entity_id": "binary_sensor.kitchen_door",
            "label": "Kitchen Door", "kind": "binary_state", "unit": "",
            "points": pts, "source": "recorder", "warnings": []}


def _request() -> dict:
    door = _door_series()
    chart_spec = {
        "chart_id": "kitchen_door_timeline", "chart_type": "timeline",
        "title": "Kitchen Door", "time_range": {"type": "relative", "duration": "1d"},
        "series": [{"series_id": "series-001", "label": "Kitchen Door", "role": "primary",
                    "render_as": "step", "transform": {"operation": "none", "window": None},
                    "unit": "", "source": {"type": "entity",
                                           "entity_id": "binary_sensor.kitchen_door",
                                           "attribute": None}}],
        "overlays": [], "x_axis": {"type": "time"}, "y_axis": {},
    }
    history_series = [door]
    # C1 under test: the integration precomputes the intervals for the PRIMARY
    # timeline series (overlays:[] → the overlay path returns []).
    derived = _compute_derived_intervals(chart_spec, history_series)
    return {"chart_spec": chart_spec, "history_series": history_series,
            "derived_intervals": derived,
            "output": {"format": "png", "width": 800, "height": 480}}


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
            # Per-bar x-widths across broken_barh collections — an off-baseline track
            # spans ~the full window; on-bars are narrower.
            widths = []
            for col in ax.collections:
                try:
                    for path in col.get_paths():
                        xs = path.vertices[:, 0]
                        if len(xs):
                            widths.append(float(xs.max() - xs.min()))
                except Exception:
                    pass
            yticks = [str(t.get_text()) for t in ax.get_yticklabels() if str(t.get_text())]
            axes.append({"xlabel": str(ax.get_xlabel()), "ylabel": str(ax.get_ylabel()),
                         "xlim": xl, "n_lines": len(ax.get_lines()),
                         "n_patches": len(ax.patches), "n_images": len(ax.images),
                         "n_collections": len(ax.collections),
                         "bar_widths": widths, "yticks": yticks})
    import os
    meta_out = meta if isinstance(meta, dict) else {}
    print("__R__" + json.dumps({"ok": True, "axes": axes,
        "answer_text": meta_out.get("answer_text"), "claims": meta_out.get("claims"),
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


def judge(execution: dict, request: dict) -> dict:
    """RENDER: a broken_barh lane (>=1 collection, no numeric line) fires; axvspan
    verticals (patches, 0 collections) or a state line fails. ANSWER: a
    state_duration claim that grounds VERIFIED and is non-degenerate fires."""
    v = {"fired": False, "render_ok": False, "answer_ok": False, "why": ""}
    axes = execution.get("axes") or []
    # A CLEAN state lane (not just "is broken_barh"): no numeric line; a grey
    # off-baseline track spanning ~the whole window (>=85% of the x-range); at
    # least one narrower on-bar; and entity y-ticks, NOT an on/off value axis
    # (the eyes-on failure the first gate over-reported).
    _STATE_WORDS = {"on", "off", "open", "closed", "true", "false", "1", "0"}
    lane = []
    for a in axes:
        if a["n_lines"] != 0:
            continue
        span = (a["xlim"][1] - a["xlim"][0]) or 1.0
        widths = a.get("bar_widths") or []
        has_offtrack = any(w >= 0.85 * span for w in widths)
        has_onbars = any(0 < w < 0.85 * span for w in widths)
        lane_labels = [y for y in (a.get("yticks") or []) if y.strip().lower() not in _STATE_WORDS]
        if has_offtrack and has_onbars and lane_labels:
            lane.append(a)
    if lane:
        v["render_ok"] = True
    else:
        v["why"] = f"no clean state lane (off-track+on-bars+entity y-ticks): {[_a(a) for a in axes]}"

    grounded = run_grounding_check(
        {"answer_text": execution.get("answer_text"), "claims": execution.get("claims") or []},
        request["history_series"])
    dur_claims = [c for c in (execution.get("claims") or [])
                  if isinstance(c, dict) and c.get("metric") == "state_duration"]
    dur_val = dur_claims[0].get("value") if dur_claims else None
    non_degenerate = isinstance(dur_val, (int, float)) and dur_val > 0
    if grounded.get("outcome") == "verified" and not grounded.get("withheld") and non_degenerate:
        v["answer_ok"] = True
    else:
        v["why"] = (v["why"] + " | " if v["why"] else "") + (
            f"answer not grounded: outcome={grounded.get('outcome')} "
            f"withheld={grounded.get('withheld')} dur_ms={dur_val}")
    v["grounding_outcome"] = grounded.get("outcome")
    v["duration_ms"] = dur_val
    v["fired"] = v["render_ok"] and v["answer_ok"]
    if v["fired"]:
        v["why"] = f"clean timeline lane + grounded {dur_val} ms (expected ~{_EXPECTED_ON_MS})"
    return v


def _a(a: dict) -> str:
    span = (a["xlim"][1] - a["xlim"][0]) or 1.0
    widths = a.get("bar_widths") or []
    wfrac = [round(w / span, 2) for w in widths]
    return (f"lines={a['n_lines']} patches={a['n_patches']} coll={a['n_collections']} "
            f"img={a['n_images']} bar_w_frac={wfrac} yticks={a.get('yticks')}")


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
            att["axes"] = execution.get("axes")
            att["answer_text"] = execution.get("answer_text")
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
          f"render_ok={vv.get('render_ok')} answer_ok={vv.get('answer_ok')} "
          f"attempts={len(rec['attempts'])} — {vv.get('why', 'n/a')}", flush=True)


def main() -> int:
    arms = {"without_timeline": rules_without_timeline(),
            "with_timeline": list(mp._CODEGEN_PROMPT_RULES)}
    only_arm = os.environ.get("ONLY_ARM", "").strip()
    if only_arm:
        arms = {only_arm: arms[only_arm]}

    results = json.loads(RESULTS_JSON.read_text()) if RESULTS_JSON.exists() else {"meta": {}, "runs": {}}
    results["meta"] = {"model": MODEL, "ollama": OLLAMA_URL, "runs": RUNS,
                       "max_repairs": MAX_REPAIRS, "prompt": PROMPT,
                       "expected_on_ms": _EXPECTED_ON_MS,
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
        t = tally.setdefault(rec["arm"], {"runs": 0, "executed": 0, "render_ok": 0, "answer_ok": 0, "fired": 0})
        t["runs"] += 1
        t["executed"] += bool(rec.get("executed"))
        vv = rec.get("verdict") or {}
        t["render_ok"] += bool(vv.get("render_ok"))
        t["answer_ok"] += bool(vv.get("answer_ok"))
        t["fired"] += bool(rec.get("fired"))
    print("\n=== tally ===")
    for arm, t in sorted(tally.items()):
        print(f"{arm}: {t['fired']}/{t['runs']} clean (render {t['render_ok']}, "
              f"answer {t['answer_ok']}, {t['executed']} executed)")
    results["tally"] = tally
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
