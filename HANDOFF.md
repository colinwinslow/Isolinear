# HANDOFF.md

## Current project phase

MVP design phase closed. The first production Home Assistant custom integration
scaffold, config-flow/options surface, dashboard resource registration surface,
WebSocket command registration surface, job state scaffold, approved entity
catalog, approved history retrieval, and job orchestration scaffold are
anchored, including clarification-answer, retry continuation,
subscription/progress, artifact storage, and render planning scaffold paths.
The model-provider planning scaffold, model-provider retry/backoff policy
scaffold, model-provider health diagnostics scaffold, worker
dispatch/rendering scaffold, worker token provisioning/readiness scaffold,
worker progress streaming scaffold, worker retry/backoff policy scaffold,
worker transport failure retry-classification scaffold, worker failure
snapshot/manual retry integration scaffold, worker health/readiness endpoint
scaffold, worker token rotation/repair scaffold, durable worker health
polling checkpoint scaffold, and durable worker token lifecycle scaffold are
now anchored. The durable
polling maintainability refactor is complete: the checkpoint still stands as
the completed ADR-0015 behavior packet, and the large production and verifier
modules have been split into focused helper modules without schema,
BDD/evidence, eval, or dashboard-card contract changes. A narrow durable
polling hardening follow-up now rejects persisted cancelled polling state
during storage load/resume so unload-cancelled scheduler metadata cannot
resurrect after restart. ADR-0016 now anchors integration-owned durable worker
token lifecycle storage: setup restores only valid same-entry persisted tokens
after lifecycle storage succeeds, fails closed before readiness/renderer setup
on lifecycle storage rejection, and records redacted repair-issue metadata
when restore is impossible.

The reality-pivot implementation packet is now in place under accepted ADR-0017:
the existing Home Assistant WebSocket job flow can use approved metadata,
approved history, an Ollama-compatible planner result, and trusted in-process
matplotlib rendering when the first-real-slice route is enabled and no worker
dispatch is used. ADR-0018 now replaces the temporary WebSocket data URL proof
with production artifact serving: rendered PNG bytes are validated, written to
integration-owned artifact storage, served from `/api/isolinear/artifacts`, and
returned to the dashboard card as same-origin URLs while local filesystem paths
stay server-side. Manual verification has now
run against real Home Assistant core with a real SQLite recorder database and a
network Ollama endpoint using `gemma4:e4b`. That live run closed two runtime
drift issues: registered WebSocket commands now use Home Assistant's
`async_response` scheduler and offload blocking orchestration through Home
Assistant's executor, and the Ollama structured-output schema now narrows
`chart_spec` to the first-slice `time_series` ChartSpec shape.

The dashboard-card long-running smoke hardening packet is complete. The Lit
card now treats `planning`, `fetching_history`, `rendering`, and `validating`
snapshots as active jobs, disables duplicate prompt submission, and polls
`isolinear/v1/job/snapshot` through the integration-owned Home Assistant
connection until a terminal snapshot arrives. The mounted `happy-dom` Vitest
smoke proves delayed `job/start` -> automatic `job/snapshot` -> chart-first PNG
result behavior, while the focused Python smoke proves the same command shapes
complete through the registered WebSocket handler path with only the
allowlisted entity and zero worker dispatches.

The production artifact-serving hardening packet is complete. Config-entry
setup now prepares integration-owned artifact storage and registers the static
artifact path at `/api/isolinear/artifacts`. The first-real-slice
trusted-renderer path validates the render request, render result, PNG payload,
artifact metadata, and final job snapshot around the file write; repeated
snapshot requests reuse the completed PNG and URL; hidden provider entities
still fail before rendering; failed complete-snapshot validation rolls back the
written PNG plus artifact/render/provider bookkeeping; and registered
WebSocket responses expose the served URL without local artifact filesystem
paths. The dashboard-card long-running smoke now expects and renders the served
artifact URL.

The worker-rendered artifact-serving hardening packet is complete. When the
real-slice planner path has a configured worker renderer, the integration sends
the same schema-valid render request through the ADR-0012 worker transport,
requires a successful PNG `RenderResult` with bounded base64 image bytes,
validates the payload, writes it to the existing served artifact store, and
stores rendered artifact metadata plus redacted worker dispatch metadata.
Worker tokens, worker-local paths, local artifact filesystem paths, and base64
image bytes are stripped from registered WebSocket responses. Missing worker
image bytes fail before artifact, render-plan, dispatch, complete-snapshot, or
file storage, oversized image bytes fail the shared schema `maxLength` gate
before decode, and post-write progress rejection removes the just-written PNG
plus artifact-write metadata. The older worker dispatch scaffold still proves
no-file placeholder behavior when the real-slice model-provider plan is absent.

The HACS install-packaging packet is complete. The repository is now shaped as
a HACS custom integration repository with root `hacs.json`, manifest
`issue_tracker` metadata, and exactly one packaged Home Assistant integration
under `custom_components/isolinear`. Runtime JSON Schemas are bundled under
`custom_components/isolinear/schemas`, the dashboard card bundle is bundled
under `custom_components/isolinear/frontend/dist`, local brand icons are
bundled under `custom_components/isolinear/brand`, and runtime validators plus
dashboard resource registration resolve package-local assets so HACS installs
do not require separately copying repo-root `docs/schemas` or `frontend/dist`.
`scripts/frontend.ps1 build` refreshes the packaged card bundle after frontend
builds, and the README now documents the HACS custom-repository install and
redownload update loop.

A live HACS-installed options-flow regression has been closed. When editing
the entity allowlist, plain entity text for
`sensor.family_room_sensor_temperature` could surface a base-level
`must_be_object` if the options flow did not retain the Home Assistant config
entry, while JSON-style pasted list text was validated as a literal malformed
entity ID. The options-flow factory now passes the config entry into
`IsolinearOptionsFlow`, the allowlist normalizer accepts a raw single entity
string and JSON-style pasted list text before the existing schema validation
gate, and the config-flow/options spec, BDD, eval outline, eval, and evidence
capture the regression.

The follow-up live HACS-installed options-flow regression is also closed. A
redownload/restart confirmed the previous commit was installed, but options
editing still returned base-level `must_be_object` when the existing config
entry reached the options flow with missing stored setup data. Options-only
edits now normalize missing config-entry data to the local-first safe defaults
before validation, so `sensor.family_room_sensor_temperature` is accepted from
the same options form while explicitly malformed or secret-bearing config data
continues to fail closed. The visible HACS/Home Assistant package version is
now `0.1.1` in both `manifest.json` and the integration constant, and future
completed implementation packets default to bumping the patch version unless
the human says otherwise.

The live dashboard-card config-entry usability regression is closed in the
repository and is ready for HACS retest. Recreating the card from the picker
previously left `config_entry_id: fake-config-entry`, so clicking **Ask** could
look inert because Home Assistant rejected the command as
`unknown_config_entry` and the card did not surface the rejection. The card now
defaults to `config_entry_id: auto`, the registered WebSocket boundary resolves
`auto` to the only configured Isolinear entry before job state, history,
planner, renderer, or worker code can run, and zero or multiple entries fail
closed with a clear config-entry error. Start-command WebSocket rejections now
render visible failed snapshots instead of leaving the card idle. The visible
package version is now `0.1.2`, the packaged dashboard card bundle has been
rebuilt, bundled schema byte parity is green, and the README documents the
explicit `/config/.storage/core.config_entries` fallback for older builds.

The live `0.1.2` HACS retest showed the repository fix did not yet translate
into a reliable Home Assistant dashboard experience. After redownload/restart
and card recreation, the picker still defaulted to
`config_entry_id: fake-config-entry`; the committed `0.1.2` bundle no longer
contains that string, so the next packet should treat stale dashboard resource
delivery as the primary failure mode. Manually changing the card to
`config_entry_id: auto` also did not produce useful Isolinear WebSocket log
evidence, so the same packet should add lightweight registered-command
observability and make `auto` resolution fall back to Home Assistant's
config-entry registry rather than depending only on `hass.data[DOMAIN]`.

That dashboard resource cache-busting packet is now closed in the repository
and ready for live HACS retest as version `0.1.3`. Lovelace resource metadata
now uses `/api/isolinear/static/isolinear-card.js?v=0.1.3` while the integration
continues to serve the stable static asset path. Existing stale Isolinear
Lovelace resource metadata is updated in place when the base URL matches the
integration card module, avoiding both stale reuse and duplicate resource
records. Registered WebSocket command decisions now write capped runtime-only
observability records and non-secret logs for accepted/rejected command
decisions, and `config_entry_id: auto` can resolve through Home Assistant's
config-entry registry when runtime `hass.data[DOMAIN]` entry data is not
available yet. Zero or multiple candidate entries still fail closed before job
state, history, planning, rendering, worker dispatch, or mutation-capable code
can run.

The live `0.1.3` HACS retest narrowed the dashboard-card issue further:
Home Assistant had the correct single Lovelace resource URL
`/api/isolinear/static/isolinear-card.js?v=0.1.3`, but the card editor still
received the obsolete `config_entry_id: fake-config-entry` value. The
repository is now ready for live HACS retest as version `0.1.4`. The dashboard
card normalizes that legacy placeholder to `auto` before the graphical editor
displays it or any versioned WebSocket command is sent, and mounted-card tests
prove both paths. The package also now includes Home Assistant brand icons at
`custom_components/isolinear/brand/icon.png` and `icon@2x.png`; HACS packaging
tests and eval evidence prove those assets ship with the integration. Lovelace
resource metadata now resolves to
`/api/isolinear/static/isolinear-card.js?v=0.1.4`.

The live `0.1.4` HACS retest then proved the placeholder/cache issue was
closed in a fresh browser: `config_entry_id: auto` reached the dashboard card's
WebSocket request. That exposed the next live boundary bug: Home Assistant's
registered WebSocket routing schema only declared `type`, so Home Assistant
rejected the card's valid `id`/`version`/`config_entry_id`/`prompt` transport
envelope as `extra keys not allowed` before Isolinear could strip transport
metadata and run its deterministic validator. The repository is now ready for
live HACS retest as version `0.1.5`. Registered Isolinear WebSocket handlers
now use a permissive Home Assistant routing schema (`type` plus extra transport
fields) while preserving the strict internal `IntegrationWsCommand` validator:
valid card envelopes route to Isolinear, Home Assistant transport `id` stays
outside the internal command contract, and unexpected card payload keys still
fail closed before orchestration.

The live `0.1.5` HACS retest then proved commands reached Isolinear, but
`job/start` still returned the obsolete job-state scaffold snapshot
(`waiting for a later orchestration packet`, validation `not_run`) instead of
the first-real-slice orchestration path. That happened because registered
WebSocket routing only entered orchestration when the setup-time approved
catalog already had at least one item; an empty or unavailable catalog silently
fell back to the old scaffold. The repository is now ready for live HACS
retest as version `0.1.6`. Once an entry has completed orchestration setup,
registered commands route through orchestration even if the approved catalog is
empty, so the card receives a deterministic approved-entity failure such as
`no_approved_entities_available` rather than `orchestration_not_implemented`.

The live `0.1.6` HACS retest then proved the orchestration gate was fixed, but
exposed an options/catalog refresh bug. Pasting
`["sensor.family_room_sensor_temperature","sensor.bathroom_sensor_temperature"]`
into the allowlist was accepted, but reopening the options form displayed the
stored list as fused text without quotes, brackets, comma, or newline. The
dashboard then still saw an empty approved catalog and failed at
`NO_APPROVED_ENTITIES_AVAILABLE`. The repository is now ready for live HACS
retest as version `0.1.7`. Stored allowlists redisplay as comma-separated text
that round-trips through the existing normalizer, and config-entry setup
registers an options update listener that refreshes the runtime approved
catalog plus allowlist-derived history/orchestration setup metadata before the
next dashboard command.

The live `0.1.7` HACS retest showed the allowlist text no longer fused
separators, but a one-entry allowlist containing
`sensor.bathrrom_sensor_temperature` still produced generic dashboard
`NO_APPROVED_ENTITIES_AVAILABLE`; the Isolinear icon also appeared on the Home
Assistant integrations page but not in HACS. The repository is now ready for
live HACS retest as version `0.1.8`. The options flow uses Home Assistant's
native multi-entity selector for the allowlist while preserving explicit
entity-ID storage and legacy text/list normalization. When catalog setup failed
because the configured allowlist referenced an entity Home Assistant could not
resolve, orchestration now reports `unknown_allowlisted_entity` with the exact
missing ID before any history read rather than flattening the problem into an
empty-catalog dashboard failure; retrying that failed job preserves the same
structured failure. Root `brand/icon.png` and `brand/icon@2x.png` are now
present for HACS and match the package-local Home Assistant brand assets.

The live `0.1.8` HACS retest then proved the Home Assistant multi-entity
picker surface itself worked: a dozen or so temperature sensors could be
selected. The dashboard still failed at `approved_entity_catalog` with generic
`NO_APPROVED_ENTITIES_AVAILABLE`, which showed the saved selector values were
not reaching the runtime catalog. The repository is now ready for live HACS
retest as version `0.1.9`. Catalog setup now treats config-entry `data` and
`options` as mapping-like values rather than requiring plain `dict`, so Home
Assistant read-only mapping options from the selector build the runtime
approved catalog and refresh history/orchestration setup metadata before the
next dashboard command. The attached live logs also showed setup-time schema
`read_text` blocking warnings in worker token lifecycle/readiness/polling;
that remains the existing separate event-loop cleanup item and was not the
catalog-empty failure.

The live `0.1.9` HACS retest then reached the next edge: an ambiguous
temperature prompt correctly produced deterministic clarification options, but
selecting one entity could complete with scaffold placeholder artifact metadata
and a broken served image URL. The repository is now ready for live HACS retest
as version `0.1.10`. Clarification-answer continuation with a configured
planner is covered through the real first-slice path and writes a rendered
served PNG for the selected entity. If the first-real render path has no
configured model-provider planner, snapshot polling now records a card-facing
failed snapshot with `model_provider_planner_not_configured` before artifact
metadata or PNG storage, rather than returning scaffold placeholder success.

The live `0.1.10` HACS retest then proved that clarification no longer returns
placeholder artifact success, but selected-entity continuation still failed at
`model_provider_planner_not_configured`. That exposed the same Home Assistant
read-only mapping shape on config-entry `data` that previously affected
allowlist `options`: model-provider planner setup required a plain `dict` and
therefore disabled the planner even when Ollama settings were present. The
repository is now ready for live HACS retest as version `0.1.11`.
Model-provider planner setup accepts mapping-like config-entry data, and
focused production artifact-serving coverage proves `mappingproxy` config data
configures the planner and completes with a served PNG artifact.

The live `0.1.11` HACS retest then showed the selected clarification entity
reached `job_orchestration_clarification_continuation_ready` and appeared to
start the Ollama planner, but the dashboard card later switched to a local
`SNAPSHOT_POLL_FAILED` state while waiting for `job/snapshot`. The repository
is now ready for live HACS retest as version `0.1.12`. The dashboard card now
retries bounded transient snapshot poll failures such as Home Assistant
frontend timeouts while keeping terminal Isolinear rejections visible, and the
backend snapshot artifact/render path now has per-job single-flight protection:
overlapping snapshot polls during planner/render work return the current active
planning snapshot with `job_orchestration_artifact_snapshot_in_progress`
instead of starting duplicate planner calls. Later snapshot polls reuse the
completed served PNG artifact.

The live `0.1.12` HACS retest still reached `SNAPSHOT_POLL_FAILED`. Edge showed
the prior local snapshot-poll failure text, while the Home Assistant iPhone app
showed `Isolinear WebSocket command rejected.`, proving at least one path was a
registered WebSocket rejection rather than only a frontend timeout wrapper. The
repository is now ready for live HACS retest as version `0.1.13`. The dashboard
card now keeps polling through bounded active-job snapshot failures when Home
Assistant wraps transient timeouts or connection loss as generic `fail`
errors, while terminal Isolinear command errors such as `unknown_job` remain
visible failures. Model-provider output validation failures, including invalid
provider ChartSpecs and hidden-entity provider output, now append sanitized
card-facing failed snapshots with `model_provider_planning` details instead of
surfacing as generic registered WebSocket command rejections; render/artifact
validation failures still fail closed before PNG writes.

The live `0.1.13` HACS retest still showed the card-local
`SNAPSHOT_POLL_FAILED` state, so the repository is now ready for live HACS
retest as version `0.1.14` with stronger backend diagnostic logging rather than
another speculative behavior change. Registered WebSocket command decisions now
log and store sanitized diagnostic fields for Home Assistant message ID,
command type, requested and resolved config-entry IDs, job ID, decision code,
orchestration/result code, snapshot status, progress stage, failure code, and
exception type when present. Unexpected registered Home Assistant WebSocket
handler exceptions are caught at the boundary and returned as structured
`isolinear_websocket_command_exception` errors while logging only sanitized
context. Prompt text, tokens, endpoints, raw history, generated code, generated
images, local filesystem paths, and image bytes remain excluded from the
diagnostic records.

The live `0.1.14` HACS retest then produced useful backend evidence: after the
dashboard reached real recorder history, `job/snapshot` was rejected with
`code=in_process_renderer_failed`, identifying the trusted matplotlib renderer
path rather than a frontend-only polling issue. The repository is now ready for
live HACS retest as version `0.1.15`. The Home Assistant manifest declares the
trusted renderer runtime dependency `matplotlib==3.11.0`, and packaging/scaffold
proof fails if that dependency is omitted. In-process renderer failures now
append sanitized card-facing failed job snapshots with
`failure.stage: chart_rendering` and `failure.code: in_process_renderer_failed`
instead of surfacing as snapshot-poll command rejections; no PNG file, artifact
metadata, render plan, or provider plan is written on that failure path.

## Product summary

Isolinear lets a user ask natural-language questions about approved Home Assistant entities and receive generated data visualizations based on entity history.

## Current architecture direction

- Home Assistant custom integration.
- Install/update path is HACS custom repository of type `integration`.
- TypeScript Lit custom dashboard card as the first UI (`custom:isolinear-card`).
- Optional Home Assistant add-on worker for rendering and sandbox execution.
- Standalone worker mode should remain possible for Home Assistant installs that cannot use add-ons.
- Model provider should be Ollama-compatible, with local-first defaults and optional stronger providers later.
- Trusted chart-spec renderer is the default path.
- The first real prompt-to-chart route renders trusted ChartSpecs either in-process or through the configured worker renderer and returns a same-origin served PNG artifact URL.
- Sandboxed matplotlib codegen is an advanced path.

## Open implementation status

Fake-provider vertical slice implemented as a local Python module with schema-backed contract validation, a pre-render plan validation gate, deterministic render metadata validation, trusted safe-mode rendering for shaded interval overlays, state interval timelines, and aggregate bar charts, fake binary-state interval extraction, confirmed threshold-derived interval extraction, deterministic threshold clarification for continuous power sensors, use-once threshold confirmation handling, deterministic threshold semantic alias creation, reuse of saved threshold aliases, deterministic invalidation of saved threshold aliases that reference unavailable or non-allowlisted entities, and a versioned semantic-memory store envelope anchor that computes invalidity at use time while failing closed for unsupported versions or duplicate alias IDs. Eval scripts now emit structured `CASE` evidence payloads, and implemented eval-backed scenario groups have paired markdown BDD/evidence files under `bdd/<feature>/`.

First real vertical slice pivot implementation is complete and manually
verified against live services through real Home Assistant core and the
registered WebSocket handler path. `custom_components/isolinear` now has a
trusted in-process matplotlib renderer for safe numeric `time_series`
ChartSpecs, best-effort real Home Assistant registry/state metadata enrichment,
best-effort recorder-history retrieval, an async-safe registered WebSocket
bridge, an Ollama structured-output schema narrowed to the first-slice
ChartSpec shape, and a first-real-slice route in the existing
`isolinear/v1/job/start` -> `job/snapshot` flow. The route now writes real PNG
bytes to integration-owned artifact storage and returns
`/api/isolinear/artifacts/<artifact_id>.png` through the card-facing snapshot.
The focused pytest proves the served PNG URL and on-disk PNG signature,
card-facing model-provider failure snapshots for hidden-entity and invalid
provider chart output before rendering/artifact storage, rollback on failed
complete-snapshot validation, idempotent completed-snapshot reuse, no local
filesystem paths in registered WebSocket render details, and no worker
dispatch for the in-process route. A follow-up worker-rendered artifact pytest
now proves the same served URL contract when a configured worker returns
validated PNG bytes, including idempotence, missing-byte failure before storage,
oversized-byte schema rejection, progress-failure rollback, worker render
failure handling, bearer redaction, and path-safe registered WebSocket
responses. The manual
evidence proves real recorder history plus `gemma4:e4b` can complete the same
route with only the allowlisted entity; the production hardening packet replaces
that temporary data URL output with the served artifact URL contract.

Dashboard card implementation technology is decided in ADR-0011: the MVP card is a TypeScript Lit custom element loaded as `custom:isolinear-card`, bundled as an ES module, and kept as a thin client over integration-owned Home Assistant WebSocket commands. The card must not directly call the worker, model provider, Home Assistant history APIs, semantic-memory storage, mutation services, or browser local storage for Isolinear state.

Dashboard card anchor implementation is complete. The repo now has a
Node-backed frontend anchor under `frontend/` with TypeScript Lit source, a
checked-in Vite ES module bundle, fake Home Assistant harness, fixture job
snapshots, Vitest adapter coverage, Python verifier/eval coverage, and raw
BDD evidence proving idle, planning, clarification, complete, failed, and
integration-boundary scenarios. Repo-local setup scripts create `.venv`, run
pytest, resolve the Windows Node.js install, and run frontend install/build/test
commands without depending on ambient PATH. A long-running mounted-card smoke
now covers the active prompt workflow beyond static fixture rendering: delayed
prompt submission, automatic snapshot polling, duplicate-submit suppression,
and chart-first PNG completion.

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

Home Assistant model-provider retry/backoff policy scaffold anchor is
complete. Enabled `isolinear/v1/job/snapshot` callbacks now record one
deterministic config-entry-scoped `IntegrationModelProviderRetryPolicy`
envelope when a configured planner returns a retry-safe provider failure. The
policy stores provider metadata, deterministic planner request metadata,
sanitized failure code/message text, manual-retry/backoff decision metadata,
and `automatic_retry_scheduled: false`, validates against JSON Schema before
storage, and returns only a schema-valid failed `IntegrationJobSnapshot` to the
dashboard card. Malformed retry metadata, secret-like provider failure text,
unknown jobs, and cross-config-entry jobs fail before provider retry-policy
storage. The packet remains read-only and bounded: it does not add provider
health polling, automatic retry, durable retry queues, worker behavior, chart
rendering, token persistence, dashboard UI, or Home Assistant mutation. The
paired spec/BDD/evidence and
`evals/home_assistant_model_provider_retry_backoff_policy_scaffold.py` prove
the anchor.

Home Assistant model-provider health diagnostics scaffold anchor is complete.
Config-entry setup now records explicit provider-health probe availability
without calling the provider. The provider health boundary validates a
schema-valid Ollama-compatible `ModelProviderHealthRequest` for `GET /api/tags`,
calls only the same-entry configured planner client, stores one
schema-valid `IntegrationModelProviderHealth` envelope for `ready`,
`not_ready`, and `unavailable` results, and rejects malformed or
secret-bearing accepted health responses before storage. Unknown entries and
unconfigured entries fail before provider calls or health metadata storage.
Dashboard-card payloads remain unchanged and do not expose provider endpoint,
request details, provider response internals, or internal health metadata. The
paired spec/BDD/evidence and
`evals/home_assistant_model_provider_health_diagnostics_scaffold.py` prove the
anchor.

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

Home Assistant durable worker health polling cancelled-state hardening is
complete. Persisted `IntegrationWorkerHealthPollingState` entries whose
scheduler metadata has `cancelled: true` are now rejected during
storage-helper load/resume, preventing unload-cancelled timer metadata from
being re-merged after restart. The scaffold spec, BDD, eval outline, evidence,
verifier anchor, and focused tests now prove cancelled persisted polling state
is skipped before merge while valid persisted entries, token-missing
diagnostics, and unsaved in-memory state remain intact. Verification on
2026-06-12 reran the focused polling tests (`17 passed`), focused durable
polling eval (`PASS home_assistant_durable_worker_health_polling_scaffold`),
adjacent worker regressions (`98 passed`), module `py_compile`, and
`git diff --check`. Standalone architecture review returned OK with no
recommendations.

Home Assistant durable worker token lifecycle scaffold is complete. ADR-0016
records the storage-helper credential persistence decision and the packet adds
`custom_components/isolinear/worker_token_lifecycle.py` plus setup wiring before
worker readiness and renderer setup. Config-entry setup loads the lifecycle
store, restores only valid same-entry persisted tokens after schema-valid
lifecycle storage succeeds, blocks readiness/renderer setup if lifecycle storage
fails, stores redacted `not_ready` repair-issue metadata when no token can be
restored, and stores disabled lifecycle state when no worker endpoint exists.
Durable explicit provision, rotation, and repair wrappers persist raw token
material privately and roll back old durable token, readiness, and renderer
state on lifecycle validation/storage failure. Dashboard-card token controls,
real Home Assistant Repairs flows, setup-time token generation, automatic repair
execution, worker health/render calls, provider calls, durable retry queues,
scheduler tasks, Home Assistant mutation, and token/endpoint leakage remain out
of scope. Verification on 2026-06-13 reran focused lifecycle tests
(`11 passed`), the focused lifecycle eval
(`PASS home_assistant_durable_worker_token_lifecycle_scaffold`), adjacent
worker regressions (`109 passed`), module `py_compile`, adjacent
worker/orchestration evals, `git diff --cached --check`, inline BDD-evidence
review, and standalone architecture review. The full Python suite previously
hit the known unrelated codegen sandbox matplotlib subprocess flake once
(`298 passed, 1 failed`), and the exact failed test passed on rerun.

## Next recommended packet

Run the live HACS `0.1.15` dashboard verification. Redownload Isolinear through
HACS, restart Home Assistant, recreate the dashboard card, and confirm the
registered Lovelace resource URL includes `?v=0.1.15` while the picker/editor
shows `config_entry_id: auto`, including when Home Assistant had previously
handed the card the old `fake-config-entry` placeholder. Confirm a stored
allowlist reopens through the multi-entity selector with the exact selected
entity IDs and the dashboard route sees those approved entities without another
restart. Confirm the integration icon appears both where Home Assistant
surfaces custom integration brand assets and where HACS reads repository-root
brand assets.
Then run both the explicit served-artifact prompt path and the ambiguous
clarification-answer path against real Home Assistant sensor history and the
configured Ollama planner, using the WebSocket decision observability and
Isolinear log lines to capture accept/reject evidence if the card cannot start
or refresh a job. The key log line shape is:
`Isolinear WebSocket command accepted/rejected: message_id=... type=...
requested_config_entry_id=... resolved_config_entry_id=... job_id=...
code=... result_code=... snapshot_status=... progress_stage=...
failure_code=... exception_type=...`.
If the card remains on `job_orchestration_clarification_continuation_ready`
while Ollama is busy, wait for subsequent snapshot polls; transient frontend
snapshot timeouts or generic Home Assistant `fail` timeout wrappers should no
longer replace the active job with `SNAPSHOT_POLL_FAILED`. If overlapping polls
are observed, the registered response may report
`job_orchestration_artifact_snapshot_in_progress` until the first
planner/render request finishes.
If the card reports a model-provider failure, it should now arrive as a
card-facing failed snapshot with `failure.stage: model_provider_planning` and a
specific code such as `invalid_model_provider_chart_spec` rather than generic
`Isolinear WebSocket command rejected.`
If the card reports a trusted renderer failure, it should now arrive as a
card-facing failed snapshot with `failure.stage: chart_rendering` and a specific
code such as `in_process_renderer_failed` rather than generic
`SNAPSHOT_POLL_FAILED`; inspect Home Assistant dependency installation and
renderer logs before changing card polling behavior again.
If the logs show `code=isolinear_websocket_command_exception`, inspect the same
line's `type`, `job_id`, `result_code`, `snapshot_status`, `progress_stage`,
`failure_code`, and `exception_type` before changing card behavior again.
If the card reports an approved-entity failure, inspect the configured
allowlist, runtime options-update listener, and entity catalog setup result
rather than treating it as a future-orchestration placeholder.
If the card reports `model_provider_planner_not_configured`, inspect the
config entry's Ollama-compatible planner settings and the model-provider setup
metadata before investigating artifact serving.
Confirm no worker token, worker-local path, local artifact path, or base64
image bytes leak to card-facing WebSocket responses.

Preserve the known codegen sandbox matplotlib subprocess flake as a historical
caveat; the first-real-slice closeout full Python suite passed cleanly
(`303 passed`) before this manual verification follow-up.

## Known unresolved design details

- Semantic-memory storage-helper implementation, migrations, and repair UI details beyond the envelope contract.
- Aggregate-style ambiguous entity clarification and aggregate alias
  creation/reuse executable evals beyond the existing threshold-backed proofs.
- Optional future allowlist picker ergonomics beyond Home Assistant's native
  multi-entity selector, such as device/area/label grouping. The stored
  allowlist must remain explicit entity IDs.
- Worker token rotation UI or real Home Assistant Repairs/automatic repair
  semantics,
  automatic/durable provider retry semantics, additional durable polling
  production hardening if requested, and long-running worker progress
  streaming semantics beyond the current bounded provider retry-policy,
  provider health diagnostics, worker progress, worker retry-policy,
  transport-classification, worker-failure snapshot, worker-health, token
  rotation/repair, durable token lifecycle, durable polling scaffolds, durable
  polling maintainability refactor, and cancelled-state hardening.
- Production entity-registry, device-registry, area-registry, and label
  adapters beyond the scaffold-compatible approved entity metadata shape.
- Live Home Assistant dashboard browser smoke against a real dev server remains
  unresolved; the completed hardening packet covers a mounted card plus the
  registered command path, and the prior manual proof used real Home Assistant
  core with a test connection object.
- Production worker packaging details for matplotlib and target Home Assistant/Raspberry Pi images.
- Post-MVP floorplan heatmap geometry, upload/storage, and room-mapping contract.
- Production worker token rotation UI or real Home Assistant Repairs/automatic
  repair behavior, automatic/durable provider retry behavior, durable retry
  queue/scheduler behavior, and orchestration retry/backoff policy beyond
  scaffold snapshots.

## Session log

Per-session details live in `STATUS.md` (rolling 5-entry log) and git history. See the rolling log at the top of `STATUS.md` for recent session summary (packet name, what closed/changed, test posture). Older sessions are archived in git commits.
