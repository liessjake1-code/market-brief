"""Phase 7: view-model assembly — glance rows, section order, honest fallbacks."""

from __future__ import annotations

from render import viewmodel as vm
from sources.quality import Field, Source


def _fields() -> dict[str, Field]:
    keys = ("sp500", "nasdaq", "dow", "russell", "ust10y", "ust2y", "dxy", "wti", "gold", "vix", "btc", "eth")
    return {k: Field(k, 100.0, Source.YFINANCE) for k in keys}


def test_glance_has_five_figure_rows_no_live_row():
    # The redesign promotes the live "This morning" row out of the glance into the
    # fenced live zone; the glance is now exactly the five settled figure rows.
    rows = vm.build_glance_rows(_fields(), {})
    assert len(rows) == 5
    assert [r.category for r in rows] == [
        "Markets", "Rates and dollar", "Commodities", "Crypto", "Volatility"
    ]
    assert not any(r.is_live for r in rows)


def test_glance_markets_row_links_figures():
    rows = vm.build_glance_rows(_fields(), {})
    markets = next(r for r in rows if r.category == "Markets")
    assert all(c.url for c in markets.figures)
    assert any("GSPC" in c.url for c in markets.figures)


def test_glance_figures_carry_direction():
    rows = vm.build_glance_rows(_fields(), {}, directions={"sp500": "up", "dow": "down"})
    markets = next(r for r in rows if r.category == "Markets")
    by_label = {c.label: c.direction for c in markets.figures}
    assert by_label["S&P"] == "up"
    assert by_label["Dow"] == "down"
    assert by_label["Nasdaq"] == "flat"  # unspecified defaults to flat


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


def test_what_to_watch_skipped_as_body_section():
    # Rendered once by the dedicated forward block, never as a body section (fix #3).
    order = ["us_equities", "what_to_watch_today", "movers"]
    sections = vm.build_sections(order, {}, top_story_id="us_equities")
    assert all(s.section_id != "what_to_watch_today" for s in sections)
    assert [s.section_id for s in sections] == ["us_equities", "movers"]


def test_sections_carry_resolved_citations():
    cited = {"us_equities": ({"title": "Reuters: Stocks rise", "url": "https://reuters.com/x"},)}
    sections = vm.build_sections(["us_equities"], {"us_equities": "Up on AI."},
                                 top_story_id="us_equities", cited_by_section=cited)
    src = sections[0].sources
    assert src == ({"label": "Reuters: Stocks rise", "url": "https://reuters.com/x"},)


def test_empty_citation_yields_no_source_label():
    sections = vm.build_sections(["commodities"], {"commodities": "Oil quiet."},
                                 top_story_id="us_equities",
                                 cited_by_section={"commodities": ()})
    assert sections[0].sources == ()


def test_hbars_only_on_top_story_sparklines_only_on_watchlist():
    bars, maxabs = vm.build_hbars({"S&P": 0.4, "Russell": -1.2})
    sparks = vm.build_sparklines({"SPCX": [3, 4, 5]})
    order = ["us_equities", "watchlist", "movers"]
    sections = vm.build_sections(order, {}, top_story_id="us_equities",
                                 hbars=bars, hbar_maxabs=maxabs, sparklines=sparks)
    by_id = {s.section_id: s for s in sections}
    assert by_id["us_equities"].hbars == bars
    assert by_id["movers"].hbars == ()           # only the Top Story gets the bar
    assert by_id["watchlist"].sparklines == sparks
    assert by_id["us_equities"].sparklines == ()  # only watchlist gets sparklines


def test_build_hbars_shares_one_scale():
    bars, maxabs = vm.build_hbars({"A": 0.4, "B": -1.2, "C": None})
    assert maxabs == 1.2
    assert {b.label for b in bars} == {"A", "B"}  # None dropped


def test_section_charts_attach_by_section():
    charts = {"commodities": {"cid": "chart_oil", "caption": "yfinance CL=F",
                              "caption_url": "https://x", "takeaway": "Oil eased."}}
    sections = vm.build_sections(["commodities"], {}, top_story_id="us_equities",
                                 section_charts=charts)
    assert sections[0].chart_cid == "chart_oil"
    assert sections[0].chart_caption == "yfinance CL=F"
    assert sections[0].chart_takeaway == "Oil eased."


def _ramp(n, start, step):
    return [round(start + step * i, 4) for i in range(n)]


def test_build_stat_tables_per_section():
    values = {"sp500": 6431.0, "nasdaq": 21054.0, "dow": 44210.0, "russell": 2318.0}
    histories = {k: _ramp(22, v - 100, 5) for k, v in values.items()}
    tables = vm.build_stat_tables(values, histories)
    eq = tables["us_equities"]
    assert len(eq) == 4
    labels = [r.label for r in eq]
    assert "S&P 500" in labels
    # Each row carries a session/week/month cell.
    assert eq[0].session is not None and eq[0].week is not None and eq[0].month is not None


def test_rates_table_includes_spread_row():
    values = {"ust10y": 4.43, "ust2y": 4.05, "dxy": 100.8}
    histories = {
        "ust10y": _ramp(22, 4.20, 0.01),
        "ust2y": _ramp(22, 4.00, 0.002),
        "dxy": _ramp(22, 99.5, 0.06),
    }
    tables = vm.build_stat_tables(values, histories)
    labels = [r.label for r in tables["rates_and_dollar"]]
    assert "2s10s spread" in labels
    # Spread row sits after the two yields, before DXY.
    assert labels.index("2s10s spread") < labels.index("US Dollar Index")
    spread_row = next(r for r in tables["rates_and_dollar"] if r.label == "2s10s spread")
    assert "bps" in spread_row.level


def test_stat_table_renders_in_section(tmp_path):
    # The stat table reaches the SectionView and is exposed for the template.
    values = {"wti": 74.0, "gold": 4247.0, "copper": 4.4}
    histories = {k: _ramp(22, v - 5, 0.2) for k, v in values.items()}
    tables = vm.build_stat_tables(values, histories)
    sections = vm.build_sections(["commodities"], {}, top_story_id="us_equities",
                                 stat_tables=tables)
    assert len(sections[0].stat_table) == 3  # WTI, Gold, Copper


def test_rates_table_excludes_monthly_macro_series():
    # CPI/PCE/Fed funds are monthly -> NOT in the session/week/month change table.
    values = {"ust10y": 4.43, "ust2y": 4.05, "dxy": 100.8, "hy_spread": 2.63,
              "cpi_yoy": 4.17, "pce_yoy": 3.77, "fed_funds": 3.63}
    histories = {k: _ramp(22, v - 0.1, 0.01) for k, v in values.items()}
    tables = vm.build_stat_tables(values, histories)
    labels = [r.label for r in tables["rates_and_dollar"]]
    for monthly_label in ("CPI inflation (YoY)", "PCE inflation (YoY)", "Fed funds rate"):
        assert monthly_label not in labels, monthly_label
    # The daily series (incl. HY spread + the synthetic spread) still appear.
    assert "High-yield credit spread" in labels
    assert "2s10s spread" in labels


def test_macro_strip_carries_monthly_readings():
    values = {"cpi_yoy": 4.17, "pce_yoy": 3.77, "fed_funds": 3.63}
    strips = vm.build_macro_strips(values)
    rates = strips["rates_and_dollar"]
    labels = [r.label for r in rates]
    assert labels == ["CPI inflation (YoY)", "PCE inflation (YoY)", "Fed funds rate"]
    # Levels are formatted as rate percentages.
    by_label = {r.label: r.value for r in rates}
    assert by_label["CPI inflation (YoY)"] == "4.17%"
    assert by_label["Fed funds rate"] == "3.63%"


def test_macro_strip_skips_missing_value():
    # A metric with no current value is dropped (nothing to show honestly).
    strips = vm.build_macro_strips({"cpi_yoy": 4.17, "pce_yoy": None, "fed_funds": 3.63})
    labels = [r.label for r in strips["rates_and_dollar"]]
    assert "PCE inflation (YoY)" not in labels
    assert labels == ["CPI inflation (YoY)", "Fed funds rate"]


def test_macro_strip_reaches_section_view():
    values = {"cpi_yoy": 4.17, "pce_yoy": 3.77, "fed_funds": 3.63}
    strips = vm.build_macro_strips(values)
    sections = vm.build_sections(["rates_and_dollar"], {}, top_story_id="us_equities",
                                 macro_strips=strips)
    assert len(sections[0].macro_strip) == 3
