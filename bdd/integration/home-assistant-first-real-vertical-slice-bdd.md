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

## Evidence

The implementing slice produces an evidence file at
`bdd/integration/home-assistant-first-real-vertical-slice-evidence.md`
containing raw outputs for each scenario.
