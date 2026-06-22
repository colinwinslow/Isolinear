# Live Planner Reasoning Streaming BDD

ADR-0025: stream the model's sanitized, length-capped reasoning into the card's
chart slot while the model works (entity selection then chart planning), then
replace it with the rendered chart (or failure card) when the model phase
completes. The reasoning is ephemeral wait-feedback, never persisted.

Status: **accepted** — implementation anchor landed 2026-06-22.

Evidence file: `bdd/dashboard-card/live-planner-reasoning-streaming-evidence.md`

Related artifacts:

- Source feature: `docs/bdd/live-planner-reasoning.feature`
- ADR: `docs/decisions/0025-live-planner-reasoning-feedback.md`
- Spec: `docs/specs/live-planner-reasoning-streaming-spec.md`
- Server tests: `tests/test_live_planner_reasoning_streaming.py`
- Card test: `frontend/src/isolinear-card.long-running-smoke.test.ts`

## Scenario A: Reasoning accumulates during the planning phase (per delta)

Given a streaming planner that emits two thinking deltas while it plans
When `OllamaCompatiblePlannerClient.plan_chart` is called with an `on_reasoning` callback
Then the request body sets `stream: true`
And the callback is invoked with the accumulated thinking, growing each delta
And the final structured-output content is parsed exactly as the non-streaming path

## Scenario B: Reasoning spans both model calls with coarse phase labels (D7, R3)

Given a streaming planner used for entity selection and then chart planning
When `select_entity` streams, the live slot stage reads "Selecting entities…"
And when `plan_chart` streams, the live slot stage reads "Planning chart…"
And an in-progress poll surfaces the slot's stage as `progress.stage` and `state_label`

## Scenario C: Reasoning is surfaced on the in-progress poll only (D2, D3, D4)

Given a planning snapshot and a populated per-job live-reasoning slot
When a concurrent `job/snapshot` poll returns the in-progress snapshot
Then `apply_live_reasoning` injects the sanitized tail as `progress.reasoning`
And the returned snapshot re-validates against the snapshot schema
And the stored snapshot is never mutated (reasoning never persisted)

## Scenario D: Reasoning is replaced by the PNG on completion (D4)

Given a job whose planning polls showed live reasoning
When the model phase completes and the chart renders
Then the complete snapshot shows the chart image
And the complete snapshot does not contain `progress.reasoning`
And the per-job live-reasoning slot is cleared

## Scenario E: Reasoning is replaced by the failure card on error (D4, R4)

Given a job whose planning polls showed live reasoning
When the model transport fails mid-stream
Then `plan_chart` returns `model_provider_connection_error` (same as today)
And the job produces the failure card
And no partial reasoning is persisted; the live-reasoning slot is cleared

## Scenario F: Off-limit content is sanitized and length-capped (D5, R1, R2)

Given a thinking trace containing a worker URL, a bearer token, and a local file path
And a trace longer than the 2000-character cap
When `sanitize_reasoning` runs
Then the worker URL, bearer token, and file path are redacted
And the result is at most 2000 characters
And the result keeps the most recent (tail) content with a leading ellipsis
And approved entity IDs are retained (already disclosed)

## Scenario G: Non-streaming provider falls back gracefully (D6)

Given a planner that does not support streaming, or a model that emits no thinking
When the planning poll runs
Then `on_reasoning` is never invoked
And the planning snapshot shows the plain planning state with no `progress.reasoning`
And the chart still renders on completion

## Scenario H: The card renders reasoning in the chart slot during the wait (R5)

Given a mounted card with a planning snapshot carrying `progress.reasoning`
When the card renders the planning state
Then the chart slot shows a monospace reasoning block (`data-testid="planning-reasoning"`)
And the heading shows the coarse phase label
And on completion the chart slot shows the PNG and no reasoning block
