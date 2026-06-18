"""Per-stock view assembly: stat rows + sparklines for Watchlist/Movers.

The per-stock table reuses engine.stats cell/change formatting (stocks are
equities, so percent change, never bps) and labels each row by its ticker. The
viewmodel builds these from already-fetched StockQuotes; thin history shows an
em dash per window, same self-heal as the macro metrics.
"""

from __future__ import annotations

from engine import stats as stats_mod
from engine.movers import MoverRow, MoversSelection
from render import viewmodel as vm
from sources.stocks import StockQuote


def _quote(ticker, closes, volume=1_000_000):
    return StockQuote(
        ticker=ticker,
        close=closes[-1] if closes else None,
        prev_close=closes[-2] if len(closes) >= 2 else None,
        history=tuple(closes),
        history_dates=tuple(f"d{i}" for i in range(len(closes))),
        volume=volume,
    )


# --- stock stat row -------------------------------------------------------- #
def test_stock_stat_row_labels_by_ticker_and_percent():
    q = _quote("NVDA", [100.0, 110.0])  # +10% session
    row = stats_mod.stock_stat_row(q)
    assert row.label == "NVDA"
    assert row.session.text == "+10.0%"
    assert row.session.direction == "up"


def test_stock_stat_row_thin_history_blank_windows():
    q = _quote("QUBT", [10.0, 10.76])  # only 2 points -> week/month blank
    row = stats_mod.stock_stat_row(q)
    assert row.session.text.endswith("%")   # session computable
    assert row.week.is_blank                 # not enough history
    assert row.month.is_blank


def test_stock_stat_row_level_is_price_formatted():
    q = _quote("TSLA", [240.0, 245.0])
    row = stats_mod.stock_stat_row(q)
    assert row.level == "245.00"


# --- viewmodel: build_stock_table ------------------------------------------ #
def test_build_stock_table_from_quotes_in_order():
    quotes = {
        "NVDA": _quote("NVDA", [100.0, 110.0]),
        "TSLA": _quote("TSLA", [240.0, 245.0]),
    }
    rows = vm.build_stock_table(["TSLA", "NVDA"], quotes)
    assert [r.label for r in rows] == ["TSLA", "NVDA"]  # caller order preserved


def test_build_stock_table_skips_missing_tickers():
    quotes = {"NVDA": _quote("NVDA", [100.0, 110.0])}
    rows = vm.build_stock_table(["NVDA", "GONE"], quotes)
    assert [r.label for r in rows] == ["NVDA"]


# --- viewmodel: build_stock_sparklines ------------------------------------- #
def test_build_stock_sparklines_from_quotes():
    quotes = {"NVDA": _quote("NVDA", [100.0, 102.0, 110.0])}
    sparks = vm.build_stock_sparklines(["NVDA"], quotes)
    assert len(sparks) == 1
    assert sparks[0].ticker == "NVDA"
    assert sparks[0].up is True


def test_build_stock_sparklines_skips_single_point():
    quotes = {"ONE": _quote("ONE", [100.0])}
    assert vm.build_stock_sparklines(["ONE"], quotes) == ()


# --- viewmodel: movers table from selection -------------------------------- #
def test_build_movers_table_from_selection():
    quotes = {
        "AAA": _quote("AAA", [100.0, 110.0]),
        "BBB": _quote("BBB", [100.0, 95.0]),
    }
    sel = MoversSelection(
        movers=(
            MoverRow("AAA", quotes["AAA"], 10.0, False),
            MoverRow("BBB", quotes["BBB"], -5.0, False),
        ),
        watchlist_only=False,
    )
    rows = vm.build_movers_table(sel, quotes)
    assert [r.label for r in rows] == ["AAA", "BBB"]
    assert rows[0].session.direction == "up"
    assert rows[1].session.direction == "down"
