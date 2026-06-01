# HANDOFF.md

## Current project phase

Seed phase. The repo is being prepared with ADRs, specs, BDD scenarios, schemas, eval outlines, and Codex working rules before production implementation.

## Product summary

Isolinear lets a user ask natural-language questions about approved Home Assistant entities and receive generated data visualizations based on entity history.

## Current architecture direction

- Home Assistant custom integration.
- Custom dashboard card as the first UI.
- Optional Home Assistant add-on worker for rendering and sandbox execution.
- Standalone worker mode should remain possible for Home Assistant installs that cannot use add-ons.
- Model provider should be Ollama-compatible, with local-first defaults and optional stronger providers later.
- Trusted chart-spec renderer is the default path.
- Sandboxed matplotlib codegen is an advanced path.

## Open implementation status

Fake-provider vertical slice implemented as a local Python module with schema-backed contract validation, a pre-render plan validation gate, deterministic render metadata validation, trusted safe-mode rendering for shaded interval overlays, fake binary-state interval extraction, confirmed threshold-derived interval extraction, deterministic threshold clarification for continuous power sensors, use-once threshold confirmation handling, deterministic threshold semantic alias creation, and reuse of saved threshold aliases. No Home Assistant integration has been built yet.

## Next recommended packet

Add deterministic invalidation handling for saved semantic aliases referencing unavailable or non-allowlisted entities:

1. Add BDD/eval coverage for a saved threshold alias whose source entity is no longer visible to the agent.
2. Ensure the fake planner does not reuse aliases that reference missing or non-allowlisted entities.
3. Return a clear clarification or cannot-resolve result instead of silently using stale memory.
4. Keep the actual Home Assistant semantic-memory storage mechanism deferred.

## Known unresolved design details

- Persistent semantic-memory store envelope, migrations, and repair UI details.
- Exact dashboard card implementation technology.
- Exact worker API transport and authentication.
- Exact sandbox implementation details for Raspberry Pi compatibility.
- Which chart primitives are included in the first trusted renderer release.

## Session log

Per-session details live in `STATUS.md` (rolling 5-entry log) and git history. See the rolling log at the top of `STATUS.md` for recent session summary (packet name, what closed/changed, test posture). Older sessions are archived in git commits.
