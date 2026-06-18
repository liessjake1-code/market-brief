"""Minor economic events and earnings calendar (spec §7; roadmap §7.12).

SECONDARY content only: feeds "What to Watch Today" and "Earnings on Deck". It is
NEVER the tier-one trigger — that is the hand-verified static file
data/tier_one_calendar.yaml, queried by the Top Story engine (engine/calendars).
A free-API miss here must never change what leads the brief.

Sources are chosen to be genuinely FREE and reachable from the cloud runner:
  - Economic events: FRED /releases/dates (the existing FRED_API_KEY). Government-
    backed, rock-solid from datacenter IPs. FRED gives the release DATE only, so a
    curated static time map supplies the usual release clock time.
  - Earnings: Finnhub /calendar/earnings (FINNHUB_API_KEY). The earnings calendar
    is on Finnhub's free tier (its economic calendar is premium, so we do not use
    that one). US-only, which is exactly what we want.
FMP was the original primary but moved its calendar endpoints behind a paid plan,
so it is no longer used here.

The two sources are INDEPENDENT: economic may succeed while earnings fails and
vice versa. Each degrades QUIETLY — a missing key, network error, or bad payload
yields [] so the section renders an honest "nothing flagged" line rather than
blocking the brief (spec §5.6, §7.5). A configured source that then fails sets
degraded=True so the brief can note the gap (it never trips the whole-brief banner;
that is core-data/model only — see brief.py).

Network is isolated behind injectable fetchers so the parse/degrade logic is
testable offline.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional

from sources import fred as fred_mod

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15

FINNHUB_EARNINGS = "https://finnhub.io/api/v1/calendar/earnings"

# A fetcher takes a URL + query params and returns parsed JSON (injected for tests).
JsonFetcher = Callable[[str, dict], object]

# Curated, market-moving US economic releases. We match a FRED release_name by
# substring (case-insensitive) against these keys and attach the canonical release
# clock time (US Central, to match the brief's 8:30 AM CT framing). FRED gives the
# date only; these times are the long-standing official release schedule. Keeping
# this list curated keeps "What to Watch" signal-dense instead of dumping every
# minor FRED release. Tier-one leads still come from the static YAML, not here.
_RELEASE_TIMES: dict[str, str] = {
    "consumer price index": "7:30 AM CT",
    "producer price index": "7:30 AM CT",
    "employment situation": "7:30 AM CT",
    "personal income and outlays": "7:30 AM CT",
    "gross domestic product": "7:30 AM CT",
    "advance monthly sales for retail": "7:30 AM CT",   # FRED's name for Retail Sales
    "retail sales": "7:30 AM CT",
    "unemployment insurance weekly claims": "7:30 AM CT",
    "import and export price indexes": "7:30 AM CT",
    "new residential construction": "7:30 AM CT",       # Housing Starts
    "industrial production": "8:15 AM CT",
    "job openings and labor turnover": "9:00 AM CT",     # JOLTS
    "new home sales": "9:00 AM CT",
    "existing home sales": "9:00 AM CT",
    "consumer confidence": "9:00 AM CT",
    "g.17 industrial production": "8:15 AM CT",
}

# Friendlier display titles for FRED's formal release names (substring -> title).
_RELEASE_TITLES: dict[str, str] = {
    "consumer price index": "Consumer Price Index (CPI)",
    "producer price index": "Producer Price Index (PPI)",
    "employment situation": "Employment Situation (jobs report)",
    "personal income and outlays": "Personal Income and Outlays (PCE)",
    "gross domestic product": "Gross Domestic Product (GDP)",
    "advance monthly sales for retail": "Retail Sales",
    "retail sales": "Retail Sales",
    "unemployment insurance weekly claims": "Weekly Jobless Claims",
    "import and export price indexes": "Import and Export Prices",
    "new residential construction": "Housing Starts",
    "job openings and labor turnover": "JOLTS Job Openings",
}


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
    releases_fetcher: Optional[fred_mod.ReleasesDatesFetcher] = None,
    fred_key: Optional[str] = None,
    finnhub_key: Optional[str] = None,
) -> CalendarData:
    """Best-effort economic events (FRED) + earnings (Finnhub) for `day`. Never raises.

    The two sources are independent and degrade on their own: economic events come
    from FRED's release schedule, earnings from Finnhub. With NO key configured for
    either, returns empty + degraded=False (an unconfigured optional source is not a
    degraded run; the section renders its honest 'nothing flagged' line). A
    configured source that then fails contributes degraded=True so the brief can
    note the gap. degraded never trips the whole-brief banner (brief.py decides).
    """
    fetch = fetcher or _fetch
    fred_key = fred_key if fred_key is not None else os.environ.get("FRED_API_KEY")
    finnhub_key = finnhub_key if finnhub_key is not None else os.environ.get("FINNHUB_API_KEY")

    events: tuple[CalendarEvent, ...] = ()
    earnings: tuple[EarningsItem, ...] = ()
    degraded = False

    if fred_key:
        ev = _try_fred_econ(day, releases_fetcher)
        if ev is None:
            degraded = True
        else:
            events = ev

    if finnhub_key:
        ea = _try_finnhub_earnings(fetch, day, finnhub_key)
        if ea is None:
            degraded = True
        else:
            earnings = ea

    return CalendarData(events=events, earnings=earnings, degraded=degraded)


def _try_fred_econ(
    day: date,
    releases_fetcher: Optional[fred_mod.ReleasesDatesFetcher],
) -> Optional[tuple[CalendarEvent, ...]]:
    """Today's curated US economic releases from FRED's schedule, or None on failure."""
    fetch = releases_fetcher or fred_mod.fetch_release_dates
    iso = day.isoformat()
    try:
        rows = fetch(iso, iso)
    except Exception as exc:
        logger.warning("calendar: FRED releases fetch failed (%s)", _describe_error(exc))
        return None
    try:
        return _parse_fred_events(rows, iso)
    except Exception as exc:
        logger.warning("calendar: FRED releases parse failed (%s)", _describe_error(exc))
        return None


def _try_finnhub_earnings(
    fetch: JsonFetcher, day: date, key: str,
) -> Optional[tuple[EarningsItem, ...]]:
    """US earnings reporting on `day` from Finnhub, or None on failure."""
    iso = day.isoformat()
    try:
        earn_raw = fetch(FINNHUB_EARNINGS, {"from": iso, "to": iso, "token": key})
    except Exception as exc:
        logger.warning("calendar: Finnhub earnings fetch failed (%s)", _describe_error(exc))
        return None
    try:
        return _parse_finnhub_earnings(earn_raw)
    except Exception as exc:
        logger.warning("calendar: Finnhub earnings parse failed (%s)", _describe_error(exc))
        return None


def _parse_fred_events(rows: list[dict], iso: str) -> tuple[CalendarEvent, ...]:
    """Keep curated, market-moving releases scheduled for `iso`; skip the rest.

    De-duplicates by display title (FRED can list a release more than once). Rows
    that match no curated key are dropped so 'What to Watch' stays signal-dense.
    """
    seen: set[str] = set()
    out: list[CalendarEvent] = []
    for row in rows:
        if str(row.get("date", "")) != iso:
            continue
        name = str(row.get("release_name", "") or "").strip()
        if not name:
            continue
        match = _match_release(name)
        if match is None:
            continue
        title = _RELEASE_TITLES.get(match, name)
        if title in seen:
            continue
        seen.add(title)
        out.append(CalendarEvent(
            title=title,
            time_label=_RELEASE_TIMES.get(match, ""),
            country="US",
            importance="",
        ))
    return tuple(out)


def _match_release(release_name: str) -> Optional[str]:
    """Return the curated key whose substring appears in release_name, else None."""
    low = release_name.lower()
    for key in _RELEASE_TIMES:
        if key in low:
            return key
    return None


def _describe_error(exc: Exception) -> str:
    """A short diagnosable reason, surfacing the HTTP status code when present.

    requests' HTTPError carries the response (and thus the status) on `.response`;
    a 402/403 here is the telltale sign of a free tier that moved the endpoint to
    paid, which is exactly what the human needs to see in the run log.
    """
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status is not None:
        return f"HTTP {status}: {type(exc).__name__}"
    return f"{type(exc).__name__}: {exc}"


# --------------------------------------------------------------------------- #
# Parsers — tolerant of missing fields; an unusable row is skipped, not fatal.
# --------------------------------------------------------------------------- #
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


def _finnhub_when(value: object) -> str:
    text = str(value or "").lower()
    if text in ("bmo", "amc"):
        return text
    return ""
