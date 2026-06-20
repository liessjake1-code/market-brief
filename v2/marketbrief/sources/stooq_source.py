from __future__ import annotations
import csv
import io
from typing import Callable
from marketbrief.core.models import SourceResult, Field
from marketbrief.core.enums import SourceHealth
from marketbrief.core.symbols import SYMBOLS
from marketbrief.fetch.net import is_offline, REQUEST_TIMEOUT

Downloader = Callable[[str, int], list[float]]
STOOQ_BASE = "https://stooq.com/q/d/l/"


def _real_download(stooq_symbol: str, days: int) -> list[float]:
    """Stooq CSV closes oldest->newest, [] on any failure including quota body."""
    import requests

    try:
        resp = requests.get(STOOQ_BASE, params={"s": stooq_symbol, "i": "d"}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        text = resp.text
        if "Exceeded" in text or "Date,Open" not in text:
            return []
        reader = csv.DictReader(io.StringIO(text))
        closes = [float(row["Close"]) for row in reader if row.get("Close")]
        return closes[-days:] if days else closes
    except Exception:
        return []


class StooqSource:
    name = "stooq"

    def __init__(self, downloader: Downloader | None = None):
        self._downloader = downloader or _real_download

    def fetch(self, ctx) -> SourceResult:
        if is_offline():
            return self._offline()
        fields: dict[str, Field] = {}
        for sym in SYMBOLS:
            if not sym.stooq:
                continue
            closes = self._downloader(sym.stooq, 5)
            if closes:
                fields[sym.metric] = Field(metric=sym.metric, value=closes[-1], source="stooq")
            else:
                fields[sym.metric] = Field(metric=sym.metric, value=None, source="missing")
        return SourceResult(name=self.name, fields=fields, health=SourceHealth.OK)

    def _offline(self) -> SourceResult:
        fields = {
            s.metric: Field(metric=s.metric, value=1.0, source="stooq")
            for s in SYMBOLS if s.stooq
        }
        return SourceResult(name=self.name, fields=fields, health=SourceHealth.OK)
