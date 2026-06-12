---
status: draft
date: 2026-06-12
depends-on-adrs:
  - 0001
  - 0005
  - 0006
  - 0007
  - 0008
---

# Home Assistant Integration: Model-Provider Retry/Backoff Policy Scaffold

## Status

Draft. Defines a narrow provider-failure follow-up for the existing
integration-owned Ollama-compatible planning boundary.

## Related Docs

- [bdd/integration/home-assistant-model-provider-retry-backoff-policy-scaffold-bdd.md](../../bdd/integration/home-assistant-model-provider-retry-backoff-policy-scaffold-bdd.md)
- [docs/specs/home-assistant-job-orchestration-model-provider-planning-scaffold-spec.md](home-assistant-job-orchestration-model-provider-planning-scaffold-spec.md)
- [docs/specs/model-provider-spec.md](model-provider-spec.md)
- [docs/decisions/0007-local-first-ollama-compatible-model-provider.md](../decisions/0007-local-first-ollama-compatible-model-provider.md)
- [docs/schemas/integration-model-provider-retry-policy.schema.json](../schemas/integration-model-provider-retry-policy.schema.json)

## Context

ADR-0007 requires model-provider failures to report provider role, endpoint or
model context, error type, and whether retry is safe. The existing
model-provider planning scaffold can call a configured planner and fail closed
on invalid provider output, but safe provider transport or runtime failures do
not yet leave a structured retry/backoff envelope.

This packet adds only that missing in-memory scaffold. It does not add provider
health checks, automatic retries, durable queues, new worker behavior, token
persistence, dashboard UI, or provider repair behavior.

## Behavior Contract

When an eligible `isolinear/v1/job/snapshot` request reaches a scaffold-ready
job with a configured planner client and that planner returns a valid
`accepted: false` provider failure:

- The integration stores one config-entry-scoped
  `IntegrationModelProviderRetryPolicy` envelope before any model-provider
  plan, render-plan, artifact, or complete snapshot storage.
- The policy records provider metadata, the deterministic planner request,
  sanitized failure code/message, retry-safe decision, manual-retry affordance,
  bounded exponential scaffold backoff, and `automatic_retry_scheduled: false`.
- The policy validates against
  `docs/schemas/integration-model-provider-retry-policy.schema.json` before
  storage.
- The WebSocket result sent to the dashboard card remains only a schema-valid
  failed `IntegrationJobSnapshot`; provider endpoint/model metadata and retry
  policy internals are not exposed in the card-facing snapshot.
- Retry-safe provider failures return a failed snapshot with
  `retry_allowed: true`.
- Provider failures with malformed retry metadata or forbidden secret-like text
  fail before retry-policy storage.
- Unknown jobs and cross-config-entry jobs fail before planner calls and before
  retry-policy storage.
- Valid provider retry policies stay isolated per config entry.

Allowed side effects are limited to reading the targeted job/source snapshot,
calling the configured planner for an eligible job, storing the in-memory
provider retry policy, appending the failed snapshot, and returning the current
WebSocket response. The packet must not call the worker, render charts, read
Home Assistant history during provider failure handling, persist semantic
memory, mutate Home Assistant state/services/devices/configuration, generate or
rotate tokens, write chart artifacts, write durable retry storage, schedule
automatic retry, add provider health polling, or change dashboard-card UI.

## Anchor Artifact

The anchor artifact is the inspectable behavior in
`custom_components/isolinear/job_orchestration.py` plus
`src/Isolinear/model_provider_retry_backoff_policy_anchor.py`, proving
provider failure policy storage, schema validation, redaction, failed snapshot
conversion, unknown/cross-entry rejection, config-entry isolation, and
side-effect bounds.

## Proof Requirements

1. `tests/test_model_provider_retry_backoff_policy_anchor.py` is green.
2. Adjacent model-provider planning and worker retry/transport tests remain
   green.
3. `evals/home_assistant_model_provider_retry_backoff_policy_scaffold.py`
   emits raw `CASE` evidence for the BDD scenarios.
4. Evidence confirms no model-provider plan, render plan, artifact metadata,
   complete snapshot, worker call, chart rendering, durable retry storage, or
   automatic retry is created for provider failure policy handling.
5. Real changed artifacts are verified on disk.

## Non-Goals

- Provider health checks or durable provider health polling.
- Automatic provider retry or durable retry queues.
- Provider token persistence, token repair, or token rotation.
- Dashboard-card UI changes.
- Worker render, worker retry, worker transport, or worker health behavior.
- Chart rendering, codegen, sandbox execution, or artifact file writes.
