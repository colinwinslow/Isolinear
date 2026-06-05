# STATUS.md — Isolinear

> **Single source of truth.** `/startup` reads ONLY this file. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-05 (dashboard card anchor implementation completed)
**Phase:** `Seed phase — Design-heavy MVP planning before production integration`  
**Next bounded packet:** `Worker API transport and authentication`
**Current readiness:** `READY-FOR-NEXT-PACKET`

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-05** — `Dashboard card anchor implementation` — Added repo-local Python and Node tooling, implemented the TypeScript Lit `isolinear-card` anchor with fake Home Assistant harness, fixture job snapshots, Vite bundle, frontend adapter tests, Python verifier, dashboard-card eval, and raw BDD evidence. Upgraded frontend dev dependencies to Vite 8/Vitest 4 with npm audit clean. Architecture review OK; BDD-evidence review OK. Frontend build/test green; Python tests green; dashboard-card eval green.
- **2026-06-02** — `Dashboard card implementation technology decision` — Added accepted ADR-0011 for a TypeScript Lit `isolinear-card`, tightened dashboard-card spec layout/boundary constraints, and added paired dashboard-card anchor BDD/evidence scaffold. Architecture review OK after ADR promotion; BDD-evidence review intentionally FAILING because implementation evidence is pending. Docs-only verification clean; tests/evals not run.
- **2026-06-01** — `Persistent semantic-memory store envelope design` — Added ADR-0010, the semantic-memory store envelope schema, spec updates, paired BDD/evidence, eval coverage, and fake-slice anchor helpers for computed invalidity, fail-closed unsupported versions, and duplicate-alias rejection. Architecture review OK; BDD-evidence review OK. Tests green; evals green.
- **2026-06-01** — `BDD evidence backfill` — Inventoried eval-backed scenarios missing paired markdown BDD/evidence, added paired BDD/evidence for six scenario groups, instrumented evals with structured CASE output, and updated BDD indexes. Architecture review OK; BDD-evidence review OK. Tests green; evals green.
- **2026-06-01** — `Semantic alias invalidation handling` — Added deterministic stale-alias filtering for unavailable and non-allowlisted threshold aliases; invalid aliases return clarification or `cannot_resolve` without rendering. Added eval, paired BDD/evidence, and unit coverage. Architecture review OK; BDD-evidence review OK. Tests green; evals green.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Dashboard card anchor implementation`

- [x] Scaffold frontend card source and minimal build/test toolchain for `isolinear-card`
- [x] Build browser-testable fake Home Assistant harness and fixture job snapshots
- [x] Render prompt-first idle state, active states, chart-first complete state, and failed state
- [x] Verify fake WebSocket adapter calls and no direct worker/model/history/memory/mutation/local-storage boundary
- [x] Replace dashboard-card anchor evidence scaffold with raw test output

## Open queue (non-blocking)

> Things worth doing that don't gate the current packet. Pull from here when the active packet closes.

- (a) Sandbox implementation for Raspberry Pi compatibility
- (b) First trusted renderer release (chart primitives scope)
- (c) Home Assistant custom integration scaffolding

## Blockers

- None.
