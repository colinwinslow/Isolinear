---
title: Card-level legend for the codegen render path
status: open
date: 2026-07-14
---

# Research: Card-level legend for the codegen render path

## Question

The Pillow-era card-level legend (ADR-0027 D1) — a rich disclosure list
*outside* the plot, one row per series/overlay with color swatch, entity id,
alias, and state breakdown — was wired end-to-end for the trusted renderer.
Since codegen became the primary render path (ADR-0030), charts either carry
no legend or an inconsistent in-image `ax.legend()` the model adds ad hoc (a
3-line multi-sensor-plus-computed-average chart rendered with no legend at
all; a similar chart the same day rendered a clean one). Is the old wiring
still usable, and what's the smallest change that makes the codegen path
populate it reliably?

## Context

Colin liked a specific convention he saw in one live codegen chart: solid
lines for real sensors, a dashed line for a computed series (e.g. the
cross-sensor average) — the same `kind: series` vs `kind: overlay` distinction
the Pillow legend already models. The ask is to get that distinction, and a
legend, consistently — not per-model-whim in-image text.

## Findings — the old wiring is fully intact and renderer-agnostic

Traced the chain end-to-end (2026-07-14 investigation):

1. **Schema** — `legendItem` is still defined in both
   `render-result.schema.json` and `integration-job-snapshot.schema.json`:
   `{label, entity_id, color (#hex), kind: series|overlay, states?}`.
2. **Snapshot assembly** (`snapshot_assembly.py:632-633`) — copies
   `artifact["legend"]` into the card snapshot whenever it's a non-empty list.
   **This code has no renderer check** — it doesn't care whether Pillow or the
   worker produced the artifact.
3. **Frontend card** (`isolinear-card.ts:390+`) — the full `<details
   class="legend">` disclosure UI (per-row swatch, entity id, alias
   disclosure, overlay tag, state breakdown) is present and gracefully renders
   nothing when `legend` is absent/empty (`isolinear-card-legend.test.ts`
   covers this).

So the frontend and the snapshot layer were never touched by the ADR-0030
codegen cutover — they're just never fed data by that path.

## The actual gap

Two artifact builders exist in `render_dispatch.py`, one per renderer:

- `_build_in_process_artifact_metadata` (Pillow, line ~1686) — copies both
  `summary` and `legend` from `render_metadata` onto the artifact (lines
  1704-1711).
- `_build_worker_artifact_metadata` (codegen/worker, line ~1739) — copies
  **only** `answer_text`. `summary` and `legend` are silently dropped. This
  parity gap was never closed when codegen became primary.

Upstream of that, the codegen sandbox's `render_chart` return contract
(`model_provider.py:268`, the `_CODEGEN_PROMPT_RULES` line) only asks for
`{title, series_plotted, warnings}` — no `legend` field exists in the
contract the model is told to fill in. The render-result schema's
`render_metadata` properties (`render-result.schema.json`) likewise has no
`legend` key today — it would need an additive schema field before a worker
response carrying one would validate.

Because matplotlib's color choice is entirely up to the generated code (no
integration-assigned palette, unlike Pillow's `_SERIES_COLORS` cycle), the
legend's `color` field can only come from the model self-reporting the colors
it used — there's no way for the integration to observe them after the fact
except by parsing the rendered PNG.

## Design sketch (three additive pieces, no rip-and-replace)

1. **Schema** — add `legend` to `render-result.schema.json`'s
   `render_metadata.properties`, reusing the existing `legendItem` `$defs`
   shape from the job-snapshot schema (or duplicating it there — check
   whether the two schemas already share `$defs` or need the definition
   copied).
2. **Prompt rule** — extend the codegen return-contract instruction
   (`model_provider.py:268` and neighboring `_CODEGEN_PROMPT_RULES` entries)
   so `render_chart` must also return `legend: [{label, entity_id, color,
   kind}]`, one entry per plotted series/overlay, with `color` being the exact
   hex the model passed to `ax.plot(..., color=...)`. This mirrors a pattern
   the model already executes correctly (it already reports `series_plotted`
   and `answer_text` the same way — self-reporting metadata about code it just
   wrote is proven, not new).
3. **`render_dispatch.py`** — add the same 2-line copy `_build_worker_artifact_metadata`
   is missing, matching `_build_in_process_artifact_metadata` exactly (and
   pick up `summary` too, since it has the identical gap and no reason not to
   fix both at once).

## Open sub-questions

- **`kind: series` vs `kind: overlay` for computed series.** Colin's liked
  convention (solid = real sensor, dashed = computed) suggests computed
  series (means, deltas, deviations) should report `kind: overlay` even
  though they're not shaded bands like the Pillow overlay convention — or
  does `legendItem.kind` need a third value (e.g. `computed`) so the frontend
  can style it distinctly from a state-overlay band? Check
  `isolinear-card.ts`'s `legendLabel`/`legend-tag` rendering to see whether
  `kind: "overlay"` implies band-specific UI that a computed line shouldn't
  inherit.
- **Enforcement / validation.** If the model's `legend` array omits an entity
  that's genuinely plotted, or claims a color it didn't use, is that
  something the static safety check or a grounding-style pass should catch,
  or is a wrong/missing legend a cosmetic-only failure (no repair loop
  trigger)? Precedent: `series_plotted` already exists in the schema
  unenforced — check whether it's ever cross-checked against anything, or if
  it's been a silently-unverified field this whole time.
- **Single-series charts.** Should a legend suppress itself when there's only
  one line (matching typical dashboard convention), or should the frontend's
  existing empty-state handling be relied on and the model just told to
  return `legend: []` in that case?
- **Backward compatibility with in-image `ax.legend()`.** Should the prompt
  also tell the model to *stop* drawing an in-image legend once the
  card-level one exists (avoiding a redundant/inconsistent double legend), or
  leave the in-image one as a fallback for anyone viewing the raw PNG outside
  the card?

## Resolution

Open — not yet promoted to a spec. Scoping needs a decision on the
`kind`/computed-series question above before a spec's contract surface can be
written cleanly. Re-scopes `STATUS.md` open-queue item (y) (originally framed
as an in-image-legend prompt nudge; this note found the richer, already-built
card-level path instead).
