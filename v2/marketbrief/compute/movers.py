"""Movers compute stage (PURE, no I/O, no model).

Turns a universe of daily-close series into a ranked MoverBoard: the top winners
and losers over the day, week, and month windows. Every percent figure is computed
here in Python from the closes (spec §1), so the board can never carry a number the
model invented. A name with too little history for a window simply does not appear
in that window (no fabrication); a window with no directional movers renders empty.
"""
from __future__ import annotations

from marketbrief.core.enums import Direction
from marketbrief.core.models import MoverRow, MoverPeriod, MoverBoard
from marketbrief.render.source_links import yahoo_ticker_url, favicon_url, safe_url
from marketbrief.sections._tickers import domain_for

# Trailing windows in trading sessions: 1 day, ~1 week (5 sessions), ~1 month (21).
_WINDOWS: tuple[tuple[str, int], ...] = (("Day", 1), ("Week", 5), ("Month", 21))
_TOP_N = 3
# Below this absolute percent move a name is treated as flat (not a real winner or
# loser), so a board of barely-moved names renders empty rather than noisy.
_FLAT_EPS = 0.05


def _pct_return(closes: list[float], lookback: int) -> float | None:
    """Percent change from `lookback` sessions ago to the latest close.

    Returns None when there is not enough history or the base price is zero, so a
    thin or unusable series contributes nothing rather than a bogus number.
    """
    if len(closes) <= lookback:
        return None
    base = closes[-1 - lookback]
    if not base:
        return None
    return (closes[-1] - base) / base * 100.0


def _direction(pct: float) -> Direction:
    if pct > _FLAT_EPS:
        return Direction.UP
    if pct < -_FLAT_EPS:
        return Direction.DOWN
    return Direction.FLAT


def _row(ticker: str, pct: float) -> MoverRow:
    return MoverRow(
        ticker=ticker,
        favicon_url=favicon_url(domain_for(ticker)),
        value_str=f"{pct:+.1f}%",
        direction=_direction(pct),
        why="",
        source_url=safe_url(yahoo_ticker_url(ticker)),
    )


def _period(label: str, lookback: int, closes_by_ticker: dict[str, list[float]]) -> MoverPeriod:
    moves: list[tuple[str, float]] = []
    for ticker, closes in closes_by_ticker.items():
        pct = _pct_return(closes, lookback)
        if pct is not None:
            moves.append((ticker, pct))
    winners = [(t, p) for t, p in moves if p > _FLAT_EPS]
    losers = [(t, p) for t, p in moves if p < -_FLAT_EPS]
    winners.sort(key=lambda m: m[1], reverse=True)   # biggest gain first
    losers.sort(key=lambda m: m[1])                  # biggest loss first
    return MoverPeriod(
        label=label,
        winners=[_row(t, p) for t, p in winners[:_TOP_N]],
        losers=[_row(t, p) for t, p in losers[:_TOP_N]],
    )


def compute_movers(closes_by_ticker: dict[str, list[float]]) -> MoverBoard:
    """Build the day/week/month winners-and-losers board from universe closes.

    Args:
        closes_by_ticker: mapping of ticker -> daily closes, oldest first. A name
            with fewer closes than a window needs is skipped for that window.

    Returns:
        A MoverBoard with one MoverPeriod per window. Empty input, all-flat input,
        or thin history all yield a board whose `has_rows` is False, so the section
        and template render nothing rather than fabricating movers.
    """
    periods = [_period(label, lookback, closes_by_ticker) for label, lookback in _WINDOWS]
    return MoverBoard(periods=periods)
