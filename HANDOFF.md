# HANDOFF.md

## Current project phase

MVP design phase closed. The first production Home Assistant custom integration
scaffold, config-flow/options surface, dashboard resource registration surface,
WebSocket command registration surface, job state scaffold, approved entity
catalog, approved history retrieval, and job orchestration scaffold are
anchored, including clarification-answer, retry continuation,
subscription/progress, artifact storage, and render planning scaffold paths.
The model-provider planning scaffold, worker dispatch/rendering scaffold,
worker token provisioning/readiness scaffold, worker progress streaming
scaffold, worker retry/backoff policy scaffold, worker transport failure
retry-classification scaffold, worker failure snapshot/manual retry
integration scaffold, worker health/readiness endpoint scaffold, worker token
rotation/repair scaffold, and durable worker health polling checkpoint scaffold
are now anchored. The durable polling maintainability refactor is complete:
the checkpoint still stands as the completed ADR-0015 behavior packet, and the
large production and verifier modules have been split into focused helper
modules without schema, BDD/evidence, eval, or dashboard-card contract changes.

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

Home Assistant job orchestration scaffold anchor is complete.
`custom_components/isolinear/job_orchestration.py` now owns the smallest
production config-entry-scoped `job/start` orchestration scaffold.
`async_setup_entry` initializes one in-memory orchestration store after job
state, approved entity catalog, and approved history retrieval setup. Enabled
`isolinear/v1/job/start` callbacks now create deterministic job state, select
approved entities only through deterministic explicit-ID or single-label-match
resolution, compose approved fake history through the existing retrieval
boundary, append schema-valid planning/fetching-history/scaffold-ready or
failed snapshots, and store per-entry run summaries. Explicit non-catalog
entity IDs fail before history read, missing approved history returns a
structured failed snapshot, and ambiguous prompts including multiple label
matches return a schema-valid `clarification_needed` snapshot without reading
history. This packet remains non-rendering and non-mutating: it does not call
the worker, model provider, semantic-memory storage helpers, Home Assistant
service/state mutation APIs, token generation, chart artifact writes, chart
rendering, durable storage, subscription progress streaming, or production
orchestration beyond scaffold bookkeeping. The paired spec/BDD/eval/evidence
and `evals/home_assistant_job_orchestration_scaffold.py` prove the anchor.
This packet was larger than ideal; follow-on orchestration work should be split
into smaller bounded packets.

Home Assistant job orchestration clarification continuation scaffold anchor is
complete. Enabled `isolinear/v1/clarification/answer` callbacks now resume the
same config-entry-scoped job when its latest snapshot is
`clarification_needed`, require a matching question ID, accept only returned
approved option IDs that resolve to exactly one current approved catalog
entity, retrieve approved fake history through the existing history boundary,
append schema-valid clarification-accepted/fetching-history/scaffold-ready
snapshots, and store per-entry continuation run summaries. Unknown options,
wrong question IDs, colliding option IDs, unknown jobs, non-clarification jobs,
and cross-config-entry jobs fail closed before history read and without
continuation snapshots. The packet remains non-rendering and non-mutating: it
does not call the worker, model provider, semantic-memory storage helpers,
Home Assistant service/state mutation APIs, token generation, chart artifact
writes, chart rendering, durable storage, retry behavior, subscription
progress streaming, or production orchestration beyond scaffold bookkeeping.
The paired spec/BDD/eval/evidence and
`evals/home_assistant_job_orchestration_clarification_continuation_scaffold.py`
prove the anchor.

Home Assistant job orchestration retry continuation scaffold anchor is
complete. Enabled `isolinear/v1/job/retry` callbacks now resume the same
config-entry-scoped job only when its latest snapshot is a failed retryable
scaffold snapshot, reuse the original job prompt through the current approved
catalog and approved fake history retrieval boundary, append schema-valid
retry-accepted/fetching-history/scaffold-ready snapshots, and store per-entry
retry continuation run summaries. Unknown jobs, cross-config-entry jobs, and
non-retryable jobs fail closed before history read and without retry
continuation snapshots. The packet remains non-rendering and non-mutating: it
does not call the worker, model provider, semantic-memory storage helpers,
Home Assistant service/state mutation APIs, token generation, chart artifact
writes, chart rendering, durable storage, subscription progress streaming,
automatic retry loops, worker retry behavior, or production orchestration
beyond scaffold bookkeeping. The paired spec/BDD/eval/evidence and
`evals/home_assistant_job_orchestration_retry_continuation_scaffold.py` prove
the anchor.

Home Assistant job orchestration subscription/progress streaming scaffold
anchor is complete. Enabled `isolinear/v1/job/subscribe` callbacks now validate
the targeted config-entry job's latest `IntegrationJobSnapshot`, record a
deterministic job-state subscription, store one deterministic
config-entry-scoped orchestration progress event envelope containing the latest
schema-valid snapshot, and return that latest snapshot immediately. Unknown jobs and
cross-config-entry jobs fail closed before subscription or progress-event
storage. The packet remains non-rendering and non-mutating: it does not call
the worker, model provider, approved Home Assistant history during subscribe,
semantic-memory storage helpers, Home Assistant service/state mutation APIs,
token generation, chart artifact writes, chart rendering, durable storage,
retry behavior, automatic progress tasks, worker streaming, or production
orchestration beyond scaffold bookkeeping. The paired spec/BDD/eval/evidence
and `evals/home_assistant_job_orchestration_subscription_progress_scaffold.py`
prove the anchor.

Home Assistant job orchestration artifact storage scaffold anchor is complete.
Enabled `isolinear/v1/job/snapshot` callbacks now validate the targeted
config-entry job's latest `IntegrationJobSnapshot`, record one deterministic
config-entry-scoped placeholder artifact metadata envelope for scaffold-ready
jobs, validate it against the `IntegrationArtifactMetadata` schema, append and
return a schema-valid complete snapshot with placeholder chart metadata, and
idempotently reuse existing artifact-backed complete snapshots. Unknown jobs
and cross-config-entry jobs fail closed before artifact metadata or complete
snapshot storage. The packet remains non-rendering and non-mutating: it does
not call the worker, model provider, approved Home Assistant history during
artifact storage, semantic-memory storage helpers, Home Assistant service/state
mutation APIs, token generation, real artifact file writes, chart rendering,
durable storage, retry behavior, automatic progress tasks, worker streaming,
or production orchestration beyond scaffold bookkeeping. The paired
spec/BDD/eval/evidence and
`evals/home_assistant_job_orchestration_artifact_storage_scaffold.py` prove the
anchor.

Home Assistant job orchestration render planning scaffold anchor is complete.
Enabled `isolinear/v1/job/snapshot` callbacks now validate the targeted
config-entry job's latest `IntegrationJobSnapshot`, record one deterministic
config-entry-scoped placeholder render-plan envelope for scaffold-ready jobs,
validate the render plan against `IntegrationRenderPlan`, validate the nested
placeholder `ChartSpec` before storage, reference the same placeholder artifact
metadata, append and return the existing schema-valid artifact-backed complete
snapshot, and idempotently reuse existing render plans and artifacts. Unknown
jobs and cross-config-entry jobs fail closed before render-plan metadata,
artifact metadata, or complete snapshot storage. The packet remains
non-rendering and non-mutating: it does not call Ollama or any model provider,
does not call the worker, does not read approved Home Assistant history during
render planning, does not persist semantic memory, does not mutate Home
Assistant state, does not generate tokens, does not write real artifact files,
does not render charts, and does not add durable storage, retry/backoff,
automatic progress tasks, worker streaming, or production orchestration beyond
scaffold bookkeeping. The paired spec/BDD/eval/evidence and
`evals/home_assistant_job_orchestration_render_planning_scaffold.py` prove the
anchor.

Home Assistant job orchestration model-provider planning scaffold anchor is
complete. Enabled `isolinear/v1/job/snapshot` callbacks now use a
config-entry-scoped Ollama-compatible planner client when provider config is
present, validate the targeted scaffold-ready source snapshot, build
deterministic planner requests from the prompt, approved entity disclosure, and
staged history entity IDs, validate `PlannerResult` and provider-produced
`ChartSpec` before storage, recursively reject hidden entity IDs anywhere in
provider output, record a deterministic `IntegrationModelProviderPlan`
envelope, and store the existing render-plan envelope using the provider
`ChartSpec`. The no-provider placeholder render-plan path remains intact.
Unknown jobs and cross-config-entry jobs fail closed before provider calls,
model-provider plan metadata, render-plan metadata, artifact metadata, or
complete snapshot storage. The packet remains non-rendering and non-mutating:
it does not call the worker, does not read approved Home Assistant history
during model-provider planning, does not persist semantic memory, does not
mutate Home Assistant state, does not generate tokens, does not write real
artifact files, does not render charts, and does not add durable storage,
retry/backoff, automatic progress tasks, worker streaming, or production
orchestration beyond bounded provider/render/artifact bookkeeping. The paired
spec/BDD/eval/evidence and
`evals/home_assistant_job_orchestration_model_provider_planning_scaffold.py`
prove the anchor.

Home Assistant job orchestration worker dispatch/rendering scaffold anchor is
complete. Enabled `isolinear/v1/job/snapshot` callbacks now use a
config-entry-scoped ADR-0012 worker renderer client when an integration-owned
worker token is already present, validate the targeted artifact-ready render
plan and staged approved history, build schema-valid `RenderRequest` and
`WorkerTransportRequest` envelopes, validate worker `RenderResult` responses,
redact bearer authorization before storing metadata or emitting evidence, and
record deterministic `IntegrationWorkerDispatch` envelopes. Existing worker
dispatches, render plans, artifact metadata, and complete snapshots are reused
idempotently. Worker failures, unknown jobs, and cross-config-entry jobs fail
closed before worker dispatch metadata, render-plan metadata, artifact
metadata, or complete snapshot storage. The packet remains read-only and
bounded: it does not read Home Assistant history during worker dispatch, does
not persist semantic memory, does not mutate Home Assistant state, does not
generate tokens, does not write real chart artifact files from the integration,
and does not add durable storage, retry/backoff, automatic progress tasks,
worker streaming, or production orchestration beyond bounded
provider/render/artifact/worker bookkeeping. The paired spec/BDD/eval/evidence
and
`evals/home_assistant_job_orchestration_worker_dispatch_rendering_scaffold.py`
prove the anchor.

Home Assistant worker token provisioning/readiness scaffold anchor is complete.
Config-entry setup now records schema-valid `IntegrationWorkerReadiness`
metadata and keeps worker rendering disabled when no valid integration-owned
token is present. Explicit in-memory token provisioning stores one
config-entry-scoped integration-owned worker token only after validating
redacted readiness metadata, enables the existing ADR-0012 worker renderer
boundary for that entry, reuses existing valid tokens idempotently, rejects
unknown config entries before token generation, rolls back generated tokens when
readiness validation/storage fails, and keeps readiness/tokens isolated per
config entry. The packet remains read-only and bounded: it does not read Home
Assistant history, persist semantic memory, mutate Home Assistant state, call
the worker, render charts, write real artifacts, write durable token storage,
rotate tokens, perform worker health checks, add retry/backoff, start automatic
progress tasks, stream worker progress, or add production orchestration beyond
readiness bookkeeping and renderer gating. The paired spec/BDD/eval/evidence
and `evals/home_assistant_worker_token_provisioning_readiness_scaffold.py`
prove the anchor.

Home Assistant worker progress streaming scaffold anchor is complete. Enabled
`isolinear/v1/job/snapshot` worker render responses may now carry up to five
bounded progress payloads through the existing ADR-0012 worker render response
metadata. The integration validates each progress payload before storage,
appends schema-valid rendering snapshots before the final complete snapshot,
records redacted config-entry-scoped `IntegrationWorkerProgress` envelopes,
includes existing same-job subscription IDs, and idempotently reuses existing
complete/progress metadata without duplicate worker calls or duplicate progress
records. Invalid progress payloads and secret/token-bearing progress text fail
closed before worker progress metadata, worker dispatch metadata, render-plan
metadata, artifact metadata, or complete snapshot storage. The card-facing
WebSocket handler still returns only `IntegrationJobSnapshot` payloads, keeping
worker progress envelopes and worker endpoint metadata internal. The packet
remains read-only and bounded: it does not read Home Assistant history during
worker progress, persist semantic memory, mutate Home Assistant state, generate
tokens, write real artifact files, add durable worker-progress queues/storage,
add retry/backoff policy, add health checks, start automatic progress tasks,
introduce a new worker transport, or add production orchestration beyond
bounded progress bookkeeping. The paired spec/BDD/eval/evidence and
`evals/home_assistant_worker_progress_streaming_scaffold.py` prove the anchor.

Home Assistant worker retry/backoff policy scaffold anchor is complete. Enabled
`isolinear/v1/job/snapshot` worker render failures that return schema-valid
ADR-0012 `RenderResult` envelopes now record one deterministic
config-entry-scoped `IntegrationWorkerRetryPolicy` envelope before returning a
failed snapshot. The policy stores redacted worker request/response metadata,
bounded exponential backoff metadata, retry eligibility, manual-retry
availability, and `automatic_retry_scheduled: false`; it validates against
JSON Schema before storage. Unknown jobs, cross-config-entry jobs, invalid
worker render results, and secret/token-bearing failure codes fail closed
before policy storage or sensitive metadata exposure. The packet remains
read-only and bounded: it does not read Home Assistant history during policy
recording, persist semantic memory, mutate Home Assistant state, generate or
rotate tokens, write real artifacts, create durable retry storage, perform
worker health checks, schedule automatic retries, introduce a new worker
transport, change job retry behavior, or classify `accepted: false` worker
transport responses. The paired spec/BDD/eval/evidence and
`evals/home_assistant_worker_retry_backoff_policy_scaffold.py` prove the
anchor.

Home Assistant worker transport failure retry classification scaffold anchor is
complete. Enabled `isolinear/v1/job/snapshot` worker client responses that
return `accepted: false` before a valid render result now record one
deterministic config-entry-scoped
`IntegrationWorkerTransportFailureClassification` envelope before returning a
failed response. The classification stores redacted worker request metadata,
sanitized failure code/message, deterministic failure family for connection,
HTTP, malformed-response, unavailable, and unknown transport failures, retry
eligibility, manual-retry availability, `automatic_retry_scheduled: false`, and
bounded exponential backoff metadata. Unknown jobs and cross-config-entry jobs
fail closed before worker calls or classification storage, and secret/token
bearing transport failure codes/messages normalize to `worker_transport_failed`
and a generic message before storage or response. The valid failed
`RenderResult` retry/backoff policy path remains unchanged. The packet remains
read-only and bounded: it does not read Home Assistant history during
classification, persist semantic memory, mutate Home Assistant state, generate
or rotate tokens, leak tokens, write real artifacts, create durable retry
storage, perform worker health checks, schedule automatic retries, introduce a
new worker transport, or store worker dispatch/progress/retry-policy/render
plan/artifact/complete metadata for transport failures. The paired
spec/BDD/eval/evidence and
`evals/home_assistant_worker_transport_failure_retry_classification_scaffold.py`
prove the anchor.

Home Assistant worker failure snapshot/manual retry integration scaffold anchor
is complete. Enabled `isolinear/v1/job/snapshot` worker render failures and
worker transport failures now bridge existing validated retry policy and
transport classification metadata into schema-valid card-facing failed
`IntegrationJobSnapshot` payloads. Failed snapshots use sanitized failure
code/message text, `worker_render` or `worker_transport` stage,
`worker_failure_snapshot_ready` progress, and retry affordance derived from the
existing internal `manual_retry_allowed` decision. Enabled
`isolinear/v1/job/retry` callbacks can now resume retryable worker failed
snapshots through the existing retry continuation path, while non-retry-safe
transport failures reject as `job_not_retryable` before approved history reads
or new snapshots. Unknown jobs and cross-config-entry jobs fail closed before
worker calls, worker failed snapshot storage, retry-policy storage, or
transport-classification storage. The card-facing payload remains only an
`IntegrationJobSnapshot`; worker endpoint, request body, bearer authorization,
retry-policy metadata, transport-classification metadata, render-plan metadata,
artifact metadata, and dispatch metadata stay internal/redacted. The packet
remains read-only and bounded: it does not mutate Home Assistant state, persist
semantic memory, generate or rotate tokens, leak tokens, write real artifacts,
create durable retry storage, perform worker health checks, schedule automatic
retries, start automatic progress tasks, introduce a new worker transport, or
add production orchestration beyond the worker failure snapshot bridge. The
paired spec/BDD/eval/evidence and
`evals/home_assistant_worker_failure_snapshot_manual_retry_integration_scaffold.py`
prove the anchor.

Home Assistant worker health/readiness endpoint scaffold anchor is complete.
ADR-0014 now records `GET /v1/health` as the concrete readiness endpoint over
ADR-0012's versioned bearer-authenticated worker transport.
`custom_components/isolinear/worker_health.py` owns the explicit
config-entry-scoped health probe, setup records only health-probe availability
without calling the worker, and eligible probes require an existing same-entry
ready worker client plus integration-owned worker token. Health requests and
responses validate against `WorkerHealthRequest` and `IntegrationWorkerHealth`
schemas; ready and not-ready worker responses store redacted internal health
envelopes, transport failures store schema-valid `unavailable` metadata
without retry/scheduler/durable side effects, and malformed accepted responses
fail closed before storage. Unknown entries and no-token/not-ready entries
fail before worker calls, tokens remain redacted in metadata and evidence, and
dashboard-card payloads do not expose worker endpoint, request, response,
authorization, or internal health metadata. The paired spec/BDD/evidence and
`evals/home_assistant_worker_health_readiness_endpoint_scaffold.py` prove the
anchor.

Home Assistant worker token rotation/repair scaffold anchor is complete.
`custom_components/isolinear/worker_readiness.py` now owns explicit
config-entry-scoped in-memory worker token rotation and repair functions.
Rotation requires an existing valid same-entry integration-owned worker token,
generates a replacement token, invalidates the old token and renderer client,
validates/stores redacted ready readiness metadata, and refreshes the same-entry
renderer setup. Repair creates a valid token only for known no-token entries
with configured worker endpoints. Unknown and cross-entry requests fail before
token generation or state changes, while readiness validation/storage and
renderer setup failures roll back token, readiness, and renderer state. The
packet remains read-only and bounded: it does not call worker render or health
endpoints, persist tokens durably, schedule repair, mutate Home Assistant state,
or expose worker endpoint, token material, readiness, health, or repair
internals to dashboard-card payloads. The paired spec/BDD/evidence and
`evals/home_assistant_worker_token_rotation_repair_scaffold.py` prove the
anchor. Focused and adjacent worker verification is green; the full Python
suite currently has an unrelated codegen sandbox matplotlib subprocess flake
documented in `STATUS.md`.

Home Assistant durable worker health polling checkpoint scaffold is committed.
ADR-0015 is now accepted, and the checkpoint adds
`custom_components/isolinear/worker_health_polling.py` plus setup/unload wiring
behind the existing worker readiness and ADR-0014 health-client boundaries. The
poller stores schema-valid redacted config-entry-scoped latest polling state in
an integration-owned storage-helper surface, enqueues post-setup polling
without setup-time worker calls, runs eligible scheduled health probes through
ADR-0014, applies the 300 second ready cadence and bounded
30/60/120/300/900 second failure backoff, removes targeted state on unload, and
keeps dashboard-card payloads free of worker endpoint, token material, health
internals, scheduler internals, repair recommendations, and durable polling
metadata. Rescue verification on 2026-06-12 reran the focused polling tests
(`17 passed`), adjacent worker regression bundle (`98 passed`), focused
durable polling eval (`PASS home_assistant_durable_worker_health_polling_scaffold`),
full Python suite (`268 passed`), and checkpoint diff formatting
(`git diff --check HEAD~1..HEAD` clean). BDD-evidence review and standalone
architecture review both returned OK with no required follow-up.

Home Assistant durable worker health polling maintainability refactor is
complete. `custom_components/isolinear/worker_health_polling.py` remains the
public orchestration facade, while constants, contract validation, storage
helper behavior, and state/redaction construction now live in focused
`worker_health_polling_*` helper modules. `src/Isolinear/worker_health_polling_anchor.py`
remains the public verifier facade, while fixtures, scenario cases, and the
aggregate verifier live in focused anchor helper modules. The refactor is
behavior-preserving: ADR-0015 polling semantics, schemas, BDD/evidence, eval
output, redaction, dashboard-card safety, and setup/unload wiring remain
unchanged; the existing BDD evidence note was refreshed with the refactor
verification posture. Verification on 2026-06-12 reran focused polling tests
(`17 passed`), the focused durable polling eval
(`PASS home_assistant_durable_worker_health_polling_scaffold`), adjacent
worker regressions (`81 passed`), module `py_compile`, `git diff --check`, and
standalone architecture review. A full `tests/` rerun hit the known unrelated
codegen sandbox matplotlib flake once (`267 passed, 1 failed`), and the exact
failed test passed on rerun.

## Next recommended packet

Choose the next worker/orchestration follow-up:

1. Keep remaining worker work split into small packets rather than extending
   the durable polling checkpoint.
2. Candidate next packets are token rotation UI/persistence/automatic repair,
   provider health/retry policy, durable retry queue/scheduler behavior, or a
   narrow durable-polling production-hardening follow-up if the human wants
   one after reading the durable polling checkpoint/refactor.
3. Preserve the known codegen sandbox matplotlib subprocess flake as a
   historical caveat, but note that the rescue-audit full-suite rerun passed
   cleanly (`268 passed`).

## Known unresolved design details

- Semantic-memory storage-helper implementation, migrations, and repair UI details beyond the envelope contract.
- Aggregate-style ambiguous entity clarification and aggregate alias
  creation/reuse executable evals beyond the existing threshold-backed proofs.
- Worker token rotation UI/persistence/automatic repair semantics, durable
  polling production hardening, and long-running worker progress streaming
  semantics beyond the current bounded worker progress, retry-policy,
  transport-classification, worker-failure snapshot, worker-health, token
  rotation/repair, durable polling scaffolds, and durable polling
  maintainability refactor.
- Production entity-registry, device-registry, area-registry, and label
  adapters beyond the scaffold-compatible approved entity metadata shape.
- Production worker packaging details for matplotlib and target Home Assistant/Raspberry Pi images.
- Post-MVP floorplan heatmap geometry, upload/storage, and room-mapping contract.
- Production worker token rotation persistence/automatic repair behavior,
  provider health/retry policy, durable retry queue/scheduler behavior, and
  orchestration retry/backoff policy beyond scaffold snapshots.

## Session log

Per-session details live in `STATUS.md` (rolling 5-entry log) and git history. See the rolling log at the top of `STATUS.md` for recent session summary (packet name, what closed/changed, test posture). Older sessions are archived in git commits.
