# STATUS.md — Isolinear

> **Single source of truth.** `/startup` reads ONLY this file. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-01 (semantic alias invalidation implemented with paired BDD evidence)
**Phase:** `Seed phase — Design-heavy MVP planning before production integration`  
**Next bounded packet:** `Backfill paired BDD evidence for existing eval-backed scenarios`
**Current readiness:** `READY-FOR-NEXT-PACKET`

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-01** — `Semantic alias invalidation handling` — Added deterministic stale-alias filtering for unavailable and non-allowlisted threshold aliases; invalid aliases return clarification or `cannot_resolve` without rendering. Added eval, paired BDD/evidence, and unit coverage. Architecture review OK; BDD-evidence review OK. Tests green; evals green.
- **2026-05-30** — `Threshold semantic alias reuse` — Added `semantic_aliases` context to planner; enabled deterministic reuse of saved dishwasher-running threshold aliases without re-prompting clarification. Tests green; evals green for all paths (prompt→chart, plan validation, overlay validation, shaded intervals, binary/numeric extraction, threshold extraction/inference, use-once, use-and-remember, alias reuse).
- **2026-05-30** — `Threshold confirmation use-and-remember` — Added `invoke_threshold_confirmation_use_and_remember` to save a schema-valid `SemanticAlias` for `dishwasher_running` after confirmed threshold; BDD passing.
- **2026-05-30** — `Threshold confirmation use-once` — Added `invoke_threshold_confirmation_use_once` to consume confirmed threshold, create overlay spec, render, validate; no saved alias. Tests + evals passing.
- **2026-05-30** — `Threshold clarification inference` — Added deterministic planner behavior to propose `sensor.dishwasher_power > 5 W` when dishwasher-running prompt needs threshold confirmation. Eval passing.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `BDD evidence backfill`

- [ ] Inventory implemented eval-backed scenarios that lack paired `bdd/<feature>/*-bdd.md` and evidence files
- [ ] Backfill paired BDD/evidence using fresh eval/test runs, not reconstructed claims
- [ ] Capture raw commands, outputs, fixtures, timestamps, and observed results
- [ ] Run BDD-evidence review on each backfilled scenario group

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
