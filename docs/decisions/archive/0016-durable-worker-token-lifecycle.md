---
id: 0016
title: Durable worker token lifecycle
status: deprecated (2026-07-02; never promoted past draft)
date: 2026-06-13
supersedes: []
superseded-by: null
tags:
  - worker
  - token
  - security
  - home-assistant
---

# ADR-0016: Durable worker token lifecycle

## Context

ADR-0012 defines the worker bearer-token boundary, ADR-0014 adds explicit
worker health probes, and ADR-0015 adds durable health polling while explicitly
leaving persistent worker token storage, token-rotation UI, and automatic
repair semantics open. The integration currently can provision, rotate, and
repair worker tokens only in memory. After restart or reload, that means a
configured worker endpoint can lose its integration-owned token even though the
worker itself may still be valid.

Token persistence and repair UI have security consequences. The dashboard card
must never receive worker tokens, worker endpoints, repair internals, or direct
rotation controls, and config-entry options must not become a credential store.
At the same time, the integration needs a deterministic way to restore its own
worker token after restart and expose a safe, inspectable repair status when no
restorable token exists.

## Decision

**Persist integration-owned worker tokens in an integration-owned Home
Assistant storage-helper surface, restore valid persisted tokens during
config-entry setup before worker readiness is evaluated, and expose only
schema-valid redacted token lifecycle and repair-issue metadata.**

The durable token lifecycle store is separate from config-entry options,
Home Assistant entity state, Recorder, dashboard-card configuration, semantic
memory, and worker health polling state. It may contain the raw
integration-owned worker token because the worker transport requires that
secret, but every lifecycle state, setup result, eval output, repair issue
metadata, and dashboard-facing payload must redact token material as
`Bearer <redacted>` or omit it entirely.

Automatic restore for the first implementation means restoring a valid
persisted token into the in-memory worker renderer boundary during setup when a
configured entry has no valid in-memory token. It does not mean generating a
new token during setup or executing a repair recommendation from health
polling. If no valid persisted token exists, the integration records a
redacted repair-issue metadata envelope that can later back a Home Assistant
Repairs flow, but this packet does not register a real Repairs flow or add
dashboard-card repair commands.

The existing in-memory provisioning, rotation, and repair functions remain
available and keep their original bounded contract. New durable lifecycle
wrappers persist tokens only after those explicit operations succeed, validate
redacted lifecycle state before storage, clear stale repair-issue metadata on
successful restore or explicit repair, and roll back durable writes if
lifecycle validation fails.

## Rationale

- Home Assistant's storage helper is the smallest durable mechanism already
  used by the integration, and avoids config-entry options or Recorder as
  credential storage.
- Restoring an existing persisted token during setup solves the restart gap
  without hidden token generation, worker calls, automatic repair execution, or
  dashboard exposure.
- A redacted repair-issue envelope gives an inspectable UI-facing contract
  before committing to Home Assistant Repairs platform details.
- Keeping lifecycle persistence in a new wrapper boundary preserves the
  existing in-memory token readiness/rotation contracts and their tests.
- Separating durable token lifecycle from durable health polling keeps health
  diagnostics from silently rotating or repairing credentials.

## Consequences

**Enables:**

- Restart-safe restoration of integration-owned worker tokens.
- Future Home Assistant Repairs integration backed by schema-valid issue
  metadata rather than ad hoc strings.
- Durable explicit provisioning, rotation, and repair flows that persist token
  material without exposing it to the dashboard card.

**Constrains:**

- Config-entry setup may restore a persisted token but must not generate a new
  token automatically or execute health-polling repair recommendations.
- Durable token storage must remain config-entry-scoped and must validate
  redacted lifecycle metadata before writes.
- Dashboard-card WebSocket payloads must not expose worker token lifecycle
  state, repair issue metadata, worker endpoint URLs, or token material.
- Token lifecycle repair must not call worker render, worker health,
  model providers, Home Assistant history, semantic memory, services, devices,
  entities, Recorder, or external queues/databases.

**Open:**

- Exact Home Assistant Repairs flow registration and user interaction.
- Token expiration/age policy and scheduled rotation cadence.
- Automatic token repair beyond persisted-token restore.
- Add-on-mediated token exchange if the worker is packaged as a Home Assistant
  add-on.

## References

- ADR-0001: Home Assistant integration plus isolated worker
- ADR-0005: Schema-driven contracts and history normalization
- ADR-0008: Read-only MVP and sandbox security
- ADR-0011: Dashboard card implementation technology
- ADR-0012: Worker transport and authentication
- ADR-0014: Worker health/readiness endpoint
- ADR-0015: Durable worker health polling
- `docs/specs/home-assistant-worker-token-provisioning-readiness-scaffold-spec.md`
- `docs/specs/home-assistant-worker-token-rotation-repair-scaffold-spec.md`
- `docs/specs/home-assistant-durable-worker-token-lifecycle-scaffold-spec.md`
