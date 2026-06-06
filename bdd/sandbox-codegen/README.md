# Sandbox Codegen BDD

Scenarios for sandboxed code generation, matplotlib rendering, and safety checks.

## Scenarios

- **Sandbox policy** — The default codegen policy uses an isolated subprocess,
  stripped environment, fixed output path, import allowlist, timeout, output
  size limit, and Linux resource-limit requests for Raspberry Pi workers.
- **Sandboxed codegen** — Generated Python runs only through
  `render_chart(data, output_path)` and writes only the fixed output image.
- **Matplotlib smoke rendering** — Allowlisted generated code imports
  `matplotlib.pyplot`, renders with the `Agg` backend, and still writes only the
  fixed output image.
- **Code safety checks** — Generated code is statically validated before
  execution and rejects forbidden imports, secret/file reads, environment
  inspection, and local-network access.
- **Codegen retry loop** — Failed code generation triggers repair attempts;
  retries are capped and static checks rerun for every repaired attempt.

## Related docs

- Spec: [docs/specs/worker-sandbox-spec.md](../../docs/specs/worker-sandbox-spec.md)
- Spec: [docs/specs/security-spec.md](../../docs/specs/security-spec.md)
- ADR: [docs/decisions/0004-chart-spec-first-rendering-with-codegen-option.md](../../docs/decisions/0004-chart-spec-first-rendering-with-codegen-option.md)
- ADR: [docs/decisions/0006-validation-and-repair-loop.md](../../docs/decisions/0006-validation-and-repair-loop.md)
- ADR: [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../../docs/decisions/0008-read-only-mvp-and-sandbox-security.md)
- Source scenarios: [docs/bdd/sandbox-codegen.feature](../../docs/bdd/sandbox-codegen.feature)
- Paired BDD: [sandbox-codegen-bdd.md](sandbox-codegen-bdd.md)
- Evidence: [sandbox-codegen-evidence.md](sandbox-codegen-evidence.md)

## Validation

Evidence for these scenarios is produced by:

- `tests/test_codegen_sandbox_anchor.py` — Sandbox policy, static checks,
  fixed entry point, output limits, and capped repair-loop unit coverage
- `evals/codegen_sandbox.py` — Deterministic raw CASE evidence for the paired BDD
- `docs/evals/codegen_repair_loop.yaml` (outline) — Legacy eval outline for
  codegen failure and repair attempts
