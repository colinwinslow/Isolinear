---
status: draft
date: 2026-06-07
depends-on-adrs:
  - 0001
  - 0005
  - 0006
  - 0008
  - 0012
---

# Home Assistant Integration: Config Flow and Options Anchor

## Status

Draft. Defines the first production Home Assistant config-flow and options-flow
surface for the Isolinear custom integration per ADR-0001, ADR-0005,
ADR-0006, ADR-0008, and ADR-0012.

## Related Docs

- [bdd/integration/home-assistant-config-flow-options-bdd.md](../../bdd/integration/home-assistant-config-flow-options-bdd.md) - observable behavior
- [docs/specs/home-assistant-integration-scaffold-spec.md](home-assistant-integration-scaffold-spec.md) - integration package scaffold
- [docs/specs/integration-spec.md](integration-spec.md) - integration responsibilities
- [STATUS.md](../../STATUS.md) - current phase and active work

## Context

The first production integration scaffold is anchored. The next packet needs a
small, inspectable Home Assistant UI setup surface so a user can create an
Isolinear config entry and edit safe options without introducing orchestration,
worker calls, model calls, Home Assistant history access, semantic-memory
storage, token generation, or dashboard resource registration.

## Behavior Contract

The integration must enable Home Assistant config flows by setting
`config_flow: true` in `custom_components/isolinear/manifest.json` and defining
`custom_components/isolinear/config_flow.py`.

The config flow must expose a `user` step that creates a config entry with the
existing local-first config data shape:

- model provider type,
- model endpoint URL,
- planner model name,
- optional codegen model name,
- optional visual validator model name,
- worker endpoint URL.

The options flow must expose an `init` step that persists the existing options
shape:

- default render mode,
- maximum codegen repair attempts,
- entity allowlist.

Both flows must reuse the existing pure `config_schema` validation helpers.
They must reject malformed URLs, unsupported render modes, malformed entity
IDs, duplicate entity IDs, credential-bearing endpoint URLs, forbidden secret
keys, and secret-like values before setup or options persistence continues.

The options flow must expose `entity_allowlist` through a list-style Home
Assistant entity selector that supports multiple selections and stores the
result as an explicit entity ID list. The legacy validator may still normalize
user-facing entity allowlist text into the same validated list shape so live
or older flows remain safe: newline-separated text, comma-separated text, a
single entity ID submitted as the options payload, and JSON-style pasted list
text such as `["sensor.family_room_sensor_temperature"]` must all normalize to
the same deterministic entity ID list before validation. Blank optional model
fields are normalized to `null`.

Stored entity allowlists must redisplay in the options form as a list of entity
IDs for the selector, not as fused text. The legacy text representation must
still include explicit separators between entity IDs. A stored two-entity
allowlist such as
`sensor.family_room_sensor_temperature` plus
`sensor.bathroom_sensor_temperature` must not reopen as fused text like
`sensor.family_room_sensor_temperaturesensor.bathroom_sensor_temperature`;
the selector default and legacy redisplayed value must both round-trip through
the same deterministic allowlist normalizer.

The Home Assistant options-flow factory must retain the config entry that Home
Assistant passes to `async_get_options_flow`, so options validation always has
the existing local-first config-entry data shape available and does not collapse
to a base-level object-shape error while editing the allowlist.

If a live or legacy config entry reaches the options flow with missing stored
setup data, options-only edits must validate against the local-first safe
defaults instead of returning a base-level `must_be_object` error. Explicit
malformed or secret-bearing config-entry data must still fail closed through the
same deterministic validation gate.

The flow anchor must remain non-orchestrating. It must not call the worker,
model provider, Home Assistant history APIs, semantic-memory storage helpers,
Home Assistant services, or Home Assistant mutation APIs.

## Anchor Artifact

The anchor artifact is the inspectable
`custom_components/isolinear/config_flow.py` module plus
`src/Isolinear/config_flow_anchor.py`, which verifies manifest config-flow
activation, flow field metadata, valid config-entry creation data, valid
options data, invalid-input rejection, and non-orchestration behavior.

## Implementation Order

1. Create this spec and its paired BDD/evidence scaffold.
2. Add failing unit tests for manifest activation, config flow data creation,
   options normalization, invalid-input rejection, and non-orchestration.
3. Add `custom_components/isolinear/config_flow.py` and update the manifest.
4. Add the Python verifier anchor and focused executable eval.
5. Verify the real files on disk.

## Proof Requirements

1. Unit tests in `tests/test_config_flow_options_anchor.py` are green.
2. `evals/home_assistant_config_flow_options.py` emits raw `CASE` evidence for
   the BDD scenarios.
3. The manifest enables config flows and `config_flow.py` exists on disk.
4. Valid config-flow input produces the validated config-entry data shape.
5. Valid options-flow input produces the validated options data shape with a
   deterministic entity allowlist.
6. Live-reported allowlist inputs for
   `sensor.family_room_sensor_temperature` normalize from both plain entity
   text and JSON-style pasted list text, two-entity JSON-style pasted list text
   normalizes to both entity IDs, the options form advertises a multi-entity
   selector whose default is the stored entity list, legacy text defaults still
   redisplay with a separator and round-trip without fused IDs, and the options
   flow uses the passed config entry while creating the updated options entry.
   A live/legacy config entry with missing stored setup data also accepts the
   same allowlist edit without returning base-level `must_be_object`.
7. Invalid and secret-bearing config/options inputs fail closed with structured
   field errors.
8. Evidence confirms no worker, model-provider, Home Assistant history,
   semantic-memory, service-mutation, token-generation, or dashboard-resource
   registration calls occur in this packet.

## Non-Goals

- Worker token generation, rotation, storage, or repair UI.
- Worker health checks or readiness validation.
- Dashboard resource auto-registration.
- Home Assistant history access or entity catalog construction.
- Model-provider calls.
- Semantic-memory persistence.
- Job orchestration, subscriptions, streaming, retries, or artifact storage.
- Reconfigure, reauth, YAML import, migrations, or config-entry repair flows.
- Creating or mutating Home Assistant devices, services, automations, scenes,
  helpers, or configuration outside the config entry/options created by this
  flow.

## References

- [docs/decisions/0001-home-assistant-integration-plus-worker.md](../decisions/0001-home-assistant-integration-plus-worker.md)
- [docs/decisions/0005-schema-driven-contracts-and-history-normalization.md](../decisions/0005-schema-driven-contracts-and-history-normalization.md)
- [docs/decisions/0006-validation-and-repair-loop.md](../decisions/0006-validation-and-repair-loop.md)
- [docs/decisions/0008-read-only-mvp-and-sandbox-security.md](../decisions/0008-read-only-mvp-and-sandbox-security.md)
- [docs/decisions/0012-worker-transport-and-authentication.md](../decisions/0012-worker-transport-and-authentication.md)
- [docs/specs/home-assistant-integration-scaffold-spec.md](home-assistant-integration-scaffold-spec.md)
- [docs/specs/integration-spec.md](integration-spec.md)
