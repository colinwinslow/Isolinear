import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.fake_slice import invoke_fake_prompt_to_chart  # noqa: E402
from Isolinear.contracts import validate_fake_prompt_to_chart_contracts  # noqa: E402


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Expected {expected!r} but got {actual!r}.")


def main():
    output_root = REPO_ROOT / ".eval-output"
    output_root.mkdir(exist_ok=True)
    now = datetime(2026, 5, 29, 15, 0, 0, tzinfo=timezone.utc)

    with tempfile.TemporaryDirectory(dir=output_root) as run_directory:
        result = invoke_fake_prompt_to_chart(
            prompt="Compare upstairs and downstairs temperatures over the last 24 hours",
            output_directory=Path(run_directory),
            now=now,
        )

    planner_result = result["planner_result"]
    chart_spec = planner_result["chart_spec"]

    assert_equal(planner_result["status"], "chart_spec_ready", "Planner status should match eval expectation.")
    assert_equal(chart_spec["chart_type"], "time_series", "Chart type should match eval expectation.")
    assert_equal(
        [series["source"]["entity_id"] for series in chart_spec["series"]],
        ["sensor.upstairs_temperature", "sensor.downstairs_temperature"],
        "Required series should match eval expectation.",
    )
    assert_equal(chart_spec["time_range"]["type"], "relative", "Time range type should match eval expectation.")
    assert_equal(chart_spec["time_range"]["duration"], "24h", "Time range duration should match eval expectation.")
    assert_equal(result["render_request"]["render_mode"], "safe", "Render mode should match eval expectation.")
    assert_equal(result["validation_result"]["status"], "pass", "Validation status should match eval expectation.")
    validate_fake_prompt_to_chart_contracts(result, repo_root=REPO_ROOT)

    print("PASS prompt_to_chart_basic")


if __name__ == "__main__":
    main()
