import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from Isolinear.contracts import validate_contract  # noqa: E402
from Isolinear.fake_slice import (  # noqa: E402
    get_fake_raw_numeric_history_records,
    normalize_numeric_history_records,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Expected {expected!r} but got {actual!r}.")


def main():
    now = datetime(2026, 5, 29, 15, 0, 0, tzinfo=timezone.utc)
    raw_records = get_fake_raw_numeric_history_records(now=now)
    series = normalize_numeric_history_records(
        raw_records=raw_records,
        series_id="upstairs_temperature",
        entity_id="sensor.upstairs_temperature",
        label="Upstairs Temperature",
        unit="\u00b0F",
    )

    assert_equal(series["series_id"], "upstairs_temperature", "Series id should match eval expectation.")
    assert_equal(
        series["entity_id"],
        "sensor.upstairs_temperature",
        "Source entity should match eval expectation.",
    )
    assert_equal(series["unit"], "\u00b0F", "Unit should match eval expectation.")
    assert_equal(
        [point["value"] for point in series["points"]],
        [70.8, 71.2, None, None, 70.9],
        "Normalized values should match eval expectation.",
    )
    assert_equal(
        [point["raw_state"] for point in series["points"]],
        ["70.8", "71.2", "unknown", "unavailable", "70.9"],
        "Raw states should be preserved.",
    )
    assert_equal(
        [point["quality"] for point in series["points"]],
        ["ok", "ok", "unknown", "unavailable", "ok"],
        "Point qualities should explain missing values.",
    )
    if not any("unknown" in warning for warning in series["warnings"]):
        raise AssertionError("Series warnings should mention unknown missing values.")
    if not any("unavailable" in warning for warning in series["warnings"]):
        raise AssertionError("Series warnings should mention unavailable missing values.")

    validate_contract("history-series", series, repo_root=REPO_ROOT)

    print_case(
        "numeric_history_normalization",
        given={
            "raw_records": raw_records,
        },
        when={
            "operation": "normalize_numeric_history_records",
            "series_id": "upstairs_temperature",
            "entity_id": "sensor.upstairs_temperature",
        },
        then={
            "series_id": series["series_id"],
            "entity_id": series["entity_id"],
            "unit": series["unit"],
            "values": [point["value"] for point in series["points"]],
            "raw_states": [point["raw_state"] for point in series["points"]],
            "qualities": [point["quality"] for point in series["points"]],
            "warnings": series["warnings"],
        },
    )
    print("PASS numeric_history_normalization")


if __name__ == "__main__":
    main()
