"""Tests for charts.py (port+restyle) and chart_set.py (no-fabrication contract)."""
import pytest
from datetime import date

from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode
from marketbrief.render.charts import (
    Chart,
    _date_xaxis,
    _fmt_date,
    _pad_ylim,
    _range_position,
    _rebased,
    _titled,
    commodities_normalized,
    commodities_takeaway,
    index_change_bar,
    ten_year_takeaway,
    ten_year_trend,
)
from marketbrief.render.chart_set import build_charts

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _ctx(watchlist=None):
    return BriefContext(
        run_date=date(2026, 6, 20),
        mode=RunMode.NO_SEND,
        config=Config(watchlist=watchlist or []),
    )


# ---------------------------------------------------------------------------
# index_change_bar
# ---------------------------------------------------------------------------

def test_index_change_bar_returns_png():
    chart = index_change_bar({"S&P": 0.4, "Nasdaq": 0.8, "Dow": 0.1, "Russell": -0.2})
    assert isinstance(chart, Chart)
    assert chart.png[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes


def test_index_change_bar_returns_none_when_empty():
    assert index_change_bar({}) is None


def test_index_change_bar_returns_none_when_all_none():
    assert index_change_bar({"S&P": None, "Dow": None}) is None


# ---------------------------------------------------------------------------
# _fmt_date
# ---------------------------------------------------------------------------

def test_fmt_date_valid():
    assert _fmt_date("2026-05-20") == "May 20"


def test_fmt_date_invalid_returns_empty():
    assert _fmt_date("not-a-date") == ""


def test_fmt_date_empty_string_returns_empty():
    assert _fmt_date("") == ""


def test_fmt_date_none_returns_empty():
    assert _fmt_date(None) == ""  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _date_xaxis
# ---------------------------------------------------------------------------

def test_date_xaxis_with_dates():
    """Axis is labeled when valid dates are present."""
    fig, ax = plt.subplots()
    dates = [f"2026-06-{i+1:02d}" for i in range(10)]
    span = _date_xaxis(ax, dates, 10)
    assert "Jun" in span
    plt.close(fig)


def test_date_xaxis_no_dates_returns_empty_span():
    """When dates list is empty, axis clears ticks and span is ''."""
    fig, ax = plt.subplots()
    span = _date_xaxis(ax, [], 5)
    assert span == ""
    plt.close(fig)


def test_date_xaxis_single_date():
    """A single valid date produces a non-empty span."""
    fig, ax = plt.subplots()
    span = _date_xaxis(ax, ["2026-06-20"], 1)
    assert "Jun 20" in span
    plt.close(fig)


# ---------------------------------------------------------------------------
# _titled
# ---------------------------------------------------------------------------

def test_titled_with_subtitle():
    """_titled should not raise when subtitle is non-empty."""
    fig, ax = plt.subplots()
    _titled(ax, "My Title", "subtitle text")
    plt.close(fig)


def test_titled_without_subtitle():
    """_titled should not raise when subtitle is empty."""
    fig, ax = plt.subplots()
    _titled(ax, "My Title", "")
    plt.close(fig)


# ---------------------------------------------------------------------------
# _pad_ylim
# ---------------------------------------------------------------------------

def test_pad_ylim_expands_tiny_range():
    """A flat series should still produce a visible y-span."""
    fig, ax = plt.subplots()
    flat = [4.4] * 10
    _pad_ylim(ax, flat)
    lo, hi = ax.get_ylim()
    assert hi > lo
    plt.close(fig)


def test_pad_ylim_realistic_range():
    """Normal yield-like series produces limits wider than raw range."""
    fig, ax = plt.subplots()
    series = [4.2 + 0.01 * i for i in range(21)]
    _pad_ylim(ax, series)
    lo, hi = ax.get_ylim()
    assert lo < min(series)
    assert hi > max(series)
    plt.close(fig)


# ---------------------------------------------------------------------------
# _rebased
# ---------------------------------------------------------------------------

def test_rebased_normal():
    rebased = _rebased([80.0, 90.0, 100.0])
    assert rebased is not None
    assert rebased[0] == pytest.approx(100.0)


def test_rebased_too_short_returns_none():
    assert _rebased([50.0]) is None


def test_rebased_zero_base_returns_none():
    assert _rebased([0.0, 1.0]) is None


def test_rebased_with_none_values():
    """None values are stripped before rebasing."""
    rebased = _rebased([None, 80.0, 100.0])  # type: ignore[list-item]
    assert rebased is not None
    assert rebased[0] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# ten_year_trend
# ---------------------------------------------------------------------------

def test_ten_year_trend_returns_png_with_history():
    history = [4.2 + 0.01 * i for i in range(25)]
    chart = ten_year_trend(ten_year_history=history)
    assert chart is not None
    assert chart.png[:8] == b"\x89PNG\r\n\x1a\n"
    assert "10-year" in chart.summary


def test_ten_year_trend_with_dates():
    history = [4.3] * 25
    dates = [f"2026-05-{i+1:02d}" for i in range(25)]
    chart = ten_year_trend(ten_year_history=history, ten_year_dates=dates)
    assert chart is not None


def test_ten_year_trend_too_short_returns_none():
    assert ten_year_trend(ten_year_history=[4.2]) is None


def test_ten_year_trend_empty_returns_none():
    assert ten_year_trend(ten_year_history=[]) is None


# ---------------------------------------------------------------------------
# _range_position
# ---------------------------------------------------------------------------

def test_range_position_near_top():
    assert _range_position([1.0, 2.0, 3.0, 4.0, 4.8]) == "near the top of"


def test_range_position_near_bottom():
    assert _range_position([4.8, 1.0, 1.2, 1.1, 1.05]) == "near the bottom of"


def test_range_position_middle():
    assert _range_position([1.0, 2.0, 3.0, 4.0, 2.5]) == "in the middle of"


def test_range_position_flat():
    assert _range_position([3.0, 3.0, 3.0]) == "flat across"


# ---------------------------------------------------------------------------
# ten_year_takeaway
# ---------------------------------------------------------------------------

def test_ten_year_takeaway_normal():
    history = [4.2 + 0.01 * i for i in range(25)]
    result = ten_year_takeaway(ten_year=history[-1], ten_year_history=history)
    assert "4." in result
    assert result.endswith(".")


def test_ten_year_takeaway_little_changed():
    """When week move < 0.5 bps, uses 'little changed' wording."""
    history = [4.4] * 25
    result = ten_year_takeaway(ten_year=4.4, ten_year_history=history)
    assert "little changed" in result


def test_ten_year_takeaway_missing_level_returns_empty():
    history = [4.2] * 25
    assert ten_year_takeaway(ten_year=None, ten_year_history=history) == ""


def test_ten_year_takeaway_too_short_returns_empty():
    assert ten_year_takeaway(ten_year=4.2, ten_year_history=[4.2]) == ""


# ---------------------------------------------------------------------------
# commodities_normalized
# ---------------------------------------------------------------------------

def _month_history(base: float) -> list[float]:
    return [base + 0.1 * i for i in range(25)]


def test_commodities_normalized_returns_png():
    histories = {
        "wti": _month_history(70.0),
        "gold": _month_history(2300.0),
        "copper": _month_history(4.0),
    }
    chart = commodities_normalized(histories)
    assert chart is not None
    assert chart.png[:8] == b"\x89PNG\r\n\x1a\n"
    assert "100" in chart.summary


def test_commodities_normalized_with_dates():
    histories = {"wti": _month_history(70.0)}
    dates = {"wti": [f"2026-05-{i+1:02d}" for i in range(25)]}
    chart = commodities_normalized(histories, dates=dates)
    assert chart is not None


def test_commodities_normalized_no_usable_data_returns_none():
    chart = commodities_normalized({})
    assert chart is None


def test_commodities_normalized_single_zero_returns_none():
    """A single-point history (too short) means no leg can be drawn."""
    chart = commodities_normalized({"wti": [0.0], "gold": [0.0], "copper": [0.0]})
    assert chart is None


# ---------------------------------------------------------------------------
# commodities_takeaway
# ---------------------------------------------------------------------------

def test_commodities_takeaway_with_all_legs():
    histories = {
        "wti": _month_history(70.0),
        "gold": _month_history(2300.0),
        "copper": _month_history(4.0),
    }
    result = commodities_takeaway(histories)
    assert "WTI" in result
    assert "Gold" in result
    assert result.endswith(".")


def test_commodities_takeaway_empty_returns_empty():
    assert commodities_takeaway({}) == ""


def test_commodities_takeaway_single_leg_no_leader_laggard():
    """With one leg there is no leader/laggard suffix."""
    histories = {"wti": _month_history(70.0)}
    result = commodities_takeaway(histories)
    assert "WTI" in result
    assert "leads" not in result


# ---------------------------------------------------------------------------
# build_charts integration
# ---------------------------------------------------------------------------

def test_build_charts_no_fabrication_when_no_data():
    png_by_cid, refs_by_section = build_charts(_ctx())
    # No same-day change data yet -> equities chart is skipped (no fabrication).
    assert refs_by_section.get("us_equities", []) == []
    # Every ChartRef that DOES exist must have a matching png entry.
    for refs in refs_by_section.values():
        for r in refs:
            assert r.cid in png_by_cid


def test_sparklines_off_when_watchlist_empty():
    _, refs = build_charts(_ctx([]))
    assert "watchlist" not in refs or refs["watchlist"] == []
