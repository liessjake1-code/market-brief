from __future__ import annotations
from marketbrief.core.models import SectionVM
from marketbrief.sections._format import SECTION_TITLES, quiet_lead


class MoversSection:
    id = "movers"
    order = 5

    def build(self, ctx) -> SectionVM | None:
        # Best-effort: per-stock universe data is deferred; default to quiet
        # (spec §7 movers best-effort rule). Real rows arrive with the universe screen.
        return SectionVM(id=self.id, title=SECTION_TITLES[self.id], order=self.order,
                         quiet=True, lead=quiet_lead(self.id), movers=[])

    def is_quiet(self, ctx) -> bool:
        return True
