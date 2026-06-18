"""Second price source — Stooq (spec §7.5, Decision 18; roadmap §5.3).

A cloud-runner Yahoo block hits every field at once and FRED backstops only two,
so a second price source is core, not optional (Decision 18). Stooq is the
conventional free choice (CSV, no key) but best-effort: low undocumented daily
quota, CAPTCHA history, uneven futures/VIX coverage. It is used only when the
primary yfinance pull is missing.

Provider is config-selected (`second_price_provider`). Stooq is implemented here;
Twelve Data is left as a documented seam (it needs a key and does not cover
indices on the free tier, so it is not a drop-in for ^GSPC/^VIX).
"""

from __future__ import annotations

import csv
import io
from typing import Optional

import requests

STOOQ_BASE = "https://stooq.com/q/d/l/"
REQUEST_TIMEOUT = 15

# yfinance symbol -> Stooq symbol. Stooq uses its own conventions; only the
# symbols it reliably serves are mapped. Unmapped symbols return [] (no backup).
YF_TO_STOOQ: dict[str, str] = {
    "^GSPC": "^spx",
    "^IXIC": "^ndq",
    "^DJI": "^dji",
    "^RUT": "^rut",
    "DX-Y.NYB": "^dxy",
    "CL=F": "cl.f",
    "GC=F": "gc.f",
    "BTC-USD": "btcusd",
    "ETH-USD": "ethusd",
    # ^VIX coverage on Stooq is unreliable; intentionally unmapped.
}


def _fetch_csv(stooq_symbol: str, days: int) -> list[float]:
    """Pull daily closes oldest->newest from Stooq's CSV endpoint.

    Returns [] on any failure, including the "Exceeded the daily hits limit"
    quota body Stooq returns instead of data (spec §7.5). Never raises.
    """
    params = {"s": stooq_symbol, "i": "d"}
    try:
        resp = requests.get(STOOQ_BASE, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        text = resp.text
        if "Exceeded" in text or "Date,Open" not in text:
            return []  # quota tripped or not a data response
        reader = csv.DictReader(io.StringIO(text))
        closes = [float(row["Close"]) for row in reader if row.get("Close")]
        return closes[-days:] if days else closes
    except Exception:
        return []


def download(symbol: str, days: int) -> list[float]:
    """Downloader-compatible: yfinance symbol -> closes via Stooq, or [] if unmapped."""
    stooq_symbol = YF_TO_STOOQ.get(symbol)
    if not stooq_symbol:
        return []
    return _fetch_csv(stooq_symbol, days)
