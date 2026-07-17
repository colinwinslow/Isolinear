#!/usr/bin/env python3
"""Open-queue (p) — live end-to-end pipeline harness, Claude-judged.

Drives the REAL pipeline the card drives — `isolinear/v1/job/start` +
`isolinear/v1/job/snapshot` polling over the Home Assistant WebSocket API —
against the live HA instance, worker, and Ollama, for the fixed prompt set in
``evals/prompts/e2e_prompts.json``. No synthetic requests anywhere: the
planner plans, history is fetched through the allowlist path, codegen runs in
the CT106 sandbox (the worker's home since the homelab ct-workload-tier-split;
CT103 is GPU-only now), and the served artifact is what the card would display.

For each prompt it captures the REAL output into a timestamped run directory:
the served PNG (fetched from ``chart.image_url``) plus the structured
metadata (``render_path``, ``render_fallback_reason``, ``answer_text``,
``answer_verification``, failure codes, timing, the full final snapshot).

There are deliberately NO programmatic pass/fail assertions (Colin,
2026-07-05): recent regressions (0.2.18 empty charts, 0.2.19/0.2.20 wrong or
missing units, the 0.2.21 overlay-as-line) rendered "successfully" and were
invisible to every static check. Claude reads the PNGs + manifest after the
run and judges each case by looking — the judgments go into REPORT.md.

Run outputs land in ``evals/e2e_runs/<UTC-timestamp>/`` (gitignored — real
home data).

Config via env:
  HA_URL     (default http://10.0.1.200:8123)
  HA_TOKEN   (required; never printed)
  PROMPTS    (default evals/prompts/e2e_prompts.json)
  OUT_ROOT   (default evals/e2e_runs)
  ONLY_IDS   (comma list of prompt ids; default all)
  POLL_S     (default 2.0 — the card polls at 1s)
  TIMEOUT_S  (default 360 per prompt — planning + codegen + repairs is minutes)
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import websockets

HERE = Path(__file__).resolve().parent
HA_URL = os.environ.get("HA_URL", "http://10.0.1.200:8123").rstrip("/")
HA_WS_URL = HA_URL.replace("http", "ws", 1) + "/api/websocket"
HA_TOKEN = os.environ.get("HA_TOKEN", "")
PROMPTS = Path(os.environ.get("PROMPTS", HERE / "prompts" / "e2e_prompts.json"))
OUT_ROOT = Path(os.environ.get("OUT_ROOT", HERE / "e2e_runs"))
POLL_S = float(os.environ.get("POLL_S", "2.0"))
TIMEOUT_S = float(os.environ.get("TIMEOUT_S", "360"))

WS_VERSION = 1
TERMINAL = {"complete", "failed"}


async def _open_authed_ws():
    ws = await websockets.connect(HA_WS_URL, max_size=None)
    await ws.recv()  # auth_required
    await ws.send(json.dumps({"type": "auth", "access_token": HA_TOKEN}))
    auth = json.loads(await ws.recv())
    if auth.get("type") != "auth_ok":
        raise SystemExit(f"HA auth failed: {auth.get('type')}")
    return ws


class HaWs:
    """Minimal authenticated HA WebSocket client with incrementing ids.

    Reconnects and retries once on a dropped socket: a long provider stall
    (GPU contention → a 280s+ snapshot poll) can make HA close the idle WS
    mid-run. The calls that actually get retried in practice are idempotent
    job/snapshot reads, so re-sending them on a fresh connection is safe. The
    generic wrapper also carries the (non-idempotent) job/start; a re-sent start
    would at worst launch one extra harmless read-only job — the harness uses
    whichever job_id comes back, and Isolinear never mutates HA (invariant #2) —
    so a reconnect never corrupts state. Keeps the 20-prompt run alive on a blip.
    """

    def __init__(self, ws):
        self.ws = ws
        self._id = 0

    async def _reconnect(self) -> None:
        try:
            await self.ws.close()
        except Exception:
            pass
        self.ws = await _open_authed_ws()

    async def call(self, message: dict) -> dict:
        self._id += 1
        message = {"id": self._id, **message}
        for attempt in (0, 1):
            try:
                await self.ws.send(json.dumps(message))
                while True:
                    reply = json.loads(await self.ws.recv())
                    if reply.get("id") == self._id and reply.get("type") == "result":
                        return reply
            except websockets.exceptions.ConnectionClosed:
                if attempt == 1:
                    raise
                await self._reconnect()


async def connect() -> HaWs:
    return HaWs(await _open_authed_ws())


async def isolinear_entry_id(client: HaWs) -> str:
    reply = await client.call({"type": "config_entries/get", "domain": "isolinear"})
    entries = reply.get("result") or []
    loaded = [e for e in entries if e.get("state") == "loaded"]
    if not loaded:
        raise SystemExit(f"no loaded isolinear config entry (found {len(entries)})")
    return loaded[0]["entry_id"]


async def live_card_version(client: HaWs) -> str | None:
    """Best-effort: read the Lovelace resource ?v= so the run records which
    integration version was actually live."""
    try:
        reply = await client.call({"type": "lovelace/resources"})
        for res in reply.get("result") or []:
            url = res.get("url") or ""
            if "isolinear" in url and "?v=" in url:
                return url.split("?v=")[-1]
    except Exception:
        pass
    return None


def fetch_png(image_url: str, dest: Path) -> int:
    req = urllib.request.Request(
        HA_URL + image_url, headers={"Authorization": f"Bearer {HA_TOKEN}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    dest.write_bytes(data)
    return len(data)


def manifest_row(pid: str, prompt: dict, snapshot: dict, elapsed: float,
                 outcome: str, png: str | None, png_bytes: int, phases: list[str],
                 reasoning_log: list[dict] | None = None) -> dict:
    chart = snapshot.get("chart") or {}
    failure = snapshot.get("failure") or {}
    clar = snapshot.get("clarification") or {}
    reasoning_log = reasoning_log or []
    return {
        "id": pid,
        "family": prompt.get("family"),
        "prompt": prompt["prompt"],
        "expect": prompt.get("expect"),
        "outcome": outcome,
        "status": snapshot.get("status"),
        "elapsed_s": round(elapsed, 1),
        "phases": phases,
        "render_path": chart.get("render_path"),
        "render_fallback_reason": chart.get("render_fallback_reason"),
        "title": chart.get("title"),
        "summary": chart.get("summary"),
        "answer_text": chart.get("answer_text"),
        "answer_verification": chart.get("answer_verification"),
        "failure_code": failure.get("failure_code") or failure.get("code"),
        "failure_stage": failure.get("failure_stage") or failure.get("stage"),
        "clarification_question": clar.get("question"),
        "clarification_options": [o.get("label") for o in (clar.get("options") or [])],
        "reasoning_stages": [e.get("stage") for e in reasoning_log],
        "reasoning_tail": reasoning_log[-1]["reasoning"] if reasoning_log else None,
        "warnings": snapshot.get("warnings") or [],
        "png": png,
        "png_bytes": png_bytes,
    }


async def run_prompt(client: HaWs, entry_id: str, prompt: dict, out_dir: Path) -> dict:
    pid = prompt["id"]
    t0 = time.time()
    phases: list[str] = []
    reply = await client.call({
        "type": "isolinear/v1/job/start", "version": WS_VERSION,
        "config_entry_id": entry_id, "prompt": prompt["prompt"]})
    if not reply.get("success"):
        err = reply.get("error") or {}
        snapshot = {"status": "failed", "failure": {"code": err.get("code"),
                                                    "message": err.get("message")}}
        (out_dir / f"{pid}_snapshot.json").write_text(json.dumps(snapshot, indent=1))
        return manifest_row(pid, prompt, snapshot, time.time() - t0,
                            "start_rejected", None, 0, phases)

    snapshot = reply["result"]
    job_id = snapshot.get("job_id")
    # Preserve the streamed selection/planning reasoning (ADR-0025) that the
    # polling loop would otherwise overwrite. A planner-stage failure surfaces a
    # generic card message (`model_provider_metadata_not_exposed_to_card`), so the
    # in-progress reasoning is the only reachable diagnostic for WHY the planner
    # clarified/declined (e.g. e2e-14: "kitchen humidity sensor required").
    reasoning_log: list[dict] = []

    def _capture_reasoning(snap: dict) -> None:
        prog = snap.get("progress") or {}
        reasoning = prog.get("reasoning")
        if reasoning and (not reasoning_log or reasoning_log[-1]["reasoning"] != reasoning):
            reasoning_log.append({
                "status": snap.get("status"),
                "stage": prog.get("stage"),
                "message": prog.get("message"),
                "reasoning": reasoning,
            })

    _capture_reasoning(snapshot)
    while True:
        status = snapshot.get("status")
        if not phases or phases[-1] != status:
            phases.append(status)
        if status in TERMINAL or status == "clarification_needed":
            break
        if time.time() - t0 > TIMEOUT_S:
            phases.append("harness_timeout")
            break
        await asyncio.sleep(POLL_S)
        poll = await client.call({
            "type": "isolinear/v1/job/snapshot", "version": WS_VERSION,
            "config_entry_id": entry_id, "job_id": job_id})
        if poll.get("success"):
            snapshot = poll["result"]
            _capture_reasoning(snapshot)

    elapsed = time.time() - t0
    (out_dir / f"{pid}_snapshot.json").write_text(json.dumps(snapshot, indent=1))
    if reasoning_log:
        (out_dir / f"{pid}_reasoning.txt").write_text(
            "\n\n".join(
                f"[{e['status']} / {e['stage']}] {e['message'] or ''}\n{e['reasoning']}"
                for e in reasoning_log
            )
        )

    outcome = snapshot.get("status") if phases[-1] != "harness_timeout" else "timeout"
    png_name, png_bytes = None, 0
    image_url = (snapshot.get("chart") or {}).get("image_url")
    if image_url:
        png_name = f"{pid}.png"
        try:
            png_bytes = fetch_png(image_url, out_dir / png_name)
        except Exception as exc:
            png_name = None
            outcome = f"{outcome}+png_fetch_failed:{type(exc).__name__}"
    return manifest_row(pid, prompt, snapshot, elapsed, outcome, png_name, png_bytes,
                        phases, reasoning_log)


def write_report(out_dir: Path, meta: dict, rows: list[dict]) -> None:
    lines = [
        "# Live e2e pipeline run — Claude-judged",
        "",
        f"- **Run:** {meta['started']}  |  HA {meta['ha_url']}  |  live card version: {meta.get('card_version') or 'unknown'}",
        f"- **Judging:** fill each Judgment line by LOOKING at the PNG + metadata"
        " (empty plot? wrong/missing unit? fallback? overlay drawn as a line? answer grounded?).",
        "",
        "| id | family | outcome | render_path | fallback_reason | elapsed | png |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['id']} | {r['family']} | {r['outcome']} | {r['render_path'] or '—'} "
            f"| {r['render_fallback_reason'] or '—'} | {r['elapsed_s']}s "
            f"| {r['png'] or '—'} |")
    lines.append("")
    for r in rows:
        lines += [
            f"## {r['id']} — {r['prompt']}",
            "",
            f"- expect: {r['expect']}",
            f"- outcome: **{r['outcome']}** (phases: {' → '.join(p or '?' for p in r['phases'])})",
            f"- render_path: {r['render_path']}  |  fallback: {r['render_fallback_reason']}",
            f"- answer_text: {r['answer_text'] or '—'}",
            f"- answer_verification: {r['answer_verification'] or '—'}",
            f"- failure: {r['failure_code'] or '—'} @ {r['failure_stage'] or '—'}",
            f"- clarification: {r['clarification_question'] or '—'}"
            + (f" (options: {', '.join(o for o in r['clarification_options'] if o)})"
               if r['clarification_options'] else ""),
            f"- reasoning (streamed, stages {r['reasoning_stages'] or '—'}): "
            f"{(r['reasoning_tail'] or '—')[:500]}"
            + (f"  →  full: {r['id']}_reasoning.txt" if r['reasoning_tail'] else ""),
            f"- image: {'![' + r['id'] + '](' + r['png'] + ')' if r['png'] else '(no image)'}",
            "",
            "**Judgment:** _pending_",
            "",
        ]
    (out_dir / "REPORT.md").write_text("\n".join(lines))


async def main() -> int:
    if not HA_TOKEN:
        print("Set HA_TOKEN to a Home Assistant long-lived access token.", file=sys.stderr)
        return 2
    corpus = json.loads(PROMPTS.read_text())
    prompts = corpus["prompts"]
    only = {s.strip() for s in os.environ.get("ONLY_IDS", "").split(",") if s.strip()}
    if only:
        prompts = [p for p in prompts if p["id"] in only]

    started = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out_dir = OUT_ROOT / started
    out_dir.mkdir(parents=True, exist_ok=True)

    client = await connect()
    entry_id = await isolinear_entry_id(client)
    card_version = await live_card_version(client)
    meta = {"started": started, "ha_url": HA_URL, "entry_id": entry_id,
            "card_version": card_version, "poll_s": POLL_S, "timeout_s": TIMEOUT_S}
    print(f"run {started}: entry={entry_id} live-version={card_version or 'unknown'}", flush=True)

    rows = []
    for prompt in prompts:
        print(f"[{prompt['id']}] {prompt['prompt']!r} ...", flush=True)
        row = await run_prompt(client, entry_id, prompt, out_dir)
        rows.append(row)
        print(f"[{prompt['id']}] {row['outcome']} render_path={row['render_path']} "
              f"fallback={row['render_fallback_reason']} png={row['png']} "
              f"({row['elapsed_s']}s)", flush=True)
        (out_dir / "manifest.json").write_text(json.dumps({"meta": meta, "rows": rows}, indent=1))

    write_report(out_dir, meta, rows)
    await client.ws.close()
    print(f"\ncaptured → {out_dir}/ (manifest.json, REPORT.md, PNGs + snapshots)")
    print("Next: Claude reads the PNGs + manifest and fills each Judgment in REPORT.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
