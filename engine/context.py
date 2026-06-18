"""Trailing time-context per metric: week and month change (redesign).

A single daily move says little on its own ("S&P +0.1%"); the same number with
its week and month context is genuinely informative ("S&P +0.1% today, +1.8% on
the week, near a 20-day high"). This module turns rolling history (the same
closes the diff line and charts already use) into those trailing changes.

Pure: takes a history list (most-recent-last), returns derived numbers. No
network, no state access, no model. Yields are reported in basis points, every
other metric in percent, matching the rest of the engine (engine/metrics).

These derived figures are computed once and used two ways (spec §6.2): surfaced
directly in the templated/computed lines and the glance, AND added to the model's
per-section input set so prose may cite them (the number validator then accepts
"up about 1.8% on the week" because 1.8 is a supplied input).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from engine.metrics import is_yield

# Trailing windows in trading sessions. A week is 5 sessions back; a month is ~21.
WEEK_SESSIONS = 5
MONTH_SESSIONS = 21


@dataclass(frozen=True)
class TimeContext:
    """Trailing changes for one metric, in the metric's native unit (pct or bps).

    Each field is None when history is too short to compute it honestly (the brief
    degrades to silence rather than guessing, spec §5.5).
    """

    week_change: Optional[float] = None    # pct, or bps for yields
    month_change: Optional[float] = None

    @property
    def has_any(self) -> bool:
        return self.week_change is not None or self.month_change is not None


def _change(history: list[float], sessions: int, metric: str) -> Optional[float]:
    """Change from `sessions` sessions ago to the latest close, in native units.

    Needs at least `sessions + 1` closes to look back a full window. Yields use an
    absolute basis-point delta (a difference of yields); everything else uses a
    percentage change. Returns None on thin history.
    """
    clean = [v for v in history if v is not None]
    if len(clean) < sessions + 1:
        return None
    latest = clean[-1]
    past = clean[-(sessions + 1)]
    if is_yield(metric):
        return (latest - past) * 100.0  # yields are in percent; *100 -> basis points
    if not past:
        return None
    return (latest - past) / past * 100.0


def time_context(history: list[float], metric: str) -> TimeContext:
    """Week and month trailing change for a metric from its rolling history."""
    return TimeContext(
        week_change=_change(history, WEEK_SESSIONS, metric),
        month_change=_change(history, MONTH_SESSIONS, metric),
    )


def context_clause(ctx: TimeContext, metric: str) -> str:
    """A short, cause-free clause: ', up 1.8% on the week and 4.0% on the month'.

    Empty when no window is computable. Uses 'flat' for a negligible move so the
    line never claims a direction it does not have.
    """
    parts: list[str] = []
    for change, label in ((ctx.week_change, "week"), (ctx.month_change, "month")):
        if change is None:
            continue
        parts.append(f"{_signed(change, metric)} on the {label}")
    if not parts:
        return ""
    return ", " + " and ".join(parts)


def _signed(change: float, metric: str) -> str:
    if is_yield(metric):
        if abs(change) < 0.5:
            return "flat"
        return f"{'up' if change > 0 else 'down'} {abs(change):.0f} bps"
    if abs(change) < 0.05:
        return "flat"
    return f"{'up' if change > 0 else 'down'} {abs(change):.1f}%"
