# Validation Gates BDD

Validation gates prevent unsafe or incomplete chart jobs from rendering and
catch renderer output drift before a result is accepted.

Evidence file:
`bdd/validation/validation-gates-evidence.md`

Related artifacts:

- Source feature: `docs/bdd/validation-loop.feature`
- Spec: `docs/specs/validation-spec.md`
- ADR: `docs/decisions/0005-schema-driven-contracts-and-history-normalization.md`
- ADR: `docs/decisions/0006-validation-and-repair-loop.md`
- Evals:
  - `evals/prompt_to_chart_basic.py`
  - `evals/plan_validation_rejects_hidden_entity.py`
  - `evals/missing_overlay_validation.py`

## Scenario: Plan validation rejects non-allowlisted entity

Given a chart spec references `sensor.hidden_temperature`
And that entity is not visible to the agent
When plan validation runs
Then validation should fail
And rendering should not start
And no image artifact should be created

## Scenario: Render metadata validation confirms expected series

Given the chart spec expects `upstairs_temperature` and `downstairs_temperature`
And the render metadata lists both series as plotted
When render metadata validation runs
Then deterministic validation should pass

## Scenario: Missing overlay fails validation

Given the chart spec expects overlay `dishwasher_running`
And the render metadata contains no plotted overlays
When render metadata validation runs
Then validation should fail with a missing overlay issue

## Proof Requirements

The evidence must include:

- A recent run timestamp.
- The exact eval commands and raw eval outputs.
- The exact unit-test command and raw test output.
- The hidden-entity chart spec, visible allowlist fixture, plotted-series
  metadata, and missing-overlay metadata.
- The observed validation statuses, failing checks, null render objects for
  pre-render failure, artifact count, and passing rendered-series check.
