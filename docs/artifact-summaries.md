# Artifact Summaries

## `AGENTS.md`

Operating rules for Codex and other coding agents. It explains the project identity, required startup behavior, safety rules, rendering rules, testing rules, and closeout report format.

## `HANDOFF.md`

Continuity file for agentic engineering sessions. It records current phase, architecture direction, open design details, and the next recommended work packet.

## `codex/startup.md`

The ritual a coding agent should run at the beginning of a session. It forces the agent to read the project contract before editing files.

## `codex/closeout.md`

The ritual a coding agent should run before ending a session. It forces tests, evals, drift checks, handoff updates, and an audit-friendly closeout summary.

## `docs/mvp-design-readiness-review.md`

The MVP design closeout record. It audits ADR, spec, schema, BDD, eval,
evidence, and anchor coverage; records the readiness verdict for production
integration scaffolding; and names the first production integration packet.

## ADRs

Architecture Decision Records. These lock load-bearing decisions such as integration plus worker, dashboard card first, entity allowlisting, chart-spec-first rendering, schema contracts, validation, local-first model provider, read-only sandbox security, dashboard card technology, and worker transport/authentication.

## Specs

Behavioral prose contracts. These describe what the product, integration, integration API transport/authentication, dashboard card, entity resolver, memory system, renderer, history normalizer, worker, validation layer, model provider, and security model must do.

## BDDs

Concrete Gherkin scenarios plus paired markdown BDD/evidence files for implemented eval-backed slices. These turn fuzzy requirements into testable examples for prompt-to-chart, allowlisting, clarification, memory, normalization, rendering, sandboxing, validation, dashboard UI, and integration transport/authentication.

## Schemas

Machine-checkable JSON contracts used internally by the product. Users do not write these. They constrain model outputs, integration commands and snapshots, worker transport requests, render requests/results, and validation results.

## Evals

Executable Python checks derived from BDD scenarios. They emit deterministic `CASE` output so paired evidence can capture exact fixtures, triggers, observed results, and pass/fail markers.

## `custom_components/isolinear/`

First production Home Assistant custom integration scaffold. It currently
contains the manifest, domain constants, local-first configuration/options data
shape, and schema-aligned WebSocket command-boundary stubs for `isolinear/v1/`
without worker, model-provider, history, semantic-memory, or mutation
orchestration.
