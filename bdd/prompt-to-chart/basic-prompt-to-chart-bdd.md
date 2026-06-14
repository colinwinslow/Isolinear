# Basic Prompt-to-Chart BDD

The prompt-to-chart slice turns a natural-language temperature comparison into
a validated chart using only approved Home Assistant entity history.

Evidence file:
`bdd/prompt-to-chart/basic-prompt-to-chart-evidence.md`

Related artifacts:

- Source feature: `docs/bdd/prompt-to-chart.feature`
- Spec: `docs/specs/product-spec.md`
- Eval: `evals/prompt_to_chart_basic.py`

## Scenario: Compare two temperature entities over the last 24 hours

Given `sensor.upstairs_temperature` and `sensor.downstairs_temperature` are
visible to the agent
And normalized history exists for both entities over the last 24 hours
When the user prompts `Compare upstairs and downstairs temperatures over the last 24 hours`
Then the planner should return `chart_spec_ready`
And the chart spec should be a `time_series`
And the chart spec should include both approved temperature entities
And the chart spec should use a relative `24h` time range
And the trusted renderer should create a PNG image in safe mode
And deterministic validation should pass

## Proof Requirements

The evidence must include:

- A recent run timestamp.
- The exact eval command and raw eval output.
- The exact unit-test command and raw test output.
- The prompt fixture and time anchor.
- The observed planner status, chart type, series entity IDs, render mode,
  render status, image MIME type, plotted series, and validation checks.
