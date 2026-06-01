# Prompt-to-Chart BDD

Scenarios for the end-to-end flow from user prompt to rendered chart.

## Scenarios

- **Prompt to basic chart** — User asks a natural-language question; agent plans, validates, and renders a chart.

## Related docs

- Spec: [docs/specs/product-spec.md](../../docs/specs/product-spec.md)
- Source scenarios: [docs/bdd/prompt-to-chart.feature](../../docs/bdd/prompt-to-chart.feature)

## Validation

Evidence for these scenarios is produced by:

- `evals/prompt_to_chart_basic.py` — Full end-to-end flow validation
- `evals/threshold_interval_inference.py` — Threshold clarification proposal
- `evals/threshold_interval_use_once.py` — Use-once confirmation path
- `evals/threshold_interval_use_and_remember.py` — Semantic alias creation and return
- `evals/threshold_interval_alias_reuse.py` — Saved alias reuse without re-prompting

## Note on evidence format

Isolinear uses executable Python evals rather than markdown evidence files. Each eval produces deterministic proof that the scenario was hit and the expected behavior occurred.
