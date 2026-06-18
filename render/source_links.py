"""Source-link and favicon URL helpers (spec §7 "Every figure links to its source").

Every figure in the brief hyperlinks to the page it came from: yfinance figures to
the matching Yahoo Finance quote page, FRED-primary yields to the FRED series page.
Favicons (Movers and Watchlist rows only) come from Google's s2 service and fail
gracefully — the row stays readable if the glyph never loads.

Pure URL construction, no network. The template calls these so link logic lives in
one place (DRY) and is unit-testable without rendering.
"""

from __future__ import annotations

from urllib.parse import quote

from sources.symbols import SYMBOLS_BY_METRIC

YAHOO_QUOTE = "https://finance.yahoo.com/quote/{symbol}"
FRED_SERIES = "https://fred.stlouisfed.org/series/{series}"
GOOGLE_FAVICON = "https://www.google.com/s2/favicons?domain={domain}&sz=64"


def source_url(metric: str) -> str | None:
    """The canonical source page for a metric's settled figure (spec §7).

    Treasury yields are FRED-primary in the morning, so they link to the FRED
    series page; everything else links to its Yahoo Finance quote page. Returns
    None for an unknown metric so the template renders plain text, not a dead link.
    """
    sym = SYMBOLS_BY_METRIC.get(metric)
    if sym is None:
        return None
    if sym.fred and _is_yield_metric(metric):
        return FRED_SERIES.format(series=sym.fred)
    return YAHOO_QUOTE.format(symbol=quote(sym.yf, safe=""))


def yahoo_ticker_url(ticker: str) -> str:
    """Yahoo quote page for a single stock ticker (Movers / Watchlist rows)."""
    return YAHOO_QUOTE.format(symbol=quote(ticker, safe=""))


def favicon_url(domain: str | None) -> str | None:
    """Google s2 favicon URL for a domain, or None when no domain is mapped.

    None means the template simply omits the glyph; the row still reads correctly
    (spec §7 graceful fail).
    """
    if not domain:
        return None
    return GOOGLE_FAVICON.format(domain=quote(domain, safe=""))


def _is_yield_metric(metric: str) -> bool:
    # Local to avoid importing the metrics registry's yield set into the URL layer;
    # the only FRED-primary metrics are the two Treasury yields (spec §3.1, §7).
    return metric in ("ust10y", "ust2y")
