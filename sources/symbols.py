"""Symbol and series mapping (spec §7 "Symbol and series mapping").

Maps each canonical metric key to its yfinance symbol and, where one exists, its
FRED series. Morning-primary source per metric is declared in engine.metrics
(FRED for Treasury yields, yfinance for the rest). Futures symbols are listed for
the pre-market snapshot (Phase 7); the settled recap uses the cash/index symbol.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SymbolMap:
    metric: str
    yf: Optional[str] = None     # yfinance cash/index symbol (None for FRED-only macro)
    yf_future: Optional[str] = None   # yfinance futures symbol (pre-market, Phase 7)
    fred: Optional[str] = None        # FRED series (primary for yields, cross-check for oil)
    fred_units: Optional[str] = None  # FRED units transform, e.g. "pc1" (YoY % change)


# Per spec §7 symbol table. Core fields for the health check are the four
# indices (or futures), the 10-year, WTI, and the dollar index.
SYMBOLS: tuple[SymbolMap, ...] = (
    SymbolMap("sp500", "^GSPC", "ES=F"),
    SymbolMap("nasdaq", "^IXIC", "NQ=F"),
    SymbolMap("dow", "^DJI", "YM=F"),
    SymbolMap("russell", "^RUT", "RTY=F"),
    SymbolMap("vix", "^VIX"),
    SymbolMap("wti", "CL=F", fred="DCOILWTICO"),       # yfinance primary, FRED cross-check (Decision 14)
    SymbolMap("gold", "GC=F"),
    SymbolMap("dxy", "DX-Y.NYB"),
    SymbolMap("ust10y", "^TNX", fred="DGS10"),          # FRED primary (spec §3.1)
    SymbolMap("ust2y", "^TNX", fred="DGS2"),            # FRED primary; yfinance has no clean 2y
    SymbolMap("btc", "BTC-USD"),
    SymbolMap("eth", "ETH-USD"),
    # --- Macro additions (all optional) -------------------------------------- #
    SymbolMap("copper", "HG=F"),                        # yfinance front-month copper future
    # Inflation as a RATE, not the index level: FRED's pc1 units transform returns
    # year-over-year percent change directly, so no manual YoY math (accuracy-safe).
    SymbolMap("cpi_yoy", fred="CPIAUCSL", fred_units="pc1"),
    SymbolMap("pce_yoy", fred="PCEPI", fred_units="pc1"),
    SymbolMap("fed_funds", fred="DFF"),                 # effective fed funds rate, daily
    SymbolMap("hy_spread", fred="BAMLH0A0HYM2"),        # ICE BofA US HY OAS (credit stress)
)

SYMBOLS_BY_METRIC: dict[str, SymbolMap] = {s.metric: s for s in SYMBOLS}

# Core fields the health check requires present + numeric (spec §7.5).
CORE_FIELDS: tuple[str, ...] = ("sp500", "nasdaq", "dow", "russell", "ust10y", "wti", "dxy")
