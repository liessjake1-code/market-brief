"""Tests for the Movers universe fetch: tickers -> closes, isolated and offline-safe."""
import os
from unittest import mock

import pytest

from marketbrief.fetch.universe import fetch_universe_closes


@pytest.fixture
def online_env(monkeypatch):
    """Ensure the offline seam is OFF so the injected downloader is exercised.

    The full suite runs under MARKET_BRIEF_OFFLINE=1; these tests verify the
    online fetch path with a fake downloader, so they must clear that env var.
    """
    monkeypatch.delenv("MARKET_BRIEF_OFFLINE", raising=False)


def test_fetch_returns_closes_per_ticker(online_env):
    downloader = lambda sym, days: [100.0, 101.0, 102.0]
    out = fetch_universe_closes(["AAPL", "MSFT"], downloader=downloader)
    assert out == {"AAPL": [100.0, 101.0, 102.0], "MSFT": [100.0, 101.0, 102.0]}


def test_empty_universe_returns_empty(online_env):
    called = []
    downloader = lambda sym, days: called.append(sym) or [1.0]
    assert fetch_universe_closes([], downloader=downloader) == {}
    assert called == []


def test_failing_ticker_is_skipped_not_raised(online_env):
    def downloader(sym, days):
        if sym == "BAD":
            raise RuntimeError("network blip")
        return [100.0, 110.0]
    out = fetch_universe_closes(["GOOD", "BAD"], downloader=downloader)
    assert "GOOD" in out and out["GOOD"] == [100.0, 110.0]
    assert "BAD" not in out  # isolated failure, no raise


def test_empty_close_series_is_dropped(online_env):
    downloader = lambda sym, days: [] if sym == "EMPTY" else [1.0, 2.0]
    out = fetch_universe_closes(["EMPTY", "FULL"], downloader=downloader)
    assert "EMPTY" not in out and "FULL" in out


@mock.patch.dict(os.environ, {"MARKET_BRIEF_OFFLINE": "1"})
def test_offline_returns_empty_without_calling_downloader():
    called = []
    downloader = lambda sym, days: called.append(sym) or [1.0]
    out = fetch_universe_closes(["AAPL"], downloader=downloader)
    assert out == {}
    assert called == []
