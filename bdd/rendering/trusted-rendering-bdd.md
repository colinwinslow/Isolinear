# Trusted Rendering BDD

The trusted renderer turns validated chart specs, normalized history, and
derived intervals into PNG artifacts with deterministic render metadata.

Evidence file:
`bdd/rendering/trusted-rendering-evidence.md`

Related artifacts:

- Source feature: `docs/bdd/chart-spec-rendering.feature`
- Spec: `docs/specs/chart-spec-rendering-spec.md`
- ADR: `docs/decisions/0004-chart-spec-first-rendering-with-codegen-option.md`
- Evals:
  - `evals/trusted_renderer_primitives.py`
  - `evals/state_interval_timeline.py`
  - `evals/prompt_to_chart_basic.py`
  - `evals/shaded_interval_rendering.py`

## Scenario: Render a multi-series time chart

Given a valid chart spec with two approved numeric time-series
And normalized history exists for both series
When the worker renders in safe mode
Then it should create a PNG image
And render metadata should list both plotted series
And deterministic validation should pass

## Scenario: Render shaded intervals

Given a valid chart spec with a numeric series and a state interval overlay
And derived intervals exist for the overlay
When the worker renders in safe mode
Then render metadata should list `dishwasher_running` as plotted
And deterministic validation should pass

## Scenario: Reject unsupported safe-mode primitive without codegen

Given a valid chart spec that asks the trusted renderer for an unsupported
primitive
When the worker renders in safe mode
Then it should return `unsupported_chart_spec`
And render metadata should report zero codegen attempts
And no image artifact should be created

## Scenario: Render a state interval timeline

Given a valid `timeline` chart spec with one approved binary-state track
And a matching `DerivedInterval` exists for that track
When the worker renders in safe mode
Then it should create a PNG image
And render metadata should list `dishwasher_state` as plotted
And render metadata should report zero codegen attempts
And deterministic validation should pass

## Proof Requirements

The evidence must include:

- A recent run timestamp.
- The exact eval commands and raw eval outputs.
- The exact unit-test command and raw test output.
- The trusted renderer primitive scope.
- The selected follow-up renderer family and scope.
- The chart spec and derived interval fixtures.
- The observed render status, PNG MIME type, render metadata, plotted series or
  overlays, and validation checks.
