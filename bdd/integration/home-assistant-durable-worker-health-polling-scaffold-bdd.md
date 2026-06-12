# Home Assistant Integration: Durable Worker Health Polling Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-durable-worker-health-polling-scaffold-spec.md](../../docs/specs/home-assistant-durable-worker-health-polling-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-durable-worker-health-polling-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the first durable worker health polling boundary. It proves
the integration can persist redacted polling state and scheduler metadata
without leaking worker internals or turning setup into a worker call.

## Scenarios

### Scenario A - happy path: setup enqueues post-setup polling without a worker call

**Given** a config entry has a configured worker endpoint, ready worker
readiness metadata, a valid integration-owned worker token, and a same-entry
worker health client
**When** config-entry setup records worker health polling state
**Then** the durable polling store should contain one schema-valid `scheduled`
polling state
**And** scheduler bookkeeping should show a post-setup poll is enqueued
**And** no worker health call should occur during setup

### Scenario B - happy path: scheduled ready poll records cadence

**Given** an eligible config entry has a worker health client that reports
`ready`
**When** the scheduled poll step runs
**Then** the durable polling store should contain one schema-valid `ready`
polling state
**And** the consecutive failure count should reset to `0`
**And** the next poll not-before time should be 300 seconds after the poll
**And** the scheduled poll should not write or overwrite explicit
`IntegrationWorkerHealth` probe state
**And** an early duplicate poll before `next_poll_not_before` should return
`worker_health_poll_not_due` without another worker call
**And** if worker preconditions disappear before `next_poll_not_before`, the
poll should record schema-valid `blocked` state before the not-due shortcut
and should not call the worker

### Scenario C - worker path: not-ready and unavailable results back off

**Given** eligible config entries have worker health clients that report
`not_ready` and `unavailable`
**When** scheduled poll steps run
**Then** durable polling state should record schema-valid redacted health
summaries
**And** failure backoff should progress deterministically from 30 to 60
seconds for repeated failures
**And** an early duplicate failure poll before `next_poll_not_before` should
not call the worker or advance consecutive failures

### Scenario D - gate path: missing preconditions block polling before worker calls

**Given** a config entry has a worker endpoint but no valid worker
readiness/token/client preconditions
**When** the scheduled poll step runs
**Then** the durable polling store should contain schema-valid `blocked` state
**And** no worker health call should occur

### Scenario E - safety path: single-flight guard prevents overlapping polls

**Given** an eligible config entry already has a poll marked in flight
**When** another scheduled poll step runs for the same entry
**Then** the poll should fail closed with `worker_health_poll_already_in_flight`
**And** a normal eligible poll should mark `poll_in_flight` before calling the
worker health endpoint
**And** the normal eligible poll should clear `poll_in_flight` in the final
stored result
**And** no additional worker health call should occur

### Scenario F - lifecycle path: unload removes durable polling state

**Given** a config entry has durable worker health polling state
**When** the integration unloads the config entry
**Then** that entry's durable polling state should be removed
**And** unrelated polling state should remain untouched
**And** stale persisted state for the unloaded entry should not be re-merged
before the pending storage save flushes
**And** an in-flight health poll that completes after unload should not
recreate durable polling state or entry-local metadata
**And** an in-flight health poll that completes after unload and same-entry
reload should not write stale state or worker health metadata onto the
reloaded entry
**And** an in-flight health poll that completes after the same entry's worker
client or token changes should clear the stale in-flight marker and allow a
new poll for the replacement context

### Scenario G - isolation path: polling state stays config-entry scoped

**Given** two config entries have separate worker tokens and worker health
clients
**When** scheduled poll steps run for both entries
**Then** each entry should store only its own durable polling state
**And** each worker client should receive only its own token-bearing request
**And** loading persisted storage should merge persisted entries without
dropping current unsaved polling entries
**And** safe token-missing diagnostic polling state should survive persisted
storage load
**And** invalid persisted polling entries should be skipped before merge
**And** persisted polling entries with out-of-bounds scheduler metadata should
be skipped before merge
**And** persisted polling entries whose stored next-poll interval does not
match the 300-second ready cadence or bounded failure backoff windows should
be skipped before merge
**And** persisted polling entries with cancelled scheduler metadata should be
skipped before merge and should not be resumable

### Scenario H - lifecycle path: setup resumes persisted polling cadence

**Given** an eligible config entry has previously stored schema-valid polling
state with a not-ready failure count, bounded backoff, and a future
`next_poll_not_before`
**When** config-entry setup loads persisted storage
**Then** setup should preserve the stored consecutive failure count, backoff,
and `next_poll_not_before`
**And** setup should schedule the remaining delay from the stored
`next_poll_not_before`
**And** setup should not call the worker health endpoint

### Scenario I - security path: polling details do not leak to the card

**Given** a provisioned entry has durable polling state after a health poll
**When** polling state, setup results, eval output, dashboard WebSocket
metadata, model provider metadata, and user-visible command payloads are
inspected
**Then** the raw token should not appear in any payload
**And** durable polling state should not include worker endpoint URLs, bearer
authorization, health request bodies, health response internals, scheduler
task objects, or automatic repair internals
**And** worker health response messages that mention endpoint URLs should be
redacted before durable polling storage or evidence output
**And** worker health response codes that normalize endpoint URLs should be
redacted before durable polling storage or evidence output
**And** worker health response codes or messages that echo the raw worker
token without a bearer marker should be redacted before durable polling
storage or evidence output
**And** dashboard-facing payloads should not include worker endpoint, token
material, health internals, scheduler internals, repair recommendations, or
durable polling metadata

### Scenario J - boundary path: polling remains bounded

**Given** the durable worker health polling scaffold has handled setup,
success, failure, blocked, single-flight, unload, isolation, and setup-resume
cases
**When** the anchor aggregates observed side effects
**Then** durable polling state writes, scheduler bookkeeping, and eligible
worker health calls should be the only allowed new side effects
**And** no Home Assistant history read, semantic-memory persistence,
service/device/state mutation, token generation/rotation/repair, worker
render call, model-provider call, chart rendering, chart artifact write,
durable retry queue, Recorder write, config-entry option write, external
queue/database, automatic retry, automatic progress task, or automatic repair
should occur

### Scenario K - runtime path: Home Assistant timer runs post-setup polling

**Given** an eligible config entry has a Home Assistant timer surface
**When** config-entry setup records worker health polling state
**Then** a post-setup timer callback should be registered without calling the
worker
**When** that callback fires
**Then** the worker health poll should run through Home Assistant's executor
path and store schema-valid `ready` state
**And** the next timer callback should be scheduled 300 seconds later
**And** unloading the config entry should cancel the pending timer callback

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_durable_worker_health_polling_scaffold.py` for each
scenario.
