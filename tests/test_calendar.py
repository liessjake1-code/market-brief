"""Phase 7 + calendar rewire: economic events come from FRED, earnings from Finnhub.

SECONDARY content only (never the tier-one trigger, which stays in engine/calendars
off the static YAML). The two sources are independent and each degrades quietly; a
free-API miss here must never block the brief or change what leads it.
"""

from __future__ import annotations

from datetime import date

from sources import calendar as cal

DAY = date(2026, 6, 17)
ISO = DAY.isoformat()


def _fred_rows(*names: str, on: str = ISO) -> list[dict]:
    return [{"date": on, "release_name": n} for n in names]


def test_no_keys_returns_empty_not_degraded():
    data = cal.fetch_calendar(DAY, fred_key=None, finnhub_key=None)
    assert data.events == ()
    assert data.earnings == ()
    assert data.degraded is False  # an unconfigured optional source is not a degraded run


def test_fred_curated_release_is_kept_with_time():
    rows = _fred_rows("Consumer Price Index", "Some Obscure Regional Survey")
    data = cal.fetch_calendar(
        DAY, releases_fetcher=lambda a, b: rows, fred_key="k", finnhub_key=None,
    )
    titles = [e.title for e in data.events]
    assert "Consumer Price Index (CPI)" in titles       # curated -> kept, friendly title
    assert all("Obscure" not in t for t in titles)        # uncurated -> dropped
    cpi = next(e for e in data.events if "CPI" in e.title)
    assert cpi.time_label == "7:30 AM CT"                  # static time map applied
    assert data.degraded is False


def test_fred_filters_other_dates_and_dedups():
    rows = _fred_rows("Employment Situation") + _fred_rows("Employment Situation") \
        + _fred_rows("Consumer Price Index", on="2026-06-18")  # different day
    data = cal.fetch_calendar(
        DAY, releases_fetcher=lambda a, b: rows, fred_key="k", finnhub_key=None,
    )
    titles = [e.title for e in data.events]
    assert titles.count("Employment Situation (jobs report)") == 1  # de-duped
    assert all("CPI" not in t for t in titles)                       # wrong day filtered


def test_finnhub_earnings_parsed():
    def fetcher(url, params):
        assert "finnhub" in url
        return {"earningsCalendar": [{"symbol": "fdx", "hour": "amc"},
                                     {"symbol": "NKE", "hour": "bmo"}]}

    data = cal.fetch_calendar(
        DAY, fetcher=fetcher, releases_fetcher=lambda a, b: [],
        fred_key="k", finnhub_key="y",
    )
    tickers = {e.ticker: e.when for e in data.earnings}
    assert tickers == {"FDX": "amc", "NKE": "bmo"}
    assert data.degraded is False


def test_fred_failure_is_degraded_earnings_still_ok():
    """The two sources are independent: FRED can fail while Finnhub succeeds."""
    def bad_releases(a, b):
        raise RuntimeError("FRED down")

    def fetcher(url, params):
        return {"earningsCalendar": [{"symbol": "AAPL", "hour": "amc"}]}

    data = cal.fetch_calendar(
        DAY, fetcher=fetcher, releases_fetcher=bad_releases,
        fred_key="k", finnhub_key="y",
    )
    assert data.degraded is True                       # FRED was configured and failed
    assert data.events == ()
    assert any(e.ticker == "AAPL" for e in data.earnings)  # earnings unaffected


def test_finnhub_failure_is_degraded_events_still_ok():
    def fetcher(url, params):
        raise RuntimeError("network")

    data = cal.fetch_calendar(
        DAY, fetcher=fetcher,
        releases_fetcher=lambda a, b: _fred_rows("Producer Price Index"),
        fred_key="k", finnhub_key="y",
    )
    assert data.degraded is True                        # Finnhub configured and failed
    assert any("PPI" in e.title for e in data.events)   # FRED events unaffected
    assert data.earnings == ()
