# Timeline render family for the codegen path — BDD

## Status

Draft. Paired with [docs/specs/timeline-codegen-rendering.md](../../docs/specs/timeline-codegen-rendering.md).

## Why this BDD exists

Pins down that a binary/categorical entity charted on its own through the codegen
render path produces a legible state **step track** (not near-zero-width
verticals) and a **grounded, non-degenerate duration answer** — replacing the
e2e-09 accept≠quality behavior on the deployed 0.2.42. Subsumes open-queue (x)
(door zero-duration intervals).

## Scenarios

### Scenario A — happy path: a standalone door timeline renders a legible step track

**Given** an approved binary entity `binary_sensor.kitchen_door` that opened a few
times today, resolved to the `timeline` family (invariant #9), rendered via codegen
**When** the user asks "When was the kitchen door open today?"
**Then** the served PNG shows a `broken_barh` "Open" lane over an off-track across
today's window (the open spans are visible as filled bars, not zero-width
verticals), and `render_path` is `codegen` with no fallback — inspectable as the
captured PNG in the run directory.

### Scenario B — the duration answer is deterministic and non-degenerate

**Given** the same request
**When** codegen builds the answer
**Then** `answer_text` reports the integration-precomputed `total_on_ms`
(formatted, e.g. "open for 6 minutes across 4 openings"), never the model's own
count — so the 0.0-minutes class (open-queue (x)) cannot recur — and the reported
duration equals the sum of the drawn bands' spans.

### Scenario C — the duration answer is grounded (independent recompute)

**Given** a codegen `state_duration` value claim over `binary_sensor.kitchen_door`
**When** the grounding check runs
**Then** `_compute_state_duration` recomputes the total active-state milliseconds
from the raw binary points independently; a value within tolerance is served as
`verified`, and a claim whose stated value is wrong (does not match the independent
recompute) is **withheld** — proven by a wrong-value guard test that stays
load-bearing.

### Scenario D — empty timeline: present-but-off, not blank

**Given** a binary entity that never turned on within the window
**When** the timeline is rendered via codegen
**Then** `derived_intervals` is empty and the PNG shows a labeled off-track across
the window (present-but-off), not a blank axis, and the duration answer reports
zero on-time explicitly (a true zero, distinct from the (x) degenerate 0.0).

### Scenario E — kill-condition fallback (only if the eval gate fails)

**Given** the `evals/timeline_render_gate.py` gate shows the floor model cannot
reliably draw the broken_barh lane even with precomputed intervals
**When** a `timeline`-family chart is dispatched
**Then** `render_dispatch` routes it deterministically to the Pillow renderer,
surfaced via `render_path` (Option A), reusing the C1 precompute unchanged — the
negative eval result is recorded as the justification.

## Evidence

The implementing slice produces an evidence file at
`bdd/codegen-generation-path/timeline-codegen-rendering-evidence.md` containing raw
outputs (not summaries) for each scenario: the served PNG path, the `answer_text`
and `answer_verification` from the live run, the grounding recompute values, and
the eval-gate with/without arm results.
</content>
