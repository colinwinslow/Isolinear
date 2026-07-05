# ADR-0033 — Integration-precomputed shaded overlay bands for codegen

- Status: **accepted** (direction decided by Colin 2026-07-05, "try it, leave room to back out"; implemented + live-proven 2026-07-05)
- Date: 2026-07-05
- Deciders: Colin (direction), agent (design)
- Relates to: ADR-0022 (state overlays / shaded_intervals), ADR-0030 (codegen-primary rendering), ADR-0031 (model-authored analysis)

## Context

Codegen (ADR-0030) is the primary render path. State overlays — shading when a
binary/categorical entity is "active" (e.g. when the AC was cooling/heating,
from `climate` `hvac_action`) — are composed deterministically into the
`chart_spec` as `shaded_intervals` overlays (ADR-0022 D4/D5), and the trusted
Pillow renderer draws them as background bands using tested region logic
(`_state_segments` / `_binary_on_regions`, attribute-aware).

On the codegen path this did not work. Live (0.2.20), an overlay prompt ("kitchen
and basement temps over the last five days and when the AC was running") rendered
COMPLETE but wrong: the floor model (`gemma4:e4b`) plotted the categorical state
series as a **line on the temperature axis** at the constant `"cool"` mode value,
instead of shading the intermittent `hvac_action` cooling/heating spans. The
0.2.19 prompt rule ("plot every series in `history_series` as a line") actively
pushed it there. Turning a state series into correct shaded intervals requires
knowing it is an overlay, reading the right attribute (`hvac_action`, not the
mode), collapsing points into held segments, computing active spans, and drawing
bands behind the lines — reliably beyond the floor model, and an accept-≠-quality
failure the static safety check cannot catch (the code is *safe*, just wrong).

## Decision

The **integration precomputes the shaded overlay bands** and hands the model
ready-to-draw geometry; the model does not derive intervals.

- `_compute_overlay_bands(chart_spec, history_series)` computes, per
  `shaded_intervals` overlay, a list of bands `{start_ms, end_ms, color, label,
  entity_id}`, **reusing the Pillow renderer's** `_binary_on_regions` /
  `_categorical_overlay_states` (so codegen matches the trusted renderer exactly,
  including attribute-awareness — `hvac_action` for climate — and the
  cooling→blue / heating→orange `color_map`).
- The bands are carried in the existing `render-request` `derived_intervals`
  field (schema already `array` of open objects — no schema change). The prompt
  projection already forwards `derived_intervals`.
- Prompt rules change: plot **only** `kind == "numeric"` series as lines; do NOT
  plot `binary_state` / `categorical_state` series as lines; draw each
  `derived_intervals` band as `ax.axvspan(...)` behind the lines with one legend
  entry per distinct label/color; do not compute intervals in generated code.
- The state overlay series stays in `history_series` (grounding/answer may use
  it); it is simply not plotted as a line.

This is a deliberate lean toward **integration-side determinism** for overlays,
against the general "lean on the model" steer ([[design-lean-on-model]]) — chosen
because the region computation already exists, is deterministic, and the model
demonstrably cannot do it. It is deliberately **isolated and revertible** (Colin's
"room to back out"): one band-computation function + the `derived_intervals`
population + the two prompt rules. Backing out is removing the population and
reverting the rules; nothing else depends on it, and the Pillow fallback is
unaffected (it computes its own overlays and ignores `derived_intervals`).

## Consequences

- Codegen overlays now match Pillow: numeric lines + shaded active-state bands,
  correct attribute, correct colors. Live-verified 5/5 (2 numeric lines, real
  cooling bands drawn via `axvspan`, no state line, no error).
- `derived_intervals` grows with the number of active spans; a pathological,
  rapidly-cycling overlay could enlarge the prompt (bounded by the codegen
  `num_ctx` + the ADR-0031 overflow safety net). If it bites, cap/merge bands.
- Kill condition: if the model can't reliably draw the given bands, or the
  determinism proves too rigid, revert per above and reconsider a model-authored
  approach with a visual validator (packet 6).
- The generic axis-word ("Value" vs "Temperature") is unchanged — a separate
  cosmetic follow-up.
