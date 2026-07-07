"""History dispatch for job orchestration (ADR-0035 step 1).

The deterministic history seam: chart-window resolution (relative/absolute,
bounded), the tiered-retrieval wrapper over history_retrieval, and the D9
epoch-ms boundary transforms (`ts_epoch_ms` on every history point crossing
to codegen — invariant: the floor model never sees raw ISO timestamps).
Layer L1. See docs/specs/job-orchestration-split.md.
"""
from __future__ import annotations

from .const import DOMAIN
from copy import deepcopy
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from .orchestration_contracts import _chart_spec_entity_ids
from .orchestration_store import DATA_JOB_ORCHESTRATION_TIME_RANGE
from .history_retrieval import (
    DATA_HISTORY_RETRIEVAL,
    retrieve_approved_history,
)
from .in_process_renderer import (
    _parse_timestamp,
    first_real_vertical_slice_enabled,
)
from typing import Any

def _retrieve_history_for_plan(
    hass: Any,
    *,
    entry_id: str,
    chart_spec: Any,
) -> dict[str, Any] | None:
    """Fetch approved history for the model-resolved window (first real slice).

    Returns ``None`` for the legacy scaffold path (history is staged at start).
    For the real path, resolves the absolute window from the chart spec
    (ADR-0020), fetches tiered history (ADR-0021), and stores it for rendering.
    On failure returns a result flagged ``history_failure`` so the snapshot path
    can surface a card-facing failed snapshot.
    """
    if not first_real_vertical_slice_enabled(hass, entry_id):
        return None
    if not isinstance(chart_spec, dict):
        return None

    entry = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {}).get("entry")
    if entry is None:
        return {"accepted": False, "code": "unknown_config_entry", "history_failure": True}

    entity_ids = sorted(_chart_spec_entity_ids(chart_spec)["entity_ids"])
    if not entity_ids:
        return {
            "accepted": False,
            "code": "missing_approved_history",
            "history_failure": True,
            "history_result": {"missing_entity_ids": []},
        }

    now = _history_now(hass)
    window = resolve_history_window(chart_spec, now=now)
    result = dict(
        retrieve_approved_history(
            hass,
            entry,
            entity_ids=entity_ids,
            start=window["start"],
            end=window["end"],
            now=now,
            allow_statistics=True,
        )
    )
    result["window"] = window
    if not result["accepted"]:
        result["history_failure"] = True
    return result


def _history_window_end_dt(history_series: list[dict[str, Any]]) -> datetime:
    """Latest point timestamp across all series — the end of the last state segment."""
    latest: datetime | None = None
    for series in history_series:
        if not isinstance(series, dict):
            continue
        for point in series.get("points", []):
            if not isinstance(point, dict):
                continue
            try:
                ts = _parse_timestamp(point.get("ts"))
            except Exception:
                continue
            if ts is not None and (latest is None or ts > latest):
                latest = ts
    return latest or datetime.now(timezone.utc)


def _timestamp_to_epoch_ms(ts: Any) -> int | None:
    """Convert an ISO-8601 timestamp string to Unix epoch milliseconds (ADR-0031 D9).

    Robust to HA's mixed-precision recorder output — the initial state is written
    on-the-second, later states with microseconds — and to a trailing ``Z``. A
    naive datetime is treated as UTC. Already-integer input passes through so the
    conversion is idempotent. Returns ``None`` for unparseable input (the point
    then simply carries no epoch-ms field).
    """
    if isinstance(ts, bool):
        return None
    if isinstance(ts, int):
        return ts
    if isinstance(ts, float):
        return int(ts)
    if not isinstance(ts, str) or not ts.strip():
        return None
    text = ts.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


def _history_series_with_epoch_ms(history_series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a copy of the history with each point's ts precomputed as epoch ms.

    The codegen data boundary (ADR-0031 D9): the model is handed epoch integers
    so it never runs ``pandas.to_datetime`` on HA's mixed-precision ISO strings
    (the benchmark's dominant failure). The raw ``ts`` stays on the point for the
    render-request contract; the prompt projection strips it so the model only
    ever sees ``ts_epoch_ms``.
    """
    normalized = deepcopy(history_series)
    for series in normalized:
        if not isinstance(series, dict):
            continue
        for point in series.get("points", []):
            if not isinstance(point, dict):
                continue
            epoch_ms = _timestamp_to_epoch_ms(point.get("ts"))
            if epoch_ms is not None:
                point["ts_epoch_ms"] = epoch_ms
    return normalized


def _history_series_for_render_plan(
    hass: Any,
    *,
    entry_id: str,
    render_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    store = entry_data.get(DATA_HISTORY_RETRIEVAL, {}) if isinstance(entry_data, dict) else {}
    staged = store.get("series", []) if isinstance(store, dict) else []
    by_entity_id = {
        series.get("entity_id"): series
        for series in staged
        if isinstance(series, dict) and isinstance(series.get("entity_id"), str)
    }
    return [
        deepcopy(by_entity_id[entity_id])
        for entity_id in render_plan.get("history_entity_ids", [])
        if entity_id in by_entity_id
    ]


def _hass_time_zone(hass: Any) -> str:
    config = getattr(hass, "config", None)
    time_zone = getattr(config, "time_zone", None)
    if isinstance(time_zone, str) and time_zone.strip():
        return time_zone
    return "UTC"


# The time window is resolved by the model (ADR-0020): the planner emits an
# absolute chart_spec.time_range, the integration validates and clamps it, and
# any failure falls back to a fixed last-24h window. The 366-day ceiling is only
# useful because windows older than recorder retention are served from long-term
# statistics (ADR-0021).
_MIN_HISTORY_WINDOW = timedelta(seconds=60)


_MAX_HISTORY_WINDOW = timedelta(days=366)


_DEFAULT_HISTORY_WINDOW = timedelta(hours=24)


def _default_history_time_range(hass: Any) -> dict[str, str]:
    """Return the deterministic last-24h fallback window (or a test override)."""
    configured = getattr(hass, "data", {}).get(DOMAIN, {}).get(DATA_JOB_ORCHESTRATION_TIME_RANGE)
    if isinstance(configured, dict) and isinstance(configured.get("start"), str) and isinstance(configured.get("end"), str):
        return {
            "start": configured["start"],
            "end": configured["end"],
        }

    end = _history_now(hass)
    start = end - _DEFAULT_HISTORY_WINDOW
    return {
        "start": start.isoformat(timespec="seconds"),
        "end": end.isoformat(timespec="seconds"),
    }


def _history_now(hass: Any) -> datetime:
    """Return 'now' (UTC, second precision), honoring a test override."""
    configured = getattr(hass, "data", {}).get(DOMAIN, {}).get(DATA_JOB_ORCHESTRATION_TIME_RANGE)
    if isinstance(configured, dict) and isinstance(configured.get("now"), str):
        parsed = _parse_window_timestamp(configured["now"])
        if parsed is not None:
            return parsed.replace(microsecond=0)
    return datetime.now(timezone.utc).replace(microsecond=0)


def resolve_history_window(chart_spec: Any, *, now: datetime) -> dict[str, Any]:
    """Validate and clamp a model-supplied absolute window, else fall back to 24h.

    Returns a dict with ``start``/``end`` ISO strings, the resolved ``source``
    intent flag ``model_resolved`` (vs. the 24h fallback), and a list of
    ``warnings`` describing any clamping that was applied. The fallback is the
    only deterministic default; there is no keyword parsing (ADR-0020).
    """
    now = now.astimezone(timezone.utc).replace(microsecond=0)
    fallback_start = now - _DEFAULT_HISTORY_WINDOW

    def _fallback(reason: str) -> dict[str, Any]:
        return {
            "model_resolved": False,
            "start": fallback_start.isoformat(timespec="seconds"),
            "end": now.isoformat(timespec="seconds"),
            "warnings": [reason],
        }

    time_range = chart_spec.get("time_range") if isinstance(chart_spec, dict) else None
    if not isinstance(time_range, dict) or time_range.get("type") != "absolute":
        return _fallback("history_window_missing_absolute_range")

    start = _parse_window_timestamp(time_range.get("start"))
    end = _parse_window_timestamp(time_range.get("end"))
    if start is None or end is None:
        return _fallback("history_window_unparseable")

    start = start.astimezone(timezone.utc).replace(microsecond=0)
    end = end.astimezone(timezone.utc).replace(microsecond=0)

    warnings: list[str] = []
    if end > now:
        end = now
        warnings.append("history_window_end_clamped_to_now")
    if start >= end:
        return _fallback("history_window_not_increasing")
    if end - start > _MAX_HISTORY_WINDOW:
        start = end - _MAX_HISTORY_WINDOW
        warnings.append("history_window_span_clamped_to_max")
    if end - start < _MIN_HISTORY_WINDOW:
        start = end - _MIN_HISTORY_WINDOW
        warnings.append("history_window_span_expanded_to_min")

    return {
        "model_resolved": True,
        "start": start.isoformat(timespec="seconds"),
        "end": end.isoformat(timespec="seconds"),
        "warnings": warnings,
    }


def _parse_window_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        # The model often returns naive ISO 8601 (no offset). Treat these as
        # UTC rather than rejecting them, which previously forced the 24-hour
        # fallback window even when the model understood the requested range.
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
