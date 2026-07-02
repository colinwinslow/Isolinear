#!/usr/bin/env python3
"""Analysis-library capability benchmark: real HA data -> local models -> execute -> score.

Drives prompts.json through two Ollama models, executes each generated
render_chart(data, output_path) against the local home_data.json fixture (produced
by extract_fixture.py), and scores strict-pass / repaired-pass / answer / PNG.
One repair round per failure mirrors Isolinear's bounded codegen repair loop.

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
OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
MODELS = os.environ.get("BENCH_MODELS", "gemma4:e4b,qwen2.5-coder:7b").split(",")
BENCH_PY = os.environ.get("BENCH_PY", sys.executable)
RUNS = HERE / "runs"; RUNS.mkdir(exist_ok=True)

fixture = json.load(open(HERE / "home_data.json"))
prompts = json.load(open(HERE / "prompts.json"))["prompts"]


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

Approved entity catalog:
{catalog()}
"""

HARNESS = textwrap.dedent('''\
    import json, warnings, traceback
    warnings.simplefilter("ignore")
    import matplotlib; matplotlib.use("Agg")
    data = json.load(open("{fixture}"))
    ns = {{}}
    try:
        exec(open("{codefile}").read(), ns)
        res = ns["render_chart"](data, "{out_png}")
        ans = res.get("answer") if isinstance(res, dict) else None
        print("__RESULT__" + json.dumps({{"ok": True, "answer": ans}}))
    except Exception as e:
        print("__RESULT__" + json.dumps({{"ok": False, "error": f"{{type(e).__name__}}: {{e}}",
              "trace": traceback.format_exc()[-600:]}}))
''')


def _chat(messages, npred=3000):
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
    return {"id": p["id"], "model": model, "target": p["target"], "gen_s": gen_s,
            "strict_pass": strict, "repaired": repaired,
            "ran": result.get("ok", False), "png": png_ok,
            "answer": ans, "nan_in_answer": bool(ans and re.search(r"\bnan\b", str(ans).lower())),
            "error": result.get("error")}


def main():
    results = []
    for p in prompts:
        for model in MODELS:
            r = score(model, p)
            tag = ("OK*" if r["repaired"] else "OK ") if (r["ran"] and r["png"]) else "FAIL"
            print(f"[{tag}] {model:20} {p['id']:14} strict={r['strict_pass']} rep={r['repaired']} "
                  f"{r['error'] or (r['answer'] or '')[:60]}")
            results.append(r)
    (HERE / "results.json").write_text(json.dumps(results, indent=1))
    for m in MODELS:
        rs = [r for r in results if r["model"] == m]
        print(f"{m}: strict {sum(r['strict_pass'] for r in rs)}/{len(rs)}  "
              f"with-repair {sum(r['ran'] and r['png'] for r in rs)}/{len(rs)}")


if __name__ == "__main__":
    main()
