# BDD Evidence Backfill Inventory

Run timestamp: 2026-06-01 10:19:02 -07:00

Purpose: identify implemented eval-backed scenarios that lacked paired
`bdd/<feature>/*-bdd.md` and `bdd/<feature>/*-evidence.md` files before this
backfill.

## Raw Inventory Commands

Eval inventory command:

```powershell
rg --files evals
```

Raw output:

```text
evals\threshold_interval_use_once.py
evals\threshold_interval_use_and_remember.py
evals\threshold_interval_inference.py
evals\threshold_interval_extraction.py
evals\threshold_interval_alias_reuse.py
evals\shaded_interval_rendering.py
evals\semantic_alias_invalidation.py
evals\prompt_to_chart_basic.py
evals\plan_validation_rejects_hidden_entity.py
evals\numeric_history_normalization.py
evals\missing_overlay_validation.py
evals\evidence.py
evals\binary_state_interval_extraction.py
```

Paired BDD/evidence inventory command:

```powershell
rg --files bdd | rg "(-bdd|-evidence)\.md$"
```

Raw output before backfill:

```text
bdd\semantic-memory\semantic-alias-invalidation-bdd.md
bdd\semantic-memory\semantic-alias-invalidation-evidence.md
```

## Backfill Groups

| Group | New BDD | New evidence | Fresh evals |
|---|---|---|---|
| Prompt to chart | `bdd/prompt-to-chart/basic-prompt-to-chart-bdd.md` | `bdd/prompt-to-chart/basic-prompt-to-chart-evidence.md` | `evals/prompt_to_chart_basic.py` |
| Entity clarification | `bdd/entity-clarification/threshold-clarification-bdd.md` | `bdd/entity-clarification/threshold-clarification-evidence.md` | `evals/threshold_interval_inference.py` |
| History normalization | `bdd/history-normalization/history-normalization-bdd.md` | `bdd/history-normalization/history-normalization-evidence.md` | `evals/numeric_history_normalization.py`, `evals/binary_state_interval_extraction.py`, `evals/threshold_interval_extraction.py` |
| Rendering | `bdd/rendering/trusted-rendering-bdd.md` | `bdd/rendering/trusted-rendering-evidence.md` | `evals/prompt_to_chart_basic.py`, `evals/shaded_interval_rendering.py`, `evals/trusted_renderer_primitives.py`, `evals/state_interval_timeline.py`, `evals/aggregate_bar_chart.py`, `evals/calendar_hour_heatmap.py`, `evals/event_markers.py`, `evals/distribution_histogram.py`, `evals/scatter_correlation.py` |
| Validation | `bdd/validation/validation-gates-bdd.md` | `bdd/validation/validation-gates-evidence.md` | `evals/prompt_to_chart_basic.py`, `evals/plan_validation_rejects_hidden_entity.py`, `evals/missing_overlay_validation.py` |
| Semantic memory | `bdd/semantic-memory/threshold-alias-lifecycle-bdd.md` | `bdd/semantic-memory/threshold-alias-lifecycle-evidence.md` | `evals/threshold_interval_use_once.py`, `evals/threshold_interval_use_and_remember.py`, `evals/threshold_interval_alias_reuse.py` |

Existing paired evidence retained:

- `bdd/semantic-memory/semantic-alias-invalidation-bdd.md`
- `bdd/semantic-memory/semantic-alias-invalidation-evidence.md`
