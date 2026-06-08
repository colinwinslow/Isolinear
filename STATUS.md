# STATUS.md — Isolinear

> **Current packet source of truth.** `/startup` reads this file and `HANDOFF.md`. `/closeout` updates it. Keep it current; keep it short.

**Last updated:** 2026-06-08 (Home Assistant job orchestration scaffold anchor)
**Phase:** `Production job orchestration scaffold anchored — clarification continuation next`
**Next bounded packet:** `Home Assistant job orchestration clarification continuation scaffold anchor`
**Current readiness:** `READY-FOR-NEXT-PACKET`

## Recent sessions (rolling, last 5)

> Newest first. Add one entry per session at `/closeout`. **Trim to 5** — older sessions live in git history.

- **2026-06-08** — `Home Assistant job orchestration scaffold anchor` — Added the paired job-orchestration scaffold spec, BDD, eval outline, raw evidence, executable eval, Python verifier anchor, focused tests, and production `custom_components/isolinear/job_orchestration.py` module. `async_setup_entry` now initializes a config-entry-scoped in-memory orchestration store after job state, approved entity catalog, and approved history retrieval setup. Enabled `isolinear/v1/job/start` commands now route through the scaffold, create deterministic job/snapshot IDs, compose approved catalog and approved fake history through existing boundaries, append schema-valid planning/fetching-history/scaffold-ready or failed snapshots, and store per-entry run summaries. The scaffold rejects explicit non-catalog entity IDs before history read, returns structured failed snapshots for missing approved history, and returns schema-valid `clarification_needed` snapshots for prompts that do not deterministically select one approved entity, including multiple label matches. It remains non-rendering and non-mutating: no worker, model-provider, semantic-memory persistence, Home Assistant service/state mutation, token-generation, chart artifact write, chart rendering, durable storage, or production orchestration occurs. Python tests green in `.venv` (`119 passed`), focused orchestration eval green, adjacent Home Assistant evals green, BDD-evidence review OK, and standalone architecture review OK after fixing the multiple-label-match ambiguity finding. Packet-size note: this slice was larger than ideal; follow-on orchestration continuation work should split clarification answer, retry, streaming, and artifact semantics into separate bounded packets.
- **2026-06-08** — `Home Assistant approved history retrieval scaffold anchor` — Added the paired approved-history retrieval scaffold spec, BDD, eval outline, raw evidence, executable eval, Python verifier anchor, focused tests, and production `custom_components/isolinear/history_retrieval.py` module. `async_setup_entry` now initializes a config-entry-scoped in-memory history retrieval store after the approved entity catalog setup. The retrieval boundary gates requested entity IDs against visible approved catalog items before reading fake Home Assistant history, normalizes approved raw state records into schema-valid `HistorySeries` records, validates every series before storage/return, stores atomically, isolates per config entry, rejects non-catalog entities before history read, clears stale history on rejected retrievals, and rejects malformed raw history and malformed normalized series with structured errors before storage. The packet remains non-orchestrating: no worker, model-provider, semantic-memory persistence, Home Assistant service/state mutation, token-generation, chart artifact write, chart rendering, WebSocket command registration, dashboard-resource metadata write, durable storage, or real job orchestration occurs. Python tests green in `.venv` (`110 passed`), focused history eval green, adjacent Home Assistant evals green, BDD-evidence review OK, and standalone architecture review OK.
- **2026-06-08** — `Home Assistant approved entity catalog scaffold anchor` — Added the paired approved-entity catalog scaffold spec, BDD, eval outline, raw evidence, executable eval, Python verifier anchor, focused tests, and production `custom_components/isolinear/entity_catalog.py` module. `async_setup_entry` now builds and stores a config-entry-scoped in-memory catalog from the configured `entity_allowlist` plus fake Home Assistant entity/state metadata, producing only schema-valid `EntityCatalogItem` records with `visible_to_agent: true`. The catalog validates every item before storage/return, stores atomically, isolates per config entry, rejects unknown allowlisted entities, clears stale catalog state on rejected rebuilds, and rejects malformed allowlists and malformed normalized items with structured errors before storage. The packet remains non-orchestrating: no worker, model-provider, Home Assistant history retrieval, semantic-memory persistence, service/state mutation, token-generation, chart artifact write, WebSocket registration, dashboard-resource metadata write, durable storage, or real job orchestration occurs. Python tests green in `.venv` (`101 passed`), focused catalog eval green, adjacent Home Assistant evals green, BDD-evidence review OK, and standalone architecture review OK after resolving stale-catalog and malformed-allowlist findings.
- **2026-06-08** — `Home Assistant job state scaffold anchor` — Added the paired job-state scaffold spec, BDD, eval outline, raw evidence, executable eval, Python verifier anchor, focused tests, and production `custom_components/isolinear/job_state.py` module. `async_setup_entry` now initializes an in-memory config-entry-scoped job store, and registered WebSocket callbacks use it after deterministic command validation and config-entry scope validation. The store creates deterministic job/snapshot IDs, validates every `IntegrationJobSnapshot` against JSON Schema before storage, returns latest snapshots, records retry and clarification-answer scaffold snapshots, records a subscription callback/event shape, rejects unknown and cross-config-entry jobs with `unknown_job`, and unload cleanup removes entry job state. The packet remains non-orchestrating: no worker, model-provider, Home Assistant history, semantic-memory persistence, service/state mutation, token-generation, chart artifact write, durable storage, or real job orchestration occurs. Python tests green in `.venv` (`92 passed`), focused job-state eval green, adjacent WebSocket/dashboard-resource evals green, BDD-evidence review OK, and standalone architecture review OK after resolving the pre-storage schema-validation finding.
- **2026-06-08** — `Home Assistant WebSocket command registration anchor` — Added the paired WebSocket command registration spec, BDD, eval outline, raw evidence, executable eval, Python verifier anchor, fake Home Assistant WebSocket registry harness, and focused tests. Replaced scaffold-only command-name bookkeeping with real `websocket_api.async_register_command` registration for the five accepted `isolinear/v1/` command names, wired registration from `async_setup_entry`, stored the result under the config-entry ID, kept registration idempotent, stripped Home Assistant transport `id` before internal schema validation, and kept Home Assistant's decorator schema to command routing while Isolinear's deterministic validator owns version, payload-shape, forbidden-material, and config-entry-scope errors. Registered callbacks return schema-valid scaffold `IntegrationJobSnapshot` payloads for known config entries and fail closed for unknown, wrong-version, leaky, mutating, malformed, and missing-config-entry commands before orchestration. No worker, model-provider, Home Assistant history, semantic-memory, service/state mutation, token-generation, job-orchestration, or dashboard-resource metadata write occurs in this boundary. Python tests green in `.venv`, focused WebSocket eval green, adjacent scaffold/config-flow/dashboard-resource evals green, BDD-evidence review OK, and standalone architecture review OK after resolving the schema-gate concern.

## Active work

> The current packet broken into checkboxes. Tick at `/closeout`.

### `Home Assistant job orchestration scaffold anchor`

- [x] Add paired job-orchestration scaffold spec, BDD, evidence, and eval outline
- [x] Add config-entry-scoped in-memory orchestration setup from `async_setup_entry`
- [x] Route enabled `isolinear/v1/job/start` commands through the orchestration scaffold
- [x] Compose job state, approved entity catalog, and approved fake history through existing boundaries
- [x] Prove non-catalog rejection before history read, missing approved history failure, ambiguous prompt clarification, schema-valid snapshots, and per-config-entry isolation
- [x] Prove side-effect boundaries with focused tests, executable eval, raw evidence, on-disk verification, BDD-evidence review, and architecture review

## Open queue (non-blocking)

> Things worth doing that don't gate the current packet. Pull from here when the active packet closes.

- (a) Aggregate-style ambiguous entity clarification executable eval
- (b) Aggregate alias creation/reuse executable eval
- (c) Post-MVP floorplan heatmap renderer requiring explicit user-provided room
  geometry and area/entity mappings
- (d) Split follow-on orchestration work into smaller packets: clarification
  continuation, retry continuation, subscription/progress streaming, and
  artifact storage should not land in one packet.

## Blockers

- None.
