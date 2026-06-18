"""Phase 7: charts produce non-empty PNG bytes and degrade on thin data (roadmap §7)."""

from __future__ import annotations

from render import charts


def _is_png(data: bytes) -> bool:
    return data[:8] == b"\x89PNG\r\n\x1a\n"


def test_index_bar_produces_png():
    chart = charts.index_change_bar({"S&P 500": 0.8, "Nasdaq": 1.2, "Dow": -0.3, "Russell": 0.1})
    assert chart is not None
    assert _is_png(chart.png) and len(chart.png) > 100
    assert chart.cid == "chart_index"


def test_index_bar_empty_returns_none():
    assert charts.index_change_bar({}) is None


def test_yield_curve_and_trend_produces_png():
    chart = charts.yield_curve_and_trend(
        ust2y=4.1, ust10y=4.44, ten_year_history=[4.3, 4.35, 4.4, 4.44],
    )
    assert chart is not None
    assert _is_png(chart.png)


def test_yield_curve_none_when_no_data():
    assert charts.yield_curve_and_trend(ust2y=None, ust10y=None, ten_year_history=[]) is None


def test_wti_trend_produces_png():
    chart = charts.wti_trend([74.1, 75.0, 76.2, 75.8, 77.0])
    assert chart is not None
    assert _is_png(chart.png)
    assert chart.cid == "chart_oil"


def test_wti_trend_thin_data_returns_none():
    assert charts.wti_trend([76.0]) is None


def test_charts_carry_text_summary_for_alt():
    # Each PNG chart carries a one-line, image-free summary used as the img alt so
    # a blocked image still leaves a readable line (HANDOFF_DESIGN).
    rates = charts.yield_curve_and_trend(ust2y=4.05, ust10y=4.43, ten_year_history=[4.3, 4.4, 4.43])
    assert "4.43%" in rates.summary and "2s10s" in rates.summary
    oil = charts.wti_trend([70.0, 72.0, 74.0])
    assert "WTI" in oil.summary and "$74" in oil.summary


def test_white_palette_constants():
    # Restyled to "The Tape" white: blue is the one accent, no navy/gold left.
    assert charts.PAPER == "#FFFFFF"
    assert charts.BLUE == "#3a6ea5"
    assert charts.INK == "#1b1a17"
