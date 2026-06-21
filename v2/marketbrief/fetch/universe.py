"""Movers universe fetch (I/O): pull daily closes for a list of stock tickers.

Reuses the yfinance daily-close downloader (same `(symbol, days) -> list[float]`
signature as the price source), one call per universe ticker. Per-name isolation:
a ticker that errors or returns nothing is dropped, never raised, so one bad symbol
cannot sink the whole board. Offline-gated like every source, so tests and the
MARKET_BRIEF_OFFLINE seam never hit the network.
"""
from __future__ import annotations

from typing import Callable

from marketbrief.fetch.net import is_offline
from marketbrief.sources.yfinance_source import download_closes

Downloader = Callable[[str, int], list[float]]

# Calendar days requested per ticker. The month window needs 22 trading closes
# (closes[-22]); 30 calendar days can fall short across weekends/holidays, so we
# request 45 to comfortably clear 22 sessions. The downloader itself also pads.
_HISTORY_DAYS = 45


def fetch_universe_closes(
    tickers: list[str], *, downloader: Downloader | None = None
) -> dict[str, list[float]]:
    """Fetch daily closes (oldest first) for each ticker in the universe.

    Args:
        tickers: stock symbols to pull. Empty list -> no network, empty result.
        downloader: injectable `(symbol, days) -> closes`; defaults to the real
            yfinance pull. Tests pass a fake.

    Returns:
        Mapping of ticker -> non-empty closes. Tickers that error or return no
        closes are omitted. Offline -> empty mapping (downloader never called).
    """
    if not tickers or is_offline():
        return {}
    dl = downloader or download_closes
    out: dict[str, list[float]] = {}
    for ticker in tickers:
        try:
            closes = dl(ticker, _HISTORY_DAYS)
        except Exception:
            continue  # isolated: one bad ticker never sinks the board
        if closes:
            out[ticker] = closes
    return out
