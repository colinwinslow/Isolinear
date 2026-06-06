# STATUS.md — Isolinear

> **Single source of truth.** `/startup` reads ONLY this file. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-06 (worker API transport and authentication completed)
**Phase:** `Seed phase — Design-heavy MVP planning before production integration`  
**Next bounded packet:** `Sandbox implementation for Raspberry Pi compatibility`
**Current readiness:** `READY-FOR-NEXT-PACKET`

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-06** — `Worker API transport and authentication` — Added draft ADR-0012, a paired integration API transport/auth spec and BDD/evidence, JSON schemas for integration WebSocket commands, integration job snapshots, and worker transport requests, plus a schema-backed Python anchor with tests/eval proving versioned card commands, bearer-auth worker render requests, bad-auth/version rejection, and token redaction. Updated the frontend adapter and checked-in bundle for job subscription commands and full integration job statuses. Standalone architecture review via `codex exec` timed out twice; inline architecture review OK; BDD-evidence review OK. Python tests green; frontend build/test green; transport/auth and dashboard-card evals green.
- **2026-06-05** — `Dashboard card anchor implementation` — Added repo-local Python and Node tooling, implemented the TypeScript Lit `isolinear-card` anchor with fake Home Assistant harness, fixture job snapshots, Vite bundle, frontend adapter tests, Python verifier, dashboard-card eval, and raw BDD evidence. Upgraded frontend dev dependencies to Vite 8/Vitest 4 with npm audit clean. Architecture review OK; BDD-evidence review OK. Frontend build/test green; Python tests green; dashboard-card eval green.
- **2026-06-02** — `Dashboard card implementation technology decision` — Added accepted ADR-0011 for a TypeScript Lit `isolinear-card`, tightened dashboard-card spec layout/boundary constraints, and added paired dashboard-card anchor BDD/evidence scaffold. Architecture review OK after ADR promotion; BDD-evidence review intentionally FAILING because implementation evidence is pending. Docs-only verification clean; tests/evals not run.
- **2026-06-01** — `Persistent semantic-memory store envelope design` — Added ADR-0010, the semantic-memory store envelope schema, spec updates, paired BDD/evidence, eval coverage, and fake-slice anchor helpers for computed invalidity, fail-closed unsupported versions, and duplicate-alias rejection. Architecture review OK; BDD-evidence review OK. Tests green; evals green.
- **2026-06-01** — `BDD evidence backfill` — Inventoried eval-backed scenarios missing paired markdown BDD/evidence, added paired BDD/evidence for six scenario groups, instrumented evals with structured CASE output, and updated BDD indexes. Architecture review OK; BDD-evidence review OK. Tests green; evals green.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Worker API transport and authentication`

- [x] Decide the card-facing WebSocket and worker-facing transport/auth envelope in draft ADR-0012
- [x] Define schemas for integration WebSocket commands, integration job snapshots, and worker transport requests
- [x] Build the schema-backed transport/auth anchor with fail-closed auth/version/secret-leak checks
- [x] Update the frontend adapter and bundle for job subscription command coverage
- [x] Capture raw BDD evidence and run Python, frontend, and eval verification

## Open queue (non-blocking)

> Things worth doing that don't gate the current packet. Pull from here when the active packet closes.

- (a) Sandbox implementation for Raspberry Pi compatibility
- (b) First trusted renderer release (chart primitives scope)
- (c) Home Assistant custom integration scaffolding once MVP design phase closes

## Blockers

- None.
