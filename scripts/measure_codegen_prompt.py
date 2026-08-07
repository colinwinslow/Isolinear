#!/usr/bin/env python3
"""Measure the REAL codegen prompt budget, field by field, against _CODEGEN_NUM_CTX.

Motivation: the 2026-07-31 e2e run produced 7 `unsafe_code` fallbacks whose
generated code was mock-data boilerplate (np.random.seed(42), 2023 date_range),
i.e. the model lost the contract. Truncation is one explanation but was never
measured. `history_series[].points` IS compressed (12-point preview), so the
question is what ELSE occupies the window — notably `derived_intervals`, which
`_codegen_request_view` deep-copies whole (model_provider.py:530).

This builds the exact prompt payload `_codegen_payload` / `_codegen_repair_payload`
send, from REAL recorder history pulled over the HA REST API, and reports a
per-field byte + token breakdown. No model call, no GPU — safe to run while the
e2e harness is mid-flight.

Token counts are estimated at 4 chars/token unless a real tokenizer is available;
the point is the RATIO to the 8192 window, not a byte-exact count.

Env:
  HA_TOKEN   (required)
  HA_URL     (default http://10.0.1.200:8123)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from custom_components.isolinear import model_provider as mp  # noqa: E402
from custom_components.isolinear import render_dispatch as rd  # noqa: E402

HA_URL = os.environ.get("HA_URL", "http://10.0.1.200:8123").rstrip("/")
TOKEN = os.environ.get("HA_TOKEN", "")
NUM_CTX = mp._CODEGEN_NUM_CTX

# The failing cases from the 2026-07-31 run, plus a passing control.
CASES = [
    ("e2e-13 (2 numeric, 2d) FAILED", ["sensor.kitchen_ecobee_temperature", "sensor.basement_temperature"], 2),
    ("e2e-14 (2 numeric mixed unit, 2d) FAILED", ["sensor.kitchen_ecobee_temperature", "sensor.kitchen_ecobee_humidity"], 2),
    ("e2e-10 (numeric + state overlay, 1d) FAILED", ["sensor.kitchen_ecobee_temperature", "climate.kitchen_ecobee"], 1),
    ("e2e-04 (numeric + state overlay, 5d) FAILED", ["sensor.kitchen_ecobee_temperature", "sensor.basement_temperature", "climate.kitchen_ecobee"], 5),
    ("e2e-01 (1 numeric, 1d) PASSED [control]", ["sensor.kitchen_ecobee_temperature"], 1),
]


def ha_history(entity_id: str, days: int) -> list[dict]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    # HA rejects an unencoded "+00:00" offset in the path/query — use Z form.
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    url = (
        f"{HA_URL}/api/history/period/{start.strftime(fmt)}"
        f"?filter_entity_id={entity_id}"
        f"&end_time={urllib.parse.quote(end.strftime(fmt))}"
    )
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    return payload[0] if payload else []


def to_series(entity_id: str, rows: list[dict]) -> dict:
    """Normalize HA history rows into the integration's history_series shape."""
    points = []
    numeric = True
    for row in rows:
        state = row.get("state")
        ts = row.get("last_changed") or row.get("last_updated")
        if not ts:
            continue
        epoch = int(datetime.fromisoformat(ts).timestamp() * 1000)
        point = {"ts": ts, "ts_epoch_ms": epoch, "raw_state": state}
        try:
            point["value"] = float(state)
        except (TypeError, ValueError):
            numeric = False
        points.append(point)
    unit = "°F" if "temperature" in entity_id else ("%" if "humidity" in entity_id else None)
    return {
        "entity_id": entity_id,
        "kind": "numeric" if numeric else "state",
        "unit": unit,
        "label": entity_id.split(".")[-1].replace("_", " ").title(),
        "points": points,
    }


def est_tokens(text: str) -> int:
    return round(len(text) / 4)


OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.0.1.39:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")


def exact_prompt_tokens(payload: dict, num_ctx: int) -> tuple[int, bool] | None:
    """Return (prompt_eval_count, truncated) from a real 1-token generation.

    This is the ONLY honest way to answer "does the repair prompt fit in 8192?" —
    a chars/token estimate is off by 30%+ on dense JSON, which is exactly the
    margin that decides it. `num_predict: 1` makes the call cheap; we only want
    the prompt-side count.

    Ollama does not error on an over-long prompt: it silently drops the leading
    tokens and reports `prompt_eval_count` pinned at exactly num_ctx. So
    `count >= num_ctx` IS the truncation signal (same logic as _context_overflow).
    """
    body = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": mp._CODEGEN_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, separators=(",", ":"))},
        ],
        "stream": False,
        "options": {"temperature": 0, "num_ctx": num_ctx, "num_predict": 1},
    }
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            out = json.load(resp)
    except Exception as exc:  # noqa: BLE001
        print(f"      (live probe failed: {exc})")
        return None
    count = out.get("prompt_eval_count")
    if not isinstance(count, int):
        return None
    return count, count >= num_ctx


def field_report(payload: dict, label: str, num_ctx: int) -> None:
    whole = json.dumps(payload, separators=(",", ":"))
    total = est_tokens(whole) + est_tokens(mp._CODEGEN_SYSTEM_PROMPT)
    pct = 100.0 * total / num_ctx
    flag = "  <<< OVER" if total >= num_ctx else ("  <<< TIGHT" if pct > 75 else "")
    print(f"\n  {label}")
    print(f"    {'TOTAL':<22} {len(whole):>9,} ch  ~{total:>6,} tok  {pct:5.1f}% of {num_ctx}{flag}")
    if os.environ.get("LIVE_TOKENS") == "1":
        probed = exact_prompt_tokens(payload, num_ctx)
        if probed:
            exact, truncated = probed
            ratio = len(whole) / exact if exact else 0
            verdict = "TRUNCATED — prompt exceeds the window" if truncated else "fits"
            print(f"    {'EXACT (real tokenizer)':<22} {'':>9}     {exact:>7,} tok  "
                  f"{100.0*exact/num_ctx:5.1f}% of {num_ctx}   {ratio:.2f} ch/tok   <<< {verdict}")
    rows = []
    for key, value in payload.items():
        blob = json.dumps(value, separators=(",", ":")) if not isinstance(value, str) else value
        rows.append((key, len(blob), est_tokens(blob)))
    # codegen_request is the interesting one — break it out
    for key, chars, toks in sorted(rows, key=lambda r: -r[1]):
        print(f"      {key:<20} {chars:>9,} ch  ~{toks:>6,} tok  {100.0*toks/num_ctx:5.1f}%")
        if key == "codegen_request":
            for sub, subval in payload[key].items():
                blob = json.dumps(subval, separators=(",", ":"))
                print(f"        └ {sub:<16} {len(blob):>9,} ch  ~{est_tokens(blob):>6,} tok")


def main() -> int:
    if not TOKEN:
        print("Set HA_TOKEN.", file=sys.stderr)
        return 1
    print(f"_CODEGEN_NUM_CTX = {NUM_CTX}")
    print(f"static floor: system={len(mp._CODEGEN_SYSTEM_PROMPT)}ch  "
          f"rules={sum(len(r) for r in mp._CODEGEN_PROMPT_RULES)}ch "
          f"(~{est_tokens(''.join(mp._CODEGEN_PROMPT_RULES)):,} tok, "
          f"{100.0*est_tokens(''.join(mp._CODEGEN_PROMPT_RULES))/NUM_CTX:.0f}% of window)")

    for label, entities, days in CASES:
        series = []
        for ent in entities:
            try:
                series.append(to_series(ent, ha_history(ent, days)))
            except Exception as exc:  # noqa: BLE001
                print(f"\n{label}: history fetch failed for {ent}: {exc}")
        if not series:
            continue
        chart_spec = {
            "chart_type": "time_series",
            "title": "Measured",
            "series": [{"entity_id": s["entity_id"], "label": s["label"]} for s in series],
        }
        request = {
            "chart_spec": chart_spec,
            "history_series": series,
            "derived_intervals": rd._compute_derived_intervals(chart_spec, series),
            "output": {"path": "/out/chart.png", "format": "png"},
        }
        pts = ", ".join(f"{s['entity_id'].split('.')[-1]}={len(s['points'])}" for s in series)
        di = request["derived_intervals"]
        print(f"\n{'='*78}\n{label}\n  raw points: {pts}   derived_intervals: {len(di)}")

        gen = {
            "task": "Fulfill user_request: ...",
            "user_request": "measured",
            "rules": mp._CODEGEN_PROMPT_RULES,
            "codegen_request": mp._codegen_request_view(request),
        }
        field_report(gen, "GENERATION prompt", NUM_CTX)

        # Repair carries previous_code too — use a realistic ~120-line script.
        fake_code = "\n".join(
            ["import matplotlib", "import pandas as pd", "def render_chart(data, output_path):"]
            + [f"    x{i} = data['history_series'][0]['points'][{i}]['value']  # line {i}" for i in range(110)]
        )
        violations = [
            {"code": "top_level_statement", "line": 84, "message": "Generated code may contain only imports and function definitions at top level.", "source_line": "time_index = pd.date_range(start='2023-10-01', periods=100, freq='H')"}
        ] * 8
        for cls_label, err in (
            ("static/unsafe_code", {"code": "unsafe_code", "message": "static gate", "traceback": None, "violations": violations}),
            ("runtime_error", {"code": "runtime_error", "message": "boom", "traceback": "Traceback (most recent call last):\n  ...\nTypeError: list indices must be integers or slices, not tuple"}),
            ("grounding", {"code": "grounding_verdict_unbacked", "message": "verdict not backed by a claim", "traceback": None}),
        ):
            rep = dict(gen)
            rep["rules"] = mp._repair_prompt_rules(err, request)
            rep["previous_code"] = fake_code
            rep["sandbox_error"] = err
            field_report(rep, f"REPAIR prompt, PRUNED rules [{cls_label}]", NUM_CTX)

        # The pre-fix shape, kept for the before/after delta.
        rep_full = dict(gen)
        rep_full["previous_code"] = fake_code
        rep_full["sandbox_error"] = {"code": "unsafe_code", "violations": violations}
        field_report(rep_full, "REPAIR prompt, FULL rules (pre-fix shape)", NUM_CTX)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
