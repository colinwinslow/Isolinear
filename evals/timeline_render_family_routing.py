"""Eval: deterministic render-family routing + categorical timeline (ADR-0022/0023).

Exercises the pre-planning `_series_kind` routing (numeric -> time_series,
binary/categorical -> timeline, mixed -> fail closed), the shared
`_binary_on_regions` primitive, and a standalone binary timeline render.
Also covers the ADR-0023 capability envelope (single-numeric gets a 3-family
envelope; histogram and aggregate_bar render from the live Pillow path).
Emits CASE evidence. No live model or recorder is required.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from custom_components.isolinear.job_orchestration import (  # noqa: E402
    _resolve_render_envelope,
    _resolve_render_family,
    validate_model_provider_chart_family,
)
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
    {"entity_id": "sensor.basement_temperature", "domain": "sensor", "state_class": "measurement"},
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
    overlay = _resolve_render_family(CATALOG, ["sensor.attic_temperature", "binary_sensor.kitchen_door"])
    multi_overlay = _resolve_render_family(
        CATALOG, ["sensor.attic_temperature", "sensor.basement_temperature", "binary_sensor.kitchen_door"]
    )
    assert_equal(numeric["family"], "time_series", "Numeric entity routes to time_series.")
    assert_equal(binary["family"], "timeline", "Binary entity routes to timeline.")
    assert_equal(categorical["family"], "timeline", "Categorical entity routes to timeline.")
    assert_equal(overlay["family"], "time_series_overlay", "One numeric + one binary routes to overlay.")
    assert_equal(overlay["numeric_entity_ids"], ["sensor.attic_temperature"], "Numeric primary recorded.")
    assert_equal(overlay["categorical_entity_ids"], ["binary_sensor.kitchen_door"], "Overlay entity recorded.")
    # Multiple numeric series + a state entity now compose as a multi-numeric
    # overlay (both lines plot, state shaded behind) rather than failing closed.
    assert_equal(multi_overlay["family"], "time_series_overlay", "Two numeric + binary composes as a multi-numeric overlay.")
    assert_equal(
        multi_overlay["numeric_entity_ids"],
        ["sensor.attic_temperature", "sensor.basement_temperature"],
        "Both numeric series recorded as overlay primaries.",
    )

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
            "overlay": overlay["family"],
            "multi_numeric_overlay": multi_overlay["family"],
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

    # --- Numeric line + binary shaded_intervals overlay (ADR-0022 D4/D5) ---
    from custom_components.isolinear.job_orchestration import _compose_binary_overlays  # noqa: E402

    numeric_spec = {
        "chart_id": "c",
        "chart_type": "time_series",
        "title": "Living Room Temperature & AC",
        "time_range": {
            "type": "absolute",
            "start": "2026-06-18T00:00:00+00:00",
            "end": "2026-06-18T20:00:00+00:00",
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
        "overlays": [],
        "x_axis": {"type": "time"},
        "y_axis": {"label": "degF"},
        "notes": [],
    }
    composed = _compose_binary_overlays(
        numeric_spec,
        overlay_entity_ids=["binary_sensor.ac"],
        catalog_items=[{"entity_id": "binary_sensor.ac", "friendly_name": "AC Running"}],
    )
    assert_equal(len(composed["overlays"]), 1, "One overlay is injected.")
    assert_equal(composed["overlays"][0]["render_as"], "shaded_intervals", "Overlay is shaded_intervals.")
    assert_equal(numeric_spec["overlays"], [], "Original spec is not mutated.")

    temp_points = [
        {
            "ts": (datetime(2026, 6, 18, h, 0, 0, tzinfo=timezone.utc)).isoformat(timespec="seconds"),
            "value": 72.0 + (1 if 8 <= h < 12 or 16 <= h < 20 else -1) * (h % 3),
            "raw_state": "x",
            "quality": "ok",
        }
        for h in range(21)
    ]
    ac_hist = _binary_history()
    ac_hist["entity_id"] = "binary_sensor.ac"
    ac_hist["series_id"] = "ac"
    overlay_request = {
        "request_id": "overlay-eval",
        "render_mode": "safe",
        "chart_spec": composed,
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
            ac_hist,
        ],
        "derived_intervals": [],
        "output": {"format": "png", "width": 1400, "height": 800},
        "theme": {},
        "codegen": None,
    }
    overlay_result = render_in_process_chart(overlay_request)
    assert_true(overlay_result["accepted"], "Overlay composition must render.")
    assert_equal(
        overlay_result["render_result"]["render_metadata"]["overlays_plotted"],
        ["overlay-001"],
        "Overlay is recorded as plotted.",
    )

    print_case(
        "numeric_line_with_binary_overlay",
        given={"primary": "sensor.living_room_temperature", "overlay": "binary_sensor.ac"},
        when={"operation": "_compose_binary_overlays + render_in_process_chart(time_series)"},
        then={
            "overlay_render_as": composed["overlays"][0]["render_as"],
            "overlays_plotted": overlay_result["render_result"]["render_metadata"]["overlays_plotted"],
            "series_plotted": overlay_result["render_result"]["render_metadata"]["series_plotted"],
            "png_signature_ok": overlay_result["png_bytes"][:8] == b"\x89PNG\r\n\x1a\n",
        },
    )

    # --- ADR-0023 capability envelope routing ---
    env_single_numeric = _resolve_render_envelope(CATALOG, ["sensor.attic_temperature"])
    env_multi_numeric = _resolve_render_envelope(
        CATALOG, ["sensor.attic_temperature", "sensor.basement_temperature"]
    )
    env_binary = _resolve_render_envelope(CATALOG, ["binary_sensor.kitchen_door"])
    env_overlay = _resolve_render_envelope(
        CATALOG, ["sensor.attic_temperature", "binary_sensor.kitchen_door"]
    )
    env_multi_overlay = _resolve_render_envelope(
        CATALOG, ["sensor.attic_temperature", "sensor.basement_temperature", "binary_sensor.kitchen_door"]
    )

    assert_equal(
        env_single_numeric["families"], ["time_series", "histogram", "aggregate_bar"],
        "Single numeric entity gets a 3-family envelope."
    )
    assert_equal(env_multi_numeric["families"], ["time_series"], "Multi-numeric gets time_series only.")
    assert_equal(env_binary["families"], ["timeline"], "Binary gets timeline only.")
    assert_equal(env_overlay["families"], ["time_series_overlay"], "Overlay gets overlay only.")
    assert_equal(env_multi_overlay["families"], ["time_series_overlay"], "Two numeric + binary gets a multi-numeric overlay envelope.")

    # Schema for single-numeric multi-family envelope has widened chart_type enum.
    multi_schema = load_planner_result_schema(
        "time_series", envelope=env_single_numeric["families"]
    )["properties"]["chart_spec"]["properties"]
    assert_true(
        set(["time_series", "histogram", "bar"]) <= set(multi_schema["chart_type"]["enum"]),
        "Multi-family schema chart_type enum includes time_series, histogram, bar."
    )

    # Out-of-envelope gate accepts in-envelope, rejects out-of-envelope choices.
    gate_accept = validate_model_provider_chart_family(
        {"chart_type": "histogram"}, env_single_numeric
    )
    gate_reject = validate_model_provider_chart_family(
        {"chart_type": "scatter"}, env_single_numeric
    )
    assert_true(gate_accept["accepted"], "histogram is in the single-numeric envelope.")
    assert_true(not gate_reject["accepted"], "scatter is NOT in the single-numeric envelope.")
    assert_equal(gate_reject["code"], "model_provider_chart_family_out_of_envelope", "Rejection code.")

    print_case(
        "capability_envelope_routing",
        given={"catalog_kinds": {item["entity_id"]: item.get("domain") for item in CATALOG}},
        when={"operation": "_resolve_render_envelope + validate_model_provider_chart_family"},
        then={
            "single_numeric_families": env_single_numeric["families"],
            "single_numeric_shape": env_single_numeric["shape"],
            "multi_numeric_families": env_multi_numeric["families"],
            "binary_families": env_binary["families"],
            "overlay_families": env_overlay["families"],
            "multi_numeric_overlay_families": env_multi_overlay["families"],
            "multi_schema_chart_types": multi_schema["chart_type"]["enum"],
            "gate_accept_histogram": gate_accept["accepted"],
            "gate_reject_scatter": not gate_reject["accepted"],
            "gate_reject_code": gate_reject["code"],
        },
    )

    # --- Histogram render (ADR-0023 live renderer) ---
    temp_hist_points = [
        {
            "ts": (datetime(2026, 6, 18, h, 0, 0, tzinfo=timezone.utc)).isoformat(timespec="seconds"),
            "value": 19.0 + h * 0.15,
            "quality": "ok",
        }
        for h in range(24)
    ]
    histogram_request = {
        "request_id": "histogram-eval",
        "render_mode": "safe",
        "output": {"format": "png", "width": 1400, "height": 800},
        "chart_spec": {
            "chart_id": "hist-c",
            "chart_type": "histogram",
            "title": "Attic Temperature Distribution",
            "time_range": {
                "type": "absolute",
                "start": "2026-06-18T00:00:00+00:00",
                "end": "2026-06-18T23:00:00+00:00",
            },
            "series": [
                {
                    "series_id": "temp-dist",
                    "label": "Attic Temperature",
                    "source": {"type": "entity", "entity_id": "sensor.attic_temperature", "attribute": None},
                    "role": "primary",
                    "render_as": "histogram",
                    "transform": {"operation": "none", "window": None},
                    "unit": "°C",
                }
            ],
            "x_axis": {"type": "value", "bin_count": 8},
            "overlays": [], "y_axis": {}, "notes": [],
        },
        "history_series": [
            {
                "series_id": "temp-dist", "entity_id": "sensor.attic_temperature",
                "label": "Attic Temperature", "kind": "numeric", "unit": "°C",
                "points": temp_hist_points, "source": "recorder_states", "resolution": "raw",
                "source_entity_ids": ["sensor.attic_temperature"], "warnings": [],
            }
        ],
        "approved_entity_ids": ["sensor.attic_temperature"],
        "source_snapshot_id": "snap-hist-eval",
    }
    hist_result = render_in_process_chart(histogram_request)
    assert_true(hist_result["accepted"], "Histogram render must succeed.")
    assert_equal(hist_result["render_result"]["status"], "success", "Histogram render status.")
    assert_equal(hist_result["png_bytes"][:8], b"\x89PNG\r\n\x1a\n", "Histogram output is a real PNG.")
    assert_equal(hist_result["render_result"]["render_metadata"]["codegen_attempts"], 0, "No codegen.")

    print_case(
        "histogram_render",
        given={"entity": "sensor.attic_temperature", "kind": "numeric", "n_points": 24},
        when={"operation": "render_in_process_chart(chart_type=histogram)"},
        then={
            "status": hist_result["render_result"]["status"],
            "renderer": hist_result["renderer"],
            "png_byte_count": hist_result["png_byte_count"],
            "series_plotted": hist_result["render_result"]["render_metadata"]["series_plotted"],
            "x_min": hist_result["render_result"]["render_metadata"]["x_min"],
            "x_max": hist_result["render_result"]["render_metadata"]["x_max"],
            "codegen_attempts": hist_result["render_result"]["render_metadata"]["codegen_attempts"],
        },
    )

    # --- Aggregate bar render (ADR-0023 live renderer) ---
    agg_points = []
    for d in range(5):
        for h in range(6):
            ts = datetime(2026, 6, 14 + d, h * 4, 0, 0, tzinfo=timezone.utc)
            agg_points.append({"ts": ts.isoformat(timespec="seconds"), "value": 20.0 + d + h * 0.4, "quality": "ok"})
    bar_request = {
        "request_id": "aggbar-eval",
        "render_mode": "safe",
        "output": {"format": "png", "width": 1400, "height": 800},
        "chart_spec": {
            "chart_id": "bar-c",
            "chart_type": "bar",
            "title": "Daily Average Attic Temperature",
            "time_range": {
                "type": "absolute",
                "start": "2026-06-14T00:00:00+00:00",
                "end": "2026-06-18T23:00:00+00:00",
            },
            "series": [
                {
                    "series_id": "temp-avg", "label": "Daily Average",
                    "source": {"type": "aggregate", "entity_id": "sensor.attic_temperature", "operation": "mean"},
                    "role": "primary", "render_as": "bar",
                    "transform": {"operation": "none", "window": None}, "unit": "°C",
                }
            ],
            "x_axis": {"type": "category", "group_by": "day"},
            "overlays": [], "y_axis": {"label": "°C"}, "notes": [],
        },
        "history_series": [
            {
                "series_id": "temp-avg", "entity_id": "sensor.attic_temperature",
                "label": "Attic Temperature", "kind": "numeric", "unit": "°C",
                "points": agg_points, "source": "recorder_states", "resolution": "raw",
                "source_entity_ids": ["sensor.attic_temperature"], "warnings": [],
            }
        ],
        "approved_entity_ids": ["sensor.attic_temperature"],
        "source_snapshot_id": "snap-bar-eval",
    }
    bar_result = render_in_process_chart(bar_request)
    assert_true(bar_result["accepted"], "Aggregate bar render must succeed.")
    assert_equal(bar_result["render_result"]["status"], "success", "Bar render status.")
    assert_equal(bar_result["png_bytes"][:8], b"\x89PNG\r\n\x1a\n", "Bar output is a real PNG.")

    print_case(
        "aggregate_bar_render",
        given={"entity": "sensor.attic_temperature", "kind": "numeric", "operation": "mean", "group_by": "day"},
        when={"operation": "render_in_process_chart(chart_type=bar)"},
        then={
            "status": bar_result["render_result"]["status"],
            "renderer": bar_result["renderer"],
            "png_byte_count": bar_result["png_byte_count"],
            "series_plotted": bar_result["render_result"]["render_metadata"]["series_plotted"],
            "x_min": bar_result["render_result"]["render_metadata"]["x_min"],
            "x_max": bar_result["render_result"]["render_metadata"]["x_max"],
            "codegen_attempts": bar_result["render_result"]["render_metadata"]["codegen_attempts"],
        },
    )

    print("PASS timeline_render_family_routing")


if __name__ == "__main__":
    main()
