import sys
import time
import tempfile
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
from custom_components.isolinear.artifact_serving import (  # noqa: E402
    ARTIFACT_STATIC_URL_PATH,
    setup_artifact_serving,
)
from custom_components.isolinear.entity_catalog import setup_entity_catalog  # noqa: E402
from custom_components.isolinear.history_retrieval import (  # noqa: E402
    DATA_HISTORY_SOURCE,
    setup_history_retrieval,
)
from custom_components.isolinear.in_process_renderer import (  # noqa: E402
    DATA_FIRST_REAL_VERTICAL_SLICE_ENABLED,
)
from custom_components.isolinear.job_orchestration import setup_job_orchestration  # noqa: E402
from custom_components.isolinear.job_state import ensure_job_state_store  # noqa: E402
from custom_components.isolinear.model_provider import DATA_MODEL_PROVIDER_PLANNER  # noqa: E402
from custom_components.isolinear.websocket_api import handle_registered_ws_command  # noqa: E402


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PROMPT = "Show sensor.upstairs_temperature for the last 24 hours"


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


class SlowSmokePlanner:
    def __init__(self) -> None:
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
        time.sleep(0.05)
        self.calls.append(request)
        return {
            "accepted": True,
            "code": "model_provider_planner_result_received",
            "provider": self.provider_metadata(),
            "planner_result": {
                "status": "chart_spec_ready",
                "chart_spec": {
                    "chart_id": "dashboard-card-long-running-smoke",
                    "chart_type": "time_series",
                    "title": "Browser Smoke Upstairs Temperature",
                    "time_range": {"type": "relative", "duration": "24h"},
                    "series": [
                        {
                            "series_id": "sensor_upstairs_temperature",
                            "label": "Upstairs Temperature",
                            "source": {
                                "type": "entity",
                                "entity_id": "sensor.upstairs_temperature",
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
                    "notes": ["dashboard_card_long_running_smoke"],
                },
                "clarification_question": None,
                "memory_proposals": [],
                "reasoning_summary": "Render the approved upstairs temperature history.",
                "warnings": [],
            },
            "provider_response": {"model": "llama3.1", "done": True},
        }


def configured_real_slice_hass(
    *,
    planner: SlowSmokePlanner,
    artifact_dir: Path,
) -> tuple[FakeHass, FakeEntry]:
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
    setup_artifact_serving(hass, entry, artifact_dir=artifact_dir)
    setup_job_orchestration(hass, entry)
    return hass, entry


def _history_records(entity_id: str) -> list[dict[str, Any]]:
    start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=4)
    return [
        {
            "entity_id": entity_id,
            "state": str(value),
            "last_changed": (start + timedelta(hours=index)).isoformat(timespec="seconds"),
            "attributes": {"unit_of_measurement": "degF"},
        }
        for index, value in enumerate((70.0, 70.6, 71.1, 71.8, 72.0))
    ]


class DashboardCardLongRunningSmokeTests(unittest.TestCase):
    def test_registered_websocket_start_then_snapshot_returns_png_for_card_polling(self):
        planner = SlowSmokePlanner()
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(planner=planner, artifact_dir=artifact_dir)

            start_message = {
                "id": 1,
                "type": COMMAND_START_JOB,
                "version": INTEGRATION_WS_VERSION,
                "config_entry_id": entry.entry_id,
                "prompt": PROMPT,
            }
            start = handle_registered_ws_command(hass, start_message)

            started_at = time.perf_counter()
            snapshot_message = {
                "id": 2,
                "type": COMMAND_GET_SNAPSHOT,
                "version": INTEGRATION_WS_VERSION,
                "config_entry_id": entry.entry_id,
                "job_id": start["snapshot"]["job_id"],
            }
            snapshot = handle_registered_ws_command(hass, snapshot_message)
            elapsed_ms = round((time.perf_counter() - started_at) * 1000)
            image_url = snapshot["snapshot"]["chart"]["image_url"]
            artifact_id = snapshot["job_orchestration"]["artifact"]["artifact_id"]
            artifact_path = artifact_dir / f"{artifact_id}.png"

            evidence = {
                "prompt": PROMPT,
                "elapsed_ms": elapsed_ms,
                "command_types": [start_message["type"], snapshot_message["type"]],
                "start_status": start["snapshot"]["status"],
                "snapshot_status": snapshot["snapshot"]["status"],
                "artifact_url": image_url,
                "artifact_path": str(artifact_path),
                "png_signature": list(artifact_path.read_bytes()[:8]),
                "planner_call_count": len(planner.calls),
                "approved_entity_ids": planner.calls[0]["approved_entity_ids"],
                "orchestration": snapshot["orchestration"],
            }
            print("REGISTERED_WS_SMOKE_EVIDENCE")
            print(evidence)

            self.assertTrue(start["accepted"], start)
            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(evidence["command_types"], [COMMAND_START_JOB, COMMAND_GET_SNAPSHOT])
            self.assertEqual(evidence["start_status"], "planning")
            self.assertEqual(evidence["snapshot_status"], "complete")
            self.assertTrue(evidence["artifact_url"].startswith(f"{ARTIFACT_STATIC_URL_PATH}/"))
            self.assertEqual(bytes(evidence["png_signature"]), PNG_SIGNATURE)
            self.assertGreaterEqual(evidence["elapsed_ms"], 50)
            self.assertEqual(evidence["planner_call_count"], 1)
            self.assertEqual(evidence["approved_entity_ids"], ["sensor.upstairs_temperature"])
            self.assertFalse(snapshot["orchestration"]["worker_called"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
