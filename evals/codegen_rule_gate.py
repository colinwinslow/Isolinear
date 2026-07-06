#!/usr/bin/env python3
"""Open-queue (o) — eval-gate the generation-side bare-non-ASCII prompt rule.

The 0.2.13 `_CODEGEN_PROMPT_RULES` rule ("labels must be Python string
literals; never use non-ASCII like ° / % as bare tokens") was failure-driven.
Two later mechanisms plausibly cover the class on their own:

  * 0.2.14 — the worker attaches `source_line` to every line-numbered
    violation, so repair sees the exact offending text instead of counting
    lines (the measured floor-model failure mode);
  * 0.2.17 — the unit-grounding rule reads the unit from
    ``history_series[i]['unit']`` (a str variable), keeping the ° symbol out
    of bare code literals structurally.

This eval runs the PRODUCTION codegen path (real
``OllamaCompatiblePlannerClient.generate_chart_code`` /
``repair_chart_code``, the real ``_CODEGEN_PROMPT_RULES`` and prompt-view
projection) against live Ollama + the live worker sandbox, with production-
shaped data (°F / % units, ``ts_epoch_ms`` points, derived_intervals bands) —
once WITH the rule and once WITHOUT it. If the without-rule arm shows no
bare-non-ASCII syntax errors, or shows them but repair recovers every one,
the rule is retirable (small floor models degrade on long rule lists).

NOTE: the older evals/codegen_reliability.py carries its own stale mirror of
the packet-5 rules and `degF` units — it cannot answer this question, which
is why this eval exists.

Config via env:
  OLLAMA_URL   (default http://10.0.1.39:11434)
  WORKER_URL   (default http://10.0.1.39:8080)
  WORKER_TOKEN (required; never printed)
  MODEL        (default gemma4:e4b — the production planner/codegen floor)
  RUNS         (default 3 — repeat runs; temp is 0 but GPU batching varies)
  MAX_REPAIRS  (default 3 — mirrors the live instance's setting)
  RESULTS_JSON (default evals/prompts/rule_gate_results.json)
  ONLY_CASES   (comma list of case ids; default all)
  ONLY_VARIANT (with_rule | without_rule; default both)
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
sys.path.insert(0, str(REPO))

from custom_components.isolinear import model_provider as mp  # noqa: E402

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.0.1.39:11434").rstrip("/")
WORKER_URL = os.environ.get("WORKER_URL", "http://10.0.1.39:8080").rstrip("/")
WORKER_TOKEN = os.environ.get("WORKER_TOKEN", "")
MODEL = os.environ.get("MODEL", "gemma4:e4b")
RUNS = int(os.environ.get("RUNS", "3"))
MAX_REPAIRS = int(os.environ.get("MAX_REPAIRS", "3"))
RESULTS_JSON = Path(os.environ.get("RESULTS_JSON", HERE / "prompts" / "rule_gate_results.json"))

# The rule under the gate, identified by its distinctive phrasing (the eval
# fails loudly if the rule text drifts rather than silently testing nothing).
RULE_MARKER = "bare Python tokens"


def gated_rule_index() -> int:
    hits = [i for i, r in enumerate(mp._CODEGEN_PROMPT_RULES) if RULE_MARKER in r]
    if len(hits) != 1:
        raise SystemExit(
            f"expected exactly one prompt rule containing {RULE_MARKER!r}, found {len(hits)} — "
            "the rule text drifted; update RULE_MARKER"
        )
    return hits[0]


# ------------------------- production-shaped cases --------------------------
# Points carry ts (schema) + ts_epoch_ms (D9) + value/raw_state/quality, units
# are the real HA strings ('°F', '%'), and the overlay case carries ADR-0033
# derived_intervals bands — everything the live pipeline hands the model.

_BASE_MS = 1751500800000  # 2026-07-03T00:00:00Z


def _pt(offset_min: int, value) -> dict:
    ms = _BASE_MS + offset_min * 60_000
    iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(ms / 1000))
    return {"ts": iso, "ts_epoch_ms": ms, "value": value, "raw_state": str(value), "quality": "ok"}


def _numeric_series(sid, eid, label, unit, base, amp, hours=24, step_min=10) -> dict:
    pts = []
    for i in range(0, hours * 60, step_min):
        v = round(base + amp * math.sin((i / (hours * 60)) * 2 * math.pi * (hours / 24) - 1.6), 1)
        pts.append(_pt(i, v))
    return {"series_id": sid, "entity_id": eid, "label": label, "kind": "numeric",
            "unit": unit, "points": pts, "source_entity_ids": [eid], "warnings": []}


def _hvac_series(sid, eid, label, hours=24, step_min=10) -> dict:
    pts = []
    for i in range(0, hours * 60, step_min):
        cooling = 11 * 60 <= (i % (24 * 60)) <= 16 * 60
        action = "cooling" if cooling else "idle"
        p = _pt(i, "cool")
        p["raw_state"] = "cool"
        p["attrs"] = {"hvac_action": action}
        pts.append(p)
    return {"series_id": sid, "entity_id": eid, "label": label, "kind": "categorical_state",
            "unit": None, "points": pts, "source_entity_ids": [eid], "warnings": []}


def _series_spec(sid, label, eid, unit, role="primary", render_as="line") -> dict:
    return {"series_id": sid, "label": label, "role": role, "render_as": render_as,
            "unit": unit, "source": {"type": "entity", "entity_id": eid}}


def _spec(title, chart_type, series, overlays=None) -> dict:
    return {"chart_id": "gate", "chart_type": chart_type, "title": title,
            "time_range": {"type": "relative", "duration": "24h"},
            "series": series, "overlays": overlays or []}


def build_cases() -> dict[str, dict]:
    cases: dict[str, dict] = {}

    s = _numeric_series("kitchen", "sensor.kitchen_temperature", "Kitchen Temperature", "°F", 71, 4)
    cases["single_temp_f"] = {
        "prompt": "Show the kitchen temperature today",
        "request": {"chart_spec": _spec("Kitchen temperature today", "time_series",
                                        [_series_spec("kitchen", "Kitchen", "sensor.kitchen_temperature", "°F")]),
                    "history_series": [s], "derived_intervals": [],
                    "output": {"format": "png", "width": 800, "height": 480}},
    }

    k = _numeric_series("kitchen", "sensor.kitchen_temperature", "Kitchen", "°F", 71, 4, hours=48)
    b = _numeric_series("basement", "sensor.basement_temperature", "Basement", "°F", 64, 2, hours=48)
    cases["two_temp_f"] = {
        "prompt": "Show the kitchen and basement temperatures over the weekend",
        "request": {"chart_spec": _spec("Kitchen and basement temperature", "time_series",
                                        [_series_spec("kitchen", "Kitchen", "sensor.kitchen_temperature", "°F"),
                                         _series_spec("basement", "Basement", "sensor.basement_temperature", "°F",
                                                      role="secondary")]),
                    "history_series": [k, b], "derived_intervals": [],
                    "output": {"format": "png", "width": 800, "height": 480}},
    }

    t = _numeric_series("kitchen", "sensor.kitchen_temperature", "Kitchen", "°F", 72, 4)
    hv = _hvac_series("ac", "climate.kitchen_ecobee", "AC")
    bands = [{"start_ms": _BASE_MS + 11 * 3600_000, "end_ms": _BASE_MS + 16 * 3600_000,
              "color": "#4c78c8", "label": "cooling", "entity_id": "climate.kitchen_ecobee"}]
    overlays = [{"overlay_id": "ac", "label": "AC", "render_as": "shaded_intervals",
                 "color_map": {"cooling": "#4c78c8", "heating": "#e08030"},
                 "source": {"type": "entity", "entity_id": "climate.kitchen_ecobee",
                            "attribute": "hvac_action"}}]
    cases["overlay_temp_f"] = {
        "prompt": "Show the kitchen temperature and when the AC was running",
        "request": {"chart_spec": _spec("Kitchen temperature with AC activity", "time_series",
                                        [_series_spec("kitchen", "Kitchen", "sensor.kitchen_temperature", "°F")],
                                        overlays=overlays),
                    "history_series": [t, hv], "derived_intervals": bands,
                    "output": {"format": "png", "width": 800, "height": 480}},
    }

    h = _numeric_series("bath", "sensor.bathroom_humidity", "Bathroom Humidity", "%", 55, 12)
    cases["humidity_pct"] = {
        "prompt": "Show the bathroom humidity over the last day",
        "request": {"chart_spec": _spec("Bathroom humidity", "time_series",
                                        [_series_spec("bath", "Humidity", "sensor.bathroom_humidity", "%")]),
                    "history_series": [h], "derived_intervals": [],
                    "output": {"format": "png", "width": 800, "height": 480}},
    }

    w = _numeric_series("office", "sensor.office_temperature", "Office", "°F", 73, 5, hours=7 * 24, step_min=30)
    cases["aggregate_temp_f"] = {
        "prompt": "Show the average office temperature per day this week",
        "request": {"chart_spec": _spec("Average office temperature per day", "bar",
                                        [_series_spec("office", "Avg Temperature", "sensor.office_temperature",
                                                      "°F", render_as="bar")]),
                    "history_series": [w], "derived_intervals": [],
                    "output": {"format": "png", "width": 800, "height": 480}},
    }

    d = _numeric_series("bed", "sensor.bedroom_temperature", "Bedroom", "°F", 69, 3, hours=72, step_min=15)
    cases["histogram_temp_f"] = {
        "prompt": "Show the distribution of the bedroom temperature",
        "request": {"chart_spec": _spec("Bedroom temperature distribution", "histogram",
                                        [_series_spec("bed", "Temperature", "sensor.bedroom_temperature",
                                                      "°F", render_as="bar")]),
                    "history_series": [d], "derived_intervals": [],
                    "output": {"format": "png", "width": 800, "height": 480}},
    }
    return cases


# ------------------------------- worker render -------------------------------
def render(request_id: str, code: str, request: dict) -> dict:
    rr = {"request_id": request_id, "render_mode": "codegen",
          "chart_spec": request["chart_spec"], "history_series": request["history_series"],
          "derived_intervals": request["derived_intervals"], "output": request["output"],
          "theme": {}, "codegen": {"python_code": code, "max_repair_attempts": 0}}
    env = {"version": 1, "operation": "render_chart", "request_id": request_id, "render_request": rr}
    req = urllib.request.Request(
        f"{WORKER_URL}/v1/render", data=json.dumps(env).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {WORKER_TOKEN}",
                 "X-Isolinear-Worker-API-Version": "1"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)["render_result"]


def _violations(res: dict) -> list[dict]:
    return (((res.get("error") or {}).get("details") or {}).get("violations")) or []


def is_bare_non_ascii(res: dict) -> bool:
    """The gated failure class: CPython tokenizer rejecting a bare non-ASCII
    token — `invalid character '°' (U+00B0)` and friends."""
    for v in _violations(res):
        if v.get("code") != "syntax_error":
            continue
        msg = (v.get("message") or "")
        if "invalid character" in msg:
            return True
        src = v.get("source_line") or ""
        if any(ord(c) > 127 for c in src):
            return True
    return False


def attempt_view(n: int, res: dict, gen_s: float, loc: int) -> dict:
    status = res.get("status")
    err = res.get("error") or {}
    return {"n": n, "gen_s": gen_s, "loc": loc, "status": status,
            "error_code": err.get("code"),
            "bare_non_ascii": is_bare_non_ascii(res),
            "violations": [f"{v.get('code')}@L{v.get('line')}: {(v.get('message') or '')[:120]}"
                           for v in _violations(res)]}


# --------------------------------- run loop ----------------------------------
def run_one(client, case_id: str, case: dict, variant: str, run_n: int, results: dict) -> None:
    request = case["request"]
    key = f"{case_id}::{variant}::run{run_n}"
    if results["runs"].get(key, {}).get("done"):
        return
    rec = {"case": case_id, "variant": variant, "run": run_n, "attempts": [],
           "accepted": False, "bare_incidents": 0, "bare_recovered": False, "done": False}
    code, sandbox_error = None, None
    for attempt in range(MAX_REPAIRS + 1):
        t0 = time.time()
        if code is None:
            gen = client.generate_chart_code(request)
        else:
            gen = client.repair_chart_code(code, sandbox_error, request)
        gen_s = round(time.time() - t0, 1)
        if not gen.get("accepted"):
            rec["attempts"].append({"n": attempt, "gen_s": gen_s,
                                    "provider_failure": gen.get("code")})
            break
        code = gen["python_code"]
        rid = f"gate_{case_id}_{variant}_{run_n}_{attempt}"
        try:
            res = render(rid, code, request)
        except Exception as exc:
            rec["attempts"].append({"n": attempt, "gen_s": gen_s,
                                    "error": f"harness:{type(exc).__name__}:{exc}"})
            break
        att = attempt_view(attempt, res, gen_s, len(code.splitlines()))
        rec["attempts"].append(att)
        if att["bare_non_ascii"]:
            rec["bare_incidents"] += 1
        if res.get("status") == "success":
            rec["accepted"] = True
            rec["repairs"] = attempt
            if rec["bare_incidents"] and attempt > 0:
                rec["bare_recovered"] = True
            break
        if attempt == MAX_REPAIRS:
            rec["final_code"] = code
            break
        sandbox_error = res.get("error") or {}
    rec["done"] = True
    results["runs"][key] = rec
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    last = rec["attempts"][-1] if rec["attempts"] else {}
    print(f"[{key}] {'ACCEPT' if rec['accepted'] else 'REJECT'} "
          f"attempts={len(rec['attempts'])} bare°={rec['bare_incidents']} "
          f"last={last.get('status') or last.get('error') or last.get('provider_failure')}",
          flush=True)


def main() -> int:
    if not WORKER_TOKEN:
        print("WORKER_TOKEN required", file=sys.stderr)
        return 2
    idx = gated_rule_index()
    original_rules = list(mp._CODEGEN_PROMPT_RULES)
    without = [r for i, r in enumerate(original_rules) if i != idx]
    variants = {"with_rule": original_rules, "without_rule": without}
    only_variant = os.environ.get("ONLY_VARIANT", "").strip()
    if only_variant:
        variants = {only_variant: variants[only_variant]}

    cases = build_cases()
    only = {s.strip() for s in os.environ.get("ONLY_CASES", "").split(",") if s.strip()}
    if only:
        cases = {k: v for k, v in cases.items() if k in only}

    results = json.loads(RESULTS_JSON.read_text()) if RESULTS_JSON.exists() else {"meta": {}, "runs": {}}
    results["meta"] = {"model": MODEL, "worker": WORKER_URL, "ollama": OLLAMA_URL,
                       "runs": RUNS, "max_repairs": MAX_REPAIRS,
                       "gated_rule": original_rules[idx],
                       "started": results["meta"].get("started")
                       or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    client = mp.OllamaCompatiblePlannerClient(endpoint_url=OLLAMA_URL, planner_model=MODEL)
    try:
        for case_id, case in cases.items():
            for variant, rules in variants.items():
                mp._CODEGEN_PROMPT_RULES = rules
                for run_n in range(1, RUNS + 1):
                    run_one(client, case_id, case, variant, run_n, results)
    finally:
        mp._CODEGEN_PROMPT_RULES = original_rules

    # ---- tally ----
    tally: dict[str, dict] = {}
    for rec in results["runs"].values():
        t = tally.setdefault(rec["variant"], {"runs": 0, "accepted": 0, "first_attempt": 0,
                                              "bare_incidents": 0, "bare_recovered": 0,
                                              "bare_unrecovered": 0})
        t["runs"] += 1
        if rec.get("accepted"):
            t["accepted"] += 1
            if rec.get("repairs", 0) == 0:
                t["first_attempt"] += 1
        if rec.get("bare_incidents"):
            t["bare_incidents"] += 1
            if rec.get("accepted"):
                t["bare_recovered"] += 1
            else:
                t["bare_unrecovered"] += 1
    results["tally"] = tally
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    print("\n=== TALLY ===")
    for variant, t in tally.items():
        print(f"  {variant}: {t['accepted']}/{t['runs']} accepted "
              f"({t['first_attempt']} first-attempt); runs with a bare-non-ASCII incident: "
              f"{t['bare_incidents']} (recovered {t['bare_recovered']}, "
              f"unrecovered {t['bare_unrecovered']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
