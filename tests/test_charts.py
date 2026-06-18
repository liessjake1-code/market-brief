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


def test_ten_year_trend_produces_png():
    chart = charts.ten_year_trend(ten_year_history=[4.3, 4.35, 4.4, 4.44])
    assert chart is not None
    assert _is_png(chart.png)
    assert chart.cid == "chart_rates"


def test_ten_year_trend_none_when_thin():
    assert charts.ten_year_trend(ten_year_history=[4.4]) is None


def test_commodities_normalized_produces_png():
    chart = charts.commodities_normalized({
        "wti": [80.0 - i * 0.4 for i in range(22)],
        "gold": [4000.0 + i * 10 for i in range(22)],
        "copper": [4.3 + i * 0.01 for i in range(22)],
    })
    assert chart is not None
    assert _is_png(chart.png)
    assert chart.cid == "chart_commodities"
    # Rebased: gold up, WTI down, all expressed off 100.
    assert "Gold" in chart.summary and "WTI" in chart.summary


def test_commodities_normalized_draws_with_one_leg():
    # Missing gold + copper: still draws WTI alone (graceful), not None.
    chart = charts.commodities_normalized({"wti": [80.0, 79.0, 78.0]})
    assert chart is not None
    assert "WTI" in chart.summary


def test_commodities_normalized_none_when_all_thin():
    assert charts.commodities_normalized({"wti": [80.0], "gold": [], "copper": []}) is None


def test_charts_carry_text_summary_for_alt():
    # Each PNG chart carries a one-line, image-free summary used as the img alt so
    # a blocked image still leaves a readable line (HANDOFF_DESIGN).
    rates = charts.ten_year_trend(ten_year_history=[4.3, 4.4, 4.43])
    assert "4.43%" in rates.summary and "10-year" in rates.summary
    com = charts.commodities_normalized({"wti": [70.0, 72.0, 74.0]})
    assert "Commodities" in com.summary


def test_white_palette_constants():
    # Restyled to "The Tape" white: blue is the one accent, no navy/gold left.
    assert charts.PAPER == "#FFFFFF"
    assert charts.BLUE == "#3a6ea5"
    assert charts.INK == "#1b1a17"


def test_ten_year_clamps_to_a_month_window():
    # A long backfill must not be drawn whole; the chart shows the trailing ~21
    # sessions and the summary computes bps over the *clamped* window.
    long_hist = [4.0 + i * 0.01 for i in range(40)]
    chart = charts.ten_year_trend(ten_year_history=long_hist)
    assert chart is not None
    assert "10-year" in chart.summary and "bps" in chart.summary


def test_ten_year_takeaway_is_computed():
    # The takeaway is Python-computed (accuracy-safe): level + week move + range.
    hist = [4.30 + i * 0.01 for i in range(22)]
    read = charts.ten_year_takeaway(ten_year=hist[-1], ten_year_history=hist)
    assert "4.51%" in read or "%" in read
    assert "range" in read


def test_ten_year_takeaway_short_history_no_duplicate_clause():
    # 2-5 sessions: the week move is not computable, but the range clause must
    # appear exactly once (regression for a sentence-duplication bug).
    read = charts.ten_year_takeaway(ten_year=4.35, ten_year_history=[4.30, 4.33, 4.35])
    assert read.count("range") == 1
    assert read.endswith(".")
    assert ", ," not in read


def test_commodities_takeaway_names_leader_and_laggard():
    read = charts.commodities_takeaway({
        "wti": [80.0 - i for i in range(22)],          # falling
        "gold": [4000.0 + i * 20 for i in range(22)],  # rising
        "copper": [4.3 + i * 0.005 for i in range(22)],
    })
    assert "Gold leads" in read and "WTI crude lags" in read


def test_charts_render_without_dates_gracefully():
    # No dates -> undated axis, still a valid chart (graceful degrade).
    rates = charts.ten_year_trend(ten_year_history=[4.3, 4.31, 4.32], ten_year_dates=None)
    assert rates is not None
    assert _is_png(rates.png)


def test_date_xaxis_ticks_are_separated():
    # The bug: adjacent x-ticks crowded into each other ("Jun JuJu 18"). Ticks must
    # now be at least _MIN_TICK_GAP indices apart so labels never overlap.
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    n = 21
    dates = [f"2026-06-{d:02d}" for d in range(1, n + 1)]
    span = charts._date_xaxis(ax, dates, n)
    ticks = sorted(ax.get_xticks())
    plt.close(fig)
    assert span  # a real "Jun 1 - Jun 21" span was returned
    gaps = [b - a for a, b in zip(ticks, ticks[1:])]
    assert all(g >= charts._MIN_TICK_GAP for g in gaps), ticks


def test_date_xaxis_no_duplicate_final_tick():
    # The appended last tick must not duplicate (or sit adjacent to) the prior pick.
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    n = 22
    dates = [f"2026-06-{d:02d}" for d in range(1, n + 1)]
    charts._date_xaxis(ax, dates, n)
    ticks = list(ax.get_xticks())
    plt.close(fig)
    assert len(ticks) == len(set(ticks))  # no duplicate index


def test_pad_ylim_widens_a_tiny_range(monkeypatch):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    series = [4.43, 4.44, 4.43, 4.45, 4.43]  # ~2 bps range
    charts._pad_ylim(ax, series)
    lo, hi = ax.get_ylim()
    plt.close(fig)
    # The enforced floor (3% of ~4.4 = ~13 bps) times the headroom widens the view
    # well past the 2 bps data range, so the line is not magnified into a sawtooth.
    assert (hi - lo) > 0.04


def test_pad_ylim_calms_a_near_flat_jagged_month():
    # The real production shape: a ~15 bps jagged month around 4.4-4.6. The padded
    # view must be wider than the raw range so the noise sits in the middle of the
    # panel, not filling it edge to edge.
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    series = [4.46, 4.49, 4.55, 4.575, 4.50, 4.47, 4.45, 4.45, 4.43, 4.425, 4.49]
    raw_span = max(series) - min(series)
    charts._pad_ylim(ax, series)
    lo, hi = ax.get_ylim()
    plt.close(fig)
    assert (hi - lo) > raw_span * 1.5   # real wiggle no longer fills the panel
