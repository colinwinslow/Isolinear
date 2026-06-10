# Home Assistant Integration: Worker Token Rotation/Repair Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-worker-token-rotation-repair-scaffold-spec.md](../../docs/specs/home-assistant-worker-token-rotation-repair-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-worker-token-rotation-repair-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the explicit integration-owned worker token rotation and
repair boundary. It proves the integration can replace stale or missing
in-memory worker token material without leaking credentials, calling the worker,
or exposing internals to the dashboard card.

## Scenarios

### Scenario A - happy path: rotation invalidates old token and refreshes readiness

**Given** a config entry has a configured worker endpoint, a valid
integration-owned worker token, and an enabled same-entry worker renderer
client
**When** the integration explicitly rotates the worker token for that entry
**Then** the old token and old renderer client should be invalidated
**And** the readiness store should contain one schema-valid `ready`
`IntegrationWorkerReadiness` envelope for the new token
**And** same-entry worker renderer setup should be refreshed without calling
worker render or worker health

### Scenario B - repair path: missing token is repaired explicitly

**Given** a config entry has a configured worker endpoint and no valid worker
token
**When** the integration explicitly repairs the worker token for that entry
**Then** a new integration-owned token should be stored
**And** readiness should become schema-valid and `ready`
**And** worker renderer setup should become enabled for that same config entry

### Scenario C - failure path: readiness validation failure rolls back rotation

**Given** a config entry has an existing valid worker token, readiness metadata,
and worker renderer client
**When** rotation generates a candidate token but readiness validation/storage
fails
**Then** the old token, old readiness metadata, old readiness setup, old
renderer client, and old renderer setup should be restored
**And** no new ready readiness envelope should be written

### Scenario D - failure path: unknown config entry fails before side effects

**Given** Home Assistant has no Isolinear config-entry data for a requested
entry ID
**When** token rotation or repair is requested for that entry ID
**Then** the request should fail closed with `unknown_config_entry`
**And** no token should be generated or stored
**And** no readiness metadata or worker renderer setup should be written

### Scenario E - failure path: cross-entry requests fail before side effects

**Given** two config entries exist with isolated worker token state
**When** entry A requests token rotation or repair for entry B
**Then** the request should fail closed with
`cross_config_entry_worker_token_request`
**And** no token should be generated or stored for either entry
**And** no readiness metadata or worker renderer setup should be changed

### Scenario F - security path: rotated and repaired tokens do not leak

**Given** rotation and repair have both stored integration-owned worker tokens
**When** readiness metadata, setup results, eval output, dashboard WebSocket
metadata, model provider metadata, and user-visible command payloads are
inspected
**Then** raw token material should not appear in any user-visible or evidence
payload
**And** bearer metadata should appear only as `Bearer <redacted>`

### Scenario G - boundary path: rotation and repair remain bounded

**Given** the worker token rotation/repair scaffold has handled success,
failure, and isolation cases
**When** the anchor aggregates observed side effects
**Then** token generation should occur only during explicit rotation or repair
**And** readiness bookkeeping and same-entry worker renderer refresh should be
the only new allowed setup side effects
**And** no Home Assistant history read, semantic-memory persistence,
service/device/state mutation, worker render call, worker health call, chart
rendering, chart artifact write, durable storage, retry queue, scheduler,
automatic retry, or automatic progress task should occur

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_worker_token_rotation_repair_scaffold.py` for each
scenario.
