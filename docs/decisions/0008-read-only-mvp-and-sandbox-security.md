# ADR 0008: Read-only MVP and sandbox security

## Status

Accepted

## Context

The product reads Home Assistant history and creates visualization artifacts. It does not need to control devices, update automations, or mutate Home Assistant state. Generated code is especially sensitive because user prompts influence it.

## Decision

The MVP is read-only with respect to Home Assistant. It may read approved entity metadata and history. It may create chart artifacts owned by the integration. It must not call arbitrary Home Assistant services or modify devices.

Sandboxed generated code must run without:

- Home Assistant token.
- Network access.
- Secrets access.
- Arbitrary filesystem read access.
- Arbitrary filesystem write access.

## Consequences

Positive:

- Limits blast radius.
- Easier to explain to users.
- Simplifies security review.

Negative:

- The product cannot create automations or control devices in the MVP.
- Some advanced workflows will be out of scope.
- Sandbox enforcement must be maintained across platforms.
