#!/usr/bin/env python3
"""Repro for the live 0.2.35 UnboundLocalError('plt') on e2e-18 (packet H follow-up).

The 25th session's new per-attempt WARNING logging (0.2.35) caught, for the
first time, an actual sandbox runtime_error's message on the deviation prompt
("Show how far the kitchen and basement temperatures deviate from their
average over the last day"): attempt 2/4 failed with
``UnboundLocalError: cannot access local variable 'plt' where it is not
associated with a value``. Only the bare exception message was logged (no
source line / traceback), so the actual generated code is unknown.

Unlike the e2e-11 sandbox-execution cascade ([[isolinear-e2e11-sandbox-cascade]]),
an UnboundLocalError on a name is a pure Python *scoping* bug in the generated
code itself (classic pattern: a name is assigned somewhere in a function body,
which makes Python treat every reference to it in that function as local, so a
reference before the assignment executes on some code path raises this) — not
an artifact of the worker sandbox's `-I` / import-allowlist / RLIMIT
restrictions. So the lightweight local harness (subprocess exec, no sandbox
restrictions) should reproduce it identically, since `generate_chart_code`
calls Ollama at temperature 0 (near-deterministic per exact request).

Usage: OLLAMA_URL / MODEL / RUNS via env, same as the other repro_e2e*.py
scripts. Prints the full traceback the first time it reproduces and dumps the
offending generated code to /tmp/e2e18_unboundlocal_repro.py.
"""
from __future__ import annotations

import os
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
# The production client defaults to a 90s timeout; e2e-18's complex analysis
# prompt + gemma4:e4b's thinking pass regularly exceeds that (which is itself
# one of the live model_provider_connection_error fallback causes under GPU
# contention). Give the repro headroom so generations actually complete.
TIMEOUT_S = int(os.environ.get("TIMEOUT_S", "300"))

PROMPT = "Show how far the kitchen and basement temperatures deviate from their average over the last day"


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


def main() -> int:
    # The model now follows the ADR-0036 rule and imports isolinear_analysis
    # (the in-sandbox helper). The local exec harness (execute() runs a plain
    # subprocess, inheriting this process's env) needs the helper on its path,
    # exactly as the worker image bakes it into system site-packages.
    worker_dir = str(REPO / "worker")
    existing = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = worker_dir + (os.pathsep + existing if existing else "")

    client = mp.OllamaCompatiblePlannerClient(
        endpoint_url=OLLAMA_URL, planner_model=MODEL, timeout_seconds=TIMEOUT_S
    )
    request = build_request()

    for run_n in range(1, RUNS + 1):
        gen = client.generate_chart_code(request, user_request=PROMPT)
        if not gen.get("accepted"):
            print(f"[run {run_n}] generation not accepted: {gen.get('code')}")
            continue
        code = gen["python_code"]
        execution = execute(code, request)
        ok = execution.get("ok")
        err = execution.get("error") or ""
        print(f"[run {run_n}] ok={ok} error={err[:120]}")
        if not ok and "UnboundLocalError" in err and "plt" in err:
            print("\n=== REPRODUCED — full traceback ===")
            print(execution.get("traceback"))
            out = Path("/tmp/e2e18_unboundlocal_repro.py")
            out.write_text(code)
            print(f"\n=== offending generated code written to {out} ===\n")
            print(code)
            return 0
    print("\nNot reproduced in", RUNS, "runs.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
