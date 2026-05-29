# History Normalization Spec

## Purpose

Home Assistant history must be converted into chart-ready internal data structures before rendering.

## Inputs

- Home Assistant history records.
- Entity catalog metadata.
- ChartSpec source references.
- Semantic aliases and derived rules.

## Output types

- `HistorySeries` for numeric, binary, categorical, or event-like series.
- `DerivedInterval` for state intervals and threshold-derived intervals.

## Numeric normalization

For numeric sensors:

- Convert numeric strings to numbers.
- Treat `unknown` and `unavailable` as missing values.
- Preserve timestamps and timezone.
- Preserve raw state for debugging.
- Preserve unit of measurement.
- Emit data quality warnings for gaps or invalid values.

## Binary/state interval extraction

For binary or categorical state entities:

- Convert state changes into intervals.
- Use the requested active values when supplied.
- End the final interval at the requested time-range end.
- Preserve state labels and reasons.

## Threshold interval extraction

For continuous sensors used as running indicators:

- Apply a confirmed threshold rule.
- Produce intervals where the threshold condition is true.
- Preserve threshold details in output metadata.

## Aggregation

Aggregates should be deterministic and should document:

- Source entity IDs.
- Operation, such as mean, min, max, sum, or count.
- Resampling interval, if any.
- Missing-data policy.

## Warnings

Normalization should warn about:

- No data in range.
- Sparse data.
- Unit mismatch.
- Unsupported state values.
- Missing attributes.
- Invalid threshold rule.
