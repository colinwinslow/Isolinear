# Home Assistant Integration: Model-Provider Retry/Backoff Policy Scaffold - BDD

## Status

Draft. Paired with
[docs/specs/home-assistant-model-provider-retry-backoff-policy-scaffold-spec.md](../../docs/specs/home-assistant-model-provider-retry-backoff-policy-scaffold-spec.md).

Evidence file:

- `bdd/integration/home-assistant-model-provider-retry-backoff-policy-scaffold-evidence.md`

## Why This BDD Exists

This BDD pins down the smallest provider-failure follow-up after the
model-provider planning scaffold: safe planner failures produce internal,
schema-valid retry metadata and a card-facing failed snapshot, without adding
automatic retry, durable queues, worker behavior, rendering, or mutation.

## Scenarios

### Scenario A - failure path: retry-safe provider failure records retry policy

**Given** a config entry has a scaffold-ready orchestration job and a
configured fake Ollama-compatible planner
**When** `job/snapshot` calls the planner and receives a valid retry-safe
provider failure
**Then** the orchestration store should contain one deterministic
`IntegrationModelProviderRetryPolicy`
**And** the card-facing result should be a schema-valid failed snapshot with
`retry_allowed: true`
**And** no model-provider plan, render plan, artifact metadata, or complete
snapshot should be stored

### Scenario B - schema path: provider retry policies validate

**Given** accepted provider-failure handling has stored retry policies
**When** the verifier validates those policies
**Then** every stored policy should validate against
`IntegrationModelProviderRetryPolicy`

### Scenario C - safety path: provider failure details stay internal and sanitized

**Given** a provider failure policy stores provider endpoint and model metadata
**When** the registered WebSocket handler sends the failed snapshot result
**Then** the card-facing snapshot should not contain provider endpoint, model,
or policy internals
**And** provider failures containing secret-like text should fail before policy
storage

### Scenario D - failure path: malformed provider failure metadata fails before policy storage

**Given** a configured planner returns `accepted: false` with malformed retry
metadata
**When** `job/snapshot` requests planning for that job
**Then** the command should fail closed before provider retry-policy storage

### Scenario E - failure path: unknown job fails before provider retry policy

**Given** a config entry has a configured planner but no matching job
**When** `job/snapshot` receives an unknown job ID
**Then** the command should fail closed with `unknown_job`
**And** the planner should not be called
**And** no provider retry policy should be stored

### Scenario F - isolation path: cross-config-entry jobs fail before provider retry policy

**Given** two config entries each have isolated job state and planner clients
**When** the second config entry requests a snapshot for the first entry's job
**Then** the command should fail closed with `unknown_job`
**And** neither planner should be called for the cross-entry request
**And** no provider retry policy should be stored in the second entry

### Scenario G - isolation path: valid provider retry policies stay config-entry scoped

**Given** two config entries each have their own scaffold-ready job and failing
planner
**When** each entry requests a snapshot for its own job
**Then** each entry should record only its own provider retry policy

### Scenario H - boundary path: model-provider retry policy remains bounded

**Given** the provider retry-policy scaffold has handled success and failure
cases
**When** the anchor aggregates observed side effects
**Then** only eligible provider-failure cases should report planner calls and
provider retry-policy bookkeeping
**And** no worker call, Home Assistant history read during provider failure
handling, semantic-memory persistence, Home Assistant mutation, token
generation, chart artifact write, chart rendering, durable retry storage,
automatic retry, provider health polling, or dashboard UI behavior should occur

## Evidence

The implementing slice produces raw outputs from
`evals/home_assistant_model_provider_retry_backoff_policy_scaffold.py` for each
scenario.
