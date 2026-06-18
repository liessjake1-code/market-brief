"""Fix #5 — no stale quiet line under a populated Movers/Watchlist table, and the
per-stock "why" note is de-duped across the two sections.

The delivered Jun 18 PDF printed "No single-stock movers flagged..." and
"Watchlist is empty. Add tickers in config.yaml" UNDER tables that were fully
populated with real stocks, because the section prose still fell back to the
SECTION_QUIET_LINE when the model wrote no section-level cause. Now: when a stock
table OR per-stock notes exist, the quiet line is suppressed (the table + notes
carry the section). Separately, a ticker's "why" note appears in only ONE section
(Movers preferred) so the SPCX article is not duplicated across both.
"""

from __future__ import annotations

from engine import stats as stats_mod
from render import viewmodel as vm
from sources.stocks import StockQuote


def _quote(ticker, closes):
    return StockQuote(
        ticker=ticker, close=closes[-1], prev_close=closes[-2],
        history=tuple(closes), history_dates=tuple(f"d{i}" for i in range(len(closes))),
        volume=1_000_000,
    )


def _watchlist_quiet() -> str:
    return vm.SECTION_QUIET_LINE["watchlist"]


def _movers_quiet() -> str:
    return vm.SECTION_QUIET_LINE["movers"]


# --- part A: quiet line suppressed when a stock table is populated --------- #
def test_watchlist_table_suppresses_empty_quiet_line():
    quotes = {"SPCX": _quote("SPCX", [28.0, 29.0])}
    tables = {"watchlist": vm.build_stock_table(["SPCX"], quotes)}
    sections = vm.build_sections(
        ["watchlist"], {}, top_story_id="us_equities", stock_tables=tables,
    )
    watch = next(s for s in sections if s.section_id == "watchlist")
    assert watch.stat_table  # table is populated
    assert watch.prose != _watchlist_quiet()
    assert "watchlist is empty" not in watch.prose.lower()


def test_movers_table_suppresses_none_flagged_quiet_line():
    quotes = {"NVDA": _quote("NVDA", [100.0, 110.0])}
    tables = {"movers": vm.build_stock_table(["NVDA"], quotes)}
    sections = vm.build_sections(
        ["movers"], {}, top_story_id="us_equities", stock_tables=tables,
    )
    movers = next(s for s in sections if s.section_id == "movers")
    assert movers.stat_table
    assert movers.prose != _movers_quiet()
    assert "no single-stock movers" not in movers.prose.lower()


def test_notes_alone_suppress_quiet_line():
    # No stat table, but per-stock notes exist -> still not the empty quiet line.
    notes = {"watchlist": ({"ticker": "SPCX", "why": "held IPO gains.",
                            "source_label": "BBG", "source_url": "https://x"},)}
    sections = vm.build_sections(
        ["watchlist"], {}, top_story_id="us_equities", stock_notes=notes,
    )
    watch = next(s for s in sections if s.section_id == "watchlist")
    assert watch.prose != _watchlist_quiet()


def test_truly_empty_watchlist_keeps_quiet_line():
    # No table, no notes -> the honest quiet line still shows (regression guard).
    sections = vm.build_sections(["watchlist"], {}, top_story_id="us_equities")
    watch = next(s for s in sections if s.section_id == "watchlist")
    assert watch.prose == _watchlist_quiet()


# --- part B: de-dup the per-stock "why" across Movers + Watchlist ---------- #
def test_dedup_why_note_prefers_movers():
    spcx_note = {"ticker": "SPCX", "why": "held IPO gains as lockup chatter eased.",
                 "source_label": "BBG: SpaceX steady", "source_url": "https://bbg/spcx"}
    notes = vm.dedup_stock_notes({
        "movers": (spcx_note,),
        "watchlist": (spcx_note,),
    })
    movers_tickers = [n["ticker"] for n in notes["movers"]]
    watch_tickers = [n["ticker"] for n in notes["watchlist"]]
    assert "SPCX" in movers_tickers          # kept in Movers
    assert "SPCX" not in watch_tickers       # dropped from Watchlist (no dup)


def test_dedup_keeps_distinct_notes():
    notes = vm.dedup_stock_notes({
        "movers": ({"ticker": "NVDA", "why": "a", "source_label": "", "source_url": ""},),
        "watchlist": ({"ticker": "SPCX", "why": "b", "source_label": "", "source_url": ""},),
    })
    assert [n["ticker"] for n in notes["movers"]] == ["NVDA"]
    assert [n["ticker"] for n in notes["watchlist"]] == ["SPCX"]
