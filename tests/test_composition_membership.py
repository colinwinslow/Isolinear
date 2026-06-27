"""Tests for ADR-0028: model-validated composition membership.

The deterministic matcher composes any numeric + state entity sharing a prompt
token, so an entity matched only on a shared location word ("kitchen") can enter the
overlay set and break planning. These tests cover the prune pass that routes the
composition candidate set through the D2 model selector before render-family routing:

  - gate fires + prune drops the noise match (door prompt → timeline; temp+AC → overlay)
  - the pruned set re-routes through _resolve_render_family by kind (invariant #9)
  - model abstain / provider failure / out-of-allowlist id → deterministic composition stands
  - no shared token among candidates → no model call (gate skips)
  - the prune pass is scoped to the numeric_with_overlay source
"""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from custom_components.isolinear.const import DOMAIN  # noqa: E402
from custom_components.isolinear.model_provider import DATA_MODEL_PROVIDER_PLANNER  # noqa: E402
from custom_components.isolinear.job_orchestration import (  # noqa: E402
    _composition_has_shared_token,
    _resolve_entity_selection_with_model,
    _resolve_render_family,
    select_prompt_entity_ids,
)

ENTRY_ID = "entry-1"

# Catalog mirrors the live kitchen allowlist that surfaced the bug.
KITCHEN_TEMP = {
    "entity_id": "sensor.kitchen_ecobee_temperature",
    "domain": "sensor",
    "friendly_name": "Kitchen Temperature",
    "state_class": "measurement",
    "device_class": "temperature",
}
KITCHEN_DOOR = {
    "entity_id": "binary_sensor.kitchen_door",
    "domain": "binary_sensor",
    "friendly_name": "Kitchen Door",
}
KITCHEN_AC = {
    "entity_id": "climate.kitchen_ecobee",
    "domain": "climate",
    "friendly_name": "Kitchen ecobee",
}
FRONT_DOOR = {
    "entity_id": "binary_sensor.front_door",
    "domain": "binary_sensor",
    "friendly_name": "Front Door",
}


class _FakePlanner:
    """Stub planner exposing select_entity; records calls and returns a scripted set."""

    def __init__(self, returned_ids, *, status="entity_selected"):
        self._returned_ids = returned_ids
        self._status = status
        self.calls = 0

    def select_entity(self, request, *, result_schema=None, on_reasoning=None):
        self.calls += 1
        self.last_request = request
        if self._returned_ids is None:
            return {"accepted": False, "code": "provider_failure"}
        return {
            "accepted": True,
            "selection_result": {"status": self._status, "entity_ids": self._returned_ids},
        }


def _hass(planner=None):
    data = {DOMAIN: {ENTRY_ID: {}}}
    if planner is not None:
        data[DOMAIN][ENTRY_ID][DATA_MODEL_PROVIDER_PLANNER] = planner
    return type("Hass", (), {"data": data})()


def _resolve(prompt, catalog, planner):
    selection = select_prompt_entity_ids(prompt, catalog)
    return selection, _resolve_entity_selection_with_model(
        _hass(planner), ENTRY_ID, prompt, catalog, selection
    )


class CompositionPruneTests(unittest.TestCase):
    def test_door_prompt_prunes_temp_and_routes_to_timeline(self):
        catalog = [KITCHEN_TEMP, KITCHEN_DOOR]
        prompt = "when was the kitchen door open today"
        planner = _FakePlanner(["binary_sensor.kitchen_door"])
        selection, resolved = _resolve(prompt, catalog, planner)

        # D1 over-composed the temperature sensor as the primary.
        self.assertEqual(selection["source"], "numeric_with_overlay")
        self.assertIn("sensor.kitchen_ecobee_temperature", selection["entity_ids"])
        # The prune drops it; the door is the sole resolved entity.
        self.assertEqual(planner.calls, 1)
        self.assertEqual(resolved["entity_ids"], ["binary_sensor.kitchen_door"])
        self.assertEqual(resolved["source"], "model_entity_selection")
        # Deterministic routing now yields a timeline, not an overlay.
        routing = _resolve_render_family(catalog, resolved["entity_ids"])
        self.assertEqual(routing["family"], "timeline")

    def test_temp_ac_prompt_prunes_spurious_door_and_keeps_overlay(self):
        catalog = [KITCHEN_TEMP, KITCHEN_DOOR, KITCHEN_AC]
        prompt = "show kitchen temp and when the AC was running"
        planner = _FakePlanner(
            ["sensor.kitchen_ecobee_temperature", "climate.kitchen_ecobee"]
        )
        selection, resolved = _resolve(prompt, catalog, planner)

        # D1 composed the spurious kitchen_door overlay.
        self.assertEqual(selection["source"], "numeric_with_overlay")
        self.assertIn("binary_sensor.kitchen_door", selection["entity_ids"])
        # The prune drops the door, keeps temp + climate.
        self.assertEqual(
            set(resolved["entity_ids"]),
            {"sensor.kitchen_ecobee_temperature", "climate.kitchen_ecobee"},
        )
        routing = _resolve_render_family(catalog, resolved["entity_ids"])
        self.assertEqual(routing["family"], "time_series_overlay")

    def test_model_abstain_keeps_deterministic_composition(self):
        catalog = [KITCHEN_TEMP, KITCHEN_DOOR]
        prompt = "when was the kitchen door open today"
        planner = _FakePlanner(None, status="clarification_needed")  # provider failure
        selection, resolved = _resolve(prompt, catalog, planner)
        self.assertEqual(planner.calls, 1)
        self.assertEqual(resolved["entity_ids"], selection["entity_ids"])
        self.assertEqual(resolved["source"], "numeric_with_overlay")

    def test_out_of_allowlist_model_id_fails_closed_to_composition(self):
        catalog = [KITCHEN_TEMP, KITCHEN_DOOR]
        prompt = "when was the kitchen door open today"
        planner = _FakePlanner(["binary_sensor.not_approved"])
        selection, resolved = _resolve(prompt, catalog, planner)
        # Off-set id is rejected by _run_model_entity_selection; composition stands.
        self.assertEqual(resolved["entity_ids"], selection["entity_ids"])
        self.assertEqual(resolved["source"], "numeric_with_overlay")

    def test_no_shared_token_skips_model_call(self):
        catalog = [KITCHEN_TEMP, FRONT_DOOR]
        prompt = "kitchen temperature and the front door"
        planner = _FakePlanner(["binary_sensor.front_door"])  # would prune if called
        selection, resolved = _resolve(prompt, catalog, planner)
        self.assertEqual(selection["source"], "numeric_with_overlay")
        self.assertEqual(planner.calls, 0)  # gate skipped the prune
        self.assertEqual(resolved["entity_ids"], selection["entity_ids"])

    def test_no_planner_keeps_composition(self):
        catalog = [KITCHEN_TEMP, KITCHEN_DOOR]
        prompt = "when was the kitchen door open today"
        selection = select_prompt_entity_ids(prompt, catalog)
        resolved = _resolve_entity_selection_with_model(
            _hass(planner=None), ENTRY_ID, prompt, catalog, selection
        )
        self.assertEqual(resolved["entity_ids"], selection["entity_ids"])
        self.assertEqual(resolved["source"], "numeric_with_overlay")

    def test_identical_model_result_keeps_composition_source(self):
        # Model confirms the whole composition (genuine multi-concept) → unchanged.
        catalog = [KITCHEN_TEMP, KITCHEN_AC]
        prompt = "show kitchen temp and when the AC was running"
        selection = select_prompt_entity_ids(prompt, catalog)
        planner = _FakePlanner(list(selection["entity_ids"]))
        resolved = _resolve_entity_selection_with_model(
            _hass(planner), ENTRY_ID, prompt, catalog, selection
        )
        self.assertEqual(set(resolved["entity_ids"]), set(selection["entity_ids"]))
        self.assertEqual(resolved["source"], "numeric_with_overlay")


class SharedTokenGateTests(unittest.TestCase):
    def test_shared_location_token_detected(self):
        self.assertTrue(
            _composition_has_shared_token(
                "when was the kitchen door open today", [KITCHEN_TEMP, KITCHEN_DOOR]
            )
        )

    def test_distinct_tokens_not_shared(self):
        self.assertFalse(
            _composition_has_shared_token(
                "kitchen temperature and the front door", [KITCHEN_TEMP, FRONT_DOOR]
            )
        )


if __name__ == "__main__":
    unittest.main()
