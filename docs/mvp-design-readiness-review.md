# MVP Design Readiness Review

Run date: 2026-06-07

## Verdict

READY for the first Home Assistant custom integration scaffold.

The MVP design phase has enough accepted architecture, behavior contracts,
schemas, BDD evidence, and executable anchor coverage to begin production
integration scaffolding. The next packet should still start with a paired BDD
and evidence scaffold, but it does not need another architecture decision
before creating the first `custom_components/isolinear` anchor.

## Review Scope

- ADRs: `docs/decisions/0001-*.md` through `docs/decisions/0012-*.md`.
- Specs: product, integration, integration API transport/authentication,
  dashboard card, entity resolution, history normalization, chart rendering,
  validation, semantic memory, security, model provider, and worker sandbox.
- Schemas: all JSON contracts under `docs/schemas/`.
- BDD and evidence: paired markdown BDD/evidence files under `bdd/` plus source
  Gherkin files under `docs/bdd/`.
- Evals and anchors: executable evals under `evals/`, Python anchors under
  `src/Isolinear/`, and the TypeScript card anchor under `frontend/`.

## Gate Results

| Gate | Result | Evidence |
|---|---|---|
| Architecture decisions | PASS | ADR-0001 through ADR-0012 cover the integration/worker split, card boundary, allowlist, rendering, schemas, validation, local-first provider, read-only sandbox, semantic memory, card technology, and worker transport/authentication. ADR-0012 is accepted in this packet because its schema/test/eval anchor has landed. |
| Behavior contracts | PASS | Specs define the MVP flow, integration responsibilities, card boundary, model-provider roles, security constraints, semantic-memory envelope, validation gates, trusted rendering scope, and worker sandbox. |
| Schema-first contracts | PASS | `ChartSpec`, `HistorySeries`, `DerivedInterval`, `SemanticAlias`, semantic-memory store, render request/result, planner result, validation result, integration WebSocket command, integration job snapshot, worker transport request, and codegen sandbox policy schemas are present. |
| BDD and evidence | PASS | Implemented slices have paired markdown BDD/evidence with raw `CASE` output and PASS markers for prompt-to-chart, validation, history normalization, threshold clarification, semantic memory lifecycle/invalidation/store envelope, trusted rendering, sandbox codegen, dashboard card, and integration transport/authentication. |
| Executable coverage | PASS | The repo has 23 executable eval scripts plus unit tests spanning the fake vertical slice, trusted renderer families, sandbox, dashboard card, and transport/auth anchors. Missing one-to-one YAML outlines for dashboard/transport/codegen anchors are added in this packet. |
| Safety invariants | PASS | Reviewed contracts preserve entity allowlist enforcement, read-only MVP behavior, sandboxed generated code, schema validation before rendering/storage, deterministic validation, chart-spec-first rendering, deterministic semantic memory, and ADR-before-architecture-change. |
| Anchor artifacts | PASS | The repo contains inspectable Python anchors for planning/rendering/validation/memory/sandbox/transport, a browser-loadable Lit card bundle and harness, schemas, evals, and paired evidence. |

## Non-Blocking Follow-Ups

- `docs/evals/ambiguous_entity_resolution.yaml` remains an outline-only eval for
  aggregate-style upstairs temperature clarification. Threshold clarification is
  already executable and proves the clarification/save-intent policy; the
  aggregate case should be implemented as an early production integration test.
- `docs/evals/semantic_memory_reuse.yaml` remains an outline-only aggregate
  alias reuse eval. Threshold alias reuse and invalidation are executable; the
  aggregate alias case should ride with the production resolver/memory path.
- Worker token rotation UI, worker health/readiness semantics, long-running
  progress streaming, production matplotlib packaging, semantic-memory repair
  UI, dashboard resource auto-registration, and post-MVP floorplan geometry
  remain known design details. None blocks the first integration scaffold.

## First Production Packet

Recommended packet: `Home Assistant integration scaffold anchor`.

The smallest useful anchor is a `custom_components/isolinear` package that can
be inspected and unit-tested before real orchestration exists. It should include
the manifest/domain constants, config/options data shape for model endpoint,
worker endpoint, render mode, and entity allowlist, and schema-valid stubs for
the `isolinear/v1/` WebSocket command boundary.

Proof should include:

- A new paired BDD/evidence file for the integration scaffold.
- Unit tests proving the manifest/config constants and command-boundary stubs.
- A focused eval that emits raw evidence for schema-valid command acceptance
  and fail-closed rejection of unknown/leaky commands.
- On-disk verification of the scaffold files.

The scaffold should not yet call the worker, model provider, Home Assistant
history APIs, semantic-memory storage helpers, or mutation services.
