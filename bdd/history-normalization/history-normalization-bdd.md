# History Normalization BDD

Home Assistant history is normalized into schema-valid numeric series and
derived intervals before rendering.

Evidence file:
`bdd/history-normalization/history-normalization-evidence.md`

Related artifacts:

- Source feature: `docs/bdd/history-normalization.feature`
- Spec: `docs/specs/history-normalization-spec.md`
- ADR: `docs/decisions/0005-schema-driven-contracts-and-history-normalization.md`
- Evals:
  - `evals/numeric_history_normalization.py`
  - `evals/binary_state_interval_extraction.py`
  - `evals/threshold_interval_extraction.py`

## Scenario: Numeric history converts string states and missing states

Given Home Assistant history for `sensor.upstairs_temperature` includes numeric
string states, `unknown`, and `unavailable`
When the normalizer processes the history
Then numeric strings should become numbers
And `unknown` and `unavailable` should become null values
And point quality and warnings should explain the missing values

## Scenario: Binary state history becomes active intervals

Given `binary_sensor.dishwasher` changes from `off` to `on` and later to `off`
When the normalizer extracts intervals where state is `on`
Then the output should contain one `dishwasher_running` derived interval
And the trusted renderer should plot that interval as an overlay
And deterministic validation should pass

## Scenario: Continuous sensor becomes threshold intervals after confirmation

Given `sensor.dishwasher_power` has a confirmed running rule `value > 5 W`
When the normalizer extracts threshold intervals
Then the output should contain one `dishwasher_running` derived interval
And the trusted renderer should plot that interval as an overlay
And deterministic validation should pass

## Proof Requirements

The evidence must include:

- A recent run timestamp.
- The exact eval commands and raw eval outputs.
- The exact unit-test command and raw test output.
- The raw numeric records, binary state history, dishwasher power history, and
  threshold fixture.
- The observed normalized values, qualities, warnings, derived intervals,
  plotted overlays, and validation statuses.
