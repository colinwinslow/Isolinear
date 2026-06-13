---
id: 0017
title: First real vertical slice
status: draft
date: 2026-06-13
supersedes: []
superseded-by: null
tags:
  - home-assistant
  - renderer
  - model-provider
  - vertical-slice
---

# ADR-0017: First real vertical slice

## Context

Isolinear has strong schema, validation, WebSocket, worker, and storage
scaffolds, but the current production path still relies on simulated entity
metadata, simulated history, placeholder artifacts, and worker-oriented render
metadata. The next useful risk reduction is to make one real prompt-to-chart
spine touch Home Assistant entity metadata, Home Assistant history, an
Ollama-compatible planner, and matplotlib output. The separate worker and
sandbox design remains valid, but it adds moving parts before the product has
proved its real data and planner assumptions.

## Decision

**The first real MVP spine renders in-process through the trusted
ChartSpec-to-matplotlib path, using real allowlisted Home Assistant metadata,
real recorder history, and the configured Ollama-compatible planner behind the
existing `isolinear/v1/` WebSocket flow.**

This decision deliberately defers the worker/add-on and sandbox split for the
first reality proof. The in-process route is allowed only for trusted
ChartSpec rendering in safe mode; generated Python remains out of scope and
must still use the existing sandbox/worker decision when re-enabled.

## Rationale

- A real Home Assistant + Ollama + matplotlib path will expose schema and data
  assumptions that scaffold-only packets cannot reveal.
- Keeping the existing card-facing WebSocket API avoids a new UI surface and
  preserves the dashboard card boundary from ADR-0011 and ADR-0012.
- In-process trusted rendering removes worker token, worker readiness,
  network, packaging, and health-polling variables from the first reality
  proof.
- The existing worker design is still useful for hardening once the real
  prompt, history, planner, and chart shapes are known.
- Schema validation, allowlist filtering, and read-only Home Assistant
  behavior remain the load-bearing safety guarantees.

## Consequences

**Enables:**
- Manual verification against a real Home Assistant dev instance and local
  Ollama endpoint.
- Earlier correction of `EntityCatalogItem`, `HistorySeries`, `PlannerResult`,
  `ChartSpec`, and artifact metadata contracts using real data.
- A visible PNG in the existing Lit dashboard card without waiting for worker
  packaging.

**Constrains:**
- The first real renderer path must support only trusted ChartSpec primitives
  and must fail closed for unsupported chart specs.
- The integration must not read non-allowlisted entity metadata or history.
- The in-process path must not call Home Assistant mutation services, execute
  generated Python, expose worker tokens, or bypass schema validation.
- Existing worker paths remain opt-in scaffolds and are not expanded until the
  real spine works.

**Open:**
- Production artifact serving endpoint versus data-URL delivery.
- Async Home Assistant recorder and aiohttp integration details for full
  production ergonomics.
- Exact worker handoff after the real in-process renderer proves the contracts.

## References

- ADR-0001: Home Assistant integration plus isolated worker
- ADR-0003: Entity allowlist, semantic resolution, memory
- ADR-0004: Chart spec first rendering with codegen option
- ADR-0005: Schema-driven contracts and history normalization
- ADR-0007: Local-first Ollama-compatible model provider
- ADR-0008: Read-only MVP and sandbox security
- ADR-0011: Dashboard card implementation technology
- ADR-0012: Worker transport and authentication
- [Reality pivot review](../reality-pivot-review.md)
- [First real vertical slice spec](../specs/home-assistant-first-real-vertical-slice.md)
