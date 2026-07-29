#!/usr/bin/env python3
"""Repro the e2e-18 UnboundLocalError('plt') via the REPAIR path (packet H).

The live 0.2.35 WARNING logs showed the deviation prompt (job-003) failing as:
  attempt 1/4: grounding_verdict_absent (executed clean, but answer_text had no
               band/verdict label the grounding check could match)
  attempt 2/4: runtime_error — UnboundLocalError('plt')

So the bug is introduced by the REPAIR, not the initial generation (which imports
plt at module top and uses it cleanly — see scripts/repro_e2e18_unboundlocal.py,
8/8 clean). This script replays that chain: generate -> feed the real
grounding_verdict_absent synthetic error to repair_chart_code -> execute the
repair -> look for the plt scoping bug.

Classic mechanism under test: the repair keeps/adds `import matplotlib.pyplot as
plt` INSIDE render_chart (or otherwise assigns plt in the function body), which
makes Python treat plt as function-local for the WHOLE body, so the first
plt.subplots() before that line raises UnboundLocalError.

Env: OLLAMA_URL, MODEL, RUNS (default 8), TIMEOUT_S (default 300).
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "evals"))

from alignment_rule_gate import _irregular_series, _request, _series_spec, execute  # noqa: E402

from custom_components.isolinear import model_provider as mp  # noqa: E402

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.0.1.39:11434").rstrip("/")
MODEL = os.environ.get("MODEL", "gemma4:e4b")
RUNS = int(os.environ.get("RUNS", "8"))
TIMEOUT_S = int(os.environ.get("TIMEOUT_S", "300"))

PROMPT = "Show how far the kitchen and basement temperatures deviate from their average over the last day"

# The exact synthetic error the integration feeds to repair when attempt 1's
# answer_text carries no matchable band/verdict label (answer_grounding.py:560).
GROUNDING_VERDICT_ABSENT = {
    "code": "grounding_verdict_absent",
    "message": "no band label found in answer_text (word-boundary search)",
    "details": {
        "labels": ["Significant", "Moderate", "Minor"],
        "answer_text_snippet": "Over the last day, the average absolute deviation ...",
    },
}


def build_request() -> dict:
    k = _irregular_series(
        "kitchen", "sensor.kitchen_ecobee_temperature", "Kitchen Temperature",
        71, 4, hours=24, step_s=420, jitter_s=90, phase_s=0,
    )
    b = _irregular_series(
        "basement", "sensor.basement_temperature", "Basement Temperature",
        64, 2, hours=24, step_s=660, jitter_s=150, phase_s=180,
    )
    two = [
        _series_spec("kitchen", "Kitchen Temperature", "sensor.kitchen_ecobee_temperature"),
        _series_spec("basement", "Basement Temperature", "sensor.basement_temperature", role="secondary"),
    ]
    return _request(
        "Show how far the kitchen and basement temperatures deviate from their average",
        two, [k, b],
    )


def _plt_assigned_in_function(code: str) -> bool:
    """Heuristic: does render_chart's body assign plt (import or =), which would
    shadow a module-level plt and risk UnboundLocalError?"""
    body = code.split("def render_chart", 1)[-1]
    return bool(
        re.search(r"^\s+import\s+matplotlib\.pyplot\s+as\s+plt", body, re.MULTILINE)
        or re.search(r"^\s+plt\s*=", body, re.MULTILINE)
    )


def main() -> int:
    worker_dir = str(REPO / "worker")
    existing = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = worker_dir + (os.pathsep + existing if existing else "")

    client = mp.OllamaCompatiblePlannerClient(
        endpoint_url=OLLAMA_URL, planner_model=MODEL, timeout_seconds=TIMEOUT_S
    )
    request = build_request()

    reproduced = 0
    shadow_seen = 0
    for run_n in range(1, RUNS + 1):
        gen = client.generate_chart_code(request, user_request=PROMPT)
        if not gen.get("accepted"):
            print(f"[run {run_n}] generation not accepted: {gen.get('code')}")
            continue
        code = gen["python_code"]

        repair = client.repair_chart_code(
            code, GROUNDING_VERDICT_ABSENT, request, user_request=PROMPT
        )
        if not repair.get("accepted"):
            print(f"[run {run_n}] repair not accepted: {repair.get('code')}")
            continue
        repaired = repair["python_code"]
        shadow = _plt_assigned_in_function(repaired)
        shadow_seen += int(shadow)

        execution = execute(repaired, request)
        ok = execution.get("ok")
        err = execution.get("error") or ""
        hit = (not ok) and "UnboundLocalError" in err and "plt" in err
        print(f"[run {run_n}] repair ok={ok} plt_shadow_in_fn={shadow} error={err[:110]}")
        if hit:
            reproduced += 1
            out = Path(f"/tmp/e2e18_repair_plt_run{run_n}.py")
            out.write_text(repaired)
            print("\n=== REPRODUCED — full traceback ===")
            print(execution.get("traceback"))
            print(f"=== repaired code -> {out} ===\n")

    print(f"\nreproduced UnboundLocalError('plt'): {reproduced}/{RUNS}; "
          f"repairs that shadowed plt inside render_chart: {shadow_seen}/{RUNS}")
    return 0 if reproduced else 1


if __name__ == "__main__":
    raise SystemExit(main())
