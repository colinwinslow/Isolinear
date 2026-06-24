---
status: accepted
date: 2026-06-21
accepted: 2026-06-24
depends-on-adrs: [0023, 0022, 0021, 0019, 0006, 0005]
---

# Render family capability envelope: model-proposed chart family within validated capability

## Status

Accepted. Implemented in 0.1.44. Defines the contract surface for ADR-0023 (model-proposed render family
within a deterministic capability envelope), including the first live-renderer
tranche (`histogram`, `aggregate_bar`) and the fail-soft sparse-render rule.

## Related docs

- [bdd/rendering/render-family-capability-envelope-bdd.md](../../bdd/rendering/render-family-capability-envelope-bdd.md) — observable behavior
- [docs/decisions/0023-model-proposed-render-family-within-capability-envelope.md](../decisions/0023-model-proposed-render-family-within-capability-envelope.md) — the decision
- [docs/specs/chart-spec-rendering-spec.md](chart-spec-rendering-spec.md) — trusted renderer scope (extended here)
- [STATUS.md](../../STATUS.md) — current phase and active work

## Context

Today render-family selection is deterministic and single-valued
(`_resolve_render_family`, ADR-0022 invariant #9): the integration picks one
family from each resolved entity's `_series_kind`, and the model never chooses
`chart_type`. Two prompts that resolve to the same entity therefore get the same
chart — "temperature over time", "distribution of temperatures", and "average
temperature per day" all collapse to one line.

ADR-0023 splits the decision along the capability/intent seam: the integration
computes the **set** of families the data shape can support (the *capability
envelope*); the model selects *within* that set from the user's intent; a
deterministic gate rejects any out-of-envelope choice. This spec defines that
contract and the first live-renderer families that make it observable. Families
not yet drawable by the live Pillow renderer stay out of every envelope, so the
mechanism can ship incrementally.

## Behavior contract

### 1. Capability envelope (deterministic, integration-owned)

A new resolver returns an **ordered, non-empty** list of families instead of a
single family. Proposed shape (in `job_orchestration.py`):

```python
def _resolve_render_envelope(resolved_entities) -> dict:
    # -> {"families": [<family>, ...],         # ordered; first = default
    #     "default_family": <family>,           # the deterministic fallback
    #     "shape": "<single_numeric|multi_numeric|numeric_with_overlay|"
    #              "all_categorical|mixed_unsupported>"}
```

Membership is a function of **data shape only — never sample count** (ADR-0023
D6). The shape → envelope mapping, gated to families the live renderer can draw:

| Resolved shape | Envelope (this spec) | Later tranches (roadmap) |
|---|---|---|
| one numeric series | `time_series`, `histogram`, `aggregate_bar` | — |
| two numeric series | `time_series` | `scatter` |
| one numeric + ≥1 binary | `time_series_overlay` | — |
| all binary / categorical | `timeline` | — |
| ≥2 numeric + binary, or categorical + numeric | (none) → fail closed `mixed_chart_composition_unsupported` | — |

`time_series` is always first (the safe default) when present. The envelope is
deterministic and auditable; it never depends on model output.

### 2. Model selects the family within the envelope

`load_planner_result_schema` (in `model_provider.py`) gains an envelope argument
so the structured-output `chart_type` enum equals the envelope's `families`
(not a hard-locked single value). The planning call site passes the resolved
envelope. The model:

- chooses `chart_type` from the enum based on prompt intent;
- records a `reasoning_summary` for the choice;
- when the envelope has exactly one member, has no discretion — behavior is
  identical to ADR-0022 (binary → `timeline`).

Each family already has, or gains, a per-family structured-output schema
fragment (the ADR-0022 per-family pattern generalizes: `aggregate_bar` needs
`source.type: aggregate` + operation; `histogram` needs `x_axis.bin_count`).

### 3. Out-of-envelope gate (deterministic, post-plan)

A new check rejects a model-chosen family outside the computed envelope, before
any render or storage:

```python
def validate_model_provider_chart_family(chart_spec, envelope) -> dict:
    # accepted, or
    # {"accepted": False,
    #  "code": "model_provider_chart_family_out_of_envelope",
    #  "chosen_family": ..., "allowed_families": [...]}
```

This is additive defense in depth alongside constrained decoding (the enum makes
out-of-envelope structurally unlikely; the gate makes it impossible to act on),
mirroring the existing entity enum-pin + structural entity gate. Failure surfaces
as a card-facing failed snapshot at `failure.stage: model_provider_planning`.

### 4. Live renderer widening (first tranche) — fail-soft

`in_process_renderer.py` gains two families on the live Pillow path:

- `_render_histogram_png` — fixed-count value bins from `x_axis.bin_count`
  (default 8) over one numeric series.
- `_render_aggregate_bar_png` — one bar per time bucket (e.g. per day/hour) or
  per aggregate source, from `mean`/`min`/`max`/`sum`/`count`.

Both reuse the 0.1.21 phone-legibility treatment (font/stroke sizing) and the
ADR-0021 statistics-aware `HistorySeries` (mean + min/max where present).

**Fail-soft density rule (ADR-0023 D6):**

- **Sparse input renders honestly thin** — a histogram of a handful of readings,
  an aggregate bar chart with one or two buckets, etc., render a valid PNG. Low
  density is never an `unsupported_chart_spec` and never withholds a family.
- **Fail-*closed* only on no usable data** — zero numeric points in the resolved
  window, or a beyond-retention window with no statistics for a non-`state_class`
  entity, still produces a card-facing failure (`no_long_term_statistics` /
  existing codes), never a silent empty chart. Unchanged from ADR-0021/0022.

`scatter`, `heatmap`, and `markers` remain matplotlib-era anchors only and stay
out of every envelope until a later tranche ports them to Pillow.

### 5. Entity enforcement unchanged (ADR-0023 D5)

The `source.entity_id` enum-pin (0.1.27) and the structural entity gate
(validates `series`/`overlays` sources + `memory_proposals[].entity_id`, ignores
free-text fields) are untouched. Family flexibility never widens which entities
or data the model may touch (invariant #1, ADR-0008).

## Anchor artifact

The simplest concrete observable proof of the whole mechanism: a "distribution"
prompt over **one approved numeric entity** computes an envelope of
`[time_series, histogram, aggregate_bar]`, the model picks `histogram`, and the
live Pillow path writes a served histogram PNG — built before any later family.

## Implementation order

1. **Anchor:** `_resolve_render_envelope` for the single-numeric shape (returns
   the 3-family envelope) + `_render_histogram_png` on the live path + the
   envelope passed into the planner schema. Prove the distribution prompt renders
   a histogram PNG end to end.
2. Out-of-envelope gate (`validate_model_provider_chart_family`) + card-facing
   failure snapshot.
3. `_render_aggregate_bar_png` + the `aggregate_bar` per-family schema fragment.
4. Fail-soft sparse-render coverage for both families; fail-closed no-data
   coverage.
5. Single-member envelopes confirmed identical to ADR-0022 (binary → timeline,
   numeric_with_overlay, mixed fail-closed) — regression, no behavior change.

## Proof requirements

1. Unit tests green: `_resolve_render_envelope` shape→families mapping;
   `validate_model_provider_chart_family` accept/reject; renderer histogram +
   aggregate_bar happy, sparse (fail-soft), and no-data (fail-closed) paths.
2. BDD scenarios in `bdd/rendering/render-family-capability-envelope-bdd.md`
   pass, with raw outputs captured in the paired evidence file.
3. Eval(s): extend `evals/timeline_render_family_routing.py` (or add an envelope
   eval) covering multi-family envelope routing + the new render CASEs; existing
   evals stay green.
4. Real-artifact proof: histogram and aggregate_bar PNGs, **including a sparse
   one**, eyes-on verified legible at the ~380px phone downscale.
5. Full suite green except the documented codegen-sandbox flake; version bump.

## Non-goals

- `scatter`, `heatmap`, `markers` on the live path (later tranches).
- Multi-axis / ≥2 numeric overlay; overlay on the `timeline` family.
- Density thresholds of any kind (explicitly rejected — D6).
- Clarification prompts for ambiguous intent across in-envelope families (the
  model picks a default and records `reasoning_summary`; revisit if live testing
  shows bad guesses).
- Any change to entity allowlist enforcement, the read-only/sandbox posture, or
  codegen mode.

## References

- ADR-0023 (this mechanism), ADR-0022 (per-family schema + routing, revised),
  ADR-0021 (tiered history / statistics), ADR-0019 (Pillow renderer),
  ADR-0006 (deterministic plan validation), ADR-0005 (schema-first contracts).
- `docs/specs/chart-spec-rendering-spec.md` — trusted renderer roadmap families.
- `custom_components/isolinear/job_orchestration.py`,
  `custom_components/isolinear/model_provider.py`,
  `custom_components/isolinear/in_process_renderer.py`.
