"""Phase 7: source-link routing — yields to FRED, everything else to Yahoo (spec §7)."""

from __future__ import annotations

from render import source_links as sl


def test_yields_link_to_fred():
    assert sl.source_url("ust10y") == "https://fred.stlouisfed.org/series/DGS10"
    assert sl.source_url("ust2y") == "https://fred.stlouisfed.org/series/DGS2"


def test_oil_links_to_yahoo_not_fred():
    # WTI is yfinance-primary in the morning; FRED is cross-check only (spec §3.1).
    url = sl.source_url("wti")
    assert "finance.yahoo.com/quote" in url
    assert "fred" not in url


def test_index_links_to_yahoo_quote():
    assert sl.source_url("sp500") == "https://finance.yahoo.com/quote/%5EGSPC"


def test_unknown_metric_returns_none():
    assert sl.source_url("not_a_metric") is None


def test_favicon_url_graceful_on_missing_domain():
    assert sl.favicon_url(None) is None
    assert sl.favicon_url("nvidia.com") == "https://www.google.com/s2/favicons?domain=nvidia.com&sz=64"


def test_ticker_url():
    assert sl.yahoo_ticker_url("AAPL") == "https://finance.yahoo.com/quote/AAPL"
