# BDD Tree

Behavior scenarios live here, grouped by feature: `bdd/<feature>/`, each with a `README.md` explaining the scenarios and their validation.

## Structure

```
bdd/
  prompt-to-chart/          # End-to-end: user prompt → chart render
  entity-clarification/     # Entity allowlist enforcement and clarification
  semantic-memory/          # Semantic alias creation, reuse, invalidation
  validation/               # Plan validation, schema checks, overlay validation
  rendering/                # Chart rendering, dashboard display
  dashboard-card/           # Home Assistant dashboard card shell and UI flow
  sandbox-codegen/          # Sandboxed code generation and safety
  history-normalization/    # Data normalization and quality
  README.md (this file)
```

## BDD format: Gherkin + Evals

Isolinear uses two complementary approaches:

### 1. **Gherkin scenarios** (docs/bdd/*.feature)

Written in Gherkin (Given/When/Then) format, these define the contract of each feature. Examples:
- `docs/bdd/prompt-to-chart.feature` — User prompt flow
- `docs/bdd/entity-allowlist.feature` — Entity resolution and allowlist enforcement
- `docs/bdd/semantic-memory.feature` — Alias creation and reuse

These live in `docs/bdd/` and are referenced by the feature folders below.

### 2. **Executable evals** (evals/*.py)

Each scenario is validated by one or more executable Python eval scripts. Evals produce **deterministic proof** — they show the exact input, exact output, and verification that the scenario was hit.

Unlike markdown evidence files, evals are **runnable** and **reproducible**. They can be re-run to confirm behavior at any time.

Examples:
- `evals/prompt_to_chart_basic.py` — Full prompt→chart flow
- `evals/plan_validation_rejects_hidden_entity.py` — Entity allowlist enforcement
- `evals/threshold_interval_alias_reuse.py` — Semantic alias reuse

## Feature folder organization

Each `bdd/<feature>/README.md` lists:
- The scenarios it covers (referencing `docs/bdd/*.feature`)
- The related specs and ADRs
- Which evals validate each scenario

### Example: bdd/semantic-memory/

```markdown
# Semantic Memory BDD

## Scenarios

- **Threshold alias creation** — [scenario from docs/bdd/semantic-memory.feature]
- **Alias reuse** — [scenario from docs/bdd/semantic-memory.feature]
- **Alias invalidation** — [scenario from docs/bdd/semantic-memory.feature]

## Validation

- `evals/threshold_interval_use_and_remember.py` — Alias creation
- `evals/threshold_interval_alias_reuse.py` — Alias reuse
- `evals/semantic_alias_invalidation.py` — Invalidation
```

When a new scenario is implemented:

1. Ensure it's covered in the relevant `docs/bdd/*.feature` file.
2. Create or update the corresponding eval(s) in `evals/`.
3. Update the feature folder's `README.md` to list the eval.

## BDD-evidence review

The architecture review pass (`codex/review-bdd-evidence.md`) checks:
- Scenarios in the BDD match scenarios in the evals
- Evidence is raw output (not summaries)
- Evals pass and prove each scenario was hit

## Paired Markdown Evidence

The kit template uses markdown Given/When/Then format (`bdd/<feature>/<slug>-bdd.md`). Isolinear keeps source Gherkin scenarios in `docs/bdd/` and now backfills paired markdown BDD/evidence files for implemented eval-backed slices:

1. Create `bdd/<feature>/<slug>-bdd.md` with Given/When/Then scenarios.
2. Create `bdd/<feature>/<slug>-evidence.md` with raw eval output or test logs.
3. The feature folder `README.md` references both.

Feature folders document the Gherkin scenarios, paired markdown BDD/evidence files, and their evals.

