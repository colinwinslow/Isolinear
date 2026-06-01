import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.contracts import validate_contract  # noqa: E402
from Isolinear.fake_slice import invoke_threshold_confirmation_use_and_remember  # noqa: E402


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
        result = invoke_threshold_confirmation_use_and_remember(
            prompt="Mark when the dishwasher was running over the last day",
            confirmation_value=confirmation_value,
            alias_name="dishwasher running",
            output_directory=Path(run_directory),
            now=now,
        )

    alias = result["saved_semantic_aliases"][0]
    assert_equal(result["planner_result"]["status"], "chart_spec_ready", "Planner should continue after confirmation.")
    assert_equal(result["validation_result"]["status"], "pass", "Validation should pass.")
    assert_equal(len(result["saved_semantic_aliases"]), 1, "Exactly one semantic alias should be saved.")
    assert_equal(alias["alias_id"], "dishwasher_running", "Alias id should match expectation.")
    assert_equal(alias["natural_names"], ["dishwasher running"], "Natural name should match expectation.")
    assert_equal(alias["meaning"], confirmation_value, "Alias meaning should preserve the confirmed threshold.")
    assert_equal(alias["source"], "user_confirmed", "Alias source should record user confirmation.")
    assert_equal(alias["enabled"], True, "Saved alias should be enabled.")

    validate_contract("semantic-alias", alias, repo_root=REPO_ROOT)
    validate_contract("planner-result", result["planner_result"], repo_root=REPO_ROOT)
    validate_contract("chart-spec", result["planner_result"]["chart_spec"], repo_root=REPO_ROOT)
    validate_contract("render-request", result["render_request"], repo_root=REPO_ROOT)
    validate_contract("render-result", result["render_result"], repo_root=REPO_ROOT)
    validate_contract("validation-result", result["validation_result"], repo_root=REPO_ROOT)

    print_case(
        "threshold_interval_use_and_remember",
        given={
            "prompt": "Mark when the dishwasher was running over the last day",
            "confirmation_value": confirmation_value,
            "alias_name": "dishwasher running",
            "time_anchor": now.isoformat(timespec="seconds"),
        },
        when={
            "operation": "invoke_threshold_confirmation_use_and_remember",
        },
        then={
            "planner_status": result["planner_result"]["status"],
            "validation_status": result["validation_result"]["status"],
            "saved_semantic_aliases": result["saved_semantic_aliases"],
            "render_status": result["render_result"]["status"],
            "overlays_plotted": result["render_result"]["render_metadata"]["overlays_plotted"],
        },
    )
    print("PASS threshold_interval_use_and_remember")


if __name__ == "__main__":
    main()
