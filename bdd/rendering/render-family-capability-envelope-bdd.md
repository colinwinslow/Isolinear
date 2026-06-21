# Render family capability envelope — BDD

## Status

Draft. Paired with
[docs/specs/render-family-capability-envelope.md](../../docs/specs/render-family-capability-envelope.md).

## Why this BDD exists

Pins down the user-visible behavior of ADR-0023: the same approved entity can be
charted as different shapes chosen from the user's words (line, histogram,
per-period bar), while the integration keeps deciding what the data can honestly
show. It also pins the fail-soft rule (sparse data renders thin, not nothing)
and proves the safety properties are unchanged.

Evidence file: `bdd/rendering/render-family-capability-envelope-evidence.md`

Related artifacts:

- Spec: `docs/specs/render-family-capability-envelope.md`
- ADR: `docs/decisions/0023-model-proposed-render-family-within-capability-envelope.md`
- Code: `job_orchestration.py` (`_resolve_render_envelope`,
  `validate_model_provider_chart_family`), `model_provider.py`
  (`load_planner_result_schema`), `in_process_renderer.py`
  (`_render_histogram_png`, `_render_aggregate_bar_png`)

## Scenarios

### Scenario A — happy path / anchor: "distribution" intent renders a histogram

**Given** one approved numeric entity (`sensor.upstairs_temperature`) with
normalized history in the resolved window
**And** the integration computes the envelope `[time_series, histogram, aggregate_bar]`
**When** the user asks "show me the distribution of upstairs temperature this week"
**Then** the planner's `chart_type` enum equals the envelope, the model chooses
`histogram`, and a served histogram PNG is written
**And** the card-facing snapshot is `complete` with the served artifact URL
**And** the model's `reasoning_summary` records why a histogram was chosen

### Scenario B — same entity, different intent: "average per day" renders an aggregate bar

**Given** the same approved numeric entity and a multi-day window
**When** the user asks "what's the average upstairs temperature per day"
**Then** the model chooses `aggregate_bar`, and a served bar-per-day PNG is
written with one bar per day bucket
**And** deterministic validation passes before the write

### Scenario C — back-compat: "over time" still renders a time-series line

**Given** the same approved numeric entity
**When** the user asks "show me upstairs temperature over time"
**Then** the model chooses `time_series` and a numeric line PNG is written,
identical to today's behavior

### Scenario D — single-member envelope: a binary entity still routes to timeline

**Given** one approved binary entity (`binary_sensor.kitchen_door`)
**When** the user asks "when was the kitchen door open today"
**Then** the envelope is exactly `[timeline]`, the `chart_type` enum has one
member, the model has no family discretion, and a timeline step PNG is written
**And** behavior is byte-for-byte the ADR-0022 path

### Scenario E — out-of-envelope choice fails closed

**Given** one approved binary entity (envelope `[timeline]`)
**And** a model that returns `chart_type: histogram` (outside the envelope)
**When** the snapshot is requested
**Then** the deterministic gate returns
`model_provider_chart_family_out_of_envelope` with the chosen and allowed
families
**And** a card-facing failed snapshot is recorded at
`failure.stage: model_provider_planning`
**And** no PNG, artifact, render plan, or provider plan is stored

### Scenario F — fail-soft: a histogram over a sparse window renders thin, not an error

**Given** one approved numeric entity whose resolved window contains only a few
readings
**When** the user asks for a distribution
**Then** a valid histogram PNG is written (sparse but legible)
**And** the result is NOT `unsupported_chart_spec` and the `histogram` family is
NOT withheld from the envelope

### Scenario G — fail-closed: no usable data is an honest failure, not an empty chart

**Given** one approved numeric entity with zero numeric points in the resolved
window (or a beyond-retention window with no statistics)
**When** the user asks for any numeric family
**Then** a card-facing failed snapshot is recorded (`no_long_term_statistics` /
existing no-data code)
**And** no silent empty PNG is produced

### Scenario H — entity enforcement is unchanged regardless of family

**Given** any computed envelope
**And** provider output whose `series`/`overlays` source or
`memory_proposals[].entity_id` references an off-allowlist entity
**When** the output is validated
**Then** it fails closed with `model_provider_referenced_unapproved_entity`
**And** an entity-shaped token in a free-text field (`chart_id`, `title`,
`notes`) is NOT treated as a reference (the 0.1.27 structural-gate behavior)

## Evidence

The implementing slice produces an evidence file at
`bdd/rendering/render-family-capability-envelope-evidence.md` containing raw
outputs (not summaries) for each scenario: the computed envelope per shape, the
planner `chart_type` enum sent, the model's chosen family + `reasoning_summary`,
the render status, PNG MIME type and byte size, render metadata (plotted
series/buckets), the deterministic validation checks, and — for Scenario F — the
sparse histogram PNG eyes-on note at the ~380px phone downscale.
