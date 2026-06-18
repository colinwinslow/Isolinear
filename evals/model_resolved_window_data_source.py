"""Eval: model-resolved time window (ADR-0020) + tiered data source (ADR-0021).

Exercises the deterministic clamp/validate layer and the data-source tier
selection without a live model or recorder, emitting CASE evidence.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from evidence import print_case


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from custom_components.isolinear.job_orchestration import resolve_history_window  # noqa: E402
from custom_components.isolinear.history_retrieval import (  # noqa: E402
    _normalize_statistics_series,
    _select_history_tier,
)


NOW = datetime(2026, 6, 18, 12, 0, 0, tzinfo=timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Expected {expected!r} but got {actual!r}.")


def _absolute(start, end):
    return {"time_range": {"type": "absolute", "start": start, "end": end}}


def main() -> None:
    # --- Window clamp/validate layer ---
    honored = resolve_history_window(
        _absolute("2026-06-16T12:00:00+00:00", "2026-06-18T12:00:00+00:00"), now=NOW
    )
    assert_equal(honored["model_resolved"], True, "Valid absolute window must be honored.")
    assert_equal(honored["warnings"], [], "A clean window has no clamp warnings.")

    future = resolve_history_window(
        _absolute("2026-06-17T12:00:00+00:00", "2026-06-25T00:00:00+00:00"), now=NOW
    )
    assert_equal(future["end"], _iso(NOW), "Future end must be clamped to now.")

    oversized = resolve_history_window(
        _absolute("2020-01-01T00:00:00+00:00", "2026-06-18T12:00:00+00:00"), now=NOW
    )
    span = datetime.fromisoformat(oversized["end"]) - datetime.fromisoformat(oversized["start"])
    assert_equal(span, timedelta(days=366), "Oversized span must clamp to 366 days.")

    inverted = resolve_history_window(
        _absolute("2026-06-18T12:00:00+00:00", "2026-06-16T12:00:00+00:00"), now=NOW
    )
    assert_equal(inverted["model_resolved"], False, "Inverted window must fall back.")
    assert_equal(
        inverted["start"], _iso(NOW - timedelta(hours=24)), "Fallback is a 24h window."
    )

    relative = resolve_history_window({"time_range": {"type": "relative", "duration": "24h"}}, now=NOW)
    assert_equal(relative["model_resolved"], False, "A relative range must fall back.")

    print_case(
        "model_resolved_window_clamp",
        given={"now": _iso(NOW), "max_window_days": 366, "fallback_hours": 24},
        when={"operation": "resolve_history_window"},
        then={
            "honored": honored,
            "future_end_clamped": future["warnings"],
            "oversized_span_days": span.days,
            "inverted_fallback": inverted["model_resolved"],
            "relative_fallback": relative["model_resolved"],
        },
    )

    # --- Tier selection ---
    raw = _select_history_tier(NOW - timedelta(hours=12), NOW, now=NOW, keep_days=10)
    hourly = _select_history_tier(NOW - timedelta(days=5), NOW, now=NOW, keep_days=10)
    daily = _select_history_tier(NOW - timedelta(days=90), NOW, now=NOW, keep_days=10)
    old_short = _select_history_tier(
        NOW - timedelta(days=30), NOW - timedelta(days=29), now=NOW, keep_days=10
    )
    assert_equal(raw, ("recorder_states", "raw", None, False), "Recent short window is raw.")
    assert_equal(hourly[:3], ("long_term_statistics", "hourly", "hour"), "Multi-day is hourly stats.")
    assert_equal(daily[:3], ("long_term_statistics", "daily", "day"), "Long window is daily stats.")
    assert_equal(old_short[3], True, "Old short window is beyond retention.")

    print_case(
        "tiered_data_source_selection",
        given={"keep_days": 10, "raw_max_span_days": 2, "hourly_max_span_days": 60},
        when={"operation": "_select_history_tier"},
        then={"raw": raw, "hourly": hourly, "daily": daily, "old_short": old_short},
    )

    # --- Statistics normalization (mean + min/max band) ---
    start = NOW - timedelta(days=20)
    buckets = [
        {"start": _iso(start + timedelta(hours=i)), "mean": 60.0 + i, "min": 58.0 + i, "max": 63.0 + i}
        for i in range(4)
    ]
    catalog_item = {"friendly_name": "Attic Temperature", "unit_of_measurement": "degF"}
    series = _normalize_statistics_series(
        "sensor.attic_temperature",
        catalog_item,
        buckets,
        range_start=start - timedelta(hours=1),
        range_end=NOW,
        resolution="hourly",
    )["series"]
    assert_equal(series["source"], "long_term_statistics", "Series records its source.")
    assert_equal(series["resolution"], "hourly", "Series records its resolution.")
    assert_equal(series["points"][0]["value"], 60.0, "Mean is the point value.")
    assert_equal(series["points"][0]["value_min"], 58.0, "Bucket min is recorded.")
    assert_equal(series["points"][0]["value_max"], 63.0, "Bucket max is recorded.")

    print_case(
        "statistics_series_normalization",
        given={"buckets": len(buckets), "resolution": "hourly"},
        when={"operation": "_normalize_statistics_series"},
        then={
            "source": series["source"],
            "resolution": series["resolution"],
            "point_count": len(series["points"]),
            "first_point": series["points"][0],
        },
    )

    print("PASS model_resolved_window_data_source")


if __name__ == "__main__":
    main()
