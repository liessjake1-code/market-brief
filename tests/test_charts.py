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


def test_wti_clamps_to_a_month_window():
    # A long backfill (e.g. 108 -> 74 over 25 sessions) must not be drawn whole;
    # the chart shows the trailing ~21 sessions so it reads as a month, not a crash.
    long_hist = [108.0 - i for i in range(40)]  # 40 descending sessions
    chart = charts.wti_trend(long_hist)
    assert chart is not None
    # The summary computes pct over the *clamped* window, not the full 40 sessions.
    # Full 40-session drop would be ~36%; a 21-session window is ~ -20/87 ~ -23%.
    assert "down" in chart.summary
    assert "WTI" in chart.summary


def test_charts_label_axes_and_dates():
    dates = [f"2026-05-{d:02d}" for d in range(1, 22)]  # 21 dated sessions
    series = [70.0 + i * 0.5 for i in range(21)]
    oil = charts.wti_trend(series, dates=dates)
    # The summary frames the window and the move from the first point.
    assert "past month" in oil.summary
    assert "from $70" in oil.summary
    rates = charts.yield_curve_and_trend(
        ust2y=4.05, ust10y=4.43, ten_year_history=series, ten_year_dates=dates)
    assert rates is not None and len(rates.png) > 100


def test_charts_render_without_dates_gracefully():
    # No dates -> undated axis, still a valid chart (graceful degrade).
    oil = charts.wti_trend([70.0, 71.0, 72.0], dates=None)
    assert oil is not None
    assert _is_png(oil.png)


def test_pad_ylim_widens_a_tiny_range(monkeypatch):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    series = [4.43, 4.44, 4.43, 4.45, 4.43]  # ~2 bps range
    charts._pad_ylim(ax, series)
    lo, hi = ax.get_ylim()
    plt.close(fig)
    # The enforced floor (1% of ~4.4 = ~4.4 bps) widens the view well past the
    # 2 bps data range, so the line is not magnified into a sawtooth.
    assert (hi - lo) > 0.04
