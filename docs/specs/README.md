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
- `home-assistant-dashboard-resource-registration-spec.md` — Integration-owned dashboard card resource registration
- `home-assistant-dashboard-card-long-running-smoke.md` — Dashboard card active-job polling smoke against versioned WebSocket snapshots
- `home-assistant-hacs-install-packaging.md` — HACS custom-repository packaging for one-click install/update
- `home-assistant-first-real-vertical-slice.md` — First real Home Assistant metadata/history plus Ollama planner plus in-process matplotlib PNG slice
- `home-assistant-production-artifact-serving.md` — Production serving for rendered chart PNG artifacts
- `home-assistant-worker-rendered-artifact-serving.md` — Worker-rendered real-slice PNG bytes written to the served artifact store
- `home-assistant-websocket-command-registration-spec.md` — Production Home Assistant WebSocket command registration boundary
- `integration-api-transport-auth-spec.md` — Integration WebSocket API and worker transport authentication
- `integration-spec.md` — Home Assistant custom integration interface
- `live-planner-reasoning-streaming-spec.md` — Live planner reasoning streamed into the chart slot as ephemeral wait feedback (ADR-0025)
- `model-provider-spec.md` — Ollama-compatible model provider contract
- `product-spec.md` — Product-level feature set
- `render-family-capability-envelope.md` — Model-proposed chart family within a deterministic capability envelope (ADR-0023); first live renderer tranche + fail-soft (draft)
- `security-spec.md` — Sandbox security and safety constraints
- `semantic-memory-spec.md` — Semantic alias storage and recall
- `validation-spec.md` — Plan validation and chart spec safety
- `worker-sandbox-spec.md` — Worker sandbox execution model
- `codegen-sandbox-module-promotion.md` — Promote the codegen sandbox anchor into a self-contained worker module (ADR-0029 packet 1) (accepted)
- `worker-http-server.md` — Standalone worker HTTP server (`POST /v1/render`, `GET /v1/health`) wrapping the codegen sandbox over the ADR-0012 transport (ADR-0029 packet 2) (accepted)
- `worker-container-image.md` — Standalone amd64 worker Docker image installing matplotlib into system site-packages so the `-I` sandbox can render (ADR-0029 packet 3) (accepted)
- `codegen-generation-path.md` — Model-generated matplotlib + integration-orchestrated repair loop, opt-in and fail-closed (ADR-0029 packet 4) (accepted)
- `model-authored-analysis.md` — Grounded natural-language answers + supporting charts: answer channel, grounding, timestamp normalization, two-part validation + progressive-verification UX, scipy/seaborn, tranche-1 transforms (ADR-0031 tranche 1) (accepted)
- `answer-grounding-check.md` — Deterministic verdict verification via a claims ledger: full recompute recipe (window/params/event anchor), three-state verified boundary, two-tier guarantee, fail-soft (ADR-0031 D8a, model-authored-analysis packet 4) (accepted)
- `deployment-worker-token.md` — The worker bearer token becomes user-supplied deployment configuration (write-only options field → integration-owned Store); the ADR-0015/0016 durability machinery is deleted (ADR-0032) (accepted)
- `job-orchestration-split.md` — ADR-0035 demolition step 1: the measured, 7-commit, behavior-preserving split of the 8.3K-line orchestration god module along the spine's seams; suite as the net, e2e harness as the gate (accepted, executed 0.2.28)
