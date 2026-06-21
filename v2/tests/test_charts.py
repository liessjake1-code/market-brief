"""Tests for charts.py (port+restyle) and chart_set.py (no-fabrication contract)."""
from datetime import date

from marketbrief.core.config import Config
from marketbrief.core.context import BriefContext
from marketbrief.core.enums import RunMode
from marketbrief.render.charts import index_change_bar, Chart
from marketbrief.render.chart_set import build_charts


def _ctx(watchlist=None):
    return BriefContext(
        run_date=date(2026, 6, 20),
        mode=RunMode.NO_SEND,
        config=Config(watchlist=watchlist or []),
    )


def test_index_change_bar_returns_png():
    chart = index_change_bar({"S&P": 0.4, "Nasdaq": 0.8, "Dow": 0.1, "Russell": -0.2})
    assert isinstance(chart, Chart)
    assert chart.png[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes


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
