---
status: draft
date: 2026-06-08
depends-on-adrs:
  - 0001
  - 0003
  - 0005
  - 0006
  - 0008
---

# Home Assistant Integration: Approved History Retrieval Scaffold Anchor

## Status

Draft. Defines the first production Home Assistant integration-owned approved
history retrieval surface per ADR-0001, ADR-0003, ADR-0005, ADR-0006, and
ADR-0008.

## Related Docs

- [bdd/integration/home-assistant-approved-history-retrieval-scaffold-bdd.md](../../bdd/integration/home-assistant-approved-history-retrieval-scaffold-bdd.md) - observable behavior
- [docs/specs/home-assistant-approved-entity-catalog-scaffold-spec.md](home-assistant-approved-entity-catalog-scaffold-spec.md) - approved catalog dependency
- [docs/specs/history-normalization-spec.md](history-normalization-spec.md) - history normalization behavior
- [docs/specs/integration-spec.md](integration-spec.md) - integration responsibilities
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The integration now owns config-entry setup, options-driven entity allowlists, a
dashboard resource registration surface, registered WebSocket commands,
config-entry-scoped job state, and a config-entry-scoped approved entity
catalog. The next production anchor needs the smallest inspectable history
retrieval surface so later orchestration packets can fetch only approved entity
history and hand schema-valid `HistorySeries` records to planning/rendering.

This packet may read approved Home Assistant history from a fake Home Assistant
history source used by tests and evals. It must not call the model provider,
call the worker, persist semantic memory, generate worker tokens, write chart
artifacts, render charts, mutate Home Assistant state/services, or perform real
job orchestration.

## Behavior Contract

The integration must add `custom_components/isolinear/history_retrieval.py`
with a small, inspectable approved-history boundary.

The history retrieval boundary must:

- Initialize one config-entry-scoped in-memory history store under
  `hass.data["isolinear"][entry_id]`.
- Read the current approved entity catalog from the same config entry before
  reading history.
- Reject requested entities that are not present and visible in the approved
  entity catalog before history is read.
- Read only fake Home Assistant history records for approved requested
  entities.
- Normalize raw state records into schema-valid `HistorySeries` records.
- Preserve entity IDs, labels, units, timestamps, raw states, data-quality
  markers, source entity IDs, and warnings.
- Validate every `HistorySeries` against
  `docs/schemas/history-series.schema.json` before storing or returning it.
- Store retrieved history atomically only after every requested series
  validates.
- Clear the config-entry history store on rejected retrievals so stale history
  cannot remain visible after a request or input failure.
- Preserve config-entry isolation when two entries have different approved
  catalogs and history requests.
- Fail closed with structured errors when request entity IDs are malformed,
  entities are not in the approved catalog, history sources are malformed,
  raw history records are malformed, or normalized series do not satisfy
  schema.

Allowed side effects for this packet are limited to:

- Reading the config-entry approved entity catalog.
- Reading approved fake Home Assistant history records.
- In-memory config-entry-scoped history store creation/update.
- Config-entry-scoped setup-result bookkeeping in `hass.data["isolinear"]`.

The history retrieval boundary must report that no worker, model-provider,
semantic-memory persistence, Home Assistant service/device/state mutation,
token-generation, chart artifact write, chart rendering, WebSocket command
registration, dashboard-resource metadata write, or real job orchestration
occurred.

## Anchor Artifact

The anchor artifact is the inspectable
`custom_components/isolinear/history_retrieval.py` module plus
`src/Isolinear/history_retrieval_scaffold_anchor.py`, which verifies catalog
enforcement, schema-valid history series, setup-entry storage, rejected
non-catalog entities, rejected malformed history inputs, rejected malformed
series before storage, config-entry isolation, stale-store clearing, and
side-effect boundaries against fake Home Assistant objects.

## Implementation Order

1. Create this spec and its paired BDD/evidence scaffold.
2. Add failing unit tests for catalog enforcement, schema validation,
   setup-entry storage, non-catalog rejection, malformed history rejection,
   malformed series rejection, stale-store clearing, per-config-entry
   isolation, and side-effect boundaries.
3. Add `custom_components/isolinear/history_retrieval.py` and call setup from
   `async_setup_entry`.
4. Add the Python verifier anchor and focused executable eval.
5. Verify the real files on disk.

## Proof Requirements

1. Unit tests in
   `tests/test_approved_history_retrieval_scaffold_anchor.py` are green.
2. Existing integration scaffold, config-flow/options, dashboard-resource,
   WebSocket registration, job-state, and approved-entity-catalog tests remain
   green.
3. `evals/home_assistant_approved_history_retrieval_scaffold.py` emits raw
   `CASE` evidence for the BDD scenarios.
4. Evidence confirms only entities present and visible in the config-entry
   approved catalog can have history read.
5. Evidence confirms every returned series validates against `HistorySeries`
   before storage/return.
6. Evidence confirms `async_setup_entry` stores a config-entry-scoped history
   retrieval store and setup result.
7. Evidence confirms two config entries receive isolated history stores based
   on their own approved catalogs.
8. Evidence confirms unknown or non-catalog requested entities fail closed
   before history is read.
9. Evidence confirms rejected retrieval clears any previous history series for
   the entry.
10. Evidence confirms malformed raw history inputs fail closed without storing
    history.
11. Evidence confirms malformed normalized history series fail closed before
    storage.
12. Evidence confirms no worker, model provider, semantic-memory persistence,
    Home Assistant service/device/state mutation, token-generation, chart
    artifact write, chart rendering, WebSocket command registration,
    dashboard-resource metadata write, or real job orchestration occurs.
13. Real artifacts are verified on disk: production history retrieval module,
    integration setup wiring, BDD, eval outline, tests, eval, and evidence.

## Non-Goals

- Production Home Assistant recorder/history API adapters.
- Model-provider calls or prompt construction.
- Worker HTTP calls, worker token generation, or artifact storage.
- Semantic-memory persistence, migration, or alias repair UI.
- Chart rendering, dashboard card state updates, subscriptions, retries, or
  progress streaming.
- Production job orchestration.
- Creating, editing, or deleting Home Assistant dashboards, devices, services,
  automations, scenes, helpers, or state.

## References

- [docs/decisions/0001-home-assistant-integration-plus-worker.md](../decisions/0001-home-assistant-integration-plus-worker.md)
- [docs/decisions/0003-entity-allowlist-semantic-resolution-memory.md](../decisions/0003-entity-allowlist-semantic-resolution-memory.md)
- [docs/decisions/0005-schema-driven-contracts-and-history-normalization.md](../decisions/0005-schema-driven-contracts-and-history-normalization.md)
- [docs/decisions/0006-validation-and-repair-loop.md](../decisions/0006-validation-and-repair-loop.md)
- [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../decisions/0008-read-only-mvp-and-sandbox-security.md)
- [docs/specs/home-assistant-approved-entity-catalog-scaffold-spec.md](home-assistant-approved-entity-catalog-scaffold-spec.md)
- [docs/specs/history-normalization-spec.md](history-normalization-spec.md)
- [docs/specs/integration-spec.md](integration-spec.md)
- [docs/schemas/history-series.schema.json](../schemas/history-series.schema.json)
