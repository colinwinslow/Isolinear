"""Eval: ADR-0028 model-validated composition membership.

Proves the deterministic wiring of the overlay-composition prune pass: given a model
that returns a pruned subset, the composition resolves to that subset and re-routes
through `_resolve_render_family` by entity kind (invariant #9). The gate skips the
model when candidates share no token. The model's actual pruning *judgment* against
the live planner is captured separately in the BDD evidence file (raw outputs).

No live model or recorder is required — a scripted planner stub stands in for D2.
Emits CASE evidence.
"""

import sys
from pathlib import Path

from evidence import print_case

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from custom_components.isolinear.const import DOMAIN  # noqa: E402
from custom_components.isolinear.model_provider import DATA_MODEL_PROVIDER_PLANNER  # noqa: E402
from custom_components.isolinear.job_orchestration import (  # noqa: E402
    _resolve_entity_selection_with_model,
    _resolve_render_family,
    select_prompt_entity_ids,
)

ENTRY_ID = "entry-eval"

KITCHEN_TEMP = {
    "entity_id": "sensor.kitchen_ecobee_temperature", "domain": "sensor",
    "friendly_name": "Kitchen Temperature", "state_class": "measurement",
    "device_class": "temperature",
}
KITCHEN_DOOR = {
    "entity_id": "binary_sensor.kitchen_door", "domain": "binary_sensor",
    "friendly_name": "Kitchen Door",
}
KITCHEN_AC = {
    "entity_id": "climate.kitchen_ecobee", "domain": "climate",
    "friendly_name": "Kitchen ecobee",
}
FRONT_DOOR = {
    "entity_id": "binary_sensor.front_door", "domain": "binary_sensor",
    "friendly_name": "Front Door",
}


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Expected {expected!r} but got {actual!r}.")


class _ScriptedPlanner:
    def __init__(self, returned_ids):
        self._returned_ids = returned_ids
        self.calls = 0

    def select_entity(self, request, *, result_schema=None, on_reasoning=None):
        self.calls += 1
        return {
            "accepted": True,
            "selection_result": {"status": "entity_selected", "entity_ids": self._returned_ids},
        }


def _hass(planner):
    data = {DOMAIN: {ENTRY_ID: {}}}
    if planner is not None:
        data[DOMAIN][ENTRY_ID][DATA_MODEL_PROVIDER_PLANNER] = planner
    return type("Hass", (), {"data": data})()


def main():
    # CASE 1 — door prompt: temperature noise match pruned -> timeline.
    catalog = [KITCHEN_TEMP, KITCHEN_DOOR]
    prompt = "when was the kitchen door open today"
    selection = select_prompt_entity_ids(prompt, catalog)
    planner = _ScriptedPlanner(["binary_sensor.kitchen_door"])
    resolved = _resolve_entity_selection_with_model(_hass(planner), ENTRY_ID, prompt, catalog, selection)
    family = _resolve_render_family(catalog, resolved["entity_ids"])["family"]
    assert_equal(selection["source"], "numeric_with_overlay", "D1 over-composes.")
    assert_equal(resolved["entity_ids"], ["binary_sensor.kitchen_door"], "Temp pruned.")
    assert_equal(family, "timeline", "Pruned single binary routes to timeline.")
    print_case(
        "composition_prune_door_to_timeline",
        given={"prompt": prompt, "catalog": [c["entity_id"] for c in catalog]},
        when={"d1_source": selection["source"], "d1_set": selection["entity_ids"],
              "model_returns": ["binary_sensor.kitchen_door"]},
        then={"resolved_set": resolved["entity_ids"], "resolved_source": resolved["source"],
              "render_family": family, "model_calls": planner.calls},
    )

    # CASE 2 — temp+AC prompt: spurious door overlay pruned -> overlay kept.
    catalog = [KITCHEN_TEMP, KITCHEN_DOOR, KITCHEN_AC]
    prompt = "show kitchen temp and when the AC was running"
    selection = select_prompt_entity_ids(prompt, catalog)
    planner = _ScriptedPlanner(["sensor.kitchen_ecobee_temperature", "climate.kitchen_ecobee"])
    resolved = _resolve_entity_selection_with_model(_hass(planner), ENTRY_ID, prompt, catalog, selection)
    family = _resolve_render_family(catalog, resolved["entity_ids"])["family"]
    assert_equal("binary_sensor.kitchen_door" in selection["entity_ids"], True, "D1 adds spurious door.")
    assert_equal("binary_sensor.kitchen_door" in resolved["entity_ids"], False, "Door pruned.")
    assert_equal(family, "time_series_overlay", "Temp + climate routes to overlay.")
    print_case(
        "composition_prune_keeps_overlay",
        given={"prompt": prompt, "catalog": [c["entity_id"] for c in catalog]},
        when={"d1_set": selection["entity_ids"],
              "model_returns": ["sensor.kitchen_ecobee_temperature", "climate.kitchen_ecobee"]},
        then={"resolved_set": sorted(resolved["entity_ids"]), "render_family": family,
              "model_calls": planner.calls},
    )

    # CASE 3 — no shared token: gate skips the model entirely.
    catalog = [KITCHEN_TEMP, FRONT_DOOR]
    prompt = "kitchen temperature and the front door"
    selection = select_prompt_entity_ids(prompt, catalog)
    planner = _ScriptedPlanner(["binary_sensor.front_door"])  # would prune if ever called
    resolved = _resolve_entity_selection_with_model(_hass(planner), ENTRY_ID, prompt, catalog, selection)
    assert_equal(planner.calls, 0, "Gate skips the model when no token is shared.")
    assert_equal(set(resolved["entity_ids"]), set(selection["entity_ids"]), "Composition kept verbatim.")
    print_case(
        "composition_gate_skips_distinct_tokens",
        given={"prompt": prompt, "catalog": [c["entity_id"] for c in catalog]},
        when={"d1_set": selection["entity_ids"]},
        then={"resolved_set": sorted(resolved["entity_ids"]), "model_calls": planner.calls},
    )

    print("PASS composition_membership_prune")


if __name__ == "__main__":
    main()
