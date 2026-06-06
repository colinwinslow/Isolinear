# STATUS.md — Isolinear

> **Single source of truth.** `/startup` reads ONLY this file. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-06 (trusted renderer state interval timeline follow-up)
**Phase:** `Seed phase — Design-heavy MVP planning before production integration`  
**Next bounded packet:** `Trusted renderer aggregate bar chart follow-up`
**Current readiness:** `READY-FOR-NEXT-PACKET`

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-06** — `Trusted renderer state interval timeline follow-up` — Selected `state_interval_timeline` as the first trusted-renderer follow-up family. Extended the chart-spec rendering spec, BDD, eval outline, evidence, and Python anchor so safe mode now supports `timeline` charts with binary/categorical `step` tracks rendered from matching `DerivedInterval` records, PNG output, absolute time-range metadata, and zero codegen attempts. Added chart-family-specific unsupported checks so `time_series` remains limited to numeric `line` series and `timeline` rejects numeric/line specs. Added a fail-closed guard for mismatched `DerivedInterval.source_entity_id` before artifact creation. Standalone architecture review via `codex exec` timed out; inline architecture review OK; BDD-evidence review OK. Python tests green; timeline and renderer evals green.
- **2026-06-06** — `First trusted renderer release scope` — Documented and anchored the first trusted renderer scope: safe-mode `time_series`, numeric `line` series, entity-backed sources, no transform except `none`, optional `shaded_intervals`, PNG output, and no fallback into codegen. Added scope enforcement to the Python trusted-renderer anchor, structured `unsupported_chart_spec` details, focused tests, executable eval/evidence, and roadmap notes for six follow-up trusted renderer families. Deferred floorplan heatmaps until post-MVP because Home Assistant floors/areas do not provide room geometry. Standalone architecture review via `codex exec` timed out; inline architecture review OK; BDD-evidence review OK. Python tests green; renderer evals green.
- **2026-06-06** — `Sandbox implementation for Raspberry Pi compatibility` — Added a schema-backed codegen sandbox policy, Python sandbox anchor, focused tests, executable eval, paired sandbox BDD/evidence, and the dev matplotlib dependency. The anchor proves fixed `render_chart(data, output_path)` execution, stripped subprocess environment, exact generated-code import allowlisting, allowlisted matplotlib `Agg` rendering, runtime audit denial for arbitrary reads routed through `pyplot.imread`, fixed output path enforcement, output-size failure, and capped repair-loop behavior with static checks rerun on each attempt. Worker sandbox spec now names the concrete Raspberry Pi-compatible strategy and import boundary. Standalone architecture review PASS; BDD-evidence review OK. Python tests green; sandbox eval green.
- **2026-06-06** — `Worker API transport and authentication` — Added draft ADR-0012, a paired integration API transport/auth spec and BDD/evidence, JSON schemas for integration WebSocket commands, integration job snapshots, and worker transport requests, plus a schema-backed Python anchor with tests/eval proving versioned card commands, bearer-auth worker render requests, bad-auth/version rejection, and token redaction. Updated the frontend adapter and checked-in bundle for job subscription commands and full integration job statuses. Standalone architecture review via `codex exec` timed out twice; inline architecture review OK; BDD-evidence review OK. Python tests green; frontend build/test green; transport/auth and dashboard-card evals green.
- **2026-06-05** — `Dashboard card anchor implementation` — Added repo-local Python and Node tooling, implemented the TypeScript Lit `isolinear-card` anchor with fake Home Assistant harness, fixture job snapshots, Vite bundle, frontend adapter tests, Python verifier, dashboard-card eval, and raw BDD evidence. Upgraded frontend dev dependencies to Vite 8/Vitest 4 with npm audit clean. Architecture review OK; BDD-evidence review OK. Frontend build/test green; Python tests green; dashboard-card eval green.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Trusted renderer follow-up family selection`

- [x] Select `state_interval_timeline` as the first trusted renderer follow-up family
- [x] Extend the paired chart-spec rendering spec, BDD, evidence, and eval outline
- [x] Render timeline tracks from matching validated `DerivedInterval` records in safe mode
- [x] Keep unsupported time-series and timeline primitives fail-closed with zero codegen attempts
- [x] Guard timeline rendering against mismatched derived-interval source entities before artifact creation
- [x] Run Python tests, timeline/renderer evals, architecture review, and BDD-evidence review

## Open queue (non-blocking)

> Things worth doing that don't gate the current packet. Pull from here when the active packet closes.

- (a) Trusted renderer follow-up families: aggregate bar, calendar/hour
  heatmap, event markers, distribution/histogram, and scatter/correlation
- (b) Post-MVP floorplan heatmap renderer requiring explicit user-provided room
  geometry and area/entity mappings
- (c) Home Assistant custom integration scaffolding once MVP design phase closes

## Blockers

- None.
