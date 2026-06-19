"""Approved history retrieval scaffold for the Isolinear integration."""

from __future__ import annotations

import asyncio
import json
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from ._paths import load_schema_document, schema_path
from .config_schema import ENTITY_ID_PATTERN
from .const import DOMAIN
from .entity_catalog import DATA_ENTITY_CATALOG


# Upper bound on a single recorder read dispatched onto the recorder DB
# executor, so a wedged event loop cannot block the calling worker thread
# indefinitely.
_RECORDER_READ_TIMEOUT_SECONDS = 60

DATA_HISTORY_RETRIEVAL = "history_retrieval"
DATA_HISTORY_RETRIEVAL_SETUP = "history_retrieval_setup"
DATA_HISTORY_SOURCE = "history_data"
DATA_STATISTICS_SOURCE = "statistics_data"
DATA_RECORDER_KEEP_DAYS = "recorder_keep_days"

# Tiered data-source selection (ADR-0021). Recent/short windows use raw recorder
# states; longer or beyond-retention windows use long-term statistics, hourly up
# to 60 days and daily beyond that to keep point counts bounded.
DEFAULT_RECORDER_KEEP_DAYS = 10.0
RAW_TIER_MAX_SPAN = timedelta(days=2)
HOURLY_TIER_MAX_SPAN = timedelta(days=60)
HISTORY_SERIES_SCHEMA_PATH = (
    schema_path("history-series.schema.json")
)

MISSING_STATE_QUALITIES = {
    "unknown": "unknown",
    "unavailable": "unavailable",
    None: "missing",
}

NO_HISTORY_RETRIEVAL_ORCHESTRATION_CALLS = {
    "worker_called": False,
    "model_provider_called": False,
    "semantic_memory_called": False,
    "home_assistant_service_or_state_mutation_called": False,
    "token_generated": False,
    "chart_artifact_written": False,
    "chart_rendering_called": False,
    "job_orchestration_called": False,
    "websocket_command_registered": False,
    "dashboard_resource_metadata_written_or_reused": False,
}


class HistorySeriesValidationError(ValueError):
    """Raised when a HistorySeries does not satisfy its schema."""

    def __init__(self, result: dict[str, Any]) -> None:
        super().__init__(result.get("error", "HistorySeries validation failed."))
        self.result = result


def setup_history_retrieval(hass: Any, entry: Any) -> dict[str, Any]:
    """Initialize one config-entry-scoped approved history retrieval store."""
    entry_id = getattr(entry, "entry_id", "scaffold-entry")
    store = ensure_history_retrieval_store(hass, entry_id)
    catalog = _approved_catalog_items(hass, entry_id)
    result = {
        "accepted": True,
        "code": "history_retrieval_ready",
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "approved_entity_ids": [item["entity_id"] for item in catalog],
        "store": summarize_history_retrieval_store(store),
        "orchestration": history_retrieval_side_effects(
            approved_entity_catalog_read=bool(catalog),
        ),
    }
    hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})[DATA_HISTORY_RETRIEVAL_SETUP] = result
    return result


def ensure_history_retrieval_store(hass: Any, entry_id: str) -> dict[str, Any]:
    """Return the in-memory approved history store for one config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    entry_data = domain_data.setdefault(entry_id, {})
    store = entry_data.get(DATA_HISTORY_RETRIEVAL)
    if isinstance(store, dict):
        return store

    store = {
        "entry_id": entry_id,
        "series": [],
        "entity_ids": [],
        "request_count": 0,
        "last_time_range": None,
    }
    entry_data[DATA_HISTORY_RETRIEVAL] = store
    return store


def retrieve_approved_history(
    hass: Any,
    entry: Any,
    *,
    entity_ids: Any,
    start: Any,
    end: Any,
    now: Any = None,
    allow_statistics: bool = False,
    history_by_entity: dict[str, Any] | None = None,
    store: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Read and normalize history only for approved catalog entities."""
    entry_id = getattr(entry, "entry_id", "scaffold-entry")
    history_store = store or ensure_history_retrieval_store(hass, entry_id)

    request_result = _normalize_history_request(entity_ids, start=start, end=end)
    if not request_result["accepted"]:
        return _history_rejection(
            request_result["code"],
            entry_id=entry_id,
            store=history_store,
            errors=request_result.get("errors"),
        )

    requested_entity_ids = request_result["entity_ids"]
    time_range = request_result["time_range"]
    catalog_items = _approved_catalog_items(hass, entry_id)
    catalog_by_entity = {
        item["entity_id"]: item
        for item in catalog_items
        if item.get("visible_to_agent") is True
    }
    rejected_entity_ids = [
        entity_id
        for entity_id in requested_entity_ids
        if entity_id not in catalog_by_entity
    ]
    if rejected_entity_ids:
        return _history_rejection(
            "entity_not_in_approved_catalog",
            entry_id=entry_id,
            store=history_store,
            rejected_entity_ids=rejected_entity_ids,
            approved_entity_catalog_read=True,
        )

    resolved_now = now if isinstance(now, datetime) else datetime.now(timezone.utc)
    if resolved_now.tzinfo is None:
        resolved_now = resolved_now.replace(tzinfo=timezone.utc)
    resolved_now = resolved_now.astimezone(timezone.utc)
    if allow_statistics:
        keep_days = _recorder_keep_days(hass)
        tier = _select_history_tier(
            time_range["start_dt"],
            time_range["end_dt"],
            now=resolved_now,
            keep_days=keep_days,
        )
    else:
        # Legacy scaffold path: raw recorder states only. Long-term statistics
        # tiering is opt-in for the model-driven first-real-slice window
        # (ADR-0020/ADR-0021).
        tier = ("recorder_states", "raw", None, False)

    series_build = _build_tiered_series(
        hass,
        requested_entity_ids=requested_entity_ids,
        catalog_by_entity=catalog_by_entity,
        time_range=time_range,
        tier=tier,
        history_by_entity=history_by_entity,
    )
    if not series_build["accepted"]:
        return _history_rejection(
            series_build["code"],
            entry_id=entry_id,
            store=history_store,
            errors=series_build.get("errors"),
            missing_entity_ids=series_build.get("missing_entity_ids"),
            statistics_unavailable_entity_ids=series_build.get("statistics_unavailable_entity_ids"),
            approved_entity_catalog_read=True,
            home_assistant_history_read=True,
        )
    series_results = series_build["series"]

    storage_result = store_validated_history_series(
        history_store,
        series_results,
        time_range={
            "start": time_range["start"],
            "end": time_range["end"],
        },
    )
    if not storage_result["accepted"]:
        return _history_rejection(
            storage_result["code"],
            entry_id=entry_id,
            store=history_store,
            validation=storage_result,
            approved_entity_catalog_read=True,
            home_assistant_history_read=True,
        )

    return {
        "accepted": True,
        "code": "approved_history_retrieved",
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "requested_entity_ids": list(requested_entity_ids),
        "approved_entity_ids": [item["entity_id"] for item in catalog_items],
        "time_range": {
            "start": time_range["start"],
            "end": time_range["end"],
        },
        "history_series": storage_result["series"],
        "validation": storage_result["validation"],
        "data_source": {"source": tier[0], "resolution": tier[1]},
        "store": summarize_history_retrieval_store(history_store),
        "orchestration": history_retrieval_side_effects(
            approved_entity_catalog_read=True,
            home_assistant_history_read=True,
            history_retrieval_written=True,
        ),
    }


def store_validated_history_series(
    store: dict[str, Any],
    series: Any,
    *,
    time_range: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Validate all HistorySeries records before mutating the store."""
    validation = validate_history_series_collection_contract(series)
    if not validation["accepted"]:
        return validation

    stored_series = deepcopy(series)
    store["series"] = stored_series
    store["entity_ids"] = [item.get("entity_id") for item in stored_series]
    store["request_count"] = int(store.get("request_count", 0)) + 1
    store["last_time_range"] = deepcopy(time_range)
    return {
        "accepted": True,
        "code": "accepted",
        "series": deepcopy(stored_series),
        "validation": validation,
    }


def validate_history_series_collection_contract(series: Any) -> dict[str, Any]:
    """Validate a list of HistorySeries records against JSON Schema."""
    if not isinstance(series, list):
        return {
            "accepted": False,
            "code": "invalid_history_series",
            "error": "$ must be a list of HistorySeries records.",
        }

    item_results = []
    for index, item in enumerate(series):
        result = validate_history_series_contract(item)
        item_results.append(result)
        if not result["accepted"]:
            return {
                **result,
                "item_index": index,
            }

    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(HISTORY_SERIES_SCHEMA_PATH),
        "series_count": len(series),
        "series": item_results,
    }


def validate_history_series_contract(series: Any) -> dict[str, Any]:
    """Validate one HistorySeries against the repo JSON Schema."""
    try:
        schema = load_schema_document(HISTORY_SERIES_SCHEMA_PATH)
        _validate_json_schema(series, schema, root_schema=schema, path="$")
    except (OSError, json.JSONDecodeError, HistorySeriesValidationError, KeyError) as exc:
        return {
            "accepted": False,
            "code": "invalid_history_series",
            "error": str(exc),
        }
    return {
        "accepted": True,
        "code": "accepted",
        "schema": str(HISTORY_SERIES_SCHEMA_PATH),
        "series_id": series["series_id"],
        "entity_id": series.get("entity_id"),
    }


def summarize_history_retrieval_store(store: dict[str, Any]) -> dict[str, Any]:
    """Return an evidence-friendly summary of a history retrieval store."""
    series = list(store.get("series", []))
    return {
        "entry_id": store.get("entry_id"),
        "series_count": len(series),
        "entity_ids": [item.get("entity_id") for item in series],
        "series_ids": [item.get("series_id") for item in series],
        "kinds": [item.get("kind") for item in series],
        "point_counts": [len(item.get("points", [])) for item in series],
        "request_count": store.get("request_count", 0),
        "last_time_range": deepcopy(store.get("last_time_range")),
    }


def history_retrieval_side_effects(
    *,
    approved_entity_catalog_read: bool = False,
    home_assistant_history_read: bool = False,
    history_retrieval_written: bool = False,
) -> dict[str, bool]:
    """Return side-effect accounting for the approved history retrieval packet."""
    return {
        **NO_HISTORY_RETRIEVAL_ORCHESTRATION_CALLS,
        "approved_entity_catalog_read": approved_entity_catalog_read,
        "home_assistant_history_read": home_assistant_history_read,
        "history_retrieval_scaffold_written": history_retrieval_written,
    }


def _normalize_history_request(entity_ids: Any, *, start: Any, end: Any) -> dict[str, Any]:
    errors = []
    if isinstance(entity_ids, tuple):
        entity_ids = list(entity_ids)
    if not isinstance(entity_ids, list) or not entity_ids:
        errors.append({"path": "$.entity_ids", "reason": "must_be_non_empty_list"})
    else:
        seen_entity_ids: set[str] = set()
        for index, entity_id in enumerate(entity_ids):
            if not isinstance(entity_id, str) or ENTITY_ID_PATTERN.search(entity_id) is None:
                errors.append({"path": f"$.entity_ids[{index}]", "reason": "invalid_entity_id"})
                continue
            if entity_id in seen_entity_ids:
                errors.append({"path": f"$.entity_ids[{index}]", "reason": "duplicate_entity_id"})
                continue
            seen_entity_ids.add(entity_id)

    start_result = _coerce_datetime(start, "$.start")
    end_result = _coerce_datetime(end, "$.end")
    if not start_result["accepted"]:
        errors.extend(start_result["errors"])
    if not end_result["accepted"]:
        errors.extend(end_result["errors"])
    if start_result["accepted"] and end_result["accepted"] and start_result["dt"] >= end_result["dt"]:
        errors.append({"path": "$.end", "reason": "must_be_after_start"})

    if errors:
        return {
            "accepted": False,
            "code": "invalid_history_request",
            "errors": errors,
        }
    return {
        "accepted": True,
        "code": "accepted",
        "entity_ids": list(entity_ids),
        "time_range": {
            "start": _isoformat(start_result["dt"]),
            "end": _isoformat(end_result["dt"]),
            "start_dt": start_result["dt"],
            "end_dt": end_result["dt"],
        },
    }


def _approved_catalog_items(hass: Any, entry_id: str) -> list[dict[str, Any]]:
    entry_data = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id, {})
    store = entry_data.get(DATA_ENTITY_CATALOG, {})
    items = store.get("items", []) if isinstance(store, dict) else []
    if not isinstance(items, list):
        return []
    return [
        item
        for item in items
        if isinstance(item, dict) and item.get("visible_to_agent") is True
    ]


def _recorder_keep_days(hass: Any) -> float:
    """Return the recorder retention horizon in days (best-effort)."""
    domain_data = getattr(hass, "data", {}).get(DOMAIN, {})
    override = domain_data.get(DATA_RECORDER_KEEP_DAYS)
    if isinstance(override, (int, float)) and not isinstance(override, bool) and override > 0:
        return float(override)
    try:  # pragma: no cover - exercised only in Home Assistant.
        from homeassistant.components.recorder import get_instance

        keep_days = getattr(get_instance(hass), "keep_days", None)
        if isinstance(keep_days, (int, float)) and not isinstance(keep_days, bool) and keep_days > 0:
            return float(keep_days)
    except Exception:  # pragma: no cover - defensive boundary.
        pass
    return DEFAULT_RECORDER_KEEP_DAYS


def _select_history_tier(
    range_start: datetime,
    range_end: datetime,
    *,
    now: datetime,
    keep_days: float,
) -> tuple[str, str, str | None, bool]:
    """Pick a single data source for the whole window (ADR-0021).

    Returns ``(source, resolution, statistics_period, beyond_retention)``.
    """
    span = range_end - range_start
    retention_start = now - timedelta(days=keep_days)
    beyond_retention = range_start < retention_start
    if not beyond_retention and span <= RAW_TIER_MAX_SPAN:
        return ("recorder_states", "raw", None, beyond_retention)
    if span <= HOURLY_TIER_MAX_SPAN:
        return ("long_term_statistics", "hourly", "hour", beyond_retention)
    return ("long_term_statistics", "daily", "day", beyond_retention)


def _build_tiered_series(
    hass: Any,
    *,
    requested_entity_ids: list[str],
    catalog_by_entity: dict[str, Any],
    time_range: dict[str, Any],
    tier: tuple[str, str, str | None, bool],
    history_by_entity: dict[str, Any] | None,
) -> dict[str, Any]:
    source_kind, resolution, period, beyond_retention = tier
    range_start = time_range["start_dt"]
    range_end = time_range["end_dt"]

    if source_kind == "recorder_states":
        return _build_raw_series(
            hass,
            requested_entity_ids=requested_entity_ids,
            catalog_by_entity=catalog_by_entity,
            range_start=range_start,
            range_end=range_end,
            history_by_entity=history_by_entity,
        )

    statistics_source = _statistics_source_from_hass(
        hass,
        entity_ids=requested_entity_ids,
        range_start=range_start,
        range_end=range_end,
        period=period,
    )
    if not isinstance(statistics_source, dict):
        unavailable = list(requested_entity_ids)
    else:
        unavailable = [
            entity_id
            for entity_id in requested_entity_ids
            if statistics_source.get(entity_id) is None
        ]
    if unavailable:
        if beyond_retention:
            return {
                "accepted": False,
                "code": "no_long_term_statistics",
                "missing_entity_ids": unavailable,
                "statistics_unavailable_entity_ids": unavailable,
            }
        # Data is still inside recorder retention; serve the whole window from
        # raw recorder states rather than mixing sources.
        return _build_raw_series(
            hass,
            requested_entity_ids=requested_entity_ids,
            catalog_by_entity=catalog_by_entity,
            range_start=range_start,
            range_end=range_end,
            history_by_entity=history_by_entity,
        )

    series_results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for entity_id in requested_entity_ids:
        series_result = _normalize_statistics_series(
            entity_id,
            catalog_by_entity[entity_id],
            statistics_source[entity_id],
            range_start=range_start,
            range_end=range_end,
            resolution=resolution,
        )
        if not series_result["accepted"]:
            errors.extend(series_result.get("errors", []))
            continue
        series_results.append(series_result["series"])
    if errors:
        return {"accepted": False, "code": "invalid_history_records", "errors": errors}
    return {"accepted": True, "series": series_results}


def _build_raw_series(
    hass: Any,
    *,
    requested_entity_ids: list[str],
    catalog_by_entity: dict[str, Any],
    range_start: datetime,
    range_end: datetime,
    history_by_entity: dict[str, Any] | None,
) -> dict[str, Any]:
    source = (
        _history_source_from_hass(
            hass,
            entity_ids=requested_entity_ids,
            range_start=range_start,
            range_end=range_end,
        )
        if history_by_entity is None
        else history_by_entity
    )
    if not isinstance(source, dict):
        return {
            "accepted": False,
            "code": "invalid_history_source",
            "errors": [{"path": "$.history_by_entity", "reason": "must_be_object"}],
        }

    series_results: list[dict[str, Any]] = []
    missing_entity_ids: list[str] = []
    errors: list[dict[str, str]] = []
    for entity_id in requested_entity_ids:
        raw_records = source.get(entity_id)
        if raw_records is None:
            missing_entity_ids.append(entity_id)
            continue
        series_result = _normalize_history_series(
            entity_id,
            catalog_by_entity[entity_id],
            raw_records,
            range_start=range_start,
            range_end=range_end,
        )
        if not series_result["accepted"]:
            errors.extend(series_result.get("errors", []))
            continue
        series_results.append(series_result["series"])

    if missing_entity_ids:
        return {
            "accepted": False,
            "code": "missing_approved_history",
            "missing_entity_ids": missing_entity_ids,
        }
    if errors:
        return {"accepted": False, "code": "invalid_history_records", "errors": errors}
    return {"accepted": True, "series": series_results}


def _statistics_source_from_hass(
    hass: Any,
    *,
    entity_ids: list[str],
    range_start: datetime,
    range_end: datetime,
    period: str | None,
) -> dict[str, Any] | None:
    domain_data = getattr(hass, "data", {}).get(DOMAIN, {})
    injected = domain_data.get(DATA_STATISTICS_SOURCE)
    if isinstance(injected, dict):
        return {entity_id: injected.get(entity_id) for entity_id in entity_ids}
    return _recorder_statistics_source_from_hass(
        hass,
        entity_ids=entity_ids,
        range_start=range_start,
        range_end=range_end,
        period=period,
    )


def _recorder_db_instance(hass: Any) -> Any | None:
    """Return the Home Assistant recorder instance, or None when unavailable."""
    try:  # pragma: no cover - exercised only in Home Assistant.
        from homeassistant.components import recorder

        return recorder.get_instance(hass)
    except (ImportError, KeyError, RuntimeError, AttributeError):  # pragma: no cover
        return None


def _read_via_recorder_executor(hass: Any, read: Callable[[], Any]) -> Any:
    """Run a recorder read on the recorder's dedicated database executor.

    Job orchestration runs synchronously on Home Assistant's general executor
    (see ``async_handle_registered_ws_command``), so a direct recorder call
    runs on the wrong thread and Home Assistant logs "accesses the database
    without the database executor". This bounces the read through the loop onto
    the recorder's DB executor. When no recorder instance or loop is available
    (repo tests, non-recorder installs) the read runs inline.
    """
    instance = _recorder_db_instance(hass)
    loop = getattr(hass, "loop", None)
    if instance is None or loop is None:
        return read()

    async def _job() -> Any:  # pragma: no cover - exercised only in Home Assistant.
        return await instance.async_add_executor_job(read)

    # Bounded so a stalled event loop cannot hang this worker thread forever;
    # on timeout the callers' best-effort recorder boundary returns no data.
    return asyncio.run_coroutine_threadsafe(_job(), loop).result(
        timeout=_RECORDER_READ_TIMEOUT_SECONDS
    )


def _recorder_statistics_source_from_hass(
    hass: Any,
    *,
    entity_ids: list[str],
    range_start: datetime,
    range_end: datetime,
    period: str | None,
) -> dict[str, Any] | None:
    """Return best-effort Home Assistant long-term statistics buckets."""
    try:  # pragma: no cover - exercised only in Home Assistant.
        from homeassistant.components.recorder.statistics import statistics_during_period
    except ImportError:  # pragma: no cover - repo tests run without Home Assistant.
        return None

    try:
        raw = _read_via_recorder_executor(
            hass,
            lambda: statistics_during_period(
                hass,
                range_start,
                range_end,
                set(entity_ids),
                period or "hour",
                None,
                {"mean", "min", "max"},
            ),
        )
    except Exception:  # pragma: no cover - defensive recorder boundary.
        return None

    if not isinstance(raw, dict):
        return None
    result: dict[str, Any] = {}
    for entity_id in entity_ids:
        rows = raw.get(entity_id)
        if rows is None:
            result[entity_id] = None
            continue
        result[entity_id] = [
            {
                "start": row.get("start") if isinstance(row, dict) else None,
                "mean": row.get("mean") if isinstance(row, dict) else None,
                "min": row.get("min") if isinstance(row, dict) else None,
                "max": row.get("max") if isinstance(row, dict) else None,
            }
            for row in rows
        ]
    return result


def _normalize_statistics_series(
    entity_id: str,
    catalog_item: dict[str, Any],
    buckets: Any,
    *,
    range_start: datetime,
    range_end: datetime,
    resolution: str,
) -> dict[str, Any]:
    if not isinstance(buckets, list):
        return _history_record_rejection(entity_id, "$.statistics", "must_be_list")

    label = catalog_item.get("friendly_name") or entity_id
    unit = catalog_item.get("unit_of_measurement")
    points = []
    warnings = []
    for index, bucket in enumerate(buckets):
        if not isinstance(bucket, dict):
            return {
                "accepted": False,
                "code": "invalid_history_records",
                "errors": [{"path": f"$.statistics.{entity_id}[{index}]", "reason": "must_be_object"}],
            }
        timestamp = _coerce_statistics_timestamp(bucket.get("start"))
        if timestamp is None:
            continue
        if timestamp < range_start or timestamp > range_end:
            continue
        mean = bucket.get("mean")
        if not isinstance(mean, (int, float)) or isinstance(mean, bool):
            continue
        points.append(
            {
                "ts": _isoformat(timestamp),
                "value": float(mean),
                "value_min": _optional_float(bucket.get("min")),
                "value_max": _optional_float(bucket.get("max")),
                "raw_state": None,
                "quality": "ok",
            }
        )

    points.sort(key=lambda point: point["ts"])
    if not points:
        warnings.append(f"No statistics for {entity_id} were found in the requested time range.")

    return {
        "accepted": True,
        "code": "accepted",
        "series": {
            "series_id": _series_id_for_entity(entity_id),
            "entity_id": entity_id,
            "label": label,
            "kind": "numeric",
            "unit": unit,
            "points": points,
            "source": "long_term_statistics",
            "resolution": resolution,
            "source_entity_ids": [entity_id],
            "warnings": warnings,
        },
    }


def _coerce_statistics_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _optional_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _history_source_from_hass(
    hass: Any,
    *,
    entity_ids: list[str],
    range_start: datetime,
    range_end: datetime,
) -> dict[str, Any]:
    domain_data = getattr(hass, "data", {}).get(DOMAIN, {})
    source = domain_data.get(DATA_HISTORY_SOURCE, {})
    if isinstance(source, dict) and source:
        return source
    recorder_source = _recorder_history_source_from_hass(
        hass,
        entity_ids=entity_ids,
        range_start=range_start,
        range_end=range_end,
    )
    if recorder_source is not None:
        return recorder_source
    if source is None:
        return {}
    return source


def _recorder_history_source_from_hass(
    hass: Any,
    *,
    entity_ids: list[str],
    range_start: datetime,
    range_end: datetime,
) -> dict[str, Any] | None:
    """Return best-effort real Home Assistant recorder history records."""
    try:  # pragma: no cover - exercised only in Home Assistant.
        from homeassistant.components.recorder import history as recorder_history
    except ImportError:  # pragma: no cover - repo tests run without Home Assistant.
        return None

    try:
        raw = _read_via_recorder_executor(
            hass,
            lambda: recorder_history.get_significant_states(
                hass,
                range_start,
                range_end,
                entity_ids,
                include_start_time_state=True,
                significant_changes_only=False,
                minimal_response=False,
                no_attributes=False,
            ),
        )
    except TypeError:  # pragma: no cover - compatibility with older HA signatures.
        try:
            raw = _read_via_recorder_executor(
                hass,
                lambda: recorder_history.get_significant_states(
                    hass,
                    range_start,
                    range_end,
                    entity_ids,
                    include_start_time_state=True,
                    significant_changes_only=False,
                ),
            )
        except Exception:
            return None
    except Exception:
        return None

    if not isinstance(raw, dict):
        return None
    return {
        entity_id: [_history_record_from_state(entity_id, state) for state in raw.get(entity_id, [])]
        for entity_id in entity_ids
    }


def _history_record_from_state(entity_id: str, state: Any) -> dict[str, Any]:
    if isinstance(state, dict):
        return {
            "entity_id": state.get("entity_id", entity_id),
            "state": state.get("state"),
            "last_changed": state.get("last_changed"),
            "attributes": state.get("attributes", {}),
        }
    return {
        "entity_id": getattr(state, "entity_id", entity_id),
        "state": getattr(state, "state", None),
        "last_changed": getattr(state, "last_changed", None),
        "attributes": getattr(state, "attributes", {}) or {},
    }


def _normalize_history_series(
    entity_id: str,
    catalog_item: dict[str, Any],
    raw_records: Any,
    *,
    range_start: datetime,
    range_end: datetime,
) -> dict[str, Any]:
    if not isinstance(raw_records, list):
        return _history_record_rejection(entity_id, "$.history_by_entity", "must_be_list")

    kind = _series_kind(catalog_item)
    unit = catalog_item.get("unit_of_measurement") if kind == "numeric" else None
    label = catalog_item.get("friendly_name") or entity_id
    points = []
    warnings = []
    errors = []

    for index, record in enumerate(raw_records):
        record_result = _normalize_history_record(
            entity_id,
            record,
            path=f"$.history_by_entity.{entity_id}[{index}]",
        )
        if not record_result["accepted"]:
            errors.extend(record_result["errors"])
            continue
        timestamp = record_result["timestamp"]
        if timestamp < range_start or timestamp > range_end:
            continue
        point_result = _history_point_for_state(
            entity_id,
            record_result["state"],
            timestamp=timestamp,
            kind=kind,
        )
        warnings.extend(point_result["warnings"])
        points.append(point_result["point"])

    if errors:
        return {
            "accepted": False,
            "code": "invalid_history_records",
            "errors": errors,
        }
    points.sort(key=lambda point: point["ts"])
    if not points:
        warnings.append(f"No history records for {entity_id} were found in the requested time range.")

    return {
        "accepted": True,
        "code": "accepted",
        "series": {
            "series_id": _series_id_for_entity(entity_id),
            "entity_id": entity_id,
            "label": label,
            "kind": kind,
            "unit": unit,
            "points": points,
            "source": "recorder_states",
            "resolution": "raw",
            "source_entity_ids": [entity_id],
            "warnings": warnings,
        },
    }


def _normalize_history_record(entity_id: str, record: Any, *, path: str) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {
            "accepted": False,
            "code": "invalid_history_records",
            "errors": [{"path": path, "reason": "must_be_object"}],
        }
    errors = []
    if "last_changed" not in record:
        errors.append({"path": f"{path}.last_changed", "reason": "required"})
    if "state" not in record:
        errors.append({"path": f"{path}.state", "reason": "required"})

    record_entity_id = record.get("entity_id", entity_id)
    if record_entity_id != entity_id:
        errors.append({"path": f"{path}.entity_id", "reason": "must_match_requested_entity"})

    state = record.get("state")
    if not _is_json_primitive(state):
        errors.append({"path": f"{path}.state", "reason": "must_be_scalar_or_null"})

    timestamp_result = _coerce_datetime(record.get("last_changed"), f"{path}.last_changed")
    if not timestamp_result["accepted"]:
        errors.extend(timestamp_result["errors"])

    attributes = record.get("attributes", {})
    if attributes is not None and not isinstance(attributes, dict):
        errors.append({"path": f"{path}.attributes", "reason": "must_be_object"})

    if errors:
        return {
            "accepted": False,
            "code": "invalid_history_records",
            "errors": errors,
        }
    return {
        "accepted": True,
        "code": "accepted",
        "state": state,
        "timestamp": timestamp_result["dt"],
    }


def _history_point_for_state(
    entity_id: str,
    state: Any,
    *,
    timestamp: datetime,
    kind: str,
) -> dict[str, Any]:
    if state in MISSING_STATE_QUALITIES:
        return {
            "point": {
                "ts": _isoformat(timestamp),
                "value": None,
                "raw_state": state,
                "quality": MISSING_STATE_QUALITIES[state],
            },
            "warnings": [f"State {state!r} for {entity_id} normalized to missing value."],
        }

    if kind == "numeric":
        try:
            value = float(state)
        except (TypeError, ValueError):
            return {
                "point": {
                    "ts": _isoformat(timestamp),
                    "value": None,
                    "raw_state": state,
                    "quality": "invalid",
                },
                "warnings": [f"State {state!r} for {entity_id} is not a valid numeric value."],
            }
        return {
            "point": {
                "ts": _isoformat(timestamp),
                "value": value,
                "raw_state": state,
                "quality": "ok",
            },
            "warnings": [],
        }

    return {
        "point": {
            "ts": _isoformat(timestamp),
            "value": state,
            "raw_state": state,
            "quality": "ok",
        },
        "warnings": [],
    }


def classify_series_kind(catalog_item: dict[str, Any]) -> str:
    """Public deterministic series-kind classifier used for render-family routing.

    Returns ``numeric`` | ``binary_state`` | ``categorical_state`` (ADR-0022).
    """
    return _series_kind(catalog_item)


def _series_kind(catalog_item: dict[str, Any]) -> str:
    if catalog_item.get("domain") == "binary_sensor":
        return "binary_state"
    if catalog_item.get("unit_of_measurement") is not None:
        return "numeric"
    if catalog_item.get("state_class") == "measurement":
        return "numeric"
    if catalog_item.get("domain") == "sensor" and catalog_item.get("device_class") in {
        "energy",
        "humidity",
        "illuminance",
        "power",
        "temperature",
        "voltage",
    }:
        return "numeric"
    return "categorical_state"


def _history_record_rejection(entity_id: str, path: str, reason: str) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": "invalid_history_records",
        "errors": [{"path": f"{path}.{entity_id}", "reason": reason}],
    }


def _history_rejection(
    code: str,
    *,
    entry_id: str,
    store: dict[str, Any],
    errors: list[dict[str, str]] | None = None,
    rejected_entity_ids: list[str] | None = None,
    missing_entity_ids: list[str] | None = None,
    statistics_unavailable_entity_ids: list[str] | None = None,
    validation: dict[str, Any] | None = None,
    approved_entity_catalog_read: bool = False,
    home_assistant_history_read: bool = False,
) -> dict[str, Any]:
    _clear_history_retrieval_store(store)
    result = {
        "accepted": False,
        "code": code,
        "entry_id": entry_id,
        "config_entry_scoped": True,
        "history_series": [],
        "store": summarize_history_retrieval_store(store),
        "orchestration": history_retrieval_side_effects(
            approved_entity_catalog_read=approved_entity_catalog_read,
            home_assistant_history_read=home_assistant_history_read,
        ),
    }
    if errors is not None:
        result["errors"] = errors
    if rejected_entity_ids is not None:
        result["rejected_entity_ids"] = rejected_entity_ids
    if missing_entity_ids is not None:
        result["missing_entity_ids"] = missing_entity_ids
    if statistics_unavailable_entity_ids is not None:
        result["statistics_unavailable_entity_ids"] = statistics_unavailable_entity_ids
    if validation is not None:
        result["validation"] = validation
    return result


def _clear_history_retrieval_store(store: dict[str, Any]) -> None:
    store["series"] = []
    store["entity_ids"] = []
    store["last_time_range"] = None


def _coerce_datetime(value: Any, path: str) -> dict[str, Any]:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return {
                "accepted": False,
                "errors": [{"path": path, "reason": "must_be_timezone_aware"}],
            }
        return {
            "accepted": True,
            "dt": value,
        }
    if not isinstance(value, str) or not value.strip():
        return {
            "accepted": False,
            "errors": [{"path": path, "reason": "must_be_datetime"}],
        }
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return {
            "accepted": False,
            "errors": [{"path": path, "reason": "must_be_datetime"}],
        }
    if parsed.tzinfo is None:
        return {
            "accepted": False,
            "errors": [{"path": path, "reason": "must_be_timezone_aware"}],
        }
    return {
        "accepted": True,
        "dt": parsed,
    }


def _isoformat(timestamp: datetime) -> str:
    return timestamp.isoformat(timespec="seconds")


def _series_id_for_entity(entity_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", entity_id).strip("_")


def _is_json_primitive(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _validate_json_schema(
    payload: Any,
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any],
    path: str,
) -> None:
    if "$ref" in schema:
        schema = _resolve_ref(schema["$ref"], root_schema)

    if "const" in schema and payload != schema["const"]:
        raise HistorySeriesValidationError(_schema_error(f"{path} must equal {schema['const']!r}."))

    if "enum" in schema and payload not in schema["enum"]:
        raise HistorySeriesValidationError(_schema_error(f"{path} must be one of {schema['enum']!r}."))

    if "type" in schema:
        _validate_type(payload, schema["type"], path)

    if isinstance(payload, dict):
        _validate_object(payload, schema, root_schema=root_schema, path=path)
    elif isinstance(payload, list):
        _validate_array(payload, schema, root_schema=root_schema, path=path)
    elif isinstance(payload, str):
        _validate_string(payload, schema, path)


def _validate_object(
    payload: dict[str, Any],
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any],
    path: str,
) -> None:
    for property_name in schema.get("required", []):
        if property_name not in payload:
            raise HistorySeriesValidationError(_schema_error(f"{path}.{property_name} is required."))

    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        extra_properties = sorted(set(payload) - set(properties))
        if extra_properties:
            raise HistorySeriesValidationError(
                _schema_error(f"{path} has unexpected properties: {extra_properties!r}.")
            )

    for property_name, property_schema in properties.items():
        if property_name in payload:
            _validate_json_schema(
                payload[property_name],
                property_schema,
                root_schema=root_schema,
                path=f"{path}.{property_name}",
            )


def _validate_array(
    payload: list[Any],
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any],
    path: str,
) -> None:
    item_schema = schema.get("items")
    if item_schema is None:
        return

    for index, item in enumerate(payload):
        _validate_json_schema(item, item_schema, root_schema=root_schema, path=f"{path}[{index}]")


def _validate_string(payload: str, schema: dict[str, Any], path: str) -> None:
    pattern = schema.get("pattern")
    if pattern is not None and re.search(pattern, payload) is None:
        raise HistorySeriesValidationError(_schema_error(f"{path} must match pattern {pattern!r}."))

    if schema.get("format") == "date-time":
        try:
            datetime.fromisoformat(payload.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HistorySeriesValidationError(_schema_error(f"{path} must be a date-time string.")) from exc


def _validate_type(payload: Any, schema_type: str | list[str], path: str) -> None:
    expected_types = [schema_type] if isinstance(schema_type, str) else schema_type
    if any(_matches_type(payload, expected_type) for expected_type in expected_types):
        return
    raise HistorySeriesValidationError(_schema_error(f"{path} must be of type {expected_types!r}."))


def _matches_type(payload: Any, schema_type: str) -> bool:
    if schema_type == "object":
        return isinstance(payload, dict)
    if schema_type == "array":
        return isinstance(payload, list)
    if schema_type == "string":
        return isinstance(payload, str)
    if schema_type == "number":
        return isinstance(payload, (int, float)) and not isinstance(payload, bool)
    if schema_type == "integer":
        return isinstance(payload, int) and not isinstance(payload, bool)
    if schema_type == "boolean":
        return isinstance(payload, bool)
    if schema_type == "null":
        return payload is None
    return False


def _resolve_ref(ref: str, root_schema: dict[str, Any]) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise HistorySeriesValidationError(_schema_error(f"Unsupported schema ref '{ref}'."))

    current: Any = root_schema
    for part in ref[2:].split("/"):
        current = current[part]
    return current


def _schema_error(error: str) -> dict[str, Any]:
    return {
        "accepted": False,
        "code": "invalid_history_series",
        "error": error,
    }
