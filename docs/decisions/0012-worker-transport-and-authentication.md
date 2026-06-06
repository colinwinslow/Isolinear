---
id: 0012
title: Worker transport and authentication
status: draft
date: 2026-06-05
supersedes: []
superseded-by: null
tags:
  - worker
  - integration-api
  - security
  - home-assistant
---

# ADR-0012: Worker transport and authentication

## Context

ADR-0001 separates the Home Assistant custom integration from an isolated
worker service. ADR-0011 then keeps the dashboard card as a thin client over
integration-owned Home Assistant WebSocket commands. The next production slice
needs exact command boundaries and a worker authentication envelope before the
integration can safely submit render work.

The worker may be packaged as a Home Assistant add-on or run standalone, so the
transport cannot depend on Home Assistant internals. At the same time, the
worker must never receive a Home Assistant token, semantic-memory store, entity
allowlist, model endpoint credentials, or browser-visible worker credentials.

## Decision

**Expose the card-facing API as versioned Home Assistant WebSocket commands
owned by the Isolinear integration, and expose the worker-facing API as
versioned HTTP JSON endpoints authenticated with an integration-owned bearer
token.**

The MVP integration API version is `1` and uses command names under
`isolinear/v1/`. The first command set covers prompt submission, clarification
answer, retry, snapshot retrieval, and job snapshot subscription. Home
Assistant authenticates the dashboard WebSocket session; the integration still
validates config-entry scope and command schema before using a request.

The worker transport version is also `1`. The integration sends render work to
`POST /v1/render` with `Content-Type: application/json`,
`X-Isolinear-Worker-API-Version: 1`, and `Authorization: Bearer <worker-token>`.
The bearer token is generated or configured by the integration/add-on setup and
is never sent to the dashboard card or model provider. Standalone worker mode
uses the same header contract, with the endpoint URL configured by the user.

## Rationale

- Home Assistant WebSocket commands keep user gestures inside the integration,
  where entity allowlists, memory, history retrieval, validation, and artifact
  ownership already belong.
- HTTP JSON keeps the worker independently runnable as an add-on or standalone
  service without binding it to Home Assistant frontend internals.
- A shared bearer token is simple enough for the MVP and can be generated,
  rotated, and redacted by the integration. It avoids passing Home Assistant
  tokens across the worker boundary.
- Explicit transport versions make incompatible integration/worker upgrades
  fail closed with structured errors.

## Consequences

**Enables:**

- A schema-backed integration API contract before production Home Assistant
  integration code exists.
- Card tests that can assert every user gesture stays on integration-owned
  WebSocket commands.
- Worker tests that can reject missing credentials, wrong credentials,
  unsupported versions, and leaked Home Assistant secrets before render work.

**Constrains:**

- The dashboard card must not store or send worker endpoints or worker tokens.
- The worker must authenticate the request before attempting render validation
  or sandbox execution.
- The integration must redact worker authorization material from evidence,
  logs, and user-visible failure details.
- Add-on and standalone worker modes must both implement the same `/v1/render`
  header and JSON payload contract.

**Open:**

- Exact token rotation UI and repair flow.
- Exact worker health-check endpoint and readiness semantics.
- Exact streaming transport for long-running worker progress, if needed after
  the first render endpoint.

## References

- ADR-0001: Home Assistant integration plus isolated worker
- ADR-0008: Read-only MVP and sandbox security
- ADR-0011: Dashboard card implementation technology
- `docs/specs/integration-api-transport-auth-spec.md`
- `docs/specs/integration-spec.md`
- `docs/specs/security-spec.md`
- `docs/specs/worker-sandbox-spec.md`
