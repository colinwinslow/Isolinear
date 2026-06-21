---
id: 0022
title: Categorical timeline render family via the model-driven path
status: accepted
date: 2026-06-18
supersedes: []
superseded-by: null
tags:
  - home-assistant
  - renderer
  - chart-spec
  - model-provider
  - vertical-slice
---

# ADR-0022: Categorical timeline render family via the model-driven path

## Context

The first real slice renders only numeric `time_series` / `line` charts. The
live Ollama structured-output schema (built in `model_provider.py`) hard-locks
`chart_type` to `["time_series"]` and `render_as` to `["line"]`, and the live
Pillow renderer (`in_process_renderer.py`) rejects anything that is not a numeric
line chart. Binary and categorical entities (door, motion, occupancy, lock,
on/off) carry no numeric state and — having no `state_class` — no long-term
statistics, so the model cannot honestly satisfy "numeric line." In practice it
substitutes or invents an entity reference, which the deterministic entity check
then rejects as `model_provider_chart_spec_hidden_entity`. The net effect: a
prompt about a door sensor fails with a misleading "outside the approved
allowlist" message even though the entity *is* approved, and the timeline
renderer the project always intended (the `state_interval_timeline` family lives
only in the simulated `src/Isolinear/fake_slice.py`, never in the live
integration) can never be reached. ADR-0020 (model-resolved window) and ADR-0021
(tiered data source) both implicitly assumed numeric charts.

## Decision

The integration **deterministically chooses the render family from the
`_series_kind` of each resolved entity, before the model is called**, and the
live Pillow renderer gains a categorical `timeline` / `step` family that reuses a
single on-region primitive shared with the (future) overlay layer.

1. **D1 — Deterministic 3-way composition (not model-chosen `chart_type`).**
   Each resolved entity is classified with the existing `_series_kind` logic
   *before* planning:
   - all numeric → `time_series` / `line` (unchanged path);
   - all binary/categorical → `timeline` / `step`;
   - **mixed** numeric + binary → `time_series` line with binary entities
     rendered as `shaded_intervals` overlays (target architecture; **lands in a
     0.1.26 fast-follow**, see Consequences).
   The model's job stays narrow — resolve the window and provide labels. The
   integration selects which per-family structured-output schema to send, so the
   model cannot pick the wrong family. This honors ADR-0006 (deterministic plan
   validation) over model discretion.

2. **D2 — One shared on-region primitive.** A binary "on" region is the same
   shape whether drawn as a standalone timeline lane or as an overlay band behind
   a numeric line. The renderer exposes `_binary_on_regions(history_series,
   active_values)` and consumes it from both `_render_timeline_png` (this packet)
   and the numeric renderer's overlay pass (0.1.26). No `DerivedInterval`
   extraction contract is introduced; step segments are computed directly from
   the normalized `binary_state` / `categorical_state` `HistorySeries` points
   (each state held until the next change).

3. **D3 — Timeline is a raw-recorder-states family.** Binary/categorical
   entities have no statistics tier. Within recorder retention the existing
   tiering already falls back to raw recorder states, so timelines render from
   raw on/off points. A timeline window that extends beyond recorder retention
   fails closed honestly (no raw states, no long-term statistics for a
   non-`state_class` entity) — preserving, not regressing, the ADR-0020/0021
   ordering: the `no_long_term_statistics` gate stays *after* planning.

4. **D4 — Mixed numeric + binary is a first-class overlay, not an error.** A set
   resolving to **exactly one numeric primary + one or more binary/categorical**
   entities composes into a numeric `time_series` line with each binary entity
   injected as a `shaded_intervals` overlay band behind it ("temperature, and
   when the AC was running"). Implemented in 0.1.26: `_resolve_render_family`
   returns the `time_series_overlay` family, the planner is disclosed only the
   numeric primary as a series, and `_compose_binary_overlays` appends the
   overlays deterministically after planning. A set with **two or more numeric
   series** mixed with a binary has no deterministic primary line and still fails
   closed with `mixed_chart_composition_unsupported`. Fuzzy prompts that match a
   single numeric + ≥1 binary resolve to this composition instead of asking the
   user to pick one entity. **Categorical noise-match handling (0.1.30):** when
   the match set also contains a categorical entity (e.g., `climate.kitchen_ecobee`
   matching "kitchen" alongside a temperature sensor and door sensor), the
   categorical is treated as a noise match and discarded. The composite was
   previously blocked in this case, dropping the temperature entity entirely.
   Categoricals cannot be rendered as `shaded_intervals` overlays regardless, so
   discarding them and proceeding with the numeric+binary composite is strictly
   better than blocking.

5. **D5 — Overlays are integration-composed, never model-emitted.** The core
   `chart-spec.schema.json` already defines a first-class `overlays[]` array
   (`render_as: shaded_intervals | band | step | markers`, `active_values`), so
   no core schema change is needed for either the timeline or the overlay. The
   model is handed only the family-appropriate series schema; the integration
   composes overlays deterministically in the 0.1.26 packet.

6. **Failure-code disambiguation.** `model_provider_chart_spec_hidden_entity` is
   split so the card-facing reason is honest:
   - `model_provider_referenced_unapproved_entity` — the model referenced an
     entity that is **not in the approved catalog at all** (a true allowlist
     breach);
   - `model_provider_substituted_entity` — the model referenced an entity that
     **is** approved but was **not disclosed for this job** (substitution /
     hallucination).
   The legacy code is retained as an accepted alias in the failure-classification
   set for back-compatibility of stored records.

## Rationale

- The integration already classifies entity kind deterministically from
  registry/recorder metadata; the model cannot reliably infer `state_class` /
  `device_class`, so family selection belongs in the integration (ADR-0006).
- Reusing one on-region primitive means the 0.1.26 overlay is additive, not a
  renderer rewrite — satisfying the requirement that this architecture must not
  preclude the overlay.
- Computing step segments directly from raw `HistorySeries` points avoids adding
  a `DerivedInterval` extraction surface to the live path.

## Consequences

**Enables:**
- Binary/categorical entities chart as legible on/off (or multi-state) step
  tracks through the live model-driven path (0.1.25).
- Numeric line + binary `shaded_intervals` overlay composition (0.1.26) with no
  renderer rewrite (shared `_binary_on_regions`) and no core schema change
  (existing `overlays[]`).
- Honest, distinct failure codes for unapproved vs. substituted entities.

**Constrains:**
- Render family is integration-chosen; the model cannot select `chart_type`.
- Timelines are raw-recorder-states only; beyond-retention timelines fail closed.
- Charts are homogeneous-kind until the 0.1.26 overlay lands; mixed-kind plots
  fail closed with `mixed_chart_composition_unsupported`.

**Open:**
- A dedicated `timeline_history_unavailable` code for beyond-retention binary
  windows (0.1.25 surfaces the existing `no_long_term_statistics` honestly).
- Overlay support for ≥2 numeric primaries (multi-axis), and overlay on the
  `timeline` family — both out of scope for 0.1.26.

## New invariant

> **Deterministic render-family routing** — the integration selects the chart
> family (`time_series` / `timeline`, and in future the overlay composition) from
> each resolved entity's `_series_kind` before planning; the model never chooses
> `chart_type`. Binary/categorical entities render as raw-states step tracks and
> cannot be charted beyond recorder retention. (ADR-0022)

## Alternatives considered

- *Let the model choose `chart_type`* — rejected: non-deterministic and the
  model cannot reliably know HA entity capability.
- *Port the `DerivedInterval` timeline contract from the fake slice* — rejected
  for the live path: adds an extraction surface; raw `HistorySeries` points
  already carry the on/off states.
- *Fail binary entities closed with "not numerically chartable"* — rejected: the
  user wants the door sensor to actually chart, not dead-end.

## References

- ADR-0019 (Pillow in-process renderer), ADR-0020 (model-resolved window),
  ADR-0021 (tiered history data source), ADR-0006 (deterministic plan
  validation), ADR-0008 (sandbox / read-only).
- `docs/specs/chart-spec-rendering-spec.md` — live trusted renderer scope.
