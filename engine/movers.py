"""Movers selection: the best-effort gainers/losers rule (spec §7), pure.

yfinance has no clean free gainers/losers screener and pre-market volume is
thin, so raw percent moves are noisy. Movers is therefore best-effort, not a
headline guarantee:

  - Default: watchlist-movers-only. The section always has something honest to
    show from names you already track.
  - Upgrade: when the curated-universe screen is reliable on a given morning
    (enough of the configured universe returned data), upgrade to the fuller
    gainers-and-losers list.
  - Degrade: if the universe screen is unreliable, ship watchlist-only rather
    than print noise. This is the default, so a bad screen morning is a non-event.

The volume floor (config movers_min_volume) gates a universe name from being
headlined; watchlist names bypass it (they are yours to track regardless).

Pure: takes already-fetched StockQuotes + config, returns a ranked selection.
The fetch + its failures live in sources/stocks.py.
"""

from __future__ import annotations

from dataclasses import dataclass

from sources.stocks import StockQuote

MAX_MOVERS = 6              # top movers headlined per send (gainers + losers combined)
FLAT_PCT = 0.05            # |move| at or below this rounds to flat -> not a mover
# Fraction of the configured universe that must return data for the screen to be
# considered reliable enough to upgrade beyond watchlist-only.
UNIVERSE_RELIABLE_FRACTION = 0.5


@dataclass(frozen=True)
class MoverRow:
    """One selected mover: its quote plus the magnitude used for ranking."""

    ticker: str
    quote: StockQuote
    change_pct: float
    on_watchlist: bool


@dataclass(frozen=True)
class MoversSelection:
    """The ranked movers plus whether we fell back to watchlist-only."""

    movers: tuple[MoverRow, ...]
    watchlist_only: bool


def _universe_reliable(quotes: dict[str, StockQuote], universe: list[str]) -> bool:
    """True when enough of the configured universe came back to trust the screen."""
    if not universe:
        return False
    returned = sum(1 for t in universe if t in quotes)
    return returned >= len(universe) * UNIVERSE_RELIABLE_FRACTION


def select_movers(
    quotes: dict[str, StockQuote],
    *,
    watchlist: list[str],
    universe: list[str],
    min_volume: float,
) -> MoversSelection:
    """Select + rank movers per the spec §7 best-effort rule.

    Watchlist names are always eligible (bypassing the volume floor); curated
    universe names are eligible only when the screen is reliable AND they clear
    the volume floor. Names are ranked by absolute session move, flat names and
    names with no computable change are excluded, and the list is capped to
    MAX_MOVERS.
    """
    watchset = set(watchlist)
    reliable = _universe_reliable(quotes, universe)
    watchlist_only = not reliable

    # Candidate tickers: always the watchlist; add the universe only on a reliable
    # screen. De-duped (watchlist + universe overlap).
    candidates = list(watchlist)
    if reliable:
        candidates += [t for t in universe if t not in watchset]

    rows: list[MoverRow] = []
    for ticker in candidates:
        quote = quotes.get(ticker)
        if quote is None:
            continue
        change = quote.change_pct
        if change is None or abs(change) <= FLAT_PCT:
            continue  # flat or uncomputable -> never headlined
        on_watchlist = ticker in watchset
        # Volume floor gates universe names only; watchlist names are yours to track.
        if not on_watchlist and quote.volume is not None and quote.volume < min_volume:
            continue
        rows.append(MoverRow(ticker, quote, change, on_watchlist))

    rows.sort(key=lambda r: abs(r.change_pct), reverse=True)
    return MoversSelection(movers=tuple(rows[:MAX_MOVERS]), watchlist_only=watchlist_only)
