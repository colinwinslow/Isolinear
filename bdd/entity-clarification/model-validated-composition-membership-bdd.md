# Composition membership: model-validated entity set — BDD

## Status

Accepted. Paired with
[docs/specs/model-validated-composition-membership.md](../../docs/specs/model-validated-composition-membership.md)
(ADR-0028). Evidence:
[model-validated-composition-membership-evidence.md](model-validated-composition-membership-evidence.md).

## Why this BDD exists

When a fuzzy prompt matches several approved entities, the integration must compose
only the entities the user actually asked about. Today it composes any binary match
plus whatever numeric matched, so an entity that hit only a shared location word
("kitchen") is wrongly included — which makes the planner clarify instead of chart.
These scenarios pin down that the model prunes those noise matches before render
family is chosen, while genuine ambiguity still clarifies and the safety boundary
holds.

## Scenarios

### Scenario A — happy path: subject is a binary entity, numeric noise match pruned

**Given** an approved catalog with `sensor.kitchen_ecobee_temperature` (numeric) and
`binary_sensor.kitchen_door` (binary), both matching the shared token "kitchen"
**And** the prompt "when was the kitchen door open today" (distinctive token "door"
present only for the door)
**When** entity selection runs and diverts the multi-match composition candidate to
the model validation pass
**Then** the model returns membership `["binary_sensor.kitchen_door"]`, the
temperature sensor is pruned as a noise match
**And** `_resolve_render_family` derives family `timeline`
**And** the planner is disclosed only the door and returns `chart_spec_ready` (no
clarification).

### Scenario B — happy path: numeric primary + intentional overlay, binary noise match pruned

**Given** an approved catalog with `sensor.kitchen_ecobee_temperature` (numeric),
`binary_sensor.kitchen_door` (binary), and `climate.kitchen_ecobee` (categorical)
**And** the prompt "show kitchen temp and when the AC was running" — "temp" is
distinctive for the temperature sensor, "AC" maps to the climate domain synonym, and
"kitchen" is the only token the door matched
**When** the composition candidate is validated by the model
**Then** the model returns membership
`["sensor.kitchen_ecobee_temperature", "climate.kitchen_ecobee"]`, dropping
`binary_sensor.kitchen_door`
**And** `_resolve_render_family` derives `time_series_overlay` (temperature line +
climate overlay)
**And** the planner (disclosed the numeric primary, AC in `overlay_entity_ids`)
returns `chart_spec_ready` with an `overlay_labels` entry for the climate entity.

### Scenario C — gate skips the prune when candidates share no token

**Given** an approved catalog with `sensor.kitchen_ecobee_temperature` (numeric) and
`binary_sensor.front_door` (binary)
**And** the prompt "kitchen temperature and the front door" — the temperature matches
on "kitchen"/"temperature" and the door matches on "front"/"door", with no shared
token between them
**When** the composition is formed
**Then** the ADR-0028 gate does not fire (no noise to prune), no `select_entity`
round-trip is made, and the deterministic composition
`["sensor.kitchen_ecobee_temperature", "binary_sensor.front_door"]` is kept verbatim
(the user named both distinctly).
**And** explicit-entity-id and single-match selections likewise never enter the prune
pass (it is scoped to the `numeric_with_overlay` source).

### Scenario D — genuine ambiguity still clarifies

**Given** an approved catalog with two equally-specified same-kind entities (e.g.
`climate.upstairs_thermostat` and `climate.downstairs_thermostat`)
**And** the prompt "show thermostat history" (matches both only on "thermostat", no
distinguishing subject)
**When** the composition/selection pass runs and the model cannot pick a unique
subject (abstains or returns both as co-equal)
**Then** the clarification card is shown listing the candidates — pruning removes
noise, never genuine ambiguity.

### Scenario E — safety: out-of-catalog model id fails closed

**Given** the model validation pass returns a membership list containing an
`entity_id` not present in the approved catalog
**When** the returned set is validated post-prune
**Then** the out-of-set id is rejected and the job fails closed (allowlist boundary
preserved, invariant #1) rather than disclosing or charting it.

## Evidence

The implementing slice produces an evidence file at
`bdd/entity-clarification/model-validated-composition-membership-evidence.md`
containing raw resolved-set outputs (the disclosed candidate payload, the model
membership response, the pruned set, and the resolved family) for each scenario —
not "✓ passed" summaries.
