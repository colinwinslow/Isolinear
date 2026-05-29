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

- If exactly one strong mapping exists, use it.
- If multiple strong mappings exist and the choice changes meaning, ask a clarifying question.
- If multiple compatible numeric entities share the requested semantic meaning, propose an aggregate and ask.
- If a continuous sensor appears to represent an on/off state, propose a threshold and ask unless a saved rule exists.
- If no reasonable mapping exists, ask the user to select an entity or update the allowlist/labels.

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
