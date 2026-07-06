---
id: 0034
title: The user's request reaches the codegen model — the analysis-intent conduit
status: draft
date: 2026-07-06
supersedes: []
superseded-by: null
tags: [codegen, analysis, prompt, planner, adr-0031]
---

# ADR-0034: The user's request reaches the codegen model — the analysis-intent conduit

## Context

The 16th-session live e2e run (open-queue (q), `evals/e2e_runs/20260706T035420Z/`)
proved the ADR-0031 tranche-1 model-authored analysis layer does **not** fire on
the live floor model: every transform / correlation / question prompt (e2e-06,
11, 12, 13, 17, 18) collapsed to plotting the raw input series with an
analysis-flavored title and an empty `answer_text`; two more (14, 15) failed at
the planner. The capability had only ever been proven by hand-fed eval prompts
(`evals/analysis_benchmark/`).

Diagnosis (17th session) found the gap is **structural, not model capability**
— the intent never reaches the model that writes the code:

1. **The codegen payload does not carry the user's request.** Its task is
   "render the supplied, already-validated ChartSpec"; `_codegen_request_view`
   discloses `chart_spec` / `history_series` / `derived_intervals` / `output`.
   The prompt-rule "**If the prompt asks a question** … return `answer_text`"
   is conditioned on a prompt the model never sees. The only intent remnant is
   the planner-authored `title`/`summary` — hence analysis-flavored titles over
   raw plots.
2. **The 0.2.19 grounding rule hard-instructs raw plotting.** "Plot each series
   in `data['history_series']` whose 'kind' is 'numeric' as a line, iterating
   that list directly" leaves an obedient floor model no room to plot a derived
   series instead — and `chart_spec` (the only intent carrier) is explicitly
   declared "intent/metadata only — NEVER read".
3. **The planner is told analysis is unsatisfiable.** "Only return status
   chart_spec_ready if every piece of information the user asked for can be
   represented using only the approved_entity_ids" — a correlation or heatmap
   is not an entity, so the planner reasonably refuses. Reproduced live:
   for e2e-15 gemma4:e4b answered *"I cannot generate a true heatmap … using
   the available chart types"* (`clarification_needed`); the single-family
   schema pins `chart_type` so it literally cannot say yes.
4. The benchmark that "proved" the capability handed the model the **question**
   with an "analysis engine" identity and no plot-raw-series rule — the
   opposite framing on every count.

A design probe (`evals/analysis_intent_probe.py`) measured the candidate fix on
the **production** codegen path (real `generate_chart_code`/`repair_chart_code`,
real rules + prompt-view) against live gemma4:e4b with execution-truth judging
(run the generated code on data with known analytics; check what was actually
plotted and answered): the baseline arm reproduces the e2e failures offline
(raw lines, no answer); the intent arm — user request in the payload, task
reframed, plot rule conditional — computes the analysis. Results:
`evals/prompts/analysis_intent_probe_results.json` +
`evals/prompts/analysis_intent_probe_findings.md`.

## Decision

**The user's request text becomes part of the codegen generation contract: the
generation and repair prompts carry `user_request`, the codegen task is "fulfill
user_request" (guided by the validated ChartSpec), and the plot-raw-series rule
becomes the default with a compute-the-derived-series exception.** The planner
prompt gains a rule that analysis prompts over approved entities ARE
satisfiable — plan the raw input series; downstream generated code computes the
analysis.

Concretely:

1. **Conduit (generation-time only).** `generate_chart_code` /
   `repair_chart_code` accept the user's prompt (length-bounded) and place it as
   `user_request` in the prompt payload beside `task`/`rules`/`codegen_request`.
   The worker render-request contract is untouched — the request text is a
   generation-time input, not render data, and never crosses to the worker.
2. **Task reframe.** The codegen task becomes: fulfill `user_request` — write
   matplotlib code that renders a chart answering the user's request from the
   supplied `history_series`, guided by the supplied already-validated
   ChartSpec.
3. **Conditional plot rule.** Default: plot each numeric series as a line
   (0.2.19 grounding, unchanged). Exception: when `user_request` asks for a
   computed analysis (cross-sensor average, difference, correlation, deviation,
   smoothing, distribution/pivot), compute the derived series from the numeric
   `history_series` points and plot the derived result. The state-series
   prohibition and the ADR-0033 `derived_intervals` band rule stay
   unconditional; `history_series` stays the sole data authority.
4. **Answer rule keys on `user_request`.** "If user_request asks a question …
   return `answer_text`" — now satisfiable. The D3 grounding contract
   (compute-and-f-string, claims ledger, verdicts derived) is unchanged, and the
   existing deterministic answer-grounding check now actually gates live
   answers.
5. **Planner analysis rule.** A prompt asking for a computed analysis over
   approved entities returns `chart_spec_ready` with one series per input
   entity the analysis needs; generated code does the math. (Live-verified:
   flips the e2e-15 heatmap refusal to a ready plan of the raw series.)

## Rationale

- **This is the architecture ADR-0031 already decided** — "grounding = generated
  code computes AND formats the answer", "model-authored transforms in generated
  code" (ADR-0030). Transforms deliberately do NOT live in schema enums or
  planner structure; the missing piece was only the intent conduit to the model
  that authors the code. The alternative — structured analysis intent planned
  into the ChartSpec (grow the `transform` enum, add analysis fields) — walks
  back that decision, caps the analysis space at what the schema enumerates, and
  burdens the *planner* (the same floor model that already fails planning a
  heatmap) with more required structure.
- **Probe-measured on the production path** (execution truth, not inspection):
  **baseline 0/12 fired — intent 12/12 fired, all first-attempt**, computing
  the true values across all six e2e failure twins: weekly-average answer 71.00,
  cross-sensor mean plotted at 67.50, delta 7.00, correlation coefficient 1.00
  with a pearson_r claim, real smoothing (plotted std 0.75 vs raw 1.88), and a
  deviation line centered on 0.00. Zero off-allowlist imports in any arm; the
  claims ledger fires (the D8a grounding check finally has live input). See the
  findings file for the full tally.
- **Grounding is preserved, not traded away.** The 0.2.18/0.2.19 regression arc
  showed the floor model needs concrete real points under the runtime key —
  that mechanism (bounded preview, `history_series` as sole data authority,
  catalog-authoritative units) is untouched. The plot rule keeps raw-line
  plotting as the DEFAULT; only an explicit analysis request diverts it.
- **`output_modality` (parked packet 5) stays parked.** With `user_request` in
  the codegen prompt, the codegen model reads compute-vs-plot and
  answer-vs-chart directly from the request; a separate planner-emitted signal
  is redundant for this slice.

## Security / boundary review

- The user's request is user-authored text already disclosed to the same model
  in the planning and entity-selection prompts — no new trust exposure; it is
  not a secret, token, or entity outside the allowlist. It is length-bounded
  before insertion (token discipline, not security).
- Prompt-injection via the request text steering generated code is contained
  exactly as before: the enforcement boundary is the worker sandbox (invariant
  #3 — static safety check on every attempt, import allowlist, audit hook,
  `-I`, stripped env, fixed output path), which this ADR does not touch. The
  request text never reaches the worker or the sandbox payload.
- Invariant #1 (allowlist) unaffected: the data disclosed to the model is still
  the validated, allowlisted render data; the analysis rule tells the planner to
  plan approved input series, and allowlist validation of the plan is unchanged.

## Consequences

**Enables:**
- The ADR-0031 "data-analysis assistant" identity live: transforms, deltas,
  correlations, deviations, smoothing, and grounded `answer_text` on the real
  card path — the headline e2e gap (open-queue (q)).
- The answer-grounding check (D8a) finally exercised live (claims now fire).
- Analysis presentations beyond the planned family for **derived numeric**
  results (a correlation scatter, an hour×day heatmap grid) become reachable
  via generated code where `user_request` asks for them, without touching
  ChartSpec routing.

**Constrains:**
- The ChartSpec stays the planning contract and data boundary (ADR-0030); the
  planner still never chooses beyond its envelope; deterministic render-family
  routing from entity KINDS (invariant #9, ADR-0022) is unchanged — the
  presentation latitude above applies to numeric-series analyses only.
  Binary/categorical routing (and its codegen gap, open-queue (r)) is a
  separate concern this ADR does not alter.
- The Pillow fallback renders the planned ChartSpec (raw series) as before — an
  analysis prompt that exhausts codegen repair degrades to a raw chart with the
  fallback surfaced, never a fabricated answer (`answer_text` only ever comes
  from executed code; ADR-0031 D3).
- The codegen prompt grows by one bounded field; rule-count discipline
  (open-queue (o): floor models degrade on long rule lists) still applies —
  this ADR rewrites two existing rules rather than appending new ones.

**Open:**
- e2e-14 (cross-metric correlation) failed live at the planner but reproduces
  as chart_spec_ready offline with the exact entity pair — planner variance or
  a different disclosed entity set; the analysis rule is expected to stabilize
  it, verify at the e2e re-run.
- Whether heatmap/scatter should eventually become first-class render families
  (envelope + Pillow parity) rather than codegen-only presentations — revisit
  if analysis presentations prove load-bearing.
- The proof gate for acceptance: the e2e harness analysis prompts
  (e2e-06/11/12/13/17/18 → PASS; e2e-14/15 → planner-ready) on a live run.

## References

- ADR-0029 (worker revival, data boundary), ADR-0030 (codegen-primary,
  model-authored transforms), ADR-0031 (model-authored analysis; D3 grounding,
  D8a grounding check, D9 epoch-ms), ADR-0033 (precomputed overlay bands)
- Spec: `docs/specs/model-authored-analysis.md` (sections 1, 2, 4)
- Evidence: `evals/e2e_runs/20260706T035420Z/REPORT.md` (the live gap),
  `evals/analysis_intent_probe.py` + `evals/prompts/analysis_intent_probe_results.json`
  + `evals/prompts/analysis_intent_probe_findings.md` (the probe),
  `evals/analysis_benchmark/FINDINGS.md` (the hand-fed proof that misled)
