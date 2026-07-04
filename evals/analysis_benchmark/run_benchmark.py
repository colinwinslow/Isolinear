#!/usr/bin/env python3
"""Analysis-library capability benchmark: real HA data -> local models -> execute -> score.

Drives prompts.json through two Ollama models, executes each generated
render_chart(data, output_path) against the local home_data.json fixture (produced
by extract_fixture.py), and scores strict-pass / repaired-pass / answer / PNG.
One repair round per failure mirrors Isolinear's bounded codegen repair loop.

Claim-emission scoring (grounding-check spec proof req #4): prompts flagged
"claim": true expect the generated code to ALSO return a machine-readable
claims recipe ({metric, inputs, window?, params?, value, verdict?, rule?}).
Emitted claims are scored by the REAL production checker
(custom_components.isolinear.answer_grounding — pure stdlib) against the same
fixture, so "well-formed" and "value agrees with an independent registry
recompute" are judged by exactly the code that will gate first display.

Env:
  OLLAMA_URL   default http://localhost:11434/api/chat
  BENCH_MODELS default "gemma4:e4b,qwen2.5-coder:7b"
  BENCH_PY     python that has pandas/scipy/seaborn/statsmodels/sklearn installed
               (default: this interpreter). Generated code executes with it.

The home data + generated code are gitignored (private). See README.md.
"""
from __future__ import annotations
import json, subprocess, textwrap, time, re, os, sys, pathlib, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
MODELS = os.environ.get("BENCH_MODELS", "gemma4:e4b,qwen2.5-coder:7b").split(",")
BENCH_PY = os.environ.get("BENCH_PY", sys.executable)
RUNS = HERE / "runs"; RUNS.mkdir(exist_ok=True)

# The production grounding checker (pure stdlib) is the claim scorer — no
# parallel reimplementation of "well-formed" (spec §3 steps 1–6).
from custom_components.isolinear.answer_grounding import _check_claim, run_grounding_check  # noqa: E402

fixture = json.load(open(HERE / "home_data.json"))
prompts = json.load(open(HERE / "prompts.json"))["prompts"]

# Fixture -> the history_series shape answer_grounding checks against
# (dict points with ts_epoch_ms; ADR-0022 raw-state kinds for anchor entities).
_KIND_MAP = {"binary": "binary_state", "categorical": "categorical_state"}
HISTORY_SERIES = [
    {"entity_id": eid,
     "kind": _KIND_MAP.get(m["kind"], m["kind"]),
     "points": [{"ts_epoch_ms": int(ts), "value": v} for ts, v in m["points"]]}
    for eid, m in fixture["entities"].items()
]
DELIVERED_IDS = {s["entity_id"] for s in HISTORY_SERIES}


def catalog():
    return "\n".join(
        f"  - {eid}  ({m['friendly_name']}) — kind={m['kind']}"
        f"{(' [' + m['unit'] + ']') if m.get('unit') else ''}, {len(m['points'])} points"
        for eid, m in fixture["entities"].items())


SYSTEM = f"""You are the analysis engine for Isolinear, a Home Assistant data-analyst plugin.
You write ONE Python function and nothing else:

    def render_chart(data, output_path):
        # data["entities"][entity_id] = {{
        #   "friendly_name": str, "unit": str|None, "device_class": str|None,
        #   "kind": "numeric"|"binary"|"categorical",
        #   "points": [[epoch_ms_int, value], ...]   # ts = unix epoch MILLISECONDS (int); value: float | "on"/"off" | "cooling"/"idle"/"fan"
        # }}
        # Sampling is IRREGULAR and differs per entity — resample/align before combining series.
        # Save a matplotlib PNG to output_path.
        # RETURN a dict. If the question has a factual answer, include "answer": a natural-language
        # sentence whose numbers AND any yes/no verdict are COMPUTED from the data (f-string over
        # computed values) — never assert a verdict you did not compute.

Available libraries: pandas, numpy, matplotlib (Agg), scipy, seaborn, statsmodels, scikit-learn.
Do NOT call print(). Do NOT read files or the network. Output only the code for render_chart, in one python code block.

Data-loading rules (the sampling is real Home Assistant history):
- Timestamps are unix epoch MILLISECONDS (integers). Build a DatetimeIndex with pd.to_datetime(<ints>, unit='ms', utc=True).
- Use CURRENT lowercase pandas offset aliases: 'h' (hour), 'min' (minute), 'D' (day) — not 'H' or 'M'.
- Series are irregular and per-entity; resample/align before combining.

Claims recipe (machine-readable, for verification only — mirrors the production codegen prompt):
When the answer includes a qualitative verdict or comparison, ALSO return a "claims" list in the
returned dict. Each claim is a dict with: 'metric' (e.g. 'pearson_r', 'mean', 'delta', 'hours_above'),
'inputs' (list of entity_ids used), 'value' (the SAME computed numeric variable formatted into the
sentence, recorded as a raw JSON number — 'value': corr, NEVER a pre-formatted string like f'{{corr:.2f}}'
or '3.0°F'; units belong in the sentence, not the claim),
'verdict' (the SAME verdict variable in the sentence), 'rule' ({{"bands": [[threshold_or_null, label], ...],
"basis": "value" or "abs"}}; bands in descending threshold order; last entry null threshold as catch-all;
labels must not be substrings of one another), and optionally 'window' ({{"start": epoch_ms, "end": epoch_ms}})
and 'params' (flat dict, e.g. {{"threshold": 75.0}}).
Example: claims = [{{'metric': 'pearson_r', 'inputs': ['sensor.a', 'sensor.b'], 'value': corr,
'verdict': verdict, 'rule': {{'bands': [[0.3, 'Yes'], [None, 'Not really']], 'basis': 'abs'}}}}].
When the analysis is scoped to a state-change event (e.g. "after the AC started cooling"), the claim
'window' may instead be ANCHORED: {{"anchor": {{"entity": <binary/categorical entity_id>, "to": <state
transitioned INTO, exact string>, "from": <prior state, optional>, "occurrence": <1-based index among
matching transitions; negative counts from the end, -1 = most recent>, "search": {{"start": epoch_ms,
"end": epoch_ms}}, "resolved_at": <the epoch_ms timestamp of the transition your code actually found>}},
"direction": "after" or "before", "duration_ms": <window length>}}. resolved_at must be the COMPUTED
transition timestamp (a variable), never a guess.

Approved entity catalog:
{catalog()}
"""

HARNESS = textwrap.dedent('''\
    import json, warnings, traceback
    warnings.simplefilter("ignore")
    import matplotlib; matplotlib.use("Agg")
    data = json.load(open("{fixture}"))
    ns = {{}}
    def _san(o):
        # numpy scalars etc. -> plain JSON so claims survive the boundary
        try:
            return float(o)
        except Exception:
            return str(o)
    try:
        exec(open("{codefile}").read(), ns)
        res = ns["render_chart"](data, "{out_png}")
        ans = res.get("answer") if isinstance(res, dict) else None
        if ans is None and isinstance(res, dict):
            ans = res.get("answer_text")
        claims = res.get("claims") if isinstance(res, dict) else None
        print("__RESULT__" + json.dumps({{"ok": True, "answer": ans, "claims": claims}}, default=_san))
    except Exception as e:
        print("__RESULT__" + json.dumps({{"ok": False, "error": f"{{type(e).__name__}}: {{e}}",
              "trace": traceback.format_exc()[-600:]}}))
''')


def _chat(messages, npred=6000):
    # 6000: the 3000 cap truncated generations mid-string once the claims
    # instruction made gemma write longer code (unterminated-string SyntaxErrors);
    # production codegen does not cap num_predict at all.
    body = json.dumps({"model": messages.pop("__model__"), "stream": False, "think": False,
                       "options": {"temperature": 0, "num_predict": npred},
                       "messages": messages["msgs"]}).encode()
    req = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    resp = json.loads(urllib.request.urlopen(req, timeout=180).read())
    return resp["message"]["content"], round(time.time() - t0, 1)


def generate(model, question):
    return _chat({"__model__": model, "msgs": [
        {"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]})


def repair(model, question, prev_code, error):
    return _chat({"__model__": model, "msgs": [
        {"role": "system", "content": SYSTEM}, {"role": "user", "content": question},
        {"role": "assistant", "content": f"```python\n{prev_code}\n```"},
        {"role": "user", "content": f"That failed with:\n{error}\nReturn the corrected render_chart in one python code block."}]})


def extract_code(text):
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    if blocks:
        code = max(blocks, key=len)
    elif "```" in text:
        code = re.sub(r"^(python|py)\s*\n", "", text.split("```", 1)[1], flags=re.IGNORECASE).split("```", 1)[0]
    else:
        code = text
    return "\n".join(l for l in code.splitlines() if l.strip() not in ("```", "```python", "```py")).strip()


def execute(model, p, code):
    mdir = RUNS / model.replace(":", "_"); mdir.mkdir(exist_ok=True)
    codefile = mdir / f"{p['id']}.py"; codefile.write_text(code)
    out_png = mdir / f"{p['id']}.png"
    if out_png.exists():
        out_png.unlink()
    hf = mdir / f"{p['id']}_harness.py"
    hf.write_text(HARNESS.format(fixture=HERE / "home_data.json", out_png=out_png, codefile=codefile))
    env = dict(os.environ, MPLBACKEND="Agg", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
    try:
        proc = subprocess.run([BENCH_PY, str(hf)], capture_output=True, text=True, timeout=90, env=env)
        line = [l for l in proc.stdout.splitlines() if l.startswith("__RESULT__")]
        result = json.loads(line[0][len("__RESULT__"):]) if line else {"ok": False, "error": "no result", "trace": proc.stderr[-600:]}
    except subprocess.TimeoutExpired:
        result = {"ok": False, "error": "timeout(90s)"}
    png_ok = out_png.exists() and out_png.stat().st_size > 1000 and out_png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    return result, png_ok


_MALFORMED_CODES = {"grounding_claim_malformed", "grounding_recipe_incomplete"}


def score_claims(answer, claims):
    """Score an emitted claims list with the production grounding checker.

    well_formed  — no claim tripped the checker's structure/recipe steps (§3 1–2)
    any_verified — at least one claim's value was independently reproduced by the
                   registry recompute (the strong value↔data tier)
    anchored     — at least one claim carried the spec-§1a anchored window form
    """
    out = {"claims_count": 0, "well_formed": None, "any_verified": False,
           "anchored": False, "claim_codes": [], "grounding_outcome": None}
    if not isinstance(claims, list) or not claims:
        return out
    answer = answer if isinstance(answer, str) else None
    out["claims_count"] = len(claims)
    well_formed = True
    for c in claims:
        r = _check_claim(c, HISTORY_SERIES, DELIVERED_IDS, answer)
        out["claim_codes"].append(r["code"])
        if r["code"] in _MALFORMED_CODES:
            well_formed = False
        if r["outcome"] == "verified":
            out["any_verified"] = True
        if isinstance(c, dict) and isinstance(c.get("window"), dict) and "anchor" in c["window"]:
            out["anchored"] = True
    out["well_formed"] = well_formed
    overall = run_grounding_check({"answer_text": answer, "claims": claims}, HISTORY_SERIES)
    out["grounding_outcome"] = overall["outcome"]
    return out


def score(model, p):
    content, gen_s = generate(model, p["question"])
    code = extract_code(content)
    result, png_ok = execute(model, p, code)
    strict = result.get("ok", False) and png_ok
    repaired = False
    if not strict:
        try:
            rcontent, rs = repair(model, p["question"], code, result.get("error", "unknown"))
            rcode = extract_code(rcontent)
            rresult, rpng = execute(model, p, rcode)
            if rresult.get("ok", False) and rpng:
                result, png_ok, repaired, gen_s = rresult, rpng, True, gen_s + rs
        except Exception:
            pass
    ans = result.get("answer")
    claim_scores = score_claims(ans, result.get("claims"))
    return {"id": p["id"], "model": model, "target": p["target"], "gen_s": gen_s,
            "strict_pass": strict, "repaired": repaired,
            "ran": result.get("ok", False), "png": png_ok,
            "answer": ans, "nan_in_answer": bool(ans and re.search(r"\bnan\b", str(ans).lower())),
            "claim_expected": bool(p.get("claim")),
            "anchored_expected": p.get("claim_window") == "anchored",
            "claims": result.get("claims"),
            "claims_count": claim_scores["claims_count"],
            "claims_well_formed": claim_scores["well_formed"],
            "claims_any_verified": claim_scores["any_verified"],
            "claims_anchored": claim_scores["anchored"],
            "claim_codes": claim_scores["claim_codes"],
            "grounding_outcome": claim_scores["grounding_outcome"],
            "error": result.get("error")}


def main():
    results = []
    for p in prompts:
        for model in MODELS:
            r = score(model, p)
            tag = ("OK*" if r["repaired"] else "OK ") if (r["ran"] and r["png"]) else "FAIL"
            claim_tag = ""
            if r["claim_expected"]:
                claim_tag = (f" claims={r['claims_count']} wf={r['claims_well_formed']} "
                             f"ver={r['claims_any_verified']} anch={r['claims_anchored']} "
                             f"[{','.join(r['claim_codes'])}]")
            print(f"[{tag}] {model:20} {p['id']:14} strict={r['strict_pass']} rep={r['repaired']} "
                  f"{r['error'] or (r['answer'] or '')[:60]}{claim_tag}")
            results.append(r)
    (HERE / "results.json").write_text(json.dumps(results, indent=1))
    for m in MODELS:
        rs = [r for r in results if r["model"] == m]
        print(f"{m}: strict {sum(r['strict_pass'] for r in rs)}/{len(rs)}  "
              f"with-repair {sum(r['ran'] and r['png'] for r in rs)}/{len(rs)}")
        # Claim-emission rate (grounding-check spec proof req #4) — over the
        # prompts whose reference demands a verdict/comparison claim.
        exp = [r for r in rs if r["claim_expected"]]
        if exp:
            emitted = [r for r in exp if r["claims_count"]]
            print(f"{m}: claim-expected {len(exp)} — emitted {len(emitted)}/{len(exp)}  "
                  f"well-formed {sum(1 for r in emitted if r['claims_well_formed'])}/{len(emitted) or 1}  "
                  f"registry-verified {sum(1 for r in emitted if r['claims_any_verified'])}/{len(emitted) or 1}")
            anch = [r for r in exp if r["anchored_expected"]]
            if anch:
                print(f"{m}: anchored-window expected {len(anch)} — emitted anchored "
                      f"{sum(1 for r in anch if r['claims_anchored'])}/{len(anch)}")
        spurious = [r for r in rs if not r["claim_expected"] and r["claims_count"]]
        if spurious:
            print(f"{m}: claims on {len(spurious)} non-claim prompts (harmless — check-only channel)")


if __name__ == "__main__":
    main()
