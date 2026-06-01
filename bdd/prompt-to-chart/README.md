# Prompt-to-Chart BDD

Scenarios for the end-to-end flow from user prompt to rendered chart.

## Scenarios

- **Prompt to basic chart** — User asks a natural-language question; agent plans, validates, and renders a chart.

## Related docs

- Spec: [docs/specs/product-spec.md](../../docs/specs/product-spec.md)
- Source scenarios: [docs/bdd/prompt-to-chart.feature](../../docs/bdd/prompt-to-chart.feature)
- Paired BDD: [basic-prompt-to-chart-bdd.md](basic-prompt-to-chart-bdd.md)
- Evidence: [basic-prompt-to-chart-evidence.md](basic-prompt-to-chart-evidence.md)

## Validation

Evidence for these scenarios is produced by:

- `evals/prompt_to_chart_basic.py` — Full end-to-end flow validation
- `evals/threshold_interval_inference.py` — Threshold clarification proposal
- `evals/threshold_interval_use_once.py` — Use-once confirmation path
- `evals/threshold_interval_use_and_remember.py` — Semantic alias creation and return
- `evals/threshold_interval_alias_reuse.py` — Saved alias reuse without re-prompting

## Evidence format

Executable evals provide deterministic behavior checks. Paired markdown evidence captures the raw commands, outputs, fixtures, and observed results for review.
