---
id: 0013
title: Dashboard resource auto-registration
status: accepted
date: 2026-06-08
supersedes: []
superseded-by: null
tags:
  - dashboard-resource
  - frontend
  - home-assistant
---

# ADR-0013: Dashboard resource auto-registration

## Context

ADR-0011 chooses a TypeScript Lit dashboard card loaded as a Home Assistant
dashboard resource, but it intentionally leaves open whether users must add the
resource manually or the integration can register it. The production
integration scaffold and config-flow/options surface now exist, so the next
packet needs the smallest real delivery path for the checked-in
`isolinear-card` bundle. Home Assistant custom cards must be served to the
frontend and registered as dashboard resources before dashboards can load
`type: custom:isolinear-card`.

## Decision

**The Isolinear integration will auto-register its dashboard card resource
during config-entry setup by serving the checked-in bundle from an
integration-owned static path and creating or reusing one Lovelace module
resource metadata record.**

The integration will use `/api/isolinear/static/isolinear-card.js` as the
resource URL and `module` as the resource type. Registration is idempotent and
fails closed before metadata creation if the bundle is missing or Home
Assistant's storage-backed resource collection is unavailable.

## Rationale

- Auto-registration avoids requiring the user to copy the bundle into
  `/config/www` or manually edit dashboard resources after installing the
  integration.
- The integration already owns the card-facing WebSocket boundary, so it is the
  right place to make the card module loadable while keeping card
  configuration separate from worker and model settings.
- Home Assistant's async static-path API provides the current non-blocking
  serving mechanism for integration-hosted assets.
- Reusing existing resource metadata preserves user installations that already
  added the same module URL and keeps repeated setup idempotent.

## Consequences

**Enables:**

- A config-entry setup path that makes `custom:isolinear-card` loadable without
  manual dashboard resource setup.
- Focused proof that dashboard resource metadata is the only Home Assistant
  metadata write in this packet.

**Constrains:**

- The integration must treat Lovelace resource metadata writes as a narrow
  allowed exception to the read-only MVP, distinct from service, state, device,
  automation, scene, helper, or configuration mutation.
- The integration must not delete the resource on config-entry unload until a
  later lifecycle spec decides ownership and multi-entry behavior.
- YAML-mode or unavailable resource storage must fail closed or require manual
  setup instead of editing YAML files.

**Open:**

- Packaging may later move the built card bundle under the custom integration
  directory; this ADR only decides the registration behavior and resource URL.
- Whether a future repair flow should surface manual resource instructions when
  storage-backed resource registration is unavailable.

## References

- ADR-0001: Home Assistant integration plus isolated worker
- ADR-0008: Read-only MVP and sandbox security
- ADR-0011: Dashboard card implementation technology
- ADR-0012: Worker transport and authentication
- `docs/specs/home-assistant-dashboard-resource-registration-spec.md`
- Home Assistant Developer Docs: Registering resources
  https://developers.home-assistant.io/docs/frontend/custom-ui/registering-resources/
- Home Assistant Developer Blog: async static path registration
  https://developers.home-assistant.io/blog/2024/06/18/async_register_static_paths/
