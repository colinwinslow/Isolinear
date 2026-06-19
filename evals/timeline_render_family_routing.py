"""Eval: deterministic render-family routing + categorical timeline (ADR-0022).

Exercises the pre-planning `_series_kind` routing (numeric -> time_series,
binary/categorical -> timeline, mixed -> fail closed), the shared
`_binary_on_regions` primitive, and a standalone binary timeline render,
emitting CASE evidence. No live model or recorder is required.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from custom_components.isolinear.job_orchestration import _resolve_render_family  # noqa: E402
from custom_components.isolinear.model_provider import load_planner_result_schema  # noqa: E402
from custom_components.isolinear.in_process_renderer import (  # noqa: E402
    _BINARY_ON_VALUES,
    _binary_on_regions,
    render_in_process_chart,
)


NOW = datetime(2026, 6, 18, 12, 0, 0, tzinfo=timezone.utc)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Expected {expected!r} but got {actual!r}.")


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


CATALOG = [
    {"entity_id": "sensor.attic_temperature", "domain": "sensor", "state_class": "measurement"},
    {"entity_id": "binary_sensor.kitchen_door", "domain": "binary_sensor"},
    {"entity_id": "sensor.washer_status", "domain": "sensor"},
]


def _binary_history():
    start = datetime(2026, 6, 18, 0, 0, 0, tzinfo=timezone.utc)
    states = [("off", 0), ("on", 6), ("off", 9), ("on", 14), ("off", 20)]
    return {
        "series_id": "kitchen_door",
        "entity_id": "binary_sensor.kitchen_door",
        "label": "Kitchen Door",
        "kind": "binary_state",
        "unit": None,
        "points": [
            {
                "ts": (start + timedelta(hours=hour)).isoformat(timespec="seconds"),
                "value": value,
                "raw_state": value,
                "quality": "ok",
            }
            for value, hour in states
        ],
        "source": "recorder_states",
        "resolution": "raw",
        "source_entity_ids": ["binary_sensor.kitchen_door"],
        "warnings": [],
    }


def main() -> None:
    # --- Deterministic routing ---
    numeric = _resolve_render_family(CATALOG, ["sensor.attic_temperature"])
    binary = _resolve_render_family(CATALOG, ["binary_sensor.kitchen_door"])
    categorical = _resolve_render_family(CATALOG, ["sensor.washer_status"])
    mixed = _resolve_render_family(CATALOG, ["sensor.attic_temperature", "binary_sensor.kitchen_door"])
    assert_equal(numeric["family"], "time_series", "Numeric entity routes to time_series.")
    assert_equal(binary["family"], "timeline", "Binary entity routes to timeline.")
    assert_equal(categorical["family"], "timeline", "Categorical entity routes to timeline.")
    assert_equal(mixed["family"], "mixed", "Mixed numeric+binary routes to mixed (fail closed).")

    ts_schema = load_planner_result_schema("time_series")["properties"]["chart_spec"]["properties"]
    tl_schema = load_planner_result_schema("timeline")["properties"]["chart_spec"]["properties"]
    assert_equal(ts_schema["chart_type"]["enum"], ["time_series"], "time_series schema locks chart_type.")
    assert_equal(tl_schema["chart_type"]["enum"], ["timeline"], "timeline schema locks chart_type.")
    assert_equal(
        tl_schema["series"]["items"]["properties"]["render_as"]["enum"],
        ["step"],
        "timeline schema locks render_as to step.",
    )

    print_case(
        "deterministic_render_family_routing",
        given={"catalog_kinds": {item["entity_id"]: item.get("domain") for item in CATALOG}},
        when={"operation": "_resolve_render_family + load_planner_result_schema"},
        then={
            "numeric": numeric["family"],
            "binary": binary["family"],
            "categorical": categorical["family"],
            "mixed": mixed["family"],
            "time_series_chart_type": ts_schema["chart_type"]["enum"],
            "timeline_chart_type": tl_schema["chart_type"]["enum"],
            "timeline_render_as": tl_schema["series"]["items"]["properties"]["render_as"]["enum"],
        },
    )

    # --- Shared on-region primitive ---
    window_end = datetime(2026, 6, 18, 20, 0, 0, tzinfo=timezone.utc)
    regions = _binary_on_regions(_binary_history(), _BINARY_ON_VALUES, window_end=window_end)
    region_hours = [(s.hour, e.hour) for s, e in regions]
    assert_equal(region_hours, [(6, 9), (14, 20)], "On-regions match open intervals.")

    # --- Standalone binary timeline render ---
    render_request = {
        "request_id": "timeline-eval",
        "render_mode": "safe",
        "chart_spec": {
            "chart_id": "c",
            "chart_type": "timeline",
            "title": "Kitchen Door State",
            "time_range": {
                "type": "absolute",
                "start": "2026-06-18T00:00:00+00:00",
                "end": "2026-06-18T20:00:00+00:00",
            },
            "series": [
                {
                    "series_id": "kitchen_door",
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
            "notes": [],
        },
        "history_series": [_binary_history()],
        "derived_intervals": [],
        "output": {"format": "png", "width": 1400, "height": 800},
        "theme": {},
        "codegen": None,
    }
    result = render_in_process_chart(render_request)
    assert_true(result["accepted"], "Binary timeline must render.")
    assert_equal(result["render_result"]["status"], "success", "Timeline render status is success.")
    assert_equal(
        result["render_result"]["render_metadata"]["codegen_attempts"], 0, "Timeline render uses no codegen."
    )
    assert_equal(result["png_bytes"][:8], b"\x89PNG\r\n\x1a\n", "Timeline output is a real PNG.")

    print_case(
        "binary_timeline_render",
        given={"entity": "binary_sensor.kitchen_door", "kind": "binary_state"},
        when={"operation": "render_in_process_chart(chart_type=timeline)"},
        then={
            "on_region_hours": region_hours,
            "status": result["render_result"]["status"],
            "renderer": result["renderer"],
            "png_signature_ok": result["png_bytes"][:8] == b"\x89PNG\r\n\x1a\n",
            "series_plotted": result["render_result"]["render_metadata"]["series_plotted"],
        },
    )

    print("PASS timeline_render_family_routing")


if __name__ == "__main__":
    main()
