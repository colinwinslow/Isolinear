"""In-process trusted matplotlib renderer for the first real slice."""

from __future__ import annotations

import base64
import os
import tempfile
from copy import deepcopy
from datetime import datetime
from io import BytesIO
from typing import Any

from .const import DOMAIN, RENDER_MODE_AUTO, RENDER_MODE_SAFE


DATA_FIRST_REAL_VERTICAL_SLICE_ENABLED = "first_real_vertical_slice_enabled"
IN_PROCESS_RENDERER_NAME = "in_process_matplotlib"
PNG_DATA_URL_PREFIX = "data:image/png;base64,"
MAX_IN_PROCESS_PNG_BYTES = 2_000_000


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
    os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="isolinear-matplotlib-"))

    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    chart_spec = render_request["chart_spec"]
    output = render_request.get("output") or {}
    width = int(output.get("width") or 1400)
    height = int(output.get("height") or 800)
    dpi = 100
    fig, ax = plt.subplots(figsize=(width / dpi, height / dpi), dpi=dpi)
    history_by_entity = {
        item.get("entity_id"): item
        for item in render_request.get("history_series", [])
        if isinstance(item, dict) and isinstance(item.get("entity_id"), str)
    }

    series_plotted: list[str] = []
    all_timestamps: list[datetime] = []
    warnings: list[str] = []
    for series_spec in chart_spec["series"]:
        entity_id = series_spec["source"]["entity_id"]
        history = history_by_entity.get(entity_id)
        if history is None:
            raise ValueError(f"Missing history for {entity_id}.")
        if history.get("kind") != "numeric":
            raise ValueError(f"History for {entity_id} is not numeric.")

        timestamps: list[datetime] = []
        values: list[float] = []
        for point in history.get("points", []):
            if not isinstance(point, dict) or point.get("quality") != "ok":
                continue
            value = point.get("value")
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            timestamps.append(_parse_timestamp(point.get("ts")))
            values.append(float(value))

        if not timestamps:
            raise ValueError(f"History for {entity_id} has no numeric points.")

        ax.plot(timestamps, values, linewidth=2, label=series_spec.get("label") or entity_id)
        all_timestamps.extend(timestamps)
        series_plotted.append(series_spec["series_id"])

    ax.set_title(chart_spec["title"])
    ax.set_xlabel("Time")
    y_label = _y_axis_label(chart_spec)
    if y_label:
        ax.set_ylabel(y_label)
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.autofmt_xdate()
    fig.tight_layout()

    buffer = BytesIO()
    fig.savefig(buffer, format="png")
    plt.close(fig)

    x_min = min(all_timestamps).isoformat(timespec="seconds")
    x_max = max(all_timestamps).isoformat(timespec="seconds")
    return buffer.getvalue(), {
        "series_plotted": series_plotted,
        "x_min": x_min,
        "x_max": x_max,
        "warnings": warnings,
    }


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
