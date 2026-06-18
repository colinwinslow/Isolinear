import sys
import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from custom_components.isolinear.const import (  # noqa: E402
    COMMAND_ANSWER_CLARIFICATION,
    COMMAND_GET_SNAPSHOT,
    COMMAND_START_JOB,
    DOMAIN,
    INTEGRATION_WS_VERSION,
)
from custom_components.isolinear.artifact_serving import (  # noqa: E402
    ARTIFACT_STATIC_URL_PATH,
    async_setup_artifact_serving,
    setup_artifact_serving,
)
from custom_components.isolinear.entity_catalog import setup_entity_catalog  # noqa: E402
from custom_components.isolinear.history_retrieval import (  # noqa: E402
    DATA_HISTORY_SOURCE,
    setup_history_retrieval,
)
from custom_components.isolinear.in_process_renderer import (  # noqa: E402
    DATA_FIRST_REAL_VERTICAL_SLICE_ENABLED,
    render_in_process_chart,
)
import custom_components.isolinear.in_process_renderer as in_process_renderer  # noqa: E402
from custom_components.isolinear.job_orchestration import (  # noqa: E402
    DATA_JOB_ORCHESTRATION,
    setup_job_orchestration,
)
import custom_components.isolinear.job_orchestration as job_orchestration  # noqa: E402
from custom_components.isolinear.job_state import ensure_job_state_store  # noqa: E402
from custom_components.isolinear.model_provider import DATA_MODEL_PROVIDER_PLANNER  # noqa: E402
from custom_components.isolinear.model_provider import DATA_MODEL_PROVIDER_SETUP  # noqa: E402
from custom_components.isolinear.model_provider import OllamaCompatiblePlannerClient  # noqa: E402
from custom_components.isolinear.model_provider import load_planner_result_schema  # noqa: E402
from custom_components.isolinear.model_provider import setup_model_provider_planner  # noqa: E402
from custom_components.isolinear.websocket_api import handle_registered_ws_command  # noqa: E402


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class FakeHass:
    def __init__(self) -> None:
        self.data: dict[str, Any] = {DOMAIN: {}}
        self.states: dict[str, Any] = {}
        self.http = FakeHttp()


class FakeHttp:
    def __init__(self) -> None:
        self.static_path_calls: list[list[Any]] = []

    async def async_register_static_paths(self, paths: list[Any]) -> None:
        self.static_path_calls.append(paths)


class FakeEntry:
    def __init__(self, entry_id: str, *, entity_allowlist: list[str] | None = None) -> None:
        self.entry_id = entry_id
        self.data = {
            "model_provider_type": "ollama_compatible",
            "model_endpoint_url": "http://localhost:11434",
            "planner_model": "llama3.1",
            "codegen_model": None,
            "visual_validator_model": None,
            "worker_endpoint_url": "http://localhost:8765",
        }
        self.options = {
            "default_render_mode": "safe",
            "max_codegen_repair_attempts": 1,
            "entity_allowlist": entity_allowlist or ["sensor.upstairs_temperature"],
        }


class FakePlanner:
    def __init__(self, *, hidden_entity: bool = False) -> None:
        self.hidden_entity = hidden_entity
        self.calls: list[dict[str, Any]] = []

    def provider_metadata(self) -> dict[str, str]:
        return {
            "type": "ollama_compatible",
            "role": "planner",
            "endpoint_url": "http://localhost:11434",
            "model": "llama3.1",
        }

    def plan_chart(
        self,
        request: dict[str, Any],
        *,
        result_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append(request)
        approved_entity_ids = request.get("approved_entity_ids")
        selected_entity_id = (
            approved_entity_ids[0]
            if (
                isinstance(approved_entity_ids, list)
                and approved_entity_ids
                and isinstance(approved_entity_ids[0], str)
            )
            else "sensor.upstairs_temperature"
        )
        entity_id = "sensor.hidden_temperature" if self.hidden_entity else selected_entity_id
        series_id = entity_id.replace(".", "_")
        chart_spec = {
            "chart_id": "real-slice-chart",
            "chart_type": "time_series",
            "title": f"Real Slice {entity_id}",
            "time_range": {"type": "relative", "duration": "24h"},
            "series": [
                {
                    "series_id": series_id,
                    "label": entity_id,
                    "source": {
                        "type": "entity",
                        "entity_id": entity_id,
                        "attribute": None,
                    },
                    "role": "primary",
                    "render_as": "line",
                    "transform": {"operation": "none", "window": None},
                    "unit": "degF",
                }
            ],
            "overlays": [],
            "x_axis": {"type": "time"},
            "y_axis": {"label": "degF"},
            "notes": ["first_real_vertical_slice"],
        }
        return {
            "accepted": True,
            "code": "model_provider_planner_result_received",
            "provider": self.provider_metadata(),
            "planner_result": {
                "status": "chart_spec_ready",
                "chart_spec": chart_spec,
                "clarification_question": None,
                "memory_proposals": [],
                "reasoning_summary": "Use the approved upstairs temperature history.",
                "warnings": [],
            },
            "provider_response": {"model": "llama3.1", "done": True},
        }


class InvalidPlannerResultPlanner(FakePlanner):
    def plan_chart(
        self,
        request: dict[str, Any],
        *,
        result_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append(request)
        return {
            "accepted": True,
            "code": "model_provider_planner_result_received",
            "provider": self.provider_metadata(),
            "planner_result": {
                "status": "chart_spec_ready",
                "chart_spec": {
                    "chart_id": "invalid-real-slice-chart",
                    "chart_type": "time_series",
                },
                "clarification_question": None,
                "memory_proposals": [],
                "reasoning_summary": "Returned an intentionally incomplete chart spec.",
                "warnings": [],
            },
            "provider_response": {"model": "llama3.1", "done": True},
        }


def configured_real_slice_hass(
    *,
    planner: FakePlanner | None,
    artifact_dir: Path | None = None,
    extra_metadata_by_entity: dict[str, dict[str, Any]] | None = None,
) -> tuple[FakeHass, FakeEntry]:
    hass = FakeHass()
    metadata_by_entity = {
        "sensor.upstairs_temperature": {
            "friendly_name": "Upstairs Temperature",
            "device_class": "temperature",
            "state_class": "measurement",
            "unit_of_measurement": "degF",
            "area": "Upstairs",
            "attributes": {
                "friendly_name": "Upstairs Temperature",
                "unit_of_measurement": "degF",
            },
        }
    }
    metadata_by_entity.update(extra_metadata_by_entity or {})
    entry = FakeEntry("real-slice-entry", entity_allowlist=list(metadata_by_entity))
    entry_data = hass.data[DOMAIN].setdefault(entry.entry_id, {})
    entry_data["entry"] = entry
    entry_data[DATA_FIRST_REAL_VERTICAL_SLICE_ENABLED] = True
    if planner is not None:
        entry_data[DATA_MODEL_PROVIDER_PLANNER] = planner
    hass.data[DOMAIN][DATA_HISTORY_SOURCE] = {
        entity_id: _history_records(entity_id)
        for entity_id in metadata_by_entity
    }

    setup_entity_catalog(
        hass,
        entry,
        metadata_by_entity=metadata_by_entity,
    )
    setup_history_retrieval(hass, entry)
    ensure_job_state_store(hass, entry.entry_id)
    if artifact_dir is not None:
        setup_artifact_serving(hass, entry, artifact_dir=artifact_dir)
    setup_job_orchestration(hass, entry)
    return hass, entry


def _history_records(entity_id: str) -> list[dict[str, Any]]:
    start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=3)
    return [
        {
            "entity_id": entity_id,
            "state": str(value),
            "last_changed": (start + timedelta(hours=index)).isoformat(timespec="seconds"),
            "attributes": {"unit_of_measurement": "degF"},
        }
        for index, value in enumerate((70.0, 70.8, 71.3, 72.1))
    ]


def _start_job(
    hass: FakeHass,
    entry: FakeEntry,
    *,
    prompt: str = "Show sensor.upstairs_temperature for the last 24 hours",
) -> dict[str, Any]:
    return handle_registered_ws_command(
        hass,
        {
            "id": 1,
            "type": COMMAND_START_JOB,
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": entry.entry_id,
            "prompt": prompt,
        },
    )


def _answer_clarification(
    hass: FakeHass,
    entry: FakeEntry,
    snapshot: dict[str, Any],
    option_id: str,
    *,
    message_id: int = 2,
    remember: bool = False,
) -> dict[str, Any]:
    return handle_registered_ws_command(
        hass,
        {
            "id": message_id,
            "type": COMMAND_ANSWER_CLARIFICATION,
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": entry.entry_id,
            "job_id": snapshot["job_id"],
            "question_id": snapshot["clarification"]["question_id"],
            "option_id": option_id,
            "remember": remember,
        },
    )


def _snapshot_job(hass: FakeHass, entry: FakeEntry, job_id: str, *, message_id: int = 2) -> dict[str, Any]:
    return handle_registered_ws_command(
        hass,
        {
            "id": message_id,
            "type": COMMAND_GET_SNAPSHOT,
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": entry.entry_id,
            "job_id": job_id,
        },
    )


def _orchestration_store(hass: FakeHass, entry: FakeEntry) -> dict[str, Any]:
    return hass.data[DOMAIN][entry.entry_id][DATA_JOB_ORCHESTRATION]


class FirstRealVerticalSliceTests(unittest.TestCase):
    def test_ollama_structured_output_schema_embeds_chart_spec_contract(self):
        schema = load_planner_result_schema()

        chart_spec_schema = schema["properties"]["chart_spec"]

        self.assertIn("chart_id", chart_spec_schema["required"])
        self.assertIn("chart_type", chart_spec_schema["required"])
        self.assertEqual(chart_spec_schema["properties"]["chart_type"]["enum"], ["time_series"])
        self.assertEqual(
            chart_spec_schema["properties"]["series"]["items"]["required"],
            ["series_id", "label", "source", "role", "render_as", "transform", "unit"],
        )
        self.assertEqual(
            chart_spec_schema["properties"]["series"]["items"]["properties"]["source"]["properties"]["type"]["enum"],
            ["entity"],
        )

    def test_config_entry_setup_registers_artifact_static_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            hass = FakeHass()
            entry = FakeEntry("artifact-serving-entry")

            result = asyncio.run(
                async_setup_artifact_serving(hass, entry, artifact_dir=Path(temp_dir))
            )

            self.assertTrue(result["accepted"], result)
            self.assertEqual(result["static_path"]["url_path"], ARTIFACT_STATIC_URL_PATH)
            self.assertEqual(result["artifact_dir"], str(Path(temp_dir)))
            self.assertEqual(len(hass.http.static_path_calls), 1)

    def test_prompt_returns_served_png_artifact_from_in_process_renderer(self):
        planner = FakePlanner()
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(planner=planner, artifact_dir=artifact_dir)

            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertTrue(start["accepted"], start)
            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "complete")
            image_url = snapshot["snapshot"]["chart"]["image_url"]
            self.assertTrue(image_url.startswith(f"{ARTIFACT_STATIC_URL_PATH}/"), image_url)
            self.assertTrue(image_url.endswith(".png"), image_url)
            self.assertFalse(image_url.startswith("data:"), image_url)
            self.assertEqual(planner.calls[0]["approved_entity_ids"], ["sensor.upstairs_temperature"])
            self.assertTrue(snapshot["orchestration"]["model_provider_called"])
            self.assertTrue(snapshot["orchestration"]["chart_rendering_called"])
            self.assertTrue(snapshot["orchestration"]["chart_artifact_written"])
            self.assertFalse(snapshot["orchestration"]["worker_called"])
            self.assertIn("in_process_render", snapshot["job_orchestration"])
            in_process_render = snapshot["job_orchestration"]["in_process_render"]
            self.assertGreater(in_process_render["png_byte_count"], 1000)
            self.assertEqual(in_process_render["image_url"], image_url)
            self.assertNotIn("artifact_path", in_process_render)
            self.assertNotIn("image_path", in_process_render["render_result"])

            store = _orchestration_store(hass, entry)
            artifact = store["latest_artifact"]
            artifact_path = artifact_dir / f"{artifact['artifact_id']}.png"
            self.assertEqual(artifact["status"], "rendered")
            self.assertEqual(artifact["image_url"], image_url)
            self.assertEqual(artifact["render_metadata"]["renderer"], "in_process_matplotlib")
            self.assertTrue(artifact_path.is_file(), artifact)
            self.assertEqual(artifact_path.read_bytes()[:8], PNG_SIGNATURE)
            self.assertEqual(len(store["model_provider_plan_order"]), 1)
            self.assertEqual(len(store["render_plan_order"]), 1)
            self.assertEqual(len(store["artifact_order"]), 1)
            self.assertEqual(len(store["worker_dispatch_order"]), 0)

    def test_clarification_answer_returns_served_png_artifact_from_in_process_renderer(self):
        planner = FakePlanner()
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(
                planner=planner,
                artifact_dir=artifact_dir,
                extra_metadata_by_entity={
                    "sensor.downstairs_temperature": {
                        "friendly_name": "Downstairs Temperature",
                        "device_class": "temperature",
                        "state_class": "measurement",
                        "unit_of_measurement": "degF",
                        "area": "Downstairs",
                        "attributes": {
                            "friendly_name": "Downstairs Temperature",
                            "unit_of_measurement": "degF",
                        },
                    }
                },
            )

            start = _start_job(hass, entry, prompt="Show me the temperature")
            answer = _answer_clarification(
                hass,
                entry,
                start["snapshot"],
                "sensor_downstairs_temperature",
            )
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"], message_id=3)

            self.assertTrue(start["accepted"], start)
            self.assertEqual(start["snapshot"]["status"], "clarification_needed")
            self.assertTrue(answer["accepted"], answer)
            self.assertEqual(answer["snapshot"]["status"], "planning")
            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "complete")
            image_url = snapshot["snapshot"]["chart"]["image_url"]
            self.assertTrue(image_url.startswith(f"{ARTIFACT_STATIC_URL_PATH}/"), image_url)
            self.assertTrue(image_url.endswith(".png"), image_url)
            self.assertEqual(planner.calls[0]["approved_entity_ids"], ["sensor.downstairs_temperature"])
            self.assertEqual(
                snapshot["snapshot"]["chart"]["series"][0]["entity_id"],
                "sensor.downstairs_temperature",
            )
            self.assertNotIn(
                "placeholder chart metadata",
                snapshot["snapshot"]["validation"]["summary"],
            )
            self.assertTrue(snapshot["orchestration"]["model_provider_called"])
            self.assertTrue(snapshot["orchestration"]["chart_rendering_called"])
            self.assertTrue(snapshot["orchestration"]["chart_artifact_written"])

            store = _orchestration_store(hass, entry)
            artifact = store["latest_artifact"]
            artifact_path = artifact_dir / f"{artifact['artifact_id']}.png"
            self.assertEqual(artifact["status"], "rendered")
            self.assertEqual(artifact["render_metadata"]["renderer"], "in_process_matplotlib")
            self.assertTrue(artifact_path.is_file(), artifact)
            self.assertEqual(artifact_path.read_bytes()[:8], PNG_SIGNATURE)
            self.assertEqual(len(store["artifact_order"]), 1)

    def test_hidden_provider_entity_fails_before_render_and_artifact_storage(self):
        planner = FakePlanner(hidden_entity=True)
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(planner=planner, artifact_dir=artifact_dir)

            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "failed")
            self.assertEqual(snapshot["snapshot"]["failure"]["stage"], "model_provider_planning")
            self.assertEqual(snapshot["snapshot"]["failure"]["code"], "model_provider_chart_spec_hidden_entity")
            self.assertEqual(len(planner.calls), 1)
            self.assertFalse(snapshot["orchestration"]["chart_rendering_called"])
            self.assertFalse(snapshot["orchestration"]["chart_artifact_written"])
            self.assertFalse(snapshot["orchestration"]["artifact_metadata_bookkeeping_written"])

            store = _orchestration_store(hass, entry)
            self.assertEqual(store["model_provider_plan_order"], [])
            self.assertEqual(store["render_plan_order"], [])
            self.assertEqual(store["artifact_order"], [])
            self.assertEqual(list(artifact_dir.glob("*.png")), [])

    def test_real_slice_missing_planner_fails_before_placeholder_artifact_storage(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(planner=None, artifact_dir=artifact_dir)

            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertTrue(start["accepted"], start)
            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "failed")
            self.assertEqual(
                snapshot["snapshot"]["failure"]["code"],
                "model_provider_planner_not_configured",
            )
            self.assertFalse(snapshot["orchestration"]["model_provider_called"])
            self.assertFalse(snapshot["orchestration"]["chart_rendering_called"])
            self.assertFalse(snapshot["orchestration"]["chart_artifact_written"])
            self.assertFalse(snapshot["orchestration"]["artifact_metadata_bookkeeping_written"])

            store = _orchestration_store(hass, entry)
            self.assertEqual(store["model_provider_plan_order"], [])
            self.assertEqual(store["render_plan_order"], [])
            self.assertEqual(store["artifact_order"], [])
            self.assertEqual(list(artifact_dir.glob("*.png")), [])

    def test_real_slice_home_assistant_mapping_config_data_configures_planner_and_serves_png(self):
        planner = FakePlanner()
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(planner=None, artifact_dir=artifact_dir)
            entry.data = MappingProxyType(dict(entry.data))

            setup = setup_model_provider_planner(hass, entry)
            self.assertTrue(setup["accepted"], setup)
            self.assertEqual(setup["code"], "model_provider_planner_configured")
            self.assertEqual(setup["provider"]["model"], "llama3.1")
            self.assertEqual(
                hass.data[DOMAIN][entry.entry_id][DATA_MODEL_PROVIDER_SETUP]["code"],
                "model_provider_planner_configured",
            )

            with patch.object(
                OllamaCompatiblePlannerClient,
                "plan_chart",
                side_effect=planner.plan_chart,
            ):
                start = _start_job(hass, entry)
                snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            image_url = snapshot["snapshot"]["chart"]["image_url"]
            artifact_path = artifact_dir / image_url.rsplit("/", 1)[-1]

            self.assertTrue(start["accepted"], start)
            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "complete")
            self.assertTrue(image_url.startswith(ARTIFACT_STATIC_URL_PATH), image_url)
            self.assertEqual(artifact_path.read_bytes()[:8], PNG_SIGNATURE)
            self.assertEqual(len(planner.calls), 1)
            self.assertTrue(snapshot["orchestration"]["model_provider_called"])
            self.assertTrue(snapshot["orchestration"]["chart_rendering_called"])
            self.assertTrue(snapshot["orchestration"]["chart_artifact_written"])

    def test_artifact_metadata_validation_failure_leaves_no_png_file(self):
        planner = FakePlanner()
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(planner=planner, artifact_dir=artifact_dir)
            original_validate = job_orchestration.validate_artifact_metadata_contract

            def reject_rendered_artifact(artifact: Any) -> dict[str, Any]:
                if isinstance(artifact, dict) and artifact.get("status") == "rendered":
                    return {
                        "accepted": False,
                        "code": "invalid_integration_artifact_metadata",
                        "error": "forced rendered artifact validation failure",
                    }
                return original_validate(artifact)

            with patch.object(
                job_orchestration,
                "validate_artifact_metadata_contract",
                side_effect=reject_rendered_artifact,
            ):
                start = _start_job(hass, entry)
                snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertFalse(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["code"], "invalid_in_process_artifact_metadata")
            self.assertFalse(snapshot["orchestration"]["chart_artifact_written"])
            self.assertFalse(snapshot["orchestration"]["artifact_metadata_bookkeeping_written"])
            self.assertEqual(list(artifact_dir.glob("*.png")), [])

    def test_complete_snapshot_validation_failure_rolls_back_png_file(self):
        planner = FakePlanner()
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(planner=planner, artifact_dir=artifact_dir)
            original_append = job_orchestration.append_validated_job_snapshot

            def reject_complete_snapshot(job: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
                if kwargs.get("status") == "complete":
                    raise job_orchestration.JobStateSnapshotValidationError(
                        {
                            "accepted": False,
                            "code": "invalid_integration_job_snapshot",
                            "error": "forced complete snapshot validation failure",
                        }
                    )
                return original_append(job, **kwargs)

            with patch.object(
                job_orchestration,
                "append_validated_job_snapshot",
                side_effect=reject_complete_snapshot,
            ):
                start = _start_job(hass, entry)
                snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertFalse(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["code"], "invalid_integration_job_snapshot")
            self.assertFalse(snapshot["orchestration"]["chart_artifact_written"])
            self.assertEqual(list(artifact_dir.glob("*.png")), [])
            self.assertFalse(snapshot["orchestration"]["artifact_metadata_bookkeeping_written"])
            self.assertFalse(snapshot["orchestration"]["render_plan_bookkeeping_written"])
            self.assertFalse(snapshot["orchestration"]["model_provider_plan_bookkeeping_written"])

            store = _orchestration_store(hass, entry)
            self.assertEqual(store["model_provider_plan_order"], [])
            self.assertEqual(store["render_plan_order"], [])
            self.assertEqual(store["artifact_order"], [])
            self.assertEqual(store["model_provider_plans"], {})
            self.assertEqual(store["render_plans"], {})
            self.assertEqual(store["artifact_metadata"], {})
            self.assertEqual(store["model_provider_plan_by_job_id"], {})
            self.assertEqual(store["render_plan_by_job_id"], {})
            self.assertEqual(store["artifact_by_job_id"], {})
            self.assertIsNone(store["latest_model_provider_plan"])
            self.assertIsNone(store["latest_render_plan"])
            self.assertIsNone(store["latest_artifact"])

    def test_invalid_planner_result_returns_card_facing_failed_snapshot(self):
        planner = InvalidPlannerResultPlanner()
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(planner=planner, artifact_dir=artifact_dir)

            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertTrue(start["accepted"], start)
            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "failed")
            self.assertEqual(snapshot["snapshot"]["failure"]["stage"], "model_provider_planning")
            self.assertEqual(snapshot["snapshot"]["failure"]["code"], "invalid_model_provider_chart_spec")
            self.assertEqual(len(planner.calls), 1)
            self.assertTrue(snapshot["orchestration"]["model_provider_called"])
            self.assertFalse(snapshot["orchestration"]["chart_rendering_called"])
            self.assertFalse(snapshot["orchestration"]["chart_artifact_written"])
            self.assertEqual(list(artifact_dir.glob("*.png")), [])

    def test_in_process_renderer_failure_returns_card_facing_failed_snapshot(self):
        planner = FakePlanner()
        renderer_failure = {
            "accepted": False,
            "code": "in_process_renderer_failed",
            "renderer": "in_process_matplotlib",
            "render_result": {
                "request_id": "forced-render-failure",
                "status": "failed",
                "image_id": None,
                "image_mime_type": None,
                "image_path": None,
                "error": {
                    "code": "in_process_renderer_failed",
                    "message": "No module named matplotlib",
                    "details": {"exception_type": "ModuleNotFoundError"},
                },
                "render_metadata": {
                    "title": None,
                    "series_plotted": [],
                    "overlays_plotted": [],
                    "x_min": None,
                    "x_max": None,
                    "warnings": ["in_process_renderer_failed"],
                    "codegen_attempts": 0,
                },
            },
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(planner=planner, artifact_dir=artifact_dir)

            with patch.object(
                job_orchestration,
                "render_in_process_chart",
                return_value=renderer_failure,
            ):
                start = _start_job(hass, entry)
                snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertTrue(start["accepted"], start)
            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(
                snapshot["code"],
                "registered_job_state_command_accepted",
            )
            self.assertEqual(snapshot["snapshot"]["status"], "failed")
            self.assertEqual(snapshot["snapshot"]["failure"]["stage"], "chart_rendering")
            self.assertEqual(snapshot["snapshot"]["failure"]["code"], "in_process_renderer_failed")
            self.assertEqual(
                snapshot["snapshot"]["progress"]["stage"],
                "in_process_renderer_failure_snapshot_ready",
            )
            self.assertTrue(snapshot["orchestration"]["model_provider_called"])
            self.assertTrue(snapshot["orchestration"]["chart_rendering_called"])
            self.assertFalse(snapshot["orchestration"]["chart_artifact_written"])
            self.assertFalse(snapshot["orchestration"]["artifact_metadata_bookkeeping_written"])
            self.assertEqual(list(artifact_dir.glob("*.png")), [])

            store = _orchestration_store(hass, entry)
            self.assertEqual(store["model_provider_plan_order"], [])
            self.assertEqual(store["render_plan_order"], [])
            self.assertEqual(store["artifact_order"], [])

    def test_renderer_reports_dependency_unavailable_when_matplotlib_import_fails(self):
        request = {"request_id": "req-dependency-check"}
        with patch.object(
            in_process_renderer,
            "_unsupported_time_series_request",
            return_value=[],
        ), patch.object(
            in_process_renderer,
            "_render_time_series_png",
            side_effect=ModuleNotFoundError(
                "No module named 'matplotlib'", name="matplotlib"
            ),
        ):
            result = render_in_process_chart(request)

        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "renderer_dependency_unavailable")
        self.assertEqual(result["render_result"]["status"], "failed")
        error = result["render_result"]["error"]
        self.assertEqual(error["code"], "renderer_dependency_unavailable")
        self.assertEqual(error["details"]["exception_type"], "ModuleNotFoundError")
        self.assertEqual(error["details"]["missing_module"], "matplotlib")

    def test_renderer_dependency_unavailable_returns_card_facing_failed_snapshot(self):
        planner = FakePlanner()
        renderer_failure = {
            "accepted": False,
            "code": "renderer_dependency_unavailable",
            "renderer": "in_process_matplotlib",
            "render_result": {
                "request_id": "forced-dependency-failure",
                "status": "failed",
                "image_id": None,
                "image_mime_type": None,
                "image_path": None,
                "error": {
                    "code": "renderer_dependency_unavailable",
                    "message": (
                        "The trusted chart renderer dependency is not available "
                        "in this Home Assistant environment."
                    ),
                    "details": {
                        "exception_type": "ModuleNotFoundError",
                        "missing_module": "matplotlib",
                    },
                },
                "render_metadata": {
                    "title": None,
                    "series_plotted": [],
                    "overlays_plotted": [],
                    "x_min": None,
                    "x_max": None,
                    "warnings": ["renderer_dependency_unavailable"],
                    "codegen_attempts": 0,
                },
            },
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(planner=planner, artifact_dir=artifact_dir)

            with patch.object(
                job_orchestration,
                "render_in_process_chart",
                return_value=renderer_failure,
            ):
                start = _start_job(hass, entry)
                snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertTrue(start["accepted"], start)
            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "failed")
            self.assertEqual(snapshot["snapshot"]["failure"]["stage"], "chart_rendering")
            self.assertEqual(
                snapshot["snapshot"]["failure"]["code"],
                "renderer_dependency_unavailable",
            )
            self.assertEqual(
                snapshot["snapshot"]["progress"]["stage"],
                "in_process_renderer_failure_snapshot_ready",
            )
            self.assertTrue(snapshot["orchestration"]["chart_rendering_called"])
            self.assertFalse(snapshot["orchestration"]["chart_artifact_written"])
            self.assertEqual(list(artifact_dir.glob("*.png")), [])

    def test_repeated_snapshot_reuses_completed_png_artifact(self):
        planner = FakePlanner()
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(planner=planner, artifact_dir=artifact_dir)

            start = _start_job(hass, entry)
            first = _snapshot_job(hass, entry, start["snapshot"]["job_id"], message_id=2)
            second = _snapshot_job(hass, entry, start["snapshot"]["job_id"], message_id=3)

            self.assertTrue(first["accepted"], first)
            self.assertTrue(second["accepted"], second)
            self.assertEqual(len(planner.calls), 1)
            self.assertEqual(first["snapshot"], second["snapshot"])
            self.assertEqual(first["snapshot"]["chart"]["image_url"], second["snapshot"]["chart"]["image_url"])
            self.assertFalse(second["orchestration"]["chart_artifact_written"])

            store = _orchestration_store(hass, entry)
            artifact = store["latest_artifact"]
            artifact_path = artifact_dir / f"{artifact['artifact_id']}.png"
            self.assertEqual(artifact_path.read_bytes()[:8], PNG_SIGNATURE)
            self.assertEqual(len(list(artifact_dir.glob("*.png"))), 1)
            self.assertEqual(len(store["model_provider_plan_order"]), 1)
            self.assertEqual(len(store["render_plan_order"]), 1)
            self.assertEqual(len(store["artifact_order"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
