from __future__ import annotations
import inspect
import os
from typing import Callable, Optional
from marketbrief.core.models import SourceResult, Field
from marketbrief.core.enums import SourceHealth
from marketbrief.core.symbols import SYMBOLS
from marketbrief.fetch.net import is_offline, REQUEST_TIMEOUT

SeriesFetcher = Callable[..., list[tuple[str, float]]]
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


def _real_series_fetcher(series_id: str, limit: int, *, units: Optional[str] = None):
    """Pull last `limit` non-missing observations oldest->newest. Raises on error."""
    import requests

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise RuntimeError("FRED_API_KEY not set")
    params = {"series_id": series_id, "api_key": api_key, "file_type": "json",
              "sort_order": "desc", "limit": limit}
    if units:
        params["units"] = units
    try:
        resp = requests.get(FRED_BASE, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        # Never let the api_key in the request URL leak into exception text,
        # which flows into SourceResult.error and stderr logs.
        status = getattr(getattr(exc, "response", None), "status_code", "error")
        raise RuntimeError(f"FRED request failed for {series_id}: {status}") from None
    obs = resp.json().get("observations", [])
    out: list[tuple[str, float]] = []
    for o in obs:
        val = o.get("value")
        if val in (None, ".", ""):
            continue
        try:
            out.append((o["date"], float(val)))
        except (ValueError, KeyError):
            continue
    out.reverse()
    return out


def _call_fetcher(fetch: SeriesFetcher, series_id: str, n: int, units: Optional[str]):
    """Pass `units` only when the fetcher accepts it; never drop it silently.

    Dropping a requested transform would store a raw index (~320) instead of the
    YoY rate (~3.2) -- a wrong number. Accuracy invariant forbids that.
    """
    if not units:
        return fetch(series_id, n)
    try:
        accepts = "units" in inspect.signature(fetch).parameters
    except (TypeError, ValueError):
        accepts = False
    return fetch(series_id, n, units=units) if accepts else fetch(series_id, n)


class FredSource:
    name = "fred"

    def __init__(self, series_fetcher: SeriesFetcher | None = None):
        self._fetch = series_fetcher or _real_series_fetcher

    def fetch(self, ctx) -> SourceResult:
        if is_offline():
            return self._offline()
        fields: dict[str, Field] = {}
        try:
            for sym in SYMBOLS:
                if not sym.fred:
                    continue
                obs = _call_fetcher(self._fetch, sym.fred, 5, sym.fred_units)
                if obs:
                    as_of, value = obs[-1]
                    fields[sym.metric] = Field(metric=sym.metric, value=value, source="fred", as_of=as_of)
                else:
                    fields[sym.metric] = Field(metric=sym.metric, value=None, source="missing")
        except Exception as exc:
            return SourceResult(name=self.name, fields={}, health=SourceHealth.FAILED, error=str(exc))
        return SourceResult(name=self.name, fields=fields, health=SourceHealth.OK)

    def _offline(self) -> SourceResult:
        fields = {
            s.metric: Field(metric=s.metric, value=1.0, source="fred", as_of="2026-06-19")
            for s in SYMBOLS if s.fred
        }
        return SourceResult(name=self.name, fields=fields, health=SourceHealth.OK)
