# Entity Resolution Spec

## Purpose

Entity resolution maps a user's natural-language prompt to approved Home Assistant entities, semantic aliases, transformations, and chart roles.

## Inputs

- User prompt.
- Approved entity catalog.
- Current Home Assistant metadata for approved entities.
- User-confirmed semantic aliases.
- User clarification answers.

## Resolution signals

The resolver may use:

- `entity_id`
- friendly name
- domain
- device class
- state class
- unit of measurement
- area
- labels
- device name
- integration name
- current state
- saved semantic aliases

## Resolution behavior

The resolver should identify:

- Requested systems or concepts.
- Areas or locations.
- Measurements.
- Time ranges.
- Comparison targets.
- Aggregations.
- Overlays or event intervals.
- Candidate entities.
- Confidence and ambiguity.

## Clarification policy

Resolution uses a three-stage pipeline (ADR-0024):

1. **Deterministic fast-path (D1)** — score each approved entity by how many
   of its distinctive tokens the prompt contains. Select the uniquely
   top-scoring entity without clarification. A top-score tie or zero matches
   falls through to stage 2.

2. **Model-driven selection (D2)** — when stage 1 cannot resolve and a model
   provider is configured, ask the model to pick the entity (or entity set)
   from the approved candidates. The model returns either a chosen set or an
   explicit `clarification_needed`. Chosen entity IDs must be in the approved
   catalog; any off-allowlist choice fails closed and falls through to stage 3.
   When no model provider is configured, skip directly to stage 3.

3. **User clarification (D3 fallback)** — show the user a clarification card
   when neither the fast-path nor the model can resolve. For a tie, offer only
   the tied candidates. For zero matches, offer the full catalog.

Additional rules:
- If multiple compatible numeric entities share the requested semantic meaning, propose an aggregate and ask.
- If a continuous sensor appears to represent an on/off state, propose a threshold and ask unless a saved rule exists.
- If no reasonable mapping exists, ask the user to select an entity or update the allowlist/labels.

The allowlist boundary is absolute at every stage (ADR-0003, ADR-0008). The
model proposes; the integration disposes.

## Examples

### Multiple temperature sensors

Prompt:

> Compare upstairs temperature and downstairs temperature.

If three approved upstairs temperature sensors match, ask whether to average them.

### Continuous sensor as running interval

Prompt:

> Mark when the dishwasher was running.

If only `sensor.dishwasher_power` is available, propose a threshold-derived interval and ask for confirmation.

### Multiple running indicators

Prompt:

> Show when the air conditioning was running.

If `binary_sensor.air_conditioning`, `sensor.hvac_current`, and `climate.main_floor` are all plausible, ask which representation to use.
