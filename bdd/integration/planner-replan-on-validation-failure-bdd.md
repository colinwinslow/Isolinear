# Planner re-plan on validation failure — BDD

## Status

Draft. Paired with [docs/specs/planner-replan-on-validation-failure.md](../../docs/specs/planner-replan-on-validation-failure.md).

## Why this BDD exists

A single unlucky planner sample that fails a post-plan contract check should not
fall straight through to the fallback when the next sample would validate. This
pins the bounded, deterministic re-plan — and, critically, that it never
overrides a legitimate `clarification_needed`.

## Scenarios

### Scenario A — happy path: a rejected sample is recovered by one re-plan

**Given** a configured planner and `max_planner_replan_attempts = 1`
**And** the planner's first sample yields a ChartSpec that fails
`validate_chart_spec_contract` (two series citing the same approved
`source.entity_id` — the e2e-18 duplicate-source class)
**And** the planner's second sample yields a contract-valid ChartSpec
**When** `_record_model_provider_plan` runs
**Then** the result is `accepted: True` with the second sample's plan
**And** `planner_replan_attempts == 1`
**And** an INFO log records the recovered code (`invalid_model_provider_chart_spec`)
and the attempt count — the observable artifact.

### Scenario B — exhaustion: the last failure is returned unchanged

**Given** `max_planner_replan_attempts = 1`
**And** every planner sample yields the same contract-failing ChartSpec
**When** `_record_model_provider_plan` runs
**Then** the result is `accepted: False` with code
`invalid_model_provider_chart_spec` and the same `validation` payload a
single-attempt run produces today
**And** `planner_replan_attempts == 1` (the cap was spent)
**And** no failure surface (code, validation, orchestration side effects) differs
from today's terminal behavior — re-plan adds nothing on the failure path.

### Scenario C — clarification is never overridden

**Given** `max_planner_replan_attempts = 3`
**And** the planner returns a schema-valid result with
`status == "clarification_needed"`
**When** `_record_model_provider_plan` runs
**Then** the planner is invoked exactly once (no re-plan)
**And** the result carries `model_provider_planner_not_chart_spec_ready` with
`planner_replan_attempts == 0` — the model's deliberate clarify is preserved.

### Scenario D — zero attempts reproduces today's behavior

**Given** `max_planner_replan_attempts = 0`
**And** the planner's first sample fails `validate_chart_spec_contract`
**When** `_record_model_provider_plan` runs
**Then** the planner is invoked exactly once
**And** the result is the byte-for-byte terminal failure the pre-feature code
returns (`invalid_model_provider_chart_spec`, `planner_replan_attempts == 0`) —
the clean revert switch.

### Scenario E — non-trigger codes are not re-planned

**Given** `max_planner_replan_attempts = 2`
**And** the resolved routing is `mixed` (→ `mixed_chart_composition_unsupported`,
a deterministic rejection re-sampling cannot change)
**When** `_record_model_provider_plan` runs
**Then** the planner is not re-invoked for that code and the failure returns
immediately with `planner_replan_attempts == 0`.

## Evidence

The implementing slice produces an evidence file at
`bdd/integration/planner-replan-on-validation-failure-evidence.md` containing raw
test output (not summaries) for each scenario, plus the raw live-gemma re-plan
recovery for the e2e-18 duplicate-source class (spec Proof requirement #4).
