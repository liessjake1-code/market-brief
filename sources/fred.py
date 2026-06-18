"""FRED pulls (spec §7, §7.5; roadmap §5.2).

FRED is the morning-PRIMARY source for Treasury yields (DGS10, DGS2) because the
H.15 release has updated overnight (spec §3.1). For oil it is a CROSS-CHECK / last
resort only: DCOILWTICO lags several business days, so it must never silently
stand in for yesterday's WTI settle (spec §7.5, Decision 14).

Network access is isolated in _fetch_series and injectable, so the fallback logic
is unit-testable offline. Requires FRED_API_KEY (env); degrades to empty when the
key or the service is unavailable (the caller decides what that means per metric).
"""

from __future__ import annotations

import os
from typing import Callable, Optional

import requests

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
REQUEST_TIMEOUT = 15  # seconds; never hang the daily run on a slow FRED

# A series fetcher returns observations oldest->newest as (date_str, value).
SeriesFetcher = Callable[[str, int], list[tuple[str, float]]]


def _fetch_series(series_id: str, limit: int) -> list[tuple[str, float]]:
    """Pull the last `limit` non-missing observations for a FRED series.

    Returns oldest->newest. Raises on HTTP error so the caller can degrade; never
    returns a partial/garbage value silently.
    """
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise RuntimeError("FRED_API_KEY not set")
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }
    resp = requests.get(FRED_BASE, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    obs = resp.json().get("observations", [])
    out: list[tuple[str, float]] = []
    for o in obs:
        val = o.get("value")
        if val in (None, ".", ""):  # FRED marks missing with "."
            continue
        try:
            out.append((o["date"], float(val)))
        except (ValueError, KeyError):
            continue
    out.reverse()  # oldest -> newest
    return out


def latest_value(
    series_id: str,
    *,
    fetcher: Optional[SeriesFetcher] = None,
) -> Optional[tuple[str, float]]:
    """(date_str, value) of the most recent observation, or None on any failure."""
    fetch = fetcher or _fetch_series
    try:
        obs = fetch(series_id, 5)
    except Exception:
        return None
    return obs[-1] if obs else None


def history(
    series_id: str,
    days: int,
    *,
    fetcher: Optional[SeriesFetcher] = None,
) -> list[float]:
    """Recent daily values oldest->newest for seeding rolling history (spec §5.5).

    Used to seed yield history from FRED so the basis matches the daily print.
    Returns [] on failure; the caller decides how to degrade.
    """
    fetch = fetcher or _fetch_series
    try:
        obs = fetch(series_id, days)
    except Exception:
        return []
    return [v for _, v in obs]
