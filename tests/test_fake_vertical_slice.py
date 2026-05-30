import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.fake_slice import (  # noqa: E402
    get_fake_approved_entity_catalog,
    get_fake_normalized_history,
    invoke_fake_prompt_to_chart,
    invoke_trusted_renderer,
    invoke_validated_chart_plan,
    iso_timestamp,
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

    def test_fake_catalog_contains_only_approved_temperature_entities(self):
        catalog = get_fake_approved_entity_catalog()

        self.assertEqual(
            [item["entity_id"] for item in catalog],
            [
                "sensor.upstairs_temperature",
                "sensor.downstairs_temperature",
            ],
        )
        self.assertTrue(all(item["visible_to_agent"] for item in catalog))
        self.assertEqual(catalog[0]["area"], "Hallway")
        self.assertEqual(catalog[1]["area"], "Living Room")
        self.assertEqual(catalog[0]["unit_of_measurement"], self.expected_unit)
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
