---
status: draft
date: 2026-07-06
depends-on-adrs: [0030, 0031, 0034]
---

# Planner re-plan on validation failure: bounded structural retry for planner-quality rejections

## Status

Draft. Defines the contract surface for a bounded re-plan loop around the
model-provider planning gate. Open-queue item (u), 17th session.

**ADR note.** This is deliberately spec-level, not a new ADR. It introduces no
new service, store, schema, or queue (invariant #8); it is a bounded, revertible
retry loop around the *existing* planner client and the *existing* validation
gates — structurally the same lever ADR-0030 already blesses for codegen
(`max_codegen_repair_attempts`, a capped repair loop), applied to the planning
stage. If Colin wants it recorded as a decision, promote it to an ADR before
acceptance; flagged for his call.

## Related docs

- [bdd/integration/planner-replan-on-validation-failure-bdd.md](../../bdd/integration/planner-replan-on-validation-failure-bdd.md) — observable behavior
- [STATUS.md](../../STATUS.md) — current phase and active work (open-queue (u))
- [docs/decisions/0034-analysis-intent-reaches-codegen.md](../decisions/0034-analysis-intent-reaches-codegen.md) — the analysis conduit whose live run surfaced the variance tails

## Context

The live e2e harness (16th/17th sessions) exposed planner **variance tails**:
individual gemma4:e4b samples that fail a post-plan validation gate where a
re-sample would land a valid plan. The observed one is e2e-18 — a sample plans a
computed result ("Deviation") as its own series; constrained decoding, whose
`source.entity_id` enum holds only approved ids, forces it onto an already-used
entity, and the duplicate-series-source contract check rejects the plan
(`invalid_model_provider_chart_spec`). Today `_record_model_provider_plan` plans
**once** and returns the failure code terminally — so a single unlucky sample
falls straight through to the surfaced Pillow fallback (or a card failure), even
though the very next sample would have been valid.

The 17th session closed e2e-18 by *prompt hardening* (a satisfiability rule
forbidding the computed result as a series). That works for the known case but is
prompt-by-prompt whack-a-mole: the next relabel/reuse variance tail needs another
rule. The structural fix is one bounded, deterministic **re-plan**: on a
planner-*output-quality* rejection, re-invoke the planner up to a small cap and
re-run the same gates, keeping the first plan that validates. This is the
planning-stage analogue of the codegen repair loop and matches ADR-0035's
"structural over prompt-by-prompt" through-line.

### What re-plan must NOT do (design boundary)

`clarification_needed` (and `cannot_resolve`) are **legitimate** planner terminals
(planner-result schema `status` enum: `chart_spec_ready` | `clarification_needed`
| `cannot_resolve`). Because `validate_planner_result_contract` runs *before* the
status gate, any plan that reaches the `model_provider_planner_not_chart_spec_ready`
rejection is schema-valid and therefore necessarily carries a non-ready but
legitimate status — the model's deliberate choice to ask the user or to decline.
**Re-planning that gate would override that correct choice**, so it is excluded
from the slice-1 trigger set. (Confirmed live via `scripts/repro_e2e14.py`:
e2e-14 fails at `model_provider_planner_not_chart_spec_ready` because entity
resolution disclosed only the temperature sensor — the planner then *correctly*
clarified that the kitchen-humidity sensor is required, and plans a valid
two-series correlation once both are disclosed. Re-planning would fight that
correct clarification; the real fix is in entity resolution, tracked separately.)

## Behavior contract

### Trigger set (slice 1)

Re-plan fires only on rejections that unambiguously mean "the model produced
broken output," never a legitimate terminal:

- `invalid_model_provider_chart_spec` — `validate_chart_spec_contract` rejected
  the planned (or overlay-composed) ChartSpec. The named e2e-18 case.
- `invalid_planner_result` — the raw planner result failed
  `validate_planner_result_contract` (malformed / schema-invalid model output).

Explicitly **terminal in slice 1** (no re-plan): `model_provider_planner_not_chart_spec_ready`
(a legitimate `clarification_needed`, see boundary above); `mixed_chart_composition_unsupported`
and `model_provider_planner_not_configured` (deterministic, re-sampling cannot
change them); the model-provider transport-retry codes already handled by
`_record_model_provider_retry_policy`; the family-envelope and output-entity
gates (candidate additions pending harness evidence — see Non-goals).

### The loop

`_record_model_provider_plan` gains a bounded loop around the planner invocation
(job_orchestration.py:3531) through the validation gates:

- Attempt 1 is today's behavior, unchanged.
- On a trigger-set rejection, re-invoke `planner.plan_chart` with the **same
  request and result schema** (a fresh sample — slice 1 does not feed the
  rejection back into a corrective prompt; see Non-goals) and re-run the gates.
- Cap total attempts at `1 + max_planner_replan_attempts`. On exhaustion, return
  the **last** attempt's failure result unchanged (same code, same `validation`),
  so no failure surface changes when re-plan doesn't help.
- The first attempt whose gates all pass proceeds exactly as today.
- Reasoning streaming (ADR-0025) continues to stream from each attempt into the
  per-job live slot; a re-plan does not blank the card.

### Config knob

New option `max_planner_replan_attempts`, mirroring `max_codegen_repair_attempts`:

- `job_orchestration.py`: `_configured_max_planner_replan_attempts(hass, entry_id)`
  reader, mirroring `_configured_max_codegen_repair_attempts`, clamped to `>= 0`
  (0 = today's single-attempt behavior, a clean revert switch).
- **Slice-1 default = 0 (opt-in).** The loop lands purely additive: with the
  reader defaulting to 0, no existing behavior changes and the full suite stays
  green (several existing failure-path tests assert exactly one planner call).
  Promoting the default to **1** (feature on) is a deliberate follow-up — it
  requires updating those call-count assertions to the exhaustion count and is
  naturally bundled with open-queue (m) (raise `max_codegen_repair_attempts`
  too). New tests set the option explicitly to exercise the loop.
- **Then** `config_schema.py` (typed field + default) + `config_flow.py`
  (options-flow integer field beside the codegen tunables) wire the user-facing
  surface — done as part of the default-promotion step so config validation and
  the effective default move together.

### Observability

The returned plan result carries `planner_replan_attempts` (int, count of extra
samples taken; 0 when the first plan validated). On a re-plan that eventually
succeeds, an INFO log records the recovered code + attempt count; on exhaustion,
the existing failure WARNING additionally carries the attempt count. No new
secret crosses any boundary (the request is the already-projected planner
request).

## Anchor artifact

A single unit test: `_record_model_provider_plan`, given a stub planner whose
first sample yields a ChartSpec that fails `validate_chart_spec_contract`
(duplicate series source) and whose second sample yields a valid ChartSpec,
returns `accepted: True` with `planner_replan_attempts == 1` — proving one bad
sample is recovered by one re-plan, no prompt change.

## Implementation order

1. Anchor test above (red).
2. `_configured_max_planner_replan_attempts` reader (default **0** — opt-in; see
   Config knob). No `config_schema.py`/`config_flow.py` change in slice 1.
3. Wrap the planner-call → validation-gates span in the bounded loop; trigger set
   as specified; `planner_replan_attempts` on the result. (green)
4. Exhaustion + clarification-exclusion + zero-attempts-revert tests.
5. **Default-promotion follow-up (bundled with (m)):** flip the reader default to
   1, wire `config_schema.py` (typed field + default) + `config_flow.py`
   (options-flow field + coercion), and update the existing failure-path tests'
   call-count assertions to the exhaustion count.
6. Live/eval proof: re-run the e2e harness (or `analysis_intent_probe`-style
   sampling) on the e2e-18-class prompt and confirm the duplicate-source variance
   tail recovers without the 0.2.24 satisfiability prompt rule (i.e. the
   structural loop subsumes the prompt patch for this class).

## Proof requirements

1. Unit tests in `tests/test_planner_replan_on_validation_failure.py` green:
   anchor (recover on re-plan), exhaustion returns last failure unchanged,
   `clarification_needed` is never re-planned, `max_planner_replan_attempts=0`
   reproduces today's single-attempt behavior byte-for-byte, non-trigger codes
   (e.g. `mixed_chart_composition_unsupported`) are not re-planned.
2. BDD scenarios in bdd/integration/planner-replan-on-validation-failure-bdd.md
   pass, with an evidence file carrying raw test output.
3. Full suite green; evals `codegen_generation_path` + `model_authored_analysis`
   still PASS.
4. Real-artifact proof: the e2e-18-class duplicate-source variance tail recovers
   via re-plan against live gemma (recorded in the evidence file).

## Non-goals

- **Corrective re-plan** (feeding the validation error back into a re-plan prompt,
  codegen-repair-style). Slice 1 is a plain re-sample — the minimal structural
  change. Corrective re-plan is a tranche-2 candidate once the harness shows which
  tails are systematic vs. variance.
- **Closing e2e-14** (cross-metric correlation): confirmed live to be an entity-
  **resolution** gap (the kitchen-humidity sensor — friendly name "Kitchen ecobee
  Humidity" — is never disclosed to the planner), not a planner or re-plan
  problem. The planner correctly clarifies and plans a valid two-series
  correlation when both sensors are disclosed. Tracked as a separate resolution
  bug, not by this loop.
- **Re-planning the family-envelope or output-entity gates.** Candidate trigger
  additions, deferred until harness evidence shows they carry recoverable variance
  rather than systematic model errors.
- **Unbounded / adaptive retry.** The cap is a small fixed config value.

## References

- ADR-0030 (codegen primary; the capped-repair-loop precedent this mirrors)
- ADR-0034 (the analysis conduit whose live run surfaced the variance tails)
- ADR-0035 §demolition (structural-over-prompt-by-prompt; this loop lives in
  job_orchestration.py, a demolition-step-1 split target — keep it on the
  planning seam so the later split carries it cleanly)
- `docs/specs/codegen-generation-path.md` (the repair-loop shape this parallels)
