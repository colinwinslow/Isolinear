---
status: accepted
date: 2026-06-26
depends-on-adrs: [0028, 0024, 0022, 0026]
---

# Composition membership: model-validated entity set before render-family routing

## Status

Accepted. Defines the contract surface for ADR-0028 — routing the multi-match
composition candidate set through the model (extending ADR-0024 D2) so noise
matches are pruned before `_resolve_render_family` runs.

## Related docs

- [bdd/entity-clarification/model-validated-composition-membership-bdd.md](../../bdd/entity-clarification/model-validated-composition-membership-bdd.md) — observable behavior
- [docs/decisions/0028-model-validated-composition-membership.md](../decisions/0028-model-validated-composition-membership.md) — the decision
- [docs/decisions/0024-model-driven-entity-selection.md](../decisions/0024-model-driven-entity-selection.md) — the D2 pass this extends
- [STATUS.md](../../STATUS.md) — current phase and active work

## Context

`select_prompt_entity_ids` short-circuits the multi-match path into a
`numeric_with_overlay` composition and returns before ADR-0024 D2 can validate it
(`job_orchestration.py:2146`). Because the composition rule composes **any** binary
match (and the numeric primary is whatever matched), entities that hit only a shared
location token — `binary_sensor.kitchen_door` against "show kitchen temp and when
the AC was running", or `sensor.kitchen_ecobee_temperature` against "when was the
kitchen door open today" — enter the disclosed set. The planner, handed a set that
does not match the prompt's subject, returns `clarification_needed`
(`model_provider_planner_not_chart_spec_ready`).

This spec makes the composition candidate set pass through the model `select_entity`
pass, which prunes noise matches and returns the subject set. The render family is
still derived deterministically from the pruned set (invariant #9). The allowlist
boundary is unchanged (invariant #1): the model only narrows already-approved,
already-disclosed candidates.

## Behavior contract

### Trigger (gate — ADR-0028 D8)

The composition-validation pass runs only when **all** hold:

- the prompt produced **>1** catalog match (not explicit-id, not single-match), and
- the matches span a composition candidate — at least one numeric **and** at least
  one state (binary/categorical) match, **or** ≥2 state matches that would otherwise
  compose, and
- the matches share at least one prompt token across candidates (the noise-match
  condition; a fully distinct multi-match set with no shared token is not the target
  and keeps existing behavior).

When the gate does not fire, the explicit-id, single-match, and existing
specificity/clarification paths are unchanged (zero added latency).

### Model call

Reuses `model_provider.select_entity` (ADR-0024 D2) / `load_entity_selector_schema`
**unchanged** — the request discloses the prompt, `candidate_entity_ids` (the composed
set), and `candidate_labels` (the per-entity friendly name). The friendly name is the
load-bearing signal: "Kitchen Door" vs "Kitchen Temperature" is enough for the model to
tell which candidate the prompt names, so no kind/area/`matched_tokens` enrichment is
added (empirically confirmed against the live `gemma4:e4b` selector for both failing
prompts — see the evidence file). Keeping the existing D2 request shape means no
schema or `model_provider.py` change.

The model returns the **subset** of disclosed `entity_id`s the prompt is actually
about (a membership list), or `clarification_needed`. It returns **no** `chart_type`,
family, or primary/overlay role — those stay integration-owned.

### Post-call resolution

1. Validate every returned id against the approved catalog; any out-of-set id fails
   closed (`model_provider_*` rejection), identical to ADR-0024 D4. Off-catalog =
   reject regardless of confidence.
2. If the model abstains or the pruned set is still genuinely ambiguous (e.g. ≥2
   equally-specified same-kind entities with no distinguishing subject), fall through
   to the clarification card (ADR-0028 D10).
3. Otherwise return the pruned set with `source: "numeric_with_overlay"` (when it
   still composes) or the appropriate single-kind source, and hand it to
   `_resolve_render_family` unchanged. Family is derived from the pruned kinds:
   pruned-to-one-binary → `timeline`; numeric + intentional state → overlay; etc.

### Invariants

- **#1 unchanged** — allowlist membership enforced post-prune; selection never widens
  data scope.
- **#9 unchanged** — family derived deterministically from kinds; model never picks
  `chart_type`; overlay primary/shaded pairing stays in `_resolve_render_family` /
  `_compose_state_overlays`.

## Anchor artifact

An eval CASE that feeds the prompt **"when was the kitchen door open today"** with a
catalog containing `sensor.kitchen_ecobee_temperature` (numeric) and
`binary_sensor.kitchen_door` (binary), and asserts the resolved set is
`["binary_sensor.kitchen_door"]` with family `timeline` — i.e. the temperature noise
match is pruned. Built first, before the gate/plumbing.

## Implementation order

1. **Anchor eval CASE** (door prompt → pruned to door → `timeline`) — red.
2. **Carry candidate items** — attach the matched composition items to the
   `numeric_with_overlay` result of `select_prompt_entity_ids` so the orchestration
   can reach them (the existing id+label disclosure needs no new payload).
3. **Gate** — detect the ambiguous-overlap composition candidate in
   `select_prompt_entity_ids` (shared-token check) and divert it from the line-2146
   short-circuit to the model pass.
4. **Resolution** — validate/prune/fallback per the contract; feed pruned set to
   `_resolve_render_family`.
5. **Second eval CASE** (temp+AC → pruned to temp+AC, door dropped → overlay) and
   the clean/no-op regression cases.
6. **BDD evidence** capturing raw resolution output for each scenario.

## Proof requirements

1. Unit tests in `tests/test_composition_membership.py` (new) green: gate fires only
   on the ambiguous-overlap case; pruning drops noise matches; out-of-catalog model
   ids fail closed; abstain/genuine-ambiguity falls through to clarification; clean
   single-match and explicit-id paths are byte-for-byte unchanged (no model call).
2. BDD scenarios in the paired BDD pass; evidence file carries raw resolved-set
   output (not summaries) for each scenario.
3. Eval CASEs (door → timeline; temp+AC → overlay with door pruned) PASS against the
   selection path; the deterministic family mapping from the pruned set is asserted
   exactly.
4. Architecture review: invariant #1 and #9 unviolated (allowlist enforced;
   family/composition deterministic).
5. Live HACS retest: the two `0.1.47` failing prompts complete (door timeline; temp +
   AC overlay) with no spurious clarification.

## Non-goals

- Letting the model choose render family, `chart_type`, or overlay primary/shaded
  role (explicitly rejected in ADR-0028; stays deterministic).
- Changing the single-entity D1/D2 behavior from ADR-0024.
- Widening the ADR-0023 capability envelope (separate lever, separate packet).
- Any change to the allowlist, history retrieval, or renderer.

## References

- ADR-0028 (this decision), ADR-0024 (D2 pass), ADR-0022 (overlay composition D4/D5),
  ADR-0026 (pollable planning phase), ADR-0023 (capability envelope — sibling).
- `custom_components/isolinear/job_orchestration.py` — `select_prompt_entity_ids`,
  `_resolve_render_family`, `_catalog_item_matches_prompt`,
  `_entity_matches_via_domain_synonym`.
- `custom_components/isolinear/model_provider.py` — `select_entity`,
  `load_entity_selector_schema`.
