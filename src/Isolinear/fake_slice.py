from __future__ import annotations

import re
import struct
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from Isolinear.contracts import ContractValidationError, validate_contract


TEMPERATURE_UNIT = "\u00b0F"
POWER_UNIT = "W"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def iso_timestamp(timestamp: datetime) -> str:
    if timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")

    return timestamp.isoformat(timespec="seconds")


def get_fake_approved_entity_catalog() -> list[dict[str, Any]]:
    return [
        {
            "entity_id": "sensor.upstairs_temperature",
            "friendly_name": "Upstairs Temperature",
            "domain": "sensor",
            "device_class": "temperature",
            "state_class": "measurement",
            "unit_of_measurement": TEMPERATURE_UNIT,
            "area": "Hallway",
            "labels": ["upstairs"],
            "device_name": "Fake Upstairs Thermometer",
            "integration": "fake_provider",
            "current_state": 70.9,
            "attributes": {},
            "visible_to_agent": True,
        },
        {
            "entity_id": "sensor.downstairs_temperature",
            "friendly_name": "Downstairs Temperature",
            "domain": "sensor",
            "device_class": "temperature",
            "state_class": "measurement",
            "unit_of_measurement": TEMPERATURE_UNIT,
            "area": "Living Room",
            "labels": ["downstairs"],
            "device_name": "Fake Downstairs Thermometer",
            "integration": "fake_provider",
            "current_state": 69.3,
            "attributes": {},
            "visible_to_agent": True,
        },
        {
            "entity_id": "binary_sensor.dishwasher",
            "friendly_name": "Dishwasher",
            "domain": "binary_sensor",
            "device_class": "running",
            "state_class": None,
            "unit_of_measurement": None,
            "area": "Kitchen",
            "labels": ["dishwasher"],
            "device_name": "Fake Dishwasher",
            "integration": "fake_provider",
            "current_state": "off",
            "attributes": {},
            "visible_to_agent": True,
        },
        {
            "entity_id": "sensor.dishwasher_power",
            "friendly_name": "Dishwasher Power",
            "domain": "sensor",
            "device_class": "power",
            "state_class": "measurement",
            "unit_of_measurement": POWER_UNIT,
            "area": "Kitchen",
            "labels": ["dishwasher"],
            "device_name": "Fake Dishwasher",
            "integration": "fake_provider",
            "current_state": 0.5,
            "attributes": {},
            "visible_to_agent": True,
        },
    ]


def _new_history_point(timestamp: datetime, value: float) -> dict[str, Any]:
    return {
        "ts": iso_timestamp(timestamp),
        "value": float(value),
        "raw_state": f"{value:.1f}",
        "quality": "ok",
    }


def _new_history_series(
    *,
    series_id: str,
    entity_id: str,
    label: str,
    now: datetime,
    values: list[float],
) -> dict[str, Any]:
    offsets = [-24, -18, -12, -6, 0]
    points = [
        _new_history_point(now + timedelta(hours=offset), values[index])
        for index, offset in enumerate(offsets)
    ]

    return {
        "series_id": series_id,
        "entity_id": entity_id,
        "label": label,
        "kind": "numeric",
        "unit": TEMPERATURE_UNIT,
        "points": points,
        "source_entity_ids": [entity_id],
        "warnings": [],
    }


def get_fake_normalized_history(now: datetime | None = None) -> list[dict[str, Any]]:
    if now is None:
        now = datetime.now(timezone.utc)

    return [
        _new_history_series(
            series_id="upstairs_temperature",
            entity_id="sensor.upstairs_temperature",
            label="Upstairs Temperature",
            now=now,
            values=[70.8, 71.4, 72.0, 71.6, 70.9],
        ),
        _new_history_series(
            series_id="downstairs_temperature",
            entity_id="sensor.downstairs_temperature",
            label="Downstairs Temperature",
            now=now,
            values=[68.9, 69.5, 70.2, 70.0, 69.3],
        ),
    ]


def get_fake_raw_numeric_history_records(now: datetime | None = None) -> list[dict[str, Any]]:
    if now is None:
        now = datetime.now(timezone.utc)

    offsets = [-24, -18, -12, -6, 0]
    states = ["70.8", "71.2", "unknown", "unavailable", "70.9"]

    return [
        {
            "entity_id": "sensor.upstairs_temperature",
            "state": states[index],
            "last_changed": iso_timestamp(now + timedelta(hours=offset)),
            "attributes": {
                "unit_of_measurement": TEMPERATURE_UNIT,
            },
        }
        for index, offset in enumerate(offsets)
    ]


def normalize_numeric_history_records(
    *,
    raw_records: list[dict[str, Any]],
    series_id: str,
    entity_id: str,
    label: str,
    unit: str | None,
) -> dict[str, Any]:
    points = []
    warnings = []

    for record in raw_records:
        raw_state = record.get("state")
        state_text = str(raw_state) if raw_state is not None else None

        if state_text in {"unknown", "unavailable"}:
            value = None
            quality = state_text
            warnings.append(
                f"State '{state_text}' for {entity_id} normalized to missing value."
            )
        else:
            try:
                value = float(raw_state)
            except (TypeError, ValueError):
                value = None
                quality = "invalid"
                warnings.append(
                    f"State '{state_text}' for {entity_id} is not a valid numeric value."
                )
            else:
                quality = "ok"

        points.append(
            {
                "ts": record["last_changed"],
                "value": value,
                "raw_state": raw_state,
                "quality": quality,
            }
        )

    return {
        "series_id": series_id,
        "entity_id": entity_id,
        "label": label,
        "kind": "numeric",
        "unit": unit,
        "points": points,
        "source_entity_ids": [entity_id],
        "warnings": warnings,
    }


def _new_state_point(timestamp: datetime, state: str) -> dict[str, Any]:
    return {
        "ts": iso_timestamp(timestamp),
        "value": state,
        "raw_state": state,
        "quality": "ok",
    }


def get_fake_dishwasher_state_history(now: datetime | None = None) -> dict[str, Any]:
    if now is None:
        now = datetime.now(timezone.utc)

    start = now - timedelta(hours=24)

    return {
        "series_id": "dishwasher_state",
        "entity_id": "binary_sensor.dishwasher",
        "label": "Dishwasher",
        "kind": "binary_state",
        "unit": None,
        "points": [
            _new_state_point(start, "off"),
            _new_state_point(start + timedelta(hours=8), "on"),
            _new_state_point(start + timedelta(hours=10), "off"),
        ],
        "source_entity_ids": ["binary_sensor.dishwasher"],
        "warnings": [],
    }


def get_fake_dishwasher_power_history(now: datetime | None = None) -> dict[str, Any]:
    if now is None:
        now = datetime.now(timezone.utc)

    start = now - timedelta(hours=24)
    offsets = [0, 6, 8, 9, 10, 24]
    values = [0.4, 0.6, 9.8, 42.0, 3.2, 0.5]

    return {
        "series_id": "dishwasher_power",
        "entity_id": "sensor.dishwasher_power",
        "label": "Dishwasher Power",
        "kind": "numeric",
        "unit": POWER_UNIT,
        "points": [
            _new_history_point(start + timedelta(hours=offset), values[index])
            for index, offset in enumerate(offsets)
        ],
        "source_entity_ids": ["sensor.dishwasher_power"],
        "warnings": [],
    }


def extract_state_intervals(
    *,
    history_series: dict[str, Any],
    interval_id: str,
    label: str,
    active_values: list[str],
    range_end: datetime,
) -> dict[str, Any]:
    active_value_set = {str(value) for value in active_values}
    active_start = None
    active_state = None
    intervals = []

    points = sorted(
        history_series.get("points", []),
        key=lambda point: datetime.fromisoformat(point["ts"]),
    )

    for point in points:
        timestamp = datetime.fromisoformat(point["ts"])
        state = str(point.get("value", point.get("raw_state")))

        if state in active_value_set and active_start is None:
            active_start = timestamp
            active_state = state
        elif state not in active_value_set and active_start is not None:
            intervals.append(
                {
                    "start": iso_timestamp(active_start),
                    "end": iso_timestamp(timestamp),
                    "state": active_state,
                    "reason": f"State was {active_state}.",
                }
            )
            active_start = None
            active_state = None

    if active_start is not None:
        intervals.append(
            {
                "start": iso_timestamp(active_start),
                "end": iso_timestamp(range_end),
                "state": active_state,
                "reason": f"State was {active_state}.",
            }
        )

    return {
        "interval_id": interval_id,
        "label": label,
        "source_entity_id": history_series["entity_id"],
        "source_attribute": None,
        "rule": {"active_values": active_values},
        "intervals": intervals,
        "warnings": [],
    }


def _threshold_matches(value: float, operator: str, threshold_value: float) -> bool:
    if operator == ">":
        return value > threshold_value
    if operator == ">=":
        return value >= threshold_value
    if operator == "<":
        return value < threshold_value
    if operator == "<=":
        return value <= threshold_value
    if operator == "==":
        return value == threshold_value
    if operator == "!=":
        return value != threshold_value
    raise ValueError(f"Unsupported threshold operator: {operator}")


def _format_threshold_rule(threshold: dict[str, Any]) -> str:
    unit = threshold.get("unit")
    unit_suffix = f" {unit}" if unit else ""
    return f"value {threshold['operator']} {threshold['value']}{unit_suffix}"


def extract_threshold_intervals(
    *,
    history_series: dict[str, Any],
    interval_id: str,
    label: str,
    threshold: dict[str, Any],
    range_end: datetime,
) -> dict[str, Any]:
    operator = threshold["operator"]
    threshold_value = float(threshold["value"])
    active_start = None
    intervals = []
    rule_text = _format_threshold_rule(threshold)

    points = sorted(
        history_series.get("points", []),
        key=lambda point: datetime.fromisoformat(point["ts"]),
    )

    for point in points:
        timestamp = datetime.fromisoformat(point["ts"])
        value = point.get("value")
        is_active = (
            value is not None
            and _threshold_matches(float(value), operator, threshold_value)
        )

        if is_active and active_start is None:
            active_start = timestamp
        elif not is_active and active_start is not None:
            intervals.append(
                {
                    "start": iso_timestamp(active_start),
                    "end": iso_timestamp(timestamp),
                    "state": True,
                    "reason": f"Threshold matched: {rule_text}.",
                }
            )
            active_start = None

    if active_start is not None:
        intervals.append(
            {
                "start": iso_timestamp(active_start),
                "end": iso_timestamp(range_end),
                "state": True,
                "reason": f"Threshold matched: {rule_text}.",
            }
        )

    return {
        "interval_id": interval_id,
        "label": label,
        "source_entity_id": history_series["entity_id"],
        "source_attribute": None,
        "rule": threshold,
        "intervals": intervals,
        "warnings": [],
    }


def create_deterministic_planner_result(
    prompt: str,
    entity_catalog: list[dict[str, Any]],
) -> dict[str, Any]:
    by_entity_id = {
        item["entity_id"]: item
        for item in entity_catalog
        if item.get("visible_to_agent")
    }
    threshold_prompt = (
        re.search(r"mark", prompt, re.IGNORECASE)
        and re.search(r"dishwasher", prompt, re.IGNORECASE)
        and re.search(r"running", prompt, re.IGNORECASE)
        and re.search(r"(last\s+day|over\s+the\s+last\s+day|last\s+24\s+hours|24\s*hours)", prompt, re.IGNORECASE)
    )

    if threshold_prompt and "sensor.dishwasher_power" in by_entity_id:
        return {
            "status": "clarification_needed",
            "chart_spec": None,
            "clarification_question": {
                "question_id": "confirm_dishwasher_power_threshold",
                "message": (
                    "Should dishwasher running be marked with a threshold where "
                    "sensor.dishwasher_power is greater than 5 W?"
                ),
                "reason": (
                    "The approved dishwasher power sensor is continuous, so the "
                    "running interval needs a confirmed threshold before rendering."
                ),
                "options": [
                    {
                        "option_id": "use_dishwasher_power_gt_5w",
                        "label": "Dishwasher power > 5 W",
                        "value": {
                            "type": "threshold_interval",
                            "entity_id": "sensor.dishwasher_power",
                            "operator": ">",
                            "value": 5,
                            "unit": POWER_UNIT,
                        },
                        "can_remember": True,
                    }
                ],
                "allow_free_text": True,
            },
            "memory_proposals": [],
            "reasoning_summary": (
                "Proposed a threshold-derived interval for the approved dishwasher "
                "power sensor and requested user confirmation."
            ),
            "warnings": ["threshold_confirmation_required"],
        }

    supported_prompt = (
        re.search(r"compare", prompt, re.IGNORECASE)
        and re.search(r"upstairs", prompt, re.IGNORECASE)
        and re.search(r"downstairs", prompt, re.IGNORECASE)
        and re.search(r"temperature", prompt, re.IGNORECASE)
        and re.search(r"(last\s+24\s+hours|24\s*hours)", prompt, re.IGNORECASE)
    )

    if not supported_prompt:
        return {
            "status": "cannot_resolve",
            "chart_spec": None,
            "clarification_question": None,
            "memory_proposals": [],
            "reasoning_summary": (
                "The fake planner only supports comparing upstairs and downstairs "
                "temperatures over the last 24 hours."
            ),
            "warnings": ["unsupported_fake_prompt"],
        }

    required_entity_ids = [
        "sensor.upstairs_temperature",
        "sensor.downstairs_temperature",
    ]
    missing_entity_ids = [
        entity_id
        for entity_id in required_entity_ids
        if entity_id not in by_entity_id
    ]

    if missing_entity_ids:
        return {
            "status": "cannot_resolve",
            "chart_spec": None,
            "clarification_question": None,
            "memory_proposals": [],
            "reasoning_summary": "The fake planner could not find the approved temperature entities.",
            "warnings": ["missing_fake_entities"],
        }

    chart_spec = {
        "chart_id": "fake_temperature_compare_24h",
        "chart_type": "time_series",
        "title": "Upstairs vs Downstairs Temperature",
        "time_range": {
            "type": "relative",
            "duration": "24h",
        },
        "series": [
            {
                "series_id": "upstairs_temperature",
                "label": by_entity_id["sensor.upstairs_temperature"]["friendly_name"],
                "source": {
                    "type": "entity",
                    "entity_id": "sensor.upstairs_temperature",
                    "attribute": None,
                },
                "role": "primary",
                "render_as": "line",
                "transform": None,
                "unit": TEMPERATURE_UNIT,
            },
            {
                "series_id": "downstairs_temperature",
                "label": by_entity_id["sensor.downstairs_temperature"]["friendly_name"],
                "source": {
                    "type": "entity",
                    "entity_id": "sensor.downstairs_temperature",
                    "attribute": None,
                },
                "role": "comparison",
                "render_as": "line",
                "transform": None,
                "unit": TEMPERATURE_UNIT,
            },
        ],
        "overlays": [],
        "x_axis": {"type": "time"},
        "y_axis": {"label": TEMPERATURE_UNIT},
        "notes": ["Deterministic fake-provider planner stub."],
    }

    return {
        "status": "chart_spec_ready",
        "chart_spec": chart_spec,
        "clarification_question": None,
        "memory_proposals": [],
        "reasoning_summary": "Matched the deterministic fake temperature comparison prompt.",
        "warnings": [],
    }


def _new_render_failure(request_id: str, code: str, message: str) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "status": "failed",
        "image_id": None,
        "image_mime_type": None,
        "image_path": None,
        "error": {
            "code": code,
            "message": message,
            "details": {},
        },
        "render_metadata": {
            "title": None,
            "series_plotted": [],
            "overlays_plotted": [],
            "x_min": None,
            "x_max": None,
            "warnings": [],
            "codegen_attempts": 0,
        },
    }


def _history_series_map(history_series: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {series["series_id"]: series for series in history_series}


def _numeric_extent(series_to_plot: list[dict[str, Any]]) -> dict[str, Any]:
    values: list[float] = []
    timestamps: list[datetime] = []

    for series in series_to_plot:
        for point in series["points"]:
            if point.get("value") is None:
                continue

            values.append(float(point["value"]))
            timestamps.append(datetime.fromisoformat(point["ts"]))

    if not values or not timestamps:
        raise ValueError("No numeric points are available to render.")

    return {
        "value_min": min(values),
        "value_max": max(values),
        "x_min": min(timestamps),
        "x_max": max(timestamps),
    }


class _Canvas:
    def __init__(self, width: int, height: int, background: tuple[int, int, int]):
        self.width = width
        self.height = height
        self.pixels = bytearray(background * width * height)

    def set_pixel(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return

        offset = ((y * self.width) + x) * 3
        self.pixels[offset : offset + 3] = bytes(color)

    def draw_line(
        self,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        color: tuple[int, int, int],
        *,
        thickness: int = 1,
    ) -> None:
        dx = abs(x1 - x0)
        sx = 1 if x0 < x1 else -1
        dy = -abs(y1 - y0)
        sy = 1 if y0 < y1 else -1
        err = dx + dy

        while True:
            self.draw_disc(x0, y0, max(0, thickness // 2), color)
            if x0 == x1 and y0 == y1:
                break

            doubled_error = 2 * err
            if doubled_error >= dy:
                err += dy
                x0 += sx
            if doubled_error <= dx:
                err += dx
                y0 += sy

    def draw_rect(
        self,
        left: int,
        top: int,
        right: int,
        bottom: int,
        color: tuple[int, int, int],
    ) -> None:
        clipped_left = max(0, min(left, self.width))
        clipped_right = max(0, min(right, self.width))
        clipped_top = max(0, min(top, self.height))
        clipped_bottom = max(0, min(bottom, self.height))

        for y in range(clipped_top, clipped_bottom):
            row_offset = ((y * self.width) + clipped_left) * 3
            self.pixels[row_offset : row_offset + ((clipped_right - clipped_left) * 3)] = (
                bytes(color) * (clipped_right - clipped_left)
            )

    def draw_disc(self, cx: int, cy: int, radius: int, color: tuple[int, int, int]) -> None:
        if radius <= 0:
            self.set_pixel(cx, cy, color)
            return

        radius_squared = radius * radius
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                if ((x - cx) * (x - cx)) + ((y - cy) * (y - cy)) <= radius_squared:
                    self.set_pixel(x, y, color)


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + chunk_type
        + payload
        + struct.pack(">I", zlib.crc32(chunk_type + payload) & 0xFFFFFFFF)
    )


def _write_png(path: Path, canvas: _Canvas) -> None:
    raw = bytearray()
    row_size = canvas.width * 3

    for y in range(canvas.height):
        raw.append(0)
        start = y * row_size
        raw.extend(canvas.pixels[start : start + row_size])

    ihdr = struct.pack(">IIBBBBB", canvas.width, canvas.height, 8, 2, 0, 0, 0)
    path.write_bytes(
        PNG_SIGNATURE
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(bytes(raw), level=6))
        + _png_chunk(b"IEND", b"")
    )


def _write_time_series_png(
    *,
    chart_spec: dict[str, Any],
    series_to_plot: list[dict[str, Any]],
    overlays_to_plot: list[dict[str, Any]],
    image_path: Path,
    width: int,
    height: int,
) -> dict[str, str]:
    extent = _numeric_extent(series_to_plot)
    value_min = float(extent["value_min"])
    value_max = float(extent["value_max"])

    if value_min == value_max:
        value_min -= 1
        value_max += 1
    else:
        padding = (value_max - value_min) * 0.12
        value_min -= padding
        value_max += padding

    x_min = extent["x_min"]
    x_max = extent["x_max"]
    total_seconds = (x_max - x_min).total_seconds() or 1

    plot_left = 76
    plot_top = 66
    plot_right = 32
    plot_bottom = 74
    plot_width = max(1, width - plot_left - plot_right)
    plot_height = max(1, height - plot_top - plot_bottom)
    value_range = value_max - value_min

    canvas = _Canvas(width, height, (255, 255, 255))
    axis_color = (80, 88, 100)
    grid_color = (224, 228, 235)
    title_color = (30, 36, 45)
    overlay_color = (245, 232, 190)
    palette = [(32, 121, 199), (222, 112, 34)]

    canvas.draw_rect(28, 24, min(width - 28, 28 + (len(chart_spec["title"]) * 7)), 29, title_color)

    for overlay in overlays_to_plot:
        for interval in overlay["derived_interval"].get("intervals", []):
            interval_start = datetime.fromisoformat(interval["start"])
            interval_end = datetime.fromisoformat(interval["end"])
            if interval_end < x_min or interval_start > x_max:
                continue

            clipped_start = max(interval_start, x_min)
            clipped_end = min(interval_end, x_max)
            x0 = plot_left + int(((clipped_start - x_min).total_seconds() / total_seconds) * plot_width)
            x1 = plot_left + int(((clipped_end - x_min).total_seconds() / total_seconds) * plot_width)
            canvas.draw_rect(x0, plot_top, max(x0 + 1, x1), height - plot_bottom, overlay_color)

    for grid_index in range(5):
        y = int(plot_top + ((plot_height / 4) * grid_index))
        canvas.draw_line(plot_left, y, width - plot_right, y, grid_color)

    canvas.draw_line(plot_left, plot_top, plot_left, height - plot_bottom, axis_color, thickness=2)
    canvas.draw_line(
        plot_left,
        height - plot_bottom,
        width - plot_right,
        height - plot_bottom,
        axis_color,
        thickness=2,
    )

    for series_index, series in enumerate(series_to_plot):
        color = palette[series_index % len(palette)]
        projected_points: list[tuple[int, int]] = []

        for point in series["points"]:
            if point.get("value") is None:
                continue

            timestamp = datetime.fromisoformat(point["ts"])
            x = plot_left + int(((timestamp - x_min).total_seconds() / total_seconds) * plot_width)
            y = plot_top + int(((value_max - float(point["value"])) / value_range) * plot_height)
            projected_points.append((x, y))

        for point_index in range(len(projected_points) - 1):
            x0, y0 = projected_points[point_index]
            x1, y1 = projected_points[point_index + 1]
            canvas.draw_line(x0, y0, x1, y1, color, thickness=3)

        for x, y in projected_points:
            canvas.draw_disc(x, y, 4, color)

        legend_x = max(plot_left + 8, width - 320)
        legend_y = 30 + (series_index * 22)
        canvas.draw_rect(legend_x, legend_y, legend_x + 16, legend_y + 5, color)
        canvas.draw_rect(legend_x + 24, legend_y - 2, legend_x + 160, legend_y + 3, (76, 86, 99))

    _write_png(image_path, canvas)

    return {
        "x_min": iso_timestamp(x_min),
        "x_max": iso_timestamp(x_max),
    }


def invoke_trusted_renderer(
    render_request: dict[str, Any],
    output_directory: Path,
) -> dict[str, Any]:
    if render_request["render_mode"] not in {"safe", "auto"}:
        return _new_render_failure(
            request_id=render_request["request_id"],
            code="unsupported_render_mode",
            message="The fake trusted renderer supports only safe or auto render mode.",
        )

    if render_request["chart_spec"]["chart_type"] != "time_series":
        return _new_render_failure(
            request_id=render_request["request_id"],
            code="unsupported_chart_spec",
            message="The trusted fake renderer supports only time_series charts.",
        )

    history_map = _history_series_map(render_request["history_series"])
    series_to_plot = []
    derived_interval_map = {
        interval["interval_id"]: interval
        for interval in render_request.get("derived_intervals", [])
    }
    overlays_to_plot = []
    warnings = []

    for series_spec in render_request["chart_spec"]["series"]:
        series_id = series_spec["series_id"]
        if series_id in history_map:
            series_to_plot.append(history_map[series_id])
        else:
            warnings.append(f"Missing history for series '{series_id}'.")

    for overlay_spec in render_request["chart_spec"].get("overlays", []):
        overlay_id = overlay_spec["overlay_id"]
        if overlay_spec["render_as"] == "shaded_intervals" and overlay_id in derived_interval_map:
            overlays_to_plot.append(
                {
                    "overlay_id": overlay_id,
                    "derived_interval": derived_interval_map[overlay_id],
                }
            )
        else:
            warnings.append(f"Missing derived intervals for overlay '{overlay_id}'.")

    if not series_to_plot:
        return _new_render_failure(
            request_id=render_request["request_id"],
            code="missing_history_series",
            message="No matching history series were available for the chart spec.",
        )

    output_directory.mkdir(parents=True, exist_ok=True)
    image_id = f"{render_request['request_id']}.png"
    image_path = output_directory / image_id

    output = render_request.get("output") or {}
    width = output.get("width", 1000)
    height = output.get("height", 600)

    try:
        extent_metadata = _write_time_series_png(
            chart_spec=render_request["chart_spec"],
            series_to_plot=series_to_plot,
            overlays_to_plot=overlays_to_plot,
            image_path=image_path,
            width=width,
            height=height,
        )
    except Exception as exc:  # pragma: no cover - defensive result shaping
        return _new_render_failure(
            request_id=render_request["request_id"],
            code="render_failed",
            message=str(exc),
        )

    return {
        "request_id": render_request["request_id"],
        "status": "success",
        "image_id": image_id,
        "image_mime_type": "image/png",
        "image_path": str(image_path),
        "error": None,
        "render_metadata": {
            "title": render_request["chart_spec"]["title"],
            "series_plotted": [series["series_id"] for series in series_to_plot],
            "overlays_plotted": [overlay["overlay_id"] for overlay in overlays_to_plot],
            "x_min": extent_metadata["x_min"],
            "x_max": extent_metadata["x_max"],
            "warnings": warnings,
            "codegen_attempts": 0,
        },
    }


def _new_check(
    name: str,
    status: str,
    message: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "message": message,
        "details": {} if details is None else details,
    }


def _referenced_entity_ids(chart_spec: dict[str, Any]) -> list[str]:
    entity_ids = []

    for item in chart_spec.get("series", []) + chart_spec.get("overlays", []):
        source = item.get("source", {})
        if source.get("type") == "entity":
            entity_ids.append(source["entity_id"])
        elif source.get("type") == "aggregate":
            entity_ids.extend(source["entity_ids"])

    return entity_ids


def validate_chart_plan(
    *,
    chart_spec: dict[str, Any],
    entity_catalog: list[dict[str, Any]],
    repo_root: Path | None = None,
) -> dict[str, Any]:
    checks = []
    chart_id = chart_spec.get("chart_id", "invalid_chart_spec")

    schema_valid = True
    try:
        validate_contract("chart-spec", chart_spec, repo_root=repo_root)
    except ContractValidationError as exc:
        schema_valid = False
        checks.append(
            _new_check(
                name="chart_spec_schema",
                status="fail",
                message="Chart spec does not match the schema.",
                details={"error": str(exc)},
            )
        )
    else:
        checks.append(
            _new_check(
                name="chart_spec_schema",
                status="pass",
                message="Chart spec matches the schema.",
            )
        )

    if schema_valid:
        visible_entity_ids = {
            item["entity_id"]
            for item in entity_catalog
            if item.get("visible_to_agent")
        }
        missing_entity_ids = [
            entity_id
            for entity_id in _referenced_entity_ids(chart_spec)
            if entity_id not in visible_entity_ids
        ]

        if missing_entity_ids:
            checks.append(
                _new_check(
                    name="allowlisted_entities",
                    status="fail",
                    message="Chart spec references non-allowlisted entities.",
                    details={"missing_entity_ids": missing_entity_ids},
                )
            )
        else:
            checks.append(
                _new_check(
                    name="allowlisted_entities",
                    status="pass",
                    message="All chart entities are allowlisted.",
                )
            )
    else:
        checks.append(
            _new_check(
                name="allowlisted_entities",
                status="skipped",
                message="Chart spec schema validation failed before allowlist validation.",
            )
        )

    overall_status = "fail" if any(check["status"] == "fail" for check in checks) else "pass"

    return {
        "validation_id": f"validation_{chart_id}",
        "status": overall_status,
        "checks": checks,
        "warnings": [],
        "repair_attempts": 0,
        "visual_validation": {
            "run": False,
            "matches_prompt": None,
            "major_issues": [],
            "advisory_only": True,
        },
    }


def validate_chart_job(
    *,
    chart_spec: dict[str, Any],
    render_result: dict[str, Any],
    entity_catalog: list[dict[str, Any]],
    expected_start: datetime,
    expected_end: datetime,
) -> dict[str, Any]:
    checks = []

    has_required_chart_fields = (
        chart_spec.get("chart_id") is not None
        and chart_spec.get("chart_type") is not None
        and chart_spec.get("title") is not None
        and chart_spec.get("time_range") is not None
        and len(chart_spec.get("series", [])) > 0
    )
    if has_required_chart_fields:
        checks.append(
            _new_check(
                name="chart_spec_shape",
                status="pass",
                message="Chart spec has required fields.",
            )
        )
    else:
        checks.append(
            _new_check(
                name="chart_spec_shape",
                status="fail",
                message="Chart spec is missing required fields.",
            )
        )

    visible_entity_ids = {
        item["entity_id"]
        for item in entity_catalog
        if item.get("visible_to_agent")
    }
    referenced_entity_ids = [
        series["source"]["entity_id"]
        for series in chart_spec.get("series", [])
        if series.get("source", {}).get("type") == "entity"
    ]
    missing_entity_ids = [
        entity_id
        for entity_id in referenced_entity_ids
        if entity_id not in visible_entity_ids
    ]

    if not missing_entity_ids:
        checks.append(
            _new_check(
                name="allowlisted_entities",
                status="pass",
                message="All chart entities are allowlisted.",
            )
        )
    else:
        checks.append(
            _new_check(
                name="allowlisted_entities",
                status="fail",
                message="Chart spec references non-allowlisted entities.",
                details={"missing_entity_ids": missing_entity_ids},
            )
        )

    if render_result.get("status") == "success":
        checks.append(
            _new_check(
                name="render_status",
                status="pass",
                message="Renderer completed successfully.",
            )
        )
    else:
        checks.append(
            _new_check(
                name="render_status",
                status="fail",
                message="Renderer did not complete successfully.",
                details={"status": render_result.get("status")},
            )
        )

    image_path = render_result.get("image_path")
    image_exists = bool(image_path) and Path(image_path).exists() and Path(image_path).stat().st_size > 0
    if image_exists:
        checks.append(
            _new_check(
                name="image_artifact",
                status="pass",
                message="Rendered image exists and is non-empty.",
            )
        )
    else:
        checks.append(
            _new_check(
                name="image_artifact",
                status="fail",
                message="Rendered image is missing or empty.",
            )
        )

    expected_series_ids = [series["series_id"] for series in chart_spec.get("series", [])]
    plotted_series_ids = render_result.get("render_metadata", {}).get("series_plotted", [])
    missing_series_ids = [
        series_id
        for series_id in expected_series_ids
        if series_id not in plotted_series_ids
    ]

    if not missing_series_ids:
        checks.append(
            _new_check(
                name="rendered_series",
                status="pass",
                message="Render metadata lists every expected series.",
            )
        )
    else:
        checks.append(
            _new_check(
                name="rendered_series",
                status="fail",
                message="Render metadata is missing expected series.",
                details={"missing_series_ids": missing_series_ids},
            )
        )

    expected_overlay_ids = [overlay["overlay_id"] for overlay in chart_spec.get("overlays", [])]
    plotted_overlay_ids = render_result.get("render_metadata", {}).get("overlays_plotted", [])
    missing_overlay_ids = [
        overlay_id
        for overlay_id in expected_overlay_ids
        if overlay_id not in plotted_overlay_ids
    ]

    if not missing_overlay_ids:
        checks.append(
            _new_check(
                name="rendered_overlays",
                status="pass",
                message="Render metadata lists every expected overlay.",
            )
        )
    else:
        checks.append(
            _new_check(
                name="rendered_overlays",
                status="fail",
                message="Render metadata is missing expected overlays.",
                details={"missing_overlay_ids": missing_overlay_ids},
            )
        )

    expected_start_text = iso_timestamp(expected_start)
    expected_end_text = iso_timestamp(expected_end)
    render_metadata = render_result.get("render_metadata", {})
    time_range_matches = (
        render_metadata.get("x_min") == expected_start_text
        and render_metadata.get("x_max") == expected_end_text
    )

    if time_range_matches:
        checks.append(
            _new_check(
                name="rendered_time_range",
                status="pass",
                message="Render metadata matches the expected time range.",
            )
        )
    else:
        checks.append(
            _new_check(
                name="rendered_time_range",
                status="fail",
                message="Render metadata time range does not match the request.",
                details={
                    "expected_x_min": expected_start_text,
                    "expected_x_max": expected_end_text,
                    "actual_x_min": render_metadata.get("x_min"),
                    "actual_x_max": render_metadata.get("x_max"),
                },
            )
        )

    warnings = list(render_metadata.get("warnings", []))
    if any(check["status"] == "fail" for check in checks):
        overall_status = "fail"
    elif warnings or any(check["status"] == "warning" for check in checks):
        overall_status = "warning"
    else:
        overall_status = "pass"

    return {
        "validation_id": f"validation_{chart_spec['chart_id']}",
        "status": overall_status,
        "checks": checks,
        "warnings": warnings,
        "repair_attempts": 0,
        "visual_validation": {
            "run": False,
            "matches_prompt": None,
            "major_issues": [],
            "advisory_only": True,
        },
    }


def invoke_validated_chart_plan(
    *,
    chart_spec: dict[str, Any],
    entity_catalog: list[dict[str, Any]],
    history_series: list[dict[str, Any]],
    output_directory: Path,
    request_id: str,
    now: datetime,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    plan_validation_result = validate_chart_plan(
        chart_spec=chart_spec,
        entity_catalog=entity_catalog,
        repo_root=repo_root,
    )
    if plan_validation_result["status"] == "fail":
        return {
            "render_request": None,
            "render_result": None,
            "validation_result": plan_validation_result,
        }

    render_request = {
        "request_id": request_id,
        "render_mode": "safe",
        "chart_spec": chart_spec,
        "history_series": history_series,
        "derived_intervals": [],
        "output": {
            "format": "png",
            "width": 1000,
            "height": 600,
        },
        "theme": {},
        "codegen": None,
    }
    render_result = invoke_trusted_renderer(
        render_request=render_request,
        output_directory=output_directory,
    )
    validation_result = validate_chart_job(
        chart_spec=chart_spec,
        render_result=render_result,
        entity_catalog=entity_catalog,
        expected_start=now - timedelta(hours=24),
        expected_end=now,
    )

    return {
        "render_request": render_request,
        "render_result": render_result,
        "validation_result": validation_result,
    }


def invoke_fake_prompt_to_chart(
    *,
    prompt: str,
    output_directory: Path,
    now: datetime | None = None,
    semantic_aliases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if now is None:
        now = datetime.now(timezone.utc)

    semantic_aliases = [] if semantic_aliases is None else semantic_aliases
    for alias in semantic_aliases:
        natural_names = {name.lower() for name in alias.get("natural_names", [])}
        meaning = alias.get("meaning", {})
        if (
            alias.get("enabled", True)
            and "dishwasher running" in natural_names
            and meaning.get("type") == "threshold_interval"
            and re.search(r"dishwasher", prompt, re.IGNORECASE)
            and re.search(r"running", prompt, re.IGNORECASE)
        ):
            result = invoke_threshold_confirmation_use_once(
                prompt=prompt,
                confirmation_value=meaning,
                output_directory=output_directory,
                now=now,
            )
            result["planner_result"]["reasoning_summary"] = (
                "Reused saved semantic alias 'dishwasher_running' for the "
                "dishwasher running threshold."
            )
            return result

    catalog = get_fake_approved_entity_catalog()
    history = get_fake_normalized_history(now=now)
    planner_result = create_deterministic_planner_result(
        prompt=prompt,
        entity_catalog=catalog,
    )

    render_request = None
    render_result = None
    validation_result = None

    if planner_result["status"] == "chart_spec_ready":
        validated_plan = invoke_validated_chart_plan(
            chart_spec=planner_result["chart_spec"],
            entity_catalog=catalog,
            history_series=history,
            output_directory=output_directory,
            request_id="fake-temperature-compare-24h",
            now=now,
        )
        render_request = validated_plan["render_request"]
        render_result = validated_plan["render_result"]
        validation_result = validated_plan["validation_result"]

    return {
        "entity_catalog": catalog,
        "history_series": history,
        "planner_result": planner_result,
        "render_request": render_request,
        "render_result": render_result,
        "validation_result": validation_result,
    }


def invoke_threshold_confirmation_use_once(
    *,
    prompt: str,
    confirmation_value: dict[str, Any],
    output_directory: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    if now is None:
        now = datetime.now(timezone.utc)

    if confirmation_value.get("type") != "threshold_interval":
        raise ValueError("confirmation_value must be a threshold_interval.")
    if confirmation_value.get("entity_id") != "sensor.dishwasher_power":
        raise ValueError("The fake use-once threshold path supports only sensor.dishwasher_power.")

    catalog = get_fake_approved_entity_catalog()
    history = get_fake_normalized_history(now=now)
    threshold = {
        "operator": confirmation_value["operator"],
        "value": confirmation_value["value"],
        "unit": confirmation_value.get("unit"),
    }
    power_history = get_fake_dishwasher_power_history(now=now)
    derived_interval = extract_threshold_intervals(
        history_series=power_history,
        interval_id="dishwasher_running",
        label="Dishwasher Running",
        threshold=threshold,
        range_end=now,
    )
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
                "unit": TEMPERATURE_UNIT,
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
                "threshold": threshold,
            }
        ],
        "x_axis": {"type": "time"},
        "y_axis": {"label": TEMPERATURE_UNIT},
        "notes": ["Use-once threshold confirmation."],
    }
    planner_result = {
        "status": "chart_spec_ready",
        "chart_spec": chart_spec,
        "clarification_question": None,
        "memory_proposals": [],
        "reasoning_summary": (
            "Applied the user-confirmed dishwasher power threshold once without "
            "saving semantic memory."
        ),
        "warnings": [],
    }

    plan_validation_result = validate_chart_plan(
        chart_spec=chart_spec,
        entity_catalog=catalog,
    )
    if plan_validation_result["status"] == "fail":
        return {
            "entity_catalog": catalog,
            "history_series": history,
            "derived_intervals": [derived_interval],
            "planner_result": planner_result,
            "render_request": None,
            "render_result": None,
            "validation_result": plan_validation_result,
            "saved_semantic_aliases": [],
        }

    render_request = {
        "request_id": "fake-threshold-use-once",
        "render_mode": "safe",
        "chart_spec": chart_spec,
        "history_series": history,
        "derived_intervals": [derived_interval],
        "output": {"format": "png", "width": 1000, "height": 600},
        "theme": {},
        "codegen": None,
    }
    render_result = invoke_trusted_renderer(
        render_request=render_request,
        output_directory=output_directory,
    )
    validation_result = validate_chart_job(
        chart_spec=chart_spec,
        render_result=render_result,
        entity_catalog=catalog,
        expected_start=now - timedelta(hours=24),
        expected_end=now,
    )

    return {
        "entity_catalog": catalog,
        "history_series": history,
        "derived_intervals": [derived_interval],
        "planner_result": planner_result,
        "render_request": render_request,
        "render_result": render_result,
        "validation_result": validation_result,
        "saved_semantic_aliases": [],
    }


def _alias_id_from_name(alias_name: str) -> str:
    alias_id = re.sub(r"[^a-z0-9]+", "_", alias_name.lower()).strip("_")
    if not alias_id:
        raise ValueError("alias_name must contain at least one alphanumeric character.")
    return alias_id


def invoke_threshold_confirmation_use_and_remember(
    *,
    prompt: str,
    confirmation_value: dict[str, Any],
    alias_name: str,
    output_directory: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    if now is None:
        now = datetime.now(timezone.utc)

    result = invoke_threshold_confirmation_use_once(
        prompt=prompt,
        confirmation_value=confirmation_value,
        output_directory=output_directory,
        now=now,
    )
    alias = {
        "alias_id": _alias_id_from_name(alias_name),
        "natural_names": [alias_name],
        "meaning": {
            "type": "threshold_interval",
            "entity_id": confirmation_value["entity_id"],
            "operator": confirmation_value["operator"],
            "value": confirmation_value["value"],
            "unit": confirmation_value.get("unit"),
        },
        "source": "user_confirmed",
        "created_from_prompt": prompt,
        "created_at": iso_timestamp(now),
        "last_used_at": iso_timestamp(now),
        "enabled": True,
    }

    result["saved_semantic_aliases"] = [alias]
    result["planner_result"]["reasoning_summary"] = (
        "Applied the user-confirmed dishwasher power threshold and created a "
        "semantic alias for future prompts."
    )
    return result
