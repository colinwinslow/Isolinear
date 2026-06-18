"""In-process trusted Pillow renderer for the first real slice.

Rendering uses Pillow (PIL), which Home Assistant core already ships, instead of
matplotlib. matplotlib cannot be installed through the integration manifest in a
stock Home Assistant Python environment: there is no prebuilt wheel for the
runtime's CPython and the package-install sandbox cannot compile it from source
(meson is not executable). See ADR-0019.
"""

from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime
from io import BytesIO
from typing import Any

from .const import DOMAIN, RENDER_MODE_AUTO, RENDER_MODE_SAFE


DATA_FIRST_REAL_VERTICAL_SLICE_ENABLED = "first_real_vertical_slice_enabled"
IN_PROCESS_RENDERER_NAME = "in_process_pillow"
PNG_DATA_URL_PREFIX = "data:image/png;base64,"
MAX_IN_PROCESS_PNG_BYTES = 2_000_000

# Deterministic, color-blind-friendly series palette (RGB).
_SERIES_COLORS = (
    (31, 119, 180),
    (255, 127, 14),
    (44, 160, 44),
    (214, 39, 40),
    (148, 103, 189),
    (140, 86, 75),
)


def first_real_vertical_slice_enabled(hass: Any, entry_id: str) -> bool:
    """Return whether the first real in-process renderer path is enabled."""
    domain_data = getattr(hass, "data", {}).get(DOMAIN, {})
    entry_data = domain_data.get(entry_id) if isinstance(domain_data, dict) else None
    if isinstance(entry_data, dict) and entry_data.get(DATA_FIRST_REAL_VERTICAL_SLICE_ENABLED) is True:
        return True
    if isinstance(domain_data, dict) and domain_data.get(DATA_FIRST_REAL_VERTICAL_SLICE_ENABLED) is True:
        return True
    return _looks_like_real_home_assistant(hass)


def render_in_process_chart(render_request: dict[str, Any]) -> dict[str, Any]:
    """Render a trusted ChartSpec to PNG bytes and a data URL."""
    unsupported = _unsupported_time_series_request(render_request)
    if unsupported:
        return _render_failure(
            render_request,
            "unsupported_chart_spec",
            "The in-process renderer supports only safe numeric time-series line charts.",
            {"unsupported": unsupported},
        )

    try:
        png_bytes, metadata = _render_time_series_png(render_request)
    except ImportError as exc:
        return _render_failure(
            render_request,
            "renderer_dependency_unavailable",
            "The trusted chart renderer dependency is not available in this Home Assistant environment.",
            {
                "exception_type": type(exc).__name__,
                "missing_module": getattr(exc, "name", None),
            },
        )
    except Exception as exc:  # pragma: no cover - defensive runtime boundary.
        return _render_failure(
            render_request,
            "in_process_renderer_failed",
            str(exc),
            {"exception_type": type(exc).__name__},
        )

    if len(png_bytes) > MAX_IN_PROCESS_PNG_BYTES:
        return _render_failure(
            render_request,
            "in_process_renderer_output_too_large",
            "The rendered PNG exceeded the maximum in-process output size.",
            {"max_bytes": MAX_IN_PROCESS_PNG_BYTES, "observed_bytes": len(png_bytes)},
        )

    image_id = f"{render_request['request_id']}-image"
    render_result = {
        "request_id": render_request["request_id"],
        "status": "success",
        "image_id": image_id,
        "image_mime_type": "image/png",
        "image_path": None,
        "error": None,
        "render_metadata": {
            "title": render_request["chart_spec"]["title"],
            "series_plotted": metadata["series_plotted"],
            "overlays_plotted": [],
            "x_min": metadata["x_min"],
            "x_max": metadata["x_max"],
            "warnings": metadata["warnings"],
            "codegen_attempts": 0,
        },
    }
    data_url = PNG_DATA_URL_PREFIX + base64.b64encode(png_bytes).decode("ascii")
    return {
        "accepted": True,
        "code": "in_process_render_succeeded",
        "renderer": IN_PROCESS_RENDERER_NAME,
        "render_result": render_result,
        "image_url": data_url,
        "png_bytes": png_bytes,
        "png_byte_count": len(png_bytes),
    }


def png_signature_from_data_url(image_url: str) -> bytes:
    """Decode the first eight bytes from a PNG data URL."""
    if not image_url.startswith(PNG_DATA_URL_PREFIX):
        return b""
    return base64.b64decode(image_url.removeprefix(PNG_DATA_URL_PREFIX))[:8]


def _unsupported_time_series_request(render_request: dict[str, Any]) -> list[dict[str, Any]]:
    unsupported: list[dict[str, Any]] = []
    if render_request.get("render_mode") not in {RENDER_MODE_SAFE, RENDER_MODE_AUTO}:
        unsupported.append({"path": "$.render_mode", "reason": "unsupported_render_mode"})
    output = render_request.get("output") or {}
    if output.get("format", "png") != "png":
        unsupported.append({"path": "$.output.format", "reason": "png_required"})

    chart_spec = render_request.get("chart_spec")
    if not isinstance(chart_spec, dict):
        return [{"path": "$.chart_spec", "reason": "must_be_object"}]
    if chart_spec.get("chart_type") != "time_series":
        unsupported.append({"path": "$.chart_spec.chart_type", "reason": "time_series_required"})
    if chart_spec.get("overlays") not in (None, []):
        unsupported.append({"path": "$.chart_spec.overlays", "reason": "overlays_not_supported"})

    series = chart_spec.get("series")
    if not isinstance(series, list) or not series:
        unsupported.append({"path": "$.chart_spec.series", "reason": "must_be_non_empty_list"})
        return unsupported

    for index, item in enumerate(series):
        if not isinstance(item, dict):
            unsupported.append({"path": f"$.chart_spec.series[{index}]", "reason": "must_be_object"})
            continue
        source = item.get("source")
        if not isinstance(source, dict) or source.get("type") != "entity":
            unsupported.append({"path": f"$.chart_spec.series[{index}].source", "reason": "entity_source_required"})
        if item.get("render_as", "line") != "line":
            unsupported.append({"path": f"$.chart_spec.series[{index}].render_as", "reason": "line_required"})
        transform = item.get("transform")
        if isinstance(transform, dict) and transform.get("operation", "none") != "none":
            unsupported.append({"path": f"$.chart_spec.series[{index}].transform", "reason": "transform_not_supported"})

    history = render_request.get("history_series")
    if not isinstance(history, list):
        unsupported.append({"path": "$.history_series", "reason": "must_be_list"})
    return unsupported


def _render_time_series_png(render_request: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    from PIL import Image, ImageDraw

    chart_spec = render_request["chart_spec"]
    output = render_request.get("output") or {}
    width = max(int(output.get("width") or 1400), 200)
    height = max(int(output.get("height") or 800), 150)

    history_by_entity = {
        item.get("entity_id"): item
        for item in render_request.get("history_series", [])
        if isinstance(item, dict) and isinstance(item.get("entity_id"), str)
    }

    series_plotted: list[str] = []
    plotted: list[tuple[str, list[datetime], list[float], list[float] | None, list[float] | None]] = []
    all_timestamps: list[datetime] = []
    all_values: list[float] = []
    warnings: list[str] = []
    for series_spec in chart_spec["series"]:
        entity_id = series_spec["source"]["entity_id"]
        history = history_by_entity.get(entity_id)
        if history is None:
            raise ValueError(f"Missing history for {entity_id}.")
        if history.get("kind") != "numeric":
            raise ValueError(f"History for {entity_id} is not numeric.")

        rows: list[tuple[datetime, float, float | None, float | None]] = []
        for point in history.get("points", []):
            if not isinstance(point, dict) or point.get("quality") != "ok":
                continue
            value = point.get("value")
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            rows.append(
                (
                    _parse_timestamp(point.get("ts")),
                    float(value),
                    _numeric_or_none(point.get("value_min")),
                    _numeric_or_none(point.get("value_max")),
                )
            )

        if not rows:
            raise ValueError(f"History for {entity_id} has no numeric points.")

        rows.sort(key=lambda row: row[0])
        timestamps = [row[0] for row in rows]
        values = [row[1] for row in rows]
        # A min/max band is drawn only when every point carries both bounds
        # (long-term statistics buckets); raw recorder series have none.
        if all(row[2] is not None and row[3] is not None for row in rows):
            mins = [row[2] for row in rows]
            maxs = [row[3] for row in rows]
        else:
            mins = None
            maxs = None
        label = series_spec.get("label") or entity_id
        plotted.append((label, timestamps, values, mins, maxs))
        all_timestamps.extend(timestamps)
        all_values.extend(values)
        if mins is not None and maxs is not None:
            all_values.extend(mins)
            all_values.extend(maxs)
        series_plotted.append(series_spec["series_id"])

    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    # The 1400x800 PNG is downscaled to a phone-width card (~3-4x), so fonts and
    # strokes are sized large in source pixels to survive that reduction.
    title_font = _load_font(max(34, width // 24))
    label_font = _load_font(max(24, width // 40))
    tick_font = _load_font(max(20, width // 48))
    series_weight = max(4, width // 280)
    axis_weight = max(3, width // 500)
    grid_weight = max(2, width // 900)

    title = chart_spec["title"]
    title_w, title_h = _text_size(draw, title, title_font)
    draw.text(((width - title_w) / 2, 20), title, fill=(20, 20, 20), font=title_font)

    plot_left = max(120, width // 11)
    plot_right = width - max(36, width // 36)
    plot_top = 24 + title_h + 24
    plot_bottom = height - max(104, height // 7)

    t_min = min(all_timestamps)
    t_max = max(all_timestamps)
    t_span = (t_max - t_min).total_seconds() or 1.0
    v_min = min(all_values)
    v_max = max(all_values)
    if v_min == v_max:
        v_min -= 1.0
        v_max += 1.0
    v_pad = (v_max - v_min) * 0.05
    v_min -= v_pad
    v_max += v_pad
    v_span = (v_max - v_min) or 1.0

    def x_px(ts: datetime) -> float:
        return plot_left + (ts - t_min).total_seconds() / t_span * (plot_right - plot_left)

    def y_px(value: float) -> float:
        return plot_bottom - (value - v_min) / v_span * (plot_bottom - plot_top)

    # Horizontal gridlines and y-axis tick labels.
    for index in range(6):
        value = v_min + v_span * index / 5
        y = y_px(value)
        draw.line([(plot_left, y), (plot_right, y)], fill=(232, 232, 232), width=grid_weight)
        label = f"{value:.1f}"
        label_w, label_h = _text_size(draw, label, tick_font)
        draw.text((plot_left - 14 - label_w, y - label_h / 2), label, fill=(90, 90, 90), font=tick_font)

    # Axis lines.
    draw.line([(plot_left, plot_top), (plot_left, plot_bottom)], fill=(60, 60, 60), width=axis_weight)
    draw.line([(plot_left, plot_bottom), (plot_right, plot_bottom)], fill=(60, 60, 60), width=axis_weight)

    # X-axis time tick labels (start, middle, end).
    for frac, align in ((0.0, "left"), (0.5, "center"), (1.0, "right")):
        ts = t_min + (t_max - t_min) * frac
        x = x_px(ts)
        text = ts.strftime("%m-%d %H:%M")
        text_w, _ = _text_size(draw, text, tick_font)
        if align == "left":
            anchor_x = x
        elif align == "right":
            anchor_x = x - text_w
        else:
            anchor_x = x - text_w / 2
        anchor_x = max(0, min(anchor_x, width - text_w))
        draw.text((anchor_x, plot_bottom + 14), text, fill=(90, 90, 90), font=tick_font)

    # Min/max bands (statistics series) are drawn behind the mean lines.
    for index, (label, timestamps, values, mins, maxs) in enumerate(plotted):
        if mins is None or maxs is None or len(timestamps) < 2:
            continue
        color = _SERIES_COLORS[index % len(_SERIES_COLORS)]
        band_fill = _band_tint(color)
        upper = [(x_px(ts), y_px(value)) for ts, value in zip(timestamps, maxs)]
        lower = [(x_px(ts), y_px(value)) for ts, value in zip(timestamps, mins)]
        polygon = upper + list(reversed(lower))
        draw.polygon(polygon, fill=band_fill)

    # Series polylines (mean).
    marker_radius = max(4, series_weight)
    for index, (label, timestamps, values, mins, maxs) in enumerate(plotted):
        color = _SERIES_COLORS[index % len(_SERIES_COLORS)]
        points = [(x_px(ts), y_px(value)) for ts, value in zip(timestamps, values)]
        if len(points) == 1:
            cx, cy = points[0]
            draw.ellipse(
                [(cx - marker_radius, cy - marker_radius), (cx + marker_radius, cy + marker_radius)],
                fill=color,
            )
        else:
            draw.line(points, fill=color, width=series_weight, joint="curve")

    # Legend (top-right inside the plot).
    legend_y = plot_top + 10
    swatch_w = max(28, width // 50)
    for index, (label, _, _, _, _) in enumerate(plotted):
        color = _SERIES_COLORS[index % len(_SERIES_COLORS)]
        label_w, label_h = _text_size(draw, label, label_font)
        entry_w = swatch_w + 10 + label_w
        entry_x = plot_right - entry_w - 10
        draw.line(
            [(entry_x, legend_y + label_h / 2), (entry_x + swatch_w, legend_y + label_h / 2)],
            fill=color,
            width=series_weight,
        )
        draw.text((entry_x + swatch_w + 10, legend_y), label, fill=(40, 40, 40), font=label_font)
        legend_y += label_h + 10

    # Y-axis label (rotated) and x-axis label.
    y_label = _y_axis_label(chart_spec)
    if y_label:
        _draw_vertical_text(image, y_label, 16, (plot_top + plot_bottom) / 2, label_font, (60, 60, 60))
    x_label = "Time"
    x_label_w, x_label_h = _text_size(draw, x_label, label_font)
    draw.text(
        ((plot_left + plot_right) / 2 - x_label_w / 2, height - x_label_h - 16),
        x_label,
        fill=(60, 60, 60),
        font=label_font,
    )

    buffer = BytesIO()
    image.save(buffer, format="PNG")

    x_min = min(all_timestamps).isoformat(timespec="seconds")
    x_max = max(all_timestamps).isoformat(timespec="seconds")
    return buffer.getvalue(), {
        "series_plotted": series_plotted,
        "x_min": x_min,
        "x_max": x_max,
        "warnings": warnings,
    }


def _load_font(size: int) -> Any:
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1 has no sizeable default font.
        return ImageFont.load_default()


def _text_size(draw: Any, text: str, font: Any) -> tuple[float, float]:
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:  # pragma: no cover - defensive font-metric fallback.
        try:
            return float(draw.textlength(text, font=font)), float(getattr(font, "size", 12))
        except Exception:
            return float(len(text) * 7), 12.0


def _draw_vertical_text(image: Any, text: str, x: float, y_center: float, font: Any, fill: Any) -> None:
    from PIL import Image, ImageDraw

    measure = ImageDraw.Draw(image)
    text_w, text_h = _text_size(measure, text, font)
    text_w = max(int(round(text_w)), 1)
    text_h = max(int(round(text_h)), 1)
    tile = Image.new("RGBA", (text_w, text_h), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((0, 0), text, font=font, fill=fill)
    rotated = tile.rotate(90, expand=True)
    image.paste(rotated, (int(x), int(y_center - rotated.height / 2)), rotated)


def _render_failure(
    render_request: dict[str, Any],
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_id = render_request.get("request_id") if isinstance(render_request, dict) else None
    return {
        "accepted": False,
        "code": code,
        "renderer": IN_PROCESS_RENDERER_NAME,
        "render_result": {
            "request_id": request_id or "unknown-render-request",
            "status": "failed",
            "image_id": None,
            "image_mime_type": None,
            "image_path": None,
            "error": {
                "code": code,
                "message": message,
                "details": deepcopy(details or {}),
            },
            "render_metadata": {
                "title": None,
                "series_plotted": [],
                "overlays_plotted": [],
                "x_min": None,
                "x_max": None,
                "warnings": [code],
                "codegen_attempts": 0,
            },
        },
    }


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("History point timestamp must be a non-empty string.")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _numeric_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _band_tint(color: tuple[int, int, int]) -> tuple[int, int, int]:
    """Return a light tint of the series color for the min/max band fill."""
    return tuple(int(round(channel * 0.25 + 255 * 0.75)) for channel in color)


def _y_axis_label(chart_spec: dict[str, Any]) -> str | None:
    y_axis = chart_spec.get("y_axis")
    if isinstance(y_axis, dict):
        label = y_axis.get("label")
        if isinstance(label, str) and label.strip():
            return label.strip()
    units = {
        series.get("unit")
        for series in chart_spec.get("series", [])
        if isinstance(series, dict) and isinstance(series.get("unit"), str) and series.get("unit")
    }
    if len(units) == 1:
        return next(iter(units))
    return None


def _looks_like_real_home_assistant(hass: Any) -> bool:
    module_name = type(hass).__module__
    if isinstance(module_name, str) and module_name.startswith("homeassistant."):
        return True
    return (
        hasattr(hass, "config_entries")
        and hasattr(hass, "states")
        and hasattr(hass, "bus")
        and hasattr(hass, "loop")
    )
