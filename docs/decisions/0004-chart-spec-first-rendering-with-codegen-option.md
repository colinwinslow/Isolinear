# ADR 0004: Chart spec first, with optional sandboxed code generation

## Status

Superseded by [ADR-0030](0030-matplotlib-codegen-primary-render-path.md)
(2026-07-02). The ChartSpec-as-central-contract half of this decision carries
forward unchanged; the trusted-renderer-as-default half is inverted — sandboxed
matplotlib codegen is now the primary render path.

## Context

The product needs flexibility, but arbitrary generated Python is risky and hard to validate. Many common visualizations can be rendered from structured chart primitives without free-form code execution.

## Decision

All chart requests first produce a `ChartSpec`: a structured visualization plan. The default renderer is a trusted deterministic renderer that turns `ChartSpec` plus normalized data into an image.

An advanced codegen mode may ask the model to write matplotlib code, but the generated code must implement a validated `ChartSpec` and run only inside the sandboxed worker contract.

## Consequences

Positive:

- Safer default path.
- Testable renderer.
- Concrete validation target.
- Codegen remains available for advanced use.

Negative:

- Trusted renderer must grow chart primitive support over time.
- Some custom charts may require codegen.
- Planner quality matters because `ChartSpec` is the central contract.
