# Semantic Memory Spec

## Purpose

Semantic memory stores user-confirmed mappings from natural-language concepts to entities, aggregates, thresholds, or other derived meanings.

## Principle

Memory is product-owned, not model-owned. The model may propose memory, but the integration decides what to save, and only after user confirmation.

## Memory examples

### Aggregate alias

`upstairs temperature` may mean the mean of three approved upstairs temperature sensors.

### Threshold interval alias

`dishwasher running` may mean `sensor.dishwasher_power > 5 W`.

### State interval alias

`AC running` may mean `binary_sensor.air_conditioning == on`.

## Save policy

The card should offer:

- Use once.
- Use and remember.

Saved memory should include:

- Alias ID.
- Natural names.
- Meaning.
- Source entities.
- Confirmation source.
- Created timestamp.
- Last used timestamp.

## Read policy

The integration injects relevant semantic aliases into each planning prompt. The model does not read memory files directly.

## Update policy

If a saved alias references entities that are no longer approved or no longer exist, the alias should be marked invalid and not used without user repair.

## Delete policy

Users must be able to delete saved semantic aliases through integration options or a future memory-management UI.
