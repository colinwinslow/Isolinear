# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-08 (Home Assistant WebSocket command registration anchor)
**Phase:** `Production WebSocket command registration anchored — job state surface next`
**Next bounded packet:** `Home Assistant job state scaffold anchor`
**Current readiness:** `READY-FOR-NEXT-PACKET`

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-08** — `Home Assistant WebSocket command registration anchor` — Added the paired WebSocket command registration spec, BDD, eval outline, raw evidence, executable eval, Python verifier anchor, fake Home Assistant WebSocket registry harness, and focused tests. Replaced scaffold-only command-name bookkeeping with real `websocket_api.async_register_command` registration for the five accepted `isolinear/v1/` command names, wired registration from `async_setup_entry`, stored the result under the config-entry ID, kept registration idempotent, stripped Home Assistant transport `id` before internal schema validation, and kept Home Assistant's decorator schema to command routing while Isolinear's deterministic validator owns version, payload-shape, forbidden-material, and config-entry-scope errors. Registered callbacks return schema-valid scaffold `IntegrationJobSnapshot` payloads for known config entries and fail closed for unknown, wrong-version, leaky, mutating, malformed, and missing-config-entry commands before orchestration. No worker, model-provider, Home Assistant history, semantic-memory, service/state mutation, token-generation, job-orchestration, or dashboard-resource metadata write occurs in this boundary. Python tests green in `.venv`, focused WebSocket eval green, adjacent scaffold/config-flow/dashboard-resource evals green, BDD-evidence review OK, and standalone architecture review OK after resolving the schema-gate concern.
- **2026-06-08** — `Home Assistant dashboard resource registration anchor` — Added ADR-0013 for integration-owned dashboard resource auto-registration and anchored `custom_components/isolinear/dashboard_resource.py`, wired from `async_setup_entry`, to serve the checked-in `frontend/dist/isolinear-card.js` bundle from `/api/isolinear/static` and create or reuse one Lovelace `module` resource at `/api/isolinear/static/isolinear-card.js`. Added paired resource-registration spec, BDD, Gherkin scenarios, eval outline, executable eval, raw evidence, Python verifier anchor, fake Home Assistant resource collection harness, and focused tests proving config-entry scoped setup bookkeeping, idempotence, pre-existing metadata reuse, missing-bundle rejection, unavailable-resource-collection rejection, and explicit side-effect accounting. The only allowed Home Assistant write is dashboard resource metadata creation/reuse; no worker, model-provider, Home Assistant history, semantic-memory, service/state mutation, token-generation, job-orchestration, or extra WebSocket command registration calls occur. Python tests green in `.venv`, focused dashboard-resource eval green, existing scaffold/config-flow evals green, BDD-evidence review OK, and standalone architecture review OK.
- **2026-06-07** — `Home Assistant config flow/options anchor` — Enabled the production integration config-flow flag and added `custom_components/isolinear/config_flow.py` with a minimal user config step and options init step that reuse the pure config/options validation helpers. Added paired config-flow/options spec, BDD, Gherkin scenarios, eval outline, executable eval, raw evidence, Python verifier anchor, and focused tests proving valid local-first config/options normalize into the expected shapes while credential-bearing endpoints, secret-like values, unsupported render modes, duplicate allowlists, malformed entity IDs, and forbidden secret material fail closed before persistence. The packet remained non-orchestrating: no worker, model provider, Home Assistant history, semantic-memory, mutation, token-generation, or dashboard-resource registration calls. Python tests green in `.venv`, focused config-flow/options eval green, existing integration-scaffold eval green, BDD-evidence review OK, and standalone architecture review OK.
- **2026-06-07** — `Home Assistant integration scaffold anchor` — Added the first production `custom_components/isolinear` package with manifest, domain constants, local-first config/options validation, and schema-aligned `isolinear/v1/` WebSocket command-boundary stubs. Added paired scaffold spec, BDD, Gherkin feature, eval outline, executable eval, raw evidence, Python verifier anchor, and focused tests proving known commands return schema-valid scaffold snapshots while unknown, wrong-version, leaky, mutating, credential-bearing endpoint, and secret-like config payloads fail closed before orchestration. Removed a premature semantic-memory storage key and updated the architecture-review protocol to default standalone reviews to a 10 minute timeout. Python tests green in `.venv`, focused scaffold eval green, BDD-evidence review OK, and standalone architecture review OK.
- **2026-06-07** — `MVP design closeout/readiness review` — Audited ADR, spec, schema, BDD, eval, evidence, and anchor coverage for the MVP design phase. Added `docs/mvp-design-readiness-review.md` with a READY verdict for the first Home Assistant integration scaffold, promoted ADR-0012 and the integration API transport/auth spec/BDD to accepted, normalized newer BDD evidence headers, and added missing eval-outline entries for the already-executable codegen sandbox, dashboard card, and integration transport/auth anchors. Identified the next bounded packet as `Home Assistant integration scaffold anchor`; aggregate ambiguity/aggregate alias eval outlines remain non-blocking production follow-ups. Python tests green in `.venv`, frontend build/test green, full eval sweep green, diff check green, and standalone architecture review completed with no invariant violations after status verification was updated.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Home Assistant WebSocket command registration anchor`

- [x] Add paired WebSocket command registration spec, BDD, evidence, and eval outline
- [x] Replace scaffold-only command bookkeeping with real `websocket_api.async_register_command` registration
- [x] Wire command registration into `async_setup_entry` with config-entry scoped bookkeeping
- [x] Prove registered callbacks return schema-valid scaffold snapshots for known config entries
- [x] Prove unknown, wrong-version, leaky, mutating, malformed, and missing-config-entry commands fail closed before orchestration
- [x] Prove idempotence and side-effect boundaries with focused tests, executable eval, raw evidence, on-disk verification, and architecture review

## Open queue (non-blocking)

> Things worth doing that don't gate the current packet. Pull from here when the active packet closes.

- (a) Aggregate-style ambiguous entity clarification executable eval
- (b) Aggregate alias creation/reuse executable eval
- (c) Post-MVP floorplan heatmap renderer requiring explicit user-provided room
  geometry and area/entity mappings

## Blockers

- None.
