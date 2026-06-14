# Validation BDD

Scenarios for plan validation, schema checking, overlay validation, and safety gates.

## Scenarios

- **Plan schema validation** — Chart specs must validate against JSON Schema before render.
- **Entity allowlist validation** — Plans can only reference allowlisted entities.
- **Overlay validation** — Rendered chart must include all overlays specified in the plan.

## Related docs

- Spec: [docs/specs/validation-spec.md](../../docs/specs/validation-spec.md)
- ADR: [docs/decisions/0005-schema-driven-contracts-and-history-normalization.md](../../docs/decisions/0005-schema-driven-contracts-and-history-normalization.md)
- ADR: [docs/decisions/0006-validation-and-repair-loop.md](../../docs/decisions/0006-validation-and-repair-loop.md)
- Source scenarios: [docs/bdd/validation-loop.feature](../../docs/bdd/validation-loop.feature)
- Paired BDD: [validation-gates-bdd.md](validation-gates-bdd.md)
- Evidence: [validation-gates-evidence.md](validation-gates-evidence.md)

## Validation

Evidence for these scenarios is produced by:

- `evals/plan_validation_rejects_hidden_entity.py` — Pre-render validation gates (schema + allowlist)
- `evals/missing_overlay_validation.py` — Post-render overlay validation (all expected overlays rendered)
- `tests/test_fake_vertical_slice.py` — Schema validation and deterministic failure paths

## Evidence format

Executable evals and unit tests provide deterministic behavior checks. Paired markdown evidence captures the raw commands, outputs, fixtures, and observed results for review.
