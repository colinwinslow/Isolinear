# Home Assistant Integration: Model-Provider Health Diagnostics Scaffold - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-model-provider-health-diagnostics-scaffold-spec.md](../../docs/specs/home-assistant-model-provider-health-diagnostics-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-model-provider-health-diagnostics-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the first integration-owned model-provider health diagnostic
boundary. It proves the integration can explicitly probe a configured
Ollama-compatible provider without exposing provider internals to the dashboard
card or turning diagnostics into retry orchestration.

## Scenarios

### Scenario A - happy path: ready provider health probe records metadata

**Given** a config entry has a configured Ollama-compatible planner client
**When** the integration explicitly checks model-provider health
**Then** the health store should contain one schema-valid `ready`
`IntegrationModelProviderHealth` envelope
**And** the request should validate before the provider call

### Scenario B - provider path: not-ready response records internal health state

**Given** an eligible config entry has a provider client that reports the
planner model is not ready
**When** the integration explicitly checks model-provider health
**Then** the health store should contain one schema-valid `not_ready` health
envelope
**And** model-provider planner setup should not be changed by the health result

### Scenario C - failure path: transport failure records unavailable health

**Given** an eligible config entry has a provider client that cannot reach the
health endpoint
**When** the integration explicitly checks model-provider health
**Then** the health store should contain one schema-valid `unavailable` health
envelope
**And** no retry, scheduler, or durable health storage side effect should occur

### Scenario D - failure path: malformed accepted response fails before storage

**Given** an eligible config entry has a provider client that returns a
malformed accepted health response
**When** the integration explicitly checks model-provider health
**Then** the request should fail closed with `invalid_model_provider_health_response`
**And** no health metadata should be written

### Scenario E - security path: secret-bearing response fails before storage

**Given** an eligible config entry has a provider client whose accepted health
response contains secret-like material
**When** the integration explicitly checks model-provider health
**Then** the request should fail closed with `invalid_model_provider_health_response`
**And** the secret-like material should not be written to provider health
metadata or user-visible results

### Scenario F - gate path: unconfigured entry is rejected before provider call

**Given** a config entry has no configured model-provider planner
**When** the integration explicitly checks model-provider health
**Then** the request should fail closed with `model_provider_health_not_configured`
**And** no provider health call or health metadata write should occur

### Scenario G - gate path: unknown config entry is rejected before provider call

**Given** Home Assistant has no Isolinear config-entry data for a requested
entry ID
**When** the integration explicitly checks model-provider health
**Then** the request should fail closed with `unknown_config_entry`
**And** no provider health call or health metadata write should occur

### Scenario H - isolation path: health state stays config-entry scoped

**Given** two config entries have separate provider health clients
**When** the integration checks health for both entries
**Then** each entry should store only its own health envelope
**And** each provider client should receive only its own health request

### Scenario I - security path: health details do not leak to the card

**Given** a configured entry has internal provider health metadata
**When** health metadata, setup results, eval output, dashboard WebSocket
metadata, worker setup metadata, and user-visible command payloads are
inspected
**Then** dashboard-facing payloads should not include the provider endpoint,
request details, health response internals, or internal health metadata

### Scenario J - boundary path: health diagnostics remain bounded

**Given** the model-provider health scaffold has handled success, failure,
setup, and isolation cases
**When** the anchor aggregates observed side effects
**Then** provider health calls should occur only for eligible explicit probes
**And** health bookkeeping should be the only new stored metadata
**And** no Home Assistant history read, semantic-memory persistence,
service/device/state mutation, worker call, model-provider planning call,
retry-policy write, chart rendering, chart artifact write, durable storage,
retry queue, scheduler, automatic retry, or automatic progress task should
occur

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_model_provider_health_diagnostics_scaffold.py` for each
scenario.
