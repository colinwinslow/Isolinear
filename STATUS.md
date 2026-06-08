# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-08 (Home Assistant approved entity catalog scaffold anchor)
**Phase:** `Production approved entity catalog scaffold anchored — history retrieval scaffold next`
**Next bounded packet:** `Home Assistant approved history retrieval scaffold anchor`
**Current readiness:** `READY-FOR-NEXT-PACKET`

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-08** — `Home Assistant approved entity catalog scaffold anchor` — Added the paired approved-entity catalog scaffold spec, BDD, eval outline, raw evidence, executable eval, Python verifier anchor, focused tests, and production `custom_components/isolinear/entity_catalog.py` module. `async_setup_entry` now builds and stores a config-entry-scoped in-memory catalog from the configured `entity_allowlist` plus fake Home Assistant entity/state metadata, producing only schema-valid `EntityCatalogItem` records with `visible_to_agent: true`. The catalog validates every item before storage/return, stores atomically, isolates per config entry, rejects unknown allowlisted entities, clears stale catalog state on rejected rebuilds, and rejects malformed allowlists and malformed normalized items with structured errors before storage. The packet remains non-orchestrating: no worker, model-provider, Home Assistant history retrieval, semantic-memory persistence, service/state mutation, token-generation, chart artifact write, WebSocket registration, dashboard-resource metadata write, durable storage, or real job orchestration occurs. Python tests green in `.venv` (`101 passed`), focused catalog eval green, adjacent Home Assistant evals green, BDD-evidence review OK, and standalone architecture review OK after resolving stale-catalog and malformed-allowlist findings.
- **2026-06-08** — `Home Assistant job state scaffold anchor` — Added the paired job-state scaffold spec, BDD, eval outline, raw evidence, executable eval, Python verifier anchor, focused tests, and production `custom_components/isolinear/job_state.py` module. `async_setup_entry` now initializes an in-memory config-entry-scoped job store, and registered WebSocket callbacks use it after deterministic command validation and config-entry scope validation. The store creates deterministic job/snapshot IDs, validates every `IntegrationJobSnapshot` against JSON Schema before storage, returns latest snapshots, records retry and clarification-answer scaffold snapshots, records a subscription callback/event shape, rejects unknown and cross-config-entry jobs with `unknown_job`, and unload cleanup removes entry job state. The packet remains non-orchestrating: no worker, model-provider, Home Assistant history, semantic-memory persistence, service/state mutation, token-generation, chart artifact write, durable storage, or real job orchestration occurs. Python tests green in `.venv` (`92 passed`), focused job-state eval green, adjacent WebSocket/dashboard-resource evals green, BDD-evidence review OK, and standalone architecture review OK after resolving the pre-storage schema-validation finding.
- **2026-06-08** — `Home Assistant WebSocket command registration anchor` — Added the paired WebSocket command registration spec, BDD, eval outline, raw evidence, executable eval, Python verifier anchor, fake Home Assistant WebSocket registry harness, and focused tests. Replaced scaffold-only command-name bookkeeping with real `websocket_api.async_register_command` registration for the five accepted `isolinear/v1/` command names, wired registration from `async_setup_entry`, stored the result under the config-entry ID, kept registration idempotent, stripped Home Assistant transport `id` before internal schema validation, and kept Home Assistant's decorator schema to command routing while Isolinear's deterministic validator owns version, payload-shape, forbidden-material, and config-entry-scope errors. Registered callbacks return schema-valid scaffold `IntegrationJobSnapshot` payloads for known config entries and fail closed for unknown, wrong-version, leaky, mutating, malformed, and missing-config-entry commands before orchestration. No worker, model-provider, Home Assistant history, semantic-memory, service/state mutation, token-generation, job-orchestration, or dashboard-resource metadata write occurs in this boundary. Python tests green in `.venv`, focused WebSocket eval green, adjacent scaffold/config-flow/dashboard-resource evals green, BDD-evidence review OK, and standalone architecture review OK after resolving the schema-gate concern.
- **2026-06-08** — `Home Assistant dashboard resource registration anchor` — Added ADR-0013 for integration-owned dashboard resource auto-registration and anchored `custom_components/isolinear/dashboard_resource.py`, wired from `async_setup_entry`, to serve the checked-in `frontend/dist/isolinear-card.js` bundle from `/api/isolinear/static` and create or reuse one Lovelace `module` resource at `/api/isolinear/static/isolinear-card.js`. Added paired resource-registration spec, BDD, Gherkin scenarios, eval outline, executable eval, raw evidence, Python verifier anchor, fake Home Assistant resource collection harness, and focused tests proving config-entry scoped setup bookkeeping, idempotence, pre-existing metadata reuse, missing-bundle rejection, unavailable-resource-collection rejection, and explicit side-effect accounting. The only allowed Home Assistant write is dashboard resource metadata creation/reuse; no worker, model-provider, Home Assistant history, semantic-memory, service/state mutation, token-generation, job-orchestration, or extra WebSocket command registration calls occur. Python tests green in `.venv`, focused dashboard-resource eval green, existing scaffold/config-flow evals green, BDD-evidence review OK, and standalone architecture review OK.
- **2026-06-07** — `Home Assistant config flow/options anchor` — Enabled the production integration config-flow flag and added `custom_components/isolinear/config_flow.py` with a minimal user config step and options init step that reuse the pure config/options validation helpers. Added paired config-flow/options spec, BDD, Gherkin scenarios, eval outline, executable eval, raw evidence, Python verifier anchor, and focused tests proving valid local-first config/options normalize into the expected shapes while credential-bearing endpoints, secret-like values, unsupported render modes, duplicate allowlists, malformed entity IDs, and forbidden secret material fail closed before persistence. The packet remained non-orchestrating: no worker, model provider, Home Assistant history, semantic-memory, mutation, token-generation, or dashboard-resource registration calls. Python tests green in `.venv`, focused config-flow/options eval green, existing integration-scaffold eval green, BDD-evidence review OK, and standalone architecture review OK.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Home Assistant approved entity catalog scaffold anchor`

- [x] Add paired approved-entity catalog scaffold spec, BDD, evidence, and eval outline
- [x] Add config-entry-scoped in-memory entity catalog setup from `async_setup_entry`
- [x] Build catalog items only from configured `entity_allowlist` plus fake Home Assistant entity/state metadata
- [x] Prove every returned/stored catalog item validates against `EntityCatalogItem`
- [x] Prove unknown entity, stale rejected rebuild, malformed allowlist, malformed catalog item, and per-config-entry isolation behavior
- [x] Prove side-effect boundaries with focused tests, executable eval, raw evidence, on-disk verification, BDD-evidence review, and architecture review

## Open queue (non-blocking)

> Things worth doing that don't gate the current packet. Pull from here when the active packet closes.

- (a) Aggregate-style ambiguous entity clarification executable eval
- (b) Aggregate alias creation/reuse executable eval
- (c) Post-MVP floorplan heatmap renderer requiring explicit user-provided room
  geometry and area/entity mappings

## Blockers

- None.
