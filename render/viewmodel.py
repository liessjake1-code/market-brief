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

from engine import stats as stats_mod
from engine.metrics import METRICS_BY_KEY, is_monthly, is_yield
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
class MacroReading:
    """One current-level macro backdrop reading (e.g. 'CPI (YoY)' -> '4.17%').

    Monthly/administered series (CPI, PCE, the policy rate) update roughly once a
    month, so a session/week/month change is meaningless. They render as a compact
    row of standalone current levels instead of a change table (the human's call).
    """

    label: str
    value: str


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
    # A Python-computed one-line read of the chart (accuracy-safe; no model number).
    chart_takeaway: str = ""
    # The session/week/month stat table shown at the TOP of the section box, before
    # the prose (redesign "Visuals + macro"). Empty for sections with no metrics.
    stat_table: tuple[stats_mod.StatRow, ...] = ()
    # Current-level macro backdrop readings (CPI/PCE/Fed funds), shown as a compact
    # standalone row, NOT in the change table (monthly series have no daily delta).
    macro_strip: tuple[MacroReading, ...] = ()
    # Per-stock "why" lines for Movers/Watchlist: each {ticker, why, source_label,
    # source_url}. Only stocks with a real sourced cause appear; a stock with no
    # catalyst is omitted (never a fabricated reason). Empty for non-stock sections.
    stock_notes: tuple[dict, ...] = ()


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
    calendar_note: str = ""   # honest note when the optional events feed is unavailable
    chart_cids: tuple[str, ...] = ()
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


# Which metrics each section's stat table shows, in display order (redesign).
# The session/week/month CHANGE table per section: only DAILY-trading series, whose
# trailing change is meaningful. The rates table keeps the two Treasuries, DXY, and
# the high-yield credit spread (all daily), plus a synthetic 2s10s spread row.
# Commodities adds copper. The monthly/administered macro series (CPI, PCE, the
# policy rate) are deliberately NOT here — they render as a current-level backdrop
# strip instead (see SECTION_MACRO_METRICS), since a daily delta is meaningless.
SECTION_STAT_METRICS: dict[str, tuple[str, ...]] = {
    "us_equities": ("sp500", "nasdaq", "dow", "russell"),
    "rates_and_dollar": ("ust10y", "ust2y", "dxy", "hy_spread"),
    "commodities": ("wti", "gold", "copper"),
    "crypto": ("btc", "eth"),
    "volatility_breadth": ("vix",),
}

# Monthly/administered macro readings shown as a compact current-level strip under
# the section's stat table (CPI YoY, PCE YoY, the policy rate). Order = display order.
SECTION_MACRO_METRICS: dict[str, tuple[str, ...]] = {
    "rates_and_dollar": ("cpi_yoy", "pce_yoy", "fed_funds"),
}


def build_stat_tables(
    values: dict[str, Optional[float]],
    histories: dict[str, list[float]],
) -> dict[str, tuple[stats_mod.StatRow, ...]]:
    """Build the per-section stat-table rows from current values + history.

    Pure pass-through to engine.stats, one table per section in SECTION_STAT_METRICS.
    The 2s10s spread is appended to the rates table as a synthetic row when both
    legs are present, so the curve shape reads as a number (the human asked for the
    spread as a NUMBER, not an extra chart line).
    """
    out: dict[str, tuple[stats_mod.StatRow, ...]] = {}
    for section_id, metrics in SECTION_STAT_METRICS.items():
        table = stats_mod.stat_table(metrics, values, histories)
        rows = list(table.rows)
        if section_id == "rates_and_dollar":
            spread = _spread_row(values, histories)
            if spread is not None:
                rows.insert(2, spread)   # after 10Y/2Y, before DXY
        out[section_id] = tuple(rows)
    return out


def build_macro_strips(
    values: dict[str, Optional[float]],
) -> dict[str, tuple[MacroReading, ...]]:
    """Current-level macro backdrop readings per section (CPI/PCE/Fed funds).

    These monthly/administered series have no meaningful daily change, so they are
    shown as standalone current levels rather than session/week/month rows. A metric
    with no current value is skipped (nothing to show honestly).
    """
    out: dict[str, tuple[MacroReading, ...]] = {}
    for section_id, metrics in SECTION_MACRO_METRICS.items():
        readings: list[MacroReading] = []
        for key in metrics:
            value = values.get(key)
            if value is None:
                continue
            m = METRICS_BY_KEY.get(key)
            label = m.label if m else key
            readings.append(MacroReading(label=label, value=stats_mod._level(value, key)))
        out[section_id] = tuple(readings)
    return out


def _spread_row(
    values: dict[str, Optional[float]],
    histories: dict[str, list[float]],
) -> Optional[stats_mod.StatRow]:
    """A synthetic 2s10s spread stat row (10Y minus 2Y, in basis points).

    The level is the current spread in bps; the session/week/month cells are the
    change in that spread (a bps delta), computed from the parallel yield histories.
    Returns None when either leg is missing.
    """
    ten, two = values.get("ust10y"), values.get("ust2y")
    if ten is None or two is None:
        return None
    th, twoh = histories.get("ust10y", []), histories.get("ust2y", [])
    spread_hist = _paired_spread_history(th, twoh)
    level_bps = (ten - two) * 100.0
    return stats_mod.StatRow(
        label="2s10s spread",
        level=f"{level_bps:+.0f} bps",
        session=stats_mod._cell(_spread_change(spread_hist, 1), "ust10y"),
        week=stats_mod._cell(_spread_change(spread_hist, stats_mod.ctx_mod.WEEK_SESSIONS), "ust10y"),
        month=stats_mod._cell(_spread_change(spread_hist, stats_mod.ctx_mod.MONTH_SESSIONS), "ust10y"),
    )


def _paired_spread_history(ten: list[float], two: list[float]) -> list[float]:
    """The 2s10s spread (in percent) per session where both legs exist, aligned to
    the most recent N closes."""
    n = min(len(ten), len(two))
    if n == 0:
        return []
    ten_t, two_t = ten[-n:], two[-n:]
    return [a - b for a, b in zip(ten_t, two_t) if a is not None and b is not None]


def _spread_change(spread_hist: list[float], sessions: int) -> Optional[float]:
    """Change in the 2s10s spread over `sessions`, in basis points."""
    if len(spread_hist) < sessions + 1:
        return None
    return (spread_hist[-1] - spread_hist[-(sessions + 1)]) * 100.0


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


def build_stock_table(
    tickers: list[str],
    quotes: dict[str, "object"],
) -> tuple[stats_mod.StatRow, ...]:
    """Per-stock session/week/month stat rows for Watchlist/Movers, in caller order.

    `quotes` maps ticker -> StockQuote (sources.stocks). A ticker with no quote is
    skipped (best-effort: the fetch may have dropped it). Each row is labeled by
    its symbol and shows percent change; thin history shows an em dash per window.
    """
    rows: list[stats_mod.StatRow] = []
    for ticker in tickers:
        quote = quotes.get(ticker)
        if quote is None:
            continue
        rows.append(stats_mod.stock_stat_row(quote))
    return tuple(rows)


def build_movers_table(
    selection: "object",
    quotes: dict[str, "object"],
) -> tuple[stats_mod.StatRow, ...]:
    """Per-stock stat rows for the Movers section, in the selection's ranked order.

    `selection` is an engine.movers.MoversSelection; its rows are already ranked by
    absolute session move and gated by the volume floor / watchlist-only rule.
    """
    return build_stock_table([m.ticker for m in selection.movers], quotes)


def build_stock_notes(
    tickers: list[str],
    stock_results: dict[str, "object"],
) -> tuple[dict, ...]:
    """Per-stock 'why' lines for Movers/Watchlist, in caller order.

    `stock_results` maps a "stock:<TICKER>" id -> a narrative SectionResult. A
    ticker is included only when its cause is real (not the templated fallback)
    and non-empty; a stock with no catalyst is omitted rather than given a
    fabricated reason (spec §2). The matched article (if any) renders as a
    clickable source. Never invents a cause or a number.
    """
    notes: list[dict] = []
    for ticker in tickers:
        res = stock_results.get(f"stock:{ticker}")
        if res is None or getattr(res, "templated", False):
            continue
        why = (getattr(res, "prose", "") or "").strip()
        if not why or why.lower().startswith("no clear catalyst"):
            continue
        cited = getattr(res, "cited_sources", ()) or ()
        source_label = cited[0]["title"] if cited else ""
        source_url = cited[0]["url"] if cited else ""
        notes.append({
            "ticker": ticker,
            "why": why,
            "source_label": source_label,
            "source_url": source_url,
        })
    return tuple(notes)


# Order in which a duplicated per-stock "why" note is kept: the FIRST section here
# that carries the ticker wins; later sections drop it. Movers is the home of the
# "why it moved" read, so a ticker that is both a mover and a watchlist name shows
# its note once, under Movers (Jun 18: SPCX duplicated across both sections).
_NOTE_DEDUP_PRIORITY: tuple[str, ...] = ("movers", "watchlist")


def dedup_stock_notes(
    stock_notes: dict[str, tuple[dict, ...]],
) -> dict[str, tuple[dict, ...]]:
    """Drop a ticker's per-stock 'why' note from all but its highest-priority section.

    A ticker appearing in both Movers and Watchlist (same article) otherwise prints
    the identical "why" line twice. We keep it once, under the higher-priority
    section (Movers), and drop the duplicate from the other. Sections not in the
    priority list pass through unchanged. Pure; returns a new dict (no mutation).
    """
    seen: set[str] = set()
    out: dict[str, tuple[dict, ...]] = dict(stock_notes)
    for section_id in _NOTE_DEDUP_PRIORITY:
        notes = stock_notes.get(section_id)
        if not notes:
            continue
        kept: list[dict] = []
        for note in notes:
            ticker = note.get("ticker")
            if ticker in seen:
                continue
            seen.add(ticker)
            kept.append(note)
        out[section_id] = tuple(kept)
    return out


def build_stock_sparklines(
    tickers: list[str],
    quotes: dict[str, "object"],
) -> tuple[Spark, ...]:
    """Inline sparklines for a set of tickers, drawn from their StockQuote history."""
    series = {}
    for ticker in tickers:
        quote = quotes.get(ticker)
        if quote is not None:
            series[ticker] = list(quote.history)
    return build_sparklines(series)


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
    stat_tables: Optional[dict[str, tuple[stats_mod.StatRow, ...]]] = None,
    macro_strips: Optional[dict[str, tuple[MacroReading, ...]]] = None,
    stock_tables: Optional[dict[str, tuple[stats_mod.StatRow, ...]]] = None,
    stock_sparklines: Optional[dict[str, tuple[Spark, ...]]] = None,
    stock_notes: Optional[dict[str, tuple[dict, ...]]] = None,
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
    stat_tables = stat_tables or {}
    macro_strips = macro_strips or {}
    stock_tables = stock_tables or {}
    stock_sparklines = stock_sparklines or {}
    stock_notes = stock_notes or {}
    stock_notes = dedup_stock_notes(stock_notes)
    out: list[SectionView] = []
    for section_id in order:
        if section_id in _BODY_SKIP:
            continue
        favicons: tuple[dict, ...] = ()
        if section_id in ("movers", "watchlist"):
            favicons = _favicons_for(favicon_tickers.get(section_id, []))
        is_top = section_id == top_story_id
        chart = section_charts.get(section_id, {})
        # Movers/Watchlist get their per-STOCK table; every other section uses the
        # metric-keyed table. Watchlist sparklines are now real per-stock series
        # (not the old accidental core-metric overlap).
        if section_id in stock_tables:
            stat_table = stock_tables[section_id]
        else:
            stat_table = stat_tables.get(section_id, ())
        section_notes = stock_notes.get(section_id, ())
        # Quiet line ONLY when the section is genuinely empty. A populated per-stock
        # table or per-stock notes carries the section, so the stale "Watchlist is
        # empty" / "No single-stock movers flagged" line is suppressed (Jun 18 bug:
        # both printed under fully-populated tables).
        has_stock_content = bool(stat_table) or bool(section_notes)
        if section_id in ("movers", "watchlist") and has_stock_content:
            prose = prose_by_section.get(section_id, "")
        else:
            prose = prose_by_section.get(section_id) or SECTION_QUIET_LINE.get(section_id, "")
        # Per-section stock sparklines take precedence; fall back to the legacy
        # watchlist-only `sparklines` arg (preview fixture + older callers).
        section_sparks = stock_sparklines.get(section_id, ())
        if not section_sparks and section_id == "watchlist":
            section_sparks = sparklines
        out.append(SectionView(
            section_id=section_id,
            title=SECTION_TITLES.get(section_id, section_id),
            prose=prose,
            is_top_story=is_top,
            favicons=favicons,
            sources=_sources_for(cited_by_section.get(section_id, ())),
            hbars=hbars if is_top else (),
            hbar_maxabs=hbar_maxabs if is_top else 1.0,
            sparklines=section_sparks,
            chart_cid=chart.get("cid"),
            chart_caption=chart.get("caption", ""),
            chart_caption_url=chart.get("caption_url", ""),
            chart_takeaway=chart.get("takeaway", ""),
            stat_table=stat_table,
            macro_strip=macro_strips.get(section_id, ()),
            stock_notes=section_notes,
        ))
    return tuple(out)
