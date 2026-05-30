import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.contracts import validate_contract  # noqa: E402
from Isolinear.fake_slice import (  # noqa: E402
    create_deterministic_planner_result,
    get_fake_approved_entity_catalog,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Expected {expected!r} but got {actual!r}.")


def main():
    catalog = [
        item
        for item in get_fake_approved_entity_catalog()
        if item["entity_id"] == "sensor.dishwasher_power"
    ]
    planner_result = create_deterministic_planner_result(
        prompt="Mark when the dishwasher was running over the last day",
        entity_catalog=catalog,
    )
    question = planner_result["clarification_question"]

    assert_equal(
        planner_result["status"],
        "clarification_needed",
        "Planner should ask for threshold confirmation.",
    )
    if question is None:
        raise AssertionError("Planner should include a clarification question.")

    message = question["message"].lower()
    for expected_text in ["threshold", "dishwasher", "running"]:
        if expected_text not in message:
            raise AssertionError(f"Clarification should mention {expected_text!r}.")

    option = question["options"][0]
    assert_equal(
        option["value"]["entity_id"],
        "sensor.dishwasher_power",
        "Clarification should propose the dishwasher power entity.",
    )
    assert_equal(
        option["value"]["type"],
        "threshold_interval",
        "Clarification should propose a threshold interval.",
    )
    assert_equal(option["value"]["operator"], ">", "Threshold operator should match expectation.")
    assert_equal(option["value"]["value"], 5, "Threshold value should match expectation.")
    assert_equal(option["value"]["unit"], "W", "Threshold unit should match expectation.")
    assert_equal(option["can_remember"], True, "Threshold confirmation should be rememberable.")
    assert_equal(planner_result["chart_spec"], None, "Clarification should not create a chart spec yet.")

    validate_contract("planner-result", planner_result, repo_root=REPO_ROOT)
    validate_contract("clarification-question", question, repo_root=REPO_ROOT)

    print("PASS threshold_interval_inference")


if __name__ == "__main__":
    main()
