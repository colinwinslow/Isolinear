import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.contracts import validate_contract  # noqa: E402
from Isolinear.fake_slice import (  # noqa: E402
    get_fake_approved_entity_catalog,
    invoke_fake_prompt_to_chart,
)


PROMPT = "Mark when the dishwasher was running over the last day"


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Expected {expected!r} but got {actual!r}.")


def make_saved_alias(entity_id, now):
    return {
        "alias_id": "dishwasher_running",
        "natural_names": ["dishwasher running"],
        "meaning": {
            "type": "threshold_interval",
            "entity_id": entity_id,
            "operator": ">",
            "value": 5,
            "unit": "W",
        },
        "source": "user_confirmed",
        "created_from_prompt": PROMPT,
        "created_at": now.isoformat(timespec="seconds"),
        "last_used_at": now.isoformat(timespec="seconds"),
        "enabled": True,
    }


def make_catalog_with_dishwasher_power_hidden():
    catalog = []
    for item in get_fake_approved_entity_catalog():
        updated_item = dict(item)
        if updated_item["entity_id"] == "sensor.dishwasher_power":
            updated_item["visible_to_agent"] = False
        catalog.append(updated_item)
    return catalog


def run_case(
    *,
    case_id,
    entity_state,
    saved_alias,
    expected_status,
    expected_invalid_alias,
    output_root,
    now,
    entity_catalog=None,
):
    with tempfile.TemporaryDirectory(dir=output_root) as run_directory:
        result = invoke_fake_prompt_to_chart(
            prompt=PROMPT,
            output_directory=Path(run_directory),
            now=now,
            semantic_aliases=[saved_alias],
            entity_catalog=entity_catalog,
        )

    planner_result = result["planner_result"]
    observed = {
        "case_id": case_id,
        "given": {
            "semantic_alias": saved_alias,
            "entity_state": entity_state,
        },
        "when": {
            "prompt": PROMPT,
        },
        "then": {
            "planner_status": planner_result["status"],
            "clarification_question_id": (
                None
                if planner_result["clarification_question"] is None
                else planner_result["clarification_question"]["question_id"]
            ),
            "invalid_semantic_aliases": result["invalid_semantic_aliases"],
            "render_request": result["render_request"],
            "render_result": result["render_result"],
            "validation_result": result["validation_result"],
        },
    }

    assert_equal(
        planner_result["status"],
        expected_status,
        "Planner should not reuse invalid alias.",
    )
    assert_equal(
        result["render_request"],
        None,
        "Invalid alias should not produce a render request.",
    )
    assert_equal(result["render_result"], None, "Invalid alias should not render a chart.")
    assert_equal(
        result["validation_result"],
        None,
        "Invalid alias should not reach chart validation.",
    )
    assert_equal(
        result["invalid_semantic_aliases"],
        [expected_invalid_alias],
        "Invalid alias should be reported with a deterministic reason.",
    )

    validate_contract("semantic-alias", saved_alias, repo_root=REPO_ROOT)
    validate_contract("planner-result", planner_result, repo_root=REPO_ROOT)
    if planner_result["clarification_question"] is not None:
        validate_contract(
            "clarification-question",
            planner_result["clarification_question"],
            repo_root=REPO_ROOT,
        )

    print(f"CASE {case_id}")
    print(json.dumps(observed, indent=2, sort_keys=True))
    print(f"PASS {case_id}")


def main():
    now = datetime(2026, 5, 29, 15, 0, 0, tzinfo=timezone.utc)
    output_root = REPO_ROOT / ".eval-output"
    output_root.mkdir(exist_ok=True)

    run_case(
        case_id="unavailable_entity",
        entity_state="unavailable",
        saved_alias=make_saved_alias("sensor.retired_dishwasher_power", now),
        expected_status="clarification_needed",
        expected_invalid_alias={
            "alias_id": "dishwasher_running",
            "entity_id": "sensor.retired_dishwasher_power",
            "reason": "entity_unavailable",
        },
        output_root=output_root,
        now=now,
    )
    run_case(
        case_id="non_allowlisted_entity",
        entity_state="no longer allowlisted",
        saved_alias=make_saved_alias("sensor.dishwasher_power", now),
        expected_status="cannot_resolve",
        expected_invalid_alias={
            "alias_id": "dishwasher_running",
            "entity_id": "sensor.dishwasher_power",
            "reason": "entity_not_allowlisted",
        },
        output_root=output_root,
        now=now,
        entity_catalog=make_catalog_with_dishwasher_power_hidden(),
    )

    print("PASS semantic_alias_invalidation")


if __name__ == "__main__":
    main()
