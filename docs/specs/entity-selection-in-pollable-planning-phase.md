---
status: accepted
date: 2026-06-23
depends-on-adrs: [0026, 0025, 0024, 0011, 0020, 0023, 0008, 0005]
---

# Entity selection in the pollable planning phase: job/start returns planning immediately

## Status

Accepted (2026-06-24). Defines the contract surface for ADR-0026 (model entity
selection runs in the pollable planning phase, not in blocking `job/start`).
Implemented and live-confirmed at `0.1.43`; deviations recorded below (deferral
gated on `first_real_vertical_slice_enabled`; single-flight rests on the lock +
pending-marker pop with no auxiliary cache field).

## Related docs

- [bdd/integration/entity-selection-in-pollable-planning-phase-bdd.md](../../bdd/integration/entity-selection-in-pollable-planning-phase-bdd.md) — observable behavior
- [docs/decisions/0026-entity-selection-in-pollable-planning-phase.md](../decisions/0026-entity-selection-in-pollable-planning-phase.md) — the decision
- [docs/specs/live-planner-reasoning-streaming-spec.md](live-planner-reasoning-streaming-spec.md) — the streaming infra this completes (ADR-0025 D7)
- [docs/specs/entity-resolution-spec.md](entity-resolution-spec.md) — the D1/D2/D3 pipeline (semantics unchanged)
- [STATUS.md](../../STATUS.md) — current phase and active work

## Context

ADR-0024 added a model round-trip (`select_entity`) to entity resolution, and
ADR-0025 D7 specified that live reasoning would stream across **both** model
round-trips — selection *and* planning. The implementation landed the
`select_entity` call inside the `job/start` handler, which is a single blocking
WebSocket call with no in-flight poll. Measured live on `0.1.42`
(`gemma4:e4b` @ `10.0.1.39`): `job/start` took 15.2s and returned
`clarification_needed`; the first `job/snapshot` returned in ~0s. Result: the
card shows nothing for ~15s (it has no `job_id` to poll while awaiting
`job/start`), and the `select_entity` reasoning — though written to the
live-reasoning slot — is never polled, so ADR-0025 D7 is unsatisfiable.

This spec moves the entity-selection block out of `job/start` and into the
pollable planning phase, behind the existing single-flight `planning_lock`, so
the ADR-0025 D3 concurrent-poll + `apply_live_reasoning` machinery (already
verified live for the planning call) covers entity selection too. **No
resolution semantics change** — the D1 → D2 → D3 pipeline is relocated, not
rewritten.

## Behavior contract

### `job/start` response contract (ADR-0026 D1, invariant #8)

`handle_job_start_orchestration` (`job_orchestration.py`, the path beginning at
`:460`) changes its observable response:

- It performs **only** cheap synchronous bookkeeping: command validation,
  config-entry resolution, job-state creation, and any pre-model structural
  rejection (see "Synchronous rejections" below). It calls **no** model provider
  and reads **no** history.
- On acceptance it returns a schema-valid `planning` snapshot
  (`status: "planning"`), with `progress.stage` a coarse pre-model phase
  (`"Resolving entities…"` — distinct from the in-flight R3 labels) and a
  `message` indicating the model phase is about to run. This snapshot carries no
  `entities`, `clarification`, `chart`, or `failure`.
- It **no longer returns** `clarification_needed`, `complete`, or `failed` as a
  direct response to `job/start`. Those become first-poll outcomes (D3).

**Synchronous rejections (resolved open item from ADR-0026).** Rejections that
occur *before any model work* and are deterministic at the command boundary stay
synchronous on `job/start`, returning the same structured errors / failed
snapshots they do today: unknown/invalid command shape, wrong version, leaky or
mutating payloads, unknown config entry, and an empty or unresolvable approved
catalog (`no_approved_entities_available`, `unknown_allowlisted_entity`). Only
**model-dependent** outcomes (D2 selection, D3 clarification, planning, render)
defer to the poll. Rationale: these structural failures are cheap, already fail
closed at the boundary, and surfacing them immediately is strictly better UX than
deferring; nothing about them benefits from the poll loop.

### Entity selection relocated under the planning lock (ADR-0026 D2, D4)

The block currently at `job_orchestration.py:471–476` —

```python
selection = select_prompt_entity_ids(command["prompt"], catalog_items)
selection = _inject_semantic_aliases(hass, entry_id, command["prompt"], catalog_items, selection)
selection = _resolve_entity_selection_with_model(
    hass, entry_id, command["prompt"], catalog_items, selection,
    store=store, job_id=job["job_id"],
)
```

— moves verbatim into the `job/snapshot` orchestration path, inside the existing
single-flight region guarded by `planning_lock`
(`_artifact_snapshot_lock_for_job`, `:1194`). The three functions
(`select_prompt_entity_ids`, `_inject_semantic_aliases`,
`_resolve_entity_selection_with_model`) are **unchanged**.

Ordering inside the lock, on the first resolving poll:

1. Resolve entity selection (D1 → semantic alias inject → D2 model).
2. If selection requires clarification → write the `clarification_needed`
   snapshot, release the lock, return it (D3).
3. If selection fails (catalog failure) → write the failed snapshot, release,
   return.
4. Otherwise → proceed to planning + render exactly as today.

### Single-flight idempotency (ADR-0026 D4)

Entity selection must run **exactly once** per job, so concurrent polls during
the ~15s model phase do not double-call the model. The existing `planning_lock`
already provides this with no separate result cache needed:

- The first poll acquires the lock and holds it for the *whole*
  resolve-plan-render, and **pops the `entity_selection_pending` marker inside
  the lock before appending any terminal snapshot**. So once resolution starts,
  no later poll re-enters selection: a terminal clarification/failed snapshot is
  no longer an artifact-source snapshot, and a successful resolution replaces the
  source snapshot with the entities-bearing planning snapshot (stage no longer
  `pending`). The pop + lock together guarantee single-flight; no auxiliary
  cache field is written.
- A poll that **cannot** acquire the lock (another poll is mid-resolution)
  returns the in-progress `planning` snapshot with the live-reasoning tail via
  the existing `apply_live_reasoning(latest_snapshot, slot)` path (`:1199`) —
  no change to that mechanism; it now also surfaces the `"Selecting entities…"`
  phase because `_run_model_entity_selection` already writes the slot during
  `job/start` today and will write it under the lock after the move.

### Retry continuation moves identically (ADR-0026 D5)

The `job/retry` continuation path (`job_orchestration.py:881–882`) runs the same
`select_prompt_entity_ids` + `_resolve_entity_selection_with_model` block and
moves the same way: `job/retry` returns `planning` immediately (for a retryable
job), and the first subsequent `job/snapshot` poll re-resolves selection under
the lock. Start and retry share one orchestration shape.

### Resolution semantics and invariants (ADR-0026 D6)

Unchanged: D1-before-D2 ordering, the deterministic specificity fast-path, the
D2 expansion/residue gating (`_D2_EXPANSION_SOURCES`, full-catalog-covered skip,
off-catalog fail-closed), the allowlist boundary (#1), no-mutation (#2),
schema-first (#4), and deterministic plan validation (#5). The model's role in
resolution is identical to ADR-0024. The only contract change is `job/start` /
`job/retry` no longer returning terminal states (#8).

### Card (no schema change; behavior follows the contract)

`frontend/src/isolinear-card.ts` requires **no code change** for correctness: it
already (a) sets `this.snapshot` to the `job/start` result and starts polling
when the status is active, and (b) handles `clarification_needed` / `complete` /
`failed` as poll outcomes. Because `job/start` now returns `planning`
immediately, `busy` flips true and the `planning` section (with
`progress.reasoning` when present) renders the instant the user clicks Ask —
fixing the inert-card symptom for free. The optional interim frontend mitigation
(optimistic snapshot) from ADR-0026 Alternatives is **not** part of this spec;
the backend change makes it unnecessary.

## Anchor artifact

The simplest concrete observable thing, built first: a single integration unit
test in which `job/start` for an ambiguous prompt returns a schema-valid
`planning` snapshot with **no model call made** (a fake provider asserts zero
invocations at `job/start` time), and then the first `job/snapshot` poll returns
the `clarification_needed` snapshot — proving the terminal state moved from the
start response to the poll outcome.

## Implementation order

Concrete-first:

1. **Relocate selection (anchor).** Move the `:471–476` block into the
   `job/snapshot` path under `planning_lock`; make `job/start` return `planning`.
   Add the anchor test (zero model calls at `job/start`; `clarification_needed`
   on first poll). Cache selection write-once on the job (D4).
2. **Synchronous-rejection boundary.** Keep pre-model structural rejections on
   `job/start`; unit tests for unknown entry / empty catalog / malformed command
   still returning synchronously, and for D2/D3/planning/render deferring to the
   poll.
3. **Idempotency / single-flight.** Tests: concurrent polls during resolution
   return the in-progress `planning` snapshot with the `"Selecting entities…"`
   reasoning tail; the model is called exactly once; cached selection is reused.
4. **Retry path (D5).** Move the `:881–882` site; tests for retry returning
   `planning` then resolving on poll.
5. **Migrate existing assertions.** Update every test/eval that asserts a
   terminal `job/start`/`job/retry` response to assert it on the first
   `job/snapshot` poll (see Proof requirement 5). No new behavior — assertion
   relocation tracking the contract move.
6. **BDD evidence.** Run the scenarios in the paired BDD and capture raw outputs.

## Proof requirements

1. Anchor: `job/start` makes zero model calls and returns `planning`; first
   `job/snapshot` poll returns `clarification_needed` — green.
2. Synchronous-rejection unit tests: unknown config entry, empty/unresolvable
   catalog, and malformed/leaky/mutating commands still fail closed on
   `job/start`; model-dependent outcomes defer to the poll — green.
3. Idempotency unit tests: during a multi-poll resolution the model is invoked
   exactly once, concurrent polls return the in-progress `planning` snapshot with
   the live-reasoning tail and `"Selecting entities…"` phase, and repeated polls
   after resolution do not re-call the model — green.
4. Retry unit tests: `job/retry` returns `planning`, first poll resolves
   selection/planning identically to start — green.
5. **Full suite migrated and green.** Every test and eval that previously
   asserted a terminal `job/start` or `job/retry` response is updated to assert
   it on the first `job/snapshot` poll; full Python suite green
   (modulo the documented pre-existing codegen-sandbox flake), affected evals
   PASS.
6. BDD scenarios in the paired BDD pass with a raw evidence file.
7. **Live HACS retest** (closes the standing STATUS.md items): the AC prompt
   resolves both entities via D2 expansion with visible "Selecting entities…"
   reasoning during the wait, the card shows the planning state immediately on
   Ask (no inert window), and reasoning streams continuously selection → planning
   → chart.

## Non-goals

- Any change to resolution semantics (D1/D2/D3 logic, scoring, expansion gating,
  alias matching) — relocation only (ADR-0026 D6).
- The optional frontend optimistic-snapshot mitigation (ADR-0026 Alternatives) —
  the backend change makes it unnecessary; not built here.
- A new push/streaming transport — the poll model (ADR-0011) is preserved.
- Schema changes — `progress.reasoning` already exists (ADR-0025); this spec adds
  no schema surface.
- Deferring pre-model structural rejections to the poll (explicitly kept
  synchronous; see "Synchronous rejections").

## References

- ADR-0026 (this feature), ADR-0025 + its spec (the streaming infra this
  completes — D7), ADR-0024 (the relocated model call), ADR-0011 (poll-based
  thin client — preserved), ADR-0020/0023 (executor offload; planning already in
  the pollable phase), ADR-0008 (redaction), ADR-0005 (schema-first).
- `custom_components/isolinear/job_orchestration.py` — `job/start` (`:460–489`,
  the block that moves), `job/retry` (`:881–882`), `planning_lock` +
  `apply_live_reasoning` (`:1194–1201`), `_resolve_entity_selection_with_model`
  (`:1518`), `_run_model_entity_selection` (`:1574`).
- `frontend/src/isolinear-card.ts` — `submitPrompt`, `pollSnapshot`,
  `renderMain` planning branch (no change required).
- Invariants #1, #2, #4, #5, #8.
