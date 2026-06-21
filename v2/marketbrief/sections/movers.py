from __future__ import annotations
from marketbrief.core.models import SectionVM, WhyLine
from marketbrief.sections._format import SECTION_TITLES, quiet_lead


class MoversSection:
    id = "movers"
    order = 5

    def build(self, ctx) -> SectionVM | None:
        # Best-effort (spec §7): show the winners/losers board only when the
        # universe screen produced real, ranked moves. A thin/empty/offline screen
        # leaves the board absent or empty, so the section degrades to quiet rather
        # than printing noise or fabricated names.
        board = getattr(ctx, "mover_board", None)
        if board is None or not board.has_rows:
            return SectionVM(id=self.id, title=SECTION_TITLES[self.id], order=self.order,
                             quiet=True, lead=quiet_lead(self.id))
        lead = WhyLine(
            text="Top three winners and losers across the tracked universe, by day, "
                 "week, and month.",
            source_url=None, hedged=True,
        )
        return SectionVM(id=self.id, title=SECTION_TITLES[self.id], order=self.order,
                         quiet=False, lead=lead, mover_board=board)

    def is_quiet(self, ctx) -> bool:
        board = getattr(ctx, "mover_board", None)
        return board is None or not board.has_rows
