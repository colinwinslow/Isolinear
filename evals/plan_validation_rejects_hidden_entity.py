import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.contracts import validate_contract  # noqa: E402
from Isolinear.fake_slice import (  # noqa: E402
    get_fake_approved_entity_catalog,
    get_fake_normalized_history,
    invoke_validated_chart_plan,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Expected {expected!r} but got {actual!r}.")


def main():
    now = datetime(2026, 5, 29, 15, 0, 0, tzinfo=timezone.utc)
    catalog = get_fake_approved_entity_catalog()
    chart_spec = {
        "chart_id": "hidden_temperature",
        "chart_type": "time_series",
        "title": "Hidden Temperature",
        "time_range": {"type": "relative", "duration": "24h"},
        "series": [
            {
                "series_id": "hidden_temperature",
                "label": "Hidden Temperature",
                "source": {
                    "type": "entity",
                    "entity_id": "sensor.hidden_temperature",
                    "attribute": None,
                },
                "role": "primary",
                "render_as": "line",
                "transform": None,
                "unit": "\u00b0F",
            }
        ],
        "overlays": [],
        "x_axis": {"type": "time"},
        "y_axis": {"label": "\u00b0F"},
        "notes": [],
    }

    output_root = REPO_ROOT / ".eval-output"
    output_root.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory(dir=output_root) as run_directory:
        result = invoke_validated_chart_plan(
            chart_spec=chart_spec,
            entity_catalog=catalog,
            history_series=get_fake_normalized_history(now=now),
            output_directory=Path(run_directory),
            request_id="hidden-temperature",
            now=now,
            repo_root=REPO_ROOT,
        )
        assert_equal(list(Path(run_directory).iterdir()), [], "Plan failure should not create image artifacts.")

    validation_result = result["validation_result"]
    allowlist_check = next(
        check for check in validation_result["checks"] if check["name"] == "allowlisted_entities"
    )

    assert_equal(validation_result["status"], "fail", "Validation status should match eval expectation.")
    assert_equal(allowlist_check["status"], "fail", "Allowlist check should fail.")
    assert_equal(
        allowlist_check["details"]["missing_entity_ids"],
        ["sensor.hidden_temperature"],
        "Missing entity should match eval expectation.",
    )
    assert_equal(result["render_request"], None, "Render request should not be created.")
    assert_equal(result["render_result"], None, "Render result should not be created.")
    validate_contract("validation-result", validation_result, repo_root=REPO_ROOT)

    print_case(
        "plan_validation_rejects_hidden_entity",
        given={
            "chart_spec": chart_spec,
            "visible_entity_ids": [
                item["entity_id"] for item in catalog if item["visible_to_agent"]
            ],
        },
        when={
            "operation": "invoke_validated_chart_plan",
            "request_id": "hidden-temperature",
        },
        then={
            "validation_status": validation_result["status"],
            "allowlist_check": allowlist_check,
            "render_request": result["render_request"],
            "render_result": result["render_result"],
            "artifact_count": 0,
        },
    )
    print("PASS plan_validation_rejects_hidden_entity")


if __name__ == "__main__":
    main()
