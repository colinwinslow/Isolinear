import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.contracts import validate_contract  # noqa: E402
from Isolinear.fake_slice import invoke_threshold_confirmation_use_once  # noqa: E402


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Expected {expected!r} but got {actual!r}.")


def main():
    now = datetime(2026, 5, 29, 15, 0, 0, tzinfo=timezone.utc)
    confirmation_value = {
        "type": "threshold_interval",
        "entity_id": "sensor.dishwasher_power",
        "operator": ">",
        "value": 5,
        "unit": "W",
    }
    output_root = REPO_ROOT / ".eval-output"
    output_root.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory(dir=output_root) as run_directory:
        result = invoke_threshold_confirmation_use_once(
            prompt="Mark when the dishwasher was running over the last day",
            confirmation_value=confirmation_value,
            output_directory=Path(run_directory),
            now=now,
        )

    planner_result = result["planner_result"]
    render_result = result["render_result"]
    validation_result = result["validation_result"]
    derived_interval = result["derived_intervals"][0]

    assert_equal(planner_result["status"], "chart_spec_ready", "Planner should continue after use-once confirmation.")
    assert_equal(
        planner_result["chart_spec"]["chart_id"],
        "temperature_with_threshold_dishwasher_overlay",
        "Chart spec id should match expectation.",
    )
    assert_equal(derived_interval["interval_id"], "dishwasher_running", "Derived interval id should match expectation.")
    assert_equal(
        render_result["render_metadata"]["overlays_plotted"],
        ["dishwasher_running"],
        "Rendered overlays should match expectation.",
    )
    assert_equal(validation_result["status"], "pass", "Validation should pass.")
    assert_equal(result["saved_semantic_aliases"], [], "Use once should not save semantic memory.")

    validate_contract("planner-result", planner_result, repo_root=REPO_ROOT)
    validate_contract("chart-spec", planner_result["chart_spec"], repo_root=REPO_ROOT)
    validate_contract("history-series", result["history_series"][0], repo_root=REPO_ROOT)
    validate_contract("derived-interval", derived_interval, repo_root=REPO_ROOT)
    validate_contract("render-request", result["render_request"], repo_root=REPO_ROOT)
    validate_contract("render-result", render_result, repo_root=REPO_ROOT)
    validate_contract("validation-result", validation_result, repo_root=REPO_ROOT)

    print("PASS threshold_interval_use_once")


if __name__ == "__main__":
    main()
