import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.dashboard_card_anchor import (  # noqa: E402
    REQUIRED_SNAPSHOT_STATES,
    VALID_CARD_CONFIG,
    boundary_check,
    load_job_snapshots,
    observed_adapter,
    observed_config_behavior,
    observed_layout,
    observed_registration,
    verify_dashboard_card_anchor,
)


class DashboardCardAnchorTests(unittest.TestCase):
    def test_fixture_snapshots_cover_required_card_states(self):
        snapshots = load_job_snapshots(REPO_ROOT)

        self.assertEqual(list(snapshots), REQUIRED_SNAPSHOT_STATES)
        for state in REQUIRED_SNAPSHOT_STATES:
            self.assertEqual(snapshots[state]["status"], state)
            self.assertIn("validation", snapshots[state])

        self.assertEqual(
            snapshots["complete"]["chart"]["image_url"],
            "../fixtures/fake-temperature-chart.svg",
        )
        self.assertEqual(
            snapshots["clarification_needed"]["clarification"]["options"][0]["can_remember"],
            True,
        )

    def test_card_module_registration_and_home_assistant_hooks_are_present(self):
        registration = observed_registration(REPO_ROOT)

        self.assertTrue(registration["custom_element_defined"])
        self.assertTrue(registration["editor_element_defined"])
        self.assertTrue(registration["lit_source_custom_element"])
        self.assertEqual(
            registration["card_picker_metadata"],
            {
                "window_custom_cards": True,
                "type": "isolinear-card",
                "name": "Isolinear",
                "preview": True,
            },
        )
        self.assertTrue(registration["configuration_surface"]["get_config_element"])
        self.assertTrue(registration["configuration_surface"]["editor_defined"])
        self.assertTrue(registration["card_sizing_hooks"]["get_card_size"])
        self.assertTrue(registration["card_sizing_hooks"]["get_grid_options"])

    def test_config_validation_accepts_minimal_config_and_rejects_invalid_config(self):
        config_behavior = observed_config_behavior()

        self.assertEqual(
            config_behavior["valid_config"]["config_entry_id"],
            VALID_CARD_CONFIG["config_entry_id"],
        )
        self.assertEqual(config_behavior["valid_default_config"]["config_entry_id"], "auto")
        self.assertTrue(
            all(not result["accepted"] for result in config_behavior["invalid_configs"])
        )
        self.assertIn(
            "custom:isolinear-card",
            config_behavior["invalid_configs"][0]["error"],
        )
        self.assertIn(
            "config_entry_id",
            config_behavior["invalid_configs"][-1]["error"],
        )

    def test_state_rendering_and_layout_markers_match_bdd_requirements(self):
        layout = observed_layout(REPO_ROOT)

        self.assertTrue(layout["idle_prompt_first"]["layout_marker"])
        self.assertTrue(layout["idle_prompt_first"]["prompt_input_marker"])
        self.assertTrue(layout["idle_prompt_first"]["submit_button_marker"])
        self.assertTrue(layout["active_planning"]["disabled_duplicate_submit_marker"])
        self.assertTrue(layout["clarification"]["panel_marker"])
        self.assertTrue(layout["clarification"]["use_once_marker"])
        self.assertTrue(layout["clarification"]["use_and_remember_marker"])
        self.assertTrue(layout["complete_chart_first"]["layout_marker"])
        self.assertTrue(layout["complete_chart_first"]["chart_image_marker"])
        self.assertTrue(layout["complete_chart_first"]["chart_dominant_rows"])
        self.assertTrue(layout["complete_chart_first"]["bottom_composer_marker"])
        self.assertTrue(layout["complete_chart_first"]["compact_complete_composer_rows"])
        self.assertTrue(layout["failed"]["failure_marker"])
        self.assertTrue(layout["failed"]["retry_marker"])
        self.assertTrue(layout["failed"]["revise_marker"])

    def test_fake_websocket_adapter_records_versioned_isolinear_messages(self):
        adapter = observed_adapter(REPO_ROOT)

        self.assertTrue(adapter["all_commands_versioned"])
        self.assertTrue(adapter["fake_hass_records_calls"])
        self.assertTrue(adapter["card_uses_send_message_promise"])
        self.assertTrue(all(adapter["command_markers_present"].values()))
        self.assertEqual(
            [message["type"] for message in adapter["recorded_messages"]],
            [
                "isolinear/v1/job/start",
                "isolinear/v1/clarification/answer",
                "isolinear/v1/clarification/answer",
                "isolinear/v1/job/retry",
            ],
        )
        self.assertEqual(adapter["recorded_messages"][1]["remember"], False)
        self.assertEqual(adapter["recorded_messages"][2]["remember"], True)

    def test_static_boundary_scan_finds_no_direct_orchestration_access(self):
        boundary = boundary_check(REPO_ROOT)

        self.assertTrue(boundary["passed"], boundary["matches"])
        self.assertEqual(boundary["matches"], [])

    def test_dashboard_card_anchor_verification_passes(self):
        result = verify_dashboard_card_anchor(REPO_ROOT)

        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
