from __future__ import annotations

import re
import struct
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from Isolinear.contracts import ContractValidationError, validate_contract


TEMPERATURE_UNIT = "\u00b0F"
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


def create_deterministic_planner_result(
    prompt: str,
    entity_catalog: list[dict[str, Any]],
) -> dict[str, Any]:
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

    by_entity_id = {
        item["entity_id"]: item
        for item in entity_catalog
        if item.get("visible_to_agent")
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
    palette = [(32, 121, 199), (222, 112, 34)]

    canvas.draw_rect(28, 24, min(width - 28, 28 + (len(chart_spec["title"]) * 7)), 29, title_color)

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
    warnings = []

    for series_spec in render_request["chart_spec"]["series"]:
        series_id = series_spec["series_id"]
        if series_id in history_map:
            series_to_plot.append(history_map[series_id])
        else:
            warnings.append(f"Missing history for series '{series_id}'.")

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
            "overlays_plotted": [],
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
) -> dict[str, Any]:
    if now is None:
        now = datetime.now(timezone.utc)

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
