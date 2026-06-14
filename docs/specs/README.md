# Specs

One spec per shippable feature: `docs/specs/<slug>.md`, paired with a BDD file
at `bdd/<feature>/<slug>-bdd.md`. Scaffold both with `/spec <slug>` (see
`codex/spec.md`).

## What a spec is

A spec defines the **contract surface** of a feature: the observable behavior,
the public interface, the anchor artifact, the proof requirements. It is the
thing implementation makes true. It is NOT a design doc or a tutorial.

## Lifecycle

- Specs are authored as `status: draft`.
- A `draft` is promoted to `accepted` once the contract is agreed.
- Accepted specs are **immutable**. Supersede by writing a new spec.

## Spec / BDD split

The spec lives here; its scenarios live in `bdd/<feature>/<slug>-bdd.md`. The
spec links to the BDD; the BDD enumerates Given/When/Then scenarios; the
implementing slice produces an evidence file proving each scenario was hit.

## Current specs

- `chart-spec-rendering-spec.md` — Chart spec rendering through trusted renderer
- `dashboard-card-spec.md` — Custom dashboard card UX
- `entity-resolution-spec.md` — Entity allowlist resolution and validation
- `history-normalization-spec.md` — Numeric and binary state history normalization
- `home-assistant-config-flow-options-spec.md` — First production Home Assistant config-flow/options surface
- `home-assistant-approved-entity-catalog-scaffold-spec.md` — Config-entry-scoped approved entity catalog scaffold
- `home-assistant-approved-history-retrieval-scaffold-spec.md` — Config-entry-scoped approved history retrieval scaffold
- `home-assistant-dashboard-resource-registration-spec.md` — Integration-owned dashboard card resource registration
- `home-assistant-dashboard-card-long-running-smoke.md` — Dashboard card active-job polling smoke against versioned WebSocket snapshots
- `home-assistant-first-real-vertical-slice.md` — First real Home Assistant metadata/history plus Ollama planner plus in-process matplotlib PNG slice
- `home-assistant-production-artifact-serving.md` — Production serving for rendered chart PNG artifacts
- `home-assistant-worker-rendered-artifact-serving.md` — Worker-rendered real-slice PNG bytes written to the served artifact store
- `home-assistant-integration-scaffold-spec.md` — First production Home Assistant custom integration scaffold
- `home-assistant-job-orchestration-clarification-continuation-scaffold-spec.md` — Config-entry-scoped clarification-answer continuation behind `clarification/answer`
- `home-assistant-job-orchestration-artifact-storage-scaffold-spec.md` — Config-entry-scoped artifact bookkeeping behind `job/snapshot`
- `home-assistant-job-orchestration-model-provider-planning-scaffold-spec.md` — Config-entry-scoped Ollama-compatible planner boundary behind `job/snapshot`
- `home-assistant-job-orchestration-render-planning-scaffold-spec.md` — Config-entry-scoped render-plan bookkeeping behind `job/snapshot`
- `home-assistant-job-orchestration-retry-continuation-scaffold-spec.md` — Config-entry-scoped retry continuation behind `job/retry`
- `home-assistant-job-orchestration-scaffold-spec.md` — Config-entry-scoped job orchestration scaffold behind `job/start`
- `home-assistant-job-orchestration-worker-dispatch-rendering-scaffold-spec.md` — Config-entry-scoped worker dispatch/rendering boundary behind `job/snapshot`
- `home-assistant-job-state-scaffold-spec.md` — Config-entry-scoped in-memory job state scaffold behind registered WebSocket commands
- `home-assistant-model-provider-health-diagnostics-scaffold-spec.md` — Config-entry-scoped explicit model-provider health diagnostics
- `home-assistant-model-provider-retry-backoff-policy-scaffold-spec.md` — Config-entry-scoped model-provider retry/backoff policy metadata for safe planner failures
- `home-assistant-worker-transport-failure-retry-classification-scaffold-spec.md` — Config-entry-scoped worker transport failure classification behind `job/snapshot`
- `home-assistant-worker-failure-snapshot-manual-retry-integration-scaffold-spec.md` — Card-facing worker failure snapshots and manual retry integration behind `job/snapshot` and `job/retry`
- `home-assistant-durable-worker-token-lifecycle-scaffold-spec.md` — Config-entry-scoped durable worker token lifecycle, setup restore, and repair-issue metadata
- `home-assistant-websocket-command-registration-spec.md` — Production Home Assistant WebSocket command registration boundary
- `integration-api-transport-auth-spec.md` — Integration WebSocket API and worker transport authentication
- `integration-spec.md` — Home Assistant custom integration interface
- `model-provider-spec.md` — Ollama-compatible model provider contract
- `product-spec.md` — Product-level feature set
- `security-spec.md` — Sandbox security and safety constraints
- `semantic-memory-spec.md` — Semantic alias storage and recall
- `validation-spec.md` — Plan validation and chart spec safety
- `worker-sandbox-spec.md` — Worker sandbox execution model
