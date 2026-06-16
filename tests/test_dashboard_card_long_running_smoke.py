import sys
import threading
import time
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from custom_components.isolinear import job_orchestration as job_orchestration_module  # noqa: E402
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


class BlockingSmokePlanner(SlowSmokePlanner):
    def __init__(self) -> None:
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()

    def plan_chart(
        self,
        request: dict[str, Any],
        *,
        result_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.entered.set()
        if not self.release.wait(timeout=2):
            raise AssertionError("Timed out waiting to release blocking smoke planner.")
        return super().plan_chart(request, result_schema=result_schema)


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
    def test_artifact_snapshot_lock_creation_is_single_flight(self):
        store: dict[str, Any] = {"_artifact_snapshot_locks": {}}
        barrier = threading.Barrier(12)
        locks: list[Any] = []
        errors: list[BaseException] = []

        def get_lock() -> None:
            try:
                barrier.wait(timeout=2)
                locks.append(
                    job_orchestration_module._artifact_snapshot_lock_for_job(
                        store,
                        "job-smoke-001",
                    )
                )
            except BaseException as exc:  # pragma: no cover - re-raised in the test thread.
                errors.append(exc)

        threads = [threading.Thread(target=get_lock) for _ in range(12)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2)

        if errors:
            raise errors[0]
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(len(locks), 12)
        self.assertEqual(len({id(lock) for lock in locks}), 1)
        self.assertEqual(list(store["_artifact_snapshot_locks"].keys()), ["job-smoke-001"])

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

    def test_registered_snapshot_poll_is_single_flight_while_planner_is_running(self):
        planner = BlockingSmokePlanner()
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
            snapshot_message = {
                "id": 2,
                "type": COMMAND_GET_SNAPSHOT,
                "version": INTEGRATION_WS_VERSION,
                "config_entry_id": entry.entry_id,
                "job_id": start["snapshot"]["job_id"],
            }
            first_result: dict[str, Any] = {}

            def run_first_snapshot() -> None:
                try:
                    first_result["snapshot"] = handle_registered_ws_command(hass, snapshot_message)
                except Exception as exc:  # pragma: no cover - re-raised in the test thread.
                    first_result["exception"] = exc

            first_thread = threading.Thread(target=run_first_snapshot)
            first_thread.start()
            self.assertTrue(planner.entered.wait(timeout=2))

            in_progress = handle_registered_ws_command(
                hass,
                {
                    **snapshot_message,
                    "id": 3,
                },
            )

            planner.release.set()
            first_thread.join(timeout=10)
            self.assertFalse(first_thread.is_alive())
            if "exception" in first_result:
                raise first_result["exception"]
            first = first_result["snapshot"]

            final = handle_registered_ws_command(
                hass,
                {
                    **snapshot_message,
                    "id": 4,
                },
            )
            artifact_id = first["job_orchestration"]["artifact"]["artifact_id"]
            artifact_path = artifact_dir / f"{artifact_id}.png"

            evidence = {
                "in_progress_code": in_progress["job_state"]["code"],
                "in_progress_status": in_progress["snapshot"]["status"],
                "in_progress_stage": in_progress["snapshot"]["progress"]["stage"],
                "first_status": first["snapshot"]["status"],
                "final_status": final["snapshot"]["status"],
                "planner_call_count": len(planner.calls),
                "png_signature": list(artifact_path.read_bytes()[:8]),
            }
            print("REGISTERED_WS_SINGLE_FLIGHT_EVIDENCE")
            print(evidence)

            self.assertTrue(start["accepted"], start)
            self.assertTrue(in_progress["accepted"], in_progress)
            self.assertEqual(in_progress["job_state"]["code"], "job_orchestration_artifact_snapshot_in_progress")
            self.assertEqual(in_progress["snapshot"]["status"], "planning")
            self.assertEqual(first["snapshot"]["status"], "complete")
            self.assertEqual(final["snapshot"], first["snapshot"])
            self.assertEqual(len(planner.calls), 1)
            self.assertEqual(artifact_path.read_bytes()[:8], PNG_SIGNATURE)

    def test_registered_snapshot_poll_rechecks_completed_artifact_after_lock_acquire(self):
        planner = BlockingSmokePlanner()
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
            snapshot_message = {
                "id": 2,
                "type": COMMAND_GET_SNAPSHOT,
                "version": INTEGRATION_WS_VERSION,
                "config_entry_id": entry.entry_id,
                "job_id": start["snapshot"]["job_id"],
            }
            original_lock_for_job = job_orchestration_module._artifact_snapshot_lock_for_job
            lock_call_guard = threading.Lock()
            lock_call_count = 0
            second_lookup_paused = threading.Event()
            allow_second_lookup = threading.Event()

            def delayed_lock_for_job(store: dict[str, Any], job_id: str) -> threading.Lock:
                nonlocal lock_call_count
                with lock_call_guard:
                    lock_call_count += 1
                    call_number = lock_call_count
                if call_number == 2:
                    second_lookup_paused.set()
                    if not allow_second_lookup.wait(timeout=2):
                        raise AssertionError("Timed out waiting to resume second lock lookup.")
                return original_lock_for_job(store, job_id)

            first_result: dict[str, Any] = {}
            second_result: dict[str, Any] = {}

            def run_first_snapshot() -> None:
                try:
                    first_result["snapshot"] = handle_registered_ws_command(hass, snapshot_message)
                except Exception as exc:  # pragma: no cover - re-raised in the test thread.
                    first_result["exception"] = exc

            def run_second_snapshot() -> None:
                try:
                    second_result["snapshot"] = handle_registered_ws_command(
                        hass,
                        {
                            **snapshot_message,
                            "id": 3,
                        },
                    )
                except Exception as exc:  # pragma: no cover - re-raised in the test thread.
                    second_result["exception"] = exc

            job_orchestration_module._artifact_snapshot_lock_for_job = delayed_lock_for_job
            try:
                first_thread = threading.Thread(target=run_first_snapshot)
                first_thread.start()
                self.assertTrue(planner.entered.wait(timeout=2))

                second_thread = threading.Thread(target=run_second_snapshot)
                second_thread.start()
                self.assertTrue(second_lookup_paused.wait(timeout=2))

                planner.release.set()
                first_thread.join(timeout=10)
                self.assertFalse(first_thread.is_alive())
                allow_second_lookup.set()
                second_thread.join(timeout=10)
                self.assertFalse(second_thread.is_alive())
            finally:
                allow_second_lookup.set()
                planner.release.set()
                job_orchestration_module._artifact_snapshot_lock_for_job = original_lock_for_job

            if "exception" in first_result:
                raise first_result["exception"]
            if "exception" in second_result:
                raise second_result["exception"]
            first = first_result["snapshot"]
            second = second_result["snapshot"]

            evidence = {
                "second_job_state_code": second["job_state"]["code"],
                "first_status": first["snapshot"]["status"],
                "second_status": second["snapshot"]["status"],
                "planner_call_count": len(planner.calls),
                "lock_call_count": lock_call_count,
            }
            print("REGISTERED_WS_STALE_LOCK_RECHECK_EVIDENCE")
            print(evidence)

            self.assertTrue(start["accepted"], start)
            self.assertEqual(first["snapshot"]["status"], "complete")
            self.assertEqual(second["job_state"]["code"], "job_orchestration_artifact_snapshot_returned")
            self.assertEqual(second["snapshot"], first["snapshot"])
            self.assertEqual(len(planner.calls), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
