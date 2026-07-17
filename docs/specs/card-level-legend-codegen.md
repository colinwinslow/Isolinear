---
status: draft
date: 2026-07-17
depends-on-adrs: [0027, 0030, 0034, 0031]
---

# Card-level legend for the codegen render path (+ computed kind)

## Status

Draft. Extends the accepted card-legend contract
([card-legend-and-summary.md](card-legend-and-summary.md), ADR-0027 D1) to the
codegen render path (ADR-0030) and adds a third legend `kind` — `computed` — for
model-authored derived series. Scope: the codegen/worker render path for
multi-series `time_series`/`time_series_overlay` charts.

## Related docs

- [card-legend-and-summary.md](card-legend-and-summary.md) — the accepted Pillow-era legend contract this extends
- [model-authored-analysis.md](model-authored-analysis.md) — the codegen return contract (ADR-0034) this adds a field to
- [docs/research/codegen-card-level-legend.md](../research/codegen-card-level-legend.md) — the investigation that found the gap
- [bdd/dashboard-card/card-level-legend-codegen-bdd.md](../../bdd/dashboard-card/card-level-legend-codegen-bdd.md) — observable behavior
- [STATUS.md](../../STATUS.md) — current phase and active work

## Context

The card-level legend (ADR-0027 D1) — a rich disclosure list *outside* the plot,
one row per series/overlay with color swatch, entity id, alias, and state
breakdown — was wired end-to-end for the trusted Pillow renderer. Since codegen
became the primary render path (ADR-0030), that legend is never populated: the
codegen return contract never asks the model for a `legend`, and
`_build_worker_artifact_metadata` (`render_dispatch.py`) drops `legend` (and
`summary`) while its Pillow twin copies both. So codegen charts render with no
legend, or an inconsistent in-image `ax.legend()` the model adds ad hoc.

The frontend disclosure UI and the snapshot-assembly copy (`snapshot_assembly.py`)
are renderer-agnostic and already intact (`isolinear-card.ts:389+`); they are
simply never fed data by the codegen path. This spec feeds them.

Colin's liked convention (one live codegen chart happened to show it): **solid
lines for real sensors, a dashed line for a computed series** (e.g. the
cross-sensor average). The legend must surface that distinction consistently, not
per-model-whim. A model-computed series is a *line*, not a shaded state band, so
it needs its own legend kind rather than overloading `overlay` (which drives
band-specific UI — a state breakdown and an "overlay" tag).

## Behavior contract

### C1 — Codegen legend manifest (`render_chart` → `render_metadata.legend`)

For multi-series codegen charts, `render_chart` returns a `legend` array, one
entry per drawn line/band, reusing the accepted C1 shape
(card-legend-and-summary.md) with the `kind` enum extended to three values:

```
{
  "label": "<descriptive label>",
  "entity_id": "<entity id>",             // the computed series' primary input, or "" if none applies
  "color": "#rrggbb",                     // the EXACT hex the code passed to ax.plot(..., color=...)
  "kind": "series" | "overlay" | "computed",
  "states": [ ... ]                        // overlays only; omitted for series and computed
}
```

- `series` — a raw sensor line (drawn **solid**).
- `computed` — a model-authored derived series (cross-sensor mean, delta,
  deviation, rolling mean, …), drawn **dashed**. `states` is omitted (it is a
  line, not a band).
- `overlay` — a precomputed state band (from `derived_intervals`), with `states`,
  unchanged from C1.
- Order matches draw order; `color` is lower-case hex.
- **Single plain series** — the model returns `[]` (or omits `legend`); a one-line
  chart carries its identity in the title, matching dashboard convention. The
  legend earns its place on multi-series/computed/overlay charts.
- The colors are **self-reported by the model** — the same proven pattern it
  already uses for `series_plotted` and `answer_text` (metadata about code it just
  wrote). There is no integration-assigned palette on the codegen path (unlike
  Pillow's `_SERIES_COLORS`), and no post-hoc PNG inspection.

### C2 — In-image legend suppressed; line style encodes the distinction

The generated code does **not** call `ax.legend()` — the card-level legend
supersedes it (no redundant double legend). The in-plot distinction is carried by
**line style**: real sensors solid, computed series dashed (`linestyle="--"`).

### C3 — Schema: `computed` added to the `kind` enum (additive, both copies)

`legendItem.kind` gains `"computed"` in:
- `render-result.schema.json` → `render_metadata.legend.items.kind`
- `integration-job-snapshot.schema.json` → `$defs.legendItem.kind`

Both the `docs/schemas/` source copies and the bundled
`custom_components/isolinear/schemas/` runtime copies, kept byte-identical.
Purely additive: existing `series`/`overlay` records validate unchanged.

### C4 — Worker artifact parity (`render_dispatch.py`)

`_build_worker_artifact_metadata` copies `legend` and `summary` from
`render_metadata` onto the artifact when present and non-empty, matching
`_build_in_process_artifact_metadata` exactly. `snapshot_assembly.py` already
threads `artifact["legend"]`/`summary` into `snapshot.chart` renderer-agnostically
— unchanged.

### C5 — Card presentation: the `computed` row

`isolinear-card.ts` `renderLegendRow` gains a `computed` branch:
- a `computed` tag (distinct text from the existing `overlay` tag);
- a swatch styled to read as dashed/hollow, echoing the dashed-line convention;
- no `states` child list (computed is a line).

`series` rows are unchanged (plain swatch, no tag). `overlay` rows are unchanged
(split swatch + state children + `overlay` tag). Empty-legend degrades gracefully
(unchanged).

### C6 — Cosmetic-only: no enforcement, no repair, no withhold

A missing, incomplete, or color-mismatched legend is **not** a grounding or
static-safety failure. It never triggers the codegen repair loop, never withholds
the analysis answer, and never blocks serving the chart. The chart and answer
serve regardless; the legend is best-effort disclosure. Precedent: `series_plotted`
is self-reported and has always been unenforced. (Rationale: verifying reported
colors would require pixel-parsing the PNG — out of proportion to a cosmetic row.)

## Anchor artifact

A live codegen chart for "average of the kitchen and basement temperatures" (2
real sensor lines + 1 computed average) that renders with **no in-image legend**,
whose `render_metadata.legend` carries three entries — two `kind: "series"` (solid
sensor colors) and one `kind: "computed"` (the dashed average) — and whose card
shows a three-row legend disclosure with a `computed` tag on the average row and
the average drawn as a dashed line. Eyes-on: the PNG is clean; the card row reads
`computed`.

## Implementation order

Concrete-first:
1. **Schema** — add `computed` to both `kind` enums (both copies). Enables a
   worker response carrying the new kind to validate. (C3)
2. **Prompt + render_dispatch** — extend the codegen return-contract rule to
   require `legend[]` (self-reported colors, `kind`, dashed computed, no
   `ax.legend()`); close the `_build_worker_artifact_metadata` parity gap
   (copy `legend` + `summary`). This is the anchor: a codegen legend reaches the
   card. (C1, C2, C4)
3. **Frontend** — the `computed` tag + swatch branch. (C5)
4. **Live proof** — eyes-on the anchor artifact on the card. (C6 is a non-event:
   confirm a legend-less older artifact still serves.)

## Proof requirements

1. **Schema** — both schemas validate a legend entry with `kind: "computed"`;
   existing `series`/`overlay` fixtures still validate (additive/back-compat).
2. **Unit (Python)** — `_build_worker_artifact_metadata` copies `legend` +
   `summary` onto the artifact (parity with the Pillow builder); a worker
   `render_result` carrying a legend threads through to `snapshot.chart.legend`.
3. **Prompt-rule regression** — a test pins the codegen return-contract text:
   `legend` required, `kind` includes `computed`, computed drawn dashed, no
   `ax.legend()` (marker-stable, rule-gate pattern).
4. **Unit (frontend, Vitest)** — a `kind: "computed"` row renders the `computed`
   tag + distinct swatch and no state children; `series`/`overlay` rows unchanged;
   empty-legend degrades.
5. **Live proof (eyes-on, deploy-time)** — a codegen multi-series chart with a
   computed average populates the card legend with a `computed` row and draws the
   computed line dashed, in-image legend absent.

## Non-goals

- Enforcing or verifying the model's reported colors against the rendered PNG
  (no pixel parsing — cosmetic-only, C6).
- An integration-assigned color palette for codegen (colors stay model-chosen).
- `timeline` / `histogram` / `aggregate_bar` family legends (still in-image; out of
  scope exactly as in the parent spec).
- The Pillow path (already wired by card-legend-and-summary.md).

## References

- [card-legend-and-summary.md](card-legend-and-summary.md) — parent contract (C1 shape, C4/C6 card presentation)
- ADR-0027 (card-owned legend), ADR-0030 (codegen primary render path), ADR-0034 (codegen analysis-intent conduit), ADR-0031 (render_metadata answer/claims channel)
- [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
