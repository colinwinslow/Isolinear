# Rule-gate findings — bare-non-ASCII prompt rule (open-queue (o))

Eval: `evals/codegen_rule_gate.py`. Runner writes `rule_gate_results.json`.

## Question

Does the generation-side `_CODEGEN_PROMPT_RULES` rule added in 0.2.13 — "write
all labels as Python string literals; never use `°` / `%` as a bare Python
token" — still earn its place in the prompt, now that (a) 0.2.14 attaches
`source_line` to every violation so repair can recover the class, and (b) the
0.2.17 unit-grounding rule makes the model read the unit from
`data['history_series'][i]['unit']` (a `str` variable), keeping `°` out of bare
code literals structurally?

## Method

The prior `evals/codegen_reliability.py` cannot answer this — it carries a stale
packet-5 mirror of the rules and `degF` (ASCII) units, so the `°` class can't
even trigger. This eval drives the **production** codegen path
(`OllamaCompatiblePlannerClient.generate_chart_code` / `repair_chart_code`, the
real `_CODEGEN_PROMPT_RULES`, the real `_codegen_request_view` projection) with
production-shaped data — `°F` / `%` units, `ts_epoch_ms` points, ADR-0033
`derived_intervals` bands — against live `gemma4:e4b` and a live worker sandbox.
Six cases (single/two-series temp, numeric+state overlay, humidity `%`,
aggregate bar, histogram) × **with vs without** the rule × 3 runs = 36 runs. A
"bare-non-ASCII incident" is a `syntax_error` violation whose message is
`invalid character …` or whose `source_line` contains a non-ASCII byte.

Run: 2026-07-06, `gemma4:e4b`, worker image with the 0.2.22 metadata-coercion +
matplotlib-submodule-allowlist fixes, `max_repairs=3`.

## Result

| arm | accepted | first-attempt | bare-non-ASCII incidents |
|---|---|---|---|
| with_rule | 18/18 | 17 | **0** |
| without_rule | 18/18 | 15 | **0** |

**Zero bare-non-ASCII incidents in either arm across all 36 runs.** The four
multi-attempt runs (one with-rule, three without) were all `runtime_error`, a
different failure class, each recovered by one repair — the 15-vs-17
first-attempt gap is model variance in the two-series runtime path, not the rule
preventing a `°` failure. The rule prevented nothing.

## Decision — RETIRE (shipped 0.2.22)

The rule is dropped from `_CODEGEN_PROMPT_RULES`. The `°` class is now prevented
structurally by the unit-grounding rule (the model never types `°` as a literal)
and recoverable by `source_line`-assisted repair if it ever recurs. Small floor
models degrade on long rule lists, so a rule that gates zero failures is net
negative. Standing division reaffirmed: contract rules stay in the prompt;
failure-driven style hints must earn their accept-rate in an eval.

**Caveat:** the corpus uses synthetic per-series data (sine waves), so this
measures the generation/repair behavior, not real-history grounding — the live
e2e harness (`evals/e2e_pipeline_harness.py`) covers the real pipeline. Re-run
this gate if a future prompt family reintroduces bare-symbol pressure.
