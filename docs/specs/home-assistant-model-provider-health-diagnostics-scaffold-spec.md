---
status: draft
date: 2026-06-12
depends-on-adrs:
  - 0001
  - 0005
  - 0007
  - 0008
---

# Home Assistant Integration: Model-Provider Health Diagnostics Scaffold

## Status

Draft. Defines the first integration-owned model-provider health diagnostics
scaffold per ADR-0001, ADR-0005, ADR-0007, and ADR-0008.

## Related Docs

- [bdd/integration/home-assistant-model-provider-health-diagnostics-scaffold-bdd.md](../../bdd/integration/home-assistant-model-provider-health-diagnostics-scaffold-bdd.md)
- [docs/specs/model-provider-spec.md](model-provider-spec.md)
- [docs/specs/home-assistant-job-orchestration-model-provider-planning-scaffold-spec.md](home-assistant-job-orchestration-model-provider-planning-scaffold-spec.md)
- [docs/specs/home-assistant-model-provider-retry-backoff-policy-scaffold-spec.md](home-assistant-model-provider-retry-backoff-policy-scaffold-spec.md)
- [docs/decisions/0007-local-first-ollama-compatible-model-provider.md](../decisions/0007-local-first-ollama-compatible-model-provider.md)
- [docs/schemas/model-provider-health-request.schema.json](../schemas/model-provider-health-request.schema.json)
- [docs/schemas/integration-model-provider-health.schema.json](../schemas/integration-model-provider-health.schema.json)

## Context

ADR-0007 requires provider failures and diagnostics to expose model-provider
problems clearly. The integration can already configure an Ollama-compatible
planner and can record retry/backoff metadata for retry-safe planner failures,
but it does not have a bounded explicit diagnostic probe for provider
availability.

This packet adds only that internal health diagnostic surface. It does not add
automatic provider polling, automatic retry, durable retry queues, provider
credential persistence, dashboard UI, worker behavior, chart rendering, or
Home Assistant mutation.

## Behavior Contract

The model-provider health diagnostics boundary must:

- Run config-entry setup without calling the model provider.
- Enable an explicit health probe only when the existing model-provider planner
  client is configured for the same config entry.
- Reject unknown config entries before provider calls or health metadata
  storage.
- Reject entries without configured model-provider planners before provider
  calls or health metadata storage.
- Build and validate a schema-valid provider health request for the
  Ollama-compatible `GET /api/tags` diagnostic endpoint before a provider call.
- Call only the planner client configured for the targeted config entry.
- Accept provider health responses that report `ready` or `not_ready` and store
  one schema-valid `IntegrationModelProviderHealth` envelope after validation.
- Record schema-valid `unavailable` health metadata for provider transport
  failures without scheduling retries or writing retry-policy metadata.
- Fail closed before health metadata storage when an accepted provider health
  response is malformed or contains secret-like material.
- Keep provider health metadata, setup results, planner clients, and provider
  calls isolated per config entry.
- Avoid exposing provider endpoint, request details, response internals, or
  internal health metadata to dashboard-card WebSocket payloads.

The `IntegrationModelProviderHealth` envelope must include:

- `health_id`
- `type`
- `config_entry_id`
- `status`
- `code`
- `provider`
- `request`
- `response`
- `validation`
- `warnings`
- `orchestration`

Allowed side effects for this packet are limited to reading the targeted config
entry and same-entry planner client, making one explicit provider health call
for an eligible entry, writing one in-memory config-entry-scoped health
envelope after validation, and existing config-entry setup bookkeeping.

The packet remains bounded: it must not mutate Home Assistant
services/devices/state/configuration, read Home Assistant history, persist
semantic memory, call worker render or worker health, run model-provider
planning, record model-provider retry-policy metadata, render charts, write
chart artifacts, add durable health or retry storage, schedule automatic health
checks or retries, start automatic progress tasks, introduce a new provider
transport, or expose provider health metadata to the dashboard card.

## Anchor Artifact

The anchor artifact is the inspectable behavior in
`custom_components/isolinear/model_provider_health.py`,
`custom_components/isolinear/model_provider.py`, and
`src/Isolinear/model_provider_health_diagnostics_anchor.py`, which verifies
ready, not-ready, unavailable, malformed-response, secret-response,
unconfigured-entry, unknown-entry, config-entry isolation, card-safety, schema
validity, and bounded side effects against fake Home Assistant config entries
and fake Ollama-compatible provider clients.

## Implementation Order

1. Create this spec, paired BDD/evidence scaffold, eval outline, and provider
   health schemas.
2. Add failing unit tests and a Python verifier anchor for success, not-ready
   response, transport failure metadata, malformed-response rejection,
   secret-response rejection, unconfigured-entry rejection, unknown-entry
   rejection, isolation, card-safety, schema validity, and side-effect
   boundaries.
3. Add the focused executable eval.
4. Add the smallest production provider health request/client helpers and
   config-entry-scoped provider health module.
5. Wire health setup bookkeeping into config-entry setup without calling the
   provider automatically.
6. Verify the real files on disk.

## Proof Requirements

1. Unit tests in `tests/test_model_provider_health_diagnostics_anchor.py` are
   green.
2. Existing model-provider planning/retry and worker health/retry/transport
   tests remain green.
3. `evals/home_assistant_model_provider_health_diagnostics_scaffold.py` emits
   raw `CASE` evidence for the BDD scenarios.
4. Evidence confirms an eligible configured entry records one schema-valid
   `ready` health envelope.
5. Evidence confirms a provider-reported `not_ready` result records a
   schema-valid internal health envelope without changing planner setup.
6. Evidence confirms provider transport failure records schema-valid
   `unavailable` health metadata without retry/scheduler/durable side effects.
7. Evidence confirms malformed and secret-bearing accepted health responses
   fail closed before health metadata storage.
8. Evidence confirms unconfigured and unknown config-entry health checks fail
   before provider calls or health metadata storage.
9. Evidence confirms two config entries keep provider health metadata and
   provider calls isolated.
10. Evidence confirms dashboard-card WebSocket payloads do not expose provider
    endpoint, request details, response internals, or internal health metadata.
11. Evidence confirms no Home Assistant history read, semantic-memory
    persistence, Home Assistant service/device/state mutation, worker call,
    model-provider planning call, retry-policy write, chart rendering, chart
    artifact write, durable storage, retry queue, scheduler, automatic retry,
    or automatic progress task occurs.
12. Real artifacts are verified on disk: production health module, provider
    client health helper, integration setup wiring, provider health schemas,
    BDD, eval outline, tests, eval, evidence, and verifier anchor.

## Non-Goals

- Automatic or scheduled provider health polling.
- Durable health state, durable retry queues, or repair UI.
- Provider token persistence, token repair, token rotation, or credential
  storage.
- Dashboard-card UI changes or a dashboard health command.
- Worker render, worker retry, worker transport, or worker health behavior.
- Model-provider planning behavior changes.
- Chart rendering, codegen, sandbox execution, or artifact file writes.
- Passing provider endpoint, request details, health metadata, or secret
  material to the dashboard card.
