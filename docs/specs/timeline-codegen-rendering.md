---
status: accepted
date: 2026-07-18
depends-on-adrs: [0022, 0030, 0031, 0033, 0034]
---

# Timeline render family for the codegen path (state step track + grounded duration)

## Status

Accepted (2026-07-20 — Scenario A confirmed live on the deployed 0.2.45; see
the paired evidence file). Extends the deterministic render-family routing (invariant #9, ADR-0022)
and the integration-precomputes-intervals pattern (ADR-0033) to the **codegen**
render path (ADR-0030) for a **primary** binary/categorical `timeline` series,
and grounds the accompanying duration answer (ADR-0031 D8a). Scope: a chart whose
resolved primary entity routes to the `timeline` family (a door, occupancy, HVAC
mode) and is rendered through codegen, not as an overlay on a numeric chart.

## Related docs

- [render-family-capability-envelope.md](render-family-capability-envelope.md) — the family routing this timeline path plugs into (invariant #9)
- [card-level-legend-codegen.md](card-level-legend-codegen.md) — the sibling codegen render-path spec this mirrors (ADR-0033 precompute pattern)
- [model-authored-analysis.md](model-authored-analysis.md) — the codegen return/prompt contract (ADR-0034) this adds a timeline idiom to
- [answer-grounding-check.md](answer-grounding-check.md) — §5 compute-claim registry this adds a `state_duration` claim to (ADR-0031 D8a)
- [bdd/codegen-generation-path/timeline-codegen-rendering-bdd.md](../../bdd/codegen-generation-path/timeline-codegen-rendering-bdd.md) — observable behavior
- [STATUS.md](../../STATUS.md) — current phase and active work (open-queue (r), and (x) which this subsumes)

## Context

Invariant #9 deterministically routes a binary/categorical entity to the
`timeline` family (`chart_type: "timeline"`, `render_as: "step"`). The **Pillow**
fallback renders it correctly — `in_process_renderer._render_timeline_png` draws
one lane per entity with a light "off" background track and `_binary_on_regions`
filled on top, over the correct window. The **codegen** path — primary since
ADR-0030 — has no timeline handling at all: `render_dispatch.py` never branches on
`chart_type == "timeline"`.

Live e2e-09 on the deployed 0.2.42 (run `evals/e2e_runs/20260717T215239Z/`,
"When was the kitchen door open today?") establishes the real current behavior —
it is neither empty nor a clean step track, it is **accept≠quality**:

- `render_path=codegen`, no fallback (it does not error, so it serves).
- The PNG shows a fake `Open`/`Closed` y-axis with ~4 **near-zero-width vertical
  marks** where the door opened. You cannot read *when* or *for how long* the door
  was open.
- The answer is degenerate: *"The kitchen door was open for a total of **0.0
  minutes** today, spanning from 13:16 to 21:09."* — this is also open-queue (x)
  (door zero-duration intervals).

Root mechanism, confirmed from the snapshot (`overlays: []`): a primary timeline
series is not an overlay, so `_compute_overlay_bands` (which iterates
`chart_spec["overlays"]`) hands codegen **empty `derived_intervals`**. The model
is then forced to derive on-regions from raw binary points itself — exactly what
the prompt forbids for numeric data and gives no idiom for — so it draws
instantaneous `axvspan` verticals and botches the duration. It even mislabels the
legend `kind: "overlay"` because "binary = a shaded band" is the only binary idiom
the codegen prompt provides.

The fix generalizes ADR-0033: the integration precomputes the state intervals
(and the total duration) with the trusted Pillow region logic and hands them to
codegen ready to draw and ready to state, so the floor model's residual job is
near-cosmetic. This preserves codegen as primary (keeping the grounded duration
answer the product vision wants), with a kill-condition to route `timeline` →
Pillow if the model cannot reliably draw the lane.

## Behavior contract

### C1 — Primary-timeline interval precompute (`derived_intervals`)

`render_dispatch` computes `derived_intervals` for a **primary** timeline series,
not only for overlays. When `chart_spec["chart_type"] == "timeline"`, for each
series whose `history_series[i].kind` is `binary_state` or `categorical_state`,
emit `{start_ms, end_ms, color, label, entity_id}` bands for the "on"/active
regions, reusing the trusted `_binary_on_regions` / `_categorical_overlay_states`
region logic (the exact functions Pillow's `_render_timeline_png` uses). Binary →
one color across the active set; categorical → one color per distinct state.

The band shape is identical to the overlay bands (`_overlay_band`), so the
downstream contract is unchanged. The precompute is additive: overlay bands are
still computed for numeric charts; the timeline branch fires only when the chart
family is `timeline`.

### C2 — Codegen prompt idiom: draw a step track, not verticals

`_CODEGEN_PROMPT_RULES` gains a timeline-family idiom (mirroring the ADR-0033
axvspan rule): when the chart is a `timeline`, draw a **`ax.broken_barh`** "on"
lane per entity from `data['derived_intervals']` (converting `start_ms`/`end_ms`
via `pandas.to_datetime(..., unit='ms')`), with an off-vs-on categorical y-axis;
never draw a numeric line and never derive regions from raw points. If
`derived_intervals` is empty for a timeline, draw an empty-but-labeled off track
over the window (present-but-off, matching Pillow), not a blank axis.

### C3 — Total on-duration summed from the precomputed intervals

The e2e-09 `0.0 minutes` bug was the model deriving intervals from **raw binary
points** badly, then summing near-zero spans. With C1 handing over correct
intervals, the fix is a prompt rule: for a timeline duration question, the model
computes the total on-time by **summing `(band['end_ms'] - band['start_ms'])` over
`data['derived_intervals']`** for the entity (precomputed and correct — never count
raw points), and reports it in `answer_text`.

> **Deviation from the draft (2026-07-19):** the draft handed a precomputed
> `data['timeline_summary']` scalar as a new render-request field. The
> render-request schema is `additionalProperties: false`, so that new input field
> would require editing the worker's bundled schema copy and **rebuilding the
> worker image**. Summing the already-precomputed `derived_intervals` (a trivial
> for-loop over correct handed numbers — not raw-point derivation, which was the
> actual bug) removes the deployment cost and keeps C3 integration-only. The
> duration is still grounded by C4's independent recompute.

### C4 — Grounded duration claim (`state_duration`)

The duration answer is grounded like any other computed value (ADR-0031 D8a). A
new compute type `state_duration` is added to the `answer_grounding` registry
(mirroring `_compute_hours_above`): `_compute_state_duration(inputs, window,
params, hs)` recomputes the total active-state milliseconds from the raw points
**independently** (grounding stays a drift-detector — it does not trust the summed
`derived_intervals`). It mirrors C1's window semantics: a still-active FINAL
segment is held to the global window end (the latest ts across all delivered
series), matching `_binary_on_regions`, so a multi-entity timeline does not
undercount a trailing on-state. The model emits a value claim
(`metric: "state_duration"`, `inputs: [<entity_id>]`, `value: <total on-ms>`,
`params: {active: [...]}`); a mismatch beyond tolerance withholds the answer,
exactly as for `mean`.

Two grounding-policy points (both surfaced/hardened by the eval gate):

- **Metric-aware tolerance.** `state_duration` values are milliseconds — the fixed
  `_TOLERANCE = 0.05` (tuned for °F-scale values) is meaningless there and a
  readable-rounded answer would falsely mismatch. `_value_tolerance` returns a
  relative tolerance (2% or 1 minute, whichever larger) for `state_duration` and
  the unchanged absolute `_TOLERANCE` for every other metric.
- **`state_duration` is a descriptive (value-only) metric class.** A duration
  ("how long was it open?") has no yes/no judgment, but gemma intermittently
  attaches a spurious verdict+rule anyway (gate: a correct 540 000 ms →
  `repair_contradicted`). `_check_claim` therefore nulls any verdict/rule on a
  `state_duration` claim and value-verifies it (the (cc) precedent). This does NOT
  weaken grounding: step-4 recompute still contradicts a wrong value regardless of
  verdict (pinned by a wrong-value-with-verdict guard test).

> **Decision-shaped (arch-review flag, 2026-07-19):** treating a whole metric
> class as descriptive-only inside `_check_claim` is a grounding-policy precedent
> future metrics may cite. Recorded here per Colin's "just a spec" call for this
> packet; if the pattern recurs it is worth promoting to an ADR
> (`value-only-metric-classes-in-grounding`).

### C5 — Legend

The state lane reuses the existing `kind: "overlay"` legend entry (a shaded state
region). Adding a distinct `timeline` legend kind is a **non-goal** here (it would
touch all seven schema copies for cosmetic gain); the legend fix already shipped
in 0.2.42 populates the row.

### Kill-condition

If the C3 eval gate (below) shows the floor model cannot reliably draw the
broken_barh lane even with precomputed intervals, fall back to **Option A**:
deterministically route a `timeline`-family chart to the Pillow renderer
(`render_dispatch` selects Pillow when `chart_type == "timeline"`), surfaced via
`render_path`, accepting the loss of the model-authored duration answer. The C1
precompute is reused unchanged by Pillow, so this fallback is cheap.

## Anchor artifact

One live codegen render of "When was the kitchen door open today?" that draws a
legible `broken_barh` "Open" lane over an off-track across today's window (not
near-zero verticals) **and** returns a non-degenerate, grounded duration answer
(e.g. "open for 6 minutes across 4 openings"), captured to an `evals/e2e_runs/`
run and eyes-on confirmed. Built before the categorical extension and before the
grounding claim is wired to every caller.

## Implementation order

1. **C1 precompute** (`render_dispatch`) — timeline-family branch reusing
   `_binary_on_regions`; unit tests that a primary door timeline yields non-empty
   `derived_intervals` matching the Pillow regions byte-for-byte.
2. **C2 prompt idiom** — the broken_barh timeline rule; the anchor render eyes-on.
3. **C3 duration precompute + prompt rule** (`timeline_summary`).
4. **C4 grounding** — `_compute_state_duration` + registry entry + the value-claim
   prompt rule; grounding unit tests (correct → verified; wrong handed value still
   caught).
5. **Eval gate** — `evals/timeline_render_gate.py`, production codegen path, live
   gemma, with/without the timeline idiom, execution-truth judge (drew a
   broken_barh lane? duration non-degenerate AND grounding-verified?). This is the
   keep/kill data for the primary-codegen approach vs the Pillow route.

## Proof requirements

1. Unit tests green: C1 primary-timeline precompute (binary + categorical) matches
   Pillow regions; C4 `_compute_state_duration` recompute (correct-value verified,
   wrong-value contradicted) in the `answer_grounding` tests.
2. `evals/timeline_render_gate.py` shows the with-idiom arm draws a broken_barh
   lane and serves a grounding-verified non-degenerate duration, vs the without
   arm reproducing the e2e-09 verticals + 0.0-minutes. (If it does not, the
   kill-condition triggers; record the negative result and route timeline→Pillow.)
3. BDD scenarios in `bdd/codegen-generation-path/timeline-codegen-rendering-bdd.md`
   pass; evidence file carries the served PNG + the grounded answer for the door
   anchor on the REAL pipeline.
4. Live e2e-09 re-run: legible step track + grounded non-zero duration, eyes-on.

## Non-goals

- A distinct `timeline` legend kind (C5 — cosmetic; reuse `overlay`).
- Multi-lane categorical *polish* beyond correct per-state segments (the binary
  door is the anchor; categorical HVAC-mode segments are in-scope for C1 but the
  eval anchor and eyes-on are binary).
- Timeline windows beyond recorder retention (invariant #9 — binary/categorical
  entities cannot be charted beyond retention).
- The >2-day state-overlay tiering wall (open-queue (t) / e2e-04) — a separate
  numeric-overlay concern.
- The spatial/floorplan heatmap renderer (open-queue (c)).

## References

- ADR-0022 (categorical timeline render family), ADR-0030 (codegen-primary),
  ADR-0033 (integration precomputes shaded intervals), ADR-0031 (grounded
  model-authored answers), ADR-0034 (user request reaches codegen).
- `custom_components/isolinear/in_process_renderer.py::_render_timeline_png` — the
  Pillow timeline renderer whose region logic C1 reuses.
- `custom_components/isolinear/render_dispatch.py::_compute_overlay_bands` — the
  overlay precompute C1 extends to primary timelines.
- `custom_components/isolinear/answer_grounding.py` — the compute-claim registry
  C4 adds `state_duration` to (mirrors `_compute_hours_above`).
- Live evidence: `evals/e2e_runs/20260717T215239Z/` (the e2e-09 accept≠quality
  repro this spec fixes).
</content>
