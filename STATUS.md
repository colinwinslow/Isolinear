# STATUS.md — Isolinear

> **Single source of truth.** `/startup` reads ONLY this file. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-02 (dashboard card implementation technology decision completed)
**Phase:** `Seed phase — Design-heavy MVP planning before production integration`  
**Next bounded packet:** `Dashboard card anchor implementation`
**Current readiness:** `READY-FOR-NEXT-PACKET`

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-02** — `Dashboard card implementation technology decision` — Added accepted ADR-0011 for a TypeScript Lit `isolinear-card`, tightened dashboard-card spec layout/boundary constraints, and added paired dashboard-card anchor BDD/evidence scaffold. Architecture review OK after ADR promotion; BDD-evidence review intentionally FAILING because implementation evidence is pending. Docs-only verification clean; tests/evals not run.
- **2026-06-01** — `Persistent semantic-memory store envelope design` — Added ADR-0010, the semantic-memory store envelope schema, spec updates, paired BDD/evidence, eval coverage, and fake-slice anchor helpers for computed invalidity, fail-closed unsupported versions, and duplicate-alias rejection. Architecture review OK; BDD-evidence review OK. Tests green; evals green.
- **2026-06-01** — `BDD evidence backfill` — Inventoried eval-backed scenarios missing paired markdown BDD/evidence, added paired BDD/evidence for six scenario groups, instrumented evals with structured CASE output, and updated BDD indexes. Architecture review OK; BDD-evidence review OK. Tests green; evals green.
- **2026-06-01** — `Semantic alias invalidation handling` — Added deterministic stale-alias filtering for unavailable and non-allowlisted threshold aliases; invalid aliases return clarification or `cannot_resolve` without rendering. Added eval, paired BDD/evidence, and unit coverage. Architecture review OK; BDD-evidence review OK. Tests green; evals green.
- **2026-05-30** — `Threshold semantic alias reuse` — Added `semantic_aliases` context to planner; enabled deterministic reuse of saved dishwasher-running threshold aliases without re-prompting clarification. Tests green; evals green for all paths (prompt→chart, plan validation, overlay validation, shaded intervals, binary/numeric extraction, threshold extraction/inference, use-once, use-and-remember, alias reuse).

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Dashboard card anchor implementation`

- [ ] Scaffold frontend card source and minimal build/test toolchain for `isolinear-card`
- [ ] Build browser-testable fake Home Assistant harness and fixture job snapshots
- [ ] Render prompt-first idle state, active states, chart-first complete state, and failed state
- [ ] Verify fake WebSocket adapter calls and no direct worker/model/history/memory/mutation/local-storage boundary
- [ ] Replace dashboard-card anchor evidence scaffold with raw test output

## Open queue (non-blocking)

> Things worth doing that don't gate the current packet. Pull from here when the active packet closes.

- (a) Worker API transport and authentication
- (b) Sandbox implementation for Raspberry Pi compatibility
- (c) First trusted renderer release (chart primitives scope)
- (d) Home Assistant custom integration scaffolding

## Blockers

- None.
