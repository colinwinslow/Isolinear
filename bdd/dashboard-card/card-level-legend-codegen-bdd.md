# Card-level legend for the codegen render path (+ computed kind) — BDD

## Status

Draft. Paired with [docs/specs/card-level-legend-codegen.md](../../docs/specs/card-level-legend-codegen.md).

## Why this BDD exists

Pins the user-visible behavior: a codegen chart that combines real sensors with a
model-computed series shows a card-level legend that distinguishes them — real
sensors solid, the computed series dashed and tagged `computed` — with no
redundant in-image legend, and never fails the render if the legend is missing.

## Scenarios

### Scenario A — happy path: a computed-average chart shows a three-row legend with a computed row

**Given** a codegen render for "the average of the kitchen and basement
temperatures" that plots two real sensor lines plus one computed cross-sensor
average
**When** the chart is served to the card
**Then** the served PNG has **no in-image `ax.legend()`**, the computed average is
drawn as a **dashed** line while the two sensors are **solid**, and the card shows
a **three-row** legend disclosure: two rows `kind: "series"` (Kitchen, Basement)
and one row `kind: "computed"` (Average) carrying a `computed` tag — inspectable in
`render_metadata.legend` (three entries, the computed one with a `#rrggbb` color
and no `states`) and on the rendered card.

### Scenario B — the codegen legend reaches the snapshot (parity with Pillow)

**Given** a worker `render_result` whose `render_metadata.legend` carries a
series row and a computed row (and a `summary` string)
**When** `_build_worker_artifact_metadata` builds the served artifact and the
snapshot is assembled
**Then** the artifact carries `legend` and `summary` (previously dropped by the
worker builder), and `snapshot.chart.legend` / `snapshot.chart.summary` deliver
them to the card unchanged — the same fields the Pillow builder already surfaces.

### Scenario C — computed vs overlay are distinct in the UI

**Given** two legend rows, one `kind: "computed"` (a dashed computed line) and one
`kind: "overlay"` (a shaded state band with `states`)
**When** the card renders the legend
**Then** the `computed` row shows a `computed` tag, a dashed/hollow swatch, and no
per-state child list; the `overlay` row shows an `overlay` tag, a split swatch,
and its per-state child list — the two are visually and semantically distinct.

### Scenario D — a missing legend never breaks the render (cosmetic-only)

**Given** a codegen chart whose generated `render_chart` returns no `legend` (or an
empty one)
**When** the chart is served
**Then** the chart and any grounded answer serve normally — no repair attempt is
triggered by the missing legend, the answer is not withheld — and the card shows no
legend section (graceful empty state), exactly as older artifacts do today.

## Evidence

The implementing slice produces an evidence file at
`bdd/dashboard-card/card-level-legend-codegen-evidence.md` containing raw outputs
(not summaries) for each scenario: the anchor chart's `render_metadata.legend`
JSON, the served PNG (in-image legend absent), the assembled `snapshot.chart`
legend/summary, the frontend render output for computed-vs-overlay rows, and a
missing-legend serve showing no repair/withhold.
