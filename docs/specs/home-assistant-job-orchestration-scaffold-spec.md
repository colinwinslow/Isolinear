---
status: draft
date: 2026-06-08
depends-on-adrs:
  - 0001
  - 0003
  - 0005
  - 0006
  - 0008
  - 0011
  - 0012
---

# Home Assistant Integration: Job Orchestration Scaffold Anchor

## Status

Draft. Defines the first production Home Assistant integration-owned job
orchestration scaffold behind `isolinear/v1/job/start` per ADR-0001,
ADR-0003, ADR-0005, ADR-0006, ADR-0008, ADR-0011, and ADR-0012.

## Related Docs

- [bdd/integration/home-assistant-job-orchestration-scaffold-bdd.md](../../bdd/integration/home-assistant-job-orchestration-scaffold-bdd.md) - observable behavior
- [docs/specs/home-assistant-job-state-scaffold-spec.md](home-assistant-job-state-scaffold-spec.md) - job state dependency
- [docs/specs/home-assistant-approved-entity-catalog-scaffold-spec.md](home-assistant-approved-entity-catalog-scaffold-spec.md) - approved entity catalog dependency
- [docs/specs/home-assistant-approved-history-retrieval-scaffold-spec.md](home-assistant-approved-history-retrieval-scaffold-spec.md) - approved history dependency
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The integration now owns the registered card-facing WebSocket command set,
config-entry-scoped job state, approved entity catalog, and approved history
retrieval surfaces. The next production anchor needs the smallest inspectable
flow that composes those surfaces for `isolinear/v1/job/start` without calling
the model provider, worker, renderer, semantic memory persistence, token
generation, chart artifact storage, or Home Assistant mutation APIs.

This packet is a scaffold, not production planning. It deterministically
selects requested approved entity IDs from explicit entity IDs or catalog labels
in the prompt, retrieves approved fake Home Assistant history, records
schema-valid `IntegrationJobSnapshot` transitions, and then stops.

## Behavior Contract

The integration must add `custom_components/isolinear/job_orchestration.py`
with a small, inspectable orchestration scaffold boundary.

The orchestration scaffold must:

- Initialize one config-entry-scoped in-memory orchestration store under
  `hass.data["isolinear"][entry_id]`.
- Run from `async_setup_entry` after job state, approved catalog, and approved
  history retrieval stores are initialized.
- Route `isolinear/v1/job/start` through the scaffold when the targeted config
  entry has at least one visible approved catalog entity.
- Preserve the existing deterministic WebSocket command validation and
  config-entry scope validation before orchestration.
- Create deterministic job state for the targeted config entry.
- Append deterministic schema-valid scaffold snapshots for planning,
  approved-history fetching, and scaffold-ready or failed outcomes.
- Select requested entity IDs from explicit entity IDs in the prompt or from
  visible approved catalog item labels/friendly names.
- Return a schema-valid `clarification_needed` snapshot when the prompt does
  not deterministically select a specific approved entity, without reading
  history or silently guessing.
- Reject explicit prompt entity IDs that are not visible in the approved
  catalog before Home Assistant history is read.
- Retrieve history only through the approved history retrieval boundary.
- Store orchestration run summaries under the targeted config entry only.
- Validate every `IntegrationJobSnapshot` before storage/return.
- Return failed schema-valid snapshots with structured failure codes for
  catalog or history gate failures, including missing approved history.
- Preserve config-entry isolation when two entries start jobs with different
  approved catalogs and history.

Allowed side effects for this packet are limited to:

- Reading the config-entry approved entity catalog.
- Reading approved fake Home Assistant history through the history retrieval
  scaffold.
- In-memory config-entry-scoped history retrieval store updates.
- In-memory config-entry-scoped job state updates.
- In-memory config-entry-scoped orchestration run bookkeeping.
- Returning or erroring a WebSocket response for the current command.
- The already-anchored global WebSocket command registration.

The orchestration scaffold must report that no worker, model-provider,
semantic-memory persistence, Home Assistant service/device/state mutation,
token-generation, chart artifact write, chart rendering, durable storage, or
real production job orchestration occurred.

## Anchor Artifact

The anchor artifact is the inspectable
`custom_components/isolinear/job_orchestration.py` module plus
`src/Isolinear/job_orchestration_scaffold_anchor.py`, which verifies
deterministic state transitions, approved catalog/history composition,
catalog-gate failure before history read, missing approved history failure,
per-config-entry isolation, schema-valid snapshots, setup storage, and
side-effect boundaries against fake Home Assistant objects.

## Implementation Order

1. Create this spec and its paired BDD/evidence scaffold.
2. Add failing unit tests for deterministic successful start transitions,
   catalog-gate failure, missing approved history failure, per-config-entry
   isolation, setup storage, malformed snapshot rejection through the shared
   job state gate, and side-effect boundaries.
3. Add `custom_components/isolinear/job_orchestration.py`, wire
   `async_setup_entry`, and route `job/start` through the scaffold only when
   the config entry has visible approved catalog entities.
4. Add the Python verifier anchor and focused executable eval.
5. Verify the real files on disk.

## Proof Requirements

1. Unit tests in `tests/test_job_orchestration_scaffold_anchor.py` are green.
2. Existing integration scaffold, config-flow/options, dashboard-resource,
   WebSocket registration, job-state, approved-entity-catalog, and
   approved-history tests remain green.
3. `evals/home_assistant_job_orchestration_scaffold.py` emits raw `CASE`
   evidence for the BDD scenarios.
4. Evidence confirms `job/start` creates deterministic job and snapshot
   transitions in the targeted config-entry job store.
5. Evidence confirms the scaffold reads only the targeted config-entry approved
   catalog and approved fake history.
6. Evidence confirms prompt entity IDs outside the approved catalog fail closed
   before history is read.
7. Evidence confirms missing approved history returns a schema-valid failed
   snapshot with failure code `missing_approved_history`.
8. Evidence confirms ambiguous prompts return a schema-valid clarification
   snapshot and do not read history.
9. Evidence confirms two config entries receive isolated jobs, history stores,
   and orchestration run summaries.
10. Evidence confirms every returned and stored snapshot validates against
   `IntegrationJobSnapshot`.
11. Evidence confirms no worker, model provider, semantic-memory persistence,
    Home Assistant service/device/state mutation, token-generation, chart
    artifact write, chart rendering, durable storage, or real production job
    orchestration occurs.
12. Real artifacts are verified on disk: production orchestration module,
    integration setup wiring, WebSocket start routing, BDD, eval outline,
    tests, eval, and evidence.

## Non-Goals

- Model-provider calls or prompt-to-plan generation.
- Worker HTTP calls, worker token generation, or artifact storage.
- Chart rendering or chart artifact writes.
- Semantic-memory persistence, migrations, or repair UI.
- Durable job persistence or production progress streaming.
- Production natural-language entity resolution beyond deterministic scaffold
  prompt matching.
- Silent fallback to all approved entities when the prompt is ambiguous.
- Retry, clarification-answer, snapshot, or subscribe production orchestration
  semantics beyond the existing job state scaffold.
- Creating, editing, or deleting Home Assistant dashboards, devices, services,
  automations, scenes, helpers, or state.

## References

- [docs/decisions/0001-home-assistant-integration-plus-worker.md](../decisions/0001-home-assistant-integration-plus-worker.md)
- [docs/decisions/0003-entity-allowlist-semantic-resolution-memory.md](../decisions/0003-entity-allowlist-semantic-resolution-memory.md)
- [docs/decisions/0005-schema-driven-contracts-and-history-normalization.md](../decisions/0005-schema-driven-contracts-and-history-normalization.md)
- [docs/decisions/0006-validation-and-repair-loop.md](../decisions/0006-validation-and-repair-loop.md)
- [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../decisions/0008-read-only-mvp-and-sandbox-security.md)
- [docs/decisions/0011-dashboard-card-implementation-technology.md](../decisions/0011-dashboard-card-implementation-technology.md)
- [docs/decisions/0012-worker-transport-and-authentication.md](../decisions/0012-worker-transport-and-authentication.md)
- [docs/schemas/integration-job-snapshot.schema.json](../schemas/integration-job-snapshot.schema.json)
- [docs/schemas/history-series.schema.json](../schemas/history-series.schema.json)
- [docs/schemas/entity-catalog-item.schema.json](../schemas/entity-catalog-item.schema.json)
