"""Phase 7: the editorial build degrades, never crashes (spec §5.6).

A matplotlib failure must ship a chart-free degraded brief; a Jinja render failure
must fall back to flat HTML. The brief never blocks on rendering.
"""

from __future__ import annotations

from datetime import date

import pytest

import brief
from engine.metrics import METRIC_KEYS
from sources.quality import Field, Source, assess

DAY = date(2026, 6, 17)


def _report():
    fields = {k: Field(k, 100.0, Source.YFINANCE) for k in METRIC_KEYS}
    return assess(fields, degraded_stale_threshold=2, hard_floor_missing_threshold=4)


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setenv("MARKET_BRIEF_OFFLINE", "1")


def test_chart_failure_ships_chart_free_degraded(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("matplotlib down")

    monkeypatch.setattr(brief, "_build_charts", boom)
    report = _report()
    html, images = brief._build_html(
        {"charts": {}}, DAY, report, {"us_equities": "S&P firmer. tail"}, {},
    )
    assert "The Tape" in html       # the full editorial brief still renders, chart-free
    assert images == []
    assert report.degraded is True


def test_render_failure_falls_back_to_flat_html(monkeypatch):
    from render import html as html_render

    def boom(view):
        raise RuntimeError("jinja down")

    monkeypatch.setattr(html_render, "render_brief", boom)
    report = _report()
    html, images = brief._build_html(
        {"charts": {}}, DAY, report, {"us_equities": "flat line. tail"}, {},
    )
    assert "Degraded run" in html
    assert "flat line" in html
    assert report.degraded is True
