from __future__ import annotations
from pydantic import BaseModel, ConfigDict


class SymbolMap(BaseModel):
    model_config = ConfigDict(frozen=True)

    metric: str
    yf: str | None = None          # yfinance cash/index symbol
    yf_future: str | None = None   # yfinance futures symbol (pre-market, later)
    fred: str | None = None        # FRED series (primary for yields, cross-check oil)
    fred_units: str | None = None  # FRED units transform, e.g. "pc1" (YoY %)
    stooq: str | None = None       # Stooq backup symbol (best-effort)


# Ported verbatim from v1 sources/symbols.py + backup_prices.py YF_TO_STOOQ.
SYMBOLS: tuple[SymbolMap, ...] = (
    SymbolMap(metric="sp500", yf="^GSPC", yf_future="ES=F", stooq="^spx"),
    SymbolMap(metric="nasdaq", yf="^IXIC", yf_future="NQ=F", stooq="^ndq"),
    SymbolMap(metric="dow", yf="^DJI", yf_future="YM=F", stooq="^dji"),
    SymbolMap(metric="russell", yf="^RUT", yf_future="RTY=F", stooq="^rut"),
    SymbolMap(metric="vix", yf="^VIX"),
    SymbolMap(metric="wti", yf="CL=F", fred="DCOILWTICO", stooq="cl.f"),
    SymbolMap(metric="gold", yf="GC=F", stooq="gc.f"),
    SymbolMap(metric="dxy", yf="DX-Y.NYB", stooq="^dxy"),
    SymbolMap(metric="ust10y", yf="^TNX", fred="DGS10"),
    SymbolMap(metric="ust2y", yf="^TNX", fred="DGS2"),
    SymbolMap(metric="btc", yf="BTC-USD", stooq="btcusd"),
    SymbolMap(metric="eth", yf="ETH-USD", stooq="ethusd"),
    SymbolMap(metric="copper", yf="HG=F"),
    SymbolMap(metric="cpi_yoy", fred="CPIAUCSL", fred_units="pc1"),
    SymbolMap(metric="pce_yoy", fred="PCEPI", fred_units="pc1"),
    SymbolMap(metric="fed_funds", fred="DFF"),
    SymbolMap(metric="hy_spread", fred="BAMLH0A0HYM2"),
)

SYMBOLS_BY_METRIC: dict[str, SymbolMap] = {s.metric: s for s in SYMBOLS}
