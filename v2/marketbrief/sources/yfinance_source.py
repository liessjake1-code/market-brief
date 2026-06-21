from __future__ import annotations
from typing import Callable
from marketbrief.core.models import SourceResult, Field
from marketbrief.core.enums import SourceHealth
from marketbrief.core.symbols import SYMBOLS
from marketbrief.fetch.net import is_offline

Downloader = Callable[[str, int], list[float]]
BACKFILL_PAD = 40  # request extra days so ~25 trading closes survive holidays


def _real_download(symbol: str, days: int) -> list[float]:
    """Real yfinance pull: closes oldest->newest, [] on any failure.

    yfinance imported lazily so importing this module never forces it. Handles
    the MultiIndex/flat Close shapes (load-bearing-pin guard, spec §13).
    """
    try:
        import yfinance as yf

        df = yf.download(
            symbol, period=f"{max(days + BACKFILL_PAD, 60)}d", interval="1d",
            auto_adjust=True, progress=False, threads=False,
        )
        if df is None or df.empty:
            return []
        close = _select_close(df, symbol)
        if close is None:
            return []
        return [float(v) for v in close.dropna().tolist()]
    except Exception:
        return []


def download_closes(symbol: str, days: int) -> list[float]:
    """Public daily-close downloader: closes oldest->newest, [] on any failure.

    Stable entry point shared by YFinanceSource and the Movers universe fetch, so
    callers do not reach into the private `_real_download` implementation.
    """
    return _real_download(symbol, days)


def _select_close(df, symbol: str):
    cols = df.columns
    if hasattr(cols, "nlevels") and cols.nlevels > 1:
        if ("Close", symbol) in cols:
            return df[("Close", symbol)]
        close_cols = [c for c in cols if c[0] == "Close"]
        return df[close_cols[0]] if close_cols else None
    return df["Close"] if "Close" in cols else None


class YFinanceSource:
    name = "yfinance"

    def __init__(self, downloader: Downloader | None = None):
        self._downloader = downloader or _real_download

    def fetch(self, ctx) -> SourceResult:
        if is_offline():
            return self._offline()
        fields: dict[str, Field] = {}
        for sym in SYMBOLS:
            if not sym.yf:
                continue
            closes = self._downloader(sym.yf, 5)
            if closes:
                fields[sym.metric] = Field(metric=sym.metric, value=closes[-1], source="yfinance")
            else:
                fields[sym.metric] = Field(metric=sym.metric, value=None, source="missing")
        return SourceResult(name=self.name, fields=fields, health=SourceHealth.OK)

    def _offline(self) -> SourceResult:
        fields = {
            s.metric: Field(metric=s.metric, value=1.0, source="yfinance")
            for s in SYMBOLS if s.yf
        }
        return SourceResult(name=self.name, fields=fields, health=SourceHealth.OK)
