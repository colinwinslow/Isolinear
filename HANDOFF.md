# HANDOFF.md

## Current project phase

MVP design phase closed. The first production Home Assistant custom integration
scaffold, config-flow/options surface, dashboard resource registration surface,
WebSocket command registration surface, job state scaffold, and approved entity
catalog and approved history retrieval scaffolds are anchored. The next packet
should define the first job orchestration scaffold that uses the approved
catalog/history surfaces while preserving the existing schema-first, BDD-first
workflow.

## Product summary

Isolinear lets a user ask natural-language questions about approved Home Assistant entities and receive generated data visualizations based on entity history.

## Current architecture direction

- Home Assistant custom integration.
- TypeScript Lit custom dashboard card as the first UI (`custom:isolinear-card`).
- Optional Home Assistant add-on worker for rendering and sandbox execution.
- Standalone worker mode should remain possible for Home Assistant installs that cannot use add-ons.
- Model provider should be Ollama-compatible, with local-first defaults and optional stronger providers later.
- Trusted chart-spec renderer is the default path.
- Sandboxed matplotlib codegen is an advanced path.

## Open implementation status

Fake-provider vertical slice implemented as a local Python module with schema-backed contract validation, a pre-render plan validation gate, deterministic render metadata validation, trusted safe-mode rendering for shaded interval overlays, state interval timelines, and aggregate bar charts, fake binary-state interval extraction, confirmed threshold-derived interval extraction, deterministic threshold clarification for continuous power sensors, use-once threshold confirmation handling, deterministic threshold semantic alias creation, reuse of saved threshold aliases, deterministic invalidation of saved threshold aliases that reference unavailable or non-allowlisted entities, and a versioned semantic-memory store envelope anchor that computes invalidity at use time while failing closed for unsupported versions or duplicate alias IDs. Eval scripts now emit structured `CASE` evidence payloads, and implemented eval-backed scenario groups have paired markdown BDD/evidence files under `bdd/<feature>/`.

Dashboard card implementation technology is decided in ADR-0011: the MVP card is a TypeScript Lit custom element loaded as `custom:isolinear-card`, bundled as an ES module, and kept as a thin client over integration-owned Home Assistant WebSocket commands. The card must not directly call the worker, model provider, Home Assistant history APIs, semantic-memory storage, mutation services, or browser local storage for Isolinear state.

Dashboard card anchor implementation is complete. The repo now has a
Node-backed frontend anchor under `frontend/` with TypeScript Lit source, a
checked-in Vite ES module bundle, fake Home Assistant harness, fixture job
snapshots, Vitest adapter coverage, Python verifier/eval coverage, and raw
BDD evidence proving idle, planning, clarification, complete, failed, and
integration-boundary scenarios. Repo-local setup scripts create `.venv`, run
pytest, resolve the Windows Node.js install, and run frontend install/build/test
commands without depending on ambient PATH.

Worker API transport and authentication is designed and anchored in ADR-0012.
The card-facing API is a versioned Home Assistant WebSocket command set under
`isolinear/v1/` for job start, clarification answer, retry, snapshot retrieval,
and subscription. The worker-facing render API is a versioned HTTP JSON
envelope for `POST /v1/render` authenticated with an integration-owned bearer
token that is never sent to the dashboard card or model provider. The repo has
schemas, a Python verifier, tests, eval evidence, and frontend adapter coverage
for the command/envelope contract, bad-auth and bad-version rejection, and token
redaction.

Sandbox implementation for Raspberry Pi compatibility is anchored. The worker
sandbox spec now defines the concrete codegen strategy: schema validation before
execution, static AST safety checks, isolated Python subprocess execution with
`-I`, stripped environment, fixed `render_chart(data, output_path)` entry point,
runtime audit hook, fixed output-path writes, subprocess timeout, Linux
`resource` CPU/address-space requests where available, and max output image
size enforcement. The repo has a `CodegenSandboxPolicy` schema, Python anchor,
focused tests, executable eval, and paired BDD/evidence proving safe fixed-entry
execution, exact generated-code import allowlisting, allowlisted matplotlib
`Agg` rendering, forbidden import/file/environment/network rejection before
execution, runtime audit denial for arbitrary reads routed through
`pyplot.imread`, oversized output failure, and capped repair-loop behavior with
static checks rerun on every attempt. The dev environment now installs
matplotlib through `requirements-dev.txt`; production worker packaging remains
responsible for providing matplotlib in the isolated worker image.

First trusted renderer release scope is anchored. The chart-spec rendering spec
now defines the safe-mode trusted scope as `time_series` charts with numeric
`line` series, entity-backed sources, no transform except `none`, optional
`shaded_intervals` overlays from supplied `DerivedInterval` records, PNG output,
and no fallback into codegen. The Python trusted-renderer anchor validates
render contracts, fails unsupported schema-valid primitives with structured
`unsupported_chart_spec` details before writing output artifacts, and reports
zero codegen attempts. The renderer BDD/evidence and
`evals/trusted_renderer_primitives.py` prove supported line/overlay rendering
and unsupported primitive rejection. The spec records six follow-up trusted
renderer families: state interval timeline, aggregate bar, calendar/hour
heatmap, event markers, distribution/histogram, and scatter/correlation.
Floorplan heatmaps are deferred until post-MVP because Home Assistant floors
and areas do not provide room geometry; they will require explicit
user-provided geometry and area/entity mappings.

Trusted renderer state interval timeline follow-up is anchored. The chart-spec
rendering spec now selects `state_interval_timeline` as the first follow-up
family and defines safe-mode `timeline` charts with binary/categorical `step`
tracks, entity-backed sources, no transform except `none`, one matching
`DerivedInterval` per track, absolute time-range metadata, PNG output, and no
codegen fallback. The Python anchor uses chart-family-specific unsupported
checks so `time_series` remains limited to numeric `line` series while
`timeline` requires state-like history and matching derived intervals. Timeline
rendering fails closed before artifact creation if the derived interval source
entity does not match the chart series source. The BDD/evidence and
`evals/state_interval_timeline.py` prove timeline rendering, deterministic
metadata, validation, and zero codegen attempts.

Trusted renderer aggregate bar chart follow-up is anchored. The chart-spec
rendering spec now defines the `aggregate_bar_chart` family as safe-mode
`bar` charts with aggregate numeric series, `source.type: aggregate`, one bar
per source entity, `mean`/`min`/`max`/`sum`/`count` operations, no transform
except `none`, no overlays, PNG output, and no codegen fallback. The Python
anchor adds bar-family primitive checks so time-series and timelines remain
entity-backed while bars require aggregate sources. Aggregate rendering
computes values from matching numeric `HistorySeries` records over the chart
time range, emits deterministic x-range metadata, and fails closed before
artifact creation if any aggregate source history is missing or has no numeric
points. The BDD/evidence and `evals/aggregate_bar_chart.py` prove rendering,
metadata, validation, and zero codegen attempts.

Trusted renderer calendar/hour heatmap follow-up is anchored. The chart-spec
rendering spec now defines the `calendar_hour_heatmap` family as safe-mode
`heatmap` charts with one numeric entity-backed series rendered as weekday-by-hour
mean cells from `x_axis.group_by: hour` and `y_axis.group_by: weekday`, no
transform except `none`, no overlays, PNG output, and no codegen fallback. The
Python anchor adds heatmap-family primitive checks for source type, render
primitive, series count, and supported grouping while preserving the existing
time-series, timeline, and bar constraints. Heatmap rendering fails closed
before artifact creation if source history is missing or has no numeric points
in range. The BDD/evidence and `evals/calendar_hour_heatmap.py` prove rendering,
metadata, validation, and zero codegen attempts.

Trusted renderer event markers and distribution/histogram follow-up is anchored.
The chart-spec rendering spec now defines safe-mode `markers` overlays on
numeric `time_series` charts and safe-mode `histogram` charts with one numeric
entity-backed series. Marker overlays are derived from matching validated
`HistorySeries` records using state `active_values`, numeric threshold
crossings, or event-kind points; histogram rendering computes deterministic
fixed-count value bins from `x_axis.bin_count` with a default of 8 bins. The
Python anchor adds marker and histogram primitive checks while preserving the
existing time-series, timeline, bar, and heatmap constraints. Marker rendering
fails closed before artifact creation if source history is missing or no marker
events match; histogram rendering fails closed before artifact creation if
source history is missing or no numeric points exist in range. The BDD/evidence
and `evals/event_markers.py` plus `evals/distribution_histogram.py` prove
rendering, metadata, validation, and zero codegen attempts.

Trusted renderer scatter/correlation follow-up is anchored. The chart-spec
rendering spec now defines safe-mode `scatter` charts with exactly two numeric
entity-backed series rendered as paired values. Scatter specs must provide
`x_axis.source_series_id` matching the first series and
`y_axis.source_series_id` matching the second series. The Python anchor pairs
numeric points only by exact matching timestamps inside the chart time range,
emits deterministic absolute time-range metadata, writes PNG output, and never
falls back into codegen. Scatter rendering fails closed before artifact creation
for unsupported series counts, mismatched axis source IDs, unsupported sources
or history kinds, missing source history, and histories with no paired numeric
points. The BDD/evidence and `evals/scatter_correlation.py` prove rendering,
metadata, validation, and zero codegen attempts.

MVP design readiness review is complete. The review artifact at
`docs/mvp-design-readiness-review.md` records a READY verdict for the first
Home Assistant custom integration scaffold. ADR-0012, the integration API
transport/authentication spec, and the paired BDD are now accepted because the
schema/test/eval/evidence anchor has landed. Eval-outline entries now exist for
the already-executable codegen sandbox, dashboard card, and integration
transport/authentication anchors.

Home Assistant integration scaffold anchor is complete. The repo now has a
minimal `custom_components/isolinear` package with a Home Assistant
`manifest.json`, domain constants, local-first config/options validation for
model endpoint, worker endpoint, render mode, repair attempts, and entity
allowlist, plus fail-closed `isolinear/v1/` WebSocket command-boundary stubs.
The scaffold accepts schema-valid command shapes and returns schema-valid
`IntegrationJobSnapshot` scaffold snapshots while rejecting unknown,
wrong-version, leaky, mutating, credential-bearing endpoint, and secret-like
configuration payloads before orchestration. It does not call the worker, model
provider, Home Assistant history APIs, semantic-memory storage helpers, or Home
Assistant mutation services. The paired spec/BDD/eval/evidence and
`evals/home_assistant_integration_scaffold.py` prove the anchor. Standalone
architecture reviews should use the updated 10 minute timeout guidance in
`codex/review-architecture.md`.

Home Assistant config flow/options anchor is complete. The manifest now enables
`config_flow`, and `custom_components/isolinear/config_flow.py` provides a
minimal Home Assistant user config step plus options init step. The flow reuses
the existing pure config/options validation helpers, normalizes blank optional
model fields to `null`, normalizes user-facing allowlist text into a
deterministic entity list, and rejects credential-bearing endpoints,
secret-like values, unsupported render modes, duplicate allowlists, malformed
entity IDs, and forbidden secret material before config-entry or options
persistence. The packet remains non-orchestrating: it does not call the worker,
model provider, Home Assistant history APIs, semantic-memory storage helpers,
Home Assistant services, token generation, or dashboard resource registration.
The paired spec/BDD/eval/evidence and
`evals/home_assistant_config_flow_options.py` prove the anchor.

Home Assistant dashboard resource registration anchor is complete. ADR-0013
now records that the integration auto-registers the dashboard card resource.
`custom_components/isolinear/dashboard_resource.py` serves the checked-in
`frontend/dist/isolinear-card.js` bundle from `/api/isolinear/static` and
creates or reuses one Lovelace `module` resource at
`/api/isolinear/static/isolinear-card.js` during `async_setup_entry`. The
registration result is stored under the config-entry ID, repeated setup is
idempotent, pre-existing matching metadata is reused, missing bundles and
unavailable resource collections fail closed before metadata creation, and the
packet explicitly reports dashboard resource metadata creation/reuse as the
only allowed Home Assistant write. It does not call the worker, model provider,
Home Assistant history APIs, semantic-memory storage helpers, Home Assistant
service/state mutation APIs, token generation, job orchestration, or extra
WebSocket command registration. The paired spec/BDD/eval/evidence and
`evals/home_assistant_dashboard_resource_registration.py` prove the anchor.

Home Assistant WebSocket command registration anchor is complete. The
integration now registers the five accepted `isolinear/v1/` card-facing command
names through Home Assistant's `websocket_api.async_register_command` boundary
during `async_setup_entry`. The registration result is stored under the
config-entry ID, repeated setup is idempotent, Home Assistant transport `id`
metadata is stripped before internal command validation, and config-entry scope
is checked before any scaffold snapshot is returned. Home Assistant's decorator
schema owns only command routing; Isolinear's deterministic validator owns
version, payload-shape, forbidden-material, and config-entry-scope rejection so
wrong-version, leaky, mutating, malformed, unknown, and missing-config-entry
commands fail closed with structured errors before orchestration. Registered
callbacks still return schema-valid scaffold `IntegrationJobSnapshot` payloads
until a later packet replaces the scaffold behavior. The boundary does not call
the worker, model provider, Home Assistant history APIs, semantic-memory
storage helpers, Home Assistant service/state mutation APIs, token generation,
job orchestration, or dashboard-resource metadata writes. The paired
spec/BDD/eval/evidence and
`evals/home_assistant_websocket_command_registration.py` prove the anchor.

Home Assistant job state scaffold anchor is complete.
`custom_components/isolinear/job_state.py` now owns the smallest production
in-memory job state surface behind the registered WebSocket commands.
`async_setup_entry` initializes one config-entry-scoped job store, registered
callbacks use it after deterministic command validation and config-entry scope
validation, and `async_unload_entry` removes entry job state by removing the
entry data. The store creates deterministic job IDs and snapshot IDs for a
fresh runtime, validates every scaffold `IntegrationJobSnapshot` against JSON
Schema before storage, returns latest snapshots, records retry and
clarification-answer scaffold snapshots, records a subscription callback/event
shape, rejects unknown and cross-config-entry job IDs with structured
`unknown_job` errors, and keeps all state scoped to the command's
`config_entry_id`. This packet remains non-orchestrating: it does not call the
worker, model provider, Home Assistant history APIs, semantic-memory storage
helpers, Home Assistant service/state mutation APIs, token generation, chart
artifact writes, durable storage, or real job orchestration. The paired
spec/BDD/eval/evidence and `evals/home_assistant_job_state_scaffold.py` prove
the anchor.

Home Assistant approved entity catalog scaffold anchor is complete.
`custom_components/isolinear/entity_catalog.py` now owns the smallest
production config-entry-scoped approved entity catalog surface.
`async_setup_entry` builds and stores one in-memory catalog from the configured
`entity_allowlist` plus fake Home Assistant entity/state metadata, producing
only schema-valid `EntityCatalogItem` records with `visible_to_agent: true`.
Catalog construction validates every item before storage/return, stores
atomically, keeps catalogs isolated per config entry, rejects unknown
allowlisted entities, clears any previous catalog on rejected rebuilds so stale
metadata cannot remain visible, and rejects malformed allowlists and malformed
normalized items with structured errors before storage. This packet remains
non-orchestrating: it does not call the worker, model provider, Home Assistant
history APIs, semantic-memory storage helpers, Home Assistant service/state
mutation APIs, token generation, chart artifact writes, WebSocket command
registration, dashboard-resource metadata writes, durable storage, or real job
orchestration. The paired spec/BDD/eval/evidence and
`evals/home_assistant_approved_entity_catalog_scaffold.py` prove the anchor.

Home Assistant approved history retrieval scaffold anchor is complete.
`custom_components/isolinear/history_retrieval.py` now owns the smallest
production config-entry-scoped approved history retrieval surface.
`async_setup_entry` initializes one in-memory history retrieval store after the
approved entity catalog setup. Retrieval gates requested entity IDs against
visible approved catalog items before reading fake Home Assistant history,
normalizes approved raw state records into schema-valid `HistorySeries`
records, validates every series before storage/return, stores atomically, keeps
stores isolated per config entry, rejects non-catalog entities before history
read, clears stale history on rejected retrievals, and rejects malformed raw
history and malformed normalized series with structured errors before storage.
This packet remains non-orchestrating: it does not call the worker, model
provider, semantic-memory storage helpers, Home Assistant service/state
mutation APIs, token generation, chart artifact writes, chart rendering,
WebSocket command registration, dashboard-resource metadata writes, durable
storage, or real job orchestration. The paired spec/BDD/eval/evidence and
`evals/home_assistant_approved_history_retrieval_scaffold.py` prove the anchor.

## Next recommended packet

Home Assistant job orchestration scaffold anchor:

1. Write paired BDD/evidence before code for the first integration-owned job
   orchestration scaffold behind `isolinear/v1/job/start`.
2. Build the smallest inspectable config-entry-scoped orchestration flow that
   uses the existing job state, approved entity catalog, and approved history
   retrieval surfaces without calling the model provider or worker.
3. Keep the packet non-rendering and non-mutating: no model-provider calls,
   worker calls, semantic-memory persistence, token generation, chart artifact
   writes, chart rendering, Home Assistant service/state mutation, durable
   storage, or production progress streaming.
4. Prove deterministic scaffold state transitions, catalog/history gate
   failures, per-config-entry isolation, schema-valid snapshots before
   storage/return, and structured errors for missing approved history.
5. Prove the anchor with unit tests, a focused eval, raw evidence, on-disk
   verification, BDD-evidence review, and standalone architecture review.

## Known unresolved design details

- Semantic-memory storage-helper implementation, migrations, and repair UI details beyond the envelope contract.
- Aggregate-style ambiguous entity clarification and aggregate alias
  creation/reuse executable evals beyond the existing threshold-backed proofs.
- Worker token rotation UI, worker health/readiness endpoint, and long-running
  progress streaming semantics.
- Production entity-registry, device-registry, area-registry, and label
  adapters beyond the scaffold-compatible approved entity metadata shape.
- Production worker packaging details for matplotlib and target Home Assistant/Raspberry Pi images.
- Post-MVP floorplan heatmap geometry, upload/storage, and room-mapping contract.
- Production Home Assistant job orchestration, subscription streaming, retry
  semantics, and artifact storage beyond scaffold snapshots.

## Session log

Per-session details live in `STATUS.md` (rolling 5-entry log) and git history. See the rolling log at the top of `STATUS.md` for recent session summary (packet name, what closed/changed, test posture). Older sessions are archived in git commits.
