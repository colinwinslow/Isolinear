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

The live `0.1.15` HACS redownload then showed commit `18f95bd` installed, but
the dashboard resource metadata still pointed at
`/api/isolinear/static/isolinear-card.js?v=0.1.14` after a full hardware
reboot. Local proof already showed stale query-string Isolinear resources
update in place when Lovelace resource storage is available, so the likely live
gap was cold-boot ordering: Isolinear setup could run before Lovelace resource
storage existed because the manifest declared no Lovelace dependency. The
repository is now ready for live HACS retest as version `0.1.16`. The Home
Assistant manifest declares `dependencies: ["lovelace"]`, HACS packaging proof
fails if that dependency is omitted, and dashboard resource evidence proves the
current package-versioned URL is `?v=0.1.16`.

The live `0.1.16` reinstall then failed before the first setup form rendered:
Home Assistant spent about 30 seconds on
`Please wait, starting configuration wizard for Isolinear` and returned
`Config flow could not be loaded: 500 Internal Server Error`. That points to
pre-flow integration loading rather than config-flow validation. The repository
is now ready for live HACS retest as version `0.1.17`. The renderer-only
`matplotlib==3.11.0` manifest requirement has been removed so Home Assistant
does not try to install a heavy compiled dependency before config-flow loading;
the trusted in-process renderer still imports matplotlib lazily and returns a
sanitized card-facing chart-rendering failure if the module is unavailable.
HACS/scaffold proof now fails if renderer-only config-flow-blocking
requirements are reintroduced, and dashboard resource evidence proves the
current package-versioned URL is `?v=0.1.17`.

Subsequent live tests confirmed `0.1.17`/`0.1.18` loaded but charts failed
closed with `RENDERER_DEPENDENCY_UNAVAILABLE` (matplotlib not present), so
`0.1.19` re-added `matplotlib>=3.7,<4` as a loose-range manifest requirement.
That install also failed: on the live Home Assistant Python 3.14 runtime the
range resolved to `matplotlib==3.11.0`, which has no prebuilt wheel for CPython
3.14, so pip built from source and failed with
`PermissionError: [Errno 13] Permission denied: 'meson'` (the package-install
sandbox cannot run the meson build backend). A failed manifest-requirement
install makes the integration fail to load entirely, which is why `0.1.19`
showed "not loaded" and left the dashboard resource pinned at `?v=0.1.18`
(setup never reached resource registration). matplotlib-via-manifest is a dead
end in this environment.

ADR-0019 resolves this: the trusted in-process renderer now draws with Pillow,
which Home Assistant core already ships, so the manifest declares no renderer
`requirements` (now `[]`). The renderer identifier is `in_process_pillow` (the
`IntegrationArtifactMetadata` schema enum is updated in both synced copies), the
scaffold guard forbids any `matplotlib` requirement regardless of version pin,
and the renderer imports Pillow lazily and still fails closed as
`renderer_dependency_unavailable` if it is somehow absent. The render interface,
supported scope (safe numeric `time_series` line charts), failure codes, and
served-PNG artifact contract are unchanged.

Live `0.1.20` then confirmed the Pillow renderer works end-to-end, but the chart
was illegible on a phone and the window was wrong. `0.1.21` enlarged the
renderer fonts/strokes for the mobile downscale and (temporarily) added a
keyword regex for the window. The window design was then redirected to be
model-driven, landing as `0.1.22` across ADR-0020 and ADR-0021.

ADR-0020 makes the chart time window **model-resolved**: the planner request
carries `now` and the Home Assistant `time_zone`; the planner emits an absolute
`chart_spec.time_range {start, end}`; the integration validates and clamps it
deterministically (tz-normalize to UTC, `start < end`, clamp `end <= now`, span
`<= 366` days, floor `60s`) and falls back to a fixed last-24h window on any
failure (no planner, missing/invalid/unclampable window). The keyword regex is
removed entirely. For the first-real-slice path, history is now fetched **after**
planning using the resolved window, so a window older than recorder retention is
no longer rejected at `job/start`; the legacy scaffold path keeps its start-time
raw fetch (statistics tiering is opt-in through an `allow_statistics` flag).

ADR-0021 adds a **tiered history data source**: raw recorder states for
recent/short windows, hourly long-term statistics up to 60 days, and daily
statistics beyond that, single-source-per-window. Long-term statistics are read
through `statistics_during_period` (read-only, off the event loop via the
existing executor offload). Each `HistorySeries` records its `source`
(`recorder_states` | `long_term_statistics`) and `resolution`
(`raw` | `hourly` | `daily`); statistics buckets carry `value` (mean) plus
`value_min`/`value_max`, and the Pillow renderer shades a min/max band behind the
mean line. An entity without long-term statistics over a beyond-retention window
fails closed with a card-facing `no_long_term_statistics` snapshot. The
HistorySeries schema gains the band point fields and the source/resolution
fields; the planner request gains `now`/`time_zone` (propagated into the
model-provider plan and retry-policy schemas); all synced schema copies are
byte-identical. The repository is ready for live HACS retest as version `0.1.22`;
the next packet is live confirmation of the model-resolved window and the
statistics tier (the only path whose live recorder calls are not unit-tested).

Live `0.1.22` testing then confirmed single-entity long-term-statistics charts
render correctly and surfaced two classes of Home Assistant event-loop/threading
warnings (open-queue item (f)), resolved in `0.1.23` as an event-loop / executor
hygiene packet with no contract changes. First, bundled JSON Schema files were
read and parsed on the event loop on every contract validation. A memoized
`load_schema_document()` plus `preload_schema_documents()` were added in
`_paths.py`; all 24 schema read sites across the integration now use the cached
loader, and `async_setup_entry` warms the cache from an executor before the first
validating setup step, so first reads happen off-loop and later validations are
cache hits. The loader returns a deep copy, preserving the prior per-call
fresh-dict contract. Second, recorder reads (`get_significant_states`,
`statistics_during_period`) ran on Home Assistant's general executor rather than
the recorder's dedicated database executor. A new `_read_via_recorder_executor()`
seam in `history_retrieval.py` bounces the read through the loop onto
`recorder.get_instance(hass).async_add_executor_job(...)` via
`asyncio.run_coroutine_threadsafe(...).result(timeout=60)` — sound because job
orchestration runs synchronously on a general-executor worker thread distinct
from both the loop and the recorder executor — and falls back to an inline read
when no recorder or loop is present (repo tests, non-recorder installs). The
architecture review returned OK (no invariant violation, no new ADR). The
session also created the missing `.claude/agents/code-reviewer.md` subagent
definition, which the architecture-review protocol referenced but which had no
backing agent file (a Codex-port dangling reference). The repository is ready for
live HACS retest as version `0.1.23`; live confirmation that the schema and
recorder blocking-call warnings are gone is folded into the existing live retest
item. The seam's real-HA leg remains `# pragma: no cover` (exercised in tests via
a fake recorder on a real background loop), so the warning removal needs the live
retest to confirm.

A card-facing failure-logging packet then landed as `0.1.24` (open-queue item
(g) part (1)). During `0.1.22` live testing the `binary_sensor.kitchen_door`
"not on the approved list" failure produced no visible Isolinear log line: a
command can be *accepted* at the WebSocket boundary yet return a card-facing
failed `IntegrationJobSnapshot` (`status: failed` with a `failure.code`), and
`_record_websocket_decision` logged those at `INFO` because the decision was
"accepted". `_record_websocket_decision` in `websocket_api.py` now escalates the
visible log to `WARNING` whenever the command is rejected **or** an accepted
command returns a failed snapshot (status `failed` or any captured
`failure_code`), so failure codes such as `entity_not_in_approved_catalog`,
`no_long_term_statistics`, and `in_process_renderer_failed` are diagnosable from
Home Assistant logs instead of buried at `INFO`. The visible log line now also
prints `failure_stage` next to `failure_code` (both were already in the runtime
observability record). No schema or contract changed — log level and format
only — so no ADR was required and the change is below the architecture-review
bar; the WebSocket-command-registration spec's observability requirement now
records the per-outcome log level and the `failure_stage` field. Item (g) part
(2) — whether the all-or-nothing approved-catalog rebuild should fail per-entity
instead of clearing the whole catalog — remains open. The repository is ready
for live HACS retest as version `0.1.24`; the live retest should confirm a
kitchen_door-class failure now emits a visible HA `WARNING` log line.

A categorical timeline render family then landed as `0.1.25` under **ADR-0022**,
resolving the `binary_sensor.kitchen_door` failure for real rather than
dead-ending it. The `0.1.24` WARNING logging surfaced the precise cause: the
door prompt failed with `model_provider_chart_spec_hidden_entity` at the
planning stage, not the intended `no_long_term_statistics`. A binary entity
cannot satisfy the numeric-only planner schema, so the model substituted an
entity and the deterministic entity-validation gate rejected it **before**
history retrieval (the ADR-0020 reorder runs history after planning, so the
planning failure masks the stats gate). The fix makes binary/categorical
entities chart: the integration now **deterministically routes the render family
from each resolved entity's `_series_kind` before planning** (new invariant #9):
all-numeric → `time_series`/`line`; all binary/categorical → a new
`timeline`/`step` family; mixed numeric + binary → fail closed with
`mixed_chart_composition_unsupported` (the overlay composition is the documented
0.1.26 target, ADR-0022 D4/D5). The integration selects the per-family Ollama
structured-output schema (`load_planner_result_schema(family)`), so the model
never picks `chart_type`. The live Pillow renderer gained `_render_timeline_png`
(one lane per series, binary on/off fills + categorical bands, phone-legible)
built on a shared `_binary_on_regions` primitive that the 0.1.26 overlay reuses
without a rewrite. The misleading hidden-entity code was split into honest
`model_provider_referenced_unapproved_entity` (absent from the approved catalog)
vs `model_provider_substituted_entity` (approved but not disclosed for this job);
the legacy code is retained as a classification alias. No **core** schema change
was needed — `chart-spec.schema.json` already allows `timeline`/`step` and a
first-class `overlays[]` array. The `no_long_term_statistics` gate stays after
planning for its intended numeric class (not regressed); a beyond-retention
binary timeline fails closed through that same gate. Verification: full suite
`388 passed`, new `timeline_render_family_routing` eval + 51 prior evals `PASS`,
the two-lane timeline anchor PNG eyes-on verified legible at a 380px phone
downscale, architecture review `OK` (no invariant violations), BDD-evidence
review `OK`, `git diff --check` clean, bump to `0.1.25`. **Caveat:** unit- and
artifact-verified; the live HACS `0.1.25` retest should confirm a real
`binary_sensor` prompt renders an on/off timeline instead of the old
hidden-entity failure. The numeric + binary overlay ("temperature and when the
AC was running") is open-queue item (i) for `0.1.26`.

The numeric + binary overlay composition then landed as `0.1.26`, completing
ADR-0022's target architecture (D4/D5). "Show me the temperature and when the AC
was running" now renders a numeric `time_series` line with the binary entity
shaded as `shaded_intervals` overlay bands behind it. `_resolve_render_family`
gained a `time_series_overlay` family for **exactly one numeric primary + one or
more binary** entities; for that family the planner is disclosed **only** the
numeric primary as a chartable series (new `entity_ids` argument on
`_model_provider_planner_request`), and the integration injects the binary
overlays deterministically **after** planning via `_compose_binary_overlays`
(the model never composes overlays — invariant #9 / D5). The live Pillow numeric
renderer gained an overlay pass: vertical "on"-region bands across the full plot
height drawn behind the primary line, reusing the `_binary_on_regions` primitive
from 0.1.25; the numeric unsupported-gate now accepts `shaded_intervals` overlays
with an entity source and rejects any other overlay shape with
`unsupported_chart_spec`. `select_prompt_entity_ids` auto-resolves a fuzzy prompt
matching one numeric + one-or-more binary entities to the composition
(`source: numeric_with_overlay`) instead of single-entity clarification. The
composition is **binary-only** by design (architecture-review scope tightening):
a non-binary categorical mixed with numeric has no "on" region to shade, so it
stays `mixed` (fail closed) rather than shading nothing, and two or more numeric
series mixed with a binary also stay `mixed` (no deterministic primary). No core
schema change was needed (`overlays[]` is already first-class). The entity
allowlist invariant holds: restricting the planner disclosure only narrows what
the model may chart, while the injected overlay entity is still validated against
the full disclosed `source_snapshot`. Verification: full suite `393 passed`,
`timeline_render_family_routing` eval extended with the overlay routing + render
cases + 51 prior evals `PASS`, the temperature+AC overlay anchor PNG eyes-on
verified legible at a 380px phone downscale, architecture review `OK` (no
invariant violations; its one note — categorical-as-overlay — was addressed by
the binary-only tightening), BDD-evidence review `OK`, `git diff --check` clean,
bump to `0.1.26`. **Caveat:** unit- and artifact-verified; the live HACS `0.1.26`
retest should confirm a real mixed prompt renders the overlay.

Night mode (dark theme) is now a recorded open-queue item ((h) in `STATUS.md`)
with the design decisions captured: scope is **chart PNG + card UI**, theme
source is **auto-follow the Home Assistant theme** (no user toggle), and it
needs a spec plus likely an ADR before implementation because the resolved theme
must be plumbed card -> `job/start` -> render request (schema-touching) and the
Pillow renderer needs a second dark palette baked at render time. It is intended
to be picked up in a fresh session.

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

The matplotlib loose-range requirement restoration packet is complete. Live
`0.1.18` testing confirmed the lazy-import fail-closed path fires correctly —
the card surfaced `failure.stage: chart_rendering` /
`RENDERER_DEPENDENCY_UNAVAILABLE` / "The trusted chart renderer dependency is
not installed in this Home Assistant environment." Charts cannot render on a
fresh HA install without matplotlib, so `matplotlib>=3.7,<4` is restored to
manifest `requirements`. The strict-pin `matplotlib==3.11.0` that caused the
0.1.16 config-flow 500 is not reused; a loose range delegates version selection
to pip's resolver so exact-pin conflicts with HA's own dependency set are
avoided. The integration scaffold guard is narrowed from flagging any
`matplotlib` prefix to flagging only `matplotlib==` exact pins, so future
accidental re-introduction of strict pins is still caught. The HACS packaging
spec, eval YAML, and proof assertions now require `matplotlib>=3.7,<4`. The
lazy-import fail-closed path remains intact as a backstop when pip install fails
in the target environment. The visible package version is `0.1.19`.

The planner entity_id enum-pin packet is complete (`0.1.27`). Live `0.1.26`
testing kept failing a binary-door prompt at `model_provider_planning` with
`model_provider_referenced_unapproved_entity` even though binary→`timeline`
routing was confirmed live. Root cause: the Ollama structured-output schema left
chart-spec `source.entity_id` a free string, so a small local model could
hallucinate an off-allowlist entity that the post-plan entity gate then rejected.
`load_planner_result_schema(family, *, entity_ids=…)` now pins `source.entity_id`
to an `enum` of exactly the disclosed entities (deduped; blanks dropped), and the
planning call site passes `request["approved_entity_ids"]` so the enum matches
the disclosure; constrained decoding now makes an off-allowlist entity
structurally impossible while the deterministic post-plan gate (Scenario L) stays
as defence in depth (no core schema-file change — the chart-spec sub-schema is
built in code). The packet also adds DEBUG request/response logging on the
`custom_components.isolinear.model_provider` logger (off by default; outgoing body
+ raw provider content + transport errors; no tokens/secrets on the planner path)
to diagnose future chart families. BDD Scenario P + evidence added. Verified
against the real Pillow renderer this session: full suite `394 passed, 3 failed`
(the 3 are the pre-existing codegen-sandbox subprocess flake, confirmed identical
on clean baseline); the live `0.1.27` retest still owes confirmation that a real
binary-door prompt now renders instead of failing at planning.

The structural provider-output entity gate packet is complete (`0.1.28`). The
live `0.1.27` retest revealed the enum-pin was correct but the binary-door prompt
*still* failed `model_provider_referenced_unapproved_entity`: gemma returned a
valid `timeline` spec referencing the approved entity, and the captured DEBUG
response proved the rejection came from our own validation. Root cause:
`validate_model_provider_output_entities` ran the `ENTITY_ID_IN_PROMPT` regex over
**every string** in provider output and mistook the model's `chart_id` slug
`binary_sensor.kitchen_door_timeline` for an off-allowlist entity reference. The
broad textual scan (`_entity_ids_in_provider_output` /
`_walk_provider_output_entity_ids`) was removed; the gate is now **structural** —
it validates only the fields that carry data-access or persistence meaning:
chart-spec `series`/`overlays` sources (unchanged) plus a new
`_memory_proposal_entity_ids` check for `memory_proposals` (a persisted, reusable
reference). Entity-shaped tokens in inert free-text fields (`chart_id`, `title`,
`notes`, axis metadata, `reasoning_summary`) are no longer treated as references —
the renderer never reads them, so this loses no real safety while removing the
false-positive class. The `ENTITY_ID_IN_PROMPT` regex remains for user-prompt
entity parsing only. Posture chosen with Colin: structured-only, with inert
mentions fail-soft and off-allowlist `memory_proposals` still failing closed. The
entity enum-pin (0.1.27) is unchanged; invariant #1 holds (and is strengthened —
it no longer false-rejects valid plans). The recursive anchor/test/eval were
reworked to `hidden_memory` (rejects) + `entity_named_chart_id` (renders), and the
planning-scaffold spec, BDD Scenario C, and evidence were corrected to the new
posture (Scenario C also carried the pre-ADR-0022 stale code
`model_provider_chart_spec_hidden_entity`, now fixed). The repository is ready for
a live HACS `0.1.28` retest confirming the real binary-door prompt now renders a
timeline.

The render-family capability envelope direction is captured as **ADR-0023**
(**accepted**, commit `5010302`) with a paired spec
(`render-family-capability-envelope.md`) and BDD that remain `draft` (they accept
when the implementation anchor lands). The decision: the integration computes a
deterministic *capability envelope* (the set of chart families the resolved data
*shape* supports — density is fail-soft, not a gate), the model selects the
family within it from user intent, and a deterministic post-plan gate rejects
out-of-envelope choices (`model_provider_chart_family_out_of_envelope`). It
revises ADR-0022 invariant #9. First live-renderer tranche is `histogram` +
`aggregate_bar`. Nothing is implemented yet.

The entity-selection specificity + timeout + timeline-readability packet is
complete (`0.1.29`). The live `0.1.28` retest **confirmed** the structural gate
fix — the binary-door prompt renders a timeline end-to-end — but surfaced that
entity *disambiguation* is the next rigidity: every multi-entity prompt forced a
clarification because the catalog matcher matched on *any* shared meaningful
token ("kitchen door" matched both `binary_sensor.kitchen_door` and
`climate.kitchen_ecobee` on the lone shared `kitchen`). **ADR-0024 is accepted**
and its **D1** is implemented: `select_prompt_entity_ids` now scores each
candidate by *how many* of its distinctive tokens the prompt contains and selects
the uniquely top-scoring approved entity (`source: catalog_label_specificity`)
when the set isn't an overlay composition; a top-score *tie* still clarifies
(offering only the tied candidates). Invariant #1 is refined in CLAUDE.md/AGENTS.md
— clarification is the *fallback*, not the first response to any multi-match, and
the allowlist boundary is unchanged. **D2** (model-driven selection on residual
ambiguity — a tie or zero matches) is staged as the next packet: it adds a small
pre-routing model selection call so the user sees a clarification card only when
the model itself abstains, and it ties into the ADR-0023 envelope work. The same
packet raised `DEFAULT_OLLAMA_TIMEOUT_SECONDS` 30 → 90 (a successful live call took
29.8s against the 30s wall; mixed/overlay prompts timed out at exactly 30s), and
fixed the binary timeline renderer to draw a light "off" track across the full
window with the "on" regions on top and an on/off legend, so a door closed all
morning reads as present-but-off instead of a blank lane. **ADR-0025 is drafted**
(not implemented): stream the model's reasoning into the card's chart slot as
ephemeral wait-feedback (`stream:true` + a bounded, sanitized `progress.reasoning`
on the active planning snapshot, surfaced through the existing ~1s poll loop,
replaced by the chart on completion). The cheaper "reasoning on the finished card"
(Tier 1) was rejected by product direction (no clutter); ADR-0025 implementation
is deferred until after ADR-0024 D2 so it streams across both model calls.
Verification: full suite `404 passed, 3 failed` (the 3 = pre-existing
codegen-sandbox flake), relevant evals `PASS`, renderer verified on disk,
architecture review (inline) `OK`. The repository is ready for a live HACS
`0.1.29` retest confirming the kitchen-door prompt skips clarification, mixed
prompts no longer time out, and the timeline reads clearly. Remaining cosmetic:
the timeline lane label clips against the axis.

The `0.1.29` live retest confirmed disambiguation is working. Two bugs surfaced
during testing of the `time_series_overlay` path and are fixed in `0.1.30`. First,
`select_prompt_entity_ids` composite detection was blocked when a categorical entity
(e.g., `climate.kitchen_ecobee`) matched a shared token alongside a numeric+binary
pair — the old guard required all non-numeric matches to be binary, so the composite
path was never reached and the temperature entity was dropped. The guard now requires
only one numeric match plus at least one binary match; categorical noise matches are
discarded (ADR-0022 D4 amended to document this). Second, `validate_chart_spec_contract`
now calls `_check_chart_spec_no_duplicate_series_sources` and rejects chart specs where
two series share the same `(type, entity_id, attribute)` source — this catches the
class of model error where a constrained planner returns two series from the same
entity with hallucinated labels. Verification: full suite `406 passed, 3 failed`
(pre-existing codegen flake), relevant evals `PASS`, architecture review CONCERNS
resolved via ADR-0022 D4 amendment. The repository is ready for a live HACS `0.1.30`
retest with a numeric temperature sensor + binary door sensor in the allowlist.

The model-driven entity selection packet (ADR-0024 D2) is complete (`0.1.31`).
When the deterministic specificity fast-path cannot resolve — a top-score tie
among candidates or zero catalog matches — the orchestrator now asks the model
to select the entity before showing the user a clarification card. A new
`select_entity` call on the planner client sends the candidate entity IDs as a
JSON Schema enum (constrained decoding, same pattern as the 0.1.27 planner
enum-pin) and returns the model's selection. The returned IDs are validated
against both the candidate set and the full approved catalog; any off-allowlist
result fails closed, and model abstention (`clarification_needed`) falls through
to the existing D3 clarification path. When no model provider is configured the
D2 step is skipped entirely. `select_prompt_entity_ids` was extended to include
`candidate_items` in its clarification return so D2 receives the narrowed
candidate set on ties and the full catalog on zero-matches. The BDD (5 scenarios
A–E) is accepted with 14 tests passing. Verification: full suite `420 passed, 3
failed` (pre-existing codegen-sandbox matplotlib subprocess flake, confirmed not
introduced by this packet), all evals `PASS`, BDD-evidence review `OK`,
architecture review `OK`.

**ADR-0025 — live planner reasoning streaming — shipped in `0.1.32`,
bug-fixed in `0.1.33`, hardened in `0.1.34`.** The full workflow landed in
`0.1.32` (ADR accepted, spec, BDD, TDD with 23 tests, frontend bundle rebuild):
the Ollama-compatible planner now streams (`stream: true`), the model's thinking
trace is sanitized and length-capped (2000-char rolling tail) into a per-job
live-reasoning slot, surfaced as `progress.reasoning` + a coarse phase label on
the active planning snapshot through the existing poll loop, and replaced by the
chart (or failure card) on completion. The reasoning is never persisted — the
stored snapshot is never mutated and the slot is cleared in a `finally` on any
terminal state. Streaming spans both model calls (D2 `select_entity` +
`plan_chart`); non-streaming/non-thinking providers fall back gracefully (D6,
nothing shown). The Lit card renders a monospace reasoning block
(`data-testid="planning-reasoning"`) in the chart slot during the wait.

`0.1.33` fixed two bugs found in live testing: (1) thinking-capable Ollama
models never streamed because `"think": true` was never sent — it is now sent on
streaming planner + entity-selector requests only (non-streaming calls
untouched); (2) `resolve_history_window` forced the 24h fallback whenever the
model returned naive ISO 8601 (no offset) — `_parse_window_timestamp` now treats
naive datetimes as UTC instead of rejecting them. Both fixes are test-covered
(`test_streaming_request_sets_think_true`,
`test_streaming_select_entity_request_sets_think_true`,
`test_non_streaming_select_entity_omits_think`,
`test_naive_timestamps_are_treated_as_utc`,
`test_parse_window_timestamp_attaches_utc_to_naive`).

`0.1.34` closed a redaction gap found by this closeout's architecture review:
`sanitize_reasoning` redacted URLs, `Bearer …`, and filesystem paths but **not**
the named secret vocabulary the rest of the card-facing surface already guards
against (`access_token`, `*_token`, `ollama_api_key`, `api_key`), nor bare
secret-like tokens (`sk-…` keys, JWTs). Since the thinking trace is unsanitized
model echo of a prompt that can contain such material, this was an invariant-3 /
ADR-0025 D5 gap. `sanitize_reasoning` now mirrors
`FORBIDDEN_WORKER_PROGRESS_TEXT`'s vocabulary plus `sk-…`/JWT patterns, with four
new redaction tests; entity IDs and the user prompt are still retained. No core
schema change. Verification: full suite `451 passed, 3 failed` (the 3 = the
pre-existing codegen-sandbox subprocess flake), all evals `PASS`, BDD-evidence
review `OK`, architecture review CONCERNS resolved by the `0.1.34` hardening.

`0.1.35` fixed two bugs found while retesting the `0.1.34` reasoning-streaming
build, both correcting existing behavior (no new architecture):

1. **`think`/`format` mutual exclusivity (ADR-0025 D1 correction).** A
   thinking-capable Ollama model still emitted no reasoning because the streaming
   payloads sent `think: true` *and* the structured-output `format` schema
   together — and Ollama silently suppresses thinking whenever `format` is set.
   ADR-0025 D1 had assumed both could coexist; they cannot. The streaming
   (reasoning) path now sends `think: true` and **omits** `format`, relying on
   system-prompt schema guidance plus a new `_strip_markdown_json` helper that
   strips the markdown code fences thinking-mode models wrap around their JSON.
   The non-streaming fallback keeps `format` for strict constrained decoding (it
   requests no thinking). This was confirmed as the last blocker to live
   reasoning streaming for thinking-capable models. ADR-0025 D1 and the streaming
   spec carry a correction note; the existing streaming-payload tests
   (`test_streaming_request_sets_think_true`,
   `test_streaming_select_entity_request_sets_think_true`,
   `test_non_streaming_select_entity_omits_think`) cover the contract and the BDD
   evidence file was refreshed (30 tests).

2. **Stopword fix for distinctive-token scoring (ADR-0022/0024 path).**
   `"temperature"` was wrongly excluded from the distinctive-token set in
   `_catalog_item_meaningful_tokens` (alongside the HA component prefixes
   `sensor`/`binary`), so a "kitchen temperature" prompt scored only on
   `kitchen` and tied with `kitchen_door`. `temperature` now counts toward the
   score, so an ecobee temperature sensor outscores a co-located door sensor
   instead of tying. Covered by the existing vertical-slice entity-selection
   tests.

No core schema change. These are bug fixes in existing mechanisms, so no new
spec/BDD/ADR was created (only correction notes to the ADR-0025/streaming-spec
text the `format` discovery invalidated) and a full architecture-review subagent
was not run (one-line fixes in documented mechanisms, below the review bar).
Verification: full suite `451 passed, 3 failed` (the 3 = the pre-existing
codegen-sandbox subprocess flake, confirmed identical on the clean baseline),
relevant model-provider/streaming/entity-resolution evals `PASS`, BDD-evidence
review `OK`.

`0.1.36` corrected the `0.1.35` fix again — the same ADR-0025 D1 mechanism, one
more layer down. Dropping `format` from the streaming call (the `0.1.35` change)
restored thinking, but it also removed `format`'s constrained decoding from the
*only* model call, and without that structural guarantee the model produced
invalid JSON structure on harder prompts (wrong field names, missing required
fields). Jobs that asked about entities **not** in `approved_entity_ids` — e.g.
"show me temperature and when the AC was running" — failed with
`invalid_planner_result` because the model hallucinated the schema structure.
The fix is a **two-pass approach**: when `on_reasoning` is provided, both
`plan_chart` and `select_entity` now make two sequential `/api/chat` calls.
*Pass 1 (think pass)* — `stream:true, think:true, no format` — streams the
reasoning chunks to the card via `on_reasoning`; its content is discarded and its
failures are non-fatal (reasoning is presentational, D6). *Pass 2 (plan/select
pass)* — `stream:false, format:result_schema, no think` — returns reliable,
schema-constrained JSON; this is the call whose result is parsed and validated.
When `on_reasoning` is None the sole call is Pass 2 (unchanged D6 fallback), so
`_strip_markdown_json` is no longer load-bearing for the result path. This
restores both live reasoning *and* constrained decoding at the cost of one extra
call. ADR-0025 D1 carries a "two-pass correction (0.1.36)" note and the streaming
spec's "Streaming planner transport (D1)" section was rewritten; no contract,
schema, or BDD change (transport-layer fix in a documented mechanism). Tests:
five cases in `tests/test_live_planner_reasoning_streaming.py` were updated to
handle the two-call pattern (routing the fake transport on the request `stream`
flag); `30 passed`. Verification: full suite `451 passed, 3 failed` (same
pre-existing codegen-sandbox flake, identical on clean baseline via `git stash`),
model-provider planning eval `PASS`, BDD-evidence review `OK`.

`0.1.38` fixed the final reason reasoning never appeared in the card. The
architecture (ADR-0025 D3: "surfaced through the existing poll loop at ~1s
granularity") was correct; the implementation failed to achieve the stated
granularity. The poll loop was **sequential** — each poll awaited the WebSocket
response before scheduling the next. The first post-submit poll acquires
`planning_lock` and drives all model calls (~40 s); no second poll fired during
that window, so every in-progress snapshot carrying `progress.reasoning` was
computed but never delivered. The fix (in `isolinear-card.ts`): call
`scheduleSnapshotPoll(generation)` **before** `await getSnapshot()`. Polls now
fire every 1 s regardless of response time. Concurrent polls hit the held
`planning_lock`, return in-progress snapshots with live reasoning immediately
(< 1 ms server cost), and the card renders them. The `pollGeneration` counter
plus `cancelSnapshotPolling()` guard stale responses when the main poll
eventually returns the complete snapshot. No server-side change. No ADR update
(D3 matches the behavior; the polling mechanism is implementation detail).
Frontend smoke tests: poll interval bumped 5 ms → 20 ms (longer than the 5 ms
mock response) so call-count assertions remain exact. Architecture review not
run (frontend-only polling bug fix; no invariant affected).

`0.1.39` adds two operational improvements with no user-facing behavior change: (1) **Entity resolution DEBUG logging** (`job_orchestration.py`): seven `_LOGGER.debug()` calls throughout `select_prompt_entity_ids` — catalog entity list on entry, explicit entity IDs in the prompt, per-candidate scores, and the resolution path taken (single match, overlay composition, unique top scorer, or tie → clarification). Requires `custom_components.isolinear.job_orchestration: debug` in `configuration.yaml`. This was requested after the live 0.1.38 retest to diagnose why "kitchen temperature + AC" dropped `climate.kitchen_ecobee`: the entity IS in the allowlist but its name has no overlap with the token "AC", so the temperature sensor wins specificity (3 tokens vs 2); the root fix is semantic alias live wiring (packet #1). (2) **`num_predict: 512` cap on think pass** (`model_provider.py`, both `_chat_payload` and `_entity_selector_payload`): caps thinking-token generation during the think pass to reduce live latency from 24–44 s to ~10–15 s; the result pass (Pass 2) is uncapped. No new ADR, spec, or BDD — both changes are below the user-facing behavior bar. Verification: `444 passed` (pre-existing codegen-sandbox subprocess flake excluded), entity-catalog and model-provider-planning evals PASS, BDD-evidence review OK. Also records the 0.1.38 live retest findings: reasoning streaming not visible — most likely Edge serving a cached pre-0.1.38 bundle despite `?v=0.1.38`; polling code IS correct in the deployed bundle.

`0.1.37` fixed a semantic bug exposed by the `0.1.36` constrained-decoding pass.
The `_chat_payload` planning rules carried an unconditional rule 2 — "Return
status chart_spec_ready with a ChartSpec for this packet." With Pass 2 now
reliably producing schema-valid JSON, the model satisfied that rule even on
prompts asking about something **not** in `approved_entity_ids`, by relabeling or
reusing an approved entity to stand in for the missing one. For "show me maren's
room temperature and when the AC was running" with only
`sensor.maren_ecobee_sensor_temperature` approved, it returned two series both
sourced from that one temperature entity ("Room Temperature" + "Kitchen AC
Status") — structurally valid, semantically wrong, and a soft brush against
invariant 1 (clarify, never silent guess). The fix replaces the unconditional
rule with three: (1) return `clarification_needed` with a `clarification_question`
when the prompt references a device/sensor/concept not represented by any
approved entity — never invent, relabel, or reuse an entity to stand in for a
missing one; (2) return `chart_spec_ready` only if every requested piece of
information is satisfiable with approved entities; (3) each series must represent
a distinct approved entity, never multiple series for the same `entity_id`. This
is a prompt-engineering change inside `_chat_payload`; the `plan_chart` docstring
documents the two-pass streaming mechanism (ADR-0025), not the rule content, and
the statuses plus clarify-not-guess behavior are already the documented contract
(invariant 1, entity-clarification / entity-allowlist BDD), so no schema, spec,
ADR, or BDD change was needed. Verified live against Ollama (the maren/AC prompt
now returns `clarification_needed` with an appropriate question); full suite
`451 passed, 3 failed` (same pre-existing codegen-sandbox flake; no codegen file
touched), model-provider planning eval `PASS`, BDD-evidence review `OK`.

## Next recommended packet

**Semantic alias live wiring — learned entity knowledge (now #1).**

Root cause: the kitchen ecobee climate entity controls whole-house AC but is
named for its location. The model has no way to know "AC running" →
`climate.kitchen_ecobee`. This pattern is universal (HVAC entities named for
sensor location, not function) and aliases are the right fix.

**What's already in place (do not re-implement):**
- `SemanticAlias` + `SemanticMemoryStore` schemas fully designed (four meaning
  types: `entity`, `state_interval`, `threshold_interval`, `aggregate`).
- `src/Isolinear/fake_slice.py` has alias matching, invalidation, and
  `saved_semantic_aliases` proposal logic — port this to the live path, don't
  rewrite it.
- Evals: `semantic_memory_store_envelope.py`, `semantic_alias_invalidation.py`,
  `threshold_interval_use_once.py`, `threshold_interval_alias_reuse.py`,
  `threshold_interval_use_and_remember.py`.
- ADR-0009 (accepted): HA integration owns the memory store.
- ADR-0010 (accepted): semantic memory store envelope.

**Tranche 1 — load/match/inject (the foundational path):**
1. Persist `SemanticMemoryStore` to HA storage (`hass.data` / `Store`) keyed by
   `config_entry_id`. Load at integration setup; save on write.
2. At entity-resolution time, match enabled aliases against the user's prompt
   tokens (same scoring logic as `fake_slice.py`). Inject matching alias
   entity IDs into the approved entity catalog so the specificity fast-path
   and model-driven D2 selector both see them.
3. Mark alias-resolved entities distinctly in the catalog entry so the planner
   can use them (and the validation gate enforces allowlist membership still
   applies — aliases cannot bypass the allowlist boundary, invariant #1).
4. New spec + BDD for Tranche 1 before any code (ADR-0009 + ADR-0010 are
   already accepted; check if a new ADR is needed for the live wiring contract).

**Tranche 2 — propose/confirm/save (the learning path):**
5. Extend the live planner result schema with optional `saved_semantic_aliases`
   (already in `fake_slice.py` result shape; wire it into the planner output
   schema and validate).
6. After a successful render, if the model proposed aliases, surface a
   "Remember this?" confirmation in the card (new card UI state).
7. On user confirm: write alias to storage. On reject: no-op.
8. Spec + BDD for Tranche 2 before implementing the card UI.

**For the AC case specifically**, the alias the system should eventually learn:
```json
{
  "alias_id": "whole_house_ac",
  "natural_names": ["ac", "air conditioning", "central air", "air conditioner"],
  "meaning": {
    "type": "state_interval",
    "entity_id": "climate.kitchen_ecobee",
    "attribute": "hvac_action",
    "active_values": ["cooling"]
  }
}
```
In the meantime, manually seeding this alias into the store (by editing the
storage JSON) is a valid workaround while Tranche 2 is pending.

**Session start for this packet:** read ADR-0009, ADR-0010,
`src/Isolinear/fake_slice.py` (alias matching section), `semantic-alias.schema.json`,
`semantic-memory-store.schema.json`, and the existing evals before writing any
code or specs.

---

**Live HACS reasoning-streaming retest — RESOLVED in `0.1.35`.** The blocker
behind the `0.1.34` retest item (reasoning text not appearing for
thinking-capable models) was the `think`/`format` mutual-exclusivity bug, now
fixed: with `format` dropped on the streaming path, a thinking-capable Ollama
model emits reasoning into the chart slot during planning. A live HACS `0.1.35`
retest is still worth a quick confirmation in the field (reasoning text appears
in the chart slot during planning; "last 4 hours" resolves to a 4-hour window,
not 24h), but it is no longer a blocking unknown.

**ADR-0023 capability envelope (now #2)** — histogram + aggregate_bar first
tranche; spec + BDD drafted, ADR accepted — implementation-ready.

**Night mode (now #3)** — dark theme for chart PNG + card UI, auto-following
HA theme. Needs spec + likely an ADR (schema-touching: theme plumbed card →
render request).

Confirm the live retest against real Home Assistant + Ollama:

0. A real `binary_sensor` prompt that previously failed with
   `model_provider_referenced_unapproved_entity` now renders (the `0.1.28`
   structural gate — this was the live `0.1.27` false positive). If it still
   fails at planning, capture the DEBUG `Isolinear -> / <- Ollama plan_chart`
   log lines (enable the `custom_components.isolinear.model_provider` logger at
   DEBUG).
1. A real `binary_sensor` prompt (e.g. "kitchen door last 24 hours") renders an
   on/off **timeline** PNG instead of the old
   `model_provider_chart_spec_hidden_entity` failure (0.1.25).
2. A mixed prompt ("show me the temperature and when the AC was running")
   renders a numeric **line with the AC-on regions shaded behind it** (0.1.26).
3. A numeric prompt still renders a line chart; a long-window `state_class`
   sensor still renders daily statistics with a min/max band.
4. Capture the WARNING log line shape for any `mixed_chart_composition_unsupported`
   or disambiguated entity failures.

Then **Night mode** (item (h)) is the next net-new feature (spec + likely ADR).

Then run the served-artifact prompt path against real Home Assistant sensor
history and the configured Ollama planner. The key success signal is a rendered
chart PNG, not `RENDERER_DEPENDENCY_UNAVAILABLE`. The key log line shape is:
`Isolinear WebSocket command accepted/rejected: message_id=... type=...
requested_config_entry_id=... resolved_config_entry_id=... job_id=...
code=... result_code=... snapshot_status=... progress_stage=...
failure_code=... exception_type=...`.

If the card still reports `RENDERER_DEPENDENCY_UNAVAILABLE` after `0.1.19` is
installed, the pip install of matplotlib failed — check HA logs for the exact
pip error before changing the manifest again. Do not restore a strict
`matplotlib==X.Y.Z` pin. If a model-provider failure arrives, it should surface
as `failure.stage: model_provider_planning`. If the logs show
`code=isolinear_websocket_command_exception`, inspect that line's fields before
changing card behavior.

Preserve the known codegen sandbox matplotlib subprocess flake as a historical
caveat; the first-real-slice closeout full Python suite passed cleanly
(`303 passed`) before this manual verification follow-up.

## Known unresolved design details

- Overlay follow-ups beyond 0.1.26: overlay for ≥2 numeric primaries
  (multi-axis), overlay on the `timeline` family, and categorical (non-binary)
  overlays. A dedicated `timeline_history_unavailable` code for beyond-retention
  binary windows (0.1.25/0.1.26 reuse `no_long_term_statistics`).
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
