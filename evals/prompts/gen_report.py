#!/usr/bin/env python3
"""Generate the codegen reliability report (markdown gallery) from
reliability_results.json + the retrieved renders/ PNGs.

Usage: python3 evals/prompts/gen_report.py
Writes evals/prompts/reliability_report.md.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "reliability_results.json"
CORPUS = HERE / "benchmark_prompts.json"
RENDERS = HERE / "renders"
OUT = HERE / "reliability_report.md"


def short_err(rec: dict) -> str:
    fe = rec.get("final_error") or {}
    code = fe.get("code") or "—"
    detail = ""
    tb = (fe.get("traceback") or "").strip().splitlines()
    st = (fe.get("stderr") or "").strip().splitlines()
    if tb:
        detail = tb[-1][:120]
    elif st:
        detail = st[-1][:120]
    return f"`{code}`" + (f" — {detail}" if detail else "")


def model_cell(rec: dict) -> str:
    if rec is None:
        return "_(not run)_"
    if rec.get("accepted"):
        img = rec.get("image_id")
        rel = f"renders/{img}"
        exists = (RENDERS / img).exists() if img else False
        rep = f" (after {rec['repairs']} repair{'s' if rec['repairs'] != 1 else ''})" if rec.get("repairs") else ""
        loc = ""
        if rec.get("attempts"):
            loc = f" · {rec['attempts'][-1].get('loc','?')} loc"
        if exists:
            return f"**✓ accepted**{rep}{loc}<br>![{img}]({rel})"
        return f"**✓ accepted**{rep}{loc}<br>_(image {img} not retrieved)_"
    return f"**✗ rejected** (after {rec.get('repairs',0)} repair attempts)<br>{short_err(rec)}"


def main() -> int:
    results = json.loads(RESULTS.read_text())
    corpus = json.loads(CORPUS.read_text())
    models = results.get("meta", {}).get("models", [])
    cases = results.get("cases", {})
    tally = results.get("tally", {})

    lines: list[str] = []
    lines.append("# Codegen reliability report — ADR-0029 packet 5\n")
    lines.append("Each real benchmark prompt was turned into a representative ChartSpec + synthetic")
    lines.append("history, then each model generated matplotlib code that was rendered through the")
    lines.append("worker sandbox (with an integration-orchestrated repair loop on retryable failures).")
    lines.append(f"Models: {', '.join(f'`{m}`' for m in models)}. "
                 f"Worker: `{results.get('meta',{}).get('worker','')}` · "
                 f"max repairs: {results.get('meta',{}).get('max_repairs')}.\n")

    # tally
    lines.append("## Accept / repair / reject\n")
    lines.append("| Model | Accepted | Needed repair | Rejected | Total chartable |")
    lines.append("|---|---|---|---|---|")
    for m in models:
        t = tally.get(m, {})
        lines.append(f"| `{m}` | {t.get('accept',0)} | {t.get('repaired',0)} | "
                     f"{t.get('reject',0)} | {t.get('total',0)} |")
    lines.append("")
    lines.append("> \"Needed repair\" = accepted only after ≥1 repair round. Rejections split into")
    lines.append("> `unsafe_code` (static safety), `runtime_error` (incl. `MemoryError` under the")
    lines.append("> sandbox memory cap), and `validation_failed` (bad ChartSpec — should be 0).\n")

    # gallery, in corpus order
    lines.append("## Gallery\n")
    for p in corpus["prompts"]:
        pid = p["id"]
        e = cases.get(pid, {})
        fam = (p.get("expect") or {}).get("render_family", "—")
        lines.append(f"### `{pid}` — {p['prompt']}\n")
        lines.append(f"*category:* `{p['category']}` · *expected family:* `{fam}`"
                     + (f" · *note:* {p['notes']}" if p.get("notes") else "") + "\n")
        if not e.get("chartable", False):
            beh = (p.get("expect") or {}).get("behavior") or fam
            lines.append(f"_Not a codegen case — expected planner behavior: **{beh}** "
                         f"(clarify/refuse/unsupported), so no chart is generated._\n")
            continue
        lines.append("| " + " | ".join(f"`{m}`" for m in models) + " |")
        lines.append("|" + "---|" * len(models))
        lines.append("| " + " | ".join(model_cell(e.get("models", {}).get(m)) for m in models) + " |")
        lines.append("")

    OUT.write_text("\n".join(lines))
    print(f"wrote {OUT} ({len(corpus['prompts'])} prompts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
