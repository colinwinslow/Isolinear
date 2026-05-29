# HANDOFF.md

## Current project phase

Seed phase. The repo is being prepared with ADRs, specs, BDD scenarios, schemas, eval outlines, and Codex working rules before production implementation.

## Product summary

Home Assistant Dataviz Agent lets a user ask natural-language questions about approved Home Assistant entities and receive generated data visualizations based on entity history.

## Current architecture direction

- Home Assistant custom integration.
- Custom dashboard card as the first UI.
- Optional Home Assistant add-on worker for rendering and sandbox execution.
- Standalone worker mode should remain possible for Home Assistant installs that cannot use add-ons.
- Model provider should be Ollama-compatible, with local-first defaults and optional stronger providers later.
- Trusted chart-spec renderer is the default path.
- Sandboxed matplotlib codegen is an advanced path.

## Open implementation status

No production implementation yet.

## Next recommended packet

Build a fake-provider vertical slice:

1. Fake entity catalog with approved entities.
2. Fake normalized history for two temperature sensors.
3. Planner stub or deterministic planner that emits a `ChartSpec`.
4. Trusted renderer that outputs a PNG.
5. Render result metadata.
6. Deterministic validator that confirms expected series and time range.

## Known unresolved design details

- Exact Home Assistant integration storage mechanism for semantic memory.
- Exact dashboard card implementation technology.
- Exact worker API transport and authentication.
- Exact sandbox implementation details for Raspberry Pi compatibility.
- Which chart primitives are included in the first trusted renderer release.

## Session notes

Update this file during `/closeout` with:

- What changed.
- Tests and evals run.
- New decisions.
- Bugs found.
- Next packet of work.
