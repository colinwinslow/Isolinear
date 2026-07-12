"""isolinear_analysis — curated in-sandbox analysis helpers (ADR-0036).

Trusted, integration-authored helpers importable by GENERATED chart code inside
the `-I` sandbox. This module exists to remove the one plumbing step every live
cross-series failure died in (the align/combine idiom: 0.2.31 entity-id
KeyError, the 0.2.32 "nan °F" empty frame, the e2e-18 repair exhaustion) from
the floor model's transcription burden. The model keeps composition — what to
compute, what to plot, the answer sentence; this module only aligns.

Compatibility surface (ADR-0036): generated and, later, saved analysis code
(ADR-0035) call this API. Changes must be additive; breaking an existing
signature requires a new ADR.

No I/O, no env access, no network — pure computation over the in-sandbox
``data`` payload.
"""
from __future__ import annotations

from typing import Any

import pandas

__version__ = "1.0.0"

__all__ = ["align", "__version__"]


def align(
    history_series: list[dict[str, Any]],
    freq: str = "5min",
) -> "pandas.DataFrame":
    """Align numeric history series onto one shared time grid, keyed by entity_id.

    Args:
        history_series: the runtime ``data['history_series']`` list. Only
            series whose ``kind`` is ``"numeric"`` participate; state series
            (binary/categorical) are ignored.
        freq: pandas resample frequency for the shared grid (default ``"5min"``).

    Returns:
        A ``pandas.DataFrame`` whose columns ARE the entity_id strings and whose
        index is a shared ``DatetimeIndex``: each series is independently
        ``resample(freq).mean().interpolate()``-ed (the proven per-entity
        idiom), then the aligned results are joined and rows with any missing
        value dropped. Column order follows ``history_series`` order.

        Typical one-liners against the result::

            frame.mean(axis=1)                        # cross-sensor average series
            frame[a] - frame[b]                       # difference series
            frame.corr().iloc[0, 1]                   # correlation coefficient
            frame.sub(frame.mean(axis=1), axis=0)     # per-sensor deviation from mean

    Raises:
        ValueError: with a specific, repair-actionable message when no numeric
            series is present, a numeric series has no finite points, or the
            aligned join is empty (no overlapping time coverage). Never returns
            an empty or all-NaN frame — a degenerate result is an explicit
            error instead of NaN propagation into answers.
    """
    if not isinstance(history_series, list):
        raise ValueError(
            "isolinear_analysis.align: history_series must be the runtime "
            "data['history_series'] list"
        )

    aligned: dict[str, "pandas.Series"] = {}
    order: list[str] = []
    for series in history_series:
        if not isinstance(series, dict) or series.get("kind") != "numeric":
            continue
        entity_id = series.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id:
            continue
        points = series.get("points")
        points = points if isinstance(points, list) else []
        values: list[float] = []
        stamps: list[int] = []
        for point in points:
            if not isinstance(point, dict):
                continue
            ts = point.get("ts_epoch_ms")
            value = point.get("value")
            if isinstance(ts, bool) or not isinstance(ts, int):
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            fvalue = float(value)
            if fvalue != fvalue or fvalue in (float("inf"), float("-inf")):
                continue
            stamps.append(ts)
            values.append(fvalue)
        if not values:
            raise ValueError(
                f"isolinear_analysis.align: numeric series {entity_id!r} has no "
                "finite points — cannot align; check the requested time window"
            )
        raw = pandas.Series(
            values, index=pandas.to_datetime(stamps, unit="ms"), dtype=float
        )
        # Duplicate timestamps (recorder quirks) collapse to their mean so the
        # resample below never sees a non-unique index.
        raw = raw.groupby(level=0).mean()
        aligned[entity_id] = raw.resample(freq).mean().interpolate()
        if entity_id not in order:
            order.append(entity_id)

    if not aligned:
        raise ValueError(
            "isolinear_analysis.align: no numeric series in history_series — "
            "state (binary/categorical) series cannot be aligned"
        )

    frame = pandas.concat(aligned, axis=1).dropna()
    frame = frame[order]
    if frame.empty:
        raise ValueError(
            "isolinear_analysis.align: no overlapping data after alignment — "
            "the series do not share any time coverage at this resolution; "
            "consider a coarser freq or a different window"
        )
    return frame
