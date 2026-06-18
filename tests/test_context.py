"""Redesign: trailing week/month time-context from rolling history."""

from __future__ import annotations

from engine import context as ctx


def test_week_and_month_change_percent():
    # 22 ascending closes: week = last vs 6-ago, month = last vs 22-ago.
    history = [100.0 + i for i in range(22)]  # 100 .. 121
    c = ctx.time_context(history, "sp500")
    # week: (121 - 116) / 116 * 100
    assert round(c.week_change, 2) == round((121 - 116) / 116 * 100, 2)
    # month: (121 - 100) / 100 * 100 = 21.0 (21 sessions back from the last index)
    assert round(c.month_change, 1) == 21.0


def test_yields_report_in_basis_points():
    history = [4.00 + 0.01 * i for i in range(10)]  # 4.00 .. 4.09
    c = ctx.time_context(history, "ust10y")
    # week = (4.09 - 4.04) * 100 = 5 bps
    assert round(c.week_change, 0) == 5.0


def test_thin_history_degrades_to_none():
    c = ctx.time_context([100.0, 101.0], "sp500")
    assert c.week_change is None
    assert c.month_change is None
    assert not c.has_any


def test_context_clause_reads_week_and_month():
    history = [100.0 + i for i in range(22)]
    clause = ctx.context_clause(ctx.time_context(history, "sp500"), "sp500")
    assert "on the week" in clause
    assert "on the month" in clause
    assert clause.startswith(", up")


def test_context_clause_empty_when_thin():
    assert ctx.context_clause(ctx.time_context([100.0], "sp500"), "sp500") == ""


def test_negligible_move_reads_flat_not_directional():
    # A move under the threshold must not claim a direction.
    history = [100.0] * 6 + [100.0]  # exactly flat over a week
    clause = ctx.context_clause(ctx.time_context(history, "sp500"), "sp500")
    assert "flat on the week" in clause
