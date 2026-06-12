---
status: draft
date: 2026-06-11
depends-on-adrs:
  - 0001
  - 0005
  - 0008
  - 0012
  - 0014
  - 0015
---

# Home Assistant Integration: Durable Worker Health Polling Scaffold Anchor

## Status

Draft. Defines the first production Home Assistant integration-owned durable
worker health polling scaffold per ADR-0001, ADR-0005, ADR-0008, ADR-0012,
ADR-0014, and accepted ADR-0015.

## Related Docs

- [bdd/integration/home-assistant-durable-worker-health-polling-scaffold-bdd.md](../../bdd/integration/home-assistant-durable-worker-health-polling-scaffold-bdd.md) - observable behavior
- [docs/specs/home-assistant-worker-health-readiness-endpoint-scaffold-spec.md](home-assistant-worker-health-readiness-endpoint-scaffold-spec.md) - explicit `GET /v1/health` probe
- [docs/specs/home-assistant-worker-token-provisioning-readiness-scaffold-spec.md](home-assistant-worker-token-provisioning-readiness-scaffold-spec.md) - worker readiness gate
- [docs/specs/home-assistant-worker-token-rotation-repair-scaffold-spec.md](home-assistant-worker-token-rotation-repair-scaffold-spec.md) - explicit token repair boundary
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The integration can explicitly provision an in-memory integration-owned worker
token, configure a same-entry worker client, and run an explicit redacted
worker health probe. It does not yet have restart-safe diagnostic health state
or scheduler metadata for setup, reload, and unload boundaries.

This packet adds the smallest durable polling scaffold behind ADR-0015. It
records schema-valid, redacted, config-entry-scoped latest polling state in an
integration-owned storage-helper surface, enqueues only post-setup polling
bookkeeping during setup, and exposes an explicit scheduled-poll step for tests
and future Home Assistant scheduling.

## Behavior Contract

The durable worker health polling boundary must:

- Promote ADR-0015 to accepted before implementation.
- Define an `IntegrationWorkerHealthPollingState` JSON Schema for the latest
  redacted polling state and scheduler metadata.
- Initialize one integration-owned storage-helper surface for worker health
  polling state. In production Home Assistant, this wraps the Home Assistant
  versioned storage helper so the latest state is restart-safe; verifier and
  fake-HA tests may use the same JSON-safe surface with in-memory storage.
- On config-entry setup after storage load, resume valid enabled persisted
  scheduler state instead of resetting failure counts, backoff, or
  `next_poll_not_before`; setup still must not call the worker.
- Persisted scheduler state is valid to resume only when its stored
  `next_poll_not_before` matches the 300-second ready cadence or one of the
  bounded failure backoff windows, and is not beyond the bounded resume window.
- During config-entry setup, write only polling state and scheduler
  bookkeeping; setup must not call the worker health endpoint.
- Enable post-setup polling only when the entry has a configured worker
  endpoint, ready worker readiness metadata, a valid integration-owned worker
  token, and a same-entry worker health client.
- Record `disabled` or `blocked` durable state for entries that fail
  preconditions, without calling the worker.
- Revalidate preconditions immediately before every scheduled poll.
- Run at most one poll at a time for a config entry. Normal poll execution
  must write `poll_in_flight: true` before the worker health call and clear it
  in the final stored result.
- Reuse the ADR-0014 `GET /v1/health` path for eligible poll attempts.
- Store only a redacted health summary in durable polling state: status,
  sanitized code/message, failure family, capability summary, last poll time,
  next poll not-before time, stale/disabled flags, and scheduler metadata.
- Scheduled polling must not write or overwrite the explicit ADR-0014
  `IntegrationWorkerHealth` probe envelope or setup marker.
- Use a 300 second ready cadence for `ready` results.
- Use bounded failure backoff of 30, 60, 120, 300, and then 900 seconds for
  `not_ready` and `unavailable` results.
- Reset the consecutive failure count after a `ready` result.
- Remove the config entry's durable polling state on unload.
- Ignore late in-flight poll completions after an unload/reload of the same
  config entry id so stale health/backoff metadata from the old entry cannot
  attach to the reloaded entry.
- Clear stale in-flight state when the same loaded config entry's worker
  client or token changes during a poll, then allow the current context to
  poll again.
- Avoid exposing worker endpoint URLs, bearer tokens, request bodies,
  response internals, scheduler internals, repair recommendations, or durable
  polling metadata to dashboard-card WebSocket payloads.

Allowed side effects for this packet are limited to:

- Reading the targeted config entry, existing worker readiness metadata,
  in-memory worker token, and same-entry worker health client.
- Writing schema-valid durable polling state through the integration-owned
  storage-helper surface.
- Writing scheduler bookkeeping for post-setup and next-poll timing.
- One explicit worker health endpoint call for each eligible scheduled poll.
- Removing the targeted entry's durable polling state on unload.

The packet remains bounded: it must not mutate Home Assistant
services/devices/state/configuration, read Home Assistant history, persist
semantic memory, generate tokens, rotate tokens, repair tokens, call worker
render, call model providers, render charts, write chart artifacts, create
durable retry queues, use Recorder, write config-entry options, introduce an
external database or queue, schedule automatic repair, or expose polling state
to the dashboard card.

## Anchor Artifact

The anchor artifact is the inspectable durable polling behavior in
`custom_components/isolinear/worker_health_polling.py` and
`src/Isolinear/worker_health_polling_anchor.py`, which verifies post-setup
scheduler bookkeeping without worker calls, eligible scheduled polling,
bounded ready cadence and failure backoff, blocked preconditions, single-flight
guarding, restart-safe setup resume, unload cleanup, schema validity, redaction, card-safety,
config-entry isolation, and bounded side effects.

## Implementation Order

1. Promote ADR-0015, then create this spec, paired BDD/evidence scaffold, eval
   outline, and polling-state schema.
2. Add failing unit tests and a Python verifier anchor for setup enqueue,
   scheduled ready poll, failure backoff, blocked preconditions, single-flight
   guard, setup resume, unload cleanup, redaction, card-safety, isolation, and
   side-effect boundaries.
3. Add the focused executable eval.
4. Add the smallest production durable polling module and setup/unload wiring.
5. Verify the real files on disk.

## Proof Requirements

1. Unit tests in `tests/test_worker_health_polling_anchor.py` are green.
2. Adjacent worker readiness, health endpoint, token rotation, worker dispatch,
   worker progress, retry/backoff, transport-classification, and
   failure-snapshot/manual-retry tests remain green.
3. `evals/home_assistant_durable_worker_health_polling_scaffold.py` emits raw
   `CASE` evidence for the BDD scenarios.
4. Evidence confirms setup enqueues post-setup polling bookkeeping and writes
   schema-valid `scheduled` polling state without a worker health call.
5. Evidence confirms the Home Assistant timer callback is registered after
   setup, runs the first health poll only after setup through Home Assistant's
   executor path, schedules the next callback from durable polling metadata,
   and cancels the pending callback on unload.
6. Evidence confirms an eligible scheduled poll records schema-valid `ready`
   polling state, resets failure count, and schedules the next poll 300
   seconds later without writing or overwriting explicit ADR-0014 worker
   health probe state.
7. Evidence confirms early duplicate polls before `next_poll_not_before`
   return `worker_health_poll_not_due` without calling the worker or advancing
   failure state, and that lost worker preconditions are revalidated before
   the not-due shortcut records schema-valid blocked state without a worker
   call.
8. Evidence confirms `not_ready` and `unavailable` poll results record
   schema-valid redacted state with deterministic 30/60/120/300/900 second
   backoff.
9. Evidence confirms entries without required readiness/token/client
   preconditions record blocked state and do not call the worker.
10. Evidence confirms a single-flight in-progress guard prevents overlapping
   poll calls for the same config entry.
11. Evidence confirms unload removes the config entry's durable polling state,
    stale persisted state for the unloaded entry is not re-merged before a
    pending storage save flushes, in-flight health poll completion after
    unload does not recreate durable polling state or entry-local metadata,
    and in-flight health poll completion after same-entry reload does not
    write stale state to the reloaded entry. Evidence also confirms a
    same-entry worker client/token change during an in-flight poll clears the
    stale in-flight marker and permits a follow-up poll.
12. Evidence confirms two config entries keep polling state, worker clients,
    tokens, and scheduler metadata isolated.
13. Evidence confirms storage-helper load merges persisted entries without
    dropping current unsaved polling entries.
14. Evidence confirms safe token-missing diagnostic polling state survives
    persisted storage load.
15. Evidence confirms invalid persisted polling entries are skipped before
    merge.
16. Evidence confirms persisted polling entries with out-of-bounds scheduler
    metadata or invalid next-poll cadence are skipped before merge.
17. Evidence confirms setup after storage load resumes valid persisted cadence
    and backoff metadata without calling the worker.
18. Evidence confirms durable polling state and eval output do not include raw
    token material, bearer authorization, worker endpoint URLs, health request
    bodies, or health response internals.
19. Evidence confirms worker health response messages that mention endpoint
    URLs are redacted before durable polling state or evidence output.
20. Evidence confirms worker health response codes that normalize endpoint URLs
    are redacted before durable polling state or evidence output.
21. Evidence confirms worker health response codes or messages that echo the
    raw worker token without a bearer marker are redacted before durable
    polling state or evidence output.
22. Evidence confirms dashboard-card WebSocket payloads do not expose worker
    endpoint, token material, health internals, scheduler internals, repair
    recommendations, or durable polling metadata.
23. Evidence confirms no Home Assistant history read, semantic-memory
    persistence, Home Assistant service/device/state mutation, token
    generation/rotation/repair, worker render call, model-provider call, chart
    rendering, chart artifact write, durable retry queue, Recorder write,
    config-entry option write, external queue/database, automatic retry,
    automatic progress task, or automatic repair occurs.
24. Real artifacts are verified on disk: production polling module,
    integration setup/unload wiring, polling-state schema, BDD, eval outline,
    tests, eval, evidence, and verifier anchor.

## Non-Goals

- Persistent worker token storage, migration, rotation UI, or automatic repair.
- Home Assistant Repairs integration.
- Worker render gating based on durable health state.
- Worker render endpoint behavior changes.
- Provider health or retry policy.
- Durable job retry queues or automatic job retries.
- Adding a dashboard-card health or polling command.
- Passing worker endpoint, request details, health internals, scheduler
  internals, repair recommendations, durable polling metadata, or token
  material to the dashboard card or model provider.
- Creating, editing, or deleting Home Assistant dashboards, devices, services,
  automations, scenes, helpers, or state.

## References

- [docs/decisions/0001-home-assistant-integration-plus-worker.md](../decisions/0001-home-assistant-integration-plus-worker.md)
- [docs/decisions/0005-schema-driven-contracts-and-history-normalization.md](../decisions/0005-schema-driven-contracts-and-history-normalization.md)
- [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../decisions/0008-read-only-mvp-and-sandbox-security.md)
- [docs/decisions/0012-worker-transport-and-authentication.md](../decisions/0012-worker-transport-and-authentication.md)
- [docs/decisions/0014-worker-health-readiness-endpoint.md](../decisions/0014-worker-health-readiness-endpoint.md)
- [docs/decisions/0015-durable-worker-health-polling.md](../decisions/0015-durable-worker-health-polling.md)
- [docs/schemas/integration-worker-health-polling-state.schema.json](../schemas/integration-worker-health-polling-state.schema.json)
