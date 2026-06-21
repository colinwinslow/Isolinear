import sys
import unittest
from copy import deepcopy
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from custom_components.isolinear.job_orchestration import (  # noqa: E402
    validate_model_provider_chart_spec_entities,
    validate_model_provider_output_entities,
)


SOURCE_SNAPSHOT = {"entities": [{"entity_id": "binary_sensor.kitchen_door"}]}


def _timeline_spec(chart_id: str = "binary_sensor.kitchen_door_timeline") -> dict:
    return {
        "chart_id": chart_id,
        "chart_type": "timeline",
        "title": "Kitchen Door",
        "time_range": {"type": "absolute", "start": "2026-06-20T00:00:00Z", "end": "2026-06-20T17:49:43Z"},
        "series": [
            {
                "series_id": "binary_sensor.kitchen_door",
                "label": "Kitchen Door",
                "source": {"type": "entity", "entity_id": "binary_sensor.kitchen_door", "attribute": None},
                "role": "primary",
                "render_as": "step",
                "transform": {"operation": "none", "window": None},
                "unit": None,
            }
        ],
        "overlays": [],
        "x_axis": {"type": "time"},
        "y_axis": {},
    }


class ProviderOutputEntityGateTests(unittest.TestCase):
    def test_chart_id_named_after_entity_is_not_a_reference(self):
        """Regression: a small model naming its timeline after the entity
        (``binary_sensor.kitchen_door_timeline``) must not be mistaken for an
        off-allowlist entity reference (the live 0.1.27 failure)."""
        result = validate_model_provider_chart_spec_entities(_timeline_spec(), SOURCE_SNAPSHOT)
        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["code"], "accepted")

    def test_entity_shaped_tokens_in_inert_fields_are_ignored(self):
        spec = _timeline_spec()
        spec["title"] = "Compared with sensor.secret_temperature"
        spec["notes"] = ["The model mentioned sensor.secret_temperature."]
        spec["x_axis"] = {"type": "time", "entity_id": "sensor.secret_temperature"}
        spec["y_axis"] = {"entity_id": "sensor.secret_temperature"}
        result = validate_model_provider_chart_spec_entities(spec, SOURCE_SNAPSHOT)
        self.assertTrue(result["accepted"], result)

    def test_reasoning_summary_mention_is_ignored(self):
        planner_result = {
            "status": "chart_spec_ready",
            "chart_spec": _timeline_spec(),
            "reasoning_summary": "The hidden sensor.secret_temperature seemed relevant.",
            "memory_proposals": [],
        }
        result = validate_model_provider_output_entities(
            planner_result, planner_result["chart_spec"], SOURCE_SNAPSHOT
        )
        self.assertTrue(result["accepted"], result)

    def test_off_allowlist_entity_in_memory_proposal_is_rejected(self):
        planner_result = {
            "status": "chart_spec_ready",
            "chart_spec": _timeline_spec(),
            "memory_proposals": [{"alias_id": "hidden", "entity_id": "sensor.secret_temperature"}],
        }
        result = validate_model_provider_output_entities(
            planner_result, planner_result["chart_spec"], SOURCE_SNAPSHOT
        )
        self.assertFalse(result["accepted"], result)
        self.assertEqual(result["code"], "model_provider_referenced_unapproved_entity")
        self.assertIn("sensor.secret_temperature", result["rejected_entity_ids"])

    def test_off_allowlist_entity_in_series_source_is_rejected(self):
        spec = _timeline_spec()
        spec["series"][0]["source"]["entity_id"] = "sensor.secret_temperature"
        result = validate_model_provider_chart_spec_entities(spec, SOURCE_SNAPSHOT)
        self.assertFalse(result["accepted"], result)
        self.assertEqual(result["code"], "model_provider_referenced_unapproved_entity")

    def test_approved_but_undisclosed_source_is_a_substitution(self):
        spec = _timeline_spec()
        spec["series"][0]["source"]["entity_id"] = "binary_sensor.front_door"
        result = validate_model_provider_output_entities(
            {"status": "chart_spec_ready", "chart_spec": spec, "memory_proposals": []},
            spec,
            SOURCE_SNAPSHOT,
            approved_catalog_entity_ids=["binary_sensor.kitchen_door", "binary_sensor.front_door"],
        )
        self.assertFalse(result["accepted"], result)
        self.assertEqual(result["code"], "model_provider_substituted_entity")

    def test_clean_approved_output_is_accepted(self):
        spec = _timeline_spec()
        result = validate_model_provider_output_entities(
            {"status": "chart_spec_ready", "chart_spec": deepcopy(spec), "memory_proposals": []},
            spec,
            SOURCE_SNAPSHOT,
        )
        self.assertTrue(result["accepted"], result)


if __name__ == "__main__":
    unittest.main()
