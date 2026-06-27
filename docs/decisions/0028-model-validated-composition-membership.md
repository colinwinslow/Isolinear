---
id: 0028
title: Model-validated composition membership for overlay/timeline selection
status: accepted
date: 2026-06-26
supersedes: []
superseded-by: null
tags:
  - home-assistant
  - model-provider
  - entity-allowlist
  - render-family
  - flexibility
---

# ADR-0028: Model-validated composition membership for overlay/timeline selection

## Context

ADR-0024 made entity selection model-driven on residual ambiguity: D1 ranks
candidates by token specificity, and D2 (`select_entity`) validates/expands/narrows
the result against the full approved catalog. ADR-0024 D2 was explicitly designed
to "validate D1's answer and add any entities the prompt mentions that D1 missed"
or "narrow it (remove a false D1 match)."

But the overlay composition path never reaches D2. In `select_prompt_entity_ids`
(`job_orchestration.py:2122-2163`), when a fuzzy prompt matches multiple catalog
entities, the code composes numeric + state entities into a `numeric_with_overlay`
set and **returns immediately at line 2146** — a deterministic short-circuit ahead
of the D2 validation pass. The composition rule itself is asymmetric: categorical
entities (e.g. climate) only join the composition if they matched a *domain
synonym* (the existing noise-match guard, line 2131-2138), but **binary entities
always compose** ("Binary entities always compose," line 2139), and the numeric
primary is whatever matched — with no check that any of them is the prompt's actual
subject.

Live `0.1.47` retest (2026-06-26) surfaced both failure directions, confirmed by
reproducing the exact disclosures against the live `gemma4:e4b`:

- **"when was the kitchen door open today"** → composed
  `[sensor.kitchen_ecobee_temperature (numeric), binary_sensor.kitchen_door
  (binary)]`. The temperature sensor noise-matched the shared location token
  **kitchen** and became the *primary*; the door — the literal subject — was
  demoted to an overlay. The planner was disclosed only the temperature sensor and
  returned `clarification_needed` ("which entity should track the door's status?").
  Correct routing is a **timeline** of the door alone.

- **"show kitchen temp and when the AC was running"** → composed
  `[sensor.kitchen_ecobee_temperature, binary_sensor.kitchen_door,
  climate.kitchen_ecobee]`. `kitchen_door` noise-matched **kitchen** and entered as
  a *spurious second overlay*, tipping the planner over the clarification threshold.
  The clean disclosure (temp + AC overlay only) plans reliably.

Both are **membership** failures — the wrong *set* of entities was composed — not
planner, schema, or family-routing bugs. The deterministic composition guard is
the exact "rigid deterministic guard" ADR-0024/ADR-0023 move away from, applied to
the one selection path D2 does not yet cover.

## Decision

**Route the multi-match composition set through the model before it is locked in:
the model prunes candidates that matched only on a shared, non-distinctive token
(noise matches) and returns the prompt's actual subject set; the integration then
derives the render family deterministically from the pruned set's entity kinds.**
The model decides *membership*; the integration keeps *family* and *overlay
composition* deterministic.

1. **D6 — Composition membership goes through D2.** The `numeric_with_overlay`
   short-circuit (line 2146) no longer returns directly. When a fuzzy prompt
   produces a multi-entity composition candidate, the candidate set is handed to
   the existing `select_entity` model pass — extending ADR-0024 D2's "validate and
   narrow" role to the composition path. The model is disclosed the prompt and each
   candidate (`entity_id`, `friendly_name`, kind, area, matched tokens) and returns
   the subset the user actually asked about. Noise matches (an entity matched only
   on a location word already shared with another candidate, contributing no
   distinctive token of its own) are dropped.

2. **D7 — Family stays deterministic (invariant #9 unchanged).** The model returns
   only a membership set, never a `chart_type`. `_resolve_render_family` runs on the
   pruned set exactly as today and derives `time_series` / `timeline` /
   `time_series_overlay` / `mixed` from entity kinds. A pruned set of one binary
   entity routes to `timeline`; a numeric + intentional state set routes to overlay.
   Overlay composition (which entity is primary vs. shaded) remains integration-owned
   (ADR-0022 D5).

3. **D8 — Gate on genuine ambiguity; keep the fast paths.** The model pass fires
   only when there is a multi-match composition candidate with token overlap — the
   case that is currently mis-resolved. The explicit-entity-id path, the single-match
   path, and an unambiguous single-kind selection keep their existing zero-latency
   deterministic resolution. This bounds the added latency to the prompts that need
   the judgment.

4. **D9 — Enforcement unchanged (invariant #1).** The model only *narrows* among
   already-approved, already-disclosed candidates. The pruned IDs are validated
   against the approved catalog and fail closed if out of set, identical to ADR-0024
   D2/D4. Selection still never widens what data may be touched.

5. **D10 — Clarification remains the honest fallback.** If pruning leaves a
   genuinely ambiguous set (e.g. two equally-specified thermostats, or the model
   abstains), the clarification card still appears. Pruning removes *noise*, not
   *genuine* ambiguity.

## Rationale

- The defect is precisely the one ADR-0024 already diagnosed (shared-word
  false composition), on the single path D2 was never wired into. Extending D2
  rather than adding more deterministic token heuristics is the consistent move and
  the one Colin steered toward (lean on the model over hard-coded determinism).
- Keeping **family** and **overlay pairing** deterministic preserves the
  constrained-decoding boundary (the per-family planner schema pins `chart_type`)
  and invariant #9, while moving only the genuinely linguistic "which entities did
  they mean" decision to the model. Letting the model pick the family too would
  reopen the composition to non-deterministic mis-pairing and forfeit exact-assertion
  evals — analysed and rejected (see Alternatives).
- Membership-only is sufficient: reproduction shows that once the set is correct,
  the existing deterministic routing produces the right family for both failing
  prompts.
- The pass reuses ADR-0024's `select_entity` infrastructure and the ADR-0026
  pollable-planning phase, so reasoning still streams and `job/start` stays fast.

## Consequences

**Enables:**
- "when was the kitchen door open today" renders a door timeline; "show kitchen
  temp and when the AC was running" renders a temp line with an AC overlay — no
  spurious clarification.
- A single, uniform model-validation seam for *all* multi-match selection, closing
  the gap ADR-0024 D2 left on the composition path.

**Constrains:**
- Adds a model round-trip on the ambiguous-composition path (bounded by D8's gate;
  amortised against the planning call that follows).
- Composition membership is now model-influenced, so its evals assert on a live (or
  recorded-fixture) model decision; the *family* mapping from the pruned set stays
  exactly assertable.

**Open:**
- ~~Whether D6 should fold into the same `select_entity` call as ADR-0024 D2's
  expansion pass or stay a distinct composition-validation call.~~ **Resolved at
  implementation:** D6 is a distinct `_prune_composition_with_model` wrapper that
  reuses the existing `_run_model_entity_selection` primitive (id + friendly-name
  disclosure, no schema change). The composition path and the expansion path stay
  separate branches of `_resolve_entity_selection_with_model`.
- The model prunes reliably from the entity friendly names alone (confirmed live for
  both failing prompts), so no kind/area/`matched_tokens` enrichment was added — the
  disclosure stays the ADR-0024 id+label shape. If a future case needs the token
  signal, that enrichment is the lever.
- Whether to surface the pruning decision in the streamed reasoning (ties to
  ADR-0025).

## Relationship to invariant #1 and #9

This ADR **further refines invariant #1's disambiguation behavior** (model
validates composition membership; clarify remains the fallback) while leaving the
**allowlist-enforcement safety property unchanged**, exactly as ADR-0024 did for the
single-entity path. **Invariant #9 is untouched**: render family is still derived
deterministically from entity kinds before planning, and the model never chooses
`chart_type`.

## Alternatives considered

- *Deterministic guard (mirror the categorical domain-synonym check for binary +
  numeric: only compose entities contributing a distinctive non-location token).*
  Viable and smaller, but it is another hard-coded, English-leaning heuristic on the
  treadmill ADR-0024 rejected; chosen against per the lean-on-model direction.
- *Let the model pick the render family / composition shape too.* Rejected: it moves
  the most failure-prone decision out from behind the per-family constrained-decoding
  schema, reopens overlay pairing to non-deterministic mis-composition, and turns
  exact family evals probabilistic. ADR-0023 already gives the model chart-type
  choice *within a deterministic envelope*; widening that envelope is the lower-risk
  lever if more model influence on family is wanted later.
- *Keep the deterministic composition short-circuit.* Rejected: it is the direct
  cause of both live failures.

## References

- ADR-0024 (model-driven entity selection — D2 validate/narrow role, extended here),
  ADR-0022 (render-family routing / overlay composition D4/D5 — kept deterministic),
  ADR-0023 (model-proposed family within a capability envelope — sibling boundary),
  ADR-0026 (entity selection in the pollable planning phase), ADR-0003/0008
  (allowlist / read-only safety, unchanged).
- `custom_components/isolinear/job_orchestration.py` — `select_prompt_entity_ids`
  (the line 2146 short-circuit), `_resolve_render_family`, `_catalog_item_matches_prompt`.
- `custom_components/isolinear/model_provider.py` — `select_entity`,
  `load_entity_selector_schema`.
- Invariant #1 and #9 in `CLAUDE.md` / `AGENTS.md` (disambiguation refined;
  allowlist enforcement and deterministic family routing unchanged).
