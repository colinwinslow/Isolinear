# STATUS.md — Isolinear

> **Single source of truth.** `/startup` reads ONLY this file. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-01 (Kit migration Phase 1 structure created; semantic alias reuse enabled)  
**Phase:** `Seed phase — Design-heavy MVP planning before production integration`  
**Next bounded packet:** `Implement deterministic invalidation for saved semantic aliases referencing unavailable entities`  
**Current readiness:** `READY-FOR-NEXT-PACKET`

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-05-30** — `Threshold semantic alias reuse` — Added `semantic_aliases` context to planner; enabled deterministic reuse of saved dishwasher-running threshold aliases without re-prompting clarification. Tests green; evals green for all paths (prompt→chart, plan validation, overlay validation, shaded intervals, binary/numeric extraction, threshold extraction/inference, use-once, use-and-remember, alias reuse).
- **2026-05-30** — `Threshold confirmation use-and-remember` — Added `invoke_threshold_confirmation_use_and_remember` to save a schema-valid `SemanticAlias` for `dishwasher_running` after confirmed threshold; BDD passing.
- **2026-05-30** — `Threshold confirmation use-once` — Added `invoke_threshold_confirmation_use_once` to consume confirmed threshold, create overlay spec, render, validate; no saved alias. Tests + evals passing.
- **2026-05-30** — `Threshold clarification inference` — Added deterministic planner behavior to propose `sensor.dishwasher_power > 5 W` when dishwasher-running prompt needs threshold confirmation. Eval passing.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Semantic alias invalidation handling`

- [ ] Add BDD/eval coverage for saved alias referencing unavailable or non-allowlisted entity
- [ ] Ensure planner does not reuse invalid aliases; return `cannot_resolve` or clarification instead
- [ ] Return clear result instead of silently using stale memory
- [ ] Keep home assistant semantic-memory storage deferred

## Open queue (non-blocking)

> Things worth doing that don't gate the current packet. Pull from here when the active packet closes.

- (a) Persistent semantic-memory store (envelope, migrations, repair UI)
- (b) Dashboard card implementation technology decision
- (c) Worker API transport and authentication
- (d) Sandbox implementation for Raspberry Pi compatibility
- (e) First trusted renderer release (chart primitives scope)
- (f) Home Assistant custom integration scaffolding

## Blockers

- None.
