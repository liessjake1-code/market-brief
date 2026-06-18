"""Per-section stat tables: session / week / month change per metric (redesign).

The "Visuals + macro" overhaul puts a small computed stat table at the TOP of each
section, before the prose. This module turns rolling history into those rows:
for each metric, the trailing change over one session, one week (5 sessions), and
one month (~21 sessions), in the metric's native unit (percent for prices, basis
points for rate-like series).

Pure: takes history lists (most-recent-last), returns formatted rows. No network,
no state, no model. Every number is computed here in Python, so the tables are
100% accurate by construction (spec §1) — the model never writes a figure.

A change is None when history is too short to compute it honestly; the row then
shows an em dash rather than guessing (spec §5.5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from engine import context as ctx_mod
from engine.metrics import METRICS_BY_KEY, is_yield

# Session change is just the trailing one-session delta; week/month reuse context.
_SESSION = 1


@dataclass(frozen=True)
class StatCell:
    """One formatted change with its direction for green/red/neutral coloring."""

    text: str                  # "+1.8%" | "-12 bps" | "—"
    direction: str = "flat"    # "up" | "down" | "flat"

    @property
    def is_blank(self) -> bool:
        return self.text == "—"


@dataclass(frozen=True)
class StatRow:
    """A metric label, its current level, and its session/week/month changes."""

    label: str
    level: str                 # formatted current value, e.g. "6,431" or "4.43%"
    session: StatCell
    week: StatCell
    month: StatCell


@dataclass(frozen=True)
class StatTable:
    """The stat table for one section: a header note plus its metric rows."""

    rows: tuple[StatRow, ...]

    @property
    def is_empty(self) -> bool:
        return not self.rows


def _change(history: list[float], sessions: int, metric: str) -> Optional[float]:
    """Trailing change over `sessions` sessions in native units (pct or bps)."""
    clean = [v for v in history if v is not None]
    if len(clean) < sessions + 1:
        return None
    latest, past = clean[-1], clean[-(sessions + 1)]
    if is_yield(metric):
        return (latest - past) * 100.0   # delta of a percent level -> basis points
    if not past:
        return None
    return (latest - past) / past * 100.0


def _cell(change: Optional[float], metric: str) -> StatCell:
    """Format a change into a signed cell with direction. None -> blank em dash."""
    if change is None:
        return StatCell(text="—", direction="flat")
    if is_yield(metric):
        if abs(change) < 0.5:               # under half a bp reads as flat
            return StatCell(text="0 bps", direction="flat")
        direction = "up" if change > 0 else "down"
        return StatCell(text=f"{change:+.0f} bps", direction=direction)
    if abs(change) < 0.05:                   # under 0.05% reads as flat
        return StatCell(text="0.0%", direction="flat")
    direction = "up" if change > 0 else "down"
    return StatCell(text=f"{change:+.1f}%", direction=direction)


def _level(value: Optional[float], metric: str) -> str:
    """Format the current level per the metric's display hint."""
    if value is None:
        return "n/a"
    m = METRICS_BY_KEY.get(metric)
    display = m.display if m else "price"
    if display == "rate":
        return f"{value:.2f}%"
    if display == "index":
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def stat_row(metric: str, value: Optional[float], history: list[float]) -> StatRow:
    """One stat row from a metric's current value + rolling history."""
    m = METRICS_BY_KEY.get(metric)
    label = m.label if m else metric
    return StatRow(
        label=label,
        level=_level(value, metric),
        session=_cell(_change(history, _SESSION, metric), metric),
        week=_cell(_change(history, ctx_mod.WEEK_SESSIONS, metric), metric),
        month=_cell(_change(history, ctx_mod.MONTH_SESSIONS, metric), metric),
    )


def stat_table(
    metrics: tuple[str, ...],
    values: dict[str, Optional[float]],
    histories: dict[str, list[float]],
) -> StatTable:
    """A stat table for an ordered set of metrics.

    A metric with no current value AND no history is skipped (nothing to show
    honestly); one with a value but thin history still appears, its missing
    windows blank. This keeps a quiet/new section's table real, never fabricated.
    """
    rows: list[StatRow] = []
    for metric in metrics:
        value = values.get(metric)
        hist = histories.get(metric, [])
        if value is None and not hist:
            continue
        rows.append(stat_row(metric, value, hist))
    return StatTable(rows=tuple(rows))
