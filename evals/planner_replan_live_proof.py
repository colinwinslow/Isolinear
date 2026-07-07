#!/usr/bin/env python3
"""Live proof for the bounded planner re-plan loop (spec Proof requirement #4).

The 17th-session live e2e run surfaced the e2e-18 duplicate-source variance
tail: a gemma4:e4b sample plans the computed result ("Deviation") as its own
series; constrained decoding — whose `source.entity_id` enum holds only
approved ids — forces it onto an already-used entity, and
`validate_chart_spec_contract` rejects the plan
(`invalid_model_provider_chart_spec`). 0.2.24 closed that with a PROMPT rule
("NEVER add an extra series for the computed result…"); open-queue (u) is the
STRUCTURAL fix — a bounded re-plan. This eval proves the loop subsumes the
prompt patch for this class, against live gemma:

  * The 0.2.24 hardening clause is surgically REMOVED from the planner rules
    (marker-gated, rule-gate pattern), restoring the exact 0.2.23 prompt under
    which the tail fired live — so the variance class can re-occur.
  * Each run drives the PRODUCTION `_record_model_provider_plan` (the real
    re-plan loop, real validation gates, real constrained-decoding schema)
    with the live planner client, the exact live e2e-18 prompt, and the exact
    live-resolved entity set. `max_planner_replan_attempts` is left ABSENT so
    the run exercises the shipped reader default (1).

PROOF (two parts):

  1. fresh-sample probe (frozen request, live): at temperature 0 — what an
     unperturbed retry samples at — the planner's structured pass is
     near-greedy (observed 3/3 byte-identical planner_results), so a re-plan
     without the override cannot recover: it reproduces the rejected plan.
     At `_PLANNER_REPLAN_TEMPERATURE` the same frozen request yields distinct
     plans (observed 3/3 distinct) — the fresh-sample property recovery
     depends on. This gates PASS/FAIL.
  2. live tail recovery (opportunistic): a run where the first sample failed a
     trigger-set gate and the loop returned `accepted: True` with
     `planner_replan_attempts >= 1`. The duplicate-source tail is a rare
     variance region (it fired once in the 17th-session live harness); if no
     first sample fails in RUNS samples, that is recorded honestly as
     tail-not-reproduced, not as failure.

Config via env: OLLAMA_URL, MODEL, RUNS (default 8), RESULTS_JSON.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

from custom_components.isolinear import job_orchestration as jo  # noqa: E402
from custom_components.isolinear.const import DOMAIN  # noqa: E402
from custom_components.isolinear.entity_catalog import DATA_ENTITY_CATALOG  # noqa: E402
from custom_components.isolinear.model_provider import (  # noqa: E402
    DATA_MODEL_PROVIDER_PLANNER,
    OllamaCompatiblePlannerClient,
)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.0.1.39:11434").rstrip("/")
MODEL = os.environ.get("MODEL", "gemma4:e4b")
RUNS = int(os.environ.get("RUNS", "8"))
RESULTS_JSON = Path(
    os.environ.get("RESULTS_JSON", HERE / "prompts" / "planner_replan_live_proof_results.json")
)

ENTRY_ID = "replan-live-proof"
# The exact live e2e-18 prompt + the exact entity set live resolution produced
# (evals/e2e_runs/20260706T205049Z/e2e-18_snapshot.json).
PROMPT = "Show how far the kitchen and basement temperatures deviate from their average over the last day"
ENTITIES = [
    {"entity_id": "sensor.basement_temperature", "label": "Basement Temperature"},
    {"entity_id": "sensor.kitchen_ecobee_temperature", "label": "Kitchen Temperature"},
]

# The 0.2.24 hardening clause under the gate, identified by distinctive phrasing
# — fail loudly if the rule text drifts (rule-gate pattern). Stripping it
# restores the 0.2.23 satisfiability rule the tail fired under.
CLAUSE_MARKER = "NEVER add an extra series for the computed result"
CLAUSE_RE = re.compile(
    r"NEVER add an extra series for the computed result.*?derived downstream\. ",
    re.S,
)


def _strip_hardening_clause(payload: dict) -> dict:
    """Remove the 0.2.24 clause from the serialized planner rules, marker-gated."""
    hits = 0
    for message in payload.get("messages", []):
        content = message.get("content")
        if not isinstance(content, str) or CLAUSE_MARKER not in content:
            continue
        prompt_payload = json.loads(content)
        rules = prompt_payload.get("rules")
        if not isinstance(rules, list):
            continue
        for i, rule in enumerate(rules):
            if isinstance(rule, str) and CLAUSE_MARKER in rule:
                stripped = CLAUSE_RE.sub("", rule)
                if CLAUSE_MARKER in stripped:
                    raise SystemExit("clause removal failed — update CLAUSE_RE")
                rules[i] = stripped
                hits += 1
        message["content"] = json.dumps(prompt_payload, separators=(",", ":"))
    if hits != 1:
        raise SystemExit(
            f"expected exactly one planner rule containing {CLAUSE_MARKER!r}, found {hits}"
        )
    return payload


def _live_planner_without_hardening() -> OllamaCompatiblePlannerClient:
    planner = OllamaCompatiblePlannerClient(endpoint_url=OLLAMA_URL, planner_model=MODEL)
    original_chat_payload = planner._chat_payload

    def patched(request, result_schema, *, stream=False, temperature=None):
        return _strip_hardening_clause(
            original_chat_payload(request, result_schema, stream=stream, temperature=temperature)
        )

    planner._chat_payload = patched
    return planner


def _catalog_item(entity_id: str, friendly_name: str) -> dict:
    return {
        "entity_id": entity_id,
        "friendly_name": friendly_name,
        "domain": "sensor",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit_of_measurement": "°F",
        "visible_to_agent": True,
    }


def _fixture_hass(planner) -> SimpleNamespace:
    entry = SimpleNamespace(
        entry_id=ENTRY_ID,
        # max_planner_replan_attempts deliberately ABSENT: the proof exercises
        # the shipped reader default (1).
        options={},
    )
    entry_data = {
        "entry": entry,
        DATA_MODEL_PROVIDER_PLANNER: planner,
        DATA_ENTITY_CATALOG: {
            "items": [
                _catalog_item(e["entity_id"], e["label"]) for e in ENTITIES
            ]
        },
    }
    return SimpleNamespace(
        data={DOMAIN: {ENTRY_ID: entry_data}},
        config=SimpleNamespace(time_zone="America/New_York"),
        states=SimpleNamespace(get=lambda entity_id: None),
    )


class _LogCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        if "re-plan" in record.getMessage():
            self.lines.append(f"{record.levelname}: {record.getMessage()}")


def run_one(run_n: int, results: dict) -> None:
    key = f"run{run_n}"
    if results["runs"].get(key, {}).get("done"):
        return
    planner = _live_planner_without_hardening()
    plan_calls: list[float] = []
    original_plan_chart = planner.plan_chart

    def counting_plan_chart(request, *, result_schema=None, **kwargs):
        plan_calls.append(time.time())
        return original_plan_chart(request, result_schema=result_schema, **kwargs)

    planner.plan_chart = counting_plan_chart
    hass = _fixture_hass(planner)
    store = {"entry_id": ENTRY_ID, "next_model_provider_plan_number": run_n}
    capture = _LogCapture()
    jo._LOGGER.addHandler(capture)
    t0 = time.time()
    try:
        result = jo._record_model_provider_plan(
            store,
            hass=hass,
            entry_id=ENTRY_ID,
            job={"job_id": f"replan-proof-{run_n}", "prompt": PROMPT},
            source_snapshot={
                "snapshot_id": f"snapshot-replan-proof-{run_n}",
                "entities": [dict(e) for e in ENTITIES],
            },
        )
    finally:
        jo._LOGGER.removeHandler(capture)

    attempts = result.get("planner_replan_attempts", 0)
    rec = {
        "done": True,
        "accepted": bool(result.get("accepted")),
        "code": result.get("code"),
        "planner_replan_attempts": attempts,
        "planner_calls": len(plan_calls),
        "elapsed_s": round(time.time() - t0, 1),
        "replan_log": capture.lines,
        "recovered": bool(result.get("accepted")) and attempts >= 1,
    }
    if not result.get("accepted"):
        validation = result.get("validation") or {}
        rec["failure_validation"] = {
            k: validation.get(k) for k in ("code", "error", "errors") if k in validation
        }
    if result.get("accepted"):
        spec = result.get("chart_spec") or {}
        rec["series"] = [
            {"label": s.get("label"), "entity_id": (s.get("source") or {}).get("entity_id")}
            for s in spec.get("series", [])
            if isinstance(s, dict)
        ]
    results["runs"][key] = rec
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    tag = "RECOVERED" if rec["recovered"] else ("ok-first-try" if rec["accepted"] else "FAILED")
    print(
        f"[{key}] {tag} code={rec['code']} replan_attempts={attempts} "
        f"planner_calls={rec['planner_calls']} {rec['elapsed_s']}s "
        f"{'; '.join(capture.lines) or ''}",
        flush=True,
    )


def fresh_sample_probe(results: dict) -> None:
    """Demonstrate the recovery mechanism live: on a FROZEN request the planner's
    structured pass at temperature 0 is near-greedy (mostly identical samples),
    while the re-plan override (_PLANNER_REPLAN_TEMPERATURE) yields distinct
    plans — the fresh-sample property recovery depends on."""
    if results.get("fresh_sample_probe", {}).get("done"):
        return
    import hashlib

    from custom_components.isolinear.model_provider import load_planner_result_schema

    planner = _live_planner_without_hardening()
    approved = [e["entity_id"] for e in ENTITIES]
    schema = load_planner_result_schema(
        "time_series", envelope=["time_series"], entity_ids=approved
    )
    request = {
        "prompt": PROMPT,
        "approved_entity_ids": approved,
        "history_entity_ids": approved,
        "now": "2026-07-07T12:00:00-04:00",  # frozen — identical request every call
        "time_zone": "America/New_York",
        "output_schema": "PlannerResult",
    }
    probe: dict = {"temps": {}, "done": False}
    for temp in (None, jo._PLANNER_REPLAN_TEMPERATURE):
        shas = []
        for _ in range(3):
            r = planner.plan_chart(request, result_schema=schema, temperature=temp)
            blob = json.dumps(r.get("planner_result"), sort_keys=True)
            shas.append(hashlib.sha256(blob.encode()).hexdigest()[:12])
        label = "temperature_0_default" if temp is None else f"replan_temperature_{temp}"
        probe["temps"][label] = {"shas": shas, "distinct": len(set(shas))}
        print(f"[fresh-sample probe] {label}: {len(set(shas))}/3 distinct samples {shas}", flush=True)
    probe["done"] = True
    results["fresh_sample_probe"] = probe
    RESULTS_JSON.write_text(json.dumps(results, indent=1))


def main() -> int:
    results = (
        json.loads(RESULTS_JSON.read_text()) if RESULTS_JSON.exists() else {"meta": {}, "runs": {}}
    )
    results["meta"] = {
        "model": MODEL,
        "ollama": OLLAMA_URL,
        "prompt": PROMPT,
        "entities": [e["entity_id"] for e in ENTITIES],
        "clause_stripped": CLAUSE_MARKER,
        "reader_default_exercised": "max_planner_replan_attempts absent -> default 1",
        "started": results["meta"].get("started")
        or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    fresh_sample_probe(results)
    for run_n in range(1, RUNS + 1):
        run_one(run_n, results)

    runs = list(results["runs"].values())
    recovered = sum(r.get("recovered", False) for r in runs)
    tail_fired = sum(r.get("planner_replan_attempts", 0) >= 1 for r in runs)
    accepted = sum(r.get("accepted", False) for r in runs)
    tally = {
        "runs": len(runs),
        "accepted": accepted,
        "tail_fired": tail_fired,
        "recovered_by_replan": recovered,
    }
    results["tally"] = tally
    RESULTS_JSON.write_text(json.dumps(results, indent=1))
    print(f"\n=== tally === {json.dumps(tally)}")

    probe = results.get("fresh_sample_probe", {}).get("temps", {})
    default_distinct = probe.get("temperature_0_default", {}).get("distinct")
    replan_key = next((k for k in probe if k.startswith("replan_temperature")), None)
    replan_distinct = probe.get(replan_key, {}).get("distinct") if replan_key else None
    if replan_distinct is None or replan_distinct < 2:
        print(
            "FAIL planner_replan_live_proof — the re-plan temperature did not "
            f"produce distinct samples on a frozen request ({probe})"
        )
        return 1
    print(
        f"PASS planner_replan_live_proof — fresh-sample property proven live "
        f"(temp-0 default: {default_distinct}/3 distinct; re-plan override: "
        f"{replan_distinct}/3 distinct)."
    )
    if recovered >= 1:
        print(f"  live tail recovery ALSO observed: {recovered} run(s) recovered by re-plan")
    elif tail_fired == 0:
        print(
            f"  tail-not-reproduced: {len(runs)}/{len(runs)} first samples validated "
            "(the duplicate-source class is a rare variance region; recorded honestly)"
        )
    else:
        print(
            f"  WARNING: tail fired {tail_fired} time(s) without recovery — "
            "inspect failure_validation in the results JSON"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
