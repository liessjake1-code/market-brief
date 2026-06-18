"""Phase 7: view-model assembly — glance rows, section order, honest fallbacks."""

from __future__ import annotations

from render import viewmodel as vm
from sources.quality import Field, Source


def _fields() -> dict[str, Field]:
    keys = ("sp500", "nasdaq", "dow", "russell", "ust10y", "ust2y", "dxy", "wti", "gold", "vix", "btc", "eth")
    return {k: Field(k, 100.0, Source.YFINANCE) for k in keys}


def test_glance_has_live_row_with_timestamp():
    rows = vm.build_glance_rows(
        _fields(), {}, live_label="Pre-market as of 8:25 CT",
        live_why="x", events_why="x", earnings_why="x", washington_why="x", bottom_line="x",
    )
    live = [r for r in rows if r.is_live]
    assert len(live) == 1
    assert live[0].category == "This morning"
    assert live[0].timestamp == "Pre-market as of 8:25 CT"


def test_glance_markets_row_links_figures():
    rows = vm.build_glance_rows(
        _fields(), {}, live_label="L",
        live_why="x", events_why="x", earnings_why="x", washington_why="x", bottom_line="x",
    )
    markets = next(r for r in rows if r.category == "Markets")
    assert all(c.url for c in markets.figures)
    assert any("GSPC" in c.url for c in markets.figures)


def test_sections_top_story_first_and_marked():
    order = ["commodities", "us_equities", "rates_and_dollar"]
    sections = vm.build_sections(order, {"commodities": "Oil slid on demand."},
                                 top_story_id="commodities")
    assert sections[0].section_id == "commodities"
    assert sections[0].is_top_story is True
    assert sections[1].is_top_story is False


def test_empty_section_gets_honest_one_liner():
    sections = vm.build_sections(["watchlist"], {}, top_story_id="us_equities")
    assert "config.yaml" in sections[0].prose  # the honest empty-watchlist line


def test_favicons_only_on_movers_and_watchlist():
    order = ["us_equities", "movers", "watchlist"]
    favicon_tickers = {"movers": [{"ticker": "NVDA", "domain": "nvidia.com"}], "watchlist": []}
    sections = vm.build_sections(order, {}, top_story_id="us_equities",
                                 favicon_tickers=favicon_tickers)
    by_id = {s.section_id: s for s in sections}
    assert by_id["us_equities"].favicons == ()
    assert by_id["movers"].favicons[0]["ticker"] == "NVDA"
    assert by_id["movers"].favicons[0]["favicon"] is not None
