# Analysis-intent probe — findings (open-queue (q), ADR-0034 evidence)

**Question.** The 16th-session live e2e run proved the model-authored analysis
layer never fires on the live floor model (every transform/correlation/question
prompt plotted raw series with an empty `answer_text`). Diagnosis attributed it
to the intent conduit, not model capability: the codegen payload carries no user
request, its task is "render the ChartSpec", and the 0.2.19 grounding rule
hard-instructs raw-line plotting. Does handing the production codegen path the
user's request (plus a reframed task and a conditional plot rule) make the
analysis fire — without hurting acceptance or grounding?

**Method.** `evals/analysis_intent_probe.py` drives the PRODUCTION codegen path
(real `generate_chart_code` / `repair_chart_code`, real `_CODEGEN_PROMPT_RULES`
+ `_codegen_request_view` projection) against live `gemma4:e4b`, six cases
mirroring the failed e2e prompts (e2e-06/11/12/13/17/18), two arms × 2 runs:

- **baseline** — the payload exactly as shipped (no user request anywhere);
- **intent** — the ADR-0034 delta: `user_request` in the payload, task reframed
  to "fulfill user_request", the plot-every-numeric-series rule made the
  DEFAULT with a compute-the-derived-series exception, the answer rule keyed on
  `user_request`. Everything else (grounded preview, unit rules, derived
  intervals, claims recipe) byte-identical production.

Ground truth is EXECUTION (15th-session method): each generation runs in a real
venv against full synthetic data with known analytics (kitchen 71±4 sin,
basement 64±2 sin, same phase → combined mean 67.5, delta 7, r≈+1; the rolling
case adds strong deterministic noise so smoothing measurably cuts std). The
judge checks what was actually plotted (matplotlib line stats) and what
`answer_text`/`claims` came back — numeric checks, not vibes.

**Result: baseline 0/12 fired — intent 12/12 fired, all first-attempt.**

| case (e2e twin) | baseline | intent |
|---|---|---|
| q_mean (e2e-06, weekly average question) | silent, no answer_text | answer carries **71.00** (true mean 71) + 1 claim |
| t_mean (e2e-11, cross-sensor mean) | raw lines at 71.0/64.0 | plotted derived line mean **67.50** (true 67.5) |
| t_delta (e2e-12, how much warmer) | silent, no answer | answer carries **7.00** (true 7) + delta claims |
| corr (e2e-13, correlated?) | silent, no coefficient | answer carries coefficient **1.00** (true ≈1) + pearson_r claim |
| roll (e2e-17, rolling average) | plotted std 1.88 = raw (no smoothing) | plotted std **0.75–0.79** vs raw 1.88 (real smoothing) |
| dev (e2e-18, deviation from average) | raw lines at 71.0/64.0 | plotted deviation line mean **0.00** |

Supporting observations:

- **The baseline arm reproduces the live e2e failure offline, 12/12** — same
  raw-lines-and-silence signature. The gap is the payload, not "gemma variance".
- **Acceptance did not degrade:** every intent run accepted first-attempt (the
  two baseline t_delta/roll runs needing a repair were ordinary runtime slips,
  repaired by the production loop).
- **Zero off-allowlist imports in any arm** — the intent framing did not push
  the model toward non-sandboxed libraries.
- **Claims fire** (1–2 per answer-bearing run, `pearson_r`/`mean`/`delta`), so
  the ADR-0031 D8a answer-grounding check finally has live input.
- Cosmetic wobble: one dev run produced a slightly garbled answer sentence
  ("…were generally The temperatures showed…") with correct numbers — the kind
  of thing the grounding check/caveat path tolerates; noted, not gating.

**Planner side (reproduced separately, same session):** the e2e-15 heatmap
refusal root-caused — as-shipped, gemma answers *"I cannot generate a true
heatmap … using the available chart types"* (`clarification_needed`; the
single-family schema pins `chart_type`). A candidate "analysis prompts over
approved entities ARE satisfiable — plan the raw input series, downstream code
computes" rule flips it to `chart_spec_ready` with the raw series. e2e-14
(cross-metric correlation) reproduced as chart_spec_ready offline with the
exact entity pair — live failure was planner variance / a different disclosed
set, not structural; the rule is expected to stabilize it.

**Conclusion.** The capability was never missing — the conduit was. ADR-0034
adopts the intent-arm deltas verbatim as the design. Accept gate for the
implementation: the live e2e harness analysis prompts (e2e-06/11/12/13/17/18 →
PASS; e2e-14/15 → planner-ready).

Raw results: `analysis_intent_probe_results.json` (per-run attempts, plotted
line stats, answers, claims, final code).
