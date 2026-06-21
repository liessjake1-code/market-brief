from __future__ import annotations
import math
from marketbrief.core.models import SourceResult, Field
from marketbrief.core.config import Config
from marketbrief.core.symbols import SYMBOLS

_YIELDS = ("ust10y", "ust2y")
_OIL_LAST_RESORT_NOTE = (
    "FRED WTI lags several business days; shown as a dated last resort."
)


def _usable(field: Field | None) -> bool:
    if field is None or field.value is None:
        return False
    try:
        v = float(field.value)
    except (TypeError, ValueError):
        return False
    return not math.isnan(v)


def _get(per: dict[str, SourceResult], service: str, metric: str) -> Field | None:
    sr = per.get(service)
    if sr is None:
        return None
    return sr.fields.get(metric)


def _missing(metric: str, *, stale: bool = False) -> Field:
    return Field(metric=metric, value=None, source="missing", stale=stale)


def _resolve_yield(per, metric) -> Field:
    fred = _get(per, "fred", metric)
    if _usable(fred):
        return fred
    yf = _get(per, "yfinance", metric)
    if _usable(yf):
        return yf
    return _missing(metric)


def _resolve_oil(per) -> Field:
    yf = _get(per, "yfinance", "wti")
    if _usable(yf):
        return yf
    fred = _get(per, "fred", "wti")
    if _usable(fred):
        return Field(
            metric="wti", value=fred.value, source="fred_last_resort",
            stale=True, as_of=fred.as_of, note=_OIL_LAST_RESORT_NOTE,
        )
    return _missing("wti", stale=True)


def _resolve_other(per, metric) -> Field:
    yf = _get(per, "yfinance", metric)
    if _usable(yf):
        return yf
    stooq = _get(per, "stooq", metric)
    if _usable(stooq):
        return stooq
    return _missing(metric)


def resolve_fields(per_service: dict[str, SourceResult], config: Config) -> dict[str, Field]:
    """Merge per-service results into one Field per metric (pure, no I/O).

    Ports v1 prices.pull_fields + _pull_oil priority/fallback/oil rules verbatim.
    """
    out: dict[str, Field] = {}
    for sym in SYMBOLS:
        metric = sym.metric
        if metric in _YIELDS:
            out[metric] = _resolve_yield(per_service, metric)
        elif metric == "wti":
            out[metric] = _resolve_oil(per_service)
        else:
            out[metric] = _resolve_other(per_service, metric)
    return out
