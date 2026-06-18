"""Flat templated why-lines (spec §5.6 failure fallback; roadmap §5.9/§5.10).

The brief never blocks on the model or news. Before the explanation engine exists
(Phase 5 ships with these) and whenever the model call fails (Phase 6 degradation),
each section gets a flat line built from numbers + direction alone. No causal
claim is asserted here, so there is nothing to validate and nothing to invent.
"""

from __future__ import annotations

from typing import Optional

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
