---
id: 0027
title: Card-owned legend with a renderer color manifest and model-authored summary
status: accepted
date: 2026-06-25
supersedes: []
superseded-by: null
tags:
  - home-assistant
  - renderer
  - dashboard-card
  - chart-spec
  - model-provider
  - flexibility
---

# ADR-0027: Card-owned legend with a renderer color manifest and model-authored summary

## Context

The complete-view dashboard card has accumulated presentation debt that the live
chart surfaced (2026-06-25 review with Colin):

1. **The legend is baked into the PNG.** `in_process_renderer.py` draws series and
   overlay legend entries directly onto the image. On a busy overlay chart the
   legend overlaps the plotted lines and bands, and it cannot be restyled,
   collapsed, or made interactive because it is pixels.
2. **The "Entities and aliases" list is not a legend and reads poorly.** It renders
   `"<label>: <entity_id>"`, where `label` comes from a weaker source than the
   chart's own series labels — yielding non-descriptive rows ("Temperature:
   sensor.family_room_sensor_temperature") and a redundant
   "climate.kitchen_ecobee: climate.kitchen_ecobee" for the overlay. It carries no
   color information, so the reader cannot connect a row to a line on the chart.
3. **The caption echoes the prompt back.** The text under the chart is the user's
   own prompt (`Isolinear Chart: <prompt>`), which tells the user nothing they did
   not just type.
4. **Clutter text.** A duplicate "Isolinear" eyebrow, a hardcoded "approved scaffold
   history window" line, and a "pass / The first real vertical slice rendered…"
   validation block sit on the happy-path complete view. (Removed in 0.1.46 as a
   no-schema cleanup; recorded here for completeness.)

Underneath these is a structural gap: **the renderer assigns colors
deterministically (`_SERIES_COLORS` by index; overlay `color_map` per state) but
exposes none of it.** The snapshot's `chart.series` / `chart.overlays` carry only
`{label, entity_id}` (and `chart.overlays` is hardcoded to `[]`). The card
therefore *cannot* know which color belongs to which series, so it cannot be the
legend even if we wanted it to.

This sits on the same seam as ADR-0023: the integration owns the deterministic,
safety-bearing decisions (which entities, what colors, is-it-an-overlay), and the
model owns the linguistic ones (series labels — already true; and, newly, a
human summary and overlay labels). Leaning on the model for the linguistic parts
while keeping the safety parts deterministic is the project's stated direction.

## Decision

**The card becomes the legend. The renderer emits a color manifest as the single
source of truth for colors, and the model authors the chart's summary sentence and
the overlay labels.** Scope for this packet: `time_series` and
`time_series_overlay` families only.

1. **D1 — Renderer emits a legend manifest (single source of truth for colors).**
   The renderer that assigns the colors reports them in `render_metadata.legend`:
   an ordered list of
   `{label, entity_id, color: "#RRGGBB", kind: "series" | "overlay", states?:
   [{label, color}]}`. Series rows carry their line color; overlay rows carry their
   per-state children (e.g. cooling → blue, heating → orange). Nothing re-derives
   the palette — not the card, not the orchestrator.

2. **D2 — The in-PNG legend is removed for `time_series` and
   `time_series_overlay`.** The card draws the legend from the manifest. The
   `timeline`, `histogram`, and `aggregate_bar` renderers keep their in-image
   legends for now; extending the manifest to them is explicit follow-up work
   (they share the legend-clutter problem and are out of scope here by Colin's
   call).

3. **D3 — The model authors a chart summary.** `chart_spec.summary` is a single
   sentence describing what the chart shows, optionally with a brief observation of
   the model's choosing ("Temperatures from the basement, Maren's room, and the
   family room, with AC running overlaid."). It is surfaced as the card caption,
   replacing the prompt echo. A deterministic fallback (e.g. the chart title) is
   used when the model omits it or returns something empty/degenerate.

4. **D4 — The model authors overlay labels; the system still composes overlays.**
   The model returns `planner_result.overlay_labels`, an `{entity_id: label}` map
   for the overlay entities it was told about in the request. `_compose_state_overlays`
   stamps that label onto the overlay it builds, falling back to the catalog
   friendly name (or a derived "<friendly name> — running state") when the model's
   label is empty or entity-id-shaped. The label is anchored on the prompt's own
   framing ("AC running"), which sidesteps the whole-home-vs-per-zone mismatch
   (the kitchen ecobee that actually reports house-wide HVAC) without the
   integration having to model HVAC topology. Overlay **structure, colors,
   shading, and entity** remain integration-composed exactly as in ADR-0022 D4/D5
   — the model contributes only words.

5. **D5 — Legend labels come from the rendered series labels, guarded.** Row labels
   are the model-authored `series[].label` values already drawn on the chart. The
   card rejects empty or raw-entity-id-shaped labels and falls back to the catalog
   friendly name. A raw `entity_id` is never a primary legend label; it is revealed
   only inside the per-row disclosure.

6. **D6 — Per-row disclosure: entity, alias, and overlay state colors.** Each
   legend row collapses to a swatch + descriptive label and expands (flip-down) to
   reveal its `entity_id` and any saved alias that resolved it — the standalone
   alias list is removed, and alias display entries gain an `entity_id` so the card
   can match an alias to its row. For a **state-based overlay row**, the collapsed
   swatch is a split / multi-color swatch (e.g. half blue / half orange to signal a
   multi-state overlay), and the disclosure additionally lists the **per-state
   children** — one entry per running state (cooling, heating, …), each with its own
   colored square matching that band's color in the chart (sourced from the D1
   manifest's `states`). Single-state overlays show a solid swatch and need no child
   list. The section is renamed **Legend**.

7. **D7 — No loosening of safety surfaces.** The model gains exactly two new
   outputs: a `summary` string and an `overlay_labels` map of *labels* (never
   entity IDs that grant access — the map is keyed by entities already disclosed to
   it). Entity allowlist enforcement (invariant #1), overlay composition, color
   assignment, and deterministic render-family routing (invariant #9) are
   unchanged. The legend manifest is descriptive output, not an authority surface.

## Rationale

- Colors are a deterministic property the renderer already computes; making the
  renderer *report* them (D1) is the minimal change that lets the card be the
  legend without duplicating the palette in TypeScript, which would silently drift
  the first time a series is reordered.
- Pulling the legend out of the PNG (D2) is the actual declutter the user asked
  for and is only safe once the manifest exists — so D1 is a prerequisite, not a
  parallel nicety.
- Summary and overlay labels are language tasks (D3/D4); the integration cannot do
  them well and the model can. This extends the ADR-0023 capability/intent split to
  presentation: the system composes the overlay for safety; the model names it from
  the user's own words. It is also forward-compatible with a later home-HVAC-config
  memory — that memory would become another *hint* the same labeling pass consumes,
  not a redesign.
- Sourcing labels from the chart's own series labels (D5) fixes the poor-label bug
  at its root (the entities list was the wrong source) rather than papering over it.

## Consequences

**Enables:**
- An interactive, restyleable legend: color swatch + descriptive label, a flip-down
  revealing the entity_id and any matched alias, and a split swatch + per-state
  children for multi-state overlays (cooling/heating).
- A meaningful caption (what the chart shows) instead of a prompt echo.
- A decluttered chart image with no baked-in legend (for the two in-scope families).

**Constrains:**
- Three schemas change (see below); this is a schema-first, spec-first packet.
- The card now depends on `chart.legend` being present for the in-scope families;
  the orchestrator must populate it from `render_metadata.legend`, and the card
  needs a graceful empty-state when it is absent (older artifacts, other families).
- `timeline` / `histogram` / `aggregate_bar` temporarily have two legend styles
  (in-image) vs the in-scope families (card). Accepted; unified in follow-up.

**Open:**
- Whether to also drop the in-PNG chart *title* once the caption carries the
  summary (the PNG still renders its own title). Lean: keep the title in-image for
  now; revisit when the summary lands live.
- Exact fallback wording for a missing overlay label ("<friendly> — running state"
  vs domain-aware phrasing) — pin in the spec.
- Extending the manifest + external legend to the other three families — separate
  packet, to be discussed.

## Schema impact

- `chart-spec.schema.json` (+ `docs/schemas/`): add optional `summary` (string).
- `planner-result.schema.json`: add optional `overlay_labels` (object,
  `additionalProperties: string`), keyed by entity_id.
- `integration-job-snapshot.schema.json`: `chart` gains `summary` (string) and
  `legend` (array of the D1 shape); alias display entries gain `entity_id`.
- `render-result` / render metadata: carry `legend` (internal contract; validated
  if a render-result schema exists).

## Alternatives considered

- *Card re-derives the palette from the same index logic.* Rejected: duplicates the
  palette across Python and TypeScript; drifts on any reorder. D1 makes the renderer
  authoritative.
- *Keep the legend in the PNG.* Rejected: the clutter is the problem being solved.
- *Derive the overlay label deterministically ("<friendly> running state").*
  Rejected (Colin): cannot capture whole-home-vs-per-zone, and loses the user's own
  framing. Kept only as the fallback.
- *Let the model emit the full overlay object (label + source + colors).* Rejected:
  hands the model control of overlay colors, structure, and entity, reopening the
  ADR-0022 safety split and complicating the entity gate. The label map (D4) gets
  the words without the authority.
- *Build a home-HVAC-config clarification + memory now to name overlays.* Deferred:
  its own ADR/spec/UX and much larger; D4 is forward-compatible with it.

## References

- ADR-0023 (capability/intent split — extended here to presentation), ADR-0022
  (overlay composition is integration-composed, never model-emitted — D4/D5),
  ADR-0005 (schema-first contracts), ADR-0006 (deterministic plan validation),
  ADR-0008 (read-only / sandbox), ADR-0009 (semantic memory / aliases),
  ADR-0019 (Pillow in-process renderer).
- `custom_components/isolinear/in_process_renderer.py` — color palettes, legend
  drawing (to emit a manifest and stop drawing for in-scope families).
- `custom_components/isolinear/job_orchestration.py` — `_compose_state_overlays`
  (consume `overlay_labels`), chart/snapshot assembly (carry `summary` + `legend`).
- `custom_components/isolinear/model_provider.py` — planner schema + prompt (request
  `summary` + `overlay_labels`).
- `frontend/src/isolinear-card.ts` — `renderEntityDisclosure` → Legend; caption.
