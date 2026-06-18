"""Minor economic events and earnings calendar (spec §7; roadmap §7.12).

SECONDARY content only: feeds "What to Watch Today" and "Earnings on Deck". It is
NEVER the tier-one trigger — that is the hand-verified static file
data/tier_one_calendar.yaml, queried by the Top Story engine (engine/calendars).
A free-API miss here must never change what leads the brief.

Primary provider is Financial Modeling Prep (FMP_API_KEY); Finnhub is the backup
(FINNHUB_API_KEY). Both degrade QUIETLY: a missing key, a network error, or a bad
payload yields [] so the section renders an honest "nothing flagged" line rather
than blocking the brief (spec §5.6, §7.5).

Network is isolated behind an injectable fetcher so the parse/degrade logic is
testable offline.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional

REQUEST_TIMEOUT = 15

FMP_ECON = "https://financialmodelingprep.com/api/v3/economic_calendar"
FMP_EARNINGS = "https://financialmodelingprep.com/api/v3/earning_calendar"
FINNHUB_ECON = "https://finnhub.io/api/v1/calendar/economic"
FINNHUB_EARNINGS = "https://finnhub.io/api/v1/calendar/earnings"

# A fetcher takes a URL + query params and returns parsed JSON (injected for tests).
JsonFetcher = Callable[[str, dict], object]


@dataclass(frozen=True)
class CalendarEvent:
    """One scheduled economic release for 'What to Watch Today'."""

    title: str
    time_label: str          # e.g. "7:30 AM CT" or "" when the provider gives no time
    country: str = "US"
    importance: str = ""      # provider's own importance tag, passed through verbatim


@dataclass(frozen=True)
class EarningsItem:
    """One company reporting, for 'Earnings on Deck'."""

    ticker: str
    name: str = ""
    when: str = ""            # "bmo" | "amc" | "" (before-open / after-close / unknown)


@dataclass(frozen=True)
class CalendarData:
    """What the calendar source returns to the brief; either list may be empty."""

    events: tuple[CalendarEvent, ...] = ()
    earnings: tuple[EarningsItem, ...] = ()
    degraded: bool = False    # True when a key/provider was expected but unavailable


def _fetch(url: str, params: dict) -> object:
    import requests

    resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT,
                        headers={"User-Agent": "market-brief/1.0"})
    resp.raise_for_status()
    return resp.json()


def fetch_calendar(
    day: date,
    *,
    fetcher: Optional[JsonFetcher] = None,
    fmp_key: Optional[str] = None,
    finnhub_key: Optional[str] = None,
) -> CalendarData:
    """Best-effort economic events + earnings for `day`. Never raises.

    Tries FMP first, then Finnhub. With no key for either, returns empty +
    degraded=False (an unconfigured optional source is not a degraded run; the
    section just renders its honest 'nothing flagged' line). A configured key that
    then fails returns degraded=True so the brief can note the gap.
    """
    fetch = fetcher or _fetch
    fmp_key = fmp_key if fmp_key is not None else os.environ.get("FMP_API_KEY")
    finnhub_key = finnhub_key if finnhub_key is not None else os.environ.get("FINNHUB_API_KEY")

    if fmp_key:
        data = _try_fmp(fetch, day, fmp_key)
        if data is not None:
            return data
        # FMP was configured but failed; try the backup before flagging degraded.
        if finnhub_key:
            data = _try_finnhub(fetch, day, finnhub_key)
            if data is not None:
                return data
        return CalendarData(degraded=True)

    if finnhub_key:
        data = _try_finnhub(fetch, day, finnhub_key)
        return data if data is not None else CalendarData(degraded=True)

    # No optional source configured at all: empty, not degraded.
    return CalendarData()


def _try_fmp(fetch: JsonFetcher, day: date, key: str) -> Optional[CalendarData]:
    iso = day.isoformat()
    try:
        econ_raw = fetch(FMP_ECON, {"from": iso, "to": iso, "apikey": key})
        earn_raw = fetch(FMP_EARNINGS, {"from": iso, "to": iso, "apikey": key})
    except Exception:
        return None
    try:
        events = _parse_fmp_events(econ_raw)
        earnings = _parse_fmp_earnings(earn_raw)
    except Exception:
        return None
    return CalendarData(events=events, earnings=earnings, degraded=False)


def _try_finnhub(fetch: JsonFetcher, day: date, key: str) -> Optional[CalendarData]:
    iso = day.isoformat()
    try:
        econ_raw = fetch(FINNHUB_ECON, {"from": iso, "to": iso, "token": key})
        earn_raw = fetch(FINNHUB_EARNINGS, {"from": iso, "to": iso, "token": key})
    except Exception:
        return None
    try:
        events = _parse_finnhub_events(econ_raw)
        earnings = _parse_finnhub_earnings(earn_raw)
    except Exception:
        return None
    return CalendarData(events=events, earnings=earnings, degraded=False)


# --------------------------------------------------------------------------- #
# Parsers — tolerant of missing fields; an unusable row is skipped, not fatal.
# --------------------------------------------------------------------------- #
def _parse_fmp_events(raw: object) -> tuple[CalendarEvent, ...]:
    out: list[CalendarEvent] = []
    for row in _as_rows(raw):
        country = str(row.get("country", "") or "")
        if country and country.upper() not in ("US", "USA", "UNITED STATES"):
            continue
        title = str(row.get("event", "") or "").strip()
        if not title:
            continue
        out.append(CalendarEvent(
            title=title,
            time_label=_time_from_iso(row.get("date")),
            country=country or "US",
            importance=str(row.get("impact", "") or ""),
        ))
    return tuple(out)


def _parse_fmp_earnings(raw: object) -> tuple[EarningsItem, ...]:
    out: list[EarningsItem] = []
    for row in _as_rows(raw):
        ticker = str(row.get("symbol", "") or "").strip().upper()
        if not ticker:
            continue
        out.append(EarningsItem(ticker=ticker, name="", when=_fmp_when(row.get("time"))))
    return tuple(out)


def _parse_finnhub_events(raw: object) -> tuple[CalendarEvent, ...]:
    rows = raw.get("economicCalendar", []) if isinstance(raw, dict) else []
    out: list[CalendarEvent] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        country = str(row.get("country", "") or "")
        if country and country.upper() not in ("US", "USA"):
            continue
        title = str(row.get("event", "") or "").strip()
        if not title:
            continue
        out.append(CalendarEvent(
            title=title,
            time_label=_time_from_iso(row.get("time")),
            country=country or "US",
            importance=str(row.get("impact", "") or ""),
        ))
    return tuple(out)


def _parse_finnhub_earnings(raw: object) -> tuple[EarningsItem, ...]:
    rows = raw.get("earningsCalendar", []) if isinstance(raw, dict) else []
    out: list[EarningsItem] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("symbol", "") or "").strip().upper()
        if not ticker:
            continue
        out.append(EarningsItem(ticker=ticker, name="", when=_finnhub_when(row.get("hour"))))
    return tuple(out)


def _as_rows(raw: object) -> list[dict]:
    return [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []


def _time_from_iso(value: object) -> str:
    """Pull a HH:MM label from a 'YYYY-MM-DD HH:MM:SS' or ISO 'YYYY-MM-DDTHH:MM' stamp."""
    if not value:
        return ""
    text = str(value)
    for sep in (" ", "T"):
        if sep in text:
            clock = text.split(sep, 1)[1]
            return clock[:5] if len(clock) >= 5 else ""
    return ""


def _fmp_when(value: object) -> str:
    text = str(value or "").lower()
    if "before" in text or "bmo" in text:
        return "bmo"
    if "after" in text or "amc" in text:
        return "amc"
    return ""


def _finnhub_when(value: object) -> str:
    text = str(value or "").lower()
    if text in ("bmo", "amc"):
        return text
    return ""
