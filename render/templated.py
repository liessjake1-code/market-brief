"""Flat templated why-lines (spec §5.6 failure fallback; roadmap §5.9/§5.10).

The brief never blocks on the model or news. Before the explanation engine exists
(Phase 5 ships with these) and whenever the model call fails (Phase 6 degradation),
each section gets a flat line built from numbers + direction alone. No causal
claim is asserted here, so there is nothing to validate and nothing to invent.

The richer `computed_section_line` (the redesign's "no empty sections" fix) goes
further: it assembles the spec §5.6 four-ingredient read MINUS the causal "why" —
level-in-context against the 5/20-day range, the move, the streak/range, and a
forward hook — all from numbers and rolling history. It NEVER asserts a cause, so
a quiet section reads as short-but-substantive instead of one bare line, without
violating "never manufacture a cause" (CLAUDE.md, spec §2).
"""

from __future__ import annotations

from typing import Optional

from engine import diff as diff_mod
from engine.metrics import METRICS_BY_KEY, is_yield
from sources.quality import Field


def direction_word(change: Optional[float]) -> str:
    if change is None:
        return "little changed"
    if change > 0:
        return "higher"
    if change < 0:
        return "lower"
    return "flat"


def templated_line(field: Field, change: Optional[float]) -> str:
    """One honest, source-free line for a metric (numbers + direction only)."""
    label = METRICS_BY_KEY[field.metric].label
    if field.is_missing:
        return f"{label}: data unavailable this morning."
    if field.stale:
        return f"{label}: last available reading {_fmt(field.value, field.metric)} (stale, not refreshed today)."
    move = ""
    if change is not None:
        unit = "bps" if is_yield(field.metric) else "%"
        move = f", {direction_word(change)} {abs(change):.1f} {unit}"
    return f"{label}: {_fmt(field.value, field.metric)}{move}. No clear catalyst."


# Per-section forward hook: a neutral "what to watch" closer with no cause claim.
_SECTION_HOOK: dict[str, str] = {
    "us_equities": "Watch whether breadth confirms the move or it stays top-heavy.",
    "rates_and_dollar": "The long end is the swing factor into the next data print.",
    "commodities": "Watch the inventory and demand reads for the next leg.",
    "crypto": "Risk appetite here tends to track the broader tape.",
    "volatility_breadth": "A low VIX leaves little hedging cushion if data surprises.",
    "movers": "Single-name moves to confirm or fade on the next session.",
    "watchlist": "Tracking the names you flagged; no broad catalyst beyond the tape.",
}


def _move_clause(history: list[float], metric: str) -> str:
    """Direction + size of the latest settled move, from history. Empty if thin."""
    if len(history) < 2 or not history[-2]:
        return ""
    if is_yield(metric):
        bps = (history[-1] - history[-2]) * 100.0
        if abs(bps) < 0.5:
            return "little changed on the session"
        return f"{direction_word(bps)} about {abs(bps):.0f} bps on the session"
    pct = (history[-1] - history[-2]) / history[-2] * 100.0
    if abs(pct) < 0.05:
        return "little changed on the session"
    return f"{direction_word(pct)} about {abs(pct):.1f}% on the session"


def _range_clause(history: list[float]) -> str:
    """Level-in-context against the recent range (a new high/low, else mid-range)."""
    brk20 = diff_mod.detect_break(history, 20)
    if brk20:
        return f"at {brk20}"
    brk5 = diff_mod.detect_break(history, 5)
    if brk5:
        return f"at {brk5}"
    streak = diff_mod.detect_streak(history)
    if streak:
        count, direction = streak
        return f"closing {direction} for the {diff_mod._ordinal(count)} straight session"
    if len(history) >= diff_mod.MIN_HISTORY_FOR_RANGE:
        return "inside its recent range"
    return ""


def computed_section_line(
    field: Field, history: list[float], *, section_id: str
) -> str:
    """A substantive, cause-free section line: level-in-context, move, hook (spec §5.6).

    The redesign's "no empty sections" fix. Builds the four-ingredient read minus
    the causal "why" (which only the model, grounded in a real article, may add).
    Stale or missing data degrades to the plain templated line rather than guessing.
    """
    if field.is_missing or field.stale:
        return templated_line(field, change=None)

    label = METRICS_BY_KEY[field.metric].label
    value = _fmt(field.value, field.metric)
    move = _move_clause(history, field.metric)
    rng = _range_clause(history)

    head = f"{label} at {value}"
    if move:
        head += f", {move}"
    if rng:
        head += f", {rng}"
    head += "."

    hook = _SECTION_HOOK.get(section_id, "")
    # No matched article means no causal "why" — that omission is correct (spec §2).
    if hook:
        return f"{head} No clear catalyst flagged. {hook}"
    return f"{head} No clear catalyst flagged."


def _fmt(value: Optional[float], metric: str) -> str:
    if value is None:
        return "n/a"
    if is_yield(metric):
        return f"{value:.2f}%"
    if metric in ("btc", "eth", "sp500", "nasdaq", "dow"):
        return f"{value:,.0f}"
    return f"{value:,.2f}"


DATA_UNAVAILABLE_HTML = (
    "<html><body style='font-family:Georgia,serif'>"
    "<h2>Market brief unavailable this morning</h2>"
    "<p>Too many core data fields were missing to build a reliable brief. "
    "This run exited without a full brief on purpose; the underlying data source "
    "(yfinance) likely failed or was blocked. Check the workflow logs.</p>"
    "</body></html>"
)
