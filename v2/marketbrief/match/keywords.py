"""Per-section keyword/ticker tables and the causal-verb regex (ported from v1
engine/matcher.py). Single source of truth: chain.py imports CAUSAL_RE from here."""
from __future__ import annotations
import re

SECTION_KEYWORDS: dict[str, list[str]] = {
    "us_equities": ["s&p", "nasdaq", "dow", "russell", "stocks", "equities",
                    "index", "rally", "selloff", "wall street", "shares"],
    "rates_and_dollar": ["yield", "treasury", "10-year", "2-year", "fed", "auction",
                          "dgs10", "rate", "dollar", "dxy", "basis points", "bps"],
    "commodities": ["oil", "crude", "wti", "opec", "gold", "barrel", "brent",
                    "energy", "bullion"],
    "washington": ["fed", "fomc", "powell", "tariff", "shutdown", "fiscal",
                   "congress", "white house", "trump", "regulation", "treasury dept"],
    "movers": ["surged", "plunged", "jumped", "tumbled", "earnings", "guidance",
               "upgrade", "downgrade", "shares"],
    "economic_data_scorecard": ["cpi", "inflation", "payrolls", "jobs", "gdp",
                                 "pce", "retail sales", "ism", "consumer", "data"],
    "earnings_on_deck": ["earnings", "reports", "quarterly", "results", "eps",
                         "guidance", "pre-open", "after close"],
    "watchlist": [],   # populated from config tickers at match time
    "crypto": ["bitcoin", "ethereum", "btc", "eth", "crypto", "token", "coin"],
    "volatility_breadth": ["vix", "volatility", "hedging", "fear", "breadth",
                           "advancers", "decliners"],
    "what_to_watch_today": ["today", "schedule", "due", "expected", "calendar"],
}

# Causal verbs/phrases that REQUIRE a cause_source_id (spec §5.6 / Part 4.5).
CAUSAL_RE = re.compile(
    r"\b(because|due to|on (?:soft|strong|weak|robust|the)|amid|after|as|driven by|"
    r"thanks to|owing to|spurred by|fueled by|on the back of)\b",
    re.IGNORECASE,
)
