"""Fix #4 — Earnings on Deck reconciles with the forward "What to Watch" block.

The delivered Jun 18 PDF showed "What to Watch" listing earnings (ACN, KR) while
the "Earnings on Deck" body section said "No notable earnings flagged before the
open." Both render paths read the SAME cal.earnings; they must agree. The body
section's prose is now built from cal.earnings (brief._earnings_on_deck_line), so
when the calendar has earnings the section names them instead of the stale quiet
line; when it has none it stays honestly empty.
"""

from __future__ import annotations

import brief as B
from sources.calendar import CalendarData, EarningsItem


def _cal(*earnings: EarningsItem) -> CalendarData:
    return CalendarData(events=(), earnings=tuple(earnings))


def test_line_names_pre_open_earnings_when_present():
    cal = _cal(
        EarningsItem(ticker="ACN", when="bmo"),
        EarningsItem(ticker="KR", when="bmo"),
    )
    line = B._earnings_on_deck_line(cal)
    assert "ACN" in line and "KR" in line
    # It must NOT be the stale "none flagged" quiet line.
    assert "no notable earnings" not in line.lower()
    assert "none flagged" not in line.lower()


def test_line_agrees_with_forward_block_tickers():
    # The forward block prefers pre-open (bmo) names; the body section must cover
    # the same set so the two never contradict each other.
    cal = _cal(
        EarningsItem(ticker="ACN", when="bmo"),
        EarningsItem(ticker="KR", when="bmo"),
        EarningsItem(ticker="FDX", when="amc"),
    )
    line = B._earnings_on_deck_line(cal)
    for t in ("ACN", "KR"):
        assert t in line


def test_line_empty_when_no_earnings():
    line = B._earnings_on_deck_line(_cal())
    assert line == ""  # empty -> viewmodel keeps the honest quiet line


def test_after_close_only_still_reconciles():
    # No pre-open names, only after-close: both paths fall back to the same set,
    # so the body section names them too (it must not claim "none flagged").
    cal = _cal(EarningsItem(ticker="NKE", when="amc"))
    line = B._earnings_on_deck_line(cal)
    assert "NKE" in line
    assert "none flagged" not in line.lower()
