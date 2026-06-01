# Semantic Memory BDD

Scenarios for semantic alias creation, storage, reuse, and invalidation.

## Scenarios

- **Threshold alias creation** — User saves a threshold rule (e.g., "dishwasher running = power > 5W") as a semantic alias.
- **Alias reuse** — Saved aliases are reused without re-prompting when the entity is still available and allowlisted.
- **Alias invalidation** — When a saved alias references an unavailable or non-allowlisted entity, clarification is triggered instead of silent reuse.

## Related docs

- Spec: [docs/specs/semantic-memory-spec.md](../../docs/specs/semantic-memory-spec.md)
- ADR: [docs/decisions/0009-semantic-memory-storage.md](../../docs/decisions/0009-semantic-memory-storage.md)
- Source scenarios: [docs/bdd/semantic-memory.feature](../../docs/bdd/semantic-memory.feature)

## Validation

Evidence for these scenarios is produced by:

- `evals/threshold_interval_use_and_remember.py` — Semantic alias creation (saved, returned to user)
- `evals/threshold_interval_alias_reuse.py` — Deterministic alias reuse without re-prompting
- (TBD) `evals/semantic_alias_invalidation.py` — Alias invalidation when entity is unavailable

## Note on evidence format

Isolinear uses executable Python evals rather than markdown evidence files. Each produces deterministic proof that the scenario was hit and the expected behavior occurred.
