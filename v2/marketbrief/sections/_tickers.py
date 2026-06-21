from __future__ import annotations

# Minimal ticker->domain map for favicons (spec §6.5). Extend as the watchlist grows.
DOMAIN_BY_TICKER: dict[str, str] = {
    "AAPL": "apple.com", "MSFT": "microsoft.com", "NVDA": "nvidia.com",
    "AMZN": "amazon.com", "GOOGL": "abc.xyz", "META": "meta.com",
    "TSLA": "tesla.com", "JPM": "jpmorganchase.com", "XOM": "exxonmobil.com",
}


def domain_for(ticker: str) -> str | None:
    return DOMAIN_BY_TICKER.get(ticker.upper())
