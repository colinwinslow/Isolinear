# Home Assistant Integration: Durable Worker Token Lifecycle Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-durable-worker-token-lifecycle-scaffold-spec.md](../../docs/specs/home-assistant-durable-worker-token-lifecycle-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-durable-worker-token-lifecycle-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down durable integration-owned worker token lifecycle behavior.
It proves the integration can restore a persisted worker token after restart
and surface redacted repair issue metadata when it cannot restore one, without
leaking credentials, executing health-polling repair recommendations, or
adding dashboard-card token controls.

## Scenarios

### Scenario A - happy path: setup restores a persisted worker token before readiness

**Given** a config entry has a configured worker endpoint and a valid persisted
integration-owned worker token but no in-memory token
**When** config-entry setup runs durable worker token lifecycle before worker
readiness setup
**Then** the persisted token should be restored into the same-entry in-memory
worker token slot
**And** worker readiness should become schema-valid and `ready`
**And** same-entry worker renderer setup should be enabled without generating a
new token or calling worker render or worker health

### Scenario B - repair issue path: missing persisted token records redacted issue metadata

**Given** a config entry has a configured worker endpoint and no valid
in-memory or persisted worker token
**When** durable worker token lifecycle setup runs
**Then** a schema-valid redacted `not_ready` lifecycle state should be stored
**And** repair-issue metadata should be present with a manual token repair
recommendation
**And** no token should be generated or stored automatically

### Scenario C - disabled path: missing worker endpoint records disabled lifecycle state

**Given** a config entry has no worker endpoint
**When** durable worker token lifecycle setup runs
**Then** a schema-valid redacted `disabled` lifecycle state should be stored
**And** repair-issue metadata should be absent
**And** no token should be generated, restored, or stored

### Scenario D - explicit path: durable wrappers persist successful token operations

**Given** config entries use the durable token lifecycle wrappers for
provisioning, rotation, and repair
**When** each explicit operation succeeds through the existing in-memory token
boundary
**Then** the durable store should privately persist the resulting raw token
**And** the stored lifecycle state should contain only redacted token metadata
**And** stale repair-issue metadata should be cleared

### Scenario E - failure path: invalid persisted entries are skipped before restore

**Given** durable token storage contains malformed tokens, mismatched config
entry ids, or malformed lifecycle metadata
**When** durable worker token lifecycle setup loads persisted entries
**Then** invalid entries should be skipped before any in-memory token restore
**And** readiness should remain `not_ready`
**And** a redacted repair issue should be recorded for the configured entry

### Scenario F - failure path: setup lifecycle storage failure blocks restore

**Given** a config entry has a configured worker endpoint and a valid persisted
integration-owned worker token
**When** setup builds a valid lifecycle state but durable lifecycle storage
fails before accepting the write
**Then** setup should fail closed before worker readiness or renderer setup
**And** the persisted token should not be restored into memory
**And** the previous private token store entry should remain intact

### Scenario G - failure path: lifecycle validation/storage failure rolls back

**Given** a config entry has an existing durable token, readiness metadata, and
worker renderer client
**When** a durable rotation candidate is generated but lifecycle
validation/storage fails
**Then** the old durable token state should remain intact
**And** old in-memory token, readiness metadata, readiness setup, renderer
client, and renderer setup should be restored
**And** no new ready lifecycle envelope should be written

### Scenario H - isolation path: lifecycle state stays config-entry scoped

**Given** two config entries have separate worker endpoint and token lifecycle
state
**When** setup restores and explicit operations run for one entry
**Then** the other entry's raw token, lifecycle state, readiness, renderer
client, and repair issue metadata should remain unchanged

### Scenario I - security path: lifecycle and repair issue details do not leak

**Given** durable restore, durable explicit operations, repair issue creation,
and invalid persisted-entry handling have all run
**When** lifecycle state, setup results, repair issue metadata, eval output,
dashboard WebSocket metadata, model provider metadata, and card-facing command
payloads are inspected
**Then** raw token material should not appear in any user-visible or evidence
payload
**And** dashboard-facing payloads should not include worker endpoint,
lifecycle state, repair issue metadata, bearer authorization, or rotation and
repair internals

### Scenario J - boundary path: durable token lifecycle remains bounded

**Given** the durable token lifecycle scaffold has handled restore, repair
issue, explicit operation, failure, and isolation cases
**When** the anchor aggregates observed side effects
**Then** durable token storage and in-memory token restoration should be the
only new allowed lifecycle side effects
**And** no Home Assistant history read, semantic-memory persistence,
service/device/state mutation, config-entry option write, Recorder write,
worker render call, worker health call, model-provider call, chart rendering,
chart artifact write, durable retry queue, scheduler task, automatic rotation,
automatic token repair execution, setup-time token generation, or
dashboard-card command registration should occur

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_durable_worker_token_lifecycle_scaffold.py` for each
scenario.
