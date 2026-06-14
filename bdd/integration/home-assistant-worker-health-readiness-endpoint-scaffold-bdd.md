# Home Assistant Integration: Worker Health/Readiness Endpoint Scaffold Anchor - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-worker-health-readiness-endpoint-scaffold-spec.md](../../docs/specs/home-assistant-worker-health-readiness-endpoint-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-worker-health-readiness-endpoint-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the first integration-owned worker health/readiness endpoint
boundary. It proves the integration can explicitly probe a configured worker
without leaking worker credentials or exposing internal health metadata to the
dashboard card.

## Scenarios

### Scenario A - happy path: ready worker health probe records redacted metadata

**Given** a config entry has a configured worker endpoint, a valid
integration-owned worker token, and a same-entry worker health client
**When** the integration explicitly checks worker health
**Then** the health store should contain one schema-valid `ready`
`IntegrationWorkerHealth` envelope
**And** the request should validate before the worker call
**And** the stored authorization should be `Bearer <redacted>`

### Scenario B - worker path: not-ready response records internal health state

**Given** an eligible config entry has a worker client that reports
`not_ready`
**When** the integration explicitly checks worker health
**Then** the health store should contain one schema-valid `not_ready`
health envelope
**And** worker renderer setup should not be changed by the health result

### Scenario C - failure path: transport failure records unavailable health

**Given** an eligible config entry has a worker client that cannot reach the
health endpoint
**When** the integration explicitly checks worker health
**Then** the health store should contain one schema-valid `unavailable`
health envelope
**And** no retry, scheduler, or durable health storage side effect should occur

### Scenario D - failure path: malformed accepted response fails before storage

**Given** an eligible config entry has a worker client that returns a malformed
accepted health response
**When** the integration explicitly checks worker health
**Then** the request should fail closed with `invalid_worker_health_response`
**And** no health metadata should be written

### Scenario E - gate path: no-token entry is rejected before worker call

**Given** a config entry has a worker endpoint but no valid integration-owned
worker token
**When** the integration explicitly checks worker health
**Then** the request should fail closed with `worker_health_not_ready`
**And** no worker health call or health metadata write should occur

### Scenario F - gate path: unknown config entry is rejected before worker call

**Given** Home Assistant has no Isolinear config-entry data for a requested
entry ID
**When** the integration explicitly checks worker health
**Then** the request should fail closed with `unknown_config_entry`
**And** no worker health call or health metadata write should occur

### Scenario G - isolation path: health state stays config-entry scoped

**Given** two config entries have separate worker tokens and worker health
clients
**When** the integration checks health for both entries
**Then** each entry should store only its own health envelope
**And** each worker client should receive only its own token-bearing request

### Scenario H - security path: health details do not leak to the card

**Given** a provisioned entry has internal worker health metadata
**When** health metadata, setup results, eval output, dashboard WebSocket
metadata, model provider metadata, and user-visible command payloads are
inspected
**Then** the raw token should not appear in any payload
**And** dashboard-facing payloads should not include the worker endpoint,
request details, bearer authorization, health response internals, or internal
health metadata

### Scenario I - boundary path: health checks remain bounded

**Given** the worker health scaffold has handled success, failure, setup, and
isolation cases
**When** the anchor aggregates observed side effects
**Then** worker health calls should occur only for eligible explicit probes
**And** health bookkeeping should be the only new stored metadata
**And** no Home Assistant history read, semantic-memory persistence,
service/device/state mutation, token generation or rotation, worker render
call, chart rendering, chart artifact write, durable storage, retry queue,
scheduler, automatic retry, or automatic progress task should occur

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_worker_health_readiness_endpoint_scaffold.py` for each
scenario.
