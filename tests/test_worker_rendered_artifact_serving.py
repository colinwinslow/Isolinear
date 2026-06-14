import base64
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from custom_components.isolinear.artifact_serving import (  # noqa: E402
    ARTIFACT_STATIC_URL_PATH,
    DATA_ARTIFACT_WRITES,
    setup_artifact_serving,
)
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
)
from custom_components.isolinear.job_orchestration import (  # noqa: E402
    DATA_JOB_ORCHESTRATION,
    setup_job_orchestration,
)
from custom_components.isolinear.job_state import ensure_job_state_store  # noqa: E402
from custom_components.isolinear.model_provider import DATA_MODEL_PROVIDER_PLANNER  # noqa: E402
from custom_components.isolinear.websocket_api import handle_registered_ws_command  # noqa: E402
from custom_components.isolinear.worker_renderer import DATA_WORKER_RENDER_CLIENT  # noqa: E402


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
WORKER_TEST_TOKEN = "worker-rendered-artifact-token-000000"
WORKER_PNG_BYTES = PNG_SIGNATURE + b"worker-rendered-artifact"
OVERSIZED_IMAGE_BYTES_BASE64_LENGTH = 2_667_001


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
            "worker_endpoint_url": "http://worker.local:8765",
        }
        self.options = {
            "default_render_mode": "safe",
            "max_codegen_repair_attempts": 1,
            "entity_allowlist": ["sensor.upstairs_temperature"],
        }


class FakePlanner:
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
        self.calls.append(request)
        return {
            "accepted": True,
            "code": "model_provider_planner_result_received",
            "provider": self.provider_metadata(),
            "planner_result": {
                "status": "chart_spec_ready",
                "chart_spec": {
                    "chart_id": "worker-rendered-real-slice-chart",
                    "chart_type": "time_series",
                    "title": "Worker Rendered Upstairs Temperature",
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
                    "notes": ["worker_rendered_artifact_serving"],
                },
                "clarification_question": None,
                "memory_proposals": [],
                "reasoning_summary": "Use the approved upstairs temperature history.",
                "warnings": [],
            },
            "provider_response": {"model": "llama3.1", "done": True},
        }


class FakeWorkerRenderer:
    provider_type = "http_json_worker"
    role = "renderer"
    api_version = 1

    def __init__(self, *, mode: str = "success") -> None:
        self.endpoint_url = "http://worker.local:8765"
        self.worker_token = WORKER_TEST_TOKEN
        self.mode = mode
        self.calls: list[dict[str, Any]] = []

    def provider_metadata(self) -> dict[str, Any]:
        return {
            "type": self.provider_type,
            "role": self.role,
            "endpoint_url": self.endpoint_url,
            "api_version": self.api_version,
        }

    def render_chart(self, transport_request: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"request": transport_request})
        render_request = transport_request["body"]["render_request"]
        if self.mode == "failed":
            return {
                "accepted": True,
                "code": "fake_worker_render_failed",
                "worker": self.provider_metadata(),
                "render_result": {
                    "request_id": render_request["request_id"],
                    "status": "failed",
                    "image_id": None,
                    "image_mime_type": None,
                    "image_path": None,
                    "error": {
                        "code": "worker_safe_renderer_failed",
                        "message": "Fake worker failed before a rendered artifact was accepted.",
                        "details": {},
                    },
                    "render_metadata": {},
                },
            }

        render_result = {
            "request_id": render_request["request_id"],
            "status": "success",
            "image_id": f"{render_request['request_id']}-image",
            "image_mime_type": "image/png",
            "image_path": f"worker://{render_request['request_id']}.png",
            "error": None,
            "render_metadata": {
                "title": render_request["chart_spec"]["title"],
                "series_plotted": [
                    series["series_id"]
                    for series in render_request["chart_spec"]["series"]
                ],
                "overlays_plotted": [],
                "warnings": ["fake_worker_renderer"],
                "codegen_attempts": 0,
            },
        }
        if self.mode == "oversized_bytes":
            render_result["image_bytes_base64"] = "A" * OVERSIZED_IMAGE_BYTES_BASE64_LENGTH
        elif self.mode != "missing_bytes":
            render_result["image_bytes_base64"] = base64.b64encode(WORKER_PNG_BYTES).decode("ascii")
        response = {
            "accepted": True,
            "code": "fake_worker_render_result",
            "worker": self.provider_metadata(),
            "render_result": render_result,
        }
        if self.mode == "invalid_progress":
            response["progress_events"] = "not-a-progress-event-list"
        return response


def configured_worker_artifact_hass(
    *,
    planner: FakePlanner,
    worker: FakeWorkerRenderer,
    artifact_dir: Path,
) -> tuple[FakeHass, FakeEntry]:
    hass = FakeHass()
    entry = FakeEntry("worker-real-slice-entry")
    entry_data = hass.data[DOMAIN].setdefault(entry.entry_id, {})
    entry_data["entry"] = entry
    entry_data[DATA_FIRST_REAL_VERTICAL_SLICE_ENABLED] = True
    entry_data[DATA_MODEL_PROVIDER_PLANNER] = planner
    entry_data[DATA_WORKER_RENDER_CLIENT] = worker
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


class WorkerRenderedArtifactServingTests(unittest.TestCase):
    def test_worker_png_bytes_are_written_as_served_artifact(self):
        planner = FakePlanner()
        worker = FakeWorkerRenderer()
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_worker_artifact_hass(
                planner=planner,
                worker=worker,
                artifact_dir=artifact_dir,
            )

            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertTrue(start["accepted"], start)
            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "complete")
            image_url = snapshot["snapshot"]["chart"]["image_url"]
            self.assertTrue(image_url.startswith(f"{ARTIFACT_STATIC_URL_PATH}/"), image_url)
            self.assertTrue(image_url.endswith(".png"), image_url)
            self.assertEqual(len(worker.calls), 1)
            self.assertEqual(
                worker.calls[0]["request"]["headers"]["authorization"],
                f"Bearer {WORKER_TEST_TOKEN}",
            )
            self.assertEqual(
                snapshot["job_orchestration"]["worker_dispatch"]["request"]["headers"]["authorization"],
                "Bearer <redacted>",
            )
            self.assertNotIn("image_bytes_base64", str(snapshot))
            self.assertNotIn("worker://", str(snapshot))
            self.assertNotIn(str(artifact_dir), str(snapshot))
            self.assertTrue(snapshot["orchestration"]["model_provider_called"])
            self.assertTrue(snapshot["orchestration"]["worker_called"])
            self.assertTrue(snapshot["orchestration"]["chart_rendering_called"])
            self.assertTrue(snapshot["orchestration"]["chart_artifact_written"])
            self.assertNotIn("in_process_render", snapshot["job_orchestration"])

            store = _orchestration_store(hass, entry)
            artifact = store["latest_artifact"]
            artifact_path = artifact_dir / f"{artifact['artifact_id']}.png"
            self.assertEqual(artifact["status"], "rendered")
            self.assertEqual(artifact["image_url"], image_url)
            self.assertEqual(artifact["render_metadata"]["renderer"], "worker_renderer")
            self.assertTrue(artifact["render_metadata"]["worker_called"])
            self.assertTrue(artifact_path.is_file(), artifact)
            self.assertEqual(artifact_path.read_bytes()[:8], PNG_SIGNATURE)
            self.assertEqual(len(store["worker_dispatch_order"]), 1)
            self.assertEqual(len(store["render_plan_order"]), 1)
            self.assertEqual(len(store["artifact_order"]), 1)
            self.assertEqual(len(hass.data[DOMAIN][entry.entry_id][DATA_ARTIFACT_WRITES]), 1)

            evidence = {
                "snapshot_status": snapshot["snapshot"]["status"],
                "artifact_url": image_url,
                "png_signature": list(artifact_path.read_bytes()[:8]),
                "worker_call_count": len(worker.calls),
                "worker_authorization_redacted": (
                    snapshot["job_orchestration"]["worker_dispatch"]["request"]["headers"]["authorization"]
                    == "Bearer <redacted>"
                ),
                "local_paths_exposed": str(artifact_dir) in str(snapshot),
                "worker_paths_exposed": "worker://" in str(snapshot),
                "orchestration": snapshot["orchestration"],
            }
            print("WORKER_RENDERED_ARTIFACT_EVIDENCE")
            print(evidence)

    def test_repeated_snapshot_reuses_worker_rendered_png(self):
        planner = FakePlanner()
        worker = FakeWorkerRenderer()
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_worker_artifact_hass(
                planner=planner,
                worker=worker,
                artifact_dir=artifact_dir,
            )

            start = _start_job(hass, entry)
            first = _snapshot_job(hass, entry, start["snapshot"]["job_id"], message_id=2)
            second = _snapshot_job(hass, entry, start["snapshot"]["job_id"], message_id=3)

            self.assertTrue(first["accepted"], first)
            self.assertTrue(second["accepted"], second)
            self.assertEqual(len(worker.calls), 1)
            self.assertEqual(first["snapshot"], second["snapshot"])
            self.assertFalse(second["orchestration"]["worker_called"])
            self.assertFalse(second["orchestration"]["chart_artifact_written"])

            store = _orchestration_store(hass, entry)
            artifact = store["latest_artifact"]
            artifact_path = artifact_dir / f"{artifact['artifact_id']}.png"
            self.assertEqual(artifact_path.read_bytes()[:8], PNG_SIGNATURE)
            self.assertEqual(len(list(artifact_dir.glob("*.png"))), 1)
            self.assertEqual(len(store["worker_dispatch_order"]), 1)
            self.assertEqual(len(store["render_plan_order"]), 1)
            self.assertEqual(len(store["artifact_order"]), 1)

    def test_missing_worker_image_bytes_fail_before_artifact_storage(self):
        planner = FakePlanner()
        worker = FakeWorkerRenderer(mode="missing_bytes")
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_worker_artifact_hass(
                planner=planner,
                worker=worker,
                artifact_dir=artifact_dir,
            )

            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "failed")
            self.assertEqual(snapshot["snapshot"]["failure"]["code"], "missing_worker_image_bytes")
            self.assertEqual(snapshot["snapshot"]["failure"]["stage"], "worker_render")
            self.assertTrue(snapshot["orchestration"]["worker_called"])
            self.assertTrue(snapshot["orchestration"]["chart_rendering_called"])
            self.assertFalse(snapshot["orchestration"]["chart_artifact_written"])
            self.assertFalse(snapshot["orchestration"]["artifact_metadata_bookkeeping_written"])
            self.assertFalse(snapshot["orchestration"]["render_plan_bookkeeping_written"])
            self.assertFalse(snapshot["orchestration"]["worker_dispatch_bookkeeping_written"])

            store = _orchestration_store(hass, entry)
            self.assertEqual(store["artifact_order"], [])
            self.assertEqual(store["render_plan_order"], [])
            self.assertEqual(store["worker_dispatch_order"], [])
            self.assertEqual(list(artifact_dir.glob("*.png")), [])

    def test_failed_worker_render_result_does_not_write_artifact(self):
        planner = FakePlanner()
        worker = FakeWorkerRenderer(mode="failed")
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_worker_artifact_hass(
                planner=planner,
                worker=worker,
                artifact_dir=artifact_dir,
            )

            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "failed")
            self.assertEqual(snapshot["snapshot"]["failure"]["code"], "worker_safe_renderer_failed")
            self.assertFalse(snapshot["orchestration"]["chart_artifact_written"])
            self.assertFalse(snapshot["orchestration"]["artifact_metadata_bookkeeping_written"])
            self.assertEqual(list(artifact_dir.glob("*.png")), [])

    def test_oversized_worker_image_bytes_fail_schema_before_decode_or_write(self):
        planner = FakePlanner()
        worker = FakeWorkerRenderer(mode="oversized_bytes")
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_worker_artifact_hass(
                planner=planner,
                worker=worker,
                artifact_dir=artifact_dir,
            )

            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertFalse(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["code"], "invalid_worker_render_result")
            self.assertTrue(snapshot["orchestration"]["worker_called"])
            self.assertTrue(snapshot["orchestration"]["chart_rendering_called"])
            self.assertFalse(snapshot["orchestration"]["chart_artifact_written"])

            store = _orchestration_store(hass, entry)
            self.assertEqual(store["artifact_order"], [])
            self.assertEqual(store["render_plan_order"], [])
            self.assertEqual(store["worker_dispatch_order"], [])
            self.assertEqual(hass.data[DOMAIN][entry.entry_id].get(DATA_ARTIFACT_WRITES, {}), {})
            self.assertEqual(list(artifact_dir.glob("*.png")), [])

    def test_invalid_worker_progress_rolls_back_written_png(self):
        planner = FakePlanner()
        worker = FakeWorkerRenderer(mode="invalid_progress")
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_worker_artifact_hass(
                planner=planner,
                worker=worker,
                artifact_dir=artifact_dir,
            )

            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertFalse(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["code"], "invalid_integration_worker_progress")
            self.assertTrue(snapshot["orchestration"]["worker_called"])
            self.assertTrue(snapshot["orchestration"]["chart_rendering_called"])
            self.assertFalse(snapshot["orchestration"]["chart_artifact_written"])

            store = _orchestration_store(hass, entry)
            self.assertEqual(store["artifact_order"], [])
            self.assertEqual(store["render_plan_order"], [])
            self.assertEqual(store["worker_dispatch_order"], [])
            self.assertEqual(store["worker_progress_event_order"], [])
            self.assertEqual(hass.data[DOMAIN][entry.entry_id].get(DATA_ARTIFACT_WRITES, {}), {})
            self.assertEqual(list(artifact_dir.glob("*.png")), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
