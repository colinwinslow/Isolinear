# Semantic Memory BDD

Scenarios for semantic alias creation, storage, reuse, and invalidation.

## Scenarios

- **Threshold alias creation** — User saves a threshold rule (e.g., "dishwasher running = power > 5W") as a semantic alias.
- **Alias reuse** — Saved aliases are reused without re-prompting when the entity is still available and allowlisted.
- **Alias invalidation** — When a saved alias references an unavailable or non-allowlisted entity, clarification or `cannot_resolve` is returned instead of silent reuse.

## Related docs

- Spec: [docs/specs/semantic-memory-spec.md](../../docs/specs/semantic-memory-spec.md)
- ADR: [docs/decisions/0009-semantic-memory-storage.md](../../docs/decisions/0009-semantic-memory-storage.md)
- Source scenarios: [docs/bdd/semantic-memory.feature](../../docs/bdd/semantic-memory.feature)
- Paired BDD: [threshold-alias-lifecycle-bdd.md](threshold-alias-lifecycle-bdd.md)
- Evidence: [threshold-alias-lifecycle-evidence.md](threshold-alias-lifecycle-evidence.md)
- Paired BDD: [semantic-alias-invalidation-bdd.md](semantic-alias-invalidation-bdd.md)
- Evidence: [semantic-alias-invalidation-evidence.md](semantic-alias-invalidation-evidence.md)

## Validation

Evidence for these scenarios is produced by:

- `evals/threshold_interval_use_and_remember.py` — Semantic alias creation (saved, returned to user)
- `evals/threshold_interval_alias_reuse.py` — Deterministic alias reuse without re-prompting
- `evals/semantic_alias_invalidation.py` — Alias invalidation when entity is unavailable or non-allowlisted

## Evidence format

Executable evals provide deterministic behavior checks. Paired markdown evidence captures the raw commands, outputs, fixtures, and observed results for review.
