#!/usr/bin/env python3
"""Eval-gate the entity-id-keyed combined-frame rule (open-queue (B) real fix).

Live root cause (reproduced 2026-07-08 against gemma4:e4b via the production
codegen path): the multi-sensor cross-math family (mean/delta/deviation) throws
an intermittent runtime_error that the worker logs only as `error=runtime_error`
(no traceback). Reproducing it captured the traceback:

    KeyError: 'sensor.kitchen_ecobee_temperature'
      File "<string>", line 44, in render_chart
      pandas/core/frame.py __getitem__ -> columns.get_loc(key) -> raise KeyError

The floor model builds `combined = pandas.concat([s1, s2], axis=1)` (columns are
a POSITIONAL RangeIndex 0,1) then sometimes indexes it by entity_id
(`combined['sensor.…']`) -> KeyError. It is intermittent because at temperature 0
Ollama still varies run-to-run whether it names the columns, uses positional
access, or assumes entity_id column names. This is a fix-RATE bug in the
generated cross-sensor math, NOT the intent-erosion the (B) packet was first
framed around (the repair-intent-retention rule showed no eval separation —
gemma retains intent on clean errors 3/3 either arm; see
evals/repair_intent_retention_gate.py).

The fix (mechanism-proven deterministically): the alignment-idiom rule now
prescribes keying the combined frame by entity_id
(`pandas.concat({s['entity_id']: aligned_s ...}, axis=1)`), so column access by
entity_id is safe; it also names positional access and mean(axis=1) and warns
that a bare-list concat gives positional columns.

This gate drives the PRODUCTION generation path against live gemma4:e4b on the
real cross-sensor-mean prompt, two arms (marker surgery on the alignment rule):

  * without_keying — the frame-keying sentence stripped (pre-(B) behaviour);
  * with_keying    — production rules as-is.

Per run: generate once, execute in the sandbox harness, record whether it
executed on the FIRST attempt and whether the failure (if any) was the entity-id
KeyError. The base incidence is low (~1/18 on synthetic 48-point series; higher
on real-data shapes), so this gate is a DIRECTIONAL signal on top of the
deterministic mechanism proof + the live worker-log evidence, not a high-power
test — read the KeyError counts, not just the pass rate. Bump RUNS for more
power.

Config via env: OLLAMA_URL, MODEL, EXEC_PY, RUNS (default 12), RESULTS_JSON,
ONLY_ARM.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

from custom_components.isolinear import model_provider as mp  # noqa: E402
# Reuse the retention gate's request builder + sandbox-harness executor.
from evals import repair_intent_retention_gate as rig  # noqa: E402

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.0.1.39:11434").rstrip("/")
MODEL = os.environ.get("MODEL", "gemma4:e4b")
RUNS = int(os.environ.get("RUNS", "12"))
RESULTS_JSON = Path(os.environ.get("RESULTS_JSON", HERE / "prompts" / "crossmath_frame_keying_results.json"))

PROMPT = "What is the average of the kitchen and family room temperatures?"

# The frame-keying prescription under the gate, identified by distinctive
# phrasing — fail loudly if the rule text drifts (rule-gate pattern).
KEYING_MARKER = "KEYED BY ENTITY_ID"
KEYING_RE = re.compile(
    r"Build that combined frame KEYED BY ENTITY_ID:.*?raises KeyError \(a live "
    r"cross-math failure\)\. ", re.S)

KEYERROR_RE = re.compile(r"KeyError")


def rules_without_keying() -> list[str]:
    hits = [i for i, r in enumerate(mp._CODEGEN_PROMPT_RULES) if KEYING_MARKER in r]
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one rule containing {KEYING_MARKER!r}, found {len(hits)}")
    rules = list(mp._CODEGEN_PROMPT_RULES)
    stripped = KEYING_RE.sub("", rules[hits[0]])
    if KEYING_MARKER in stripped:
        raise SystemExit("frame-keying sentence removal failed — update KEYING_RE")
    rules[hits[0]] = stripped
    return rules


def run_one(client, arm, run_n, results) -> None:
    key = f"{arm}::run{run_n}"
    if results["runs"].get(key, {}).get("done"):
        return
    request = rig._request()
    t0 = time.time()
    gen = client.generate_chart_code(request, user_request=PROMPT)
    gen_s = round(time.time() - t0, 1)
    rec = {"arm": arm, "run": run_n, "done": True, "executed": False, "keyerror": False}
    if not gen.get("accepted"):
        rec["provider_failure"] = gen.get("code")
    else:
        code = gen["python_code"]
        ex = rig.execute(code, request)
        rec["executed"] = bool(ex.get("ok"))
        rec["loc"] = len(code.splitlines())
        rec["gen_s"] = gen_s
        if not ex.get("ok"):
            err = ex.get("error") or ""
            rec["error"] = err
            rec["keyerror"] = bool(KEYERROR_RE.search(err) or KEYERROR_RE.search(ex.get("traceback") or ""))
    results["runs"][key] = rec
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    tag = "OK" if rec["executed"] else ("KEYERROR" if rec["keyerror"] else "fail")
    print(f"[{key}] {tag} — {rec.get('error', 'executed')}", flush=True)


def main() -> int:
    only_arm = os.environ.get("ONLY_ARM", "").strip()
    arms = {"without_keying": rules_without_keying(),
            "with_keying": list(mp._CODEGEN_PROMPT_RULES)}
    if only_arm:
        arms = {only_arm: arms[only_arm]}

    results = json.loads(RESULTS_JSON.read_text()) if RESULTS_JSON.exists() else {"meta": {}, "runs": {}}
    results["meta"] = {"model": MODEL, "ollama": OLLAMA_URL, "runs": RUNS, "prompt": PROMPT,
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
        t = tally.setdefault(rec["arm"], {"runs": 0, "executed": 0, "keyerror": 0})
        t["runs"] += 1
        t["executed"] += bool(rec.get("executed"))
        t["keyerror"] += bool(rec.get("keyerror"))
    print("\n=== tally ===")
    for arm, t in sorted(tally.items()):
        print(f"{arm}: {t['executed']}/{t['runs']} first-attempt executed, "
              f"{t['keyerror']} entity-id KeyErrors")
    results["tally"] = tally
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
