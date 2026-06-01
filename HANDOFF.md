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

Fake-provider vertical slice implemented as a local Python module with schema-backed contract validation, a pre-render plan validation gate, deterministic render metadata validation, trusted safe-mode rendering for shaded interval overlays, fake binary-state interval extraction, confirmed threshold-derived interval extraction, deterministic threshold clarification for continuous power sensors, use-once threshold confirmation handling, deterministic threshold semantic alias creation, reuse of saved threshold aliases, deterministic invalidation of saved threshold aliases that reference unavailable or non-allowlisted entities, and a versioned semantic-memory store envelope anchor that computes invalidity at use time while failing closed for unsupported versions or duplicate alias IDs. Eval scripts now emit structured `CASE` evidence payloads, and implemented eval-backed scenario groups have paired markdown BDD/evidence files under `bdd/<feature>/`. No Home Assistant integration has been built yet.

## Next recommended packet

Dashboard card implementation technology decision:

1. Read the existing architecture ADRs and any dashboard-card references.
2. Identify Home Assistant dashboard-card technology constraints for the MVP.
3. Decide whether the card technology choice needs a new ADR before implementation.
4. Define the smallest anchor artifact and proof requirements.

## Known unresolved design details

- Semantic-memory storage-helper implementation, migrations, and repair UI details beyond the envelope contract.
- Exact dashboard card implementation technology.
- Exact worker API transport and authentication.
- Exact sandbox implementation details for Raspberry Pi compatibility.
- Which chart primitives are included in the first trusted renderer release.

## Session log

Per-session details live in `STATUS.md` (rolling 5-entry log) and git history. See the rolling log at the top of `STATUS.md` for recent session summary (packet name, what closed/changed, test posture). Older sessions are archived in git commits.
