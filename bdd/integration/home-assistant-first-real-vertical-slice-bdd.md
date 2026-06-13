# Home Assistant Integration: First Real Vertical Slice - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-first-real-vertical-slice.md](../../docs/specs/home-assistant-first-real-vertical-slice.md).

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

### Scenario C - repeated snapshot requests reuse the artifact

**Given** a real-slice job has already completed
**When** the dashboard card asks for the same job snapshot again
**Then** the integration returns the same complete snapshot and does not call
the planner or renderer again.

## Evidence

The implementing slice produces an evidence file at
`bdd/integration/home-assistant-first-real-vertical-slice-evidence.md`
containing raw outputs for each scenario.
