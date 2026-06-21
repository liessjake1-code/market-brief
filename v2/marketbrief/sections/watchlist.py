from __future__ import annotations
from marketbrief.core.enums import Direction
from marketbrief.core.models import SectionVM, MoverRow, WhyLine
from marketbrief.sections._format import SECTION_TITLES, quiet_lead
from marketbrief.sections._tickers import domain_for
from marketbrief.render.source_links import yahoo_ticker_url, favicon_url


class WatchlistSection:
    id = "watchlist"
    order = 8

    def build(self, ctx) -> SectionVM | None:
        tickers = list(ctx.config.watchlist)
        if not tickers:
            return SectionVM(id=self.id, title=SECTION_TITLES[self.id], order=self.order,
                             quiet=True, lead=quiet_lead(self.id), movers=[])
        rows = [MoverRow(ticker=t, favicon_url=favicon_url(domain_for(t)),
                         value_str="n/a", direction=Direction.FLAT, why="",
                         source_url=yahoo_ticker_url(t)) for t in tickers]
        lead = WhyLine(text="Your tracked names.", source_url=None, hedged=True)
        return SectionVM(id=self.id, title=SECTION_TITLES[self.id], order=self.order,
                         quiet=False, lead=lead, movers=rows)

    def is_quiet(self, ctx) -> bool:
        return not ctx.config.watchlist
