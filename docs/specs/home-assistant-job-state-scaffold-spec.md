---
status: draft
date: 2026-06-08
depends-on-adrs:
  - 0001
  - 0005
  - 0006
  - 0008
  - 0011
  - 0012
---

# Home Assistant Integration: Job State Scaffold Anchor

## Status

Draft. Defines the first production Home Assistant integration-owned job state
surface behind the registered card-facing WebSocket commands per ADR-0001,
ADR-0005, ADR-0006, ADR-0008, ADR-0011, and ADR-0012.

## Related Docs

- [bdd/integration/home-assistant-job-state-scaffold-bdd.md](../../bdd/integration/home-assistant-job-state-scaffold-bdd.md) - observable behavior
- [docs/specs/integration-api-transport-auth-spec.md](integration-api-transport-auth-spec.md) - accepted command contract
- [docs/specs/home-assistant-websocket-command-registration-spec.md](home-assistant-websocket-command-registration-spec.md) - registered command boundary
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The integration now has a real Home Assistant package, config flow/options
surface, dashboard resource registration, and registered WebSocket command
handlers. Those handlers still return one-shot scaffold snapshots. The next
production anchor needs the smallest inspectable job state surface so the card
can start a job, retrieve the latest snapshot, retry it, answer a clarification
for it, and subscribe to future snapshots without introducing real
orchestration.

This packet must remain non-orchestrating. It may create and update
config-entry-scoped in-memory `IntegrationJobSnapshot` records, but it must not
fetch Home Assistant history, call the model provider, call the worker, persist
semantic memory, generate worker tokens, write chart artifacts, or mutate Home
Assistant state/services.

## Behavior Contract

The integration must create one in-memory job state store per Isolinear config
entry under `hass.data["isolinear"][entry_id]`.

The store must:

- Be initialized from `async_setup_entry`.
- Be removed when `async_unload_entry` removes the config-entry data.
- Generate deterministic job IDs for a fresh runtime using the config-entry ID
  and a monotonic counter.
- Generate deterministic snapshot IDs for each job using a per-job snapshot
  counter.
- Store the latest schema-valid `IntegrationJobSnapshot` per job.
- Validate every scaffold `IntegrationJobSnapshot` against JSON Schema before
  storing it as job state.
- Keep all lookups scoped to the command's `config_entry_id`.
- Keep config-entry stores isolated from each other.
- Record a minimal subscription callback/event shape for
  `isolinear/v1/job/subscribe` without starting a streaming worker or progress
  task.

Registered command handlers must preserve the existing deterministic command
validation gate and config-entry scope gate, then use the job state store:

- `isolinear/v1/job/start` creates a new job and returns its first
  `planning` snapshot.
- `isolinear/v1/job/snapshot` returns the latest snapshot for the requested
  job when that job belongs to the targeted config entry.
- `isolinear/v1/job/retry` appends a new `planning` scaffold snapshot for an
  existing job and returns it.
- `isolinear/v1/clarification/answer` appends a new `planning` scaffold
  snapshot for an existing job and records that the answer was accepted by the
  state surface only.
- `isolinear/v1/job/subscribe` records a subscription event shape for an
  existing job and returns the latest schema-valid snapshot immediately.

Unknown jobs, jobs from a different config entry, missing config entries,
wrong-version commands, malformed payloads, leaky payloads, and mutating
payloads must fail closed with structured WebSocket errors before orchestration.

Allowed side effects for this packet are limited to:

- In-memory config-entry-scoped job state creation/update/removal.
- In-memory config-entry-scoped subscription bookkeeping.
- Returning or erroring a WebSocket response for the current command.
- The already-anchored global WebSocket command registration.

The job state boundary must report that no worker, model-provider, Home
Assistant history, semantic-memory persistence, Home Assistant service/device/
state mutation, token-generation, chart artifact write, or real job
orchestration occurred.

## Anchor Artifact

The anchor artifact is the inspectable
`custom_components/isolinear/job_state.py` module plus
`src/Isolinear/job_state_scaffold_anchor.py`, which verifies deterministic job
and snapshot IDs, schema-valid snapshots, per-config-entry isolation,
subscription callback shape, unknown-job errors, unload cleanup, and side
effect boundaries against fake Home Assistant objects.

## Implementation Order

1. Create this spec and its paired BDD/evidence scaffold.
2. Add failing unit tests for start/snapshot/retry/clarification/subscribe
   behavior, per-config-entry isolation, unknown-job rejection, unload cleanup,
   and side-effect boundaries.
3. Add the smallest job state store and wire registered WebSocket callbacks to
   it after command validation and config-entry scope validation.
4. Add the Python verifier anchor and focused executable eval.
5. Verify the real files on disk.

## Proof Requirements

1. Unit tests in `tests/test_job_state_scaffold_anchor.py` are green.
2. Existing WebSocket registration and integration scaffold tests remain green.
3. `evals/home_assistant_job_state_scaffold.py` emits raw `CASE` evidence for
   the BDD scenarios.
4. Evidence confirms `job/start` creates deterministic schema-valid job and
   snapshot IDs in the targeted config-entry store.
5. Evidence confirms `job/snapshot`, `job/retry`, and
   `clarification/answer` operate only on existing jobs in the targeted
   config-entry store.
6. Evidence confirms `job/subscribe` records the subscription callback/event
   shape and immediately returns the latest schema-valid snapshot.
7. Evidence confirms unknown jobs and cross-config-entry job lookups fail
   closed before orchestration.
8. Evidence confirms unload cleanup removes the config-entry job store.
9. Evidence confirms malformed scaffold snapshots are rejected before storage.
10. Evidence confirms no worker, model provider, Home Assistant history,
   semantic-memory persistence, Home Assistant service/device/state mutation,
   token-generation, chart artifact write, or real job orchestration occurs.
11. Real artifacts are verified on disk: production job state module,
    WebSocket callback wiring, integration setup/unload wiring, BDD, eval
    outline, tests, eval, and evidence.

## Non-Goals

- Home Assistant history access or entity catalog construction.
- Model-provider calls.
- Worker HTTP calls, worker token generation, rotation, storage, or repair UI.
- Semantic-memory persistence or migration.
- Chart artifact storage or dashboard resource registration changes.
- Production job orchestration, progress streaming, retry semantics, or
  artifact lifecycle beyond schema-valid scaffold snapshots.
- Creating, editing, or deleting Home Assistant dashboards, devices, services,
  automations, scenes, helpers, or state.

## References

- [docs/decisions/0001-home-assistant-integration-plus-worker.md](../decisions/0001-home-assistant-integration-plus-worker.md)
- [docs/decisions/0005-schema-driven-contracts-and-history-normalization.md](../decisions/0005-schema-driven-contracts-and-history-normalization.md)
- [docs/decisions/0006-validation-and-repair-loop.md](../decisions/0006-validation-and-repair-loop.md)
- [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../decisions/0008-read-only-mvp-and-sandbox-security.md)
- [docs/decisions/0011-dashboard-card-implementation-technology.md](../decisions/0011-dashboard-card-implementation-technology.md)
- [docs/decisions/0012-worker-transport-and-authentication.md](../decisions/0012-worker-transport-and-authentication.md)
- [docs/specs/integration-api-transport-auth-spec.md](integration-api-transport-auth-spec.md)
- [docs/specs/home-assistant-websocket-command-registration-spec.md](home-assistant-websocket-command-registration-spec.md)
- [docs/schemas/integration-ws-command.schema.json](../schemas/integration-ws-command.schema.json)
- [docs/schemas/integration-job-snapshot.schema.json](../schemas/integration-job-snapshot.schema.json)
