# Alignment rule gate — findings (e2e-11/12/13 root fix + e2e-18 hardening, 0.2.24)

**Context.** The 0.2.23 live e2e run (ADR-0034 conduit) made the analysis layer
fire — and firing exposed how the floor model combines irregular series: the
cross-sensor mean spiked ABOVE both inputs (e2e-11, impossible for a true mean),
the delta came back empty (e2e-12), and correlation found "no common timestamps"
(e2e-13 — the 8th-session `pearson_r` exact-intersection gap, live). Root cause:
the production codegen rules carried the benchmark's D9 epoch-ms lesson but never
its OTHER data-loading lesson — *"sampling is IRREGULAR and differs per entity;
resample/align before combining"* — which had only ever lived in the benchmark's
own system prompt. The analysis-intent probe couldn't see this class: its
synthetic series shared one perfectly aligned grid.

**Method.** `evals/alignment_rule_gate.py` drives the PRODUCTION codegen path
against live gemma4:e4b with genuinely irregular data (per-entity step 7 vs 11
min, deterministic jitter ±90/±150 s, phase offset → the two sensors share ZERO
timestamps), two arms (production rules with/without the alignment text),
execution-truth judges tuned to the live failures: the union artifact is caught
by std (a true derived mean of these sines has std ≈ 2.1; the union artifact
swings 64↔71, std ≥ 3.4), the exact-join delta by the NaN answer, the empty
intersection by the missing coefficient.

**Iteration 1 — prose ordering: 2/6.** The first alignment sentence prescribed
the steps in prose ("one Series per entity … resample each … interpolate, then
dropna"). The without-arm reproduced every live failure exactly (union-artifact
std 4.16; answers literally reading "the kitchen is nan °F warmer"; "correlation
could not be calculated due to insufficient or misaligned data points") — but
the with-arm only went 2/6. Reading the failing generations: gemma absorbed the
*vocabulary* but scrambled the *order* — it built
`pd.DataFrame({'kitchen': s_k, 'basement': s_b}).dropna()` FIRST (on disjoint
indexes `.dropna()` deletes every row), then resampled/interpolated the
emptiness → an all-NaN derived series → invisible line / nan answers.

**Iteration 2 — literal idiom: 9/9.** Rewrote the rule around one copyable
per-entity idiom with the order baked in
(`pandas.Series([p['value'] …], index=pandas.to_datetime([p['ts_epoch_ms'] …],
unit='ms')).resample('5min').mean().interpolate()` — resample EACH series
separately BEFORE combining; only then combine and `.dropna()`), plus the
explicit DON'T (never `.dropna()` a DataFrame built from two un-resampled
series). Result: **with_alignment 9/9 clean, all first-attempt** (mean 67.51 /
std 2.12 ≈ truth; delta 7.00; coefficient 1.00) vs **without_alignment 0/6**.
This is the ADR-0033 `axvspan` lesson generalized: **a floor model follows a
literal code idiom reliably where it scrambles an equivalent prose ordering.**

**e2e-18 hardening (same commit).** The live `invalid_model_provider_chart_spec`
on the deviation prompt was diagnosed as a planner variance tail: a sample plans
the computed result ("Average"/"Deviation") as its own series, and constrained
decoding — whose `source.entity_id` enum only contains approved ids — forces it
onto an already-used entity → `_check_chart_spec_no_duplicate_series_sources`
rejection (the 0.1.37 relabel-reuse class through a new door). The
satisfiability rule now explicitly prohibits planning the computed result as a
series. Re-check with the hardened rule: deviation ×3, heatmap ×2, cross-metric
correlation ×2 → **7/7 `chart_spec_ready`, 7/7 contract-valid.** (The
cross-metric prompt — live e2e-14's planner failure — also planned cleanly in
every sample here; its live failure remains attributed to variance/disclosure
shape. A bounded re-plan-on-validation-failure pass would close both tails
structurally — noted in the open queue.)

Raw evidence: `alignment_rule_gate_results.json` (both arms, per-run attempts,
line stats, answers, final code).
