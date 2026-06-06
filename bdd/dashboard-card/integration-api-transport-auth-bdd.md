# Integration API: Transport and Authentication - BDD

## Status

Draft. Paired with
[docs/specs/integration-api-transport-auth-spec.md](../../docs/specs/integration-api-transport-auth-spec.md).

## Why This BDD Exists

This BDD pins down the user-visible boundary between the dashboard card, the
Home Assistant integration, and the isolated worker. The card can ask for chart
work through versioned integration commands, while worker credentials and Home
Assistant secrets remain behind the integration boundary.

## Scenarios

### Scenario A - happy path: card commands are versioned integration commands

**Given** the dashboard card is configured with an Isolinear config entry  
**When** the user submits a prompt, answers clarification, retries, fetches a
snapshot, or subscribes to job updates  
**Then** each message should match the `IntegrationWsCommand` schema  
**And** each message should stay under `isolinear/v1/`

### Scenario B - happy path: worker render request uses integration-owned auth

**Given** the integration has a worker endpoint and worker bearer token  
**When** it submits a render request to `POST /v1/render`  
**Then** the request should match the `WorkerTransportRequest` schema  
**And** the nested render payload should match `RenderRequest`  
**And** the worker should accept the request only after the bearer token and
version match

### Scenario C - failure path: bad worker credentials fail closed

**Given** a worker render request with missing or incorrect authorization  
**When** the worker validates the request  
**Then** the request should be rejected before rendering  
**And** the decision should use a structured failure code

### Scenario D - failure path: unsupported worker version fails closed

**Given** a worker render request using an unsupported worker API version  
**When** the worker validates the request  
**Then** the request should be rejected before rendering  
**And** no render request should be accepted under a mismatched version

### Scenario E - boundary path: secrets are not exposed across boundaries

**Given** the card-facing command schema and worker transport envelope  
**When** the verifier scans valid and invalid examples  
**Then** card commands should contain no worker URL, worker token, model
endpoint, entity allowlist, raw history, generated code, or semantic-memory data  
**And** worker evidence should redact the bearer token  
**And** requests containing Home Assistant tokens should be rejected

## Evidence

The implementing slice produces an evidence file at
`bdd/dashboard-card/integration-api-transport-auth-evidence.md` containing raw
outputs from `evals/integration_api_transport_auth.py` for each scenario.
