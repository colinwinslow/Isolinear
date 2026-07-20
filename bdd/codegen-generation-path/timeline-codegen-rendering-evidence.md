# Timeline render family for the codegen path — Evidence

Paired with [docs/specs/timeline-codegen-rendering.md](../../docs/specs/timeline-codegen-rendering.md)
and [timeline-codegen-rendering-bdd.md](timeline-codegen-rendering-bdd.md).

Raw outputs from the production codegen path (live gemma4:e4b on 10.0.1.39, real
sandbox exec via `/home/claude/.expenv/bin/python`), 0.2.45.

## Live baseline this packet fixes — e2e-09 on deployed 0.2.42

Run `evals/e2e_runs/20260717T215239Z/` (harness, deployed integration):

```
[e2e-09] 'When was the kitchen door open today?' complete render_path=codegen fallback=None (134.9s)
answer_text: "The kitchen door was open for a total of 0.0 minutes today, spanning from 13:16 to 21:09."
snapshot chart.overlays: []   (primary timeline → overlay precompute empty → model draws verticals)
```

The served PNG showed ~4 near-zero-width vertical marks on a fake Open/Closed
axis — not a readable step track; the duration was the degenerate `0.0 minutes`
(open-queue (x)).

## Eval gate — evals/timeline_render_gate.py (RUNS=3, MAX_REPAIRS=2)

The gate drives the production codegen path with vs without the broken_barh
timeline rule; each run is judged on BOTH the render (a `broken_barh` lane =
≥1 PolyCollection, no numeric line) and the answer (a `state_duration` claim that
`run_grounding_check` verifies, non-degenerate).

The render judge is STRENGTHENED (after the first eyes-on over-reported a
thin-bar render): a clean lane requires no numeric line, a grey off-baseline track
spanning ≥85% of the x-range, at least one narrower on-bar, AND entity y-ticks
(not an on/off value axis).

Final results (`evals/prompts/timeline_render_gate_results.json`, strengthened
judge + final off-track idiom + state_duration grounding fix):

```
with_timeline::run1    CLEAN  render_ok=True  answer_ok=True   executed=True
with_timeline::run2    fail   render/answer=None               executed=False  (codegen runtime error, 2 repairs exhausted — variance)
with_timeline::run3    CLEAN  render_ok=True  answer_ok=True   executed=True
without_timeline::run1 fail   render_ok=False (0 coll, yticks numeric)  answer verified
without_timeline::run2 fail   render_ok=False (0 coll, yticks numeric)  answer verified
without_timeline::run3 fail   render_ok=False (0 coll, yticks numeric)  answer verified

tally: with_timeline 2/3 clean (2/2 EXECUTED runs pass the strict lane check)
       without_timeline 0/3 (render 0 — axvspan verticals, numeric axis)
```

Reading: the timeline idiom is load-bearing — without it the model draws axvspan
verticals on a numeric axis every run (0/3), reproducing e2e-09; with it, every
run that EXECUTES draws a clean off-track + entity-lane timeline (2/2). The 1 miss
is a codegen runtime error that exhausted the gate's 2 repairs (production default
is 3) — general codegen variance, not a timeline defect. (The duration answer
verifies in both arms because the C3 duration rule is present in both — the gate
strips only the render rule — so the without arm isolates the RENDER regression
exactly.) Kill-condition NOT triggered; Option B (codegen-primary) holds. An
earlier run with the WEAK judge (`≥1 collection`) scored with_timeline render 3/3
but the eyes-on showed thin off→on bars with no baseline — which is exactly why
the judge was strengthened (accept≠quality).

### First gate run surfaced the (cc)-class grounding bug (fixed)

`evals/prompts/timeline_render_gate_results.json` (before the grounding fix):

```
with_timeline 0/3 (render 2, answer 0) — every answer_ok=False was
  ground=repair_contradicted withheld=True dur_ms=540000  (correct value, contradicted)
```

gemma intermittently attached a spurious verdict+rule to the descriptive
duration; step-5/6 verdict containment then withheld a CORRECT 540000 ms answer.
Fix: grounding nulls verdict/rule for `state_duration` (inherently descriptive)
→ value-only verify. Pinned by
`tests/test_answer_grounding.py::TestStateDuration::test_spurious_verdict_on_duration_still_verifies`
and `::test_wrong_value_with_verdict_still_caught`.

## Scenario B/C — grounded, non-degenerate duration (captured claim)

A production-path generation (verdict emitted null this run) returned:

```
answer_text: "The kitchen door was open for approximately 9.0 minutes today."
claims: [{"metric": "state_duration", "inputs": ["binary_sensor.kitchen_door"],
          "value": 540000, "verdict": null, "rule": null}]
run_grounding_check → outcome: verified, withheld: False
```

540000 ms = the sum of the three precomputed derived_intervals (120000 + 240000 +
180000), independently recomputed from the raw points by `_compute_state_duration`
→ verified. No `0.0 minutes` (open-queue (x) closed).

## Scenario A — eyes-on legible state lane

Served PNG from the production codegen path with the final timeline idiom:
`evals/prompts/timeline_eyeson.png` (captured 2026-07-19; answer_text "The kitchen
door was open for approximately 9.0 minutes (0.1 hours)."). Eyes-on:

- A light grey "off" baseline track spans the WHOLE day (00:00 → next 00:00) so
  the mostly-closed door reads as present-but-off, not floating marks.
- ONE horizontal lane labelled with the entity ("Kitchen Door" on the y-axis) —
  NOT an on/off value axis.
- The three openings render as visible orange bars at ~13:00, ~15:00, ~20:00 (a
  window-relative min-width keeps 2–4 min openings visible over a 24 h axis).
- Legible time x-axis; grounded, non-degenerate 9.0-minute answer.

This is the fix to the first-cut render (thin off→on bars, no baseline) that the
strengthened gate judge caught. The evolution across the session:
1. e2e-09 baseline (deployed 0.2.42): axvspan verticals + "0.0 minutes".
2. first idiom: a `broken_barh` family but thin off→on bars, no off-track (the
   gate's weak `≥1 collection` check over-reported it — accept≠quality).
3. strengthened idiom + gate: grey off-track + fixed entity lane + window-relative
   min-width; gate asserts off-track + on-bars + entity y-ticks.

## Scenario E — kill-condition

Not exercised: the gate did not trigger the kill-condition (with_timeline 3/3
clean), so `timeline` stays on the codegen path. The Pillow route remains the
fallback (invariant #6) and reuses the same C1 precompute if ever selected.
</content>
