"""Per-stock yfinance pulls for the watchlist + movers sections (spec §4.3, §7).

Separate from sources/prices.py, which is firmly keyed by macro metric. This
module pulls arbitrary equity tickers, carrying closes + dates + the latest
session volume (the movers floor gate, config movers_min_volume).

Best-effort by design (spec §7): a stock fetch is NEVER core data, so a failed
ticker is simply omitted from the result and a total failure yields {}. It never
raises and never trips the degraded banner. The single network call is isolated
in _download_stock (injectable) so the assembly logic is unit-testable offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

# A downloader maps (ticker, days) -> (closes, iso_dates, latest_volume),
# closes/dates oldest->newest and aligned. Injected so tests never hit network.
StockDownloader = Callable[[str, int], tuple[list[float], list[str], Optional[float]]]

BACKFILL_PAD = 40  # request extra calendar days so enough trading closes survive gaps


@dataclass(frozen=True)
class StockQuote:
    """One ticker's settled snapshot + rolling history for a section row."""

    ticker: str
    close: Optional[float]
    prev_close: Optional[float]
    history: tuple[float, ...]
    history_dates: tuple[str, ...]
    volume: Optional[float]

    @property
    def change_pct(self) -> Optional[float]:
        """Session percent change off the previous close; None if unavailable."""
        if self.close is None or self.prev_close in (None, 0):
            return None
        return (self.close - self.prev_close) / self.prev_close * 100.0


def _select_close(df, ticker: str):
    """Extract the Close series across yfinance frame shapes (see prices._select_close)."""
    cols = df.columns
    if hasattr(cols, "nlevels") and cols.nlevels > 1:
        if ("Close", ticker) in cols:
            return df[("Close", ticker)]
        close_cols = [c for c in cols if c[0] == "Close"]
        return df[close_cols[0]] if close_cols else None
    return df["Close"] if "Close" in cols else None


def _select_volume(df, ticker: str):
    """Extract the Volume series across yfinance frame shapes; None if absent."""
    cols = df.columns
    if hasattr(cols, "nlevels") and cols.nlevels > 1:
        if ("Volume", ticker) in cols:
            return df[("Volume", ticker)]
        vol_cols = [c for c in cols if c[0] == "Volume"]
        return df[vol_cols[0]] if vol_cols else None
    return df["Volume"] if "Volume" in cols else None


def _download_stock(
    ticker: str, days: int
) -> tuple[list[float], list[str], Optional[float]]:
    """Real yfinance pull: (closes, iso_dates, latest_volume). Empty on any failure.

    Mirrors prices._download (yfinance==1.4.1, auto_adjust, threads off) but also
    returns the DatetimeIndex as ISO dates and the most-recent session volume.
    """
    try:
        import yfinance as yf

        df = yf.download(
            ticker,
            period=f"{max(days + BACKFILL_PAD, 60)}d",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        if df is None or df.empty:
            return [], [], None

        close = _select_close(df, ticker)
        if close is None:
            return [], [], None
        close = close.dropna()
        closes = [float(v) for v in close.tolist()]
        dates = [ts.date().isoformat() for ts in close.index]

        volume = None
        vol_series = _select_volume(df, ticker)
        if vol_series is not None:
            vol_series = vol_series.dropna()
            if not vol_series.empty:
                volume = float(vol_series.iloc[-1])

        return closes, dates, volume
    except Exception:
        return [], [], None


def fetch_stocks(
    tickers: list[str],
    *,
    days: int = 10,
    downloader: Optional[StockDownloader] = None,
) -> dict[str, StockQuote]:
    """Pull a StockQuote per ticker, best-effort. Failed/empty tickers are omitted.

    De-dupes the input (watchlist and movers_universe overlap, e.g. TSLA/NVDA),
    preserving first-seen order. A ticker that returns no closes is dropped; an
    exception in the downloader for one ticker never sinks the others or raises.
    """
    dl = downloader or _download_stock
    out: dict[str, StockQuote] = {}
    for ticker in tickers:
        if ticker in out:
            continue
        try:
            closes, dates, volume = dl(ticker, days)
        except Exception:
            continue
        if not closes:
            continue
        out[ticker] = StockQuote(
            ticker=ticker,
            close=closes[-1],
            prev_close=closes[-2] if len(closes) >= 2 else None,
            history=tuple(closes),
            history_dates=tuple(dates),
            volume=volume,
        )
    return out
