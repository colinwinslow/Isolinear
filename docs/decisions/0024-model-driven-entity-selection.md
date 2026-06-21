---
id: 0024
title: Model-driven entity selection with a deterministic disambiguation fast-path
status: accepted
date: 2026-06-21
supersedes: []
superseded-by: null
tags:
  - home-assistant
  - model-provider
  - entity-allowlist
  - clarification
  - flexibility
---

# ADR-0024: Model-driven entity selection with a deterministic disambiguation fast-path

## Context

Invariant #1 (ADR-0003, ADR-0008) requires that plans reference only approved
entities and that **ambiguous** entity prompts trigger clarification rather than
a silent guess. The current implementation realizes "ambiguous" in
`select_prompt_entity_ids` (`job_orchestration.py`) with a deterministic
token-overlap matcher: an approved entity is a *match* if **any** of its
meaningful label/entity-id tokens appears in the prompt
(`_catalog_item_matches_prompt`). One match → use it; multiple matches →
clarification; zero → clarification over the whole catalog.

The any-token rule over-triggers clarification. Live `0.1.28` testing:

- Prompt "show me when the kitchen door was open this morning", allowlist
  `binary_sensor.kitchen_door` + `climate.kitchen_ecobee`. Both match on the
  single shared token **kitchen** (`door` and `ecobee` are not weighed against
  it), so every kitchen-door prompt demands a "door or ecobee?" clarification —
  an answer a competent reader has from the words alone.

This is the entity-selection counterpart of the flexibility ceiling ADR-0023
addresses for chart *family*: a deterministic guard that the user experiences as
**rigid**, asking for clarification a language reader would not need. The matcher
conflates two cases it cannot tell apart:

1. **False ambiguity** — one entity is clearly specified and merely shares a word
   with another ("kitchen door" vs "kitchen ecobee"). The distinctive token
   (`door`) is present for exactly one candidate.
2. **Genuine ambiguity** — competing entities are matched only on a shared term
   and none is more specified ("show thermostat history" with two thermostats).

Entity selection from natural language is a language task. The integration owns
the safety boundary (the allowlist); which approved entity the user *meant* is
the model's strength — the same capability-vs-intent seam ADR-0023 draws for
chart family.

## Decision

**Resolve the obvious cases deterministically by token *specificity*, and route
the residue to the model; show the user a clarification only when neither the
deterministic ranker nor the model can confidently resolve.** The model
proposes; the allowlist disposes.

1. **D1 — Specificity-ranked deterministic fast-path (this packet).** Score each
   approved entity by *how many* of its distinctive tokens the prompt contains
   (not merely whether one does). When the candidate set is not an overlay
   composition (ADR-0022 D4) and exactly one candidate outranks all others,
   select it without clarification. A tie at the top score is genuine ambiguity
   and still clarifies. This keeps invariant #1's "no silent guess" property —
   a uniquely best-specified reading is not a guess — while eliminating the
   shared-word false clarification. The existing explicit-entity-id path,
   single-match path, and numeric+binary overlay composition are unchanged; the
   specificity tie-break is inserted only on the previously-clarify path.

2. **D2 — Model-driven selection on residual ambiguity (staged, next packet).**
   When the deterministic fast-path cannot resolve (a top-score tie, or zero
   matches against a non-trivial catalog), the integration asks the model to
   select the entity (or entity set) from the **approved** catalog given the
   prompt, returning either a chosen set or an explicit `clarification_needed`.
   The user sees a clarification card **only when the model abstains**. This is
   the entity-selection counterpart of ADR-0023: the model selects only from
   disclosed approved entities; the chosen IDs are validated against the
   allowlist and fail closed if out of set (the same belt-and-suspenders as the
   `source.entity_id` enum-pin + structural entity gate).

3. **D3 — Ordering.** Model entity selection runs *before* render-family routing
   (ADR-0022/0023); family routing then operates on the selected set. The
   selection call is a distinct, small structured-output call that returns entity
   IDs, not a chart spec — so it composes with both the current per-family
   planner and the future capability-envelope planner. Whether selection,
   family, and chart-spec eventually collapse into a single envelope call (one
   round-trip) is left open (see Open) and tracked with ADR-0023.

4. **D4 — Enforcement unchanged.** Selection widens *which approved entity is
   chosen*, never *what data may be touched*. Selected entities validate against
   the allowlist; out-of-allowlist selections fail closed. Invariant #1's
   allowlist enforcement and ADR-0008 (read-only / sandbox) are untouched.

5. **D5 — Clarification remains the honest fallback.** Clarification is not
   removed; it is demoted from "first response to any multi-match" to "last
   resort when confident resolution is impossible." A genuinely ambiguous prompt
   ("which thermostat?") still asks, because guessing there *would* be a silent
   guess.

## Rationale

- The safety property of invariant #1 is *allowlist membership*, not *always
  clarify on multiple matches*. Selecting the uniquely best-specified approved
  entity touches only approved data — it is not the silent guess the invariant
  forbids. The UX rule (clarify) was a proxy for "don't guess"; specificity
  ranking is a more faithful proxy.
- Token *count* is a cheap, deterministic, language-agnostic-enough signal that
  separates the two real cases (false vs genuine ambiguity) without a model
  round-trip, keeping the common case instant.
- The model is the right tool for the residue, exactly as in ADR-0023; gating it
  behind the deterministic fast-path avoids a ~tens-of-seconds local-model call
  on every obvious prompt.
- Staging (D1 now, D2 next) lets the immediate live-testing pain close
  this packet while the larger model-selection plumbing — which interacts with
  the ADR-0023 envelope — gets its own spec/BDD/eval.

## Consequences

**Enables:**
- "kitchen door" stops demanding "door or ecobee?"; shared-word prompts resolve
  to the specifically-named entity.
- A clean staged path to true model-driven selection without reopening allowlist
  safety.

**Constrains:**
- The specificity tie-break is still a heuristic; genuinely novel phrasings that
  share all tokens, or name nothing distinctive, fall through to D2 / clarify
  (by design — that is the residue the model or the user should resolve).
- D2 adds a model round-trip on the ambiguous path (mitigated by the timeout
  raise shipping alongside D1, and by the fast-path handling the common case).

**Open:**
- Whether D2's selection call should fold into the ADR-0023 capability-envelope
  call (select entities + family + spec in one round-trip) or stay a distinct
  pre-routing call. Lean: distinct first (smaller, testable), converge later if
  the double round-trip hurts.
- Exact specificity scoring details (stopwords, token weighting, minimum
  distinctive-token length) — pinned in the spec + BDD for D2; D1 reuses the
  existing meaningful-token extraction with a count instead of a boolean.
- Whether to surface the model's chosen-entity reasoning to the card (ties to the
  planner reasoning-feedback question — see HANDOFF open items).

## Relationship to invariant #1 and ADR-0023

This ADR **refines invariant #1's disambiguation behavior** (clarify is the
fallback, not the first response) while leaving its **allowlist-enforcement
safety property unchanged**. It is the entity-selection sibling of ADR-0023's
family-selection envelope: both move an *intent* decision from a rigid
deterministic guard to the model, fenced by a deterministic safety boundary the
integration owns (allowlist here; capability envelope there).

## Alternatives considered

- *Keep any-token matching.* Rejected: it is the direct cause of the
  clarify-on-every-prompt rigidity.
- *Strict all-token matching* (require every entity token in the prompt).
  Rejected: too strict — it breaks the genuine "show thermostat history" case
  (each thermostat matches only the shared `thermostat` token, so neither would
  match at all) and demands users recite full entity labels.
- *Endless stopword / weighting tuning.* Rejected: brittle, English-only, and
  exactly the deterministic-intent-reading treadmill ADR-0023 moves away from.
- *Pure model selection on every prompt (no fast-path).* Rejected: a
  tens-of-seconds local-model round-trip for an obvious single match is poor UX;
  the deterministic fast-path keeps the common case instant.

## References

- ADR-0003 (entity allowlist), ADR-0008 (read-only MVP / sandbox), ADR-0006
  (deterministic plan validation), ADR-0022 (render-family routing / overlay
  composition), ADR-0023 (model-proposed render family within a capability
  envelope — sibling decision).
- `custom_components/isolinear/job_orchestration.py` —
  `select_prompt_entity_ids`, `_catalog_item_matches_prompt`.
- Invariant #1 in `CLAUDE.md` / `AGENTS.md` (disambiguation refined; allowlist
  enforcement unchanged).
