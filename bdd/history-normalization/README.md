# History Normalization BDD

Scenarios for normalizing Home Assistant history data (numeric strings, missing states, data quality).

## Scenarios

- **Numeric string normalization** — Numeric history values stored as strings are converted to floats.
- **Missing state handling** — `unknown` and `unavailable` states are normalized to null with point-quality metadata.
- **Data quality warnings** — Series-level warnings are emitted for data quality issues (e.g., sparse data).

## Related docs

- Spec: [docs/specs/history-normalization-spec.md](../../docs/specs/history-normalization-spec.md)
- ADR: [docs/decisions/0005-schema-driven-contracts-and-history-normalization.md](../../docs/decisions/0005-schema-driven-contracts-and-history-normalization.md)
- Source scenarios: [docs/bdd/history-normalization.feature](../../docs/bdd/history-normalization.feature)
- Paired BDD: [history-normalization-bdd.md](history-normalization-bdd.md)
- Evidence: [history-normalization-evidence.md](history-normalization-evidence.md)

## Validation

Evidence for these scenarios is produced by:

- `evals/numeric_history_normalization.py` — Numeric string and missing-state normalization
- `evals/binary_state_interval_extraction.py` — Binary state history (on/off) normalization
- `tests/test_fake_vertical_slice.py` — History series validation and quality checks

## Evidence format

Executable evals and unit tests provide deterministic behavior checks. Paired markdown evidence captures the raw commands, outputs, fixtures, and observed results for review.
