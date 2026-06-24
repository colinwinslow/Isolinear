---
id: 0026
title: Model entity selection runs in the pollable planning phase, not in blocking job/start
status: accepted
date: 2026-06-23
supersedes: []
superseded-by: null
tags:
  - home-assistant
  - model-provider
  - orchestration
  - streaming
  - ux
---

# ADR-0026: Model entity selection runs in the pollable planning phase, not in blocking job/start

> **Status: accepted (2026-06-24).** Diagnosed from a live `0.1.42` session on a
> homelab Ollama (`gemma4:e4b` @ `10.0.1.39`): a measured `job/start` round-trip
> took **15.2s** and returned `clarification_needed`, while the first
> `job/snapshot` returned in ~0s. This ADR corrects the orchestration phase
> boundary so ADR-0025 D7's "continuous reasoning from submit to chart" promise
> is actually reachable. Implemented and live-confirmed at `0.1.43` (commit
> `7466ee5`): `job/start` now 0.01s, reasoning streams selection → planning →
> chart. Spec + BDD + evidence under `docs/specs/` and `bdd/integration/`.

## Context

ADR-0024 added a model round-trip (`select_entity`, the D2 expansion/residue
pass) to entity resolution. ADR-0025 D7 specified that live reasoning would
stream across **both** model round-trips — selection *and* planning — "so the
user watches continuously from submit to chart," and deliberately deferred its
own implementation until D2 existed so it wouldn't be built against the single
planning call and then reworked.

The implementation landed the D2 call in the wrong phase. The `job/start`
orchestration handler runs `select_prompt_entity_ids` (D1, deterministic) →
`_inject_semantic_aliases` → `_resolve_entity_selection_with_model` (D2, model)
→ the D3 clarification decision **synchronously, inline, before returning**
(`job_orchestration.py:471–476`). `job/start` is a single blocking WebSocket
call with no in-flight poll, so:

1. **No wait-feedback.** The card does `await startJob(...)` before it has a
   `job_id`; for the full ~15s `this.snapshot` is still `idle`, so `busy=false`,
   no `planning` UI renders, and the card looks inert until `job/start` returns
   and jumps straight to a near-terminal state. The Ask button is not broken —
   it just has no observable effect for 15 seconds.
2. **Entity-selection reasoning is structurally invisible.** `select_entity`'s
   think pass *does* write the live-reasoning slot (it is handed `store` +
   `job_id` for exactly that), but nothing polls during `job/start`, so the slot
   is never read. ADR-0025 D7 is unsatisfiable as wired.

ADR-0025 D3's concurrent-poll + single-flight machinery (the `planning_lock` at
`job_orchestration.py:1194`, with `apply_live_reasoning` surfacing the slot at
line 1199) already exists and already works — verified live: planning-phase
reasoning streamed 20 → 1333 chars on concurrent polls. It simply does not cover
the phase where most of the latency now lives, because that phase is in
`job/start`.

This is a **phase-boundary** problem, not a resolution-policy problem. The D1 →
D2 → D3 pipeline, the deterministic-first ordering, and the allowlist boundary
are all correct and unchanged. The only defect is *where in the request
lifecycle* the existing model call executes.

## Decision

**Move model-driven entity selection (D1 + D2 + the D3 decision) out of the
blocking `job/start` handler and into the pollable planning phase, behind the
existing single-flight `planning_lock`.** `job/start` returns a `planning`
snapshot immediately after cheap synchronous bookkeeping; the first
`job/snapshot` poll resolves entity selection, then planning and render, under
the lock — so concurrent polls surface reasoning across the whole model phase,
exactly as ADR-0025 D7 intended.

1. **D1 — `job/start` returns `planning` immediately.** The handler creates job
   state and returns a schema-valid `planning` snapshot. It performs no model
   calls and reads no history. It no longer emits `clarification_needed`,
   `complete`, or `failed` as a direct response.

2. **D2 — Entity selection moves under the planning lock.** The
   `select_prompt_entity_ids` → `_inject_semantic_aliases` →
   `_resolve_entity_selection_with_model` block runs in the snapshot/planning
   handler, inside the same `planning_lock` single-flight region that already
   guards the planning model call. Resolution logic is **byte-for-byte
   unchanged**; only its call site moves.

3. **D3 — Terminal states become poll outcomes.** After the move, the first
   resolving `job/snapshot` poll returns `clarification_needed` (D2 abstained /
   genuine ambiguity), `complete` (resolved → planned → rendered), or `failed`.
   The card already treats all three as poll outcomes; only the
   `job/start`-returns-the-clarification assumption changes.

4. **D4 — Idempotent, single-flight re-entry.** Entity selection must run exactly
   once per job and cache its result on the job, so concurrent polls during the
   model phase return the in-progress snapshot (with live reasoning) rather than
   launching a second resolution. This reuses the `planning_lock` +
   `apply_live_reasoning` discipline already established for planning (ADR-0025
   D3); the selection result joins the planning result as lock-guarded,
   write-once job state.

5. **D5 — Both orchestration call sites move together.** The `job/retry`
   continuation path (`job_orchestration.py:881–882`) runs the same
   selection-with-model block and moves the same way, so start and retry share
   one orchestration shape rather than diverging.

6. **D6 — No change to resolution semantics or invariants.** D1-before-D2
   ordering, the allowlist boundary (#1), no-mutation (#2), schema-first (#4),
   and deterministic plan validation (#5) are all preserved. The model's role in
   resolution is unchanged from ADR-0024 — this ADR moves a call, it does not
   hand any new decision to the model. The change that triggers this ADR
   (invariant #8) is the **observable contract of `job/start`**: it no longer
   returns terminal states.

## Rationale

- ADR-0025 D7 already specified streaming across both model round-trips; this is
  the orchestration boundary that decision assumed but the implementation didn't
  deliver. It is a correction, not a new capability.
- The fix reuses machinery that already exists and is already verified live (the
  single-flight lock + concurrent-poll reasoning surfacing). Nothing new is
  built on the transport or model side.
- Putting model latency behind the pollable phase is the project's established
  pattern: planning (ADR-0020/0023) already runs there precisely so the loop
  stays responsive and reasoning can stream. Entity selection is the odd one out;
  this aligns it.
- It keeps the thin-client poll model (ADR-0011) intact — no new push channel,
  no new card→integration transport.

## Consequences

**Enables:**
- Immediate `planning` feedback the instant the user clicks Ask, instead of a
  ~15s inert card.
- Live reasoning across the *entire* model phase (selection → planning),
  finally realizing ADR-0025 D7.
- One orchestration shape for start and retry (D5).

**Constrains:**
- The `job/start` WebSocket response contract changes: it returns `planning`,
  never a terminal state. This is the largest surface area — every test, smoke,
  and eval asserting "`job/start` returns the clarification/failure" must move
  the assertion to the first `job/snapshot` poll. (Frontend already handles all
  terminal states as poll outcomes.)
- Entity selection must be made idempotent and single-flight-safe under the lock
  (D4); a non-idempotent re-entry would double-call the model.
- The clarification-continuation and retry paths must be re-verified against the
  new phase boundary (D5), including the live retest items already open in
  STATUS.md (AC-prompt D2 expansion; "Use and remember" alias reuse).

**Resolved during implementation:**
- *Synchronous vs deferred rejections* — **pre-model structural rejections stay
  synchronous.** An empty/unresolvable catalog fails closed on `job/start`
  (`_synchronous_empty_catalog_failure`); only model-dependent outcomes (D2/D3,
  planning, render) defer to the poll. Pinned in the spec's "Synchronous
  rejections".
- *Storage shape for the resolved selection* — **no auxiliary cache is written.**
  Single-flight rests entirely on the existing `planning_lock` plus popping the
  `entity_selection_pending` marker inside the lock before any terminal snapshot;
  an early `job["entity_selection"]` cache field was implemented then removed as
  dead state (architecture-review finding) because the lock + pop already
  guarantee at-most-once model invocation.

## Alternatives considered

- **Frontend-only optimistic `planning` snapshot in `submitPrompt`.** Cheap, no
  schema change, and fixes the "inert card" symptom — but it does **not** make
  entity-selection reasoning pollable (that work is still trapped in the blocking
  `job/start`), so ADR-0025 D7 stays unsatisfied. Viable as an *interim*
  mitigation shipped ahead of this ADR, not as the fix.
- **Stream reasoning during `job/start` via a push channel.** Rejected for the
  same reason ADR-0025 rejected it: the card is a poll-based thin client
  (ADR-0011); a push channel is disproportionate and reopens the transport
  surface.
- **Status quo.** Rejected: a 15s inert card plus permanently invisible
  selection reasoning is the exact UX defect this addresses, and it silently
  breaks an already-accepted decision (ADR-0025 D7).

## References

- ADR-0024 (model-driven entity selection — the D2 call being relocated),
  ADR-0025 (live planner reasoning; **D7** in particular — this ADR makes it
  reachable), ADR-0011 (poll-based thin-client card — preserved), ADR-0020 /
  ADR-0023 (executor offload + planning already in the pollable phase),
  ADR-0017 (in-process real slice).
- `custom_components/isolinear/job_orchestration.py` — `job/start` orchestration
  (`:471–476`, the block that moves), `job/retry` continuation (`:881–882`, the
  second call site), `planning_lock` single-flight + `apply_live_reasoning`
  (`:1194–1201`, the machinery reused).
- `frontend/src/isolinear-card.ts` — `submitPrompt` (`await startJob`),
  `pollSnapshot` (concurrent poll, schedule-before-await), `renderMain`
  `planning` branch (already renders `progress.reasoning`).
- Invariants #1 (allowlist), #4 (schema-first), #5 (deterministic validation),
  #8 (no silent architecture decisions — the `job/start` contract change).
