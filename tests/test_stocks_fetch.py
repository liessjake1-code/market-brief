"""Per-stock batch fetch (watchlist + movers).

A best-effort, graceful-fail pull of per-ticker daily closes + dates + latest
volume. A failed ticker is simply omitted from the result; the fetch NEVER
raises and NEVER trips the brief's degraded banner (that stays core-metric /
model only, spec §7.5). The network call is injected so tests run offline.
"""

from __future__ import annotations

import pytest

from sources import stocks as ST


# --- a deterministic offline downloader ----------------------------------- #
def _fake_dl(ticker: str, days: int):
    """Return (closes, dates, volume) oldest->newest for known tickers, else empty."""
    table = {
        "NVDA": ([128.0, 130.0, 132.5], ["2026-06-16", "2026-06-17", "2026-06-18"], 250_000),
        "TSLA": ([240.0, 245.0], ["2026-06-17", "2026-06-18"], 80_000),
        "QUBT": ([], [], None),  # a ticker that returns nothing
    }
    return table.get(ticker, ([], [], None))


def test_fetch_returns_quote_per_successful_ticker():
    out = ST.fetch_stocks(["NVDA", "TSLA"], downloader=_fake_dl)
    assert set(out.keys()) == {"NVDA", "TSLA"}
    nvda = out["NVDA"]
    assert nvda.ticker == "NVDA"
    assert nvda.close == 132.5
    assert nvda.prev_close == 130.0
    assert nvda.history == (128.0, 130.0, 132.5)
    assert nvda.history_dates == ("2026-06-16", "2026-06-17", "2026-06-18")
    assert nvda.volume == 250_000


def test_empty_ticker_is_omitted_not_raised():
    out = ST.fetch_stocks(["NVDA", "QUBT"], downloader=_fake_dl)
    assert "NVDA" in out
    assert "QUBT" not in out  # no data -> dropped, not a crash


def test_unknown_ticker_is_omitted():
    out = ST.fetch_stocks(["ZZZZ"], downloader=_fake_dl)
    assert out == {}


def test_downloader_exception_is_swallowed_per_ticker():
    def boom(ticker: str, days: int):
        if ticker == "BAD":
            raise RuntimeError("yfinance blew up")
        return _fake_dl(ticker, days)

    out = ST.fetch_stocks(["BAD", "NVDA"], downloader=boom)
    # The bad ticker is dropped; the good one survives. Never raises.
    assert "BAD" not in out
    assert "NVDA" in out


def test_prev_close_none_with_single_point():
    def single(ticker: str, days: int):
        return ([100.0], ["2026-06-18"], 5_000)

    out = ST.fetch_stocks(["ONE"], downloader=single)
    assert out["ONE"].close == 100.0
    assert out["ONE"].prev_close is None
    assert out["ONE"].history == (100.0,)


def test_change_pct_computed_from_close_and_prev():
    out = ST.fetch_stocks(["TSLA"], downloader=_fake_dl)
    # (245 - 240) / 240 * 100 = 2.083...
    assert out["TSLA"].change_pct == pytest.approx(2.0833, abs=1e-3)


def test_change_pct_none_when_no_prev():
    def single(ticker: str, days: int):
        return ([100.0], ["2026-06-18"], 5_000)

    out = ST.fetch_stocks(["ONE"], downloader=single)
    assert out["ONE"].change_pct is None


def test_empty_ticker_list_returns_empty():
    assert ST.fetch_stocks([], downloader=_fake_dl) == {}


def test_dedupes_tickers():
    out = ST.fetch_stocks(["NVDA", "NVDA"], downloader=_fake_dl)
    assert list(out.keys()) == ["NVDA"]
