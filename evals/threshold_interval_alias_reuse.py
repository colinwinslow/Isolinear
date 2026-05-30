import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.contracts import validate_contract  # noqa: E402
from Isolinear.fake_slice import invoke_fake_prompt_to_chart  # noqa: E402


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Expected {expected!r} but got {actual!r}.")


def main():
    now = datetime(2026, 5, 29, 15, 0, 0, tzinfo=timezone.utc)
    saved_alias = {
        "alias_id": "dishwasher_running",
        "natural_names": ["dishwasher running"],
        "meaning": {
            "type": "threshold_interval",
            "entity_id": "sensor.dishwasher_power",
            "operator": ">",
            "value": 5,
            "unit": "W",
        },
        "source": "user_confirmed",
        "created_from_prompt": "Mark when the dishwasher was running over the last day",
        "created_at": now.isoformat(timespec="seconds"),
        "last_used_at": now.isoformat(timespec="seconds"),
        "enabled": True,
    }
    output_root = REPO_ROOT / ".eval-output"
    output_root.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory(dir=output_root) as run_directory:
        result = invoke_fake_prompt_to_chart(
            prompt="Mark when the dishwasher was running over the last day",
            output_directory=Path(run_directory),
            now=now,
            semantic_aliases=[saved_alias],
        )

    planner_result = result["planner_result"]
    assert_equal(planner_result["status"], "chart_spec_ready", "Planner should reuse saved alias.")
    assert_equal(planner_result["clarification_question"], None, "Planner should not ask clarification.")
    assert_equal(
        planner_result["chart_spec"]["chart_id"],
        "temperature_with_threshold_dishwasher_overlay",
        "Chart id should match threshold overlay chart.",
    )
    assert_equal(
        result["render_result"]["render_metadata"]["overlays_plotted"],
        ["dishwasher_running"],
        "Rendered overlays should include dishwasher running.",
    )
    assert_equal(result["validation_result"]["status"], "pass", "Validation should pass.")

    validate_contract("semantic-alias", saved_alias, repo_root=REPO_ROOT)
    validate_contract("planner-result", planner_result, repo_root=REPO_ROOT)
    validate_contract("chart-spec", planner_result["chart_spec"], repo_root=REPO_ROOT)
    validate_contract("render-request", result["render_request"], repo_root=REPO_ROOT)
    validate_contract("render-result", result["render_result"], repo_root=REPO_ROOT)
    validate_contract("validation-result", result["validation_result"], repo_root=REPO_ROOT)

    print("PASS threshold_interval_alias_reuse")


if __name__ == "__main__":
    main()
