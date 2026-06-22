---
id: 0025
title: Live planner reasoning as in-place wait feedback in the card
status: accepted
date: 2026-06-22
supersedes: []
superseded-by: null
tags:
  - home-assistant
  - dashboard-card
  - model-provider
  - streaming
  - ux
---

# ADR-0025: Live planner reasoning as in-place wait feedback in the card

> **Status: accepted (2026-06-22).** ADR-0024 D2 (model-driven entity selection)
> landed in `0.1.31`, so the implementation anchor exists and the feature can
> stream across the whole model phase (selection + planning). The open items
> below are now pinned (see "Resolved open items"); implementation proceeds under
> spec `docs/specs/live-planner-reasoning-streaming-spec.md` + BDD
> `docs/bdd/live-planner-reasoning.feature`.

## Context

A local Ollama planner call against a homelab GPU takes tens of seconds — live
`0.1.28` runs showed ~30s for a simple chart and timeouts beyond that (raised to
90s in `0.1.29`). During that window the card shows only a static `planning`
state, so the user stares at a spinner with nothing to indicate progress or that
the model is doing anything sensible. ADR-0024 D2 adds a *second* model
round-trip (entity selection) ahead of planning, lengthening the wait further.

The Ollama `/api/chat` response already contains a rich `thinking` trace (the
model's step-by-step reasoning — visible in the `model_provider` DEBUG logs), and
`PlannerResult` carries a `reasoning_summary`. None of it reaches the user.

A separate, cheaper option — surfacing the final `reasoning_summary` as a "why
this chart" note on the *completed* card — was considered and **rejected by
product direction**: it clutters the finished card, and the value is in the
*wait*, not the result. The goal is to give the user something interesting to
watch *while the model works*, in the place the chart will appear, and then get
out of the way.

## Decision

**Stream the model's reasoning into the card's chart placeholder while the model
runs, and replace it with the rendered chart (or failure) when the model
phase completes.** The reasoning is ephemeral wait-feedback, never a persisted
artifact and never shown on the finished card.

1. **D1 — Streaming planner transport.** The Ollama client issues the model
   call with `stream: true` and reads the NDJSON chunk stream, accumulating the
   `message.thinking` (and/or `message.content`) deltas. The structured-output
   `format` schema still governs the final content; thinking is a side channel.
   The call still runs synchronously on the executor worker thread (off the HA
   event loop, per the ADR-0020/0023 offload), so streaming reads never block the
   loop. A non-streaming path remains as fallback (D6).

2. **D2 — Partial reasoning lives on the active snapshot.** As chunks arrive, the
   planner thread writes the accumulated, **sanitized, length-capped** reasoning
   text onto the job's active `planning` snapshot — the `progress` object is its
   natural home (`integration-job-snapshot.schema.json`; today
   `progress = {stage, message}`, `additionalProperties: false`). This is a
   schema change (a new optional `progress.reasoning` string), so it requires
   this ADR (invariant #8) and lands schema-first (invariant #4), with all synced
   schema copies kept byte-identical.

3. **D3 — Surfaced through the existing poll loop, not a new push channel.** The
   card already polls `isolinear/v1/job/snapshot` and reuses the single-flight
   active-planning snapshot (0.1.12). It simply renders the latest
   `progress.reasoning` it polls. No new card→integration transport; ADR-0011's
   poll-based thin-client model is preserved. Granularity is the poll interval
   ("chunks appearing every ~second"), not token-by-token — deliberately
   "live-ish," which is enough for wait-feedback and avoids a streaming socket.

4. **D4 — In-place in the chart slot, ephemeral.** The card renders the reasoning
   in the area the chart PNG will occupy (e.g. monospace, auto-scrolled to the
   tail). On `complete` the PNG replaces it; on `failed` the failure card
   replaces it. The reasoning is never written to the completed snapshot, never
   stored as an artifact, and never shown after the wait (honoring the "no
   clutter on the finished card" direction).

5. **D5 — Sanitization is mandatory.** The thinking trace is unsanitized model
   output. Before it reaches the card it passes the same redaction posture as
   every card-facing field: no tokens, endpoints, worker URLs, local filesystem
   paths, raw history values, or secret-like material; bounded length. Approved
   entity IDs and the user's own prompt may appear (already disclosed/shown).
   The cap also bounds snapshot size against a runaway trace.

6. **D6 — Graceful degradation.** Providers that don't support streaming, or
   models that emit no `thinking` (non-reasoning models), fall back to today's
   plain `planning` state. The feature is additive wait-feedback, never a hard
   dependency of the planning path.

7. **D7 — Covers the whole model phase (with ADR-0024 D2).** Once D2's entity
   selection call exists, the streamed reasoning spans both model round-trips
   (selection → planning), so the user watches continuously from submit to chart.
   This is why implementation waits for D2 — building it against the single
   planning call now would only have to be reworked.

## Rationale

- The expensive thing (a slow local model) is exactly the thing worth narrating;
  the reasoning trace already exists and is the most honest possible progress
  signal — it *is* the work.
- Reusing the snapshot poll loop (D3) gets "live-ish" feedback with zero new
  transport surface, keeping the thin-client invariant (ADR-0011) intact. A true
  token stream would need a WebSocket push channel — disproportionate for
  wait-feedback (see Alternatives).
- Putting it in the chart slot and discarding it on completion matches the
  product call: value in the wait, not the result; no finished-card clutter.
- Streaming stays stdlib (`urllib` NDJSON line reads) — no new dependency,
  consistent with the existing planner client.

## Resolved open items (pinned on acceptance)

The draft's open items are pinned here so the spec/BDD/implementation have a
single authority:

- **R1 — Character cap: 2000 characters.** `progress.reasoning` is capped at
  2000 characters. The cap bounds snapshot size against a runaway trace (D5) and
  is comfortably enough text to read as wait-feedback at the ~1s poll cadence.
  The cap is enforced server-side (in the integration) before the field is
  written to the snapshot, never relying on the card to truncate.

- **R2 — Rolling tail, not full accumulation.** The 2000-char field holds the
  **tail** of the accumulated reasoning (the most recent characters). The model's
  newest thinking is the most relevant wait-feedback, and a rolling tail keeps
  the field bounded without dropping the "live" feel as the trace grows past the
  cap. When the tail is taken mid-trace, a leading `…` ellipsis marks the elision.

- **R3 — Coarse phase label, surfaced via `progress.stage`.** A phase label is
  shown, derived from which model call is active: `"Selecting entities…"` during
  the ADR-0024 D2 `select_entity` call and `"Planning chart…"` during the
  `plan_chart` call. This reuses the existing `progress.stage` / `state_label`
  plumbing (no new field): the active-planning snapshot's stage carries the
  coarse phase while `progress.reasoning` carries the live trace. (D7.)

- **R4 — Mid-stream transport error → failure card.** If the provider transport
  fails mid-stream, the job falls straight to the existing failure card; partial
  reasoning is **not** preserved (it is ephemeral wait-feedback, D4, and a
  truncated half-thought is not a useful result). This matches the draft's lean
  and keeps the failure path identical to today's non-streaming transport-error
  handling (D6).

- **R5 — Card presentation: monospace, tail-anchored.** The card renders
  `progress.reasoning` in the chart slot as preformatted monospace text,
  visually anchored to its tail (newest content), replaced wholesale by the PNG
  on `complete` or the failure card on `failed` (D4). Verified in the mounted
  Vitest smoke.

## Consequences

**Enables:**
- The user watches the model reason in the chart area instead of a dead spinner,
  across both ADR-0024 model calls.
- A natural place for future "model is selecting entities… / planning the
  chart…" phase labels alongside the reasoning (now realized as R3).

**Constrains:**
- Adds a bounded optional field to the job-snapshot schema (synced copies,
  schema-first) and a streaming mode to the planner client.
- Feedback granularity is the poll interval, not per-token (accepted; D3).
- Sanitization + length cap are load-bearing and must be tested as such (D5/R1).

## Alternatives considered

- *Tier 1 — final `reasoning_summary` on the completed card.* Rejected by
  product direction: clutters the finished card; the value is the wait, not the
  result.
- *Token-by-token WebSocket push to the card.* Rejected: the card is a poll-based
  thin client by design (ADR-0011); a push channel is disproportionate for
  wait-feedback and reopens the client/transport surface.
- *No feedback (status quo).* Rejected: a 30–90s dead spinner across two model
  calls is the UX problem this addresses.
- *Fake/animated progress.* Rejected: dishonest; the real reasoning trace already
  exists and is more interesting.

## References

- ADR-0011 (Lit thin-client card / poll model — preserved), ADR-0017 (in-process
  real slice), ADR-0020 / ADR-0023 (executor offload off the HA loop), ADR-0024
  (model-driven entity selection — the second model call this streams over).
- `custom_components/isolinear/model_provider.py` — `OllamaCompatiblePlannerClient`
  (`stream: false` today; gains the streaming read).
- `custom_components/isolinear/schemas/integration-job-snapshot.schema.json` —
  `progress` object gains an optional bounded `reasoning` (synced copies).
- `frontend/src/isolinear-card.ts` — renders `progress.reasoning` in the chart
  slot during the model phase.
- Invariants #4 (schema-first), #8 (no silent architecture decisions — new
  transport mode), and the card-facing redaction posture (#1 / ADR-0008).
