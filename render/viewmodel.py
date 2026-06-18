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
class HBar:
    """One row of the inline HTML %-change bar chart (no image, renders anywhere)."""

    label: str
    pct: float


@dataclass(frozen=True)
class Spark:
    """One inline HTML sparkline: a ticker + its normalized recent series."""

    ticker: str
    series: tuple[float, ...]
    up: bool


@dataclass(frozen=True)
class SectionView:
    section_id: str
    title: str
    prose: str
    is_top_story: bool = False
    favicons: tuple[dict, ...] = ()   # {ticker, url, favicon} for Movers/Watchlist only
    # The matched reporting behind the causal "why", as {label, url} for a clickable
    # citation (spec §7). Empty when the section made no cause claim (no empty label).
    sources: tuple[dict, ...] = ()
    # Inline HTML charts drawn from numbers in the template (no image): the Top
    # Story index %-change bars and the Watchlist sparklines. Empty otherwise.
    hbars: tuple[HBar, ...] = ()
    hbar_maxabs: float = 1.0
    sparklines: tuple[Spark, ...] = ()
    # The PNG chart (matplotlib, CID-embedded) that belongs inline in this section,
    # with its caption text + link. None when this section has no PNG chart.
    chart_cid: Optional[str] = None
    chart_caption: str = ""
    chart_caption_url: str = ""


@dataclass(frozen=True)
class BriefView:
    """The full view-model the template renders."""

    date_label: str
    send_label: str
    degraded: bool
    diff_line: str
    glance_rows: tuple[GlanceRow, ...]
    text_rows: tuple[tuple[str, str], ...]   # the 4 (label, text) glance rows
    sections: tuple[SectionView, ...]
    live_label: str
    live_figures: tuple[FigureCell, ...]
    forward_events: tuple[dict, ...]
    earnings: tuple[dict, ...]
    chart_cids: tuple[str, ...]
    sources_note: str = "Sources: yfinance, FRED, RSS (incl. WSJ). Automated; audit against the linked pages."


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


# Short, scannable At-a-Glance labels (the full "S&P 500" reads in the body).
_GLANCE_LABELS: dict[str, str] = {
    "sp500": "S&P", "nasdaq": "Nasdaq", "dow": "Dow", "russell": "Russell",
    "ust10y": "10Y", "ust2y": "2Y", "dxy": "DXY",
    "wti": "WTI", "gold": "Gold", "btc": "BTC", "eth": "ETH", "vix": "VIX",
}


def figure_for(field: Field, *, direction: str = "flat", short: bool = False) -> FigureCell:
    """A linked, formatted figure cell for a metric Field (spec §7 every figure links).

    `direction` ("up"|"down"|"flat") colors the value green/red/neutral; the caller
    derives it from settled history. `short` uses the compact At-a-Glance label.
    """
    metric = METRICS_BY_KEY.get(field.metric)
    if short and field.metric in _GLANCE_LABELS:
        label = _GLANCE_LABELS[field.metric]
    else:
        label = metric.label if metric else field.metric
    return FigureCell(
        label=label,
        value=_fmt_value(field),
        url=source_links.source_url(field.metric),
        direction=direction,
    )


def _glance_figures(
    fields: dict[str, Field],
    keys: tuple[str, ...],
    directions: Optional[dict[str, str]] = None,
) -> tuple[FigureCell, ...]:
    directions = directions or {}
    return tuple(
        figure_for(fields[k], direction=directions.get(k, "flat"), short=True)
        for k in keys if k in fields
    )


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
    section_tag: dict[str, str],
    *,
    directions: Optional[dict[str, str]] = None,
) -> tuple[GlanceRow, ...]:
    """The five settled figure rows of At a Glance (redesign structure fix #2).

    Only the five figure-bearing categories live here now: each carries its
    figures plus a SHORT direction/quiet tag (not the full causal sentence — that
    lives once in the body section). The single live "This morning" row is promoted
    out to the fenced live zone, and the four text rows (events, earnings,
    Washington, bottom line) render separately as `text_rows` so there are no empty
    figure cells. See HANDOFF_DESIGN structure fixes 1, 2, 4.
    """
    rows: list[GlanceRow] = []
    for category, section_id, keys in _GLANCE_SPEC:
        rows.append(GlanceRow(
            category=category,
            figures=_glance_figures(fields, keys, directions),
            why=section_tag.get(section_id, ""),
        ))
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


def build_hbars(index_changes: dict[str, float]) -> tuple[tuple[HBar, ...], float]:
    """Inline %-change bars for the Top Story (pure; no matplotlib).

    `index_changes` maps an index label -> daily percent change. Returns the bar
    rows and the shared max-abs scale so all bars share one axis. Empty in -> empty
    out (the template then draws no bar block).
    """
    bars = tuple(HBar(label=lbl, pct=pct) for lbl, pct in index_changes.items() if pct is not None)
    if not bars:
        return (), 1.0
    maxabs = max(abs(b.pct) for b in bars) or 1.0
    return bars, maxabs


def build_sparklines(series_by_ticker: dict[str, list[float]]) -> tuple[Spark, ...]:
    """Inline sparklines for the Watchlist (pure; no matplotlib).

    Each ticker -> its recent close series; `up` is the sign of first->last so the
    bars color green/red. A series shorter than two points is skipped (nothing to
    draw honestly).
    """
    out: list[Spark] = []
    for ticker, series in series_by_ticker.items():
        clean = tuple(v for v in series if v is not None)
        if len(clean) < 2:
            continue
        out.append(Spark(ticker=ticker, series=clean, up=clean[-1] >= clean[0]))
    return tuple(out)


# What to Watch Today is rendered ONCE, by the template's dedicated forward block,
# so it is never also a body section (HANDOFF_DESIGN structure fix #3). The Top
# Story engine still reasons over all eleven (engine/top_story FALLBACK_ORDER is
# untouched); we only suppress it here at render time.
_BODY_SKIP: frozenset[str] = frozenset({"what_to_watch_today"})


def _sources_for(cited: tuple[dict, ...]) -> tuple[dict, ...]:
    """Map narrative cited_sources ({title,url}) to the template's {label,url}.

    Empty in -> empty out, so a section with no matched article shows no "Source"
    label (spec §7: no empty source labels).
    """
    out: list[dict] = []
    for c in cited:
        url = c.get("url")
        title = c.get("title")
        if url and title:
            out.append({"label": title, "url": url})
    return tuple(out)


def build_sections(
    order: list[str],
    prose_by_section: dict[str, str],
    *,
    top_story_id: str,
    favicon_tickers: Optional[dict[str, list[dict]]] = None,
    cited_by_section: Optional[dict[str, tuple[dict, ...]]] = None,
    section_charts: Optional[dict[str, dict]] = None,
    hbars: tuple[HBar, ...] = (),
    hbar_maxabs: float = 1.0,
    sparklines: tuple[Spark, ...] = (),
) -> tuple[SectionView, ...]:
    """Order the body sections per the Top Story decision; rich line when quiet.

    `order` is TopStoryDecision.order (Top Story first, rest in fixed fallback);
    what_to_watch_today is skipped (rendered once by the forward block). Favicons
    are confined to Movers and Watchlist (spec §6.5). Per-section citations come
    from the validated narrative cause_source_id; the inline HTML index-bar chart
    attaches to the Top Story, and sparklines to the Watchlist. A PNG chart
    (rates, oil) attaches to its section via `section_charts`.
    """
    favicon_tickers = favicon_tickers or {}
    cited_by_section = cited_by_section or {}
    section_charts = section_charts or {}
    out: list[SectionView] = []
    for section_id in order:
        if section_id in _BODY_SKIP:
            continue
        prose = prose_by_section.get(section_id) or SECTION_QUIET_LINE.get(section_id, "")
        favicons: tuple[dict, ...] = ()
        if section_id in ("movers", "watchlist"):
            favicons = _favicons_for(favicon_tickers.get(section_id, []))
        is_top = section_id == top_story_id
        chart = section_charts.get(section_id, {})
        out.append(SectionView(
            section_id=section_id,
            title=SECTION_TITLES.get(section_id, section_id),
            prose=prose,
            is_top_story=is_top,
            favicons=favicons,
            sources=_sources_for(cited_by_section.get(section_id, ())),
            hbars=hbars if is_top else (),
            hbar_maxabs=hbar_maxabs if is_top else 1.0,
            sparklines=sparklines if section_id == "watchlist" else (),
            chart_cid=chart.get("cid"),
            chart_caption=chart.get("caption", ""),
            chart_caption_url=chart.get("caption_url", ""),
        ))
    return tuple(out)
