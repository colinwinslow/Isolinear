# Entity selection in the pollable planning phase — BDD

## Status

Draft. Paired with
[docs/specs/entity-selection-in-pollable-planning-phase.md](../../docs/specs/entity-selection-in-pollable-planning-phase.md).

ADR-0026: model-driven entity selection (D1 + D2 + the D3 decision) moves out of
the blocking `job/start` handler into the pollable planning phase, behind the
existing single-flight planning lock, so `job/start` returns `planning`
immediately and the model phase streams reasoning across selection → planning
(realizing ADR-0025 D7). Resolution semantics are unchanged — relocation only.

Evidence file: `bdd/integration/entity-selection-in-pollable-planning-phase-evidence.md`

Related artifacts:

- ADR: `docs/decisions/0026-entity-selection-in-pollable-planning-phase.md`
- Spec: `docs/specs/entity-selection-in-pollable-planning-phase.md`
- Predecessor: `docs/decisions/0025-live-planner-reasoning-feedback.md` (D7),
  `docs/decisions/0024-model-driven-entity-selection.md`

## Why this BDD exists

It pins the observable contract change: `job/start` (and `job/retry`) return
`planning` with no model call, terminal states become first-poll outcomes, and
the model phase is concurrently pollable so entity-selection reasoning is finally
visible — without changing which entity gets chosen.

## Scenarios

### Scenario A — happy path: job/start returns planning, never calls the model

**Given** an approved catalog with at least one resolvable entity
And a model provider is configured
**When** the user submits a prompt via `isolinear/v1/job/start`
**Then** the response is a schema-valid snapshot with `status: planning`
And `progress.stage` is the pre-model phase `"Resolving entities…"`
And the fake provider records **zero** `select_entity` / `plan_chart` calls at
  `job/start` time
And the response carries no `entities`, `clarification`, `chart`, or `failure`.

### Scenario B — entity-selection clarification becomes a first-poll outcome

**Given** two thermostats that tie on the shared token "thermostat"
And a model provider configured to abstain on `select_entity`
**When** the user submits "show thermostat history" via `job/start`
**Then** `job/start` returns `status: planning` (no clarification on the start
  response)
And the first `isolinear/v1/job/snapshot` poll runs D1 → D2 (model abstains) → D3
And that poll returns `status: clarification_needed` with both thermostats as
  options
And the entity-selection logic invoked is byte-for-byte the pre-ADR-0026
  pipeline (same candidates, same `source` codes).

### Scenario C — D2 expansion resolves on poll with visible reasoning (the AC prompt)

**Given** an approved catalog containing `sensor.kitchen_ecobee_temperature` and
  `climate.kitchen_ecobee`
And a model provider whose `select_entity` think pass emits reasoning deltas
**When** the user submits "show kitchen temp and when the AC was running"
**Then** `job/start` returns `status: planning` immediately
And while the first poll holds the planning lock, concurrent `job/snapshot` polls
  return an in-progress `planning` snapshot whose `progress.stage` is
  `"Selecting entities…"` and whose `progress.reasoning` carries the sanitized
  live thinking tail
And the resolving poll returns the composed result with both the temperature
  sensor and `climate.kitchen_ecobee` (D2 expansion), no clarification.

### Scenario D — single-flight: the model is called exactly once

**Given** a prompt that triggers a model `select_entity` call taking longer than
  one poll interval
**When** several `job/snapshot` polls arrive during resolution
**Then** exactly one poll acquires the planning lock and performs resolution
And every other concurrent poll returns the in-progress `planning` snapshot via
  `apply_live_reasoning` without launching a second resolution
And the cached `job["entity_selection"]` is reused by later polls
And the fake provider records exactly **one** `select_entity` invocation.

### Scenario E — pre-model structural rejection stays synchronous on job/start

**Given** a config entry whose approved catalog is empty
**When** the user submits any prompt via `job/start`
**Then** `job/start` returns the existing structured failure
  (`no_approved_entities_available`) **synchronously**, not deferred to a poll
And no model provider call is made
And likewise an unknown config entry, wrong version, or leaky/mutating payload
  still fails closed at the `job/start` boundary.

### Scenario F — retry continuation moves identically

**Given** a retryable failed job with a configured model provider
**When** the user submits `isolinear/v1/job/retry`
**Then** `job/retry` returns `status: planning` (no terminal state on the retry
  response)
And the first subsequent `job/snapshot` poll re-resolves entity selection under
  the planning lock and proceeds to planning/render exactly as a fresh start
  would.

### Scenario G — non-reasoning model still resolves (graceful degradation)

**Given** a model provider that emits no thinking deltas
**When** a prompt requiring D2 resolves on the first poll
**Then** the poll returns the resolved/planned result with no `progress.reasoning`
  ever populated
And the absence of reasoning never blocks or fails the resolution (D6 fallback,
  inherited from ADR-0025).

### Scenario H — invariants preserved across the move

**Given** any prompt routed through the relocated pipeline
**When** entity selection resolves under the planning lock
**Then** only allowlisted, `visible_to_agent: true` entities are ever selected
  (invariant #1)
And no Home Assistant state is mutated (invariant #2)
And every returned snapshot validates against
  `integration-job-snapshot.schema.json` (invariant #4)
And the D1-before-D2 ordering and D2 expansion gating are identical to ADR-0024.

## Evidence

The implementing slice produces an evidence file at
`bdd/integration/entity-selection-in-pollable-planning-phase-evidence.md`
containing raw outputs (not summaries) for each scenario: the `job/start`
`planning` snapshot JSON with the zero-model-call assertion, the first-poll
`clarification_needed` / composed-selection JSON, the concurrent-poll in-progress
snapshot showing the `"Selecting entities…"` reasoning tail, the single-flight
call-count, the synchronous-rejection responses, and the retry-path poll outputs.
