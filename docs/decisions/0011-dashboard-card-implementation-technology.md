---
id: 0011
title: Dashboard card implementation technology
status: accepted
date: 2026-06-01
supersedes: []
superseded-by: null
tags:
  - dashboard-card
  - frontend
  - home-assistant
---

# ADR-0011: Dashboard card implementation technology

## Context

ADR-0002 chooses a Home Assistant dashboard card as the first Isolinear UI, but
the implementation technology was intentionally left open. The next UI slice
needs a concrete frontend surface that can render prompt entry, clarification,
job progress, chart results, validation status, and failure details without
pulling orchestration or durable state out of the Home Assistant integration.

Home Assistant custom cards are custom elements loaded as JavaScript module
resources. The platform calls card lifecycle hooks such as `setConfig`, passes
Home Assistant data through the frontend context, and supports sizing and
graphical configuration hooks. Home Assistant also lets integrations expose
custom WebSocket commands to the frontend, and recent guidance requires async
static path registration for integration-hosted frontend assets.

The MVP card must preserve the existing safety boundaries: the worker never
receives a Home Assistant token, semantic memory remains integration-owned, and
the UI must not bypass entity allowlist validation or call Home Assistant
mutation services.

## Decision

**Implement the MVP dashboard UI as a TypeScript Lit custom card named
`isolinear-card`, bundled as an ES module and loaded as a Home Assistant
dashboard resource. The card communicates only with integration-owned,
versioned Home Assistant WebSocket commands and never calls the worker, model
provider, Home Assistant history APIs, semantic-memory storage, or browser
local storage directly.**

The card module must define:

- A custom element used as `type: custom:isolinear-card`.
- A graphical configuration surface through Home Assistant custom-card hooks,
  limited to selecting the Isolinear config entry and display defaults.
- Card sizing hooks for masonry and sections dashboards.
- Card picker metadata in `window.customCards`.
- A small API adapter boundary for Isolinear WebSocket commands, so UI tests can
  run against a fake Home Assistant object before the integration exists.

The eventual Home Assistant integration should serve the built card asset from
an integration-owned static path registered with
`hass.http.async_register_static_paths`. The JavaScript bundle must contain no
tokens, secrets, worker credentials, entity allowlist contents, raw history,
generated images, generated code, or semantic-memory records.

Until the integration scaffold exists, the first anchor artifact should be a
standalone browser-testable card shell that imports the bundled module, renders
against a fake `hass` object, and records the Isolinear WebSocket calls it would
make.

## Rationale

- Custom elements are the native Home Assistant custom-card extension point,
  so the card can live inside existing dashboards instead of introducing a full
  panel or separate application.
- Lit keeps the runtime model close to web components while providing a small,
  typed rendering layer suitable for a multi-state interactive card.
- TypeScript makes the UI state machine, card config, and integration adapter
  contracts explicit before Home Assistant integration code exists.
- Home Assistant custom WebSocket commands keep prompt submission, job state,
  memory writes, allowlist filtering, history retrieval, and artifact ownership
  in the integration, preserving ADR-0001, ADR-0008, and ADR-0009.
- A fake-`hass` browser harness gives the project an inspectable anchor artifact
  before full Home Assistant setup, while still proving the card is a real
  custom element rather than a paper mockup.

## Consequences

**Enables:**

- A narrow first UI implementation slice: register and render the card shell,
  submit a prompt through a fake Isolinear WebSocket adapter, and display a
  deterministic job snapshot.
- Frontend tests that verify custom-element registration, Home Assistant card
  hooks, and the no-direct-worker/no-local-storage boundary.
- Later integration-hosted delivery without asking users to copy runtime files
  into Home Assistant's `/config/www` directory.

**Constrains:**

- The repository will need a frontend build/test toolchain for the card, used
  only to produce the dashboard resource bundle.
- The card is a thin client: durable job state, memory, entity visibility,
  history access, and chart artifacts remain integration-owned.
- Card configuration must not store secrets, worker endpoints, model endpoints,
  raw entity history, generated code, generated images, or semantic aliases.
- Private Home Assistant frontend internals are not a stable dependency surface;
  the card should prefer documented custom-card hooks, web standards, and
  Home Assistant theme variables.

**Open:**

- Exact Isolinear WebSocket command schemas for job start, clarification answer,
  retry, snapshot retrieval, and subscription.
- Exact source and bundle paths once the Home Assistant integration scaffold is
  created.
- Whether the integration can auto-register the dashboard resource for the MVP
  or the user must add the resource manually.

## Rejected alternatives

### React, Vue, Svelte, or a bundled SPA

Rejected for the MVP because the card needs a small Home Assistant-native
custom element, not an application shell. React also adds custom-element
compatibility friction relative to Lit for this use case.

### Full custom panel first

Rejected because ADR-0002 intentionally chooses a dashboard card before a full
custom panel. A panel would expand routing, navigation, and layout concerns
before the prompt-to-chart UI is proven.

### Browser local storage for job state or memory

Rejected because ADR-0009 makes semantic memory integration-owned and
auditable, and because job state must survive card rerenders without becoming a
browser-specific source of truth.

### Direct worker, model-provider, or history API calls from the card

Rejected because those calls would bypass integration-owned allowlist,
validation, memory, artifact, and security boundaries.

## References

- ADR-0001: Home Assistant integration plus isolated worker
- ADR-0002: Dashboard card as the first user interface
- ADR-0008: Read-only MVP and sandbox security
- ADR-0009: Semantic memory storage
- `docs/specs/dashboard-card-spec.md`
- `docs/specs/integration-spec.md`
- `bdd/dashboard-card/custom-card-anchor-bdd.md`
- Home Assistant Developer Docs: Custom card
  https://developers.home-assistant.io/docs/frontend/custom-ui/custom-card/
- Home Assistant Developer Docs: Registering resources
  https://developers.home-assistant.io/docs/frontend/custom-ui/registering-resources/
- Home Assistant Developer Docs: Extending the WebSocket API
  https://developers.home-assistant.io/docs/frontend/extending/websocket-api/
- Home Assistant Developer Blog: async static path registration
  https://developers.home-assistant.io/blog/2024/06/18/async_register_static_paths/
