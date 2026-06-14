import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.contracts import validate_contract  # noqa: E402
from Isolinear.fake_slice import (  # noqa: E402
    get_fake_approved_entity_catalog,
    get_fake_normalized_history,
    invoke_trusted_renderer,
    iso_timestamp,
    validate_chart_job,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Expected {expected!r} but got {actual!r}.")


def main():
    now = datetime(2026, 5, 29, 15, 0, 0, tzinfo=timezone.utc)
    start = now - timedelta(hours=24)
    chart_spec = {
        "chart_id": "temperature_with_dishwasher_overlay",
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
                "unit": "\u00b0F",
            }
        ],
        "overlays": [
            {
                "overlay_id": "dishwasher_running",
                "label": "Dishwasher Running",
                "source": {
                    "type": "entity",
                    "entity_id": "sensor.upstairs_temperature",
                    "attribute": None,
                },
                "render_as": "shaded_intervals",
                "active_values": ["on"],
            }
        ],
        "x_axis": {"type": "time"},
        "y_axis": {"label": "\u00b0F"},
        "notes": [],
    }
    derived_interval = {
        "interval_id": "dishwasher_running",
        "label": "Dishwasher Running",
        "source_entity_id": "sensor.upstairs_temperature",
        "source_attribute": None,
        "rule": {"state": "on"},
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
    render_request = {
        "request_id": "fake-shaded-overlay",
        "render_mode": "safe",
        "chart_spec": chart_spec,
        "history_series": get_fake_normalized_history(now=now),
        "derived_intervals": [derived_interval],
        "output": {"format": "png", "width": 1000, "height": 600},
        "theme": {},
        "codegen": None,
    }

    output_root = REPO_ROOT / ".eval-output"
    output_root.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory(dir=output_root) as run_directory:
        render_result = invoke_trusted_renderer(
            render_request=render_request,
            output_directory=Path(run_directory),
        )
        validation_result = validate_chart_job(
            chart_spec=chart_spec,
            render_result=render_result,
            entity_catalog=get_fake_approved_entity_catalog(),
            expected_start=start,
            expected_end=now,
        )

    assert_equal(render_result["status"], "success", "Renderer status should match eval expectation.")
    assert_equal(
        render_result["render_metadata"]["overlays_plotted"],
        ["dishwasher_running"],
        "Plotted overlays should match eval expectation.",
    )
    assert_equal(validation_result["status"], "pass", "Validation status should match eval expectation.")
    validate_contract("render-request", render_request, repo_root=REPO_ROOT)
    validate_contract("render-result", render_result, repo_root=REPO_ROOT)
    validate_contract("validation-result", validation_result, repo_root=REPO_ROOT)

    print_case(
        "shaded_interval_rendering",
        given={
            "chart_spec": {
                "chart_id": chart_spec["chart_id"],
                "chart_type": chart_spec["chart_type"],
                "title": chart_spec["title"],
                "time_range": chart_spec["time_range"],
                "series": [
                    {
                        "series_id": series["series_id"],
                        "label": series["label"],
                        "source": series["source"],
                        "role": series["role"],
                        "render_as": series["render_as"],
                        "unit": series["unit"],
                    }
                    for series in chart_spec["series"]
                ],
                "overlays": chart_spec["overlays"],
            },
            "derived_interval": derived_interval,
            "output": render_request["output"],
        },
        when={
            "operation": "invoke_trusted_renderer_then_validate_chart_job",
            "request_id": render_request["request_id"],
        },
        then={
            "render_status": render_result["status"],
            "image_mime_type": render_result["image_mime_type"],
            "render_metadata": render_result["render_metadata"],
            "validation_status": validation_result["status"],
            "validation_checks": [
                {"name": check["name"], "status": check["status"]}
                for check in validation_result["checks"]
            ],
        },
    )
    print("PASS shaded_interval_rendering")


if __name__ == "__main__":
    main()
