---
id: 0015
title: Durable worker health polling
status: draft
date: 2026-06-10
supersedes: []
superseded-by: null
tags:
  - worker
  - health
  - scheduler
  - security
  - home-assistant
---

# ADR-0015: Durable worker health polling

## Context

ADR-0012 defines the worker HTTP transport and bearer-token boundary, and
ADR-0014 defines explicit `GET /v1/health` probes while deliberately leaving
automatic polling, durable health state, scheduler behavior, and repair
semantics open. The integration now has in-memory worker readiness, explicit
health probing, and explicit token rotation/repair scaffolds, but no durable
source of truth for worker availability across setup, reload, and Home
Assistant restart boundaries.

Durable worker health polling has security and UX consequences. It can create
background worker calls, persistent diagnostic data, retry cadence, and repair
signals, and it could accidentally expose worker endpoints, bearer tokens,
request details, scheduler internals, or repair internals to the dashboard
card if the boundary is not explicit. The decision must also preserve
ADR-0008's read-only MVP posture and avoid turning a health poller into a
hidden render gate, token rotation mechanism, or Home Assistant mutator.

## Decision

**Durable worker health polling will be an integration-owned diagnostic loop
that stores only schema-valid, redacted, config-entry-scoped worker health
summary state in Home Assistant storage, schedules bounded probes through the
existing ADR-0014 health endpoint, and never performs automatic token repair,
token rotation, worker render calls, or dashboard-card exposure.**

Polling is enabled only for config entries with a configured worker endpoint,
an existing valid integration-owned worker token, ready worker readiness
metadata, and a same-entry worker health client. Entries without those
preconditions record disabled or blocked poller state and do not call the
worker. The poller reuses ADR-0012 authentication and ADR-0014 request/response
validation for every probe.

This ADR extends ADR-0014's explicit-probe scaffold without replacing its
health endpoint decision. ADR-0014's constraint that config-entry setup must
not become an automatic health poller remains true for that scaffold and for
setup's synchronous work: setup may create scheduler bookkeeping and enqueue a
later poll after setup completes, but setup itself must not call the worker
health endpoint.

The first durable polling implementation must use a Home Assistant
integration-owned storage helper, not config-entry options, Home Assistant
entity state, Recorder, an external database, or a queue service. Stored state
is versioned and limited to one latest redacted health result per config entry
plus scheduler metadata needed to resume safely: status, sanitized code and
message, failure family, consecutive failure count, last poll time, next poll
not-before time, stale/disabled flags, and validation metadata. The store must
not duplicate worker endpoint URLs, raw tokens, bearer headers, request bodies,
response internals beyond sanitized health summary fields, scheduler task
objects, or repair internals. Removing a config entry removes that entry's
durable health polling state.

Polling starts after config-entry setup or reload only when the preconditions
above are satisfied. A startup or reload poll is scheduled after setup
bookkeeping completes; missed polls are not replayed after restart. Ready
workers use a low-rate periodic probe, initially specified as every 300
seconds. `not_ready` and `unavailable` outcomes use bounded exponential backoff
of 30, 60, 120, 300, and then 900 seconds. A later ready result resets the
failure count and returns the entry to the ready cadence. Poll tasks must be
single-flight per config entry, cancel on unload, and validate state before
each worker call so stale tokens, missing clients, or cross-entry state cannot
be used accidentally.

Durable health state is diagnostic and scheduler input, not an authorization
gate. It does not disable an otherwise ready worker renderer, invalidate
tokens, alter job retry behavior, or decide render outcomes by itself. Worker
render dispatch remains governed by the existing readiness gate and dispatch
failure handling. A future implementation may use fresh durable health state to
produce card-safe failure wording or diagnostics, but only through a paired
spec/BDD/eval slice and without exposing worker internals.

Health polling may record an internal repair recommendation such as
`none`, `manual_probe`, `check_worker`, or `token_repair_available`, but it
must not automatically call token provisioning, token rotation, token repair,
Home Assistant repair flows, service calls, device mutations, or configuration
mutations. Automatic repair, persistent worker token storage, token-rotation
UI, and Home Assistant Repairs integration remain separate decisions.

## Rationale

- Reusing ADR-0012 and ADR-0014 avoids a second worker protocol and keeps
  add-on and standalone worker modes aligned.
- A Home Assistant storage helper is the smallest durable mechanism that stays
  inside the integration boundary without introducing a database, queue, entity
  platform, or Recorder dependency.
- Keeping only the latest redacted health summary gives restart-safe
  diagnostics without creating an unbounded health log or retaining sensitive
  worker transport details.
- Single-flight polling and bounded backoff prevent noisy local-worker failure
  loops while still recovering automatically when the worker becomes ready.
- Treating health state as diagnostic avoids a hidden coupling where a stale
  health result blocks rendering even though the worker might be reachable.
- Separating repair recommendations from repair execution keeps token
  generation, token rotation, and user-facing repair semantics explicit.

## Consequences

**Enables:**

- Restart-safe worker health diagnostics for setup, reload, and future repair
  flows.
- A future schema-backed polling state contract with deterministic tests and
  BDD evidence.
- Bounded automatic health probes without worker render calls or dashboard-card
  exposure.
- Future card-safe user messaging that can say the worker is unavailable
  without revealing endpoint, token, request, response, scheduler, or repair
  details.

**Constrains:**

- Polling must reuse the ADR-0012 bearer-token boundary and ADR-0014
  `GET /v1/health` validation path.
- Stored polling state must be schema-valid, redacted, versioned, and scoped
  to one config entry.
- Polling must not run for unknown entries, entries without valid worker
  tokens, entries without ready readiness metadata, or entries without
  same-entry worker health clients.
- Polling must not call worker render, model providers, Home Assistant
  history, semantic-memory storage, Home Assistant mutation services, token
  provisioning, token rotation, or token repair.
- Dashboard-card WebSocket payloads must not expose worker endpoint, bearer
  material, health internals, scheduler internals, repair recommendations, or
  durable polling metadata.
- Future implementation must add a paired spec, BDD/evidence, schema, tests,
  and eval before adding the poller.

**Open:**

- Exact JSON Schema name and field layout for durable polling state.
- Whether a later user-facing repair UI should use Home Assistant Repairs,
  integration options, or another explicit surface.
- Whether future fresh health state should become a fail-fast hint for worker
  jobs, and what freshness window would be required.
- Persistent worker token storage and automatic token rotation semantics.
- Provider health/retry policy and durable job retry queue behavior.
- Full-suite verification still carries the unrelated codegen sandbox
  matplotlib subprocess flake documented in `STATUS.md`; this ADR does not
  alter that behavior.

## References

- ADR-0001: Home Assistant integration plus isolated worker
- ADR-0005: Schema-driven contracts and history normalization
- ADR-0008: Read-only MVP and sandbox security
- ADR-0012: Worker transport and authentication
- ADR-0014: Worker health/readiness endpoint
- `docs/specs/home-assistant-worker-health-readiness-endpoint-scaffold-spec.md`
- `docs/specs/home-assistant-worker-token-provisioning-readiness-scaffold-spec.md`
- `docs/specs/home-assistant-worker-token-rotation-repair-scaffold-spec.md`
- `STATUS.md`
