from __future__ import annotations
import os

REQUEST_TIMEOUT = 15  # seconds; never hang the daily run on a slow provider


def is_offline() -> bool:
    """True when MARKET_BRIEF_OFFLINE is set truthy (test/offline seam)."""
    return os.environ.get("MARKET_BRIEF_OFFLINE", "").strip().lower() in ("1", "true", "yes")


def http_get(url: str, params: dict | None = None, *, headers: dict | None = None) -> str:
    """Real HTTP GET returning response text. Raises on HTTP error.

    Isolated here so sources inject a fake fetcher in tests and never hit network.
    """
    import requests

    resp = requests.get(url, params=params or {}, timeout=REQUEST_TIMEOUT, headers=headers or {})
    resp.raise_for_status()
    return resp.text
