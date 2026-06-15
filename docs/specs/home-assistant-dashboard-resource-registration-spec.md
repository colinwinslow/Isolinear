---
status: draft
date: 2026-06-08
depends-on-adrs:
  - 0001
  - 0005
  - 0008
  - 0011
  - 0012
  - 0013
---

# Home Assistant Integration: Dashboard Resource Registration Anchor

## Status

Draft. Defines the first production dashboard resource registration surface for
the Isolinear custom integration per ADR-0001, ADR-0005, ADR-0008, ADR-0011,
ADR-0012, and ADR-0013.

## Related Docs

- [bdd/integration/home-assistant-dashboard-resource-registration-bdd.md](../../bdd/integration/home-assistant-dashboard-resource-registration-bdd.md) - observable behavior
- [docs/specs/dashboard-card-spec.md](dashboard-card-spec.md) - custom card contract
- [docs/specs/home-assistant-integration-scaffold-spec.md](home-assistant-integration-scaffold-spec.md) - integration package scaffold
- [docs/specs/home-assistant-config-flow-options-spec.md](home-assistant-config-flow-options-spec.md) - config-entry surface
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The production integration scaffold and config-flow/options surface are
anchored. The existing dashboard card bundle at
`frontend/dist/isolinear-card.js` is a real ES module, but Home Assistant still
needs an integration-owned way to serve and register that module as a dashboard
resource so dashboards can use `type: custom:isolinear-card`.

This packet must keep resource registration separate from job orchestration.
It may register static HTTP paths and Home Assistant dashboard resource
metadata, but it must not call the worker, model provider, Home Assistant
history APIs, semantic-memory storage helpers, token generation, or Home
Assistant service/device/state mutation APIs.

## Behavior Contract

The integration must add `custom_components/isolinear/dashboard_resource.py`
with a small, inspectable registration boundary.

The registration boundary must:

- Serve the checked-in card bundle from an integration-owned static HTTP path
  using Home Assistant's async static-path API when running inside Home
  Assistant.
- Register exactly one Lovelace/dashboard resource metadata record for the card
  bundle URL with resource type `module`.
- Serve the card asset from `/api/isolinear/static/isolinear-card.js`, while
  using a package-versioned Lovelace resource URL such as
  `/api/isolinear/static/isolinear-card.js?v=<version>`.
- Run from `async_setup_entry`, store the registration result under the
  config-entry ID, and keep the resource metadata global because Home
  Assistant dashboard resources are global.
- Reuse an existing resource metadata record with the same URL and type instead
  of creating a duplicate.
- Update an existing Isolinear resource metadata record with the legacy
  unversioned URL or an older version query to the current versioned URL instead
  of silently reusing the stale URL or creating a duplicate.
- Remain idempotent across repeated setup calls for the same config entry.
- Fail closed with a structured code before registering resource metadata when
  the card bundle is missing or the Lovelace storage resource collection is not
  available.

Allowed side effects for this packet are limited to:

- Static HTTP path registration for the card bundle directory.
- Creation, reuse, or in-place update of Home Assistant dashboard resource
  metadata for the Isolinear card module. Updates are limited to Isolinear
  module resources whose base URL matches the integration card resource.
- Config-entry-scoped bookkeeping in `hass.data["isolinear"][entry_id]`.

The registration boundary must report that no worker, model-provider, Home
Assistant history, semantic-memory, Home Assistant service/device/state
mutation, token-generation, job-orchestration, or WebSocket command handling
call occurred. It must separately report dashboard resource metadata creation,
reuse, or stale-resource update as the allowed Home Assistant metadata write
for this packet.

## Anchor Artifact

The anchor artifact is the inspectable
`custom_components/isolinear/dashboard_resource.py` module plus
`src/Isolinear/dashboard_resource_anchor.py`, which verifies static path
metadata, Lovelace resource metadata, idempotence, missing-bundle rejection,
config-entry setup storage, and side-effect boundaries against fake Home
Assistant objects.

## Implementation Order

1. Create this spec and its paired BDD/evidence scaffold.
2. Add failing unit tests for static path metadata, resource metadata,
   idempotence, setup-entry storage, missing-bundle rejection, and side-effect
   boundaries.
3. Add `custom_components/isolinear/dashboard_resource.py` and call it from
   `async_setup_entry`.
4. Add the Python verifier anchor and focused executable eval.
5. Verify the real files on disk.

## Proof Requirements

1. Unit tests in `tests/test_dashboard_resource_registration_anchor.py` are
   green.
2. `evals/home_assistant_dashboard_resource_registration.py` emits raw `CASE`
   evidence for the BDD scenarios.
3. Evidence confirms the checked-in bundle exists and is served from the
   integration-owned static path.
4. Evidence confirms the registered dashboard resource URL is the current
   package-versioned `/api/isolinear/static/isolinear-card.js?v=<version>` URL
   and the resource type is `module`.
5. Evidence confirms repeated setup and pre-existing resource metadata do not
   create duplicates.
6. Evidence confirms stale Isolinear resource metadata is updated in place
   rather than duplicated or silently reused.
7. Evidence confirms missing bundle and unavailable resource collection cases
   fail closed before metadata creation.
8. Evidence confirms no worker, model provider, Home Assistant history,
   semantic-memory, Home Assistant service/device/state mutation, token-generation, job
   orchestration, or extra WebSocket command handling calls occur.
9. Real artifacts are verified on disk: production resource module, integration
   setup call, BDD, eval outline, tests, eval, and evidence.

## Non-Goals

- Worker token generation, rotation, storage, or repair UI.
- Worker health checks or readiness validation.
- Home Assistant history access or entity catalog construction.
- Model-provider calls.
- Semantic-memory persistence.
- Job orchestration, subscriptions, streaming, retries, or artifact storage.
- Creating, editing, or deleting Home Assistant dashboards or dashboard cards.
- Editing unrelated dashboard resource metadata.
- Removing dashboard resource metadata on config-entry unload.
- Moving or rebuilding the frontend bundle.
- YAML-mode resource editing beyond a structured fail-closed/manual-required
  result when storage resource metadata is unavailable.

## References

- [docs/decisions/0001-home-assistant-integration-plus-worker.md](../decisions/0001-home-assistant-integration-plus-worker.md)
- [docs/decisions/0005-schema-driven-contracts-and-history-normalization.md](../decisions/0005-schema-driven-contracts-and-history-normalization.md)
- [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../decisions/0008-read-only-mvp-and-sandbox-security.md)
- [docs/decisions/0011-dashboard-card-implementation-technology.md](../decisions/0011-dashboard-card-implementation-technology.md)
- [docs/decisions/0012-worker-transport-and-authentication.md](../decisions/0012-worker-transport-and-authentication.md)
- [docs/decisions/0013-dashboard-resource-auto-registration.md](../decisions/0013-dashboard-resource-auto-registration.md)
- [docs/specs/dashboard-card-spec.md](dashboard-card-spec.md)
- [docs/specs/home-assistant-integration-scaffold-spec.md](home-assistant-integration-scaffold-spec.md)
- Home Assistant Developer Docs: Registering resources
  https://developers.home-assistant.io/docs/frontend/custom-ui/registering-resources/
- Home Assistant Developer Blog: async static path registration
  https://developers.home-assistant.io/blog/2024/06/18/async_register_static_paths/
