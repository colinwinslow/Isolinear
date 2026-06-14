import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.contracts import validate_contract  # noqa: E402
from Isolinear.fake_slice import (  # noqa: E402
    PNG_SIGNATURE,
    extract_state_intervals,
    get_fake_approved_entity_catalog,
    get_fake_dishwasher_state_history,
    get_trusted_renderer_primitive_scope,
    invoke_trusted_renderer,
    iso_timestamp,
    validate_chart_job,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Expected {expected!r} but got {actual!r}.")


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def _timeline_chart_spec(*, start: datetime, end: datetime) -> dict:
    return {
        "chart_id": "dishwasher_state_timeline",
        "chart_type": "timeline",
        "title": "Dishwasher State Timeline",
        "time_range": {
            "type": "absolute",
            "start": iso_timestamp(start),
            "end": iso_timestamp(end),
        },
        "series": [
            {
                "series_id": "dishwasher_state",
                "label": "Dishwasher Running",
                "source": {
                    "type": "entity",
                    "entity_id": "binary_sensor.dishwasher",
                    "attribute": None,
                },
                "role": "primary",
                "render_as": "step",
                "transform": None,
                "unit": None,
            }
        ],
        "overlays": [],
        "x_axis": {"type": "time"},
        "y_axis": {"label": "state"},
        "notes": ["Selected trusted renderer follow-up family fixture."],
    }


def main():
    now = datetime(2026, 5, 29, 15, 0, 0, tzinfo=timezone.utc)
    start = now - timedelta(hours=24)
    history_series = get_fake_dishwasher_state_history(now=now)
    derived_interval = extract_state_intervals(
        history_series=history_series,
        interval_id="dishwasher_state",
        label="Dishwasher Running",
        active_values=["on"],
        range_end=now,
    )
    chart_spec = _timeline_chart_spec(start=start, end=now)
    request = {
        "request_id": "state-interval-timeline",
        "render_mode": "safe",
        "chart_spec": chart_spec,
        "history_series": [history_series],
        "derived_intervals": [derived_interval],
        "output": {"format": "png", "width": 1000, "height": 420},
        "theme": {},
        "codegen": None,
    }

    output_root = REPO_ROOT / ".eval-output"
    output_root.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory(dir=output_root) as run_directory:
        run_path = Path(run_directory)
        render_result = invoke_trusted_renderer(
            render_request=request,
            output_directory=run_path,
        )
        image_signature = Path(render_result["image_path"]).read_bytes()[:8]
        output_files = sorted(path.name for path in run_path.iterdir())
        validation_result = validate_chart_job(
            chart_spec=chart_spec,
            render_result=render_result,
            entity_catalog=get_fake_approved_entity_catalog(),
            expected_start=start,
            expected_end=now,
        )

    assert_equal(render_result["status"], "success", "Timeline should render.")
    assert_equal(render_result["image_mime_type"], "image/png", "Timeline output should be a PNG.")
    assert_equal(
        render_result["render_metadata"]["series_plotted"],
        ["dishwasher_state"],
        "Timeline metadata should list the plotted track.",
    )
    assert_equal(
        render_result["render_metadata"]["codegen_attempts"],
        0,
        "Trusted timeline renderer must not fall into codegen mode.",
    )
    assert_equal(validation_result["status"], "pass", "Timeline render should validate.")
    assert_true(image_signature == PNG_SIGNATURE, "Timeline render should create a PNG.")

    validate_contract("chart-spec", chart_spec, repo_root=REPO_ROOT)
    validate_contract("history-series", history_series, repo_root=REPO_ROOT)
    validate_contract("derived-interval", derived_interval, repo_root=REPO_ROOT)
    validate_contract("render-request", request, repo_root=REPO_ROOT)
    validate_contract("render-result", render_result, repo_root=REPO_ROOT)
    validate_contract("validation-result", validation_result, repo_root=REPO_ROOT)

    print_case(
        "state_interval_timeline",
        given={
            "selected_family": "state_interval_timeline",
            "primitive_scope": get_trusted_renderer_primitive_scope(),
            "chart_spec": chart_spec,
            "history_series": history_series,
            "derived_interval": derived_interval,
        },
        when={
            "operation": "invoke_trusted_renderer_for_state_interval_timeline",
            "render_mode": "safe",
        },
        then={
            "render_status": render_result["status"],
            "image_mime_type": render_result["image_mime_type"],
            "series_plotted": render_result["render_metadata"]["series_plotted"],
            "overlays_plotted": render_result["render_metadata"]["overlays_plotted"],
            "x_min": render_result["render_metadata"]["x_min"],
            "x_max": render_result["render_metadata"]["x_max"],
            "codegen_attempts": render_result["render_metadata"]["codegen_attempts"],
            "validation_status": validation_result["status"],
            "validation_checks": validation_result["checks"],
            "output_files": output_files,
        },
    )
    print("PASS state_interval_timeline")


if __name__ == "__main__":
    main()
