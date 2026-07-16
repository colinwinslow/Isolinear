---
id: 0036
title: In-sandbox analysis helper library — ship the idiom as a callable
status: accepted
date: 2026-07-12
supersedes: []
superseded-by: null
tags: [codegen, analysis, sandbox, worker, prompt, adr-0030, adr-0034]
---

# ADR-0036: In-sandbox analysis helper library — ship the idiom as a callable

## Context

Every cross-series analysis failure of the last week died in the same ~10
generated lines — the plumbing between "raw per-entity points" and "an aligned,
entity-keyed DataFrame":

1. **0.2.31** — intermittent `KeyError: 'sensor.…'`: the floor model built a
   bare-list `pandas.concat([s1, s2], axis=1)` (positional columns) then indexed
   it by entity_id (live worker logs; reproduced; frame-keying rule gated at
   N=40/arm: without 2/40 KeyErrors, with 0/40).
2. **0.2.32 live** — "the average … was nan °F" served under an empty chart:
   an alignment variant emptied the combined frame to NaN (0.2.33 added the
   degenerate-answer tripwire so it can never be *served*, but the compute
   still fails).
3. **e2e-18 (2026-07-11, live 0.2.33)** — the deviation member: first attempt
   `syntax_error@L14`, then `runtime_error` ×3 → repair exhaustion → surfaced
   Pillow fallback, no derived series, no answer.

The composition *around* that step — which analysis to compute, what to plot,
the grounded answer sentence — the model handles well (e2e-11/19/20 all PASS
first-attempt on the same run). The failures are **re-implementation variance**:
at temperature 0 the model still varies run-to-run in how it transcribes the
alignment/keying idiom, and each cross-math request pays that transcription risk
again.

This project has already learned the underlying lesson twice, and escalated
twice: **floor models follow a code idiom where they scramble equivalent
prose** (ADR-0033 axvspan: literal idiom over prose; 0.2.24 alignment rule:
literal per-entity idiom 9/9 vs prose-ordered 2/6). The current rung is a
~900-character literal idiom embedded in the prompt rules — which the model
must re-type correctly every time, and which crowds a rule list floor models
degrade on (the 0.2.22 rule-retirement lesson).

The next rung is obvious: stop asking the model to transcribe the idiom and
ship the idiom as a function it calls.

## Decision

**A small, curated, integration-authored analysis helper module —
`isolinear_analysis` — is installed into the worker image's system
site-packages and allowlisted for generated-code import. The codegen prompt
rules prescribe calling it for cross-series math instead of transcribing the
alignment/keying idiom.** The model keeps composition (what to compute, what to
plot, the answer); the helper hardens only the plumbing step where every live
failure has occurred.

Tranche 1 is deliberately **one function**:

```python
import isolinear_analysis

frame = isolinear_analysis.align(data["history_series"], freq="5min")
# → pandas.DataFrame: one column PER ENTITY_ID (columns are the entity_id
#   strings), shared resampled time grid (DatetimeIndex), per-series
#   resample(freq).mean().interpolate(), then inner-joined and dropna'd.
#   Numeric series only (kind == "numeric"); raises ValueError with a clear,
#   repair-actionable message on no numeric series or an empty aligned result
#   (never returns an all-NaN frame).
```

Everything the model currently fumbles becomes a one-liner it reliably writes
against that frame: `frame.mean(axis=1)` (cross-sensor mean),
`frame[a] - frame[b]` (delta), `frame.corr()` (correlation),
`frame.sub(frame.mean(axis=1), axis=0)` (deviation — the residual live
failure). The alignment + frame-keying prompt rules collapse to a short
"call `isolinear_analysis.align()`" prescription with those one-liner examples
— the prompt gets **shorter**, not longer.

Mechanics:

1. **Packaging.** The module lives in-repo at `worker/isolinear_analysis/`
   and is COPY'd into the interpreter's system site-packages in
   `worker/Dockerfile` (the `-I` sandbox excludes user site and script dir;
   system site-packages is how matplotlib/pandas are importable today).
   Changes ship via worker image rebuild on CT103.
2. **Allowlist.** `isolinear_analysis` is added to the sandbox policy's
   `allowed_imports` (exact-match, one curated module). All other sandbox
   machinery — static safety check on every attempt, audit hook, `-I`, stripped
   env, memory cap, fixed output path — is untouched.
3. **Prompt.** The cross-series section of `_CODEGEN_PROMPT_RULES` is rewritten
   around the helper call; the repair task references it the same way. The raw
   idiom text (resample/keying) is dropped from the rules once the gate proves
   the helper arm.
4. **Failure semantics.** Helper errors are ordinary sandbox `runtime_error`s
   carrying the helper's explicit message (e.g. "no overlapping data after
   alignment") — honest, specific, and repair-actionable, instead of NaN
   propagation or a KeyError deep in pandas.

## Rationale

- **It targets the measured failure, not a hypothesis.** The 0.2.31/0.2.33/
  e2e-18 ledger localizes all recent cross-math variance to the align/combine
  step. A callable eliminates transcription of exactly that step; the model's
  remaining job on these prompts (compose one-liners over an entity-keyed
  frame + plot + answer) is the part it already passes.
- **It is the established escalation path, one rung further.** Prose →
  literal idiom was gated and won twice (ADR-0033, 0.2.24). Idiom → callable is
  the same move with a stronger guarantee: the plumbing cannot be mistyped
  because it is not typed.
- **Composition stays with the model** (the lean-on-model steer, bent only for
  plumbing). This is NOT planner-side tool-calling and NOT structured
  transforms in the ChartSpec: both alternatives cap the analysis space at an
  enumerated surface and were explicitly rejected by ADR-0030/0031/0034. The
  helper constrains nothing about *what* can be computed — generated code can
  still do anything the sandbox allows; it just no longer has to hand-roll
  alignment.
- **Prompt-length discipline.** ~900 chars of idiom leave the rules; the
  replacement prescription is a fraction of that. The 0.2.22 lesson (floor
  models degrade on long rule lists; hints must earn their keep) favors this
  on its own.
- **ADR-0035 synergy.** Saved re-runnable analysis code (v0.3 north star)
  calling a stable helper API survives model swaps and prompt-rule churn far
  better than idiom soup frozen at save time.
- **Alternatives considered:**
  - *Keep escalating prompt idioms* — the current rung already leaves e2e-18
    failing live; each new variance variant needs another sentence, growing the
    rule list without a structural guarantee.
  - *Ollama function-calling (planner or codegen calls `compute_mean(...)`)* —
    abandons the codegen architecture ADR-0030/0034 bet on and that now
    demonstrably fires live; caps flexibility at the tool list (the bottleneck
    Isolinear exists to escape).
  - *Structured transform enums in the ChartSpec* — walks back ADR-0031/0034
    explicitly (see ADR-0034 Rationale); burdens the planner, the weaker link.

## Security / boundary review

- The helper is **trusted, integration-authored code reviewed in-repo** and
  baked into the image — the same trust class as the sandbox runner itself. It
  adds no capability: it reads the in-sandbox `data` payload (already
  validated, allowlisted, normalized) and returns a DataFrame. No I/O, no env,
  no network, no file access.
- The import allowlist grows by exactly one curated module. Generated code is
  still statically checked on every attempt; nothing else in the sandbox
  posture changes (invariant #3).
- **The answer-grounding check's independence is preserved.** The
  integration-side `answer_grounding` registry remains a separate
  implementation in a separate process on the other side of the data boundary —
  "independently recomputed" in the two-tier guarantee stays true. Drift
  between helper and registry is testable (shared fixture tests), not a shared
  code path.
- No data-boundary change (ADR-0029): what crosses to the worker is unchanged;
  the helper runs inside the sandbox on data already there.

## Consequences

**Enables:**
- Structurally eliminates the align/combine transcription-variance class
  (KeyError, all-NaN frames, hand-rolled loop slips) — the residual cross-math
  variance basin after 0.2.31, including the e2e-18 deviation member.
- A shorter codegen rule list (the idiom text retires).
- A stable in-sandbox API surface for ADR-0035 saved analyses.
- A natural home for future *proven-need* helpers (the bar: a live failure
  ledger, like this one — no speculative generality, invariant #8).

**Constrains:**
- `isolinear_analysis` becomes a compatibility surface: generated (and later,
  saved) code depends on it. Changes must be additive; the module carries a
  `__version__`; breaking an existing signature requires a new ADR.
- Helper changes require a worker image rebuild + CT103 redeploy (the
  two-repo coordination cost) — unlike prompt-rule changes, which stay
  HACS-only. Keeping the surface minimal keeps this rare.
- The helper must never become a planner-visible enum or schema surface —
  it is generated-code convenience only; planning contracts are unchanged.

**Open:**
- Whether the prompt should keep a one-sentence fallback idiom for the case
  where the model needs non-default alignment (e.g. a different grid), or
  whether `align(freq=...)` parameters cover it. Tranche-1 lean: parameters.
- Whether `align` should also expose the label map (entity_id → friendly
  label) to nudge better derived-series labeling (the "Temperature" generic-
  label polish item). Tranche-1 lean: no — one job per function.
- Pillow fallback parity is explicitly NOT a goal (fallback renders the raw
  ChartSpec, as today).

## Proof gate (before acceptance)

1. **Unit tests** on `isolinear_analysis.align` (shape, keying, irregular
   inputs, empty/degenerate raises, parity fixtures against the
   `answer_grounding` registry's mean/delta on the same data).
2. **In-image proof**: the module imports under `python -I` in the rebuilt
   worker image and a helper-calling render returns a valid PNG through the
   live CT103 worker (the packet-3 pattern).
3. **Offline with/without gate** (the 0.2.26/0.2.31 pattern): the cross-math
   family — mean, delta, deviation, correlation — through the PRODUCTION
   codegen path against live gemma4:e4b, helper-arm rules vs current rules,
   execution-truth judged; headline metric = first-attempt execute + intent
   fire on the **deviation** member (the live residual failure).
4. **Live e2e re-run** post-deploy: e2e-11/12/13/17/18/19/20 — no verdict may
   degrade; e2e-18 flipping to PASS is the acceptance headline.

## References

- ADR-0029 (data boundary), ADR-0030 (codegen-primary, model-authored
  transforms), ADR-0031 (model-authored analysis; D3 grounding), ADR-0033
  (idiom-over-prose lesson), ADR-0034 (analysis-intent conduit), ADR-0035
  (saved re-runnable analysis code)
- Spec: `docs/specs/model-authored-analysis.md` §2 (the rules this rewrites)
- Evidence: `evals/crossmath_frame_keying_gate.py` +
  `evals/prompts/crossmath_frame_keying_results.json` (the KeyError class),
  `evals/repair_intent_retention_gate.py` (the negative result that redirected
  (B) to fix-rate), `evals/e2e_runs/20260711T194126Z/REPORT.md` (e2e-18 FAIL,
  the residual member), worker logs 2026-07-07..11 (the runtime_error ledger)
