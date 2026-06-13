# Home Assistant Dashboard Card: Long-Running Prompt Smoke - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-dashboard-card-long-running-smoke.md](../../docs/specs/home-assistant-dashboard-card-long-running-smoke.md).

## Why this BDD exists

This BDD pins down the user-visible prompt workflow after the first real slice:
the card must not get stuck in an active state after `job/start`; it must keep
refreshing through integration-owned WebSocket snapshots until the chart result
is visible.

## Scenarios

### Scenario A - happy path: delayed card prompt reaches chart result

**Given** the dashboard card is mounted with a Home Assistant connection that
returns a delayed `planning` snapshot from `isolinear/v1/job/start`
**When** the user submits `Show sensor.upstairs_temperature for the last 24 hours`
**Then** the card should disable duplicate submit while the job is active
**And** the card should automatically send `isolinear/v1/job/snapshot` for the
active job
**And** the final card state should be `complete` with chart-first layout,
validation status `pass`, and a PNG data URL image.

### Scenario B - integration path: registered commands return a PNG snapshot

**Given** the first-real-slice route is enabled for an entry allowlisting only
`sensor.upstairs_temperature`
**When** the same versioned `job/start` and `job/snapshot` command shapes are
sent through the registered WebSocket command helper
**Then** the snapshot should complete with a PNG data URL
**And** the planner should be called once with only the allowlisted entity
**And** no worker dispatch should occur.

### Scenario C - boundary: browser remains a thin client

**Given** the card completes the long-running prompt smoke
**When** the observed card commands and result rendering are inspected
**Then** the browser-side workflow should use only integration-owned WebSocket
commands
**And** the card should not call the worker, model provider, Home Assistant
history APIs, mutation services, semantic-memory storage, local storage, or
token-bearing endpoints directly.

## Evidence

The implementing slice produces an evidence file at
`bdd/dashboard-card/home-assistant-dashboard-card-long-running-smoke-evidence.md`
containing raw outputs for each scenario.
