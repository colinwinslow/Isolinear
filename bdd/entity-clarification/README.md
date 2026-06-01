# Entity Clarification BDD

Scenarios for entity resolution, allowlist enforcement, and user clarification when entity mapping is ambiguous.

## Scenarios

- **Entity allowlist enforcement** — Only allowlisted entities can be referenced in plans.
- **Entity clarification** — When a prompt could map to multiple entities, the agent asks for clarification.
- **Hidden entity rejection** — Plans referencing non-allowlisted entities are rejected pre-render.

## Related docs

- Spec: [docs/specs/entity-resolution-spec.md](../../docs/specs/entity-resolution-spec.md)
- Spec: [docs/specs/security-spec.md](../../docs/specs/security-spec.md)
- Source scenarios: [docs/bdd/entity-allowlist.feature](../../docs/bdd/entity-allowlist.feature)
- Source scenarios: [docs/bdd/entity-clarification.feature](../../docs/bdd/entity-clarification.feature)
- Paired BDD: [threshold-clarification-bdd.md](threshold-clarification-bdd.md)
- Evidence: [threshold-clarification-evidence.md](threshold-clarification-evidence.md)

## Validation

Evidence for these scenarios is produced by:

- `evals/plan_validation_rejects_hidden_entity.py` — Hidden-entity rejection validation
- `evals/threshold_interval_inference.py` — Threshold clarification proposal
- `tests/test_fake_vertical_slice.py` — Allowlist enforcement and validation gates

## Evidence format

Executable evals and unit tests provide deterministic behavior checks. Paired markdown evidence captures the raw commands, outputs, fixtures, and observed results for review.
