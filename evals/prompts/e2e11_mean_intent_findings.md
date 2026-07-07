# e2e-11 mean-intent diagnosis (open-queue (z)) — findings

**Date:** 2026-07-07 (20th session). **Repro:** `scripts/repro_e2e11.py`
(production `generate_chart_code`/`repair_chart_code`, live gemma4:e4b,
execution-truth classification of every generation).

## The symptom

Live e2e run 20260706T205049Z (0.2.24): "What is the average of the kitchen and
basement temperatures over the last day?" rendered BOTH raw series plus a flat
scalar "Average Temperature" `axhline` and returned NULL `answer_text` — where
the 17th-session run (0.2.23, 20260706T172905Z) had plotted a (spiky
union-index) mean SERIES and answered "72.13 °F". Judged PARTIAL; queued as (z)
with the question "why does the model draw a scalar line, not a mean series?"

## What was tested (all against live gemma, production codegen path)

| Arm | Data | Rules | Result |
|---|---|---|---|
| gate title ("Average of…") | synthetic 7 °F-apart | current | 2/2 mean series + answer |
| live title ("… Temperature History") | synthetic | current | 3/3 mean series + answer |
| live title + live summary ("…trends…") | synthetic | current | 3/3 mean series (1 run lost answer_text after TWO repairs) |
| live title + summary | REAL HA 24 h history (means 1.4 °F apart) | current (0.2.26+) | 3/3 mean series + answer, first attempt |
| live title + summary | REAL HA history | **0.2.24** (family-degrade rule stripped, marker-gated) | 3/3 mean series + answer — but **3/3 needed a repair** |

The live planner (phase 1, 2 near-greedy samples) emits exactly the raw-history
framing seen live: title "Kitchen and Basement Temperature History", summary
"…temperature trends…", two raw series — so planner framing was faithfully
reproduced and did NOT flip codegen to a scalar.

## Conclusions

1. **The scalar-line render is not structural — it is a temperature-0 variance
   basin.** Across 14 executed generations spanning both rule sets, synthetic
   and real data, and all planner-framing arms, ZERO produced the scalar line.
   The mode is a true computed mean series (real data: mean 72.48 °F, std 0.38
   — between the raw bands) plus a grounded `answer_text`. The live render was
   one unlucky sample.

2. **The plausible live mechanism is repair-chain intent erosion.** The live
   run took 191 s (repair-consistent; Colin's box runs
   `max_codegen_repair_attempts=3`), and under the 0.2.24 rules every real-data
   first attempt hit a repairable runtime slip. Observed once directly
   (synthetic, two-repair chain): the repaired code KEPT the mean series but
   DROPPED `answer_text` — the repair task refocuses the model on the error and
   the analysis intent erodes, one element per rewrite. A deeper live chain
   plausibly eroded the mean series to raw-lines + scalar annotation before
   converging. The repair prompt already says "still fulfills user_request";
   saying it is not the same as weighting it.

3. **The 0.2.26 family-degrade rule incidentally improved this prompt's
   first-attempt reliability** (real data: 3/3 first-attempt with it vs 0/3
   without it — small N, but consistent with its explicit "user_request may
   change WHAT is computed" cue reinforcing the compute path).

4. **Gate hardening landed:** `evals/alignment_rule_gate.py`'s `derived_mean`
   judge had a scalar blind spot — a flat axhline at the combined mean (std ~0)
   passed `std <= max_std`. It now requires `std >= min_std` (default 0.5) and
   reports `SCALAR LINE` distinctly, so future alignment-gate runs cannot bless
   the e2e-11 failure mode.

## Recommended follow-up (not implemented — needs its own eval-gated packet)

A repair-intent-retention rule: the repair task should require the corrected
code to preserve every computed/derived series and the `answer_text` emission
from the previous attempt (fixing the error must never remove the analysis).
Gate it like 0.2.26: drive `repair_chart_code` on a mean-series generation with
an injected runtime error, with/without the rule, judge whether the repaired
code retains the computed series + answer. Expected to close both the observed
answer_text erosion and the live raw+scalar terminal state. Until then, (z) is
**likely-fixed in the mode** on 0.2.26+ — confirm on the next live e2e run
before closing.
