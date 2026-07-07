# e2e-15 heatmap diagnosis — open-queue (w) findings

**Date:** 2026-07-06 (19th session). **Model:** gemma4:e4b (temp 0) on CT103.
**Repros:** `scripts/repro_e2e15_planner.py` (planner stage),
`scripts/repro_e2e15.py` (production codegen path, both chart-family arms;
artifacts in gitignored `evals/e2e_runs/repro_e2e15*/`).

## The live failure

18th-session live run (`evals/e2e_runs/20260706T205049Z`, 0.2.24): e2e-15
"Show a heatmap of the kitchen temperature by hour of day and day over the
last week" rendered nonsense — y-axis "Temperature (°F)" spanning 0–2 with
alternating 1/2 bars, x-axis raw epoch-ms, no colour grid, title "Kitchen
Temperature Distribution Over the Last Week". Codegen accepted it (no
fallback): a hard accept≠quality repro. The 17th-session run (0.2.23) instead
exhausted repairs → Pillow fallback (`runtime_error`). Same root, two surfaces.

## Root cause — two stacked failures

### 1. The planner deterministically mis-routes heatmap prompts to `histogram`

The single-numeric ADR-0023 envelope offers `[time_series, histogram,
aggregate_bar]` — there is no heatmap family, and the envelope's
chart_type_rule glosses histogram as "for value distributions". The planner
reads "heatmap … by hour of day and day" as distribution-flavoured and picks
**histogram 6/6 samples**, emitting the exact title seen on the live garbage
render ("Kitchen Temperature Distribution Over the Last Week") plus
`render_as: histogram`, `x_axis {type: value, bin_count: 8}`.

Codegen then receives a chart_spec whose intent ("implement the supplied
chart_spec": a histogram) fights `user_request` ("fulfill user_request: a
heatmap by hour and day"). The conflicted output varies by sample but is
consistently NOT the asked-for temperature heatmap — live it was count-shaped
1/2 bars against epoch-ms; the repro arm produced a frequency 2D histogram
(temperature bins × day, colorbar "Frequency (Count)", y-label "Time (Day)
(°F)"). Note e2e-16 ("show the distribution…") PASSES with the same histogram
spec — the failure needs the conflict, not the family.

### 2. Under an unconflicted spec, codegen attempts a REAL heatmap but is
### killed by one near-deterministic bad emission

The counterfactual arm (time_series chart_spec, same stats-tier data, same
user_request) shows gemma **has the capability**: it writes
`groupby([dayofweek, hour]).mean()` → `unstack` → `sns.heatmap`, and run 3
produced a genuinely correct 24×7 heatmap (proper diurnal gradient, °F
colorbar; PNG in the repro dir).

But 2 of 3 runs died on **the same character-level emission**: a dead-code
"data not found" guard containing `transform=ax.transAxes')` — a stray quote
→ `syntax_error`, re-emitted every repair attempt (6/6 attempts across both
runs; temp-0 emissions are near-deterministic, so the repair loop regenerates
its own bug). A secondary systematic slip: `unstack(level=0)` followed by
`reindex(index=range(7), columns=range(24))` — transposed orientation (rows
are hours after `unstack(level=0)`), which would render a wrong-but-plausible
grid if the syntax bug were absent.

Venv fidelity note: run 3's only failure was `resample('H')` under the exec
venv's pandas 3.x; the worker pins pandas 2.x where 'H' is accepted, so that
run would have been a FIRST-ATTEMPT live success.

## Why this is structural, not model variance

- Planner mis-route: deterministic (6/6).
- Codegen bad emission: near-deterministic at temp 0; repair cannot fix a
  character it cannot see and regenerates the same pattern. More repair budget
  (open-queue (m)) does NOT help this class.
- The successful sample differs precisely by NOT emitting the guard-branch
  preamble — the failure is a memorized code pattern, displaceable by a
  prescribed idiom (the ADR-0033 axvspan / 0.2.24 alignment-idiom lesson).

## Decision (2026-07-07, Colin — "ship simple") + fix SHIPPED (0.2.26)

Two fixes were on the table: (A) render a real temporal heatmap (planner routes
heatmap→`time_series`, codegen pivots + draws via `seaborn.heatmap` — pre-
validated: the planner-routing patch flipped 3/3, `scripts/repro_e2e15_planner_fix.py`);
or (B) degrade the heatmap ask to the histogram the planner already picks.
Colin chose **B** — the niche temporal heatmap isn't worth the codegen pivot
idiom + risk, and B keeps the WORD "heatmap" reserved for the future spatial /
floorplan renderer (open-queue (c)). A temporal calendar heatmap, if ever
built, becomes its own NAMED family, not an overload of "heatmap".

**The frame that made B one rule, not three:** the bug isn't "wrong viz" — it's
codegen overriding the planner's chart FAMILY via the ADR-0034 `user_request`
conduit, which violates invariant #9 (the model never chooses `chart_type`).
Chart family is the planner's job; `user_request` drives the COMPUTATION within
it. A heatmap is a family, so codegen must not invent one.

**Shipped (0.2.26):** one `_CODEGEN_PROMPT_RULES` sentence — render only
line/histogram/bar; never draw a 2-D heatmap/matrix/grid (no `seaborn.heatmap`,
`pcolormesh`, `imshow`, `hist2d`); a single-sensor "heatmap by hour and day"
degrades to a histogram of the sensor's values; `user_request` may change WHAT
is computed, never the family. No planner change (it already routes to
histogram 6/6), no Pillow heatmap, no new ADR (reinforces invariant #9);
spec `model-authored-analysis` §2 updated; regression test
`FamilyDegradePromptRuleTests`. Eval-gated with `evals/heatmap_rule_gate.py`
(production codegen path, live histogram chart_spec + heatmap `user_request`,
with/without the sentence, execution-truth judge = a clean 1-D histogram, not a
2-D `QuadMesh`/image).

**Gate result (2026-07-07, live gemma4:e4b):** `with_degrade` **3/3 clean
histograms** (8 bins, x-range 67.6–75.4 °F, first attempt each);
`without_degrade` **0/3** — all three drew a 2-D grid (`n_collections=1`), the
live e2e-15 failure reproduced. The rule closes the gap deterministically.

Known limitation (logged, not solved): a MULTI-sensor "heatmap of correlations"
goes through the `time_series` envelope and degrades to multi-line series, not
a histogram — coherent, weaker; acceptable by the coherent-degrade bar.

## Histogram-arm repro (live-condition confirmation)

3 runs under the live planner's exact histogram chart_spec (title, render_as,
`x_axis {type: value, bin_count: 8}`), same data + user_request:

| run | attempt-0 failure | final render |
|---|---|---|
| 1 | `TimedeltaIndex has no attribute 'dt'` (real bug) | **WRONG** — 2D frequency histogram: 8 temperature bins (the spec's bin_count!) × day, colorbar "Frequency (Count)", y-label "Time (Day) (°F)" |
| 2 | `Invalid frequency: H` (repro-venv pandas 3.x only) | **CORRECT** hour×date temperature heatmap |
| 3 | `Invalid frequency: H` (repro-venv only) | **CORRECT** hour×date temperature heatmap |

The conflicted spec turns the outcome into per-sample roulette spanning
perfect → wrong-flavoured grid → (live 0.2.24) accepted 1/2-bar nonsense →
(live 0.2.23) repair exhaustion. Run 1's render is the conflict made visible:
it honours the histogram spec's bin_count AND the heatmap request's 2D grid in
one blended wrong chart. Caveat: repro data is a clean synthetic sine; the
live 1/2-bars flavour likely needs real-data warts — the attribution rests on
the planner title match plus the conflict mechanism, not a byte repro.

## Proposed-fix pre-validation

`scripts/repro_e2e15_planner_fix.py` patches ONLY the envelope chart_type_rule
sentence (payload-level monkeypatch, no production change) with the proposed
heatmap→time_series routing clause: **3/3 samples flip to `chart_type:
time_series`** (baseline 6/6 histogram), title "Kitchen Temperature Over the
Last Week". The planner half of the fix is pre-validated; the codegen idiom
half needs the gate eval (`evals/heatmap_rule_gate.py`, to be built with the
fix packet) to prove the pivot idiom displaces the stray-quote emission.
