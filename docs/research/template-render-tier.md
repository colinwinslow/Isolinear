---
title: Template render tier for small models
status: open
date: 2026-08-07
---

# Research: Template render tier for small models

## Question

Should Isolinear add a **third render tier** — canned matplotlib templates where
the model only *selects* which series feed which template — sitting between the
trusted Pillow fallback and freeform sandboxed codegen? And if so, is it a
capability tier keyed to the configured model, or a universal preference?

## Context

Colin's proposal (2026-08-07): "what if we had canned matplotlib code for common
graph types and all the model really does is pick which sensor data to plug into
a template. I bet that would let us avoid repair altogether a lot of the time,
and we could still fall back to freeform code generation if the user asks for
something that doesn't neatly fit into a template."

Two things must be said plainly up front, because they shape the whole question:

**1. This architecture already exists here — it is the path ADR-0030 demoted.**
ChartSpec + the trusted Pillow renderer *is* "model selects, deterministic code
renders": a schema-validated selection, deterministic rendering, and no repair
loop because there is nothing to repair. ADR-0030 demoted it not because it
failed but because it hit a ceiling — no computed analysis, no grounded answers,
Pillow-grade output. So the real proposal is **re-widening the deterministic
tier with matplotlib templates instead of Pillow primitives**, and it should be
argued as that. A third render path also requires an ADR under invariant #8.

**2. The evidence that motivated it has since been explained away.** The 7 stable
e2e failures were a *prompt-truncation bug* (repair prompts pinned at
`prompt_eval_count == 8192`), not a model-capability ceiling. 0.2.48 pruned the
repair rules and the stable-7 went **0/7 → 6/7** with no architectural change,
and `unsafe_code` vanished across 42 post-fix prompts. Attempt-1 code was real
code with real bugs all along. The strongest version of the motivating argument
is therefore gone; what remains is aesthetics, variance, and cost.

## What still argues FOR it

- **The failure asymmetry is real and matches the proposal exactly.** Across all
  four e2e runs the *planner* — constrained JSON against a schema — essentially
  never failed. Every failure was freeform code authoring under pressure. Small
  models are good pickers and fragile authors.
- **Repair is the expensive, fragile step.** Templates remove it entirely for
  covered prompts: no repair budget, no truncation risk, no static-gate
  round-trips, and a large latency win (repair-heavy prompts ran 137–290s vs
  55–95s for clean first-attempt ones).
- **Determinism.** A template tier would flatten the measured ~26% run-to-run
  flip rate for the prompts it covers, which is independently valuable — the
  suite's noise is currently a research obstacle in its own right.

## What argues AGAINST it

- **The prompts that actually fail are the analysis prompts** — correlation,
  deviation, comparison, overlay. Templating those means canning the *compute*,
  not just the plot, which is a much larger surface than "common graph types".
- **It reverses two standing directions**, and an ADR would need to say so
  explicitly rather than quietly: ADR-0035's north star ("the product is saved,
  re-runnable, model-authored analysis code") and Colin's standing steer toward
  model+hints over hard-coded determinism.
- **Template coverage is a treadmill.** Every new ask either fits a template or
  falls through to codegen; the fallback path must stay first-class anyway, so
  this adds a tier rather than replacing one.
- **ADR-0035 step 4 is already committed to *retiring* deterministic families**
  (Pillow histogram/aggregate_bar) once codegen covers them. A template tier
  pushes directly against that sequencing and would need to be reconciled with
  it, not bolted alongside.

## The interesting variant

The sharpest form of the idea is not "canned plots" but **canned compute**: the
grounding recomputes (`_compute_mean`, `_compute_delta`, `_compute_pearson_r`,
`_compute_state_duration` in `answer_grounding.py`) are already trusted,
deterministic implementations of exactly the metrics the analysis prompts ask
for. If those ran as the *primary* computation for covered metrics, with a
template rendering the result, then **the answer is verified by construction** —
the whole emission / claims / withhold / repair-on-grounding-failure machinery
collapses for that tier, along with the claimless-answer trap (a served,
unchecked, wrong number) that has bitten repeatedly.

That is a genuinely different product shape, not an optimization, and it is the
version worth writing an ADR about if this proceeds.

## Open sub-questions

- Which families/metrics would templates cover, and what fraction of real asks
  is that? (The e2e set is the wrong sample — it is deliberately adversarial.)
- Tier selection: keyed on the configured model, on a capability probe, on
  prompt classification, or user-selectable like `render_path`?
- How does a template tier interact with ADR-0035 step 4's retirement plan?
- If canned compute runs primary, what does grounding check *against* — does it
  become a no-op for that tier, or does it re-verify independently?
- Does the model still author the *answer sentence* (prose) over a canned
  number, or is that templated too? (Prose templating is where this would most
  visibly feel less capable.)

## Resolution

Open. **Deliberately parked pending evidence** — re-run the suite on a clean
0.2.48+ build and look at eventual success on the always-fail set. If failures
persist without a truncation explanation, this is the right shape and earns its
ADR. If they do not, the remaining case is aesthetics and variance, which is a
weaker basis for a third render path. Tracked as ROADMAP (kk).
