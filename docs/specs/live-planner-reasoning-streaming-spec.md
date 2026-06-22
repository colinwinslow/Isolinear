---
status: draft
date: 2026-06-22
depends-on-adrs: [0025, 0024, 0011, 0020, 0023, 0022, 0008, 0005]
---

# Live planner reasoning streaming: in-place wait feedback in the card

## Status

Draft. Defines the contract surface for ADR-0025 (live planner reasoning as
in-place wait feedback). The ADR is `accepted` (2026-06-22) with its open items
pinned in the ADR's "Resolved open items" section (R1–R5); this spec turns those
into a concrete contract.

## Related docs

- [docs/bdd/live-planner-reasoning.feature](../bdd/live-planner-reasoning.feature) — observable behavior
- [docs/decisions/0025-live-planner-reasoning-feedback.md](../decisions/0025-live-planner-reasoning-feedback.md) — the decision
- [docs/specs/model-provider-spec.md](model-provider-spec.md) — the planner client
- [STATUS.md](../../STATUS.md) — current phase and active work

## Context

A local Ollama planner call against a homelab GPU takes tens of seconds, and
ADR-0024 D2 adds a second model round-trip (entity selection) ahead of planning.
During that 30–90s window the card shows only a static `planning` spinner. The
Ollama `/api/chat` response already carries a rich `thinking` trace; ADR-0025
streams that trace into the card's chart slot as ephemeral wait-feedback, then
replaces it with the chart (or failure) when the model phase completes.

This spec covers the server side (streaming planner transport, sanitization,
length cap, writing the live trace onto the active planning snapshot) and the
card side (rendering `progress.reasoning` in the chart slot). It is purely
additive: providers that don't stream, or models that emit no thinking, fall
back to today's plain `planning` state (D6).

## Behavior contract

### Schema (D2, invariant #4 — schema-first)

`integration-job-snapshot.schema.json` (both synced copies: repo-root
`docs/schemas/` and package-local `custom_components/isolinear/schemas/`, kept
byte-identical) gains one optional property on the `progress` object:

```json
"reasoning": {
  "type": "string",
  "maxLength": 2000
}
```

- The `progress` object remains `additionalProperties: false`; `reasoning` is
  added to `properties` but **not** to `required` (it is optional; existing
  snapshots without it stay valid).
- `maxLength: 2000` is the schema-level guard for R1; the integration also caps
  to 2000 chars before writing, so a runaway trace is bounded both ways.
- No `pattern: "\\S"` constraint — unlike `stage`/`message`, an empty string is
  permitted (e.g. a reasoning field that sanitizes down to nothing), though the
  integration omits the field entirely rather than writing an empty one.

### Streaming planner transport (D1)

`OllamaCompatiblePlannerClient.plan_chart` and `.select_entity`
(`custom_components/isolinear/model_provider.py`) gain an optional keyword
argument:

```python
def plan_chart(
    self,
    request: dict,
    *,
    result_schema: dict | None = None,
    on_reasoning: Callable[[str], None] | None = None,
) -> dict: ...

def select_entity(
    self,
    request: dict,
    *,
    result_schema: dict | None = None,
    on_reasoning: Callable[[str], None] | None = None,
) -> dict: ...
```

- When `on_reasoning is None` (default): unchanged non-streaming behavior — a
  single call with `"stream": False, format: result_schema` (no `think`). This is
  the D6 fallback path and keeps every existing caller/test green.
- When `on_reasoning` is provided: **two sequential calls** (the 0.1.36 two-pass
  correction). `think` and `format` are mutually exclusive on Ollama — when
  `format` is set Ollama silently suppresses thinking, and without `format` the
  model produces structurally invalid JSON on harder prompts — so reasoning and
  constrained decoding cannot share one call:
  - **Pass 1 — think pass** (`stream:true, think:true, no format`): the client
    reads the NDJSON chunk stream line-by-line, accumulating `message.thinking`
    (and, if absent, `message.content`) deltas, and after each delta calls
    `on_reasoning(accumulated_text)` with the full accumulated raw thinking so
    far. The think-pass *content* is discarded; think-pass *failures are
    non-fatal* (reasoning is presentational — planning proceeds regardless, D6).
  - **Pass 2 — plan / select pass** (`stream:false, format:result_schema, no
    think`): the same request as the non-streaming fallback; returns reliable,
    schema-constrained JSON. This is the call whose result is parsed and
    validated; `on_reasoning` is **not** passed to it.
- The return shape is identical in both modes (`accepted`, `code`, `provider`,
  `planner_result`/`selection_result`, `provider_response`) — it always comes
  from the format-constrained pass.
- The call still runs synchronously on the executor worker thread (ADR-0020/0023
  offload); streaming line-reads never touch the HA event loop.
- A non-reasoning model (no `thinking`, empty deltas) simply never invokes the
  callback — graceful degradation (D6).

A module-level helper performs the streaming read and sanitization:

```python
REASONING_CHAR_CAP = 2000

def sanitize_reasoning(raw: str) -> str:
    """Redact + rolling-tail-cap a raw model thinking trace for card display."""
```

`sanitize_reasoning` (D5, R1, R2):
1. Redacts off-limit material: bearer/auth tokens, endpoint/worker URLs
   (`http(s)://…`), local filesystem paths (`/…`, `C:\…`), and obvious
   secret-like tokens. Approved entity IDs and the user's own prompt may remain
   (already disclosed).
2. Collapses to the trailing `REASONING_CHAR_CAP` characters (rolling tail, R2);
   when content was elided from the front, prefixes a single `…`.
3. Returns the sanitized, capped string (possibly empty → caller omits the
   field).

### Writing the live trace onto the active snapshot (D2, D3)

`job_orchestration.py` drives both model calls during a `job/snapshot` poll
(under the single-flight planning lock, 0.1.12). It passes an `on_reasoning`
callback that writes the **sanitized, capped** trace to a shared per-job slot so
that concurrent polls — which today return the `job_orchestration_artifact_snapshot_in_progress`
snapshot — surface the latest reasoning:

- A per-job `live_reasoning` slot lives on the orchestration `store` keyed by
  `job_id` (`store["live_reasoning"][job_id] = {"stage": <phase>, "text": <tail>}`).
- The callback sets `stage` to the coarse phase (R3): `"Selecting entities…"`
  during `select_entity`, `"Planning chart…"` during `plan_chart`.
- When a poll returns the in-progress active-planning snapshot, the integration
  injects the slot's `text` as `progress.reasoning` and the slot's `stage` as
  `progress.stage` (and a matching `state_label`) on the returned snapshot —
  via a single helper `apply_live_reasoning(snapshot, slot)` that re-validates
  the snapshot against the schema before returning.
- The slot is cleared when the job leaves the model phase (complete or failed):
  `progress.reasoning` is **never** written to the stored complete/failed
  snapshot (D4) — it exists only on the transient in-progress snapshot the poll
  synthesizes.

### Mid-stream transport error (R4)

If the NDJSON read raises a transport error mid-stream, `plan_chart` /
`select_entity` return the same `model_provider_http_error` /
`model_provider_connection_error` failure they return today, and the orchestration
produces the existing failure card. Partial reasoning is discarded; the slot is
cleared. No new failure code, no partial-reasoning persistence.

### Card rendering (D4, R3, R5)

`frontend/src/isolinear-card.ts` (+ `types.ts`):

- `IsolinearJobSnapshot.progress` gains optional `reasoning?: string`.
- The `planning` branch of `renderMain` renders, in the chart slot:
  - the coarse phase as the heading (`progress.stage`),
  - `progress.message` as today, and
  - when `progress.reasoning` is present and non-empty, a preformatted monospace
    block (`data-testid="planning-reasoning"`) anchored to its tail (newest
    content visible).
- `complete` replaces the slot with the PNG; `failed` replaces it with the
  failure card. Reasoning is never shown after the wait (D4).

## Anchor artifact

The simplest concrete observable thing, built first: a single unit test in which
a streaming fake provider emits two thinking deltas, and one `job/snapshot` poll
returns an in-progress `planning` snapshot whose `progress.reasoning` equals the
sanitized accumulation of those deltas and whose `progress.stage` is the coarse
phase label. That snapshot — schema-valid, with a live reasoning tail — is the
artifact.

## Implementation order

Concrete-first:

1. **Schema** (invariant #4): add `progress.reasoning` to both synced copies;
   confirm byte-identical. Add a failing unit test that the schema accepts a
   snapshot with `progress.reasoning` and rejects one over 2000 chars.
2. **`sanitize_reasoning` + streaming read** in `model_provider.py`, behind the
   `on_reasoning` callback (default-None = unchanged). Unit tests for redaction,
   rolling-tail cap, and the NDJSON accumulation/callback (anchor).
3. **Orchestration plumbing**: `store["live_reasoning"]` slot, callbacks wired
   into both model calls, `apply_live_reasoning` injecting onto the in-progress
   poll snapshot, slot cleared on terminal states. Unit tests for the per-poll
   update, the two-call phase labels, and the clear-on-complete/failed paths.
4. **Frontend**: `types.ts` + `isolinear-card.ts` render; mounted Vitest smoke.
   Rebuild bundle, copy dist to the HACS package.
5. **BDD evidence**: run the scenarios in
   `docs/bdd/live-planner-reasoning.feature` and capture raw outputs.

## Proof requirements

1. Unit tests for `sanitize_reasoning` (redaction + rolling-tail cap) and the
   NDJSON streaming accumulation/callback in `model_provider.py` green.
2. Unit tests for the orchestration live-reasoning slot — per-poll update, both
   model-call phase labels, clear-on-complete, clear-on-failed, and the
   non-streaming fallback (no reasoning) — green.
3. Schema unit test: a snapshot with a valid `progress.reasoning` passes; one
   exceeding 2000 chars fails; both synced schema copies are byte-identical.
4. BDD scenarios in `docs/bdd/live-planner-reasoning.feature` pass with a raw
   evidence file.
5. Frontend mounted smoke renders `progress.reasoning` in the chart slot during
   planning and shows the PNG (not the reasoning) on completion.
6. Real-artifact proof on disk: read back the changed schema, model_provider,
   orchestration, and bundled card; confirm the field flows end-to-end.

## Non-goals

- Token-by-token streaming to the card (rejected by ADR-0025; granularity is the
  poll interval, D3). No WebSocket push channel.
- Persisting reasoning on the completed/failed snapshot or as an artifact (D4).
- Surfacing the final `reasoning_summary` on the finished card (rejected Tier 1).
- Preserving partial reasoning across a mid-stream transport error (R4).
- A new failure code or new transport surface (D3, R4).

## References

- ADR-0025 (this feature), ADR-0024 (the second model call), ADR-0011 (poll-based
  thin client — preserved), ADR-0020/0023 (executor offload), ADR-0022 (render
  routing), ADR-0008 (redaction posture), ADR-0005 (schema-first).
- `custom_components/isolinear/model_provider.py`, `job_orchestration.py`,
  `schemas/integration-job-snapshot.schema.json`, `frontend/src/isolinear-card.ts`.
