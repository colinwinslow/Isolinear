---
id: 0023
title: Model-proposed render family within a deterministic capability envelope
status: accepted
date: 2026-06-20
supersedes: []
superseded-by: null
tags:
  - home-assistant
  - renderer
  - chart-spec
  - model-provider
  - flexibility
---

# ADR-0023: Model-proposed render family within a deterministic capability envelope

## Context

ADR-0022 established invariant #9 (deterministic render-family routing): the
integration picks the chart family from each resolved entity's `_series_kind`
*before* planning, and the model never chooses `chart_type`. That was the right
call for the reason given — the model cannot reliably infer Home Assistant
entity capability (`state_class`, `device_class`, statistics availability,
retention) — and it fixed the binary-door dead-end.

But the product goal is **flexible visualizations from natural language**, and
the current design caps flexibility on three axes:

1. **The model cannot choose the chart shape.** Family selection is purely a
   function of `_series_kind`, so two prompts that resolve to the *same* entity
   get the *same* chart. "Show me the temperature over time" and "show me the
   distribution of temperatures" and "what's the average temperature per day"
   all collapse to one numeric line, because routing ignores user intent
   entirely.
2. **The live renderer only draws two shapes.** `in_process_renderer.py`
   supports `time_series` (line + shaded overlay) and `timeline` (step). The
   `bar` / `histogram` / `heatmap` / `scatter` / `markers` families exist only
   as matplotlib-era anchors in `src/Isolinear/` and `evals/` — never wired into
   the live Pillow path. So even a perfect family choice has nowhere to render.
3. **Over-eager deterministic guards reject valid model output** — e.g. the
   `0.1.27` entity gate that mistook a `chart_id` slug for an off-allowlist
   entity (fixed by structural validation; see Consequences).

The deterministic routing conflates two genuinely different concerns:
**capability** (what the data *can* honestly support — the integration's job,
because it has the registry/recorder metadata) and **intent** (what the user
*wants to see* — the model's job, because that is a language task the integration
cannot do). ADR-0022 solved capability by removing the model from the loop
entirely; that also removed intent, which is the half the model is good at.

## Decision

**The integration computes a deterministic _capability envelope_ — the set of
chart families that are valid for the resolved entities' data — and the model
selects the family _within_ that envelope from the user's intent. The validator
rejects any out-of-envelope choice.** The model proposes; the deterministic
envelope, JSON Schema, and entity allowlist dispose.

1. **D1 — Capability envelope (deterministic, integration-owned).** Before
   planning, from each resolved entity's `_series_kind` and the *shape* of the
   resolved set (how many numeric vs. binary/categorical series), the integration
   derives the *set* of families the data can support, not a single family.
   Envelope membership is a function of data *shape*, not data *density* — sample
   count never gates a family (see D6). Illustrative mapping:

   | Resolved data | Envelope (allowed families) |
   |---|---|
   | one numeric series | `time_series`, `histogram`, `aggregate_bar` |
   | two numeric series | `time_series`, `scatter` |
   | one numeric + ≥1 binary | `time_series_overlay` (numeric line + shaded bands) |
   | all binary / categorical | `timeline` |
   | mixed (≥2 numeric + binary, or categorical + numeric) | fail closed (`mixed_chart_composition_unsupported`, per ADR-0022) |

   The envelope is computed deterministically and is auditable; it never depends
   on model output.

2. **D2 — The model selects the family within the envelope from intent.** The
   per-call Ollama structured-output schema sets the `chart_type` enum to the
   *envelope members* (not a hard-locked single value as in ADR-0022). The model
   chooses based on the prompt's intent ("distribution" → `histogram`, "average
   per day" → `aggregate_bar`, "X vs Y" → `scatter`, "over time" →
   `time_series`) and records a `reasoning_summary`. When the envelope has
   exactly one member, this is byte-for-byte the ADR-0022 behavior — binary
   entities still deterministically render as a `timeline`, with no model
   discretion.

3. **D3 — Out-of-envelope choices fail closed.** A model-chosen family outside
   the computed envelope is rejected by a deterministic post-plan gate with a
   structured `model_provider_chart_family_out_of_envelope` failure (carrying the
   chosen family and the allowed set), the same fail-closed posture as the entity
   allowlist gate. This preserves ADR-0006 (deterministic plan validation): the
   model widens *expressiveness*, never *authority*.

4. **D4 — Renderer support is the gating dependency, staged.** A family may only
   enter an envelope once the **live Pillow renderer** can draw it. This ADR
   commits to widening the live renderer beyond `time_series` + `timeline`;
   concrete family scope and ordering are defined in a follow-up spec
   (`docs/specs/chart-spec-rendering-spec.md`), with the existing matplotlib-era
   anchors as a design reference to *port to Pillow*, not to wire in directly.
   Recommended first tranche (highest intent-coverage for numeric homelab
   sensors): `histogram` (distribution) and `aggregate_bar` (per-period
   summaries). `scatter` and `heatmap` follow. Until a family renders live, it
   stays out of every envelope.

5. **D5 — Flexibility in chart shape does not loosen entity enforcement.** The
   structured-output `source.entity_id` enum-pin (0.1.27) and the structural
   entity gate (post-0.1.27 fix: validates `series`/`overlays` sources +
   `memory_proposals[].entity_id`, ignores free-text fields) remain unchanged.
   Invariant #1 (entity allowlist) and ADR-0008 (read-only / sandbox) are
   untouched: the model gains latitude over *how data is drawn*, never over
   *which entities or data it may touch*.

6. **D6 — Low density is fail-soft; only "no usable data" fails closed.** The
   envelope never withholds a family because the resolved window is sparse. A
   family with few samples renders honestly thin — a histogram of a handful of
   readings looks sparse, a scatter with few time-aligned pairs shows few dots —
   rather than being removed from the model's choices. Fail-*closed* is reserved
   for *no usable data*: zero numeric points, or a beyond-retention window with
   no statistics for a non-`state_class` entity (unchanged from ADR-0021/0022).
   A thin chart is an honest answer ("there isn't much data here"); silently
   dropping a family the user asked for is more confusing than showing the
   sparse truth.

## Rationale

- Capability is a deterministic property of HA metadata the integration already
  computes; intent is a language-mapping task the integration cannot do and the
  model does well. Splitting the decision along that seam puts each half where it
  belongs, instead of sacrificing intent to keep capability deterministic.
- A *validated enum* is a safe way to lean on the model: constrained decoding
  makes an out-of-envelope family structurally unlikely, and the deterministic
  post-plan gate (D3) makes it impossible to act on — the same belt-and-suspenders
  pattern that the entity enum-pin already uses successfully.
- Staging on renderer support (D4) means this ADR can land incrementally: the
  envelope can start at today's two families (a no-op relative to ADR-0022) and
  widen as each renderer family ships, with no flag-day.
- It directly addresses the stated product goal — more flexible visualizations,
  more reliance on the model — without reopening the safety properties that
  ADR-0022 and ADR-0008 protect.
- Keeping the envelope shape-only (D6) avoids per-family density thresholds —
  tuning that would be brittle, cadence-dependent, and another form of rigid
  deterministic intent-reading. A sparse chart is self-documenting; the cost
  moves to the renderer (degrade gracefully), where it belongs.

## Consequences

**Enables:**
- The same entity can be charted as a line, a histogram, a per-day bar, etc.,
  chosen from the user's words — the core "flexible visualization" goal.
- Incremental rollout: envelope = {today's families} is identical to ADR-0022;
  each new renderer family widens expressiveness with no behavior change for
  existing prompts.
- A clean home for future families (heatmap, scatter) without another routing
  rewrite.

**Constrains:**
- A family is selectable only if the live Pillow renderer can draw it; the
  renderer becomes the pacing item, not the planner.
- The model's family choice is bounded by the deterministic envelope and
  rejected if out of bounds — flexibility is *within* validated capability, not
  unbounded.
- Each new family needs its own per-family structured-output schema fragment and
  unsupported-gate checks (the ADR-0022 per-family pattern generalizes).

**Open:**
- Exact envelope rules per `_series_kind` × set shape (numeric / binary series
  counts) — to be pinned in the rendering spec + BDD. Density thresholds are
  intentionally *not* a gate (D6); the renderer must instead degrade gracefully
  on sparse input, which becomes a renderer test obligation.
- Whether ambiguous intent across multiple in-envelope families should ask a
  clarification ("as a trend or a distribution?") vs. let the model pick a
  default. Lean: model picks a default, records `reasoning_summary`; revisit if
  live testing shows bad guesses.
- Whether `heatmap`/`scatter` are worth the renderer cost for the homelab MVP.

## Revised invariant (replaces ADR-0022 invariant #9)

> **Capability-bounded model render-family selection** — the integration
> computes a deterministic *capability envelope* (the set of chart families the
> resolved entities' data honestly supports) before planning; the model selects
> the family *within* that envelope from the user's intent, and a deterministic
> post-plan gate rejects any out-of-envelope choice. A single-member envelope is
> integration-determined exactly as before (binary → `timeline`). The model
> never widens what data or entities it may touch (invariant #1, ADR-0008). A
> family is in an envelope only if the live renderer can draw it. (ADR-0023)

## Relationship to ADR-0022

This ADR **revises ADR-0022's invariant #9 and decision D1** (deterministic
single-family routing). The rest of ADR-0022 stands unchanged and is relied on
here: D2 (the shared `_binary_on_regions` primitive), D3 (timeline is a
raw-recorder-states family), D4/D5 (overlay composition is integration-composed,
never model-emitted), and the unapproved-vs-substituted failure-code
disambiguation. The mixed-kind fail-closed behavior is preserved. (Formal
bookkeeping — whether to record this as a partial `supersedes` of 0022 — is left
for review; `supersedes` is currently empty pending that call.)

## Alternatives considered

- *Keep ADR-0022 as-is (integration picks the single family).* Rejected: it is
  the direct cause of the flexibility ceiling; identical entities cannot produce
  different intent-driven charts.
- *Let the model choose `chart_type` freely (no envelope).* Rejected: reintroduces
  exactly the ADR-0022 failure mode — the model picking a family the data cannot
  honestly support (a histogram of a door sensor), and a non-deterministic safety
  surface.
- *Infer intent deterministically with prompt keywords* (regex for "distribution",
  "average", …). Rejected: brittle, English-only, and exactly the kind of rigid
  deterministic intent-reading this ADR moves away from; intent mapping is the
  model's strength.
- *Widen the renderer but keep deterministic routing.* Rejected: more chart
  families with no way for the user to ask for them by intent is wasted capacity.
- *Gate families by a density threshold (e.g. ≥30 points for a histogram).*
  Rejected (D6): thresholds are brittle and cadence-dependent, and withholding a
  requested family is more confusing than an honestly sparse chart. Density is
  handled fail-soft in the renderer instead.

## References

- ADR-0022 (categorical timeline render family / invariant #9 — revised here),
  ADR-0006 (deterministic plan validation), ADR-0005 (schema-first contracts),
  ADR-0008 (read-only MVP / sandbox), ADR-0019 (Pillow in-process renderer),
  ADR-0020 (model-resolved window), ADR-0021 (tiered history data source).
- `docs/specs/chart-spec-rendering-spec.md` — live trusted renderer scope (to be
  extended per D4).
- `custom_components/isolinear/job_orchestration.py` — `_resolve_render_family`,
  `validate_model_provider_output_entities` (structural entity gate).
- `custom_components/isolinear/model_provider.py` — `load_planner_result_schema`
  (per-family structured-output schema; `chart_type` enum becomes the envelope).
