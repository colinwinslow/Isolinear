import sys
import tempfile
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.contracts import validate_contract  # noqa: E402
from Isolinear.fake_slice import (  # noqa: E402
    PNG_SIGNATURE,
    get_fake_normalized_history,
    get_trusted_renderer_primitive_scope,
    invoke_trusted_renderer,
    iso_timestamp,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Expected {expected!r} but got {actual!r}.")


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def _line_chart_spec() -> dict:
    return {
        "chart_id": "trusted_scope_temperature_lines",
        "chart_type": "time_series",
        "title": "Trusted Scope Temperature Lines",
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
                "unit": "\u00b0F",
            },
            {
                "series_id": "downstairs_temperature",
                "label": "Downstairs Temperature",
                "source": {
                    "type": "entity",
                    "entity_id": "sensor.downstairs_temperature",
                    "attribute": None,
                },
                "role": "comparison",
                "render_as": "line",
                "transform": {"operation": "none", "window": None},
                "unit": "\u00b0F",
            },
        ],
        "overlays": [],
        "x_axis": {"type": "time"},
        "y_axis": {"label": "\u00b0F"},
        "notes": ["First trusted renderer release scope fixture."],
    }


def _shaded_interval_chart_spec() -> dict:
    chart_spec = deepcopy(_line_chart_spec())
    chart_spec["chart_id"] = "trusted_scope_temperature_overlay"
    chart_spec["title"] = "Trusted Scope Temperature Overlay"
    chart_spec["series"] = [chart_spec["series"][0]]
    chart_spec["overlays"] = [
        {
            "overlay_id": "dishwasher_running",
            "label": "Dishwasher Running",
            "source": {
                "type": "entity",
                "entity_id": "binary_sensor.dishwasher",
                "attribute": None,
            },
            "render_as": "shaded_intervals",
            "active_values": ["on"],
        }
    ]
    return chart_spec


def _unsupported_area_chart_spec() -> dict:
    chart_spec = deepcopy(_line_chart_spec())
    chart_spec["chart_id"] = "trusted_scope_unsupported_area"
    chart_spec["title"] = "Trusted Scope Unsupported Area"
    chart_spec["series"][0]["render_as"] = "area"
    return chart_spec


def _render_request(
    *,
    request_id: str,
    chart_spec: dict,
    now: datetime,
    derived_intervals: list[dict] | None = None,
) -> dict:
    return {
        "request_id": request_id,
        "render_mode": "safe",
        "chart_spec": chart_spec,
        "history_series": get_fake_normalized_history(now=now),
        "derived_intervals": [] if derived_intervals is None else derived_intervals,
        "output": {"format": "png", "width": 1000, "height": 600},
        "theme": {},
        "codegen": None,
    }


def main():
    now = datetime(2026, 5, 29, 15, 0, 0, tzinfo=timezone.utc)
    start = now - timedelta(hours=24)
    primitive_scope = get_trusted_renderer_primitive_scope()
    derived_interval = {
        "interval_id": "dishwasher_running",
        "label": "Dishwasher Running",
        "source_entity_id": "binary_sensor.dishwasher",
        "source_attribute": None,
        "rule": {"active_values": ["on"]},
        "intervals": [
            {
                "start": iso_timestamp(start + timedelta(hours=8)),
                "end": iso_timestamp(start + timedelta(hours=10)),
                "state": "on",
                "reason": "Fake dishwasher running interval.",
            }
        ],
        "warnings": [],
    }
    line_request = _render_request(
        request_id="trusted-scope-lines",
        chart_spec=_line_chart_spec(),
        now=now,
    )
    overlay_request = _render_request(
        request_id="trusted-scope-overlay",
        chart_spec=_shaded_interval_chart_spec(),
        now=now,
        derived_intervals=[derived_interval],
    )
    unsupported_request = _render_request(
        request_id="trusted-scope-unsupported-area",
        chart_spec=_unsupported_area_chart_spec(),
        now=now,
    )

    output_root = REPO_ROOT / ".eval-output"
    output_root.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory(dir=output_root) as run_directory:
        run_path = Path(run_directory)
        line_result = invoke_trusted_renderer(
            render_request=line_request,
            output_directory=run_path,
        )
        overlay_result = invoke_trusted_renderer(
            render_request=overlay_request,
            output_directory=run_path,
        )
        unsupported_result = invoke_trusted_renderer(
            render_request=unsupported_request,
            output_directory=run_path,
        )

        line_image_signature = Path(line_result["image_path"]).read_bytes()[:8]
        overlay_image_signature = Path(overlay_result["image_path"]).read_bytes()[:8]
        output_files = sorted(path.name for path in run_path.iterdir())

    assert_equal(line_result["status"], "success", "Line primitive should render.")
    assert_equal(overlay_result["status"], "success", "Shaded interval primitive should render.")
    assert_equal(
        unsupported_result["status"],
        "failed",
        "Unsupported primitive should fail closed.",
    )
    assert_equal(
        unsupported_result["error"]["code"],
        "unsupported_chart_spec",
        "Unsupported primitive should return the expected error.",
    )
    assert_equal(
        unsupported_result["render_metadata"]["codegen_attempts"],
        0,
        "Trusted renderer must not fall into codegen mode.",
    )
    assert_equal(
        unsupported_result["image_path"],
        None,
        "Unsupported primitive should not create an image path.",
    )
    assert_true(line_image_signature == PNG_SIGNATURE, "Line render should create a PNG.")
    assert_true(overlay_image_signature == PNG_SIGNATURE, "Overlay render should create a PNG.")
    assert_equal(
        primitive_scope["chart_types"],
        ["time_series", "timeline", "bar", "heatmap", "histogram"],
        "Primitive scope should list all trusted chart types.",
    )
    assert_equal(
        primitive_scope["time_series"]["overlay_render_as"],
        ["shaded_intervals", "markers"],
        "Time-series scope should include marker overlays.",
    )
    assert_equal(
        primitive_scope["histogram"]["series_render_as"],
        ["histogram"],
        "Histogram scope should include histogram series.",
    )

    for request in [line_request, overlay_request, unsupported_request]:
        validate_contract("render-request", request, repo_root=REPO_ROOT)
        validate_contract("chart-spec", request["chart_spec"], repo_root=REPO_ROOT)
    validate_contract("derived-interval", derived_interval, repo_root=REPO_ROOT)
    for result in [line_result, overlay_result, unsupported_result]:
        validate_contract("render-result", result, repo_root=REPO_ROOT)

    print_case(
        "trusted_renderer_primitives",
        given={
            "primitive_scope": primitive_scope,
            "line_chart_spec": line_request["chart_spec"],
            "overlay_chart_spec": overlay_request["chart_spec"],
            "unsupported_chart_spec": unsupported_request["chart_spec"],
            "derived_interval": derived_interval,
        },
        when={
            "operation": "invoke_trusted_renderer_for_trusted_primitive_scope",
            "render_mode": "safe",
        },
        then={
            "line_render_status": line_result["status"],
            "line_series_plotted": line_result["render_metadata"]["series_plotted"],
            "overlay_render_status": overlay_result["status"],
            "overlay_plotted": overlay_result["render_metadata"]["overlays_plotted"],
            "unsupported_render_status": unsupported_result["status"],
            "unsupported_error_code": unsupported_result["error"]["code"],
            "unsupported_error_details": unsupported_result["error"]["details"],
            "unsupported_codegen_attempts": unsupported_result["render_metadata"]["codegen_attempts"],
            "output_files": output_files,
        },
    )
    print("PASS trusted_renderer_primitives")


if __name__ == "__main__":
    main()
