---
id: 0014
title: Worker health/readiness endpoint
status: accepted
date: 2026-06-09
supersedes: []
superseded-by: null
tags:
  - worker
  - integration-api
  - security
  - home-assistant
---

# ADR-0014: Worker health/readiness endpoint

## Context

ADR-0012 defines the versioned HTTP JSON worker transport and bearer-token
authentication for render work, but intentionally left exact worker
health-check endpoint and readiness semantics open. The integration now needs
the smallest inspectable worker readiness probe that can support setup and
future repair flows without adding polling, token rotation, durable queues, or
dashboard-card exposure. The probe must stay inside the existing
integration-owned worker boundary so Home Assistant credentials, worker bearer
tokens, and internal worker metadata never become card-facing or model-facing
data.

## Decision

**Expose worker readiness as `GET /v1/health` over ADR-0012's versioned,
bearer-authenticated worker HTTP JSON transport, and record only schema-valid,
redacted, config-entry-scoped health metadata from explicit integration-owned
probes.**

The health probe uses `X-Isolinear-Worker-API-Version: 1` and
`Authorization: Bearer <worker-token>`, reusing the integration-owned worker
token and the existing worker readiness gate. The integration may store
validated internal health metadata for `ready`, `not_ready`, and
`unavailable` outcomes, but setup does not call the worker automatically and
the dashboard card does not receive worker endpoint, request, response, or
authorization details.

## Rationale

- Reusing ADR-0012 transport and authentication avoids a second worker
  protocol and preserves add-on plus standalone worker compatibility.
- A `GET /v1/health` endpoint gives setup and repair flows a simple,
  inspectable readiness check separate from render submission.
- Explicit probes avoid introducing scheduler, retry, or durable health-state
  semantics before those decisions are needed.
- Schema-valid redacted metadata gives future diagnostics a deterministic
  source of truth without exposing worker credentials or internals to the
  dashboard card or model provider.

## Consequences

**Enables:**

- Worker readiness evidence that is independent from render dispatch.
- Future setup, repair, or diagnostics flows that can query worker readiness
  through one stable endpoint.
- Deterministic validation of worker health request/response metadata before
  internal storage.

**Constrains:**

- Worker health calls must reuse the ADR-0012 bearer-token boundary and must
  redact authorization in stored metadata, evidence, logs, and user-visible
  output.
- Health metadata remains internal and config-entry-scoped; card-facing
  WebSocket payloads must not include worker endpoint, request, response, or
  authorization details.
- Config-entry setup must not become an automatic health poller.
- Transport failures may record an internal `unavailable` result, but must not
  schedule retries, create durable retry storage, rotate tokens, or mutate
  Home Assistant state.

**Open:**

- Token rotation UI and repair flow.
- Durable worker health history, if later needed.
- Scheduled or background health polling, if later needed.

## References

- ADR-0001: Home Assistant integration plus isolated worker
- ADR-0005: Schema-driven contracts and history normalization
- ADR-0008: Read-only MVP and sandbox security
- ADR-0012: Worker transport and authentication
- `docs/specs/home-assistant-worker-health-readiness-endpoint-scaffold-spec.md`
- `docs/specs/integration-api-transport-auth-spec.md`
- `docs/specs/home-assistant-worker-token-provisioning-readiness-scaffold-spec.md`
