"""yfinance pulls + resilient field assembly (spec §7, §7.5; roadmap §5).

yfinance is the single point of failure (spec §7.5), so this module:
  - pulls all symbols, carrying rolling history (for backfill + z-scores),
  - produces a Field per metric with its source and stale flag,
  - falls back to FRED for yields when yfinance is missing/NaN (clean for the
    settled recap, spec §7.5),
  - treats oil specially: prefer marking WTI stale over substituting a multi-day
    -old FRED print; FRED oil is only an explicitly date-stamped last resort
    (spec §7.5, Decision 14),
  - exposes a history fetcher for the Phase 2 first-run backfill, sourcing each
    metric's history from its morning-primary source.

The single network call is isolated in _download (injectable) so the resilience
and fallback logic is unit-testable offline.
"""

from __future__ import annotations

from typing import Callable, Optional

from engine.metrics import METRIC_KEYS, METRICS_BY_KEY, is_yield
from sources import fred
from sources.quality import Field, Source
from sources.symbols import SYMBOLS_BY_METRIC

# A downloader maps a yfinance symbol -> recent daily closes oldest->newest.
# Injected so tests never hit the network; the real one wraps yf.download.
Downloader = Callable[[str, int], list[float]]

BACKFILL_PAD = 40  # request extra days so ~25 trading closes survive holidays/gaps


def _download(symbol: str, days: int) -> list[float]:
    """Real yfinance pull: closing prices oldest->newest. Empty on any failure.

    Uses yf.download (yfinance==1.4.1) with progress off and auto_adjust on.
    Imported lazily so importing this module never forces yfinance at import time
    (keeps unit tests and --no-send stubs light).
    """
    try:
        import yfinance as yf

        df = yf.download(
            symbol,
            period=f"{max(days + BACKFILL_PAD, 60)}d",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        if df is None or df.empty:
            return []
        close = _select_close(df, symbol)
        if close is None:
            return []
        return [float(v) for v in close.dropna().tolist()]
    except Exception:
        return []


def _select_close(df, symbol: str):
    """Extract the Close series across yfinance frame shapes.

    yfinance==1.4.1 returns a MultiIndex column frame even for a single symbol:
    columns are ('Close', '<symbol>'). Older/other shapes use a flat 'Close'
    column. This handles both so a benign upstream shape change does not silently
    zero out every pull (the load-bearing-pin failure mode, spec §13).
    """
    cols = df.columns
    if hasattr(cols, "nlevels") and cols.nlevels > 1:
        # MultiIndex: prefer ('Close', symbol), else any ('Close', *) column.
        if ("Close", symbol) in cols:
            return df[("Close", symbol)]
        close_cols = [c for c in cols if c[0] == "Close"]
        return df[close_cols[0]] if close_cols else None
    return df["Close"] if "Close" in cols else None


def fetch_history(
    days: int,
    *,
    downloader: Optional[Downloader] = None,
    series_fetcher=None,
) -> dict[str, list[float]]:
    """History per metric for the Phase 2 backfill, from each morning-primary source.

    yields -> FRED (DGS10/DGS2), everything else -> yfinance (spec §5.5). Returns
    {metric_key: [closes oldest->newest]}; a failed pull yields [] for that key.
    """
    dl = downloader or _download
    out: dict[str, list[float]] = {}
    for key in METRIC_KEYS:
        sym = SYMBOLS_BY_METRIC[key]
        # FRED-sourced rate-like metrics (yields + the macro additions) seed from
        # FRED so the history basis matches the daily print; a FRED-only metric
        # (no yfinance symbol) always takes this path.
        if sym.fred and (is_yield(key) or not sym.yf):
            out[key] = fred.history(
                sym.fred, days, fetcher=series_fetcher, units=sym.fred_units,
            )
        elif sym.yf:
            out[key] = dl(sym.yf, days)
        else:
            out[key] = []
    return out


def _field_from_closes(metric: str, closes: list[float], source: Source) -> Field:
    if not closes:
        return Field(metric=metric, value=None, source=Source.MISSING)
    return Field(metric=metric, value=closes[-1], source=source)


def pull_fields(
    *,
    downloader: Optional[Downloader] = None,
    series_fetcher=None,
) -> dict[str, Field]:
    """Pull today's settled value per metric as Fields, with fallbacks (spec §7.5).

    - yields: FRED primary; yfinance ^TNX only if FRED is missing.
    - oil: yfinance primary; if missing, mark STALE (do not silently use lagging
      FRED). FRED oil is surfaced as a date-stamped last resort with a note.
    - everything else: yfinance; missing -> Field(MISSING).
    """
    dl = downloader or _download
    fields: dict[str, Field] = {}

    for key in METRIC_KEYS:
        sym = SYMBOLS_BY_METRIC[key]

        if is_yield(key) and sym.fred:
            fv = fred.latest_value(sym.fred, fetcher=series_fetcher, units=sym.fred_units)
            if fv is not None:
                fields[key] = Field(key, fv[1], Source.FRED, as_of=fv[0])
                continue
            # yfinance fallback only exists for the Treasury yields (^TNX); a
            # FRED-only macro metric simply degrades to MISSING (it is optional).
            if sym.yf:
                closes = dl(sym.yf, 5)
                fields[key] = _field_from_closes(key, closes, Source.YFINANCE)
            else:
                fields[key] = Field(key, None, Source.MISSING)
            continue

        if key == "wti":
            fields[key] = _pull_oil(dl, sym, series_fetcher)
            continue

        closes = dl(sym.yf, 5)
        fields[key] = _field_from_closes(key, closes, Source.YFINANCE)

    return fields


def _pull_oil(dl: Downloader, sym, series_fetcher) -> Field:
    """Oil: yfinance primary; mark stale over a lagging FRED print (Decision 14)."""
    closes = dl(sym.yf, 5)
    if closes:
        return Field("wti", closes[-1], Source.YFINANCE)
    # yfinance failed. Surface FRED only as an explicitly date-stamped last resort,
    # flagged stale, never as if it were yesterday's settle.
    if sym.fred:
        fv = fred.latest_value(sym.fred, fetcher=series_fetcher)
        if fv is not None:
            return Field(
                "wti", fv[1], Source.FRED_LAST_RESORT, stale=True, as_of=fv[0],
                note="FRED WTI lags several business days; shown as a dated last resort.",
            )
    return Field("wti", None, Source.MISSING, stale=True)
