"""Movers selection (spec §7 best-effort rule), pure.

Movers is treated as best-effort: default to watchlist-only, upgrade to the
fuller curated-universe gainers/losers list only when the universe screen is
reliable, and degrade to watchlist-only rather than print noise. The volume
floor (config movers_min_volume) gates a move from being headlined; raw
pre-market/thin ticks are noisy and easy to misread.

Pure: takes already-fetched StockQuotes + config, returns a ranked selection.
"""

from __future__ import annotations

from engine import movers as M
from sources.stocks import StockQuote


def _q(ticker, close, prev, volume):
    hist = (prev, close) if prev is not None else (close,)
    return StockQuote(
        ticker=ticker,
        close=close,
        prev_close=prev,
        history=hist,
        history_dates=(),
        volume=volume,
    )


def test_ranks_by_absolute_session_move():
    quotes = {
        "AAA": _q("AAA", 110.0, 100.0, 1_000_000),  # +10%
        "BBB": _q("BBB", 95.0, 100.0, 1_000_000),   # -5%
        "CCC": _q("CCC", 101.0, 100.0, 1_000_000),  # +1%
    }
    sel = M.select_movers(quotes, watchlist=[], universe=["AAA", "BBB", "CCC"], min_volume=0)
    # Biggest absolute movers first.
    assert [m.ticker for m in sel.movers][:2] == ["AAA", "BBB"]


def test_volume_floor_drops_thin_names():
    quotes = {
        "THIN": _q("THIN", 200.0, 100.0, 10),       # +100% but tiny volume
        "LIQ": _q("LIQ", 105.0, 100.0, 1_000_000),  # +5% liquid
    }
    sel = M.select_movers(quotes, watchlist=[], universe=["THIN", "LIQ"], min_volume=50_000)
    tickers = [m.ticker for m in sel.movers]
    assert "THIN" not in tickers       # below floor -> not headlined
    assert "LIQ" in tickers


def test_watchlist_names_bypass_volume_floor():
    # The watchlist is "names you already track" -- show them even if thin.
    quotes = {
        "WL": _q("WL", 120.0, 100.0, 10),  # +20%, tiny volume, but on the watchlist
    }
    sel = M.select_movers(quotes, watchlist=["WL"], universe=[], min_volume=50_000)
    assert [m.ticker for m in sel.movers] == ["WL"]


def test_default_watchlist_only_when_universe_empty():
    quotes = {
        "WL": _q("WL", 110.0, 100.0, 1_000_000),
        "UNI": _q("UNI", 120.0, 100.0, 1_000_000),
    }
    # No universe configured -> watchlist-only mode, universe names excluded.
    sel = M.select_movers(quotes, watchlist=["WL"], universe=[], min_volume=0)
    assert [m.ticker for m in sel.movers] == ["WL"]
    assert sel.watchlist_only is True


def test_upgrades_to_universe_when_reliable():
    quotes = {
        "WL": _q("WL", 110.0, 100.0, 1_000_000),
        "UNI": _q("UNI", 120.0, 100.0, 1_000_000),
    }
    sel = M.select_movers(quotes, watchlist=["WL"], universe=["UNI", "WL"], min_volume=0)
    tickers = {m.ticker for m in sel.movers}
    assert "UNI" in tickers and "WL" in tickers
    assert sel.watchlist_only is False


def test_degrades_to_watchlist_only_when_universe_unreliable():
    # The universe is configured but almost none of it came back (thin screen).
    quotes = {
        "WL": _q("WL", 110.0, 100.0, 1_000_000),
        # only 1 of 5 universe names returned -> unreliable screen
        "UNI1": _q("UNI1", 120.0, 100.0, 1_000_000),
    }
    sel = M.select_movers(
        quotes,
        watchlist=["WL"],
        universe=["UNI1", "UNI2", "UNI3", "UNI4", "UNI5"],
        min_volume=0,
    )
    assert sel.watchlist_only is True
    assert [m.ticker for m in sel.movers] == ["WL"]  # noise avoided


def test_caps_to_max_movers():
    quotes = {
        f"T{i}": _q(f"T{i}", 100.0 + i, 100.0, 1_000_000) for i in range(1, 12)
    }
    universe = list(quotes.keys())
    sel = M.select_movers(quotes, watchlist=[], universe=universe, min_volume=0)
    assert len(sel.movers) <= M.MAX_MOVERS


def test_flat_names_excluded():
    quotes = {
        "FLAT": _q("FLAT", 100.0, 100.0, 1_000_000),     # 0%
        "MOVED": _q("MOVED", 103.0, 100.0, 1_000_000),   # +3%
    }
    sel = M.select_movers(quotes, watchlist=[], universe=["FLAT", "MOVED"], min_volume=0)
    assert [m.ticker for m in sel.movers] == ["MOVED"]


def test_empty_quotes_yields_empty_selection():
    sel = M.select_movers({}, watchlist=["WL"], universe=["UNI"], min_volume=0)
    assert sel.movers == ()
    assert sel.watchlist_only is True


def test_missing_change_pct_excluded():
    # A quote with no prev_close (single point) has no change -> can't be a mover.
    quotes = {"NOPREV": _q("NOPREV", 100.0, None, 1_000_000)}
    sel = M.select_movers(quotes, watchlist=[], universe=["NOPREV"], min_volume=0)
    assert sel.movers == ()
