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

## Validation

Evidence for these scenarios is produced by:

- `evals/plan_validation_rejects_hidden_entity.py` — Hidden-entity rejection validation
- `tests/test_fake_vertical_slice.py` — Allowlist enforcement and validation gates

## Note on evidence format

Isolinear uses executable Python evals and unit tests rather than markdown evidence files. Each produces deterministic proof that the scenario was hit and the expected behavior occurred.
