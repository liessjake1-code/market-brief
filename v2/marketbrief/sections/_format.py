from __future__ import annotations
from marketbrief.core.enums import Direction
from marketbrief.core.models import Field, FigureCell, WhyLine
from marketbrief.render.source_links import source_url

METRIC_LABELS: dict[str, str] = {
    "sp500": "S&P", "nasdaq": "Nasdaq", "dow": "Dow", "russell": "Russell",
    "ust10y": "10Y", "ust2y": "2Y", "dxy": "DXY", "hy_spread": "HY spread",
    "wti": "WTI", "gold": "Gold", "copper": "Copper",
    "btc": "BTC", "eth": "ETH", "vix": "VIX",
    "cpi_yoy": "CPI YoY", "pce_yoy": "PCE YoY", "fed_funds": "Fed funds",
}

SECTION_TITLES: dict[str, str] = {
    "us_equities": "US Equities", "rates_and_dollar": "Rates and the Dollar",
    "commodities": "Commodities", "washington": "Washington and Policy",
    "movers": "Movers", "economic_data_scorecard": "Economic Data Scorecard",
    "earnings_on_deck": "Earnings on Deck", "watchlist": "Watchlist",
    "crypto": "Crypto", "volatility_breadth": "Volatility and Breadth",
    "what_to_watch_today": "What to Watch Today",
}

# Honest one-line fallbacks (spec §2, §5.6). No em dashes, no emojis.
QUIET_LINES: dict[str, str] = {
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


def direction_of(change: float | None) -> Direction:
    if change is None or change == 0.0:
        return Direction.FLAT
    return Direction.UP if change > 0 else Direction.DOWN


def _fmt_value(field: Field) -> str:
    if field.value is None:
        return "n/a"
    return f"{field.value:,.2f}"


def figure_cell(metric: str, field: Field, *, change: float | None = None) -> FigureCell:
    # change= is intentionally omitted until ComputedNumbers pre-compute wiring lands (deferred)
    return FigureCell(
        metric_label=METRIC_LABELS.get(metric, metric),
        value_str=_fmt_value(field),
        change_str="" if change is None else f"{change:+.2f}",
        direction=direction_of(change),
        source_url=source_url(metric),
        stale=field.stale,
    )


def quiet_lead(section_id: str) -> WhyLine:
    return WhyLine(text=QUIET_LINES[section_id], source_url=None, hedged=True)
