# Analysis-library benchmark (ADR-0031)

Measures whether local 3060-class models (`gemma4:e4b`, `qwen2.5-coder:7b`) can
write **working analysis code** — pandas / scipy / seaborn / statsmodels /
scikit-learn — that answers real natural-language questions about **real Home
Assistant history**, under Isolinear's `render_chart(data, output_path)`
contract. It is the proof gate ADR-0031 acceptance depends on.

## Why real data

Synthetic uniform-timestamp data hides the failures that actually matter. The
first run of this benchmark discovered that the dominant failure mode is not
statistics but **`pandas.to_datetime` format-inference on HA's mixed-precision
timestamps** — invisible with clean synthetic data. Hence: real history.

## Layout

- `prompts.json` — 16 natural-language prompts mapped to library targets, plus
  grounding adversarials. Committed.
- `extract_fixture.py` — pulls a 7-day history sample from your HA into
  `home_data.json` (timestamps as epoch-ms per ADR-0031 decision 9).
  **gitignored output** (real home data).
- `run_benchmark.py` — drives both models, executes each generation against the
  fixture, scores strict / repaired / png / answer. One repair round per failure.
- `FINDINGS.md` — the 2026-07-02 results and what they decided in ADR-0031.
- `runs/`, `home_data.json`, `results.json` — **gitignored** (real data +
  generated code).

## Run

```bash
# 1. Extract the fixture from your HA (never committed)
HA_URL=http://<ha-host>:8123 HA_TOKEN=<long-lived-token> \
  python3 evals/analysis_benchmark/extract_fixture.py

# 2. Point BENCH_PY at an interpreter with the analysis stack installed
python3 -m venv /tmp/bench && /tmp/bench/bin/pip install \
  pandas numpy matplotlib scipy seaborn statsmodels scikit-learn

# 3. Run against a reachable Ollama
OLLAMA_URL=http://<ollama-host>:11434/api/chat \
  BENCH_PY=/tmp/bench/bin/python \
  python3 evals/analysis_benchmark/run_benchmark.py
```

## Note on the execution environment

`run_benchmark.py` executes generated code with `BENCH_PY`, **not** the real
worker sandbox. It measures analytical capability + result quality. The pinned
worker environment (pandas 2.x, the `-I` sandbox, the import allowlist) is a
separate concern validated when scipy/seaborn are actually added to the worker
image. Note pandas 3.x rejects the deprecated `'H'`/`'M'` offset aliases that the
worker's pandas 2.x still accepts (with a FutureWarning) — a preview of a future
image bump.
