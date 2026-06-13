import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from custom_components.isolinear.const import (  # noqa: E402
    COMMAND_GET_SNAPSHOT,
    COMMAND_START_JOB,
    DOMAIN,
    INTEGRATION_WS_VERSION,
)
from custom_components.isolinear.entity_catalog import setup_entity_catalog  # noqa: E402
from custom_components.isolinear.history_retrieval import (  # noqa: E402
    DATA_HISTORY_SOURCE,
    setup_history_retrieval,
)
from custom_components.isolinear.in_process_renderer import (  # noqa: E402
    DATA_FIRST_REAL_VERTICAL_SLICE_ENABLED,
    png_signature_from_data_url,
)
from custom_components.isolinear.job_orchestration import (  # noqa: E402
    DATA_JOB_ORCHESTRATION,
    setup_job_orchestration,
)
from custom_components.isolinear.job_state import ensure_job_state_store  # noqa: E402
from custom_components.isolinear.model_provider import DATA_MODEL_PROVIDER_PLANNER  # noqa: E402
from custom_components.isolinear.model_provider import load_planner_result_schema  # noqa: E402
from custom_components.isolinear.websocket_api import handle_registered_ws_command  # noqa: E402


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class FakeHass:
    def __init__(self) -> None:
        self.data: dict[str, Any] = {DOMAIN: {}}
        self.states: dict[str, Any] = {}


class FakeEntry:
    def __init__(self, entry_id: str) -> None:
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
            "entity_allowlist": ["sensor.upstairs_temperature"],
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
        entity_id = "sensor.hidden_temperature" if self.hidden_entity else "sensor.upstairs_temperature"
        chart_spec = {
            "chart_id": "real-slice-chart",
            "chart_type": "time_series",
            "title": "Real Slice Upstairs Temperature",
            "time_range": {"type": "relative", "duration": "24h"},
            "series": [
                {
                    "series_id": "sensor_upstairs_temperature",
                    "label": "Upstairs Temperature",
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


def configured_real_slice_hass(*, planner: FakePlanner) -> tuple[FakeHass, FakeEntry]:
    hass = FakeHass()
    entry = FakeEntry("real-slice-entry")
    entry_data = hass.data[DOMAIN].setdefault(entry.entry_id, {})
    entry_data["entry"] = entry
    entry_data[DATA_FIRST_REAL_VERTICAL_SLICE_ENABLED] = True
    entry_data[DATA_MODEL_PROVIDER_PLANNER] = planner
    hass.data[DOMAIN][DATA_HISTORY_SOURCE] = {
        "sensor.upstairs_temperature": _history_records("sensor.upstairs_temperature")
    }

    setup_entity_catalog(
        hass,
        entry,
        metadata_by_entity={
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
        },
    )
    setup_history_retrieval(hass, entry)
    ensure_job_state_store(hass, entry.entry_id)
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


def _start_job(hass: FakeHass, entry: FakeEntry) -> dict[str, Any]:
    return handle_registered_ws_command(
        hass,
        {
            "id": 1,
            "type": COMMAND_START_JOB,
            "version": INTEGRATION_WS_VERSION,
            "config_entry_id": entry.entry_id,
            "prompt": "Show sensor.upstairs_temperature for the last 24 hours",
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

    def test_prompt_returns_png_data_url_from_in_process_renderer(self):
        planner = FakePlanner()
        hass, entry = configured_real_slice_hass(planner=planner)

        start = _start_job(hass, entry)
        snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

        self.assertTrue(start["accepted"], start)
        self.assertTrue(snapshot["accepted"], snapshot)
        self.assertEqual(snapshot["snapshot"]["status"], "complete")
        self.assertEqual(png_signature_from_data_url(snapshot["snapshot"]["chart"]["image_url"]), PNG_SIGNATURE)
        self.assertEqual(planner.calls[0]["approved_entity_ids"], ["sensor.upstairs_temperature"])
        self.assertTrue(snapshot["orchestration"]["model_provider_called"])
        self.assertTrue(snapshot["orchestration"]["chart_rendering_called"])
        self.assertFalse(snapshot["orchestration"]["worker_called"])
        self.assertIn("in_process_render", snapshot["job_orchestration"])
        self.assertGreater(snapshot["job_orchestration"]["in_process_render"]["png_byte_count"], 1000)

        store = _orchestration_store(hass, entry)
        artifact = store["latest_artifact"]
        self.assertEqual(artifact["status"], "rendered")
        self.assertEqual(artifact["render_metadata"]["renderer"], "in_process_matplotlib")
        self.assertEqual(len(store["model_provider_plan_order"]), 1)
        self.assertEqual(len(store["render_plan_order"]), 1)
        self.assertEqual(len(store["artifact_order"]), 1)
        self.assertEqual(len(store["worker_dispatch_order"]), 0)

    def test_hidden_provider_entity_fails_before_render_and_artifact_storage(self):
        planner = FakePlanner(hidden_entity=True)
        hass, entry = configured_real_slice_hass(planner=planner)

        start = _start_job(hass, entry)
        snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

        self.assertFalse(snapshot["accepted"], snapshot)
        self.assertEqual(snapshot["code"], "model_provider_chart_spec_hidden_entity")
        self.assertEqual(len(planner.calls), 1)
        self.assertFalse(snapshot["orchestration"]["chart_rendering_called"])
        self.assertFalse(snapshot["orchestration"]["artifact_metadata_bookkeeping_written"])

        store = _orchestration_store(hass, entry)
        self.assertEqual(store["model_provider_plan_order"], [])
        self.assertEqual(store["render_plan_order"], [])
        self.assertEqual(store["artifact_order"], [])

    def test_repeated_snapshot_reuses_completed_png_artifact(self):
        planner = FakePlanner()
        hass, entry = configured_real_slice_hass(planner=planner)

        start = _start_job(hass, entry)
        first = _snapshot_job(hass, entry, start["snapshot"]["job_id"], message_id=2)
        second = _snapshot_job(hass, entry, start["snapshot"]["job_id"], message_id=3)

        self.assertTrue(first["accepted"], first)
        self.assertTrue(second["accepted"], second)
        self.assertEqual(len(planner.calls), 1)
        self.assertEqual(first["snapshot"], second["snapshot"])
        self.assertEqual(png_signature_from_data_url(second["snapshot"]["chart"]["image_url"]), PNG_SIGNATURE)

        store = _orchestration_store(hass, entry)
        self.assertEqual(len(store["model_provider_plan_order"]), 1)
        self.assertEqual(len(store["render_plan_order"]), 1)
        self.assertEqual(len(store["artifact_order"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
