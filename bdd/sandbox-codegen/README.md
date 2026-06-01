# Sandbox Codegen BDD

Scenarios for sandboxed code generation, matplotlib rendering, and safety checks.

## Scenarios

- **Sandboxed codegen** — Generated Python runs in a sandbox with no access to HA tokens, secrets, or services.
- **Code safety checks** — Generated code is statically validated before execution.
- **Codegen retry loop** — Failed code generation triggers repair attempts; retries are capped.

## Related docs

- Spec: [docs/specs/worker-sandbox-spec.md](../../docs/specs/worker-sandbox-spec.md)
- Spec: [docs/specs/security-spec.md](../../docs/specs/security-spec.md)
- ADR: [docs/decisions/0004-chart-spec-first-rendering-with-codegen-option.md](../../docs/decisions/0004-chart-spec-first-rendering-with-codegen-option.md)
- ADR: [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../../docs/decisions/0008-read-only-mvp-and-sandbox-security.md)
- Source scenarios: [docs/bdd/sandbox-codegen.feature](../../docs/bdd/sandbox-codegen.feature)

## Validation

Evidence for these scenarios is produced by:

- `evals/codegen_repair_loop.yaml` (outline) — Codegen failure and repair attempts
- `tests/test_fake_vertical_slice.py` — Sandbox safety constraints

## Note on evidence format

Isolinear uses executable Python evals and unit tests rather than markdown evidence files. Sandbox codegen is an advanced feature (non-MVP); execution scenarios are validated in integration tests.
