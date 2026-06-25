# Dashboard Card BDD

Scenarios for the Home Assistant dashboard card shell, prompt workflow, and
integration boundary.

## Scenarios

- **Prompt progress** - User submits a prompt and sees planning progress.
- **Custom card anchor** - Home Assistant loads `custom:isolinear-card` from a
  dashboard resource and the card renders the idle prompt surface.
- **Clarification answer** - User answers a clarification and the job continues.
- **Threshold clarification** - User accepts a threshold-derived interval once.
- **Chart result** - User sees a chart-dominant result view with entity
  disclosure, aliases, validation status, and a compact bottom prompt composer
  for a new request.
- **Long-running prompt smoke** - User submits a prompt, the card disables
  duplicate submission, polls `job/snapshot`, and reaches a chart-first PNG
  result.
- **Failure details** - User sees the failed stage and retry or revision action.
- **Integration boundary** - Card gestures are sent through integration-owned
  WebSocket commands, not direct worker, model, history, memory, or mutation
  calls.
- **Integration API transport/auth** - Card commands match versioned
  integration-owned WebSocket schemas, while worker render requests use
  integration-owned bearer authentication that is rejected and redacted when
  invalid.
- **Live planner reasoning** - While the model runs (entity selection then chart
  planning), the card streams the model's sanitized, length-capped reasoning into
  the chart slot as ephemeral wait feedback, then replaces it with the PNG (or
  failure card) on completion. (ADR-0025)
- **Card-owned legend and summary** - The renderer emits a color manifest, the
  card renders an interactive legend from it (swatches, flip-downs, split swatch +
  per-state children for overlays) in place of the in-PNG legend, the caption shows
  a model-authored summary, and overlay labels are model-authored. (ADR-0027)

## Related docs

- Spec: [docs/specs/dashboard-card-spec.md](../../docs/specs/dashboard-card-spec.md)
- Spec: [docs/specs/integration-api-transport-auth-spec.md](../../docs/specs/integration-api-transport-auth-spec.md)
- Spec: [docs/specs/live-planner-reasoning-streaming-spec.md](../../docs/specs/live-planner-reasoning-streaming-spec.md)
- ADR: [docs/decisions/0001-home-assistant-integration-plus-worker.md](../../docs/decisions/0001-home-assistant-integration-plus-worker.md)
- ADR: [docs/decisions/0002-dashboard-card-first-ui.md](../../docs/decisions/0002-dashboard-card-first-ui.md)
- ADR: [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../../docs/decisions/0008-read-only-mvp-and-sandbox-security.md)
- ADR: [docs/decisions/0009-semantic-memory-storage.md](../../docs/decisions/0009-semantic-memory-storage.md)
- ADR: [docs/decisions/0011-dashboard-card-implementation-technology.md](../../docs/decisions/0011-dashboard-card-implementation-technology.md)
- ADR: [docs/decisions/0012-worker-transport-and-authentication.md](../../docs/decisions/0012-worker-transport-and-authentication.md)
- Source scenarios: [docs/bdd/dashboard-card.feature](../../docs/bdd/dashboard-card.feature)
- Paired BDD: [custom-card-anchor-bdd.md](custom-card-anchor-bdd.md)
- Paired BDD: [home-assistant-dashboard-card-long-running-smoke-bdd.md](home-assistant-dashboard-card-long-running-smoke-bdd.md)
- Paired BDD: [integration-api-transport-auth-bdd.md](integration-api-transport-auth-bdd.md)
- Paired BDD: [live-planner-reasoning-streaming-bdd.md](live-planner-reasoning-streaming-bdd.md)
- Paired BDD: [card-legend-and-summary-bdd.md](card-legend-and-summary-bdd.md)
- Evidence: [custom-card-anchor-evidence.md](custom-card-anchor-evidence.md)
- Evidence: [home-assistant-dashboard-card-long-running-smoke-evidence.md](home-assistant-dashboard-card-long-running-smoke-evidence.md)
- Evidence: [integration-api-transport-auth-evidence.md](integration-api-transport-auth-evidence.md)
- Evidence: [live-planner-reasoning-streaming-evidence.md](live-planner-reasoning-streaming-evidence.md)
- Eval: [evals/dashboard_card_anchor.py](../../evals/dashboard_card_anchor.py)
- Eval: [evals/integration_api_transport_auth.py](../../evals/integration_api_transport_auth.py)

## Validation

The implementation slice produces browser-testable evidence for:

- Custom-element registration and `window.customCards` metadata.
- Minimal valid and invalid card config handling.
- Rendered fixture states for idle, planning, clarification, complete, and
  failed jobs.
- Layout evidence for prompt-first idle state and chart-first complete state
  with a compact bottom prompt composer.
- Recorded fake Home Assistant WebSocket calls for prompt submission and
  clarification answers.
- Static or runtime checks that the card does not use direct worker/model calls,
  direct Home Assistant history calls, mutation service calls, semantic-memory
  file access, or browser local storage for Isolinear state.
- Schema-backed integration API and worker transport/auth checks for prompt
  submission, clarification answer, retry, snapshot retrieval, subscription,
  bearer-token acceptance, bad-auth rejection, version rejection, and evidence
  redaction.

## Evidence format

The paired evidence file contains raw test output, browser harness output,
fixture snapshots, recorded WebSocket messages, and any static-check output
needed to inspect the integration boundary.
