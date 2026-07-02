#!/usr/bin/env python3
"""ADR-0029 packet 5 — codegen reliability eval.

For each chartable prompt in evals/prompts/benchmark_prompts.json, build a
representative ChartSpec + synthetic history, then for each configured model:
generate matplotlib code -> render through the worker sandbox -> on a retryable
failure, ask the model to repair (feeding the sandbox error) up to a cap. Record
accept / reject / repair outcomes and the produced image id.

This measures whether a 3060-class local model can produce correct, safe
matplotlib code (the data the ADR-0029 keep/remove decision rests on). It talks
to a running worker (packet 2/3) over HTTP and a real Ollama endpoint. Results
are written incrementally and the run is resumable.

Config via env:
  OLLAMA_URL   (default http://10.0.1.39:11434)
  WORKER_URL   (default http://10.0.1.39:8080)
  WORKER_TOKEN (required)
  MODELS       (comma list; default "gemma4:e4b,qwen2.5-coder:7b")
  RESULTS_JSON (default evals/prompts/reliability_results.json)
  MAX_REPAIRS  (default 2)
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CORPUS = HERE / "prompts" / "benchmark_prompts.json"

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.0.1.39:11434").rstrip("/")
WORKER_URL = os.environ.get("WORKER_URL", "http://10.0.1.39:8080").rstrip("/")
WORKER_TOKEN = os.environ.get("WORKER_TOKEN", "")
MODELS = [m.strip() for m in os.environ.get("MODELS", "gemma4:e4b,qwen2.5-coder:7b").split(",") if m.strip()]
RESULTS_JSON = Path(os.environ.get("RESULTS_JSON", HERE / "prompts" / "reliability_results.json"))
MAX_REPAIRS = int(os.environ.get("MAX_REPAILS", os.environ.get("MAX_REPAIRS", "2")))

# ---- codegen prompt (mirrors custom_components/isolinear/model_provider.py) ----
SYSTEM = ("You are the Isolinear chart-code generator. Return ONLY Python source code "
          "for a single function; no prose, no explanation, no markdown outside a code fence.")
RULES = [
    "Define exactly one top-level function: def render_chart(data, output_path):",
    "Implement the supplied chart_spec using matplotlib and the supplied history_series.",
    "Read the series points from data['history_series']; each point has 'ts' and 'value'.",
    "Save the figure to output_path as PNG (fig.savefig(output_path, format='png')).",
    "You may import matplotlib and numpy, plus the stdlib helpers datetime, math, "
    "statistics, json, itertools, functools, collections, and typing. Do NOT use pandas "
    "or any other third-party library. No os, sys, socket, requests, subprocess, open() "
    "on arbitrary paths, or network access.",
    "Do not read environment variables, secrets, tokens, or files other than writing "
    "the figure to output_path.",
    "Return a small metadata dict (title, series_plotted, warnings-as-a-list) from render_chart.",
    "Return only the code — no commentary, no example invocation.",
]


def strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if "```" in t[3:] else t[3:]
        if t.lower().startswith("python"):
            t = t[6:]
    if t.endswith("```"):
        t = t[:-3]
    return t.strip()


# ---------------------------- synthetic data --------------------------------
def _iso(day: int, hour: int) -> str:
    return f"2026-06-{20 + day:02d}T{hour:02d}:00:00Z"


def _numeric_points(base: float, amp: float, step_h: int = 2) -> list[dict]:
    pts = []
    for i, h in enumerate(range(0, 24, step_h)):
        v = round(base + amp * math.sin((h / 24) * 2 * math.pi - 1.6), 1)
        pts.append({"ts": _iso(0, h), "value": v, "raw_state": str(v), "quality": "ok"})
    return pts


def _numeric_series(sid: str, eid: str, label: str, base: float, amp: float) -> dict:
    return {"series_id": sid, "entity_id": eid, "label": label, "kind": "numeric",
            "unit": "degF", "points": _numeric_points(base, amp),
            "source_entity_ids": [eid], "warnings": []}


def _binary_series(sid: str, eid: str, label: str, on_hours: set[int]) -> dict:
    pts = []
    for h in range(0, 24):
        state = "on" if h in on_hours else "off"
        pts.append({"ts": _iso(0, h), "value": 1 if state == "on" else 0,
                    "raw_state": state, "quality": "ok"})
    return {"series_id": sid, "entity_id": eid, "label": label, "kind": "binary_state",
            "unit": None, "points": pts, "source_entity_ids": [eid], "warnings": []}


def _multi_day_numeric(sid: str, eid: str, label: str, base: float) -> dict:
    pts = []
    for d in range(7):
        for h in (6, 12, 18):
            v = round(base + 3 * math.sin(d) + (h - 12) * 0.2, 1)
            pts.append({"ts": _iso(d, h), "value": v, "raw_state": str(v), "quality": "ok"})
    return {"series_id": sid, "entity_id": eid, "label": label, "kind": "numeric",
            "unit": "degF", "points": pts, "source_entity_ids": [eid], "warnings": []}


def _chart_spec(chart_id, chart_type, title, series, overlays=None, extra=None):
    spec = {"chart_id": chart_id, "chart_type": chart_type, "title": title,
            "time_range": {"type": "relative", "duration": "24h"},
            "series": series, "overlays": overlays or []}
    if extra:
        spec.update(extra)
    return spec


def build_case(prompt: dict):
    """Return (chart_spec, history_series, derived_intervals) or None if not chartable."""
    fam = (prompt.get("expect") or {}).get("render_family")
    title = prompt["prompt"]
    if fam in (None, "clarification", "refuse"):
        return None

    if fam == "time_series":
        multi = (prompt.get("expect") or {}).get("series") == 2
        if multi:
            s1 = _numeric_series("upstairs", "sensor.upstairs_temperature", "Upstairs", 70, 4)
            s2 = _numeric_series("downstairs", "sensor.downstairs_temperature", "Downstairs", 67, 3)
            spec = _chart_spec("c", "time_series", title,
                               [{"series_id": "upstairs", "label": "Upstairs", "role": "primary",
                                 "render_as": "line", "unit": "degF",
                                 "source": {"type": "entity", "entity_id": "sensor.upstairs_temperature"}},
                                {"series_id": "downstairs", "label": "Downstairs", "role": "secondary",
                                 "render_as": "line", "unit": "degF",
                                 "source": {"type": "entity", "entity_id": "sensor.downstairs_temperature"}}])
            return spec, [s1, s2], []
        s = _numeric_series("temp", "sensor.room_temperature", "Temperature", 70, 5)
        spec = _chart_spec("c", "time_series", title,
                           [{"series_id": "temp", "label": "Temperature", "role": "primary",
                             "render_as": "line", "unit": "degF",
                             "source": {"type": "entity", "entity_id": "sensor.room_temperature"}}])
        return spec, [s], []

    if fam == "time_series_overlay":
        num = _numeric_series("temp", "sensor.room_temperature", "Temperature", 71, 4)
        bins = _binary_series("ac", "binary_sensor.ac_running", "AC Running", {11, 12, 13, 14, 15})
        overlays = [{"overlay_id": "ac", "label": "AC Running", "render_as": "shaded_intervals",
                     "source": {"type": "entity", "entity_id": "binary_sensor.ac_running"}}]
        spec = _chart_spec("c", "time_series", title,
                           [{"series_id": "temp", "label": "Temperature", "role": "primary",
                             "render_as": "line", "unit": "degF",
                             "source": {"type": "entity", "entity_id": "sensor.room_temperature"}}],
                           overlays=overlays)
        intervals = [{"entity_id": "binary_sensor.ac_running", "state": "on",
                      "start": _iso(0, 11), "end": _iso(0, 16)}]
        return spec, [num, bins], intervals

    if fam == "timeline":
        b = _binary_series("door", "binary_sensor.kitchen_door", "Kitchen Door", {7, 8, 13, 18, 19})
        spec = _chart_spec("c", "timeline", title,
                           [{"series_id": "door", "label": "Kitchen Door", "role": "primary",
                             "render_as": "step",
                             "source": {"type": "entity", "entity_id": "binary_sensor.kitchen_door"}}])
        return spec, [b], []

    if fam == "histogram":
        # denser numeric sample for a distribution
        import random
        random.seed(7)
        pts = [{"ts": _iso(0, 0), "value": round(random.gauss(70, 3), 1),
                "raw_state": "x", "quality": "ok"} for _ in range(60)]
        s = {"series_id": "temp", "entity_id": "sensor.room_temperature", "label": "Temperature",
             "kind": "numeric", "unit": "degF", "points": pts,
             "source_entity_ids": ["sensor.room_temperature"], "warnings": []}
        spec = _chart_spec("c", "histogram", title,
                           [{"series_id": "temp", "label": "Temperature", "role": "primary",
                             "render_as": "bar", "unit": "degF",
                             "source": {"type": "entity", "entity_id": "sensor.room_temperature"}}])
        return spec, [s], []

    if fam == "aggregate_bar":
        s = _multi_day_numeric("temp", "sensor.room_temperature", "Temperature", 70)
        spec = _chart_spec("c", "bar", title,
                           [{"series_id": "temp", "label": "Avg Temperature", "role": "primary",
                             "render_as": "bar", "unit": "degF",
                             "source": {"type": "entity", "entity_id": "sensor.room_temperature"}}])
        return spec, [s], []

    return None


# ------------------------------- clients ------------------------------------
def _post(url, body, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _request_view(chart_spec, history_series, derived_intervals):
    return {"chart_spec": chart_spec, "history_series": history_series,
            "derived_intervals": derived_intervals, "output": {"format": "png", "width": 800, "height": 480}}


def generate_code(model, view, prev_code=None, error=None):
    if prev_code is None:
        payload = {"task": "Write Python matplotlib code that renders the supplied, already-validated "
                           "Isolinear ChartSpec using the supplied history_series data.",
                   "rules": RULES, "codegen_request": view}
    else:
        payload = {"task": "The previous render_chart code failed in the sandbox. Return corrected "
                           "Python matplotlib code that fixes the reported error and still implements the ChartSpec.",
                   "rules": RULES, "previous_code": prev_code, "sandbox_error": error, "codegen_request": view}
    body = {"model": model, "stream": False, "options": {"temperature": 0},
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": json.dumps(payload, separators=(",", ":"))}]}
    t = time.time()
    resp = _post(f"{OLLAMA_URL}/api/chat", body, {}, timeout=240)
    return strip_fences(resp["message"]["content"]), round(time.time() - t, 1)


def render(request_id, code, chart_spec, history_series, derived_intervals):
    rr = {"request_id": request_id, "render_mode": "codegen", "chart_spec": chart_spec,
          "history_series": history_series, "derived_intervals": derived_intervals,
          "output": {"format": "png", "width": 800, "height": 480}, "theme": {},
          "codegen": {"python_code": code, "max_repair_attempts": 0}}
    env = {"version": 1, "operation": "render_chart", "request_id": request_id, "render_request": rr}
    resp = _post(f"{WORKER_URL}/v1/render", env,
                 {"Authorization": f"Bearer {WORKER_TOKEN}", "X-Isolinear-Worker-API-Version": "1"}, timeout=90)
    return resp["render_result"]


SECURITY_VIOLATIONS = {"forbidden_import", "forbidden_attribute", "forbidden_call",
                       "dunder_attribute", "scope_escape"}


def error_view(res):
    err = res.get("error") or {}
    det = err.get("details") or {}
    return {"code": err.get("code"), "message": err.get("message"),
            "violations": det.get("violations") or [],
            "stderr": (det.get("stderr") or "")[-600:], "traceback": (det.get("traceback") or "")[-600:]}


def is_terminal(ecode, res):
    """Genuine security violations are terminal (don't coach past the gate).
    Syntax errors and disallowed-but-safe imports are repairable — feed them
    back so the model can adapt (the sandbox re-gates every attempt)."""
    if ecode != "unsafe_code":
        return False
    viols = ((res.get("error") or {}).get("details") or {}).get("violations") or []
    return any(v.get("code") in SECURITY_VIOLATIONS for v in viols)


# ------------------------------- run loop -----------------------------------
def slug(s):
    return "".join(c if c.isalnum() else "_" for c in s)


def load_results():
    if RESULTS_JSON.exists():
        return json.loads(RESULTS_JSON.read_text())
    return {"meta": {}, "cases": {}}


def main():
    if not WORKER_TOKEN:
        print("WORKER_TOKEN required", file=sys.stderr)
        return 2
    corpus = json.loads(CORPUS.read_text())
    prompts = corpus["prompts"]
    only = {s.strip() for s in os.environ.get("ONLY_IDS", "").split(",") if s.strip()}
    if only:
        prompts = [p for p in prompts if p["id"] in only]
    results = load_results()
    results["meta"] = {"models": MODELS, "worker": WORKER_URL, "ollama": OLLAMA_URL,
                       "max_repairs": MAX_REPAIRS, "started": results["meta"].get("started") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    for p in prompts:
        pid = p["id"]
        case = build_case(p)
        entry = results["cases"].setdefault(pid, {"prompt": p["prompt"], "category": p["category"],
                                                   "expect": p.get("expect"), "chartable": case is not None, "models": {}})
        if case is None:
            entry["chartable"] = False
            continue
        chart_spec, history_series, derived_intervals = case
        view = _request_view(chart_spec, history_series, derived_intervals)
        for model in MODELS:
            if model in entry["models"] and entry["models"][model].get("done"):
                continue
            mslug = slug(model)
            rid = f"{pid}__{mslug}"
            rec = {"attempts": [], "accepted": False, "repairs": 0, "image_id": None, "done": False}
            code, prev_err = None, None
            for attempt in range(MAX_REPAIRS + 1):
                try:
                    code, gen_s = generate_code(model, view, prev_code=code, error=prev_err)
                    res = render(rid, code, chart_spec, history_series, derived_intervals)
                except Exception as exc:  # transport / model error
                    rec["attempts"].append({"n": attempt, "error": f"harness:{type(exc).__name__}:{exc}"})
                    break
                status = res.get("status")
                ecode = (res.get("error") or {}).get("code")
                rec["attempts"].append({"n": attempt, "gen_s": gen_s, "status": status,
                                        "error_code": ecode, "loc": len(code.splitlines())})
                rec["code"] = code
                if status == "success":
                    rec["accepted"] = True
                    rec["repairs"] = attempt
                    rec["image_id"] = res.get("image_id")
                    break
                if is_terminal(ecode, res) or attempt == MAX_REPAIRS:
                    rec["repairs"] = attempt
                    rec["final_error"] = error_view(res)
                    break
                prev_err = error_view(res)  # repair with this error
            rec["done"] = True
            entry["models"][model] = rec
            RESULTS_JSON.write_text(json.dumps(results, indent=1))
            a = rec["attempts"][-1] if rec["attempts"] else {}
            print(f"[{pid}] {model}: {'ACCEPT' if rec['accepted'] else 'REJECT'} "
                  f"repairs={rec['repairs']} last={a.get('status') or a.get('error')}", flush=True)

    # tallies
    tally = {m: {"accept": 0, "reject": 0, "repaired": 0, "total": 0} for m in MODELS}
    for pid, e in results["cases"].items():
        if not e.get("chartable"):
            continue
        for m, r in e.get("models", {}).items():
            tally[m]["total"] += 1
            if r.get("accepted"):
                tally[m]["accept"] += 1
                if r.get("repairs", 0) > 0:
                    tally[m]["repaired"] += 1
            else:
                tally[m]["reject"] += 1
    results["tally"] = tally
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    print("\n=== TALLY ===")
    for m, t in tally.items():
        print(f"  {m}: {t['accept']}/{t['total']} accepted "
              f"({t['repaired']} needed repair), {t['reject']} rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
