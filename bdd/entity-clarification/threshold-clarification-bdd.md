# Threshold Clarification BDD

Continuous sensors require a deterministic user confirmation before the system
turns a natural-language running state into threshold intervals.

Evidence file:
`bdd/entity-clarification/threshold-clarification-evidence.md`

Related artifacts:

- Source feature: `docs/bdd/entity-clarification.feature`
- Spec: `docs/specs/entity-resolution-spec.md`
- Spec: `docs/specs/security-spec.md`
- Eval: `evals/threshold_interval_inference.py`

## Scenario: Continuous power sensor proposes a threshold confirmation

Given `sensor.dishwasher_power` is visible to the agent
When the user prompts `Mark when the dishwasher was running over the last day`
Then the planner should return `clarification_needed`
And the planner should not create a chart spec yet
And the clarification should ask whether dishwasher running means
`sensor.dishwasher_power > 5 W`
And the clarification option should be rememberable

## Proof Requirements

The evidence must include:

- A recent run timestamp.
- The exact eval command and raw eval output.
- The exact unit-test command and raw test output.
- The prompt and visible entity fixture.
- The observed planner status, null chart spec, clarification question, proposed
  threshold, and `can_remember` flag.
