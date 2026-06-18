"""Fix (A): an optional-calendar failure must NOT trip the degraded banner.

The degraded banner is reserved for stale CORE data or a failed model (spec §7.5).
When the optional "What to Watch" events feed fails, the brief shows an honest
per-section note and logs the HTTP-status reason, but the banner stays clean.
"""

from __future__ import annotations

import logging
from datetime import date

import pytest

import brief
from engine.metrics import METRIC_KEYS
from sources import calendar as cal
from sources.quality import Field, Source, assess

DAY = date(2026, 6, 17)


def _clean_report():
    """A fully-usable core report: nothing core is stale or missing."""
    fields = {k: Field(k, 100.0, Source.YFINANCE) for k in METRIC_KEYS}
    return assess(fields, degraded_stale_threshold=2, hard_floor_missing_threshold=4)


def test_calendar_failure_does_not_trip_banner(monkeypatch):
    monkeypatch.setattr(brief, "_load_calendar",
                        lambda cfg, today: cal.CalendarData(degraded=True))
    report = _clean_report()

    view = brief._build_view({}, DAY, report, {}, {})

    assert view.degraded is False                       # banner stays clean
    assert view.calendar_note == brief._CALENDAR_DEGRADED_NOTE  # honest note instead


def test_clean_calendar_leaves_no_note(monkeypatch):
    monkeypatch.setattr(brief, "_load_calendar",
                        lambda cfg, today: cal.CalendarData())
    report = _clean_report()

    view = brief._build_view({}, DAY, report, {}, {})

    assert view.degraded is False
    assert view.calendar_note == ""


def test_core_failure_still_trips_banner(monkeypatch):
    """The banner must still fire for its real cause: stale/missing CORE data."""
    monkeypatch.setattr(brief, "_load_calendar",
                        lambda cfg, today: cal.CalendarData())  # calendar fine
    fields = {k: Field(k, None, Source.MISSING) for k in METRIC_KEYS}
    report = assess(fields, degraded_stale_threshold=2, hard_floor_missing_threshold=4)
    assert report.degraded is True                      # core data is gone

    view = brief._build_view({}, DAY, report, {}, {})

    assert view.degraded is True                        # banner correctly fires


def test_describe_error_surfaces_http_status():
    class _Resp:
        status_code = 402

    class _HTTPError(Exception):
        response = _Resp()

    assert "HTTP 402" in cal._describe_error(_HTTPError("Payment Required"))


def test_describe_error_without_response():
    assert "RuntimeError" in cal._describe_error(RuntimeError("network"))


def test_failed_provider_logs_reason(monkeypatch, caplog):
    def fetcher(url, params):
        raise RuntimeError("network down")

    with caplog.at_level(logging.WARNING, logger="sources.calendar"):
        data = cal.fetch_calendar(DAY, fetcher=fetcher, fmp_key="x", finnhub_key="y")

    assert data.degraded is True
    text = caplog.text
    assert "FMP fetch failed" in text
    assert "Finnhub fetch failed" in text
