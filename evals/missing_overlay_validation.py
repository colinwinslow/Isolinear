import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.contracts import validate_contract  # noqa: E402
from Isolinear.fake_slice import (  # noqa: E402
    get_fake_approved_entity_catalog,
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

    with tempfile.TemporaryDirectory() as run_directory:
        image_path = Path(run_directory) / "overlay-missing.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        render_result = {
            "request_id": "overlay-missing",
            "status": "success",
            "image_id": "overlay-missing.png",
            "image_mime_type": "image/png",
            "image_path": str(image_path),
            "error": None,
            "render_metadata": {
                "title": "Temperature With Dishwasher Running",
                "series_plotted": ["upstairs_temperature"],
                "overlays_plotted": [],
                "x_min": start.isoformat(timespec="seconds"),
                "x_max": now.isoformat(timespec="seconds"),
                "warnings": [],
                "codegen_attempts": 0,
            },
        }
        validation_result = validate_chart_job(
            chart_spec=chart_spec,
            render_result=render_result,
            entity_catalog=get_fake_approved_entity_catalog(),
            expected_start=start,
            expected_end=now,
        )

    overlay_check = next(
        check for check in validation_result["checks"] if check["name"] == "rendered_overlays"
    )

    assert_equal(validation_result["status"], "fail", "Validation status should match eval expectation.")
    assert_equal(overlay_check["status"], "fail", "Overlay check should fail.")
    assert_equal(
        overlay_check["details"]["missing_overlay_ids"],
        ["dishwasher_running"],
        "Missing overlay should match eval expectation.",
    )
    validate_contract("validation-result", validation_result, repo_root=REPO_ROOT)

    print("PASS missing_overlay_validation")


if __name__ == "__main__":
    main()
