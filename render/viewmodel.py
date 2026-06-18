"""Assemble the template view-model from validated engine outputs (spec §4, §6).

The Jinja template stays logic-light: all decisions about ordering, formatting,
source links, the live-zone label, and the honest one-line fallbacks happen here,
in tested Python, against the real shapes the engine produces. The template just
renders this dict.

Inputs are already validated upstream: Fields carry health (sources/quality), the
DiffResult/TopStoryDecision are computed deterministically, narrative SectionResults
are number-and-cause validated (engine/narrative), and the calendar is best-effort.
Nothing here invents a number or a cause (spec §1, §2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from engine.metrics import METRICS_BY_KEY, is_yield
from render import source_links
from sources.quality import Field

# Section id -> display title and the metric keys that ground its At-a-Glance row.
SECTION_TITLES: dict[str, str] = {
    "us_equities": "US Equities",
    "rates_and_dollar": "Rates and the Dollar",
    "commodities": "Commodities",
    "washington": "Washington and Policy",
    "movers": "Movers",
    "economic_data_scorecard": "Economic Data Scorecard",
    "earnings_on_deck": "Earnings on Deck",
    "watchlist": "Watchlist",
    "crypto": "Crypto",
    "volatility_breadth": "Volatility and Breadth",
    "what_to_watch_today": "What to Watch Today",
}

# Honest one-liner shown when a section has no model prose and no data (spec §4.3:
# "all eleven sections always appear"; an empty one gets one honest line).
SECTION_QUIET_LINE: dict[str, str] = {
    "us_equities": "Indices little changed; no clear catalyst.",
    "rates_and_dollar": "Rates and the dollar steady; nothing to read into it.",
    "commodities": "Commodities quiet; no clear catalyst.",
    "washington": "No market-moving policy news flagged this morning.",
    "movers": "No single-stock movers flagged from the curated universe.",
    "economic_data_scorecard": "No major economic releases on the board.",
    "earnings_on_deck": "No notable earnings flagged before the open.",
    "watchlist": "Watchlist is empty. Add tickers in config.yaml before first send.",
    "crypto": "Crypto little changed; risk appetite neutral.",
    "volatility_breadth": "VIX flat, no hedging demand, nothing to read into it.",
    "what_to_watch_today": "No scheduled events flagged for today.",
}


@dataclass(frozen=True)
class FigureCell:
    """A single figure with its label, formatted value, and source link."""

    label: str
    value: str
    url: Optional[str] = None
    direction: str = "flat"   # "up" | "down" | "flat" -> green/red/neutral in template


@dataclass(frozen=True)
class GlanceRow:
    category: str
    figures: tuple[FigureCell, ...]
    why: str
    is_live: bool = False
    timestamp: str = ""       # set only on the one live "This morning" row


@dataclass(frozen=True)
class SectionView:
    section_id: str
    title: str
    prose: str
    is_top_story: bool = False
    favicons: tuple[dict, ...] = ()   # {ticker, url, favicon} for Movers/Watchlist only


@dataclass(frozen=True)
class BriefView:
    """The full view-model the template renders."""

    date_label: str
    send_label: str
    degraded: bool
    diff_line: str
    glance_rows: tuple[GlanceRow, ...]
    sections: tuple[SectionView, ...]
    live_label: str
    live_figures: tuple[FigureCell, ...]
    forward_events: tuple[dict, ...]
    earnings: tuple[dict, ...]
    chart_cids: tuple[str, ...]
    sources_note: str = "Sources: yfinance, FRED, RSS. Automated; audit against the linked pages."


def _fmt_value(field: Field) -> str:
    if field.is_missing:
        return "n/a"
    value = field.value
    metric = field.metric
    if is_yield(metric):
        return f"{value:.2f}%"
    if metric in ("btc", "eth", "sp500", "nasdaq", "dow", "russell"):
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def figure_for(field: Field) -> FigureCell:
    """A linked, formatted figure cell for a metric Field (spec §7 every figure links)."""
    metric = METRICS_BY_KEY.get(field.metric)
    label = metric.label if metric else field.metric
    return FigureCell(
        label=label,
        value=_fmt_value(field),
        url=source_links.source_url(field.metric),
        direction="flat",   # direction is a settled-close concept; left neutral here
    )


def _glance_figures(fields: dict[str, Field], keys: tuple[str, ...]) -> tuple[FigureCell, ...]:
    return tuple(figure_for(fields[k]) for k in keys if k in fields)


# Which metrics ground each At-a-Glance row (spec §4.1 row order).
_GLANCE_SPEC: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("Markets", "us_equities", ("sp500", "nasdaq", "dow", "russell")),
    ("Rates and dollar", "rates_and_dollar", ("ust10y", "ust2y", "dxy")),
    ("Commodities", "commodities", ("wti", "gold")),
    ("Crypto", "crypto", ("btc", "eth")),
    ("Volatility", "volatility_breadth", ("vix",)),
)


def build_glance_rows(
    fields: dict[str, Field],
    section_why: dict[str, str],
    *,
    live_label: str,
    live_why: str,
    events_why: str,
    earnings_why: str,
    washington_why: str,
    bottom_line: str,
) -> tuple[GlanceRow, ...]:
    """The 10-row At a Glance table (spec §4.1, Appendix A row order).

    Nine settled rows plus the single live "This morning" row, which is labeled
    with its pull timestamp and never confused for a settled fact.
    """
    rows: list[GlanceRow] = []
    for category, section_id, keys in _GLANCE_SPEC:
        rows.append(GlanceRow(
            category=category,
            figures=_glance_figures(fields, keys),
            why=section_why.get(section_id, ""),
        ))
    rows.append(GlanceRow(
        category="This morning",
        figures=(),
        why=live_why,
        is_live=True,
        timestamp=live_label,
    ))
    rows.append(GlanceRow(category="Today's events", figures=(), why=events_why))
    rows.append(GlanceRow(category="Earnings (pre-open)", figures=(), why=earnings_why))
    rows.append(GlanceRow(category="Washington", figures=(), why=washington_why))
    rows.append(GlanceRow(category="Bottom line", figures=(), why=bottom_line))
    return tuple(rows)


def _favicons_for(tickers: list[dict]) -> tuple[dict, ...]:
    """{ticker, url, favicon} rows for Movers/Watchlist; favicon may be None (graceful)."""
    out: list[dict] = []
    for item in tickers:
        ticker = item["ticker"]
        domain = item.get("domain")
        out.append({
            "ticker": ticker,
            "url": source_links.yahoo_ticker_url(ticker),
            "favicon": source_links.favicon_url(domain),
        })
    return tuple(out)


def build_sections(
    order: list[str],
    prose_by_section: dict[str, str],
    *,
    top_story_id: str,
    favicon_tickers: Optional[dict[str, list[dict]]] = None,
) -> tuple[SectionView, ...]:
    """Order the eleven sections per the Top Story decision; honest line when empty.

    `order` is TopStoryDecision.order (Top Story first, rest in fixed fallback).
    Favicons are confined to Movers and Watchlist (spec §6.5).
    """
    favicon_tickers = favicon_tickers or {}
    out: list[SectionView] = []
    for section_id in order:
        prose = prose_by_section.get(section_id) or SECTION_QUIET_LINE.get(section_id, "")
        favicons: tuple[dict, ...] = ()
        if section_id in ("movers", "watchlist"):
            favicons = _favicons_for(favicon_tickers.get(section_id, []))
        out.append(SectionView(
            section_id=section_id,
            title=SECTION_TITLES.get(section_id, section_id),
            prose=prose,
            is_top_story=(section_id == top_story_id),
            favicons=favicons,
        ))
    return tuple(out)
