# Home Assistant Integration: Worker Token Provisioning/Readiness Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-worker-token-provisioning-readiness-scaffold-spec.md](../../docs/specs/home-assistant-worker-token-provisioning-readiness-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-worker-token-provisioning-readiness-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the first integration-owned worker token readiness boundary.
It proves the integration can explicitly provision or verify a worker token
without leaking credentials or changing the existing no-token worker-dispatch
behavior.

## Scenarios

### Scenario A - happy path: explicit token provisioning records ready state

**Given** a config entry has a configured worker endpoint and no worker token
**When** the integration explicitly provisions one worker token for that entry
**Then** the readiness store should contain one schema-valid `ready`
`IntegrationWorkerReadiness` envelope
**And** the envelope and setup result should contain only redacted bearer
metadata
**And** worker renderer setup should become enabled for that same config entry

### Scenario B - setup path: no token leaves worker not ready

**Given** a config entry has a configured worker endpoint but no worker token
**When** config-entry setup runs
**Then** the readiness store should contain one schema-valid `not_ready`
readiness envelope
**And** worker renderer setup should remain disabled
**And** no worker renderer client should be created

### Scenario C - setup path: missing worker endpoint is disabled

**Given** a config entry has no configured worker endpoint and no worker token
**When** config-entry setup runs
**Then** the readiness store should contain one schema-valid `disabled`
readiness envelope
**And** worker renderer setup should remain disabled
**And** no worker renderer client should be created

### Scenario D - idempotence path: repeated provisioning reuses token

**Given** a config entry already has a valid integration-owned worker token
**When** token provisioning is requested again
**Then** the existing token should be reused
**And** no second token should be generated
**And** readiness should remain schema-valid and `ready`

### Scenario E - failure path: unknown config entry fails before token generation

**Given** Home Assistant has no Isolinear config-entry data for a requested
entry ID
**When** token provisioning is requested for that entry ID
**Then** the request should fail closed with `unknown_config_entry`
**And** no token should be generated or stored
**And** no readiness metadata should be written

### Scenario F - failure path: readiness validation failure rolls back token

**Given** a known config entry has a worker endpoint but readiness schema
validation is unavailable
**When** token provisioning is requested for that entry
**Then** the request should fail closed with
`invalid_integration_worker_readiness`
**And** the generated token should not remain stored
**And** no provisioned-ready readiness envelope should be written

### Scenario G - isolation path: readiness and tokens stay config-entry scoped

**Given** two config entries have worker endpoints
**When** only the first entry receives a provisioned worker token
**Then** the first entry should report `ready`
**And** the second entry should report `not_ready`
**And** the entries should keep separate readiness envelopes, tokens, and
worker renderer setup results

### Scenario H - security path: worker token does not leak

**Given** a provisioned entry has an in-memory integration-owned worker token
**When** readiness metadata, setup results, eval output, dashboard WebSocket
metadata, and model provider setup metadata are inspected
**Then** the raw token should not appear in any user-visible or evidence
payload
**And** bearer metadata should appear only as `Bearer <redacted>`

### Scenario I - boundary path: readiness remains bounded

**Given** the worker token/readiness scaffold has handled success, setup, and
failure cases
**When** the anchor aggregates observed side effects
**Then** token generation should occur only during explicit provisioning
**And** readiness bookkeeping and worker renderer setup should be the only new
allowed setup side effects
**And** no Home Assistant history read, semantic-memory persistence,
service/device/state mutation, worker call, chart rendering, chart artifact
write, durable token storage, token rotation, health check, retry/backoff
policy, automatic progress task, or worker streaming should occur

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_worker_token_provisioning_readiness_scaffold.py` for each
scenario.
