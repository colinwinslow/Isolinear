import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.fake_slice import (  # noqa: E402
    create_semantic_memory_store,
    create_deterministic_planner_result,
    extract_state_intervals,
    extract_threshold_intervals,
    get_fake_approved_entity_catalog,
    get_fake_dishwasher_power_history,
    get_fake_dishwasher_state_history,
    get_fake_normalized_history,
    get_fake_raw_numeric_history_records,
    get_trusted_renderer_primitive_scope,
    invoke_fake_prompt_to_chart,
    invoke_threshold_confirmation_use_once,
    invoke_threshold_confirmation_use_and_remember,
    invoke_trusted_renderer,
    invoke_validated_chart_plan,
    iso_timestamp,
    normalize_numeric_history_records,
    prepare_semantic_memory_for_planning,
    validate_chart_job,
)
from Isolinear.contracts import (  # noqa: E402
    ContractValidationError,
    validate_contract,
    validate_fake_prompt_to_chart_contracts,
)


class FakeVerticalSliceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 5, 29, 15, 0, 0, tzinfo=timezone.utc)
        self.start = self.now - timedelta(hours=24)
        self.expected_unit = "\u00b0F"

    def assert_contract_valid(self, contract_name, payload):
        try:
            validate_contract(contract_name, payload, repo_root=REPO_ROOT)
        except ContractValidationError as exc:
            self.fail(str(exc))

    def test_fake_catalog_contains_approved_temperature_binary_and_power_entities(self):
        catalog = get_fake_approved_entity_catalog()

        self.assertEqual(
            [item["entity_id"] for item in catalog],
            [
                "sensor.upstairs_temperature",
                "sensor.downstairs_temperature",
                "binary_sensor.dishwasher",
                "sensor.dishwasher_power",
            ],
        )
        self.assertTrue(all(item["visible_to_agent"] for item in catalog))
        self.assertEqual(catalog[0]["area"], "Hallway")
        self.assertEqual(catalog[1]["area"], "Living Room")
        self.assertEqual(catalog[0]["unit_of_measurement"], self.expected_unit)
        self.assertEqual(catalog[2]["area"], "Kitchen")
        self.assertEqual(catalog[2]["current_state"], "off")
        self.assertEqual(catalog[3]["area"], "Kitchen")
        self.assertEqual(catalog[3]["device_class"], "power")
        self.assertEqual(catalog[3]["unit_of_measurement"], "W")
        for item in catalog:
            self.assert_contract_valid("entity-catalog-item", item)

    def test_fake_history_is_normalized_numeric_data_for_last_24_hours(self):
        history = get_fake_normalized_history(now=self.now)

        self.assertEqual(len(history), 2)
        for series in history:
            self.assertEqual(series["kind"], "numeric")
            self.assertEqual(series["unit"], self.expected_unit)
            self.assertEqual(len(series["points"]), 5)
            self.assertEqual(series["points"][0]["ts"], iso_timestamp(self.start))
            self.assertEqual(series["points"][-1]["ts"], iso_timestamp(self.now))

            for point in series["points"]:
                self.assertEqual(point["quality"], "ok")
                self.assertIsInstance(point["value"], float)
            self.assert_contract_valid("history-series", series)

    def test_raw_numeric_history_normalizes_strings_and_missing_states(self):
        raw_records = get_fake_raw_numeric_history_records(now=self.now)
        series = normalize_numeric_history_records(
            raw_records=raw_records,
            series_id="upstairs_temperature",
            entity_id="sensor.upstairs_temperature",
            label="Upstairs Temperature",
            unit=self.expected_unit,
        )

        self.assertEqual(series["series_id"], "upstairs_temperature")
        self.assertEqual(series["entity_id"], "sensor.upstairs_temperature")
        self.assertEqual(series["kind"], "numeric")
        self.assertEqual(series["unit"], self.expected_unit)
        self.assertEqual(series["source_entity_ids"], ["sensor.upstairs_temperature"])
        self.assertEqual(
            [point["ts"] for point in series["points"]],
            [record["last_changed"] for record in raw_records],
        )
        self.assertEqual(
            [point["value"] for point in series["points"]],
            [70.8, 71.2, None, None, 70.9],
        )
        self.assertEqual(
            [point["raw_state"] for point in series["points"]],
            ["70.8", "71.2", "unknown", "unavailable", "70.9"],
        )
        self.assertEqual(
            [point["quality"] for point in series["points"]],
            ["ok", "ok", "unknown", "unavailable", "ok"],
        )
        self.assertTrue(any("unknown" in warning for warning in series["warnings"]))
        self.assertTrue(any("unavailable" in warning for warning in series["warnings"]))
        self.assert_contract_valid("history-series", series)

    def test_binary_state_history_extracts_active_interval(self):
        history_series = get_fake_dishwasher_state_history(now=self.now)
        derived_interval = extract_state_intervals(
            history_series=history_series,
            interval_id="dishwasher_running",
            label="Dishwasher Running",
            active_values=["on"],
            range_end=self.now,
        )

        self.assertEqual(history_series["kind"], "binary_state")
        self.assertEqual(
            [point["value"] for point in history_series["points"]],
            ["off", "on", "off"],
        )
        self.assertEqual(derived_interval["interval_id"], "dishwasher_running")
        self.assertEqual(derived_interval["source_entity_id"], "binary_sensor.dishwasher")
        self.assertEqual(len(derived_interval["intervals"]), 1)
        self.assertEqual(
            derived_interval["intervals"][0]["start"],
            iso_timestamp(self.start + timedelta(hours=8)),
        )
        self.assertEqual(
            derived_interval["intervals"][0]["end"],
            iso_timestamp(self.start + timedelta(hours=10)),
        )
        self.assertEqual(derived_interval["intervals"][0]["state"], "on")
        self.assert_contract_valid("history-series", history_series)
        self.assert_contract_valid("derived-interval", derived_interval)

    def test_confirmed_threshold_rule_extracts_numeric_intervals(self):
        history_series = get_fake_dishwasher_power_history(now=self.now)
        derived_interval = extract_threshold_intervals(
            history_series=history_series,
            interval_id="dishwasher_running",
            label="Dishwasher Running",
            threshold={"operator": ">", "value": 5, "unit": "W"},
            range_end=self.now,
        )

        self.assertEqual(history_series["series_id"], "dishwasher_power")
        self.assertEqual(history_series["entity_id"], "sensor.dishwasher_power")
        self.assertEqual(history_series["kind"], "numeric")
        self.assertEqual(history_series["unit"], "W")
        self.assertEqual(
            [point["value"] for point in history_series["points"]],
            [0.4, 0.6, 9.8, 42.0, 3.2, 0.5],
        )
        self.assertEqual(derived_interval["interval_id"], "dishwasher_running")
        self.assertEqual(derived_interval["source_entity_id"], "sensor.dishwasher_power")
        self.assertEqual(
            derived_interval["rule"],
            {"operator": ">", "value": 5, "unit": "W"},
        )
        self.assertEqual(len(derived_interval["intervals"]), 1)
        self.assertEqual(
            derived_interval["intervals"][0]["start"],
            iso_timestamp(self.start + timedelta(hours=8)),
        )
        self.assertEqual(
            derived_interval["intervals"][0]["end"],
            iso_timestamp(self.start + timedelta(hours=10)),
        )
        self.assertEqual(derived_interval["intervals"][0]["state"], True)
        self.assertIn("value > 5 W", derived_interval["intervals"][0]["reason"])
        self.assert_contract_valid("history-series", history_series)
        self.assert_contract_valid("derived-interval", derived_interval)

    def test_threshold_interval_feeds_shaded_interval_renderer(self):
        chart_spec = {
            "chart_id": "temperature_with_threshold_dishwasher_overlay",
            "chart_type": "time_series",
            "title": "Temperature With Dishwasher Running",
            "time_range": {"type": "relative", "duration": "24h"},
            "series": [
                {
                    "series_id": "upstairs_temperature",
                    "label": "Upstairs Temperature",
                    "source": {
                        "type": "entity",
                        "entity_id": "sensor.upstairs_temperature",
                        "attribute": None,
                    },
                    "role": "primary",
                    "render_as": "line",
                    "transform": None,
                    "unit": self.expected_unit,
                }
            ],
            "overlays": [
                {
                    "overlay_id": "dishwasher_running",
                    "label": "Dishwasher Running",
                    "source": {
                        "type": "entity",
                        "entity_id": "sensor.dishwasher_power",
                        "attribute": None,
                    },
                    "render_as": "shaded_intervals",
                    "threshold": {"operator": ">", "value": 5, "unit": "W"},
                }
            ],
            "x_axis": {"type": "time"},
            "y_axis": {"label": self.expected_unit},
            "notes": [],
        }
        power_history = get_fake_dishwasher_power_history(now=self.now)
        derived_interval = extract_threshold_intervals(
            history_series=power_history,
            interval_id="dishwasher_running",
            label="Dishwasher Running",
            threshold={"operator": ">", "value": 5, "unit": "W"},
            range_end=self.now,
        )
        render_request = {
            "request_id": "fake-threshold-overlay",
            "render_mode": "safe",
            "chart_spec": chart_spec,
            "history_series": get_fake_normalized_history(now=self.now),
            "derived_intervals": [derived_interval],
            "output": {"format": "png", "width": 1000, "height": 600},
            "theme": {},
            "codegen": None,
        }

        with tempfile.TemporaryDirectory() as run_directory:
            render_result = invoke_trusted_renderer(
                render_request=render_request,
                output_directory=Path(run_directory),
            )
            validation_result = validate_chart_job(
                chart_spec=chart_spec,
                render_result=render_result,
                entity_catalog=get_fake_approved_entity_catalog(),
                expected_start=self.start,
                expected_end=self.now,
            )

        self.assertEqual(render_result["status"], "success")
        self.assertEqual(
            render_result["render_metadata"]["overlays_plotted"],
            ["dishwasher_running"],
        )
        self.assertEqual(validation_result["status"], "pass")
        self.assert_contract_valid("chart-spec", chart_spec)
        self.assert_contract_valid("derived-interval", derived_interval)
        self.assert_contract_valid("render-request", render_request)
        self.assert_contract_valid("render-result", render_result)
        self.assert_contract_valid("validation-result", validation_result)

    def test_prompt_to_chart_slice_renders_png_and_passes_validation(self):
        output_root = REPO_ROOT / ".test-output"
        output_root.mkdir(exist_ok=True)

        with tempfile.TemporaryDirectory(dir=output_root) as run_directory:
            result = invoke_fake_prompt_to_chart(
                prompt="Compare upstairs and downstairs temperatures over the last 24 hours",
                output_directory=Path(run_directory),
                now=self.now,
            )

            planner_result = result["planner_result"]
            self.assertEqual(planner_result["status"], "chart_spec_ready")
            self.assertEqual(planner_result["chart_spec"]["chart_type"], "time_series")
            self.assertEqual(planner_result["chart_spec"]["time_range"]["type"], "relative")
            self.assertEqual(planner_result["chart_spec"]["time_range"]["duration"], "24h")
            self.assertEqual(
                [series["source"]["entity_id"] for series in planner_result["chart_spec"]["series"]],
                [
                    "sensor.upstairs_temperature",
                    "sensor.downstairs_temperature",
                ],
            )

            render_result = result["render_result"]
            self.assertEqual(render_result["status"], "success")
            self.assertEqual(render_result["image_mime_type"], "image/png")
            image_path = Path(render_result["image_path"])
            self.assertTrue(image_path.exists())
            self.assertGreater(image_path.stat().st_size, 0)
            self.assertEqual(image_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(
                render_result["render_metadata"]["series_plotted"],
                [
                    "upstairs_temperature",
                    "downstairs_temperature",
                ],
            )
            self.assertEqual(render_result["render_metadata"]["x_min"], iso_timestamp(self.start))
            self.assertEqual(render_result["render_metadata"]["x_max"], iso_timestamp(self.now))

            validation_result = result["validation_result"]
            self.assertEqual(validation_result["status"], "pass")
            for check in validation_result["checks"]:
                self.assertEqual(check["status"], "pass")
            validate_fake_prompt_to_chart_contracts(result, repo_root=REPO_ROOT)

    def test_planner_asks_to_confirm_threshold_for_dishwasher_running(self):
        catalog = [
            item
            for item in get_fake_approved_entity_catalog()
            if item["entity_id"] == "sensor.dishwasher_power"
        ]
        planner_result = create_deterministic_planner_result(
            prompt="Mark when the dishwasher was running over the last day",
            entity_catalog=catalog,
        )

        self.assertEqual(planner_result["status"], "clarification_needed")
        self.assertIsNone(planner_result["chart_spec"])

        question = planner_result["clarification_question"]
        self.assertEqual(question["question_id"], "confirm_dishwasher_power_threshold")
        self.assertIn("dishwasher", question["message"].lower())
        self.assertIn("threshold", question["message"].lower())
        self.assertIn("running", question["message"].lower())
        self.assertTrue(question["allow_free_text"])
        self.assertEqual(len(question["options"]), 1)
        option = question["options"][0]
        self.assertTrue(option["can_remember"])
        self.assertEqual(option["value"]["type"], "threshold_interval")
        self.assertEqual(option["value"]["entity_id"], "sensor.dishwasher_power")
        self.assertEqual(option["value"]["operator"], ">")
        self.assertEqual(option["value"]["value"], 5)
        self.assertEqual(option["value"]["unit"], "W")

        self.assert_contract_valid("planner-result", planner_result)
        self.assert_contract_valid("clarification-question", question)

    def test_use_once_threshold_confirmation_renders_chart_without_memory(self):
        output_root = REPO_ROOT / ".test-output"
        output_root.mkdir(exist_ok=True)
        confirmation_value = {
            "type": "threshold_interval",
            "entity_id": "sensor.dishwasher_power",
            "operator": ">",
            "value": 5,
            "unit": "W",
        }

        with tempfile.TemporaryDirectory(dir=output_root) as run_directory:
            result = invoke_threshold_confirmation_use_once(
                prompt="Mark when the dishwasher was running over the last day",
                confirmation_value=confirmation_value,
                output_directory=Path(run_directory),
                now=self.now,
            )

        planner_result = result["planner_result"]
        self.assertEqual(planner_result["status"], "chart_spec_ready")
        self.assertEqual(planner_result["memory_proposals"], [])
        self.assertEqual(
            planner_result["chart_spec"]["chart_id"],
            "temperature_with_threshold_dishwasher_overlay",
        )
        self.assertEqual(
            planner_result["chart_spec"]["overlays"][0]["threshold"],
            {"operator": ">", "value": 5, "unit": "W"},
        )

        self.assertEqual(len(result["derived_intervals"]), 1)
        derived_interval = result["derived_intervals"][0]
        self.assertEqual(derived_interval["interval_id"], "dishwasher_running")
        self.assertEqual(derived_interval["source_entity_id"], "sensor.dishwasher_power")
        self.assertEqual(derived_interval["rule"], {"operator": ">", "value": 5, "unit": "W"})
        self.assertEqual(result["saved_semantic_aliases"], [])

        render_request = result["render_request"]
        self.assertEqual(render_request["derived_intervals"], [derived_interval])
        render_result = result["render_result"]
        self.assertEqual(render_result["status"], "success")
        self.assertEqual(
            render_result["render_metadata"]["overlays_plotted"],
            ["dishwasher_running"],
        )
        validation_result = result["validation_result"]
        self.assertEqual(validation_result["status"], "pass")

        self.assert_contract_valid("planner-result", planner_result)
        self.assert_contract_valid("chart-spec", planner_result["chart_spec"])
        self.assert_contract_valid("history-series", result["history_series"][0])
        self.assert_contract_valid("derived-interval", derived_interval)
        self.assert_contract_valid("render-request", render_request)
        self.assert_contract_valid("render-result", render_result)
        self.assert_contract_valid("validation-result", validation_result)

    def test_use_and_remember_threshold_confirmation_saves_alias_and_renders_chart(self):
        output_root = REPO_ROOT / ".test-output"
        output_root.mkdir(exist_ok=True)
        confirmation_value = {
            "type": "threshold_interval",
            "entity_id": "sensor.dishwasher_power",
            "operator": ">",
            "value": 5,
            "unit": "W",
        }

        with tempfile.TemporaryDirectory(dir=output_root) as run_directory:
            result = invoke_threshold_confirmation_use_and_remember(
                prompt="Mark when the dishwasher was running over the last day",
                confirmation_value=confirmation_value,
                alias_name="dishwasher running",
                output_directory=Path(run_directory),
                now=self.now,
            )

        self.assertEqual(result["planner_result"]["status"], "chart_spec_ready")
        self.assertEqual(result["render_result"]["status"], "success")
        self.assertEqual(result["validation_result"]["status"], "pass")
        self.assertEqual(len(result["saved_semantic_aliases"]), 1)

        alias = result["saved_semantic_aliases"][0]
        self.assertEqual(alias["alias_id"], "dishwasher_running")
        self.assertEqual(alias["natural_names"], ["dishwasher running"])
        self.assertEqual(
            alias["meaning"],
            {
                "type": "threshold_interval",
                "entity_id": "sensor.dishwasher_power",
                "operator": ">",
                "value": 5,
                "unit": "W",
            },
        )
        self.assertEqual(alias["source"], "user_confirmed")
        self.assertEqual(
            alias["created_from_prompt"],
            "Mark when the dishwasher was running over the last day",
        )
        self.assertEqual(alias["created_at"], iso_timestamp(self.now))
        self.assertEqual(alias["last_used_at"], iso_timestamp(self.now))
        self.assertTrue(alias["enabled"])

        self.assert_contract_valid("semantic-alias", alias)
        self.assert_contract_valid("planner-result", result["planner_result"])
        self.assert_contract_valid("chart-spec", result["planner_result"]["chart_spec"])
        self.assert_contract_valid("render-request", result["render_request"])
        self.assert_contract_valid("render-result", result["render_result"])
        self.assert_contract_valid("validation-result", result["validation_result"])

    def test_saved_threshold_alias_reuses_memory_without_clarification(self):
        output_root = REPO_ROOT / ".test-output"
        output_root.mkdir(exist_ok=True)
        confirmation_value = {
            "type": "threshold_interval",
            "entity_id": "sensor.dishwasher_power",
            "operator": ">",
            "value": 5,
            "unit": "W",
        }

        with tempfile.TemporaryDirectory(dir=output_root) as setup_directory:
            saved_result = invoke_threshold_confirmation_use_and_remember(
                prompt="Mark when the dishwasher was running over the last day",
                confirmation_value=confirmation_value,
                alias_name="dishwasher running",
                output_directory=Path(setup_directory),
                now=self.now,
            )
        saved_alias = saved_result["saved_semantic_aliases"][0]

        with tempfile.TemporaryDirectory(dir=output_root) as run_directory:
            result = invoke_fake_prompt_to_chart(
                prompt="Mark when the dishwasher was running over the last day",
                output_directory=Path(run_directory),
                now=self.now,
                semantic_aliases=[saved_alias],
            )

        planner_result = result["planner_result"]
        self.assertEqual(planner_result["status"], "chart_spec_ready")
        self.assertIsNone(planner_result["clarification_question"])
        self.assertEqual(
            planner_result["chart_spec"]["chart_id"],
            "temperature_with_threshold_dishwasher_overlay",
        )
        self.assertEqual(
            planner_result["chart_spec"]["overlays"][0]["threshold"],
            {"operator": ">", "value": 5, "unit": "W"},
        )
        self.assertEqual(result["render_result"]["status"], "success")
        self.assertEqual(
            result["render_result"]["render_metadata"]["overlays_plotted"],
            ["dishwasher_running"],
        )
        self.assertEqual(result["validation_result"]["status"], "pass")
        self.assert_contract_valid("planner-result", planner_result)
        self.assert_contract_valid("chart-spec", planner_result["chart_spec"])
        self.assert_contract_valid("render-request", result["render_request"])
        self.assert_contract_valid("render-result", result["render_result"])
        self.assert_contract_valid("validation-result", result["validation_result"])

    def test_saved_threshold_alias_referencing_unavailable_entity_is_not_reused(self):
        output_root = REPO_ROOT / ".test-output"
        output_root.mkdir(exist_ok=True)
        saved_alias = {
            "alias_id": "dishwasher_running",
            "natural_names": ["dishwasher running"],
            "meaning": {
                "type": "threshold_interval",
                "entity_id": "sensor.retired_dishwasher_power",
                "operator": ">",
                "value": 5,
                "unit": "W",
            },
            "source": "user_confirmed",
            "created_from_prompt": "Mark when the dishwasher was running over the last day",
            "created_at": iso_timestamp(self.now),
            "last_used_at": iso_timestamp(self.now),
            "enabled": True,
        }

        with tempfile.TemporaryDirectory(dir=output_root) as run_directory:
            result = invoke_fake_prompt_to_chart(
                prompt="Mark when the dishwasher was running over the last day",
                output_directory=Path(run_directory),
                now=self.now,
                semantic_aliases=[saved_alias],
            )

        planner_result = result["planner_result"]
        self.assertEqual(planner_result["status"], "clarification_needed")
        self.assertEqual(
            planner_result["clarification_question"]["question_id"],
            "confirm_dishwasher_power_threshold",
        )
        self.assertIsNone(result["render_request"])
        self.assertIsNone(result["render_result"])
        self.assertIsNone(result["validation_result"])
        self.assertEqual(
            result["invalid_semantic_aliases"],
            [
                {
                    "alias_id": "dishwasher_running",
                    "entity_id": "sensor.retired_dishwasher_power",
                    "reason": "entity_unavailable",
                }
            ],
        )
        self.assertIn("semantic_alias_invalid", planner_result["warnings"])

        self.assert_contract_valid("semantic-alias", saved_alias)
        validate_fake_prompt_to_chart_contracts(result, repo_root=REPO_ROOT)

    def test_saved_threshold_alias_referencing_non_allowlisted_entity_is_not_reused(self):
        output_root = REPO_ROOT / ".test-output"
        output_root.mkdir(exist_ok=True)
        catalog = []
        for item in get_fake_approved_entity_catalog():
            updated_item = dict(item)
            if updated_item["entity_id"] == "sensor.dishwasher_power":
                updated_item["visible_to_agent"] = False
            catalog.append(updated_item)
        saved_alias = {
            "alias_id": "dishwasher_running",
            "natural_names": ["dishwasher running"],
            "meaning": {
                "type": "threshold_interval",
                "entity_id": "sensor.dishwasher_power",
                "operator": ">",
                "value": 5,
                "unit": "W",
            },
            "source": "user_confirmed",
            "created_from_prompt": "Mark when the dishwasher was running over the last day",
            "created_at": iso_timestamp(self.now),
            "last_used_at": iso_timestamp(self.now),
            "enabled": True,
        }

        with tempfile.TemporaryDirectory(dir=output_root) as run_directory:
            result = invoke_fake_prompt_to_chart(
                prompt="Mark when the dishwasher was running over the last day",
                output_directory=Path(run_directory),
                now=self.now,
                semantic_aliases=[saved_alias],
                entity_catalog=catalog,
            )

        planner_result = result["planner_result"]
        self.assertEqual(planner_result["status"], "cannot_resolve")
        self.assertIsNone(planner_result["clarification_question"])
        self.assertIsNone(result["render_request"])
        self.assertIsNone(result["render_result"])
        self.assertIsNone(result["validation_result"])
        self.assertEqual(
            result["invalid_semantic_aliases"],
            [
                {
                    "alias_id": "dishwasher_running",
                    "entity_id": "sensor.dishwasher_power",
                    "reason": "entity_not_allowlisted",
                }
            ],
        )
        self.assertIn("semantic_alias_invalid", planner_result["warnings"])

        self.assert_contract_valid("semantic-alias", saved_alias)
        validate_fake_prompt_to_chart_contracts(result, repo_root=REPO_ROOT)

    def test_semantic_memory_store_filters_valid_aliases_and_computes_invalidity(self):
        valid_alias = {
            "alias_id": "dishwasher_running",
            "natural_names": ["dishwasher running"],
            "meaning": {
                "type": "threshold_interval",
                "entity_id": "sensor.dishwasher_power",
                "operator": ">",
                "value": 5,
                "unit": "W",
            },
            "source": "user_confirmed",
            "created_from_prompt": "Mark when the dishwasher was running over the last day",
            "created_at": iso_timestamp(self.now),
            "last_used_at": iso_timestamp(self.now),
            "enabled": True,
        }
        unavailable_alias = {
            "alias_id": "retired_dishwasher_running",
            "natural_names": ["retired dishwasher running"],
            "meaning": {
                "type": "threshold_interval",
                "entity_id": "sensor.retired_dishwasher_power",
                "operator": ">",
                "value": 5,
                "unit": "W",
            },
            "source": "user_confirmed",
            "created_from_prompt": "Mark when the dishwasher was running over the last day",
            "created_at": iso_timestamp(self.now),
            "last_used_at": iso_timestamp(self.now),
            "enabled": True,
        }
        disabled_alias = {
            "alias_id": "disabled_dishwasher_running",
            "natural_names": ["disabled dishwasher running"],
            "meaning": {
                "type": "threshold_interval",
                "entity_id": "sensor.retired_dishwasher_power",
                "operator": ">",
                "value": 5,
                "unit": "W",
            },
            "source": "user_confirmed",
            "created_from_prompt": "Mark when the dishwasher was running over the last day",
            "created_at": iso_timestamp(self.now),
            "last_used_at": iso_timestamp(self.now),
            "enabled": False,
        }
        store = create_semantic_memory_store(
            aliases=[valid_alias, unavailable_alias, disabled_alias],
            now=self.now,
            repo_root=REPO_ROOT,
        )
        original_store = deepcopy(store)

        result = prepare_semantic_memory_for_planning(
            semantic_memory_store=store,
            entity_catalog=get_fake_approved_entity_catalog(),
            repo_root=REPO_ROOT,
        )

        self.assertEqual(result["valid_semantic_aliases"], [valid_alias])
        self.assertEqual(
            result["invalid_semantic_aliases"],
            [
                {
                    "alias_id": "retired_dishwasher_running",
                    "entity_id": "sensor.retired_dishwasher_power",
                    "reason": "entity_unavailable",
                }
            ],
        )
        self.assertIsNone(result["store_error"])
        self.assertEqual(store, original_store)
        self.assertNotIn("invalid_semantic_aliases", store)
        for alias in store["aliases"]:
            self.assertNotIn("invalid_reason", alias)

        self.assert_contract_valid("semantic-memory-store", store)
        self.assert_contract_valid("semantic-alias", valid_alias)
        self.assert_contract_valid("semantic-alias", unavailable_alias)
        self.assert_contract_valid("semantic-alias", disabled_alias)

    def test_semantic_memory_store_unsupported_version_fails_closed(self):
        valid_alias = {
            "alias_id": "dishwasher_running",
            "natural_names": ["dishwasher running"],
            "meaning": {
                "type": "threshold_interval",
                "entity_id": "sensor.dishwasher_power",
                "operator": ">",
                "value": 5,
                "unit": "W",
            },
            "source": "user_confirmed",
            "created_from_prompt": "Mark when the dishwasher was running over the last day",
            "created_at": iso_timestamp(self.now),
            "last_used_at": iso_timestamp(self.now),
            "enabled": True,
        }
        store = {
            "store_version": 99,
            "config_entry_id": "fake-config-entry",
            "created_at": iso_timestamp(self.now),
            "updated_at": iso_timestamp(self.now),
            "aliases": [valid_alias],
        }

        result = prepare_semantic_memory_for_planning(
            semantic_memory_store=store,
            entity_catalog=get_fake_approved_entity_catalog(),
            repo_root=REPO_ROOT,
        )

        self.assertEqual(result["valid_semantic_aliases"], [])
        self.assertEqual(result["invalid_semantic_aliases"], [])
        self.assertEqual(
            result["store_error"]["code"],
            "semantic_memory_store_invalid",
        )
        self.assertIn("$.store_version must equal 1.", result["store_error"]["message"])

    def test_semantic_memory_store_duplicate_alias_ids_fail_closed(self):
        valid_alias = {
            "alias_id": "dishwasher_running",
            "natural_names": ["dishwasher running"],
            "meaning": {
                "type": "threshold_interval",
                "entity_id": "sensor.dishwasher_power",
                "operator": ">",
                "value": 5,
                "unit": "W",
            },
            "source": "user_confirmed",
            "created_from_prompt": "Mark when the dishwasher was running over the last day",
            "created_at": iso_timestamp(self.now),
            "last_used_at": iso_timestamp(self.now),
            "enabled": True,
        }
        conflicting_alias = deepcopy(valid_alias)
        conflicting_alias["natural_names"] = ["alternate dishwasher running"]
        conflicting_alias["meaning"] = {
            "type": "threshold_interval",
            "entity_id": "sensor.retired_dishwasher_power",
            "operator": ">",
            "value": 5,
            "unit": "W",
        }
        store = {
            "store_version": 1,
            "config_entry_id": "fake-config-entry",
            "created_at": iso_timestamp(self.now),
            "updated_at": iso_timestamp(self.now),
            "aliases": [valid_alias, conflicting_alias],
        }

        result = prepare_semantic_memory_for_planning(
            semantic_memory_store=store,
            entity_catalog=get_fake_approved_entity_catalog(),
            repo_root=REPO_ROOT,
        )

        self.assertEqual(result["valid_semantic_aliases"], [])
        self.assertEqual(result["invalid_semantic_aliases"], [])
        self.assertEqual(
            result["store_error"]["code"],
            "semantic_memory_store_invalid",
        )
        self.assertIn(
            "Duplicate semantic alias IDs: dishwasher_running.",
            result["store_error"]["message"],
        )

        with self.assertRaises(ContractValidationError):
            create_semantic_memory_store(
                aliases=[valid_alias, conflicting_alias],
                now=self.now,
                repo_root=REPO_ROOT,
            )

    def test_safe_renderer_rejects_unsupported_chart_spec(self):
        request = {
            "request_id": "fake-unsupported-chart",
            "render_mode": "safe",
            "chart_spec": {
                "chart_id": "fake_bar",
                "chart_type": "bar",
                "title": "Unsupported",
                "time_range": {"type": "relative", "duration": "24h"},
                "series": [
                    {
                        "series_id": "upstairs_temperature",
                        "label": "Upstairs Temperature",
                        "source": {
                            "type": "entity",
                            "entity_id": "sensor.upstairs_temperature",
                            "attribute": None,
                        },
                        "role": "primary",
                        "render_as": "bar",
                        "transform": None,
                        "unit": self.expected_unit,
                    }
                ],
            },
            "history_series": get_fake_normalized_history(now=self.now),
            "derived_intervals": [],
            "output": {"format": "png", "width": 1000, "height": 600},
            "theme": {},
            "codegen": None,
        }

        with tempfile.TemporaryDirectory() as run_directory:
            render_result = invoke_trusted_renderer(
                render_request=request,
                output_directory=Path(run_directory),
            )

        self.assertEqual(render_result["status"], "failed")
        self.assertEqual(render_result["error"]["code"], "unsupported_chart_spec")
        self.assert_contract_valid("render-request", request)
        self.assert_contract_valid("chart-spec", request["chart_spec"])
        self.assert_contract_valid("render-result", render_result)

    def test_safe_renderer_rejects_unsupported_trusted_primitives_without_codegen(self):
        scope = get_trusted_renderer_primitive_scope()
        self.assertEqual(scope["chart_types"], ["time_series", "timeline", "bar", "heatmap", "histogram"])
        self.assertEqual(scope["time_series"]["series_render_as"], ["line"])
        self.assertEqual(scope["time_series"]["overlay_render_as"], ["shaded_intervals", "markers"])
        self.assertEqual(scope["time_series"]["marker_source_types"], ["entity"])
        self.assertEqual(scope["time_series"]["marker_source_kinds"], ["binary_state", "categorical_state", "event"])
        self.assertEqual(scope["time_series"]["marker_threshold_source_kinds"], ["numeric"])
        self.assertEqual(scope["timeline"]["series_render_as"], ["step"])
        self.assertEqual(scope["timeline"]["series_kinds"], ["binary_state", "categorical_state"])
        self.assertEqual(scope["bar"]["series_render_as"], ["bar"])
        self.assertEqual(scope["bar"]["series_source_types"], ["aggregate"])
        self.assertEqual(scope["bar"]["aggregate_operations"], ["mean", "min", "max", "sum", "count"])
        self.assertEqual(scope["heatmap"]["series_render_as"], ["heatmap"])
        self.assertEqual(scope["heatmap"]["series_source_types"], ["entity"])
        self.assertEqual(scope["heatmap"]["x_group_by"], ["hour"])
        self.assertEqual(scope["heatmap"]["y_group_by"], ["weekday"])
        self.assertEqual(scope["heatmap"]["cell_aggregation"], ["mean"])
        self.assertEqual(scope["histogram"]["series_render_as"], ["histogram"])
        self.assertEqual(scope["histogram"]["series_source_types"], ["entity"])
        self.assertEqual(scope["histogram"]["bin_count_min"], 4)
        self.assertEqual(scope["histogram"]["bin_count_max"], 64)
        self.assertEqual(scope["histogram"]["default_bin_count"], 8)
        self.assertEqual(scope["overlay_render_as"], ["shaded_intervals", "markers"])
        self.assertFalse(scope["fallback_to_codegen"])

        base_chart_spec = {
            "chart_id": "unsupported_time_series_primitive",
            "chart_type": "time_series",
            "title": "Unsupported Time Series Primitive",
            "time_range": {"type": "relative", "duration": "24h"},
            "series": [
                {
                    "series_id": "upstairs_temperature",
                    "label": "Upstairs Temperature",
                    "source": {
                        "type": "entity",
                        "entity_id": "sensor.upstairs_temperature",
                        "attribute": None,
                    },
                    "role": "primary",
                    "render_as": "line",
                    "transform": None,
                    "unit": self.expected_unit,
                }
            ],
            "overlays": [],
            "x_axis": {"type": "time"},
            "y_axis": {"label": self.expected_unit},
            "notes": [],
        }

        unsupported_variants = []

        area_chart = deepcopy(base_chart_spec)
        area_chart["chart_id"] = "unsupported_area_series"
        area_chart["series"][0]["render_as"] = "area"
        unsupported_variants.append(("area-series", area_chart))

        step_time_series_chart = deepcopy(base_chart_spec)
        step_time_series_chart["chart_id"] = "unsupported_time_series_step"
        step_time_series_chart["series"][0]["render_as"] = "step"
        unsupported_variants.append(("time-series-step", step_time_series_chart))

        rolling_chart = deepcopy(base_chart_spec)
        rolling_chart["chart_id"] = "unsupported_rolling_transform"
        rolling_chart["series"][0]["transform"] = {
            "operation": "rolling_mean",
            "window": "1h",
        }
        unsupported_variants.append(("rolling-transform", rolling_chart))

        aggregate_chart = deepcopy(base_chart_spec)
        aggregate_chart["chart_id"] = "unsupported_aggregate_source"
        aggregate_chart["series"][0]["source"] = {
            "type": "aggregate",
            "entity_ids": [
                "sensor.upstairs_temperature",
                "sensor.downstairs_temperature",
            ],
            "operation": "mean",
        }
        unsupported_variants.append(("aggregate-source", aggregate_chart))

        band_chart = deepcopy(base_chart_spec)
        band_chart["chart_id"] = "unsupported_band_overlay"
        band_chart["overlays"] = [
            {
                "overlay_id": "comfort_band",
                "label": "Comfort Band",
                "source": {
                    "type": "entity",
                    "entity_id": "sensor.upstairs_temperature",
                    "attribute": None,
                },
                "render_as": "band",
            }
        ]
        unsupported_variants.append(("band-overlay", band_chart))

        numeric_timeline_chart = deepcopy(base_chart_spec)
        numeric_timeline_chart["chart_id"] = "unsupported_numeric_timeline"
        numeric_timeline_chart["chart_type"] = "timeline"
        numeric_timeline_chart["series"][0]["render_as"] = "line"
        unsupported_variants.append(("numeric-timeline", numeric_timeline_chart))

        bad_heatmap_grouping_chart = deepcopy(base_chart_spec)
        bad_heatmap_grouping_chart["chart_id"] = "unsupported_heatmap_grouping"
        bad_heatmap_grouping_chart["chart_type"] = "heatmap"
        bad_heatmap_grouping_chart["series"][0]["render_as"] = "heatmap"
        bad_heatmap_grouping_chart["x_axis"] = {"type": "time", "group_by": "day"}
        bad_heatmap_grouping_chart["y_axis"] = {"type": "time", "group_by": "weekday"}
        unsupported_variants.append(("heatmap-grouping", bad_heatmap_grouping_chart))

        bad_histogram_bin_chart = deepcopy(base_chart_spec)
        bad_histogram_bin_chart["chart_id"] = "unsupported_histogram_bin_count"
        bad_histogram_bin_chart["chart_type"] = "histogram"
        bad_histogram_bin_chart["series"][0]["render_as"] = "histogram"
        bad_histogram_bin_chart["x_axis"] = {"type": "value", "bin_count": 2}
        bad_histogram_bin_chart["y_axis"] = {"label": "count"}
        unsupported_variants.append(("histogram-bin-count", bad_histogram_bin_chart))

        for variant_name, chart_spec in unsupported_variants:
            request = {
                "request_id": f"fake-unsupported-{variant_name}",
                "render_mode": "safe",
                "chart_spec": chart_spec,
                "history_series": get_fake_normalized_history(now=self.now),
                "derived_intervals": [],
                "output": {"format": "png", "width": 1000, "height": 600},
                "theme": {},
                "codegen": None,
            }

            with self.subTest(variant_name=variant_name):
                with tempfile.TemporaryDirectory() as run_directory:
                    render_result = invoke_trusted_renderer(
                        render_request=request,
                        output_directory=Path(run_directory),
                    )
                    self.assertEqual(list(Path(run_directory).iterdir()), [])

                self.assertEqual(render_result["status"], "failed")
                self.assertEqual(render_result["error"]["code"], "unsupported_chart_spec")
                self.assertIn(
                    "unsupported_primitives",
                    render_result["error"]["details"],
                )
                self.assertEqual(
                    render_result["render_metadata"]["codegen_attempts"],
                    0,
                )
                self.assertIsNone(render_result["image_path"])
                self.assert_contract_valid("render-request", request)
                self.assert_contract_valid("chart-spec", request["chart_spec"])
                self.assert_contract_valid("render-result", render_result)

    def test_validation_fails_for_non_allowlisted_entity(self):
        catalog = get_fake_approved_entity_catalog()
        chart_spec = {
            "chart_id": "hidden_temperature",
            "chart_type": "time_series",
            "title": "Hidden Temperature",
            "time_range": {"type": "relative", "duration": "24h"},
            "series": [
                {
                    "series_id": "hidden_temperature",
                    "label": "Hidden Temperature",
                    "source": {
                        "type": "entity",
                        "entity_id": "sensor.hidden_temperature",
                        "attribute": None,
                    },
                    "role": "primary",
                    "render_as": "line",
                    "transform": None,
                    "unit": self.expected_unit,
                }
            ],
            "overlays": [],
            "x_axis": {"type": "time"},
            "y_axis": {"label": self.expected_unit},
            "notes": [],
        }
        render_result = {
            "request_id": "fake-render",
            "status": "success",
            "image_id": "fake-render.png",
            "image_mime_type": "image/png",
            "image_path": None,
            "error": None,
            "render_metadata": {
                "title": "Hidden Temperature",
                "series_plotted": ["hidden_temperature"],
                "overlays_plotted": [],
                "x_min": iso_timestamp(self.start),
                "x_max": iso_timestamp(self.now),
                "warnings": [],
                "codegen_attempts": 0,
            },
        }

        validation_result = validate_chart_job(
            chart_spec=chart_spec,
            render_result=render_result,
            entity_catalog=catalog,
            expected_start=self.start,
            expected_end=self.now,
        )

        self.assertEqual(validation_result["status"], "fail")
        allowlist_check = next(
            check for check in validation_result["checks"] if check["name"] == "allowlisted_entities"
        )
        self.assertEqual(allowlist_check["status"], "fail")
        self.assertEqual(
            allowlist_check["message"],
            "Chart spec references non-allowlisted entities.",
        )
        self.assertEqual(
            allowlist_check["details"]["missing_entity_ids"],
            ["sensor.hidden_temperature"],
        )
        self.assert_contract_valid("chart-spec", chart_spec)
        self.assert_contract_valid("render-result", render_result)
        self.assert_contract_valid("validation-result", validation_result)

    def test_validation_fails_when_expected_overlay_is_missing_from_render_metadata(self):
        catalog = get_fake_approved_entity_catalog()
        chart_spec = {
            "chart_id": "temperature_with_dishwasher_overlay",
            "chart_type": "time_series",
            "title": "Temperature With Dishwasher Running",
            "time_range": {"type": "relative", "duration": "24h"},
            "series": [
                {
                    "series_id": "upstairs_temperature",
                    "label": "Upstairs Temperature",
                    "source": {
                        "type": "entity",
                        "entity_id": "binary_sensor.dishwasher",
                        "attribute": None,
                    },
                    "role": "primary",
                    "render_as": "line",
                    "transform": None,
                    "unit": self.expected_unit,
                }
            ],
            "overlays": [
                {
                    "overlay_id": "dishwasher_running",
                    "label": "Dishwasher Running",
                    "source": {
                        "type": "entity",
                        "entity_id": "sensor.upstairs_temperature",
                        "attribute": None,
                    },
                    "render_as": "shaded_intervals",
                    "active_values": ["on"],
                }
            ],
            "x_axis": {"type": "time"},
            "y_axis": {"label": self.expected_unit},
            "notes": [],
        }

        with tempfile.TemporaryDirectory() as run_directory:
            image_path = Path(run_directory) / "overlay-missing.png"
            image_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
            render_result = {
                "request_id": "overlay-missing",
                "status": "success",
                "image_id": "overlay-missing.png",
                "image_mime_type": "image/png",
                "image_path": str(image_path),
                "error": None,
                "render_metadata": {
                    "title": "Temperature With Dishwasher Running",
                    "series_plotted": ["upstairs_temperature"],
                    "overlays_plotted": [],
                    "x_min": iso_timestamp(self.start),
                    "x_max": iso_timestamp(self.now),
                    "warnings": [],
                    "codegen_attempts": 0,
                },
            }

            validation_result = validate_chart_job(
                chart_spec=chart_spec,
                render_result=render_result,
                entity_catalog=catalog,
                expected_start=self.start,
                expected_end=self.now,
            )

        self.assertEqual(validation_result["status"], "fail")
        overlay_check = next(
            check for check in validation_result["checks"] if check["name"] == "rendered_overlays"
        )
        self.assertEqual(overlay_check["status"], "fail")
        self.assertEqual(
            overlay_check["details"]["missing_overlay_ids"],
            ["dishwasher_running"],
        )
        self.assert_contract_valid("chart-spec", chart_spec)
        self.assert_contract_valid("render-result", render_result)
        self.assert_contract_valid("validation-result", validation_result)

    def test_safe_renderer_plots_shaded_interval_overlay(self):
        chart_spec = {
            "chart_id": "temperature_with_dishwasher_overlay",
            "chart_type": "time_series",
            "title": "Temperature With Dishwasher Running",
            "time_range": {"type": "relative", "duration": "24h"},
            "series": [
                {
                    "series_id": "upstairs_temperature",
                    "label": "Upstairs Temperature",
                    "source": {
                        "type": "entity",
                        "entity_id": "sensor.upstairs_temperature",
                        "attribute": None,
                    },
                    "role": "primary",
                    "render_as": "line",
                    "transform": None,
                    "unit": self.expected_unit,
                }
            ],
            "overlays": [
                {
                    "overlay_id": "dishwasher_running",
                    "label": "Dishwasher Running",
                    "source": {
                        "type": "entity",
                        "entity_id": "sensor.upstairs_temperature",
                        "attribute": None,
                    },
                    "render_as": "shaded_intervals",
                    "active_values": ["on"],
                }
            ],
            "x_axis": {"type": "time"},
            "y_axis": {"label": self.expected_unit},
            "notes": [],
        }
        dishwasher_history = get_fake_dishwasher_state_history(now=self.now)
        derived_interval = extract_state_intervals(
            history_series=dishwasher_history,
            interval_id="dishwasher_running",
            label="Dishwasher Running",
            active_values=["on"],
            range_end=self.now,
        )
        render_request = {
            "request_id": "fake-shaded-overlay",
            "render_mode": "safe",
            "chart_spec": chart_spec,
            "history_series": get_fake_normalized_history(now=self.now),
            "derived_intervals": [derived_interval],
            "output": {"format": "png", "width": 1000, "height": 600},
            "theme": {},
            "codegen": None,
        }

        with tempfile.TemporaryDirectory() as run_directory:
            render_result = invoke_trusted_renderer(
                render_request=render_request,
                output_directory=Path(run_directory),
            )
            validation_result = validate_chart_job(
                chart_spec=chart_spec,
                render_result=render_result,
                entity_catalog=get_fake_approved_entity_catalog(),
                expected_start=self.start,
                expected_end=self.now,
            )

        self.assertEqual(render_result["status"], "success")
        self.assertEqual(
            render_result["render_metadata"]["overlays_plotted"],
            ["dishwasher_running"],
        )
        self.assertEqual(validation_result["status"], "pass")
        self.assert_contract_valid("chart-spec", chart_spec)
        self.assert_contract_valid("derived-interval", derived_interval)
        self.assert_contract_valid("render-request", render_request)
        self.assert_contract_valid("render-result", render_result)
        self.assert_contract_valid("validation-result", validation_result)

    def test_safe_renderer_plots_state_interval_timeline(self):
        chart_spec = {
            "chart_id": "dishwasher_state_timeline",
            "chart_type": "timeline",
            "title": "Dishwasher State Timeline",
            "time_range": {
                "type": "absolute",
                "start": iso_timestamp(self.start),
                "end": iso_timestamp(self.now),
            },
            "series": [
                {
                    "series_id": "dishwasher_state",
                    "label": "Dishwasher Running",
                    "source": {
                        "type": "entity",
                        "entity_id": "binary_sensor.dishwasher",
                        "attribute": None,
                    },
                    "role": "primary",
                    "render_as": "step",
                    "transform": None,
                    "unit": None,
                }
            ],
            "overlays": [],
            "x_axis": {"type": "time"},
            "y_axis": {"label": "state"},
            "notes": ["Selected trusted renderer follow-up family fixture."],
        }
        dishwasher_history = get_fake_dishwasher_state_history(now=self.now)
        derived_interval = extract_state_intervals(
            history_series=dishwasher_history,
            interval_id="dishwasher_state",
            label="Dishwasher Running",
            active_values=["on"],
            range_end=self.now,
        )
        render_request = {
            "request_id": "fake-state-timeline",
            "render_mode": "safe",
            "chart_spec": chart_spec,
            "history_series": [dishwasher_history],
            "derived_intervals": [derived_interval],
            "output": {"format": "png", "width": 1000, "height": 420},
            "theme": {},
            "codegen": None,
        }

        with tempfile.TemporaryDirectory() as run_directory:
            render_result = invoke_trusted_renderer(
                render_request=render_request,
                output_directory=Path(run_directory),
            )
            image_signature = Path(render_result["image_path"]).read_bytes()[:8]
            output_files = sorted(path.name for path in Path(run_directory).iterdir())
            validation_result = validate_chart_job(
                chart_spec=chart_spec,
                render_result=render_result,
                entity_catalog=get_fake_approved_entity_catalog(),
                expected_start=self.start,
                expected_end=self.now,
            )

        self.assertEqual(render_result["status"], "success")
        self.assertEqual(render_result["image_mime_type"], "image/png")
        self.assertEqual(render_result["render_metadata"]["series_plotted"], ["dishwasher_state"])
        self.assertEqual(render_result["render_metadata"]["overlays_plotted"], [])
        self.assertEqual(render_result["render_metadata"]["codegen_attempts"], 0)
        self.assertEqual(render_result["render_metadata"]["x_min"], iso_timestamp(self.start))
        self.assertEqual(render_result["render_metadata"]["x_max"], iso_timestamp(self.now))
        self.assertEqual(image_signature, b"\x89PNG\r\n\x1a\n")
        self.assertEqual(output_files, ["fake-state-timeline.png"])
        self.assertEqual(validation_result["status"], "pass")
        self.assert_contract_valid("chart-spec", chart_spec)
        self.assert_contract_valid("derived-interval", derived_interval)
        self.assert_contract_valid("render-request", render_request)
        self.assert_contract_valid("render-result", render_result)
        self.assert_contract_valid("validation-result", validation_result)

    def test_safe_renderer_plots_aggregate_bar_chart(self):
        chart_spec = {
            "chart_id": "average_temperature_by_room",
            "chart_type": "bar",
            "title": "Average Temperature By Room",
            "time_range": {
                "type": "absolute",
                "start": iso_timestamp(self.start),
                "end": iso_timestamp(self.now),
            },
            "series": [
                {
                    "series_id": "average_temperature_by_room",
                    "label": "Average Temperature",
                    "source": {
                        "type": "aggregate",
                        "entity_ids": [
                            "sensor.upstairs_temperature",
                            "sensor.downstairs_temperature",
                        ],
                        "operation": "mean",
                    },
                    "role": "primary",
                    "render_as": "bar",
                    "transform": None,
                    "unit": self.expected_unit,
                }
            ],
            "overlays": [],
            "x_axis": {"type": "category"},
            "y_axis": {"label": self.expected_unit},
            "notes": ["Selected trusted renderer follow-up family fixture."],
        }
        render_request = {
            "request_id": "fake-aggregate-bar",
            "render_mode": "safe",
            "chart_spec": chart_spec,
            "history_series": get_fake_normalized_history(now=self.now),
            "derived_intervals": [],
            "output": {"format": "png", "width": 1000, "height": 520},
            "theme": {},
            "codegen": None,
        }

        with tempfile.TemporaryDirectory() as run_directory:
            render_result = invoke_trusted_renderer(
                render_request=render_request,
                output_directory=Path(run_directory),
            )
            image_signature = Path(render_result["image_path"]).read_bytes()[:8]
            output_files = sorted(path.name for path in Path(run_directory).iterdir())
            validation_result = validate_chart_job(
                chart_spec=chart_spec,
                render_result=render_result,
                entity_catalog=get_fake_approved_entity_catalog(),
                expected_start=self.start,
                expected_end=self.now,
            )

        self.assertEqual(render_result["status"], "success")
        self.assertEqual(render_result["image_mime_type"], "image/png")
        self.assertEqual(render_result["render_metadata"]["series_plotted"], ["average_temperature_by_room"])
        self.assertEqual(render_result["render_metadata"]["overlays_plotted"], [])
        self.assertEqual(render_result["render_metadata"]["codegen_attempts"], 0)
        self.assertEqual(render_result["render_metadata"]["x_min"], iso_timestamp(self.start))
        self.assertEqual(render_result["render_metadata"]["x_max"], iso_timestamp(self.now))
        self.assertEqual(image_signature, b"\x89PNG\r\n\x1a\n")
        self.assertEqual(output_files, ["fake-aggregate-bar.png"])
        self.assertEqual(validation_result["status"], "pass")
        self.assert_contract_valid("chart-spec", chart_spec)
        self.assert_contract_valid("render-request", render_request)
        self.assert_contract_valid("render-result", render_result)
        self.assert_contract_valid("validation-result", validation_result)

    def test_safe_renderer_plots_calendar_hour_heatmap(self):
        chart_spec = {
            "chart_id": "dishwasher_power_by_weekday_hour",
            "chart_type": "heatmap",
            "title": "Dishwasher Power By Weekday Hour",
            "time_range": {
                "type": "absolute",
                "start": iso_timestamp(self.start),
                "end": iso_timestamp(self.now),
            },
            "series": [
                {
                    "series_id": "dishwasher_power_heatmap",
                    "label": "Dishwasher Power",
                    "source": {
                        "type": "entity",
                        "entity_id": "sensor.dishwasher_power",
                        "attribute": None,
                    },
                    "role": "primary",
                    "render_as": "heatmap",
                    "transform": None,
                    "unit": "W",
                }
            ],
            "overlays": [],
            "x_axis": {"type": "time", "group_by": "hour"},
            "y_axis": {"type": "time", "group_by": "weekday"},
            "notes": ["Selected trusted renderer follow-up family fixture."],
        }
        render_request = {
            "request_id": "fake-calendar-hour-heatmap",
            "render_mode": "safe",
            "chart_spec": chart_spec,
            "history_series": [get_fake_dishwasher_power_history(now=self.now)],
            "derived_intervals": [],
            "output": {"format": "png", "width": 1000, "height": 520},
            "theme": {},
            "codegen": None,
        }

        with tempfile.TemporaryDirectory() as run_directory:
            render_result = invoke_trusted_renderer(
                render_request=render_request,
                output_directory=Path(run_directory),
            )
            image_signature = Path(render_result["image_path"]).read_bytes()[:8]
            output_files = sorted(path.name for path in Path(run_directory).iterdir())
            validation_result = validate_chart_job(
                chart_spec=chart_spec,
                render_result=render_result,
                entity_catalog=get_fake_approved_entity_catalog(),
                expected_start=self.start,
                expected_end=self.now,
            )

        self.assertEqual(render_result["status"], "success")
        self.assertEqual(render_result["image_mime_type"], "image/png")
        self.assertEqual(render_result["render_metadata"]["series_plotted"], ["dishwasher_power_heatmap"])
        self.assertEqual(render_result["render_metadata"]["overlays_plotted"], [])
        self.assertEqual(render_result["render_metadata"]["codegen_attempts"], 0)
        self.assertEqual(render_result["render_metadata"]["x_min"], iso_timestamp(self.start))
        self.assertEqual(render_result["render_metadata"]["x_max"], iso_timestamp(self.now))
        self.assertEqual(image_signature, b"\x89PNG\r\n\x1a\n")
        self.assertEqual(output_files, ["fake-calendar-hour-heatmap.png"])
        self.assertEqual(validation_result["status"], "pass")
        self.assert_contract_valid("chart-spec", chart_spec)
        self.assert_contract_valid("render-request", render_request)
        self.assert_contract_valid("render-result", render_result)
        self.assert_contract_valid("validation-result", validation_result)

    def test_safe_renderer_plots_event_markers(self):
        chart_spec = {
            "chart_id": "temperature_with_dishwasher_start_marker",
            "chart_type": "time_series",
            "title": "Temperature With Dishwasher Start Marker",
            "time_range": {
                "type": "absolute",
                "start": iso_timestamp(self.start),
                "end": iso_timestamp(self.now),
            },
            "series": [
                {
                    "series_id": "upstairs_temperature",
                    "label": "Upstairs Temperature",
                    "source": {
                        "type": "entity",
                        "entity_id": "sensor.upstairs_temperature",
                        "attribute": None,
                    },
                    "role": "primary",
                    "render_as": "line",
                    "transform": None,
                    "unit": self.expected_unit,
                }
            ],
            "overlays": [
                {
                    "overlay_id": "dishwasher_started",
                    "label": "Dishwasher Started",
                    "source": {
                        "type": "entity",
                        "entity_id": "binary_sensor.dishwasher",
                        "attribute": None,
                    },
                    "render_as": "markers",
                    "active_values": ["on"],
                }
            ],
            "x_axis": {"type": "time"},
            "y_axis": {"label": self.expected_unit},
            "notes": ["Selected trusted renderer follow-up family fixture."],
        }
        render_request = {
            "request_id": "fake-event-markers",
            "render_mode": "safe",
            "chart_spec": chart_spec,
            "history_series": get_fake_normalized_history(now=self.now)
            + [get_fake_dishwasher_state_history(now=self.now)],
            "derived_intervals": [],
            "output": {"format": "png", "width": 1000, "height": 520},
            "theme": {},
            "codegen": None,
        }

        with tempfile.TemporaryDirectory() as run_directory:
            render_result = invoke_trusted_renderer(
                render_request=render_request,
                output_directory=Path(run_directory),
            )
            image_signature = Path(render_result["image_path"]).read_bytes()[:8]
            output_files = sorted(path.name for path in Path(run_directory).iterdir())
            validation_result = validate_chart_job(
                chart_spec=chart_spec,
                render_result=render_result,
                entity_catalog=get_fake_approved_entity_catalog(),
                expected_start=self.start,
                expected_end=self.now,
            )

        self.assertEqual(render_result["status"], "success")
        self.assertEqual(render_result["image_mime_type"], "image/png")
        self.assertEqual(render_result["render_metadata"]["series_plotted"], ["upstairs_temperature"])
        self.assertEqual(render_result["render_metadata"]["overlays_plotted"], ["dishwasher_started"])
        self.assertEqual(render_result["render_metadata"]["codegen_attempts"], 0)
        self.assertEqual(render_result["render_metadata"]["x_min"], iso_timestamp(self.start))
        self.assertEqual(render_result["render_metadata"]["x_max"], iso_timestamp(self.now))
        self.assertEqual(image_signature, b"\x89PNG\r\n\x1a\n")
        self.assertEqual(output_files, ["fake-event-markers.png"])
        self.assertEqual(validation_result["status"], "pass")
        self.assert_contract_valid("chart-spec", chart_spec)
        self.assert_contract_valid("render-request", render_request)
        self.assert_contract_valid("render-result", render_result)
        self.assert_contract_valid("validation-result", validation_result)

    def test_safe_renderer_plots_distribution_histogram(self):
        chart_spec = {
            "chart_id": "dishwasher_power_distribution",
            "chart_type": "histogram",
            "title": "Dishwasher Power Distribution",
            "time_range": {
                "type": "absolute",
                "start": iso_timestamp(self.start),
                "end": iso_timestamp(self.now),
            },
            "series": [
                {
                    "series_id": "dishwasher_power_distribution",
                    "label": "Dishwasher Power",
                    "source": {
                        "type": "entity",
                        "entity_id": "sensor.dishwasher_power",
                        "attribute": None,
                    },
                    "role": "primary",
                    "render_as": "histogram",
                    "transform": None,
                    "unit": "W",
                }
            ],
            "overlays": [],
            "x_axis": {"type": "value", "bin_count": 6},
            "y_axis": {"label": "count"},
            "notes": ["Selected trusted renderer follow-up family fixture."],
        }
        render_request = {
            "request_id": "fake-distribution-histogram",
            "render_mode": "safe",
            "chart_spec": chart_spec,
            "history_series": [get_fake_dishwasher_power_history(now=self.now)],
            "derived_intervals": [],
            "output": {"format": "png", "width": 1000, "height": 520},
            "theme": {},
            "codegen": None,
        }

        with tempfile.TemporaryDirectory() as run_directory:
            render_result = invoke_trusted_renderer(
                render_request=render_request,
                output_directory=Path(run_directory),
            )
            image_signature = Path(render_result["image_path"]).read_bytes()[:8]
            output_files = sorted(path.name for path in Path(run_directory).iterdir())
            validation_result = validate_chart_job(
                chart_spec=chart_spec,
                render_result=render_result,
                entity_catalog=get_fake_approved_entity_catalog(),
                expected_start=self.start,
                expected_end=self.now,
            )

        self.assertEqual(render_result["status"], "success")
        self.assertEqual(render_result["image_mime_type"], "image/png")
        self.assertEqual(render_result["render_metadata"]["series_plotted"], ["dishwasher_power_distribution"])
        self.assertEqual(render_result["render_metadata"]["overlays_plotted"], [])
        self.assertEqual(render_result["render_metadata"]["codegen_attempts"], 0)
        self.assertEqual(render_result["render_metadata"]["x_min"], iso_timestamp(self.start))
        self.assertEqual(render_result["render_metadata"]["x_max"], iso_timestamp(self.now))
        self.assertEqual(image_signature, b"\x89PNG\r\n\x1a\n")
        self.assertEqual(output_files, ["fake-distribution-histogram.png"])
        self.assertEqual(validation_result["status"], "pass")
        self.assert_contract_valid("chart-spec", chart_spec)
        self.assert_contract_valid("render-request", render_request)
        self.assert_contract_valid("render-result", render_result)
        self.assert_contract_valid("validation-result", validation_result)

    def test_safe_renderer_rejects_heatmap_missing_source_history_without_artifact(self):
        chart_spec = {
            "chart_id": "dishwasher_power_by_weekday_hour_missing_source",
            "chart_type": "heatmap",
            "title": "Dishwasher Power By Weekday Hour Missing Source",
            "time_range": {
                "type": "absolute",
                "start": iso_timestamp(self.start),
                "end": iso_timestamp(self.now),
            },
            "series": [
                {
                    "series_id": "dishwasher_power_heatmap",
                    "label": "Dishwasher Power",
                    "source": {
                        "type": "entity",
                        "entity_id": "sensor.dishwasher_power",
                        "attribute": None,
                    },
                    "role": "primary",
                    "render_as": "heatmap",
                    "transform": None,
                    "unit": "W",
                }
            ],
            "overlays": [],
            "x_axis": {"type": "time", "group_by": "hour"},
            "y_axis": {"type": "time", "group_by": "weekday"},
            "notes": [],
        }
        render_request = {
            "request_id": "fake-calendar-hour-heatmap-missing-source",
            "render_mode": "safe",
            "chart_spec": chart_spec,
            "history_series": get_fake_normalized_history(now=self.now),
            "derived_intervals": [],
            "output": {"format": "png", "width": 1000, "height": 520},
            "theme": {},
            "codegen": None,
        }

        with tempfile.TemporaryDirectory() as run_directory:
            render_result = invoke_trusted_renderer(
                render_request=render_request,
                output_directory=Path(run_directory),
            )
            output_files = sorted(path.name for path in Path(run_directory).iterdir())

        self.assertEqual(render_result["status"], "failed")
        self.assertEqual(render_result["error"]["code"], "missing_history_series")
        self.assertEqual(render_result["render_metadata"]["codegen_attempts"], 0)
        self.assertIsNone(render_result["image_path"])
        self.assertEqual(output_files, [])
        self.assertEqual(
            render_result["error"]["details"]["missing_heatmap_sources"],
            [
                {
                    "series_id": "dishwasher_power_heatmap",
                    "entity_id": "sensor.dishwasher_power",
                    "reason": "missing_history_series",
                }
            ],
        )
        self.assert_contract_valid("chart-spec", chart_spec)
        self.assert_contract_valid("render-request", render_request)
        self.assert_contract_valid("render-result", render_result)

    def test_safe_renderer_rejects_marker_overlay_without_matching_events_before_artifact(self):
        chart_spec = {
            "chart_id": "temperature_with_missing_marker_events",
            "chart_type": "time_series",
            "title": "Temperature With Missing Marker Events",
            "time_range": {
                "type": "absolute",
                "start": iso_timestamp(self.start),
                "end": iso_timestamp(self.now),
            },
            "series": [
                {
                    "series_id": "upstairs_temperature",
                    "label": "Upstairs Temperature",
                    "source": {
                        "type": "entity",
                        "entity_id": "sensor.upstairs_temperature",
                        "attribute": None,
                    },
                    "role": "primary",
                    "render_as": "line",
                    "transform": None,
                    "unit": self.expected_unit,
                }
            ],
            "overlays": [
                {
                    "overlay_id": "dishwasher_started",
                    "label": "Dishwasher Started",
                    "source": {
                        "type": "entity",
                        "entity_id": "binary_sensor.dishwasher",
                        "attribute": None,
                    },
                    "render_as": "markers",
                    "active_values": ["running"],
                }
            ],
            "x_axis": {"type": "time"},
            "y_axis": {"label": self.expected_unit},
            "notes": [],
        }
        render_request = {
            "request_id": "fake-event-markers-no-events",
            "render_mode": "safe",
            "chart_spec": chart_spec,
            "history_series": get_fake_normalized_history(now=self.now)
            + [get_fake_dishwasher_state_history(now=self.now)],
            "derived_intervals": [],
            "output": {"format": "png", "width": 1000, "height": 520},
            "theme": {},
            "codegen": None,
        }

        with tempfile.TemporaryDirectory() as run_directory:
            render_result = invoke_trusted_renderer(
                render_request=render_request,
                output_directory=Path(run_directory),
            )
            output_files = sorted(path.name for path in Path(run_directory).iterdir())

        self.assertEqual(render_result["status"], "failed")
        self.assertEqual(render_result["error"]["code"], "missing_marker_events")
        self.assertEqual(render_result["render_metadata"]["codegen_attempts"], 0)
        self.assertIsNone(render_result["image_path"])
        self.assertEqual(output_files, [])
        self.assertEqual(
            render_result["error"]["details"]["missing_marker_sources"],
            [
                {
                    "overlay_id": "dishwasher_started",
                    "entity_id": "binary_sensor.dishwasher",
                    "reason": "no_matching_marker_events",
                }
            ],
        )
        self.assert_contract_valid("chart-spec", chart_spec)
        self.assert_contract_valid("render-request", render_request)
        self.assert_contract_valid("render-result", render_result)

    def test_safe_renderer_rejects_histogram_missing_source_history_without_artifact(self):
        chart_spec = {
            "chart_id": "dishwasher_power_distribution_missing_source",
            "chart_type": "histogram",
            "title": "Dishwasher Power Distribution Missing Source",
            "time_range": {
                "type": "absolute",
                "start": iso_timestamp(self.start),
                "end": iso_timestamp(self.now),
            },
            "series": [
                {
                    "series_id": "dishwasher_power_distribution",
                    "label": "Dishwasher Power",
                    "source": {
                        "type": "entity",
                        "entity_id": "sensor.dishwasher_power",
                        "attribute": None,
                    },
                    "role": "primary",
                    "render_as": "histogram",
                    "transform": None,
                    "unit": "W",
                }
            ],
            "overlays": [],
            "x_axis": {"type": "value", "bin_count": 6},
            "y_axis": {"label": "count"},
            "notes": [],
        }
        render_request = {
            "request_id": "fake-distribution-histogram-missing-source",
            "render_mode": "safe",
            "chart_spec": chart_spec,
            "history_series": get_fake_normalized_history(now=self.now),
            "derived_intervals": [],
            "output": {"format": "png", "width": 1000, "height": 520},
            "theme": {},
            "codegen": None,
        }

        with tempfile.TemporaryDirectory() as run_directory:
            render_result = invoke_trusted_renderer(
                render_request=render_request,
                output_directory=Path(run_directory),
            )
            output_files = sorted(path.name for path in Path(run_directory).iterdir())

        self.assertEqual(render_result["status"], "failed")
        self.assertEqual(render_result["error"]["code"], "missing_history_series")
        self.assertEqual(render_result["render_metadata"]["codegen_attempts"], 0)
        self.assertIsNone(render_result["image_path"])
        self.assertEqual(output_files, [])
        self.assertEqual(
            render_result["error"]["details"]["missing_histogram_sources"],
            [
                {
                    "series_id": "dishwasher_power_distribution",
                    "entity_id": "sensor.dishwasher_power",
                    "reason": "missing_history_series",
                }
            ],
        )
        self.assert_contract_valid("chart-spec", chart_spec)
        self.assert_contract_valid("render-request", render_request)
        self.assert_contract_valid("render-result", render_result)

    def test_safe_renderer_rejects_aggregate_bar_missing_source_history_without_artifact(self):
        chart_spec = {
            "chart_id": "average_temperature_with_missing_source",
            "chart_type": "bar",
            "title": "Average Temperature With Missing Source",
            "time_range": {
                "type": "absolute",
                "start": iso_timestamp(self.start),
                "end": iso_timestamp(self.now),
            },
            "series": [
                {
                    "series_id": "average_temperature_by_room",
                    "label": "Average Temperature",
                    "source": {
                        "type": "aggregate",
                        "entity_ids": [
                            "sensor.upstairs_temperature",
                            "sensor.dishwasher_power",
                        ],
                        "operation": "mean",
                    },
                    "role": "primary",
                    "render_as": "bar",
                    "transform": None,
                    "unit": self.expected_unit,
                }
            ],
            "overlays": [],
            "x_axis": {"type": "category"},
            "y_axis": {"label": self.expected_unit},
            "notes": [],
        }
        render_request = {
            "request_id": "fake-aggregate-bar-missing-source",
            "render_mode": "safe",
            "chart_spec": chart_spec,
            "history_series": get_fake_normalized_history(now=self.now),
            "derived_intervals": [],
            "output": {"format": "png", "width": 1000, "height": 520},
            "theme": {},
            "codegen": None,
        }

        with tempfile.TemporaryDirectory() as run_directory:
            render_result = invoke_trusted_renderer(
                render_request=render_request,
                output_directory=Path(run_directory),
            )
            output_files = sorted(path.name for path in Path(run_directory).iterdir())

        self.assertEqual(render_result["status"], "failed")
        self.assertEqual(render_result["error"]["code"], "missing_history_series")
        self.assertEqual(render_result["render_metadata"]["codegen_attempts"], 0)
        self.assertIsNone(render_result["image_path"])
        self.assertEqual(output_files, [])
        self.assertEqual(
            render_result["error"]["details"]["missing_aggregate_sources"],
            [
                {
                    "series_id": "average_temperature_by_room",
                    "entity_id": "sensor.dishwasher_power",
                    "reason": "missing_history_series",
                }
            ],
        )
        self.assert_contract_valid("chart-spec", chart_spec)
        self.assert_contract_valid("render-request", render_request)
        self.assert_contract_valid("render-result", render_result)

    def test_safe_renderer_rejects_timeline_interval_source_mismatch_without_artifact(self):
        chart_spec = {
            "chart_id": "dishwasher_state_timeline_mismatch",
            "chart_type": "timeline",
            "title": "Dishwasher State Timeline",
            "time_range": {
                "type": "absolute",
                "start": iso_timestamp(self.start),
                "end": iso_timestamp(self.now),
            },
            "series": [
                {
                    "series_id": "dishwasher_state",
                    "label": "Dishwasher Running",
                    "source": {
                        "type": "entity",
                        "entity_id": "binary_sensor.dishwasher",
                        "attribute": None,
                    },
                    "role": "primary",
                    "render_as": "step",
                    "transform": None,
                    "unit": None,
                }
            ],
            "overlays": [],
            "x_axis": {"type": "time"},
            "y_axis": {"label": "state"},
            "notes": [],
        }
        dishwasher_history = get_fake_dishwasher_state_history(now=self.now)
        derived_interval = extract_state_intervals(
            history_series=dishwasher_history,
            interval_id="dishwasher_state",
            label="Dishwasher Running",
            active_values=["on"],
            range_end=self.now,
        )
        derived_interval["source_entity_id"] = "sensor.dishwasher_power"
        render_request = {
            "request_id": "fake-state-timeline-mismatch",
            "render_mode": "safe",
            "chart_spec": chart_spec,
            "history_series": [dishwasher_history],
            "derived_intervals": [derived_interval],
            "output": {"format": "png", "width": 1000, "height": 420},
            "theme": {},
            "codegen": None,
        }

        with tempfile.TemporaryDirectory() as run_directory:
            render_result = invoke_trusted_renderer(
                render_request=render_request,
                output_directory=Path(run_directory),
            )
            output_files = sorted(path.name for path in Path(run_directory).iterdir())

        self.assertEqual(render_result["status"], "failed")
        self.assertEqual(render_result["error"]["code"], "derived_interval_source_mismatch")
        self.assertEqual(render_result["render_metadata"]["codegen_attempts"], 0)
        self.assertIsNone(render_result["image_path"])
        self.assertEqual(output_files, [])
        self.assertEqual(
            render_result["error"]["details"]["source_mismatches"],
            [
                {
                    "series_id": "dishwasher_state",
                    "expected_entity_id": "binary_sensor.dishwasher",
                    "actual_entity_id": "sensor.dishwasher_power",
                }
            ],
        )
        self.assert_contract_valid("chart-spec", chart_spec)
        self.assert_contract_valid("derived-interval", derived_interval)
        self.assert_contract_valid("render-request", render_request)
        self.assert_contract_valid("render-result", render_result)

    def test_contract_validation_rejects_malformed_payload(self):
        malformed_catalog_item = {
            "entity_id": "not-an-entity-id",
            "domain": "sensor",
            "visible_to_agent": True,
        }

        with self.assertRaises(ContractValidationError):
            validate_contract(
                "entity-catalog-item",
                malformed_catalog_item,
                repo_root=REPO_ROOT,
            )

    def test_plan_validation_rejects_non_allowlisted_entity_before_rendering(self):
        catalog = get_fake_approved_entity_catalog()
        chart_spec = {
            "chart_id": "hidden_temperature",
            "chart_type": "time_series",
            "title": "Hidden Temperature",
            "time_range": {"type": "relative", "duration": "24h"},
            "series": [
                {
                    "series_id": "hidden_temperature",
                    "label": "Hidden Temperature",
                    "source": {
                        "type": "entity",
                        "entity_id": "sensor.hidden_temperature",
                        "attribute": None,
                    },
                    "role": "primary",
                    "render_as": "line",
                    "transform": None,
                    "unit": self.expected_unit,
                }
            ],
            "overlays": [],
            "x_axis": {"type": "time"},
            "y_axis": {"label": self.expected_unit},
            "notes": [],
        }

        with tempfile.TemporaryDirectory() as run_directory:
            result = invoke_validated_chart_plan(
                chart_spec=chart_spec,
                entity_catalog=catalog,
                history_series=get_fake_normalized_history(now=self.now),
                output_directory=Path(run_directory),
                request_id="hidden-temperature",
                now=self.now,
                repo_root=REPO_ROOT,
            )
            self.assertEqual(list(Path(run_directory).iterdir()), [])

        self.assertIsNone(result["render_request"])
        self.assertIsNone(result["render_result"])
        self.assertEqual(result["validation_result"]["status"], "fail")
        allowlist_check = next(
            check for check in result["validation_result"]["checks"] if check["name"] == "allowlisted_entities"
        )
        self.assertEqual(allowlist_check["status"], "fail")
        self.assertEqual(
            allowlist_check["details"]["missing_entity_ids"],
            ["sensor.hidden_temperature"],
        )
        self.assert_contract_valid("validation-result", result["validation_result"])

    def test_plan_validation_rejects_schema_invalid_chart_spec_before_rendering(self):
        catalog = get_fake_approved_entity_catalog()
        chart_spec = {
            "chart_id": "missing_series",
            "chart_type": "time_series",
            "title": "Missing Series",
            "time_range": {"type": "relative", "duration": "24h"},
        }

        with tempfile.TemporaryDirectory() as run_directory:
            result = invoke_validated_chart_plan(
                chart_spec=chart_spec,
                entity_catalog=catalog,
                history_series=get_fake_normalized_history(now=self.now),
                output_directory=Path(run_directory),
                request_id="missing-series",
                now=self.now,
                repo_root=REPO_ROOT,
            )
            self.assertEqual(list(Path(run_directory).iterdir()), [])

        self.assertIsNone(result["render_request"])
        self.assertIsNone(result["render_result"])
        self.assertEqual(result["validation_result"]["status"], "fail")
        schema_check = next(
            check for check in result["validation_result"]["checks"] if check["name"] == "chart_spec_schema"
        )
        self.assertEqual(schema_check["status"], "fail")
        self.assertIn("$.series is required.", schema_check["details"]["error"])
        self.assert_contract_valid("validation-result", result["validation_result"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
