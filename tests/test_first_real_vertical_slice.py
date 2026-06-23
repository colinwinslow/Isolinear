import sys
import asyncio
import json
import tempfile
from copy import deepcopy
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
    retrieve_approved_history,
    setup_history_retrieval,
)
import custom_components.isolinear.history_retrieval as history_retrieval  # noqa: E402
from custom_components.isolinear.job_orchestration import (  # noqa: E402
    DATA_JOB_ORCHESTRATION_TIME_RANGE,
    resolve_history_window,
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


class SubstituteEntityPlanner(FakePlanner):
    """A planner that references an approved entity that was not disclosed."""

    def __init__(self, *, substitute_entity_id: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._substitute_entity_id = substitute_entity_id

    def plan_chart(self, request, *, result_schema=None):
        response = super().plan_chart(request, result_schema=result_schema)
        series = response["planner_result"]["chart_spec"]["series"][0]
        series["source"]["entity_id"] = self._substitute_entity_id
        series["label"] = self._substitute_entity_id
        return response


class TimelinePlanner(FakePlanner):
    """A planner that emits a binary timeline (step) chart spec for one entity."""

    def __init__(self, *, entity_id: str, time_range: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._entity_id = entity_id
        self._time_range = time_range or {"type": "relative", "duration": "24h"}

    def plan_chart(self, request, *, result_schema=None):
        self.calls.append(request)
        series_id = self._entity_id.replace(".", "_")
        chart_spec = {
            "chart_id": "real-slice-timeline",
            "chart_type": "timeline",
            "title": f"Timeline {self._entity_id}",
            "time_range": deepcopy(self._time_range),
            "series": [
                {
                    "series_id": series_id,
                    "label": self._entity_id,
                    "source": {"type": "entity", "entity_id": self._entity_id, "attribute": None},
                    "role": "primary",
                    "render_as": "step",
                    "transform": {"operation": "none", "window": None},
                    "unit": None,
                }
            ],
            "overlays": [],
            "x_axis": {"type": "time"},
            "y_axis": {},
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
                "reasoning_summary": "Door state over time.",
                "warnings": [],
            },
            "provider_response": {"model": "llama3.1", "done": True},
        }


def _binary_history_records(entity_id: str) -> list[dict[str, Any]]:
    start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=10)
    states = ["off", "on", "off", "on", "off"]
    return [
        {
            "entity_id": entity_id,
            "state": state,
            "last_changed": (start + timedelta(hours=2 * index)).isoformat(timespec="seconds"),
            "attributes": {"device_class": "door"},
        }
        for index, state in enumerate(states)
    ]


_DOOR_METADATA = {
    "binary_sensor.kitchen_door": {
        "friendly_name": "Kitchen Door",
        "device_class": "door",
        "attributes": {"friendly_name": "Kitchen Door", "device_class": "door"},
    }
}


class RenderFamilyRoutingTests(unittest.TestCase):
    def test_resolve_render_family_routes_by_series_kind(self):
        catalog = [
            {"entity_id": "sensor.temp", "domain": "sensor", "state_class": "measurement"},
            {"entity_id": "sensor.humidity", "domain": "sensor", "state_class": "measurement"},
            {"entity_id": "binary_sensor.door", "domain": "binary_sensor"},
        ]
        self.assertEqual(
            job_orchestration._resolve_render_family(catalog, ["sensor.temp"])["family"],
            "time_series",
        )
        self.assertEqual(
            job_orchestration._resolve_render_family(catalog, ["binary_sensor.door"])["family"],
            "timeline",
        )
        # One numeric + one binary composes into a numeric line + overlay.
        overlay_routing = job_orchestration._resolve_render_family(
            catalog, ["sensor.temp", "binary_sensor.door"]
        )
        self.assertEqual(overlay_routing["family"], "time_series_overlay")
        self.assertEqual(overlay_routing["numeric_entity_ids"], ["sensor.temp"])
        self.assertEqual(overlay_routing["categorical_entity_ids"], ["binary_sensor.door"])
        # Two numeric series + a binary stays ambiguous (no deterministic primary).
        self.assertEqual(
            job_orchestration._resolve_render_family(
                catalog, ["sensor.temp", "sensor.humidity", "binary_sensor.door"]
            )["family"],
            "mixed",
        )
        # A non-binary categorical mixed with numeric is NOT an overlay (it has no
        # "on" region to shade) — it stays ambiguous rather than shading nothing.
        catalog_cat = catalog + [{"entity_id": "sensor.washer_status", "domain": "sensor"}]
        self.assertEqual(
            job_orchestration._resolve_render_family(
                catalog_cat, ["sensor.temp", "sensor.washer_status"]
            )["family"],
            "mixed",
        )
        # All-binary multi-entity is still the timeline family (not overlay).
        self.assertEqual(
            job_orchestration._resolve_render_family(
                catalog_cat, ["binary_sensor.door", "sensor.washer_status"]
            )["family"],
            "timeline",
        )

    def test_timeline_planner_schema_locks_timeline_step(self):
        schema = load_planner_result_schema("timeline")
        chart_spec = schema["properties"]["chart_spec"]["properties"]
        self.assertEqual(chart_spec["chart_type"]["enum"], ["timeline"])
        self.assertEqual(
            chart_spec["series"]["items"]["properties"]["render_as"]["enum"],
            ["step"],
        )

    @staticmethod
    def _schema_entity_id_constraint(schema: dict) -> dict:
        return (
            schema["properties"]["chart_spec"]["properties"]["series"]["items"][
                "properties"
            ]["source"]["properties"]["entity_id"]
        )

    def test_planner_schema_pins_entity_id_to_disclosed_enum(self):
        # With disclosed entities the structured-output source.entity_id is
        # constrained to an enum, so the provider's constrained decoding cannot
        # reference an off-allowlist entity (ADR-0022, invariant #1).
        schema = load_planner_result_schema(
            "timeline", entity_ids=["binary_sensor.kitchen_door"]
        )
        self.assertEqual(
            self._schema_entity_id_constraint(schema),
            {"enum": ["binary_sensor.kitchen_door"]},
        )

    def test_planner_schema_dedupes_disclosure_and_defaults_to_free_string(self):
        pinned = load_planner_result_schema(
            "time_series", entity_ids=["sensor.a", "sensor.b", "sensor.a", "", None]
        )
        # Duplicates collapse deterministically; blanks/non-strings are dropped.
        self.assertEqual(
            self._schema_entity_id_constraint(pinned), {"enum": ["sensor.a", "sensor.b"]}
        )
        # No disclosure -> backward-compatible free string.
        unpinned = load_planner_result_schema("time_series")
        self.assertEqual(
            self._schema_entity_id_constraint(unpinned), {"type": "string"}
        )

    def test_timeline_flow_pins_schema_entity_enum_to_disclosed_entity(self):
        class RecordingTimelinePlanner(TimelinePlanner):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.result_schemas: list[dict] = []

            def plan_chart(self, request, *, result_schema=None):
                self.result_schemas.append(result_schema)
                return super().plan_chart(request, result_schema=result_schema)

        planner = RecordingTimelinePlanner(entity_id="binary_sensor.kitchen_door")
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(
                planner=planner,
                artifact_dir=artifact_dir,
                extra_metadata_by_entity=_DOOR_METADATA,
            )
            hass.data[DOMAIN][DATA_HISTORY_SOURCE]["binary_sensor.kitchen_door"] = _binary_history_records(
                "binary_sensor.kitchen_door"
            )
            start = _start_job(
                hass, entry, prompt="Show binary_sensor.kitchen_door for the last 24 hours"
            )
            _snapshot_job(hass, entry, start["snapshot"]["job_id"])

        self.assertEqual(len(planner.result_schemas), 1)
        self.assertEqual(
            self._schema_entity_id_constraint(planner.result_schemas[0]),
            {"enum": ["binary_sensor.kitchen_door"]},
        )

    def test_binary_prompt_renders_timeline_png(self):
        planner = TimelinePlanner(entity_id="binary_sensor.kitchen_door")
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(
                planner=planner,
                artifact_dir=artifact_dir,
                extra_metadata_by_entity=_DOOR_METADATA,
            )
            # Remove the numeric default entity so only the door is allowlisted/disclosed.
            hass.data[DOMAIN][DATA_HISTORY_SOURCE]["binary_sensor.kitchen_door"] = _binary_history_records(
                "binary_sensor.kitchen_door"
            )

            start = _start_job(
                hass,
                entry,
                prompt="Show binary_sensor.kitchen_door for the last 24 hours",
            )
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "complete", snapshot["snapshot"])
            image_url = snapshot["snapshot"]["chart"]["image_url"]
            self.assertTrue(image_url.startswith("/api/isolinear/artifacts/"), image_url)
            # The planner was given the timeline schema (deterministic routing).
            self.assertEqual(len(planner.calls), 1)
            png_files = list(artifact_dir.glob("*.png"))
            self.assertEqual(len(png_files), 1, png_files)
            self.assertEqual(png_files[0].read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_beyond_retention_binary_timeline_fails_closed(self):
        # A binary entity has no long-term statistics; a window older than
        # recorder retention has no raw states either, so the timeline fails
        # closed through the history-retrieval gate (ADR-0022 D3 / Scenario K).
        beyond = {
            "type": "absolute",
            "start": "2026-03-01T00:00:00+00:00",
            "end": "2026-03-08T00:00:00+00:00",
        }
        planner = TimelinePlanner(entity_id="binary_sensor.kitchen_door", time_range=beyond)
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(
                planner=planner,
                artifact_dir=artifact_dir,
                extra_metadata_by_entity=_DOOR_METADATA,
            )
            hass.data[DOMAIN][DATA_HISTORY_SOURCE]["binary_sensor.kitchen_door"] = _binary_history_records(
                "binary_sensor.kitchen_door"
            )
            start = _start_job(
                hass,
                entry,
                prompt="Show binary_sensor.kitchen_door in early March",
            )
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "failed")
            self.assertEqual(
                snapshot["snapshot"]["failure"]["code"],
                "no_long_term_statistics",
            )
            self.assertEqual(list(artifact_dir.glob("*.png")), [])

    def test_compose_binary_overlays_injects_shaded_intervals(self):
        chart_spec = {
            "chart_id": "c",
            "chart_type": "time_series",
            "title": "Temp",
            "time_range": {"type": "relative", "duration": "24h"},
            "series": [
                {
                    "series_id": "temp",
                    "label": "Temp",
                    "source": {"type": "entity", "entity_id": "sensor.upstairs_temperature", "attribute": None},
                    "role": "primary",
                    "render_as": "line",
                    "transform": {"operation": "none", "window": None},
                    "unit": "degF",
                }
            ],
            "overlays": [],
            "x_axis": {"type": "time"},
            "y_axis": {},
            "notes": [],
        }
        composed = job_orchestration._compose_binary_overlays(
            chart_spec,
            overlay_entity_ids=["binary_sensor.kitchen_door"],
            catalog_items=[{"entity_id": "binary_sensor.kitchen_door", "friendly_name": "Kitchen Door"}],
        )
        self.assertEqual(len(composed["overlays"]), 1)
        overlay = composed["overlays"][0]
        self.assertEqual(overlay["render_as"], "shaded_intervals")
        self.assertEqual(overlay["source"]["entity_id"], "binary_sensor.kitchen_door")
        self.assertEqual(overlay["active_values"], ["on"])
        self.assertEqual(overlay["label"], "Kitchen Door")
        # The original spec is not mutated.
        self.assertEqual(chart_spec["overlays"], [])

    def test_fuzzy_mixed_prompt_resolves_numeric_primary_plus_overlay(self):
        catalog = [
            {
                "entity_id": "sensor.living_room_temperature",
                "domain": "sensor",
                "state_class": "measurement",
                "friendly_name": "Living Room Temperature",
            },
            {
                "entity_id": "binary_sensor.living_room_ac",
                "domain": "binary_sensor",
                "friendly_name": "Living Room AC",
            },
        ]
        selection = job_orchestration.select_prompt_entity_ids(
            "show me the living room temperature and when the ac was running", catalog
        )
        self.assertTrue(selection["accepted"], selection)
        self.assertEqual(selection["source"], "numeric_with_overlay")
        self.assertEqual(selection["entity_ids"][0], "sensor.living_room_temperature")
        self.assertIn("binary_sensor.living_room_ac", selection["entity_ids"])

    def test_fuzzy_mixed_prompt_resolves_composite_despite_categorical_noise_match(self):
        # Fix: categorical entity matching a shared token ("kitchen") must not
        # block the numeric+binary composite detection path. Only the numeric
        # primary and binary entities are forwarded; the categorical is discarded.
        catalog = [
            {
                "entity_id": "sensor.kitchen_ecobee_current_temperature",
                "domain": "sensor",
                "unit_of_measurement": "°F",
                "friendly_name": "Kitchen Ecobee Current Temperature",
            },
            {
                "entity_id": "binary_sensor.kitchen_door",
                "domain": "binary_sensor",
                "friendly_name": "Kitchen Door",
            },
            {
                "entity_id": "climate.kitchen_ecobee",
                "domain": "climate",
                "friendly_name": "Kitchen Ecobee",
            },
        ]
        selection = job_orchestration.select_prompt_entity_ids(
            "show me the kitchen temperature yesterday and when the kitchen door was open",
            catalog,
        )
        self.assertTrue(selection["accepted"], selection)
        self.assertEqual(selection["source"], "numeric_with_overlay")
        self.assertEqual(selection["entity_ids"][0], "sensor.kitchen_ecobee_current_temperature")
        self.assertIn("binary_sensor.kitchen_door", selection["entity_ids"])
        self.assertNotIn("climate.kitchen_ecobee", selection["entity_ids"])

    def test_shared_word_prompt_picks_more_specific_entity(self):
        # ADR-0024 D1: "kitchen door" shares only "kitchen" with the ecobee but
        # matches "door" too, so the door wins without a clarification round-trip.
        catalog = [
            {
                "entity_id": "binary_sensor.kitchen_door",
                "domain": "binary_sensor",
                "friendly_name": "Kitchen Door",
            },
            {
                "entity_id": "climate.kitchen_ecobee",
                "domain": "climate",
                "friendly_name": "Kitchen Ecobee",
            },
        ]
        selection = job_orchestration.select_prompt_entity_ids(
            "show me when the kitchen door was open this morning", catalog
        )
        self.assertTrue(selection["accepted"], selection)
        self.assertEqual(selection["source"], "catalog_label_specificity")
        self.assertEqual(selection["entity_ids"], ["binary_sensor.kitchen_door"])

    def test_equally_specific_matches_still_clarify(self):
        # ADR-0024 D1: a top-score tie is genuine ambiguity and must still ask,
        # offering only the tied candidates.
        catalog = [
            {
                "entity_id": "climate.upstairs_thermostat",
                "domain": "climate",
                "friendly_name": "Upstairs Thermostat",
            },
            {
                "entity_id": "climate.downstairs_thermostat",
                "domain": "climate",
                "friendly_name": "Downstairs Thermostat",
            },
        ]
        selection = job_orchestration.select_prompt_entity_ids(
            "show thermostat history", catalog
        )
        self.assertFalse(selection["accepted"], selection)
        self.assertEqual(selection["code"], "entity_selection_requires_clarification")
        self.assertEqual(len(selection["options"]), 2)

    def test_explicit_mixed_prompt_renders_overlay_png(self):
        planner = FakePlanner()
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(
                planner=planner,
                artifact_dir=artifact_dir,
                extra_metadata_by_entity=_DOOR_METADATA,
            )
            hass.data[DOMAIN][DATA_HISTORY_SOURCE]["binary_sensor.kitchen_door"] = _binary_history_records(
                "binary_sensor.kitchen_door"
            )
            start = _start_job(
                hass,
                entry,
                prompt="Show sensor.upstairs_temperature binary_sensor.kitchen_door for the last 24 hours",
            )
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "complete", snapshot["snapshot"])
            self.assertEqual(len(planner.calls), 1)
            # The planner was disclosed only the numeric primary as a series.
            self.assertEqual(planner.calls[0]["approved_entity_ids"], ["sensor.upstairs_temperature"])

            store = _orchestration_store(hass, entry)
            render_plan = store["render_plans"][store["render_plan_order"][-1]]
            overlays = render_plan["chart_spec"]["overlays"]
            self.assertEqual(len(overlays), 1)
            self.assertEqual(overlays[0]["source"]["entity_id"], "binary_sensor.kitchen_door")
            self.assertEqual(overlays[0]["render_as"], "shaded_intervals")

            png_files = list(artifact_dir.glob("*.png"))
            self.assertEqual(len(png_files), 1, png_files)
            self.assertEqual(png_files[0].read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_two_numeric_plus_binary_fails_closed_with_mixed_code(self):
        # Two numeric series mixed with a binary entity has no deterministic
        # primary line, so it still fails closed (ADR-0022 D4 boundary).
        planner = FakePlanner()
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(
                planner=planner,
                artifact_dir=artifact_dir,
                extra_metadata_by_entity={
                    **_DOOR_METADATA,
                    "sensor.basement_temperature": {
                        "friendly_name": "Basement Temperature",
                        "device_class": "temperature",
                        "state_class": "measurement",
                        "unit_of_measurement": "degF",
                        "attributes": {"unit_of_measurement": "degF"},
                    },
                },
            )
            hass.data[DOMAIN][DATA_HISTORY_SOURCE]["binary_sensor.kitchen_door"] = _binary_history_records(
                "binary_sensor.kitchen_door"
            )
            start = _start_job(
                hass,
                entry,
                prompt=(
                    "Show sensor.upstairs_temperature sensor.basement_temperature "
                    "binary_sensor.kitchen_door for the last 24 hours"
                ),
            )
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "failed")
            self.assertEqual(
                snapshot["snapshot"]["failure"]["code"],
                "mixed_chart_composition_unsupported",
            )
            # Fails before the planner is called.
            self.assertEqual(len(planner.calls), 0)
            self.assertEqual(list(artifact_dir.glob("*.png")), [])


    def test_validate_chart_spec_contract_rejects_duplicate_series_sources(self):
        # A planner that returns two series from the same (entity_id, attribute)
        # source is always wrong — the renderer would draw two identical lanes.
        # This reproduces the "kitchen temperature mirrors door state" failure seen
        # when a constrained planner hallucinated a temperature label on a door sensor.
        chart_spec = {
            "chart_id": "duplicate_source_test",
            "chart_type": "timeline",
            "title": "Duplicate Source Test",
            "time_range": {"type": "absolute", "start": "2026-06-20T00:00:00+00:00", "end": "2026-06-21T00:00:00+00:00"},
            "series": [
                {
                    "series_id": "s1",
                    "label": "Kitchen Temperature",
                    "source": {"type": "entity", "entity_id": "binary_sensor.kitchen_door", "attribute": None},
                    "role": "primary",
                    "render_as": "step",
                    "transform": {"operation": "none", "window": None},
                    "unit": "temperature",
                },
                {
                    "series_id": "s2",
                    "label": "Kitchen Door Open/Closed",
                    "source": {"type": "entity", "entity_id": "binary_sensor.kitchen_door", "attribute": None},
                    "role": "secondary",
                    "render_as": "step",
                    "transform": {"operation": "none", "window": None},
                    "unit": None,
                },
            ],
        }
        result = job_orchestration.validate_chart_spec_contract(chart_spec)
        self.assertFalse(result["accepted"], result)
        self.assertEqual(result["code"], "invalid_chart_spec")
        self.assertIn("duplicates the source of series[0]", result["error"])


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
            self.assertEqual(artifact["render_metadata"]["renderer"], "in_process_pillow")
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
            self.assertEqual(artifact["render_metadata"]["renderer"], "in_process_pillow")
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
            # sensor.hidden_temperature is absent from the approved catalog → a
            # true allowlist breach, not a substitution (ADR-0022 disambiguation).
            self.assertEqual(
                snapshot["snapshot"]["failure"]["code"],
                "model_provider_referenced_unapproved_entity",
            )
            self.assertEqual(len(planner.calls), 1)
            self.assertFalse(snapshot["orchestration"]["chart_rendering_called"])

    def test_substituted_approved_but_undisclosed_entity_fails_with_substitution_code(self):
        # Two numeric entities are allowlisted, but only one is disclosed for a
        # given job. A planner that references the *other* approved entity is a
        # substitution, not an allowlist breach (ADR-0022 disambiguation).
        planner = SubstituteEntityPlanner(substitute_entity_id="sensor.basement_temperature")
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(
                planner=planner,
                artifact_dir=artifact_dir,
                extra_metadata_by_entity={
                    "sensor.basement_temperature": {
                        "friendly_name": "Basement Temperature",
                        "device_class": "temperature",
                        "state_class": "measurement",
                        "unit_of_measurement": "degF",
                        "area": "Basement",
                        "attributes": {
                            "friendly_name": "Basement Temperature",
                            "unit_of_measurement": "degF",
                        },
                    }
                },
            )
            start = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start["snapshot"]["job_id"])

            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "failed")
            self.assertEqual(snapshot["snapshot"]["failure"]["stage"], "model_provider_planning")
            self.assertEqual(
                snapshot["snapshot"]["failure"]["code"],
                "model_provider_substituted_entity",
            )
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
            "renderer": "in_process_pillow",
            "render_result": {
                "request_id": "forced-render-failure",
                "status": "failed",
                "image_id": None,
                "image_mime_type": None,
                "image_path": None,
                "error": {
                    "code": "in_process_renderer_failed",
                    "message": "Forced in-process renderer failure for the test.",
                    "details": {"exception_type": "ValueError"},
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

    def test_renderer_reports_dependency_unavailable_when_pillow_import_fails(self):
        request = {"request_id": "req-dependency-check"}
        with patch.object(
            in_process_renderer,
            "_unsupported_time_series_request",
            return_value=[],
        ), patch.object(
            in_process_renderer,
            "_render_time_series_png",
            side_effect=ModuleNotFoundError(
                "No module named 'PIL'", name="PIL"
            ),
        ):
            result = render_in_process_chart(request)

        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "renderer_dependency_unavailable")
        self.assertEqual(result["render_result"]["status"], "failed")
        error = result["render_result"]["error"]
        self.assertEqual(error["code"], "renderer_dependency_unavailable")
        self.assertEqual(error["details"]["exception_type"], "ModuleNotFoundError")
        self.assertEqual(error["details"]["missing_module"], "PIL")

    def test_renderer_dependency_unavailable_returns_card_facing_failed_snapshot(self):
        planner = FakePlanner()
        renderer_failure = {
            "accepted": False,
            "code": "renderer_dependency_unavailable",
            "renderer": "in_process_pillow",
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
                        "missing_module": "PIL",
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


def _varying_render_request(*, width: int = 1400, height: int = 800) -> dict[str, Any]:
    import math

    start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=44)
    points = [
        {
            "ts": (start + timedelta(hours=index)).isoformat(timespec="seconds"),
            "value": round(51 + 6 * math.sin(index / 24 * 2 * math.pi), 2),
            "raw_state": "x",
            "quality": "ok",
        }
        for index in range(48)
    ]
    return {
        "request_id": "legibility-anchor",
        "render_mode": "safe",
        "chart_spec": {
            "chart_id": "c",
            "chart_type": "time_series",
            "title": "Attic Temperature History",
            "series": [
                {
                    "series_id": "attic",
                    "label": "Attic Temperature",
                    "source": {
                        "type": "entity",
                        "entity_id": "sensor.attic_sensor_temperature",
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
            "notes": [],
        },
        "history_series": [
            {
                "series_id": "attic",
                "entity_id": "sensor.attic_sensor_temperature",
                "label": "Attic Temperature",
                "kind": "numeric",
                "unit": "degF",
                "points": points,
                "source_entity_ids": ["sensor.attic_sensor_temperature"],
                "warnings": [],
            }
        ],
        "derived_intervals": [],
        "output": {"format": "png", "width": width, "height": height},
        "theme": {},
        "codegen": None,
    }


class InProcessRendererLegibilityTests(unittest.TestCase):
    def _open(self, png_bytes: bytes):
        from io import BytesIO

        from PIL import Image

        return Image.open(BytesIO(png_bytes)).convert("RGB")

    def test_title_text_is_rendered_large_enough_for_mobile(self):
        result = render_in_process_chart(_varying_render_request())
        self.assertTrue(result["accepted"], result)
        image = self._open(result["png_bytes"])
        self.assertEqual(image.size, (1400, 800))

        # The title occupies the top band; its dark-ink height proves the font is
        # large in source pixels so it survives the ~4x downscale to a phone card.
        title_band = image.crop((0, 0, image.width, 110)).convert("L")
        binarized = title_band.point(lambda value: 255 if value < 110 else 0)
        bbox = binarized.getbbox()
        self.assertIsNotNone(bbox, "expected rendered title ink in the top band")
        title_ink_height = bbox[3] - bbox[1]
        self.assertGreaterEqual(
            title_ink_height,
            34,
            f"title ink height {title_ink_height}px is too small to read on mobile",
        )

    def test_statistics_series_renders_min_max_band(self):
        # A series whose points carry value_min/value_max paints a light band of
        # the tinted series color between the bounds, behind the mean line.
        request = _varying_render_request()
        points = request["history_series"][0]["points"]
        for point in points:
            point["value_min"] = point["value"] - 4
            point["value_max"] = point["value"] + 4
        request["history_series"][0]["source"] = "long_term_statistics"
        request["history_series"][0]["resolution"] = "daily"
        result = render_in_process_chart(request)
        self.assertTrue(result["accepted"], result)
        image = self._open(result["png_bytes"])
        band_tint = tuple(int(round(channel * 0.25 + 255 * 0.75)) for channel in (31, 119, 180))
        found = False
        pixels = image.load()
        for y in range(0, image.height, 2):
            for x in range(0, image.width, 2):
                if pixels[x, y] == band_tint:
                    found = True
                    break
            if found:
                break
        self.assertTrue(found, "expected min/max band tint in the rendered chart")

    def test_varying_series_is_plotted_across_full_plot_height(self):
        # Guards the "flat line / values not plotted" rendering failure mode: a
        # series that swings high and low must paint series-colored ink in both
        # the upper and lower bands of the plot, not collapse to one row.
        result = render_in_process_chart(_varying_render_request())
        image = self._open(result["png_bytes"])
        series_color = (31, 119, 180)
        upper = lower = False
        pixels = image.load()
        for y in range(image.height):
            for x in range(0, image.width, 3):
                if pixels[x, y] == series_color:
                    if y < image.height * 0.40:
                        upper = True
                    elif y > image.height * 0.60:
                        lower = True
            if upper and lower:
                break
        self.assertTrue(upper, "series ink missing from the upper plot band")
        self.assertTrue(lower, "series ink missing from the lower plot band")


def _binary_timeline_render_request(width: int = 1400, height: int = 800) -> dict[str, Any]:
    # A door that is closed, then open for a stretch, then closed again.
    start = datetime(2026, 6, 18, 0, 0, 0, tzinfo=timezone.utc)
    states = [
        ("off", 0),
        ("on", 6),
        ("off", 9),
        ("on", 14),
        ("off", 20),
    ]
    points = [
        {
            "ts": (start + timedelta(hours=hour)).isoformat(timespec="seconds"),
            "value": value,
            "raw_state": value,
            "quality": "ok",
        }
        for value, hour in states
    ]
    return {
        "request_id": "timeline-anchor",
        "render_mode": "safe",
        "chart_spec": {
            "chart_id": "c",
            "chart_type": "timeline",
            "title": "Kitchen Door State",
            "time_range": {
                "type": "absolute",
                "start": start.isoformat(timespec="seconds"),
                "end": (start + timedelta(hours=24)).isoformat(timespec="seconds"),
            },
            "series": [
                {
                    "series_id": "kitchen_door",
                    "label": "Kitchen Door",
                    "source": {
                        "type": "entity",
                        "entity_id": "binary_sensor.kitchen_door",
                        "attribute": None,
                    },
                    "role": "primary",
                    "render_as": "step",
                    "transform": {"operation": "none", "window": None},
                    "unit": None,
                }
            ],
            "overlays": [],
            "x_axis": {"type": "time"},
            "y_axis": {},
            "notes": [],
        },
        "history_series": [
            {
                "series_id": "kitchen_door",
                "entity_id": "binary_sensor.kitchen_door",
                "label": "Kitchen Door",
                "kind": "binary_state",
                "unit": None,
                "points": points,
                "source": "recorder_states",
                "resolution": "raw",
                "source_entity_ids": ["binary_sensor.kitchen_door"],
                "warnings": [],
            }
        ],
        "derived_intervals": [],
        "output": {"format": "png", "width": width, "height": height},
        "theme": {},
        "codegen": None,
    }


class InProcessTimelineRendererTests(unittest.TestCase):
    def _open(self, png_bytes: bytes):
        from io import BytesIO

        from PIL import Image

        return Image.open(BytesIO(png_bytes)).convert("RGB")

    def test_binary_timeline_renders_valid_png_with_on_regions(self):
        result = render_in_process_chart(_binary_timeline_render_request())
        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["render_result"]["status"], "success")
        self.assertEqual(result["render_result"]["render_metadata"]["codegen_attempts"], 0)
        self.assertEqual(result["render_result"]["render_metadata"]["series_plotted"], ["kitchen_door"])
        self.assertEqual(result["png_bytes"][:8], b"\x89PNG\r\n\x1a\n")

        image = self._open(result["png_bytes"])
        self.assertEqual(image.size, (1400, 800))
        # The "on" regions paint filled bars in the lane (series color #1f77b4).
        on_color = (31, 119, 180)
        on_pixels = sum(
            1
            for y in range(0, image.height, 4)
            for x in range(0, image.width, 4)
            if image.getpixel((x, y)) == on_color
        )
        self.assertGreater(on_pixels, 50, "expected filled on-regions in the timeline lane")

    def test_timeline_on_regions_match_open_intervals(self):
        from custom_components.isolinear.in_process_renderer import (
            _binary_on_regions,
            _BINARY_ON_VALUES,
        )

        request = _binary_timeline_render_request()
        history = request["history_series"][0]
        window_end = datetime(2026, 6, 18, 20, 0, 0, tzinfo=timezone.utc)
        regions = _binary_on_regions(history, _BINARY_ON_VALUES, window_end=window_end)
        # Door is on 06:00-09:00 and 14:00-20:00 (held to window end).
        spans = [((s.hour), (e.hour)) for s, e in regions]
        self.assertEqual(spans, [(6, 9), (14, 20)])

    def test_numeric_chart_spec_still_routes_to_line_renderer(self):
        # Regression guard: timeline dispatch must not capture numeric specs.
        result = render_in_process_chart(_varying_render_request())
        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["render_result"]["render_metadata"]["series_plotted"], ["attic"])

    def test_timeline_with_numeric_history_fails_closed(self):
        request = _binary_timeline_render_request()
        request["history_series"][0]["kind"] = "numeric"
        result = render_in_process_chart(request)
        self.assertFalse(result["accepted"], result)
        self.assertEqual(result["code"], "in_process_renderer_failed")


def _overlay_render_request(width: int = 1400, height: int = 800) -> dict[str, Any]:
    # Temperature line + AC-running shaded_intervals overlay (ADR-0022 D4/D5).
    import math

    start = datetime(2026, 6, 18, 0, 0, 0, tzinfo=timezone.utc)
    temp_points = [
        {
            "ts": (start + timedelta(hours=index)).isoformat(timespec="seconds"),
            "value": round(72 + 5 * math.sin(index / 24 * 2 * math.pi), 2),
            "raw_state": "x",
            "quality": "ok",
        }
        for index in range(25)
    ]
    ac_states = [("off", 0), ("on", 8), ("off", 12), ("on", 16), ("off", 21)]
    ac_points = [
        {
            "ts": (start + timedelta(hours=hour)).isoformat(timespec="seconds"),
            "value": value,
            "raw_state": value,
            "quality": "ok",
        }
        for value, hour in ac_states
    ]
    return {
        "request_id": "overlay-anchor",
        "render_mode": "safe",
        "chart_spec": {
            "chart_id": "c",
            "chart_type": "time_series",
            "title": "Living Room Temperature & AC",
            "time_range": {
                "type": "absolute",
                "start": start.isoformat(timespec="seconds"),
                "end": (start + timedelta(hours=24)).isoformat(timespec="seconds"),
            },
            "series": [
                {
                    "series_id": "temp",
                    "label": "Living Room Temperature",
                    "source": {"type": "entity", "entity_id": "sensor.living_room_temperature", "attribute": None},
                    "role": "primary",
                    "render_as": "line",
                    "transform": {"operation": "none", "window": None},
                    "unit": "degF",
                }
            ],
            "overlays": [
                {
                    "overlay_id": "overlay-001",
                    "label": "AC Running",
                    "source": {"type": "entity", "entity_id": "binary_sensor.ac", "attribute": None},
                    "render_as": "shaded_intervals",
                    "active_values": ["on"],
                }
            ],
            "x_axis": {"type": "time"},
            "y_axis": {"label": "degF"},
            "notes": [],
        },
        "history_series": [
            {
                "series_id": "temp",
                "entity_id": "sensor.living_room_temperature",
                "label": "Living Room Temperature",
                "kind": "numeric",
                "unit": "degF",
                "points": temp_points,
                "source_entity_ids": ["sensor.living_room_temperature"],
                "warnings": [],
            },
            {
                "series_id": "ac",
                "entity_id": "binary_sensor.ac",
                "label": "AC Running",
                "kind": "binary_state",
                "unit": None,
                "points": ac_points,
                "source": "recorder_states",
                "resolution": "raw",
                "source_entity_ids": ["binary_sensor.ac"],
                "warnings": [],
            },
        ],
        "derived_intervals": [],
        "output": {"format": "png", "width": width, "height": height},
        "theme": {},
        "codegen": None,
    }


class InProcessOverlayRendererTests(unittest.TestCase):
    def _open(self, png_bytes: bytes):
        from io import BytesIO

        from PIL import Image

        return Image.open(BytesIO(png_bytes)).convert("RGB")

    def test_numeric_line_with_binary_overlay_renders_band_and_line(self):
        result = render_in_process_chart(_overlay_render_request())
        self.assertTrue(result["accepted"], result)
        meta = result["render_result"]["render_metadata"]
        self.assertEqual(meta["series_plotted"], ["temp"])
        self.assertEqual(meta["overlays_plotted"], ["overlay-001"])
        self.assertEqual(meta["codegen_attempts"], 0)

        image = self._open(result["png_bytes"])
        pixels = image.load()
        overlay_tint = (255, 224, 178)
        line_color = (31, 119, 180)
        overlay_found = any(
            pixels[x, y] == overlay_tint
            for y in range(0, image.height, 3)
            for x in range(0, image.width, 3)
        )
        line_found = any(
            pixels[x, y] == line_color
            for y in range(0, image.height, 3)
            for x in range(0, image.width, 3)
        )
        self.assertTrue(overlay_found, "expected AC-on shaded band tint behind the line")
        self.assertTrue(line_found, "expected the temperature line drawn over the overlay")

    def test_overlay_with_unsupported_render_as_fails_closed(self):
        request = _overlay_render_request()
        request["chart_spec"]["overlays"][0]["render_as"] = "markers"
        result = render_in_process_chart(request)
        self.assertFalse(result["accepted"], result)
        self.assertEqual(result["code"], "unsupported_chart_spec")


NOW = datetime(2026, 6, 18, 12, 0, 0, tzinfo=timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


class AbsoluteWindowPlanner(FakePlanner):
    """A planner that resolves the window to a fixed absolute range."""

    def __init__(self, *, start: str, end: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._start = start
        self._end = end

    def plan_chart(self, request, *, result_schema=None):
        response = super().plan_chart(request, result_schema=result_schema)
        response["planner_result"]["chart_spec"]["time_range"] = {
            "type": "absolute",
            "start": self._start,
            "end": self._end,
        }
        return response


class ResolveHistoryWindowTests(unittest.TestCase):
    def _spec(self, start: Any, end: Any) -> dict[str, Any]:
        return {"time_range": {"type": "absolute", "start": start, "end": end}}

    def test_valid_absolute_window_is_honored(self):
        window = resolve_history_window(
            self._spec("2026-06-16T12:00:00+00:00", "2026-06-18T12:00:00+00:00"),
            now=NOW,
        )
        self.assertTrue(window["model_resolved"])
        self.assertEqual(window["start"], "2026-06-16T12:00:00+00:00")
        self.assertEqual(window["end"], "2026-06-18T12:00:00+00:00")
        self.assertEqual(window["warnings"], [])

    def test_future_end_is_clamped_to_now(self):
        window = resolve_history_window(
            self._spec("2026-06-17T12:00:00+00:00", "2026-06-20T00:00:00+00:00"),
            now=NOW,
        )
        self.assertTrue(window["model_resolved"])
        self.assertEqual(window["end"], _iso(NOW))
        self.assertIn("history_window_end_clamped_to_now", window["warnings"])

    def test_oversized_window_is_clamped_to_max(self):
        window = resolve_history_window(
            self._spec("2020-01-01T00:00:00+00:00", "2026-06-18T12:00:00+00:00"),
            now=NOW,
        )
        self.assertTrue(window["model_resolved"])
        span = datetime.fromisoformat(window["end"]) - datetime.fromisoformat(window["start"])
        self.assertEqual(span, timedelta(days=366))
        self.assertIn("history_window_span_clamped_to_max", window["warnings"])

    def test_inverted_window_falls_back_to_24h(self):
        window = resolve_history_window(
            self._spec("2026-06-18T12:00:00+00:00", "2026-06-16T12:00:00+00:00"),
            now=NOW,
        )
        self.assertFalse(window["model_resolved"])
        self.assertEqual(window["end"], _iso(NOW))
        self.assertEqual(window["start"], _iso(NOW - timedelta(hours=24)))

    def test_unparseable_window_falls_back_to_24h(self):
        window = resolve_history_window(self._spec("not-a-date", "also-bad"), now=NOW)
        self.assertFalse(window["model_resolved"])
        self.assertEqual(window["start"], _iso(NOW - timedelta(hours=24)))

    def test_naive_timestamps_are_treated_as_utc(self):
        # The model frequently returns naive ISO 8601 (no offset). These are
        # interpreted as UTC and honored, not rejected to the 24h fallback.
        window = resolve_history_window(
            self._spec("2026-06-17T12:00:00", "2026-06-18T12:00:00"),
            now=NOW,
        )
        self.assertTrue(window["model_resolved"])
        self.assertEqual(window["start"], "2026-06-17T12:00:00+00:00")
        self.assertEqual(window["end"], "2026-06-18T12:00:00+00:00")

    def test_parse_window_timestamp_attaches_utc_to_naive(self):
        parsed = job_orchestration._parse_window_timestamp("2026-06-22T04:49:00")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.tzinfo, timezone.utc)
        self.assertEqual(parsed.isoformat(), "2026-06-22T04:49:00+00:00")

    def test_relative_or_missing_range_falls_back_to_24h(self):
        self.assertFalse(
            resolve_history_window(
                {"time_range": {"type": "relative", "duration": "24h"}}, now=NOW
            )["model_resolved"]
        )
        self.assertFalse(resolve_history_window({}, now=NOW)["model_resolved"])


class HistoryTierSelectionTests(unittest.TestCase):
    def _tier(self, start: datetime, end: datetime):
        return history_retrieval._select_history_tier(start, end, now=NOW, keep_days=10)

    def test_recent_short_window_uses_raw(self):
        source, resolution, period, beyond = self._tier(NOW - timedelta(hours=12), NOW)
        self.assertEqual((source, resolution, period, beyond), ("recorder_states", "raw", None, False))

    def test_multi_day_window_uses_hourly_statistics(self):
        source, resolution, period, beyond = self._tier(NOW - timedelta(days=5), NOW)
        self.assertEqual((source, resolution, period), ("long_term_statistics", "hourly", "hour"))

    def test_long_window_uses_daily_statistics(self):
        source, resolution, period, beyond = self._tier(NOW - timedelta(days=90), NOW)
        self.assertEqual((source, resolution, period), ("long_term_statistics", "daily", "day"))
        self.assertTrue(beyond)

    def test_short_but_old_window_is_beyond_retention_hourly(self):
        source, resolution, period, beyond = self._tier(
            NOW - timedelta(days=30), NOW - timedelta(days=29)
        )
        self.assertEqual((source, resolution, period), ("long_term_statistics", "hourly", "hour"))
        self.assertTrue(beyond)


class TieredHistoryRetrievalTests(unittest.TestCase):
    def _hass(self):
        hass, entry = configured_real_slice_hass(planner=None)
        hass.data[DOMAIN][history_retrieval.DATA_RECORDER_KEEP_DAYS] = 10
        return hass, entry

    def test_beyond_retention_window_uses_statistics_with_band(self):
        hass, entry = self._hass()
        start = NOW - timedelta(days=20)
        end = NOW - timedelta(days=18)
        buckets = [
            {
                "start": _iso(start + timedelta(hours=index)),
                "mean": 70.0 + index,
                "min": 69.0 + index,
                "max": 72.0 + index,
            }
            for index in range(6)
        ]
        hass.data[DOMAIN][history_retrieval.DATA_STATISTICS_SOURCE] = {
            "sensor.upstairs_temperature": buckets
        }
        result = retrieve_approved_history(
            hass,
            entry,
            entity_ids=["sensor.upstairs_temperature"],
            start=_iso(start),
            end=_iso(end),
            now=NOW,
            allow_statistics=True,
        )
        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["data_source"]["source"], "long_term_statistics")
        series = result["history_series"][0]
        self.assertEqual(series["source"], "long_term_statistics")
        self.assertEqual(series["resolution"], "hourly")
        self.assertEqual(series["points"][0]["value_min"], 69.0)
        self.assertEqual(series["points"][0]["value_max"], 72.0)

    def test_beyond_retention_without_statistics_fails_closed(self):
        hass, entry = self._hass()
        start = NOW - timedelta(days=20)
        end = NOW - timedelta(days=18)
        hass.data[DOMAIN][history_retrieval.DATA_STATISTICS_SOURCE] = {}
        result = retrieve_approved_history(
            hass,
            entry,
            entity_ids=["sensor.upstairs_temperature"],
            start=_iso(start),
            end=_iso(end),
            now=NOW,
            allow_statistics=True,
        )
        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "no_long_term_statistics")
        self.assertIn(
            "sensor.upstairs_temperature",
            result["statistics_unavailable_entity_ids"],
        )

    def test_recent_window_uses_raw_recorder_states(self):
        hass, entry = self._hass()
        start = NOW - timedelta(hours=12)
        records = [
            {
                "entity_id": "sensor.upstairs_temperature",
                "state": str(70.0 + index),
                "last_changed": _iso(start + timedelta(hours=index)),
                "attributes": {"unit_of_measurement": "degF"},
            }
            for index in range(6)
        ]
        hass.data[DOMAIN][DATA_HISTORY_SOURCE] = {"sensor.upstairs_temperature": records}
        result = retrieve_approved_history(
            hass,
            entry,
            entity_ids=["sensor.upstairs_temperature"],
            start=_iso(start),
            end=_iso(NOW),
            now=NOW,
            allow_statistics=True,
        )
        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["data_source"]["source"], "recorder_states")
        series = result["history_series"][0]
        self.assertEqual(series["resolution"], "raw")
        self.assertNotIn("value_min", series["points"][0])


class ModelResolvedWindowEndToEndTests(unittest.TestCase):
    def _configure_now(self, hass):
        hass.data[DOMAIN][DATA_JOB_ORCHESTRATION_TIME_RANGE] = {"now": _iso(NOW)}

    def test_absolute_seasonal_window_renders_statistics_png(self):
        start = NOW - timedelta(days=90)
        end = NOW - timedelta(days=1)
        planner = AbsoluteWindowPlanner(start=_iso(start), end=_iso(end))
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(planner=planner, artifact_dir=artifact_dir)
            self._configure_now(hass)
            hass.data[DOMAIN][history_retrieval.DATA_RECORDER_KEEP_DAYS] = 10
            buckets = [
                {
                    "start": _iso(start + timedelta(days=index)),
                    "mean": 60.0 + index,
                    "min": 58.0 + index,
                    "max": 63.0 + index,
                }
                for index in range(80)
            ]
            hass.data[DOMAIN][history_retrieval.DATA_STATISTICS_SOURCE] = {
                "sensor.upstairs_temperature": buckets
            }

            start_result = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start_result["snapshot"]["job_id"])

            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "complete")
            image_url = snapshot["snapshot"]["chart"]["image_url"]
            self.assertTrue(image_url.endswith(".png"), image_url)
            artifact_path = artifact_dir / Path(image_url).name
            self.assertEqual(artifact_path.read_bytes()[:8], PNG_SIGNATURE)
            store = hass.data[DOMAIN][entry.entry_id]["history_retrieval"]
            self.assertEqual(store["series"][0]["source"], "long_term_statistics")
            self.assertEqual(store["series"][0]["resolution"], "daily")

    def test_beyond_retention_without_statistics_returns_failed_snapshot(self):
        start = NOW - timedelta(days=40)
        end = NOW - timedelta(days=39)
        planner = AbsoluteWindowPlanner(start=_iso(start), end=_iso(end))
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            hass, entry = configured_real_slice_hass(planner=planner, artifact_dir=artifact_dir)
            self._configure_now(hass)
            hass.data[DOMAIN][history_retrieval.DATA_RECORDER_KEEP_DAYS] = 10
            hass.data[DOMAIN][history_retrieval.DATA_STATISTICS_SOURCE] = {}

            start_result = _start_job(hass, entry)
            snapshot = _snapshot_job(hass, entry, start_result["snapshot"]["job_id"])

            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "failed")
            self.assertEqual(
                snapshot["snapshot"]["failure"]["stage"], "approved_history_retrieval"
            )
            self.assertEqual(
                snapshot["snapshot"]["failure"]["code"], "no_long_term_statistics"
            )
            self.assertEqual(list(artifact_dir.glob("*.png")), [])


class OllamaPlannerClientDebugLoggingTests(unittest.TestCase):
    """The real Ollama client logs request/response at DEBUG for diagnosis."""

    def _run_plan_chart(self, response_body: bytes):
        client = OllamaCompatiblePlannerClient(
            endpoint_url="http://localhost:11434",
            planner_model="gemma4:e4b",
        )

        sent: dict[str, bytes] = {}

        class _FakeResponse:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *exc):
                return False

            def read(self_inner):
                return response_body

        def _fake_urlopen(req, timeout=None):
            sent["body"] = req.data
            return _FakeResponse()

        request = {
            "prompt": "show me the kitchen door state over the last four hours",
            "approved_entity_ids": ["binary_sensor.kitchen_door"],
            "history_entity_ids": ["binary_sensor.kitchen_door"],
            "now": "2026-06-19T16:00:00+00:00",
            "time_zone": "UTC",
            "output_schema": "PlannerResult",
        }
        schema = load_planner_result_schema(
            "timeline", entity_ids=["binary_sensor.kitchen_door"]
        )
        with patch(
            "custom_components.isolinear.model_provider.urllib.request.urlopen",
            side_effect=_fake_urlopen,
        ):
            with self.assertLogs(
                "custom_components.isolinear.model_provider", level="DEBUG"
            ) as logs:
                result = client.plan_chart(request, result_schema=schema)
        return result, sent, "\n".join(logs.output)

    def test_plan_chart_logs_request_and_response_at_debug(self):
        content = json.dumps({"status": "chart_spec_ready", "chart_spec": {}})
        body = json.dumps({"message": {"role": "assistant", "content": content}, "done": True}).encode(
            "utf-8"
        )
        result, sent, log_text = self._run_plan_chart(body)

        self.assertTrue(result["accepted"], result)
        self.assertIn("Isolinear -> Ollama plan_chart request", log_text)
        self.assertIn("Isolinear <- Ollama plan_chart response", log_text)
        # The outgoing body carries the prompt + disclosed entity for inspection.
        self.assertIn("binary_sensor.kitchen_door", sent["body"].decode("utf-8"))
        # The response content is visible for diagnosing new chart families.
        self.assertIn("chart_spec_ready", log_text)


# ---------------------------------------------------------------------------
# Helpers for D2 tests
# ---------------------------------------------------------------------------

class _FakeEntitySelector:
    """A minimal planner stub with only select_entity; used for unit tests."""

    def __init__(self, *, selects: set[str]) -> None:
        self._selects = selects
        self.calls: list[dict[str, Any]] = []

    def provider_metadata(self) -> dict[str, str]:
        return {"type": "ollama_compatible", "role": "planner", "endpoint_url": "", "model": "test"}

    def select_entity(self, request: dict[str, Any], *, result_schema: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append(request)
        chosen = [eid for eid in request.get("candidate_entity_ids", []) if eid in self._selects]
        if chosen:
            return {
                "accepted": True,
                "code": "model_provider_entity_selection_received",
                "provider": self.provider_metadata(),
                "selection_result": {"status": "entity_selected", "entity_ids": chosen},
                "provider_response": {},
            }
        return {
            "accepted": True,
            "code": "model_provider_entity_selection_received",
            "provider": self.provider_metadata(),
            "selection_result": {"status": "clarification_needed"},
            "provider_response": {},
        }


class _AbstainingEntitySelector:
    """A planner stub that always returns clarification_needed from select_entity."""

    def provider_metadata(self) -> dict[str, str]:
        return {"type": "ollama_compatible", "role": "planner", "endpoint_url": "", "model": "test"}

    def select_entity(self, request: dict[str, Any], *, result_schema: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "accepted": True,
            "code": "model_provider_entity_selection_received",
            "provider": self.provider_metadata(),
            "selection_result": {"status": "clarification_needed"},
            "provider_response": {},
        }


class _D2FakePlanner(FakePlanner):
    """FakePlanner extended with select_entity support for D2 integration tests.

    ``selects``: the entity_id the selector picks, or None to abstain.
    """

    def __init__(self, *, selects: str | list[str] | None) -> None:
        super().__init__()
        if selects is None:
            self._selects: list[str] = []
        elif isinstance(selects, str):
            self._selects = [selects]
        else:
            self._selects = list(selects)
        self.select_calls: int = 0
        self.plan_calls: int = 0
        self.last_select_request: dict[str, Any] = {}

    def select_entity(
        self, request: dict[str, Any], *, result_schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.select_calls += 1
        self.last_select_request = request
        candidates = request.get("candidate_entity_ids", [])
        chosen = [eid for eid in self._selects if eid in candidates]
        if chosen:
            return {
                "accepted": True,
                "code": "model_provider_entity_selection_received",
                "provider": self.provider_metadata(),
                "selection_result": {"status": "entity_selected", "entity_ids": chosen},
                "provider_response": {},
            }
        return {
            "accepted": True,
            "code": "model_provider_entity_selection_received",
            "provider": self.provider_metadata(),
            "selection_result": {"status": "clarification_needed"},
            "provider_response": {},
        }

    def plan_chart(
        self, request: dict[str, Any], *, result_schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.plan_calls += 1
        return super().plan_chart(request, result_schema=result_schema)


_THERMOSTAT_METADATA = {
    "climate.upstairs_thermostat": {
        "friendly_name": "Upstairs Thermostat",
        "domain": "climate",
        "unit_of_measurement": "°F",
    },
    "climate.downstairs_thermostat": {
        "friendly_name": "Downstairs Thermostat",
        "domain": "climate",
        "unit_of_measurement": "°F",
    },
}


# ---------------------------------------------------------------------------
# D2 test class
# ---------------------------------------------------------------------------

class EntitySelectionD2Tests(unittest.TestCase):
    """ADR-0024 D2: model-driven entity selection on residual ambiguity."""

    def _tied_catalog(self) -> list[dict[str, Any]]:
        return [
            {"entity_id": "climate.upstairs_thermostat", "domain": "climate", "friendly_name": "Upstairs Thermostat"},
            {"entity_id": "climate.downstairs_thermostat", "domain": "climate", "friendly_name": "Downstairs Thermostat"},
        ]

    def _hass_with_planner(self, entry_id: str, planner: Any) -> FakeHass:
        hass = FakeHass()
        hass.data[DOMAIN].setdefault(entry_id, {})[DATA_MODEL_PROVIDER_PLANNER] = planner
        return hass

    # -- unit: select_prompt_entity_ids returns candidate_items ---------------

    def test_clarification_result_includes_candidate_items_on_tie(self):
        catalog = self._tied_catalog()
        result = job_orchestration.select_prompt_entity_ids("show thermostat history", catalog)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "entity_selection_requires_clarification")
        self.assertIn("candidate_items", result)
        candidate_ids = {item["entity_id"] for item in result["candidate_items"]}
        self.assertEqual(candidate_ids, {"climate.upstairs_thermostat", "climate.downstairs_thermostat"})

    def test_clarification_result_includes_candidate_items_on_zero_match(self):
        catalog = self._tied_catalog()
        result = job_orchestration.select_prompt_entity_ids("show humidity data", catalog)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "entity_selection_requires_clarification")
        self.assertIn("candidate_items", result)
        # Full catalog when zero matches
        self.assertEqual(len(result["candidate_items"]), 2)

    # -- unit: _run_model_entity_selection ------------------------------------

    def test_no_model_provider_returns_rejection(self):
        hass = FakeHass()
        result = job_orchestration._run_model_entity_selection(
            hass, "entry-1", "show thermostat history",
            catalog_items=self._tied_catalog(),
            candidate_items=self._tied_catalog(),
        )
        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "no_model_provider_for_entity_selection")

    def test_model_without_select_entity_returns_rejection(self):
        # A planner that only has plan_chart but not select_entity (e.g. FakePlanner)
        # should not cause an error — D2 is silently skipped.
        planner = FakePlanner()
        hass = self._hass_with_planner("entry-1", planner)
        result = job_orchestration._run_model_entity_selection(
            hass, "entry-1", "show thermostat history",
            catalog_items=self._tied_catalog(),
            candidate_items=self._tied_catalog(),
        )
        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "no_model_provider_for_entity_selection")

    def test_model_picks_valid_entity_accepted(self):
        catalog = self._tied_catalog()
        planner = _FakeEntitySelector(selects={"climate.upstairs_thermostat"})
        hass = self._hass_with_planner("entry-1", planner)
        result = job_orchestration._run_model_entity_selection(
            hass, "entry-1", "show upstairs thermostat history",
            catalog_items=catalog,
            candidate_items=catalog,
        )
        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["source"], "model_entity_selection")
        self.assertEqual(result["entity_ids"], ["climate.upstairs_thermostat"])

    def test_model_abstains_returns_rejection(self):
        catalog = self._tied_catalog()
        hass = self._hass_with_planner("entry-1", _AbstainingEntitySelector())
        result = job_orchestration._run_model_entity_selection(
            hass, "entry-1", "show thermostat history",
            catalog_items=catalog,
            candidate_items=catalog,
        )
        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "model_entity_selection_abstained")

    def test_model_picks_entity_not_in_candidate_set_fail_closed(self):
        # Simulates a model that bypasses the enum pin and returns an entity
        # outside the disclosed candidate set — the integration rejects it.
        catalog = self._tied_catalog()

        class _UnconstrainedSelector:
            def provider_metadata(self):
                return {"type": "ollama_compatible", "role": "planner", "endpoint_url": "", "model": "test"}

            def select_entity(self, request, *, result_schema=None):
                return {
                    "accepted": True,
                    "code": "model_provider_entity_selection_received",
                    "provider": self.provider_metadata(),
                    "selection_result": {"status": "entity_selected", "entity_ids": ["sensor.unlisted_entity"]},
                    "provider_response": {},
                }

        hass = self._hass_with_planner("entry-1", _UnconstrainedSelector())
        result = job_orchestration._run_model_entity_selection(
            hass, "entry-1", "show thermostat history",
            catalog_items=catalog,
            candidate_items=catalog,
        )
        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "model_entity_selection_out_of_allowlist")

    def test_model_picks_entity_not_in_allowlist_fail_closed(self):
        # Even if the entity was in the candidate list (shouldn't happen in practice),
        # it must also be in the full catalog (allowlist boundary).
        catalog = self._tied_catalog()
        planner = _FakeEntitySelector(selects={"climate.unlisted_thermostat"})
        hass = self._hass_with_planner("entry-1", planner)
        result = job_orchestration._run_model_entity_selection(
            hass, "entry-1", "show thermostat history",
            catalog_items=catalog,
            # Candidate not in catalog — should still fail closed
            candidate_items=catalog + [{"entity_id": "climate.unlisted_thermostat", "domain": "climate"}],
        )
        self.assertFalse(result["accepted"])
        self.assertEqual(result["code"], "model_entity_selection_out_of_allowlist")

    def test_selector_schema_pins_entity_ids_to_enum(self):
        from custom_components.isolinear.model_provider import load_entity_selector_schema
        schema = load_entity_selector_schema(["climate.upstairs_thermostat", "climate.downstairs_thermostat"])
        self.assertEqual(schema["type"], "object")
        self.assertIn("entity_selected", schema["properties"]["status"]["enum"])
        self.assertIn("clarification_needed", schema["properties"]["status"]["enum"])
        items_schema = schema["properties"]["entity_ids"]["items"]
        self.assertIn("enum", items_schema)
        self.assertIn("climate.upstairs_thermostat", items_schema["enum"])
        self.assertIn("climate.downstairs_thermostat", items_schema["enum"])

    # -- integration: full job/start → snapshot path -------------------------

    def test_tie_model_picks_proceeds_to_render(self):
        """Tie → model picks upstairs → renders without clarification (BDD Scenario A)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            planner = _D2FakePlanner(selects="climate.upstairs_thermostat")
            hass, entry = configured_real_slice_hass(
                planner=planner,
                artifact_dir=Path(temp_dir),
                extra_metadata_by_entity=_THERMOSTAT_METADATA,
            )
            start = _start_job(hass, entry, prompt="show thermostat history")
            self.assertTrue(start["accepted"], start)
            job_id = start["snapshot"]["job_id"]

            snapshot = _snapshot_job(hass, entry, job_id)
            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "complete", snapshot["snapshot"])
            # D2 selector called once; chart planner called once
            self.assertEqual(planner.select_calls, 1)
            self.assertEqual(planner.plan_calls, 1)
            # Model was offered both tied candidates
            self.assertIn(
                "climate.upstairs_thermostat",
                planner.last_select_request["candidate_entity_ids"],
            )
            self.assertIn(
                "climate.downstairs_thermostat",
                planner.last_select_request["candidate_entity_ids"],
            )

    def test_tie_model_abstains_clarification_shown(self):
        """Tie → model abstains → clarification snapshot (BDD Scenario B)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            planner = _D2FakePlanner(selects=None)
            hass, entry = configured_real_slice_hass(
                planner=planner,
                artifact_dir=Path(temp_dir),
                extra_metadata_by_entity=_THERMOSTAT_METADATA,
            )
            start = _start_job(hass, entry, prompt="show thermostat history")
            self.assertTrue(start["accepted"], start)
            self.assertEqual(start["snapshot"]["status"], "clarification_needed", start["snapshot"])
            option_ids = {o["option_id"] for o in start["snapshot"]["clarification"]["options"]}
            self.assertIn("climate_upstairs_thermostat", option_ids)
            self.assertIn("climate_downstairs_thermostat", option_ids)
            # Selector called; planner not called
            self.assertEqual(planner.select_calls, 1)
            self.assertEqual(planner.plan_calls, 0)

    def test_no_model_shows_clarification_without_selector_call(self):
        """No model provider → clarification immediately, no model call (BDD Scenario C)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            hass, entry = configured_real_slice_hass(
                planner=None,
                artifact_dir=Path(temp_dir),
                extra_metadata_by_entity=_THERMOSTAT_METADATA,
            )
            start = _start_job(hass, entry, prompt="show thermostat history")
            self.assertTrue(start["accepted"], start)
            self.assertEqual(start["snapshot"]["status"], "clarification_needed", start["snapshot"])

    def test_invalid_entity_from_model_falls_back_to_clarification(self):
        """Model returns off-allowlist entity → fail closed → clarification (BDD Scenario D)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            planner = _D2FakePlanner(selects="climate.secret_unlisted_entity")
            hass, entry = configured_real_slice_hass(
                planner=planner,
                artifact_dir=Path(temp_dir),
                extra_metadata_by_entity=_THERMOSTAT_METADATA,
            )
            start = _start_job(hass, entry, prompt="show thermostat history")
            self.assertTrue(start["accepted"], start)
            self.assertEqual(start["snapshot"]["status"], "clarification_needed", start["snapshot"])
            # Selector called; pick rejected; chart planner never reached
            self.assertEqual(planner.select_calls, 1)
            self.assertEqual(planner.plan_calls, 0)

    def test_zero_matches_model_picks_from_full_catalog(self):
        """Zero matches → D2 called with full catalog → model picks → renders (BDD Scenario E)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            planner = _D2FakePlanner(selects="sensor.upstairs_temperature")
            hass, entry = configured_real_slice_hass(
                planner=planner,
                artifact_dir=Path(temp_dir),
            )
            # "humidity" matches nothing in the default catalog
            start = _start_job(hass, entry, prompt="show humidity")
            self.assertTrue(start["accepted"], start)
            job_id = start["snapshot"]["job_id"]

            snapshot = _snapshot_job(hass, entry, job_id)
            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "complete", snapshot["snapshot"])
            self.assertEqual(planner.select_calls, 1)
            self.assertEqual(planner.plan_calls, 1)
            # Full catalog offered as candidates for zero-match case
            self.assertIn(
                "sensor.upstairs_temperature",
                planner.last_select_request["candidate_entity_ids"],
            )

    # -- D2 expansion (ADR-0024, 2026-06-23) ----------------------------------
    #
    # After a confident single-entity D1 result, D2 re-runs against the full
    # catalog to add concepts D1's token scoring missed (e.g. "AC").

    def _kitchen_catalog(self) -> list[dict[str, Any]]:
        return [
            {"entity_id": "sensor.kitchen_temperature", "domain": "sensor",
             "friendly_name": "Kitchen Temperature", "unit_of_measurement": "°F"},
            {"entity_id": "climate.kitchen_ecobee", "domain": "climate",
             "friendly_name": "Kitchen Ecobee"},
        ]

    def _confident_d1_selection(self) -> dict[str, Any]:
        # What select_prompt_entity_ids returns for "show kitchen temperature":
        # the temperature sensor uniquely outscores the climate entity.
        return {
            "accepted": True,
            "code": "accepted",
            "entity_ids": ["sensor.kitchen_temperature"],
            "source": "catalog_label_specificity",
        }

    def test_d1_confidently_resolves_then_misses_ac_concept(self):
        # Establishes the gap D2 expansion closes: D1 picks only the temp sensor.
        selection = job_orchestration.select_prompt_entity_ids(
            "show kitchen temperature and when the AC was running", self._kitchen_catalog()
        )
        self.assertTrue(selection["accepted"], selection)
        self.assertEqual(selection["entity_ids"], ["sensor.kitchen_temperature"])
        self.assertEqual(selection["source"], "catalog_label_specificity")

    def test_d2_expansion_adds_missed_entity(self):
        planner = _D2FakePlanner(selects=["sensor.kitchen_temperature", "climate.kitchen_ecobee"])
        hass = self._hass_with_planner("entry-1", planner)
        resolved = job_orchestration._resolve_entity_selection_with_model(
            hass, "entry-1", "show kitchen temperature and when the AC was running",
            self._kitchen_catalog(), self._confident_d1_selection(),
        )
        self.assertTrue(resolved["accepted"], resolved)
        self.assertEqual(resolved["source"], "model_entity_selection")
        self.assertEqual(
            set(resolved["entity_ids"]),
            {"sensor.kitchen_temperature", "climate.kitchen_ecobee"},
        )
        self.assertEqual(planner.select_calls, 1)
        # D2 was offered the full catalog and told what D1 had already picked.
        self.assertIn("climate.kitchen_ecobee", planner.last_select_request["candidate_entity_ids"])
        self.assertEqual(
            planner.last_select_request["already_selected_entity_ids"],
            ["sensor.kitchen_temperature"],
        )

    def test_d2_expansion_confirms_d1_unchanged(self):
        # Model validates the D1 pick and adds nothing — selection is preserved.
        planner = _D2FakePlanner(selects=["sensor.kitchen_temperature"])
        hass = self._hass_with_planner("entry-1", planner)
        resolved = job_orchestration._resolve_entity_selection_with_model(
            hass, "entry-1", "show kitchen temperature",
            self._kitchen_catalog(), self._confident_d1_selection(),
        )
        self.assertTrue(resolved["accepted"], resolved)
        self.assertEqual(resolved["entity_ids"], ["sensor.kitchen_temperature"])
        self.assertEqual(planner.select_calls, 1)

    def test_d2_expansion_falls_back_to_d1_when_model_abstains(self):
        planner = _D2FakePlanner(selects=None)
        hass = self._hass_with_planner("entry-1", planner)
        d1 = self._confident_d1_selection()
        resolved = job_orchestration._resolve_entity_selection_with_model(
            hass, "entry-1", "show kitchen temperature", self._kitchen_catalog(), d1,
        )
        # D1's confident answer stands; no clarification surfaced.
        self.assertEqual(resolved, d1)
        self.assertEqual(planner.select_calls, 1)

    def test_d2_expansion_off_catalog_pick_falls_back_to_d1(self):
        # Model returns an off-allowlist entity → fail closed → D1 result stands.
        planner = _D2FakePlanner(selects="sensor.unlisted_entity")
        hass = self._hass_with_planner("entry-1", planner)
        d1 = self._confident_d1_selection()
        resolved = job_orchestration._resolve_entity_selection_with_model(
            hass, "entry-1", "show kitchen temperature", self._kitchen_catalog(), d1,
        )
        self.assertEqual(resolved, d1)

    def test_d2_expansion_skipped_without_model(self):
        # Planner without select_entity → expansion silently skipped, no error.
        hass = self._hass_with_planner("entry-1", FakePlanner())
        d1 = self._confident_d1_selection()
        resolved = job_orchestration._resolve_entity_selection_with_model(
            hass, "entry-1", "show kitchen temperature", self._kitchen_catalog(), d1,
        )
        self.assertEqual(resolved, d1)

    def test_d2_expansion_skipped_for_explicit_entity_id(self):
        planner = _D2FakePlanner(selects=["climate.kitchen_ecobee"])
        hass = self._hass_with_planner("entry-1", planner)
        d1 = {"accepted": True, "code": "accepted",
              "entity_ids": ["sensor.kitchen_temperature"], "source": "explicit_entity_id"}
        resolved = job_orchestration._resolve_entity_selection_with_model(
            hass, "entry-1", "show sensor.kitchen_temperature", self._kitchen_catalog(), d1,
        )
        self.assertEqual(resolved, d1)
        self.assertEqual(planner.select_calls, 0)

    def test_d2_expansion_skipped_for_overlay_composition(self):
        planner = _D2FakePlanner(selects=["climate.kitchen_ecobee"])
        hass = self._hass_with_planner("entry-1", planner)
        d1 = {"accepted": True, "code": "accepted",
              "entity_ids": ["sensor.kitchen_temperature", "binary_sensor.kitchen_door"],
              "source": "numeric_with_overlay"}
        resolved = job_orchestration._resolve_entity_selection_with_model(
            hass, "entry-1", "kitchen temp and door", self._kitchen_catalog(), d1,
        )
        self.assertEqual(resolved, d1)
        self.assertEqual(planner.select_calls, 0)

    def test_d2_expansion_skipped_for_semantic_alias(self):
        # A user-confirmed alias already resolved the concept deterministically.
        planner = _D2FakePlanner(selects=["climate.kitchen_ecobee"])
        hass = self._hass_with_planner("entry-1", planner)
        d1 = {"accepted": True, "code": "accepted",
              "entity_ids": ["sensor.kitchen_temperature", "climate.kitchen_ecobee"],
              "source": "semantic_alias", "matched_alias_ids": ["whole_house_ac"]}
        resolved = job_orchestration._resolve_entity_selection_with_model(
            hass, "entry-1", "show kitchen temp and the AC", self._kitchen_catalog(), d1,
        )
        self.assertEqual(resolved, d1)
        self.assertEqual(planner.select_calls, 0)

    def test_d2_expansion_skipped_when_d1_covers_whole_catalog(self):
        # Single-entity catalog: nothing for the model to expand to → no call.
        planner = _D2FakePlanner(selects=["sensor.kitchen_temperature"])
        hass = self._hass_with_planner("entry-1", planner)
        catalog = [{"entity_id": "sensor.kitchen_temperature", "domain": "sensor",
                    "friendly_name": "Kitchen Temperature"}]
        d1 = self._confident_d1_selection()
        resolved = job_orchestration._resolve_entity_selection_with_model(
            hass, "entry-1", "show kitchen temperature", catalog, d1,
        )
        self.assertEqual(resolved, d1)
        self.assertEqual(planner.select_calls, 0)

    def test_d2_expansion_integration_renders_both_entities(self):
        """AC prompt: D1 picks temp sensor, D2 expands to include the climate
        entity, both flow to planning and render (ADR-0024 D2 expansion)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            planner = _D2FakePlanner(
                selects=["sensor.kitchen_temperature", "climate.kitchen_ecobee"]
            )
            hass, entry = configured_real_slice_hass(
                planner=planner,
                artifact_dir=Path(temp_dir),
                extra_metadata_by_entity={
                    "sensor.kitchen_temperature": {
                        "friendly_name": "Kitchen Temperature",
                        "device_class": "temperature", "state_class": "measurement",
                        "unit_of_measurement": "degF", "area": "Kitchen",
                    },
                    "climate.kitchen_ecobee": {
                        "friendly_name": "Kitchen Ecobee",
                        "state_class": "measurement", "unit_of_measurement": "degF",
                        "area": "Kitchen",
                    },
                },
            )
            start = _start_job(
                hass, entry,
                prompt="show kitchen temperature and when the AC was running",
            )
            self.assertTrue(start["accepted"], start)
            job_id = start["snapshot"]["job_id"]

            snapshot = _snapshot_job(hass, entry, job_id)
            self.assertTrue(snapshot["accepted"], snapshot)
            self.assertEqual(snapshot["snapshot"]["status"], "complete", snapshot["snapshot"])
            self.assertEqual(planner.select_calls, 1)
            self.assertEqual(planner.plan_calls, 1)
            # Both the directly-matched sensor and the D2-expanded climate entity
            # were forwarded to planning.
            planned_ids = set(planner.calls[0]["approved_entity_ids"])
            self.assertIn("sensor.kitchen_temperature", planned_ids)
            self.assertIn("climate.kitchen_ecobee", planned_ids)


if __name__ == "__main__":
    unittest.main(verbosity=2)
