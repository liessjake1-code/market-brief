"""Phase 7: the secondary calendar parses FMP/Finnhub and degrades quietly (roadmap §7).

Never the tier-one trigger (that stays in engine/calendars off the static YAML);
a free-API miss here must never block the brief or change what leads it.
"""

from __future__ import annotations

from datetime import date

from sources import calendar as cal

DAY = date(2026, 6, 17)


def test_no_keys_returns_empty_not_degraded():
    data = cal.fetch_calendar(DAY, fmp_key=None, finnhub_key=None)
    assert data.events == ()
    assert data.earnings == ()
    assert data.degraded is False  # an unconfigured optional source is not a degraded run


def test_fmp_failure_falls_back_to_finnhub():
    def fetcher(url, params):
        if "financialmodelingprep" in url:
            raise RuntimeError("FMP down")
        if "economic" in url:
            return {"economicCalendar": [{"country": "US", "event": "CPI", "time": "2026-06-17 07:30:00"}]}
        return {"earningsCalendar": [{"symbol": "AAPL", "hour": "amc"}]}

    data = cal.fetch_calendar(DAY, fetcher=fetcher, fmp_key="x", finnhub_key="y")
    assert data.degraded is False
    assert any(e.title == "CPI" for e in data.events)
    assert any(e.ticker == "AAPL" for e in data.earnings)


def test_fmp_success_parses_events_and_earnings():
    def fetcher(url, params):
        if "economic_calendar" in url:
            return [{"country": "US", "event": "Retail Sales", "date": "2026-06-17 07:30:00", "impact": "High"}]
        if "earning_calendar" in url:
            return [{"symbol": "fdx", "time": "bmo"}]
        return []

    data = cal.fetch_calendar(DAY, fetcher=fetcher, fmp_key="x")
    assert data.events[0].title == "Retail Sales"
    assert data.events[0].time_label == "07:30"
    assert data.earnings[0].ticker == "FDX"
    assert data.earnings[0].when == "bmo"


def test_both_providers_down_is_degraded():
    def fetcher(url, params):
        raise RuntimeError("network")

    data = cal.fetch_calendar(DAY, fetcher=fetcher, fmp_key="x", finnhub_key="y")
    assert data.degraded is True
    assert data.events == ()


def test_non_us_events_are_filtered():
    def fetcher(url, params):
        if "economic_calendar" in url:
            return [{"country": "JP", "event": "BOJ Decision", "date": "2026-06-17 03:00:00"}]
        return []

    data = cal.fetch_calendar(DAY, fetcher=fetcher, fmp_key="x")
    assert data.events == ()
