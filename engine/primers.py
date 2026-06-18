"""The eleven section domain primers (spec §5.6 step 4; Part 4.6; roadmap §6.4).

One evergreen, author-controlled line per section, handed to the model as the
`primer`. These are the ONLY place structural knowledge enters, so they cannot go
stale. Verbatim from execution guide Part 4.6.
"""

from __future__ import annotations

PRIMERS: dict[str, str] = {
    "us_equities": (
        "The spread between indices signals the move's character: small-cap "
        "(Russell) leading means risk-on breadth; mega-cap (Nasdaq) leading "
        "alone is narrow."
    ),
    "rates_and_dollar": (
        "The 10-year is the main equity discount rate; the 2s10s spread is a "
        "growth/recession signal; a stronger dollar pressures commodities and "
        "exporters."
    ),
    "commodities": (
        "Oil is a real-time growth and inflation signal that feeds straight into "
        "rates and the Fed; gold is a fear and real-rate gauge."
    ),
    "washington": (
        "Policy is the standing risk backdrop; energy and Fed content here is "
        "usually the cause of the rates and commodities moves above it."
    ),
    "movers": (
        "Single-name moves are only meaningful above the volume floor; a large "
        "move on thin volume is noise."
    ),
    "economic_data_scorecard": (
        "What matters is the surprise versus expectations, not the absolute number."
    ),
    "earnings_on_deck": (
        "Pre-open and after-close reporters drive intraday volatility in their sector."
    ),
    "watchlist": (
        "These are the user's tracked names; relevance is personal, not market-wide."
    ),
    "crypto": (
        "BTC and ETH are a risk-appetite gut check that trades 24/7, so overnight "
        "moves preview the equity mood."
    ),
    "volatility_breadth": (
        "VIX rises into fear and falls into complacency; a low flat VIX means no "
        "hedging demand and little to read into."
    ),
    "what_to_watch_today": (
        "Pure schedule, not prediction; it lists known event times only."
    ),
}
