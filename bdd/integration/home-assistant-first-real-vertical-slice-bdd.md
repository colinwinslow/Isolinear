# Home Assistant Integration: First Real Vertical Slice - BDD

## Status

Accepted. Paired with
[docs/specs/home-assistant-first-real-vertical-slice.md](../../docs/specs/home-assistant-first-real-vertical-slice.md)
and backed by focused pytest evidence plus manual Home Assistant/Ollama
verification.

## Why this BDD exists

This BDD pins down the first visible real-product behavior after the reality
pivot: a prompt over the existing card command boundary returns a PNG chart
from approved history and a provider-produced `ChartSpec`.

## Scenarios

### Scenario A - happy path: allowed prompt returns a PNG chart

**Given** a configured Isolinear entry with one allowlisted numeric entity, an
Ollama-compatible planner, and approved history for that entity
**When** the dashboard card sends `isolinear/v1/job/start` and then
`isolinear/v1/job/snapshot`
**Then** the returned complete snapshot contains a chart image URL that decodes
to PNG bytes, and the stored provider plan, render plan, artifact metadata, and
history series validate.

### Scenario B - hidden provider entity fails closed

**Given** the same configured entry and history
**When** the planner result references a non-allowlisted entity anywhere in its
output
**Then** the snapshot request fails before in-process rendering, artifact
metadata storage, or complete snapshot storage.

### Scenario C - invalid provider chart output returns a failed snapshot

**Given** the same configured entry and history
**When** the planner returns a chart spec that fails schema validation
**Then** the snapshot request returns a card-facing failed job snapshot with the
model-provider failure code
**And** the integration does not render a chart or write an artifact file.

### Scenario D - repeated snapshot requests reuse the artifact

**Given** a real-slice job has already completed
**When** the dashboard card asks for the same job snapshot again
**Then** the integration returns the same complete snapshot and does not call
the planner or renderer again.

### Scenario E - trusted renderer failure returns a failed snapshot

**Given** the planner produced a valid allowlisted chart spec
**When** the trusted in-process renderer fails before returning an accepted PNG
**Then** the snapshot request returns a card-facing failed job snapshot with
`failure.stage: chart_rendering`
**And** the integration does not write a PNG file or artifact metadata.

### Scenario F - the model resolves the time window (ADR-0020)

**Given** a configured entry whose planner emits an absolute
`chart_spec.time_range {start, end}` for a fuzzy prompt, with `now` and
`time_zone` supplied in the planner request
**When** the dashboard card runs `job/start` then `job/snapshot`
**Then** history is fetched after planning for the resolved window (clamped to
end <= now and span <= 366 days), and a window that is missing, inverted, or
otherwise unclampable falls back to a fixed last-24h window rather than a
keyword guess.

### Scenario G - seasonal window uses long-term statistics with a band (ADR-0021)

**Given** a configured entry, a ~90-day absolute window from the planner, and
long-term statistics available for the entity
**When** the snapshot path retrieves history
**Then** the series is sourced from `long_term_statistics` at `daily`
resolution, each point carries `value`/`value_min`/`value_max`, and the rendered
PNG shades a min/max band behind the mean line.

### Scenario H - beyond retention without statistics fails closed

**Given** a configured entry and a window older than recorder retention for an
entity that has no long-term statistics (no `state_class`)
**When** the snapshot path retrieves history
**Then** it returns a card-facing failed snapshot with
`failure.stage: approved_history_retrieval` and `failure.code:
no_long_term_statistics`, and no PNG file is written.

### Scenario I - binary entity renders an on/off timeline (ADR-0022)

**Given** a configured entry whose single resolved entity is a `binary_sensor`
(e.g. `binary_sensor.kitchen_door`) with raw on/off recorder history in the
resolved window
**When** the dashboard card runs `job/start` then `job/snapshot`
**Then** the integration classifies the entity as `binary_state` *before*
planning, sends the planner the `timeline` schema, and renders a `timeline`
`step` PNG whose decoded signature is valid, with filled "on" regions and gaps
for "off", and reports zero codegen attempts
**And** the run never produces a `model_provider_chart_spec_hidden_entity` (or
the new substitution) failure for the approved, disclosed door sensor.

### Scenario J - deterministic render-family routing (ADR-0022)

**Given** the integration has resolved the entities for a job
**When** it classifies them by `_series_kind`
**Then** an all-numeric set routes to `time_series`/`line`, an all-categorical
set routes to `timeline`/`step`, and a mixed numeric + binary set fails closed
with `mixed_chart_composition_unsupported` before the planner is called
(overlay composition is deferred to the 0.1.26 packet).

### Scenario K - beyond-retention timeline fails closed (ADR-0022)

**Given** a `binary_sensor` resolved entity and a window older than recorder
retention
**When** the snapshot path retrieves history for the timeline
**Then** it fails closed (no raw states and no long-term statistics for a
non-`state_class` entity) with a card-facing failed snapshot, and no PNG is
written.

### Scenario L - honest failure-code disambiguation (ADR-0022)

**Given** the same configured entry and history
**When** the planner result references an entity that is **not in the approved
catalog at all**
**Then** the snapshot fails before rendering with
`model_provider_referenced_unapproved_entity`
**And when** instead it references an entity that **is** approved but was **not
disclosed for this job**, the snapshot fails before rendering with
`model_provider_substituted_entity`.

### Scenario M - numeric line with binary overlay band (0.1.26, ADR-0022 D4/D5)

**Given** a prompt that resolves exactly one numeric entity and one or more
binary entities (e.g. "show me the temperature and when the AC was running")
**When** the snapshot path composes the chart deterministically
**Then** the integration routes to `time_series_overlay`, discloses only the
numeric primary to the planner, injects a `shaded_intervals` overlay for each
binary entity (`_compose_binary_overlays`), and renders a single PNG with the
numeric series as the primary line and the binary entity shaded as an "on"-region
band behind it — with the overlay entity allowlist-validated.

### Scenario N - fuzzy mixed prompt resolves to the overlay composition (0.1.26)

**Given** a fuzzy prompt matching one numeric series plus one binary entity by
catalog tokens
**When** `select_prompt_entity_ids` resolves it
**Then** it returns both entities (`source: numeric_with_overlay`) rather than
asking the user to pick one, while a multi-match that is not exactly one numeric
+ binary still clarifies.

### Scenario O - two numeric series + a binary still fails closed (0.1.26)

**Given** a prompt resolving two numeric entities plus a binary entity
**When** the snapshot path classifies the set
**Then** it fails closed with `mixed_chart_composition_unsupported` before the
planner is called, because no primary line can be chosen deterministically.

## Evidence

The implementing slice produces an evidence file at
`bdd/integration/home-assistant-first-real-vertical-slice-evidence.md`
containing raw outputs for each scenario. Scenarios I-L are active in 0.1.25;
Scenarios M-O are active in 0.1.26.
